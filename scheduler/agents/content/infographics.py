"""Infographics sub-agent — self-contained drafter.

Part of the 7-agent split (quick-260421-eoe). Filters
``content_agent.fetch_stories()`` to the infographic predicted_format and
drafts a tweet caption plus the paste-ready claude.ai render fields
(suggested_headline, data_facts, image_prompt). Writes a ContentBundle with
``content_type="infographic"``.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from anthropic import AsyncAnthropic

from agents import content_agent
from agents.brand_preamble import BRAND_PREAMBLE
from agents.content import _is_already_covered_today, run_text_story_cycle
from config import get_settings
from database import AsyncSessionLocal
from models.agent_run import AgentRun
from models.content_bundle import ContentBundle
from services.market_snapshot import fetch_market_snapshot, render_snapshot_block

logger = logging.getLogger(__name__)

CONTENT_TYPE: str = "infographic"
AGENT_NAME: str = "sub_infographics"

# ---------------------------------------------------------------------------
# Analytical-historical fallback — quick-260423-lvp
# ---------------------------------------------------------------------------

ANALYTICAL_HISTORICAL_QUERIES: list[str] = [
    "gold price performance during major wars historical",
    "gold bull markets historical analysis 1970-2025",
    "central bank gold purchases trends 2020-2025",
    "gold inflation correlation 50 years historical",
    "gold during recessions analysis 1973 2008 2020",
    "gold vs dollar weakness historical pattern",
    "safe haven asset performance gold historical",
    "gold ETF flows historical trends 2010-2025",
    "gold mining output decline historical analysis",
    "gold crisis performance historical comparison",
]


def _select_analytical_queries(shortfall: int, *, buffer: int = 2) -> list[str]:
    """Pick (shortfall + buffer) queries with a day-seeded deterministic shuffle.

    Rotation strategy (quick-260423-lvp): seed random.Random with
    date.today().toordinal() so every invocation on the same day returns the
    same list, but the list differs across consecutive days. Buffer compensates
    for fetches that return empty or get gold-gate-rejected.

    Clamped to len(ANALYTICAL_HISTORICAL_QUERIES).
    """
    import random as _random  # noqa: PLC0415
    from datetime import date as _date  # noqa: PLC0415

    count = min(shortfall + buffer, len(ANALYTICAL_HISTORICAL_QUERIES))
    rng = _random.Random(_date.today().toordinal())
    shuffled = list(ANALYTICAL_HISTORICAL_QUERIES)
    rng.shuffle(shuffled)
    return shuffled[:count]


async def _run_analytical_fallback(shortfall: int) -> int:
    """Second-phase fallback for sub_infographics — fetch analytical-historical
    stories and draft infographics to fill the daily 2-per-day target.

    Fires ONLY when the news phase returns items_queued < 2 (quick-260423-lvp).
    Uses the SAME _draft function as the news phase — no prompt edits.

    Writes a SEPARATE AgentRun row (agent_name=AGENT_NAME, notes includes
    phase='analytical_fallback') so telemetry is distinct from the news row.

    Returns the number of items queued by the fallback phase (0..shortfall).
    """
    if shortfall <= 0:
        return 0

    settings = get_settings()
    anthropic_client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    queries = _select_analytical_queries(shortfall)

    async with AsyncSessionLocal() as session:
        agent_run = AgentRun(
            agent_name=AGENT_NAME,
            status="running",
            started_at=datetime.now(timezone.utc),
            items_found=0,
            items_queued=0,
            items_filtered=0,
        )
        session.add(agent_run)
        await session.commit()

        items_queued = 0
        try:
            try:
                market_snapshot = await fetch_market_snapshot(session=session)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "%s analytical_fallback: market snapshot failed (%s)",
                    AGENT_NAME,
                    type(exc).__name__,
                )
                market_snapshot = None

            stories = await content_agent.fetch_analytical_historical_stories(queries)
            agent_run.items_found = len(stories)
            if not stories:
                agent_run.notes = json.dumps(
                    {
                        "phase": "analytical_fallback",
                        "shortfall": shortfall,
                        "queued": 0,
                    }
                )
                agent_run.status = "completed"
                return 0

            gate_config = {
                "content_gold_gate_enabled": "true",
                "content_gold_gate_model": "claude-haiku-4-5",
                "content_bearish_filter_enabled": "true",
            }

            for story in stories:
                if items_queued >= shortfall:
                    break
                try:
                    if await _is_already_covered_today(
                        session,
                        story["link"],
                        story["title"],
                        content_type=CONTENT_TYPE,
                    ):
                        continue

                    gate = await content_agent.is_gold_relevant_or_systemic_shock(
                        story,
                        gate_config,
                        client=anthropic_client,
                    )
                    if not gate["keep"]:
                        continue

                    article_text, fetch_ok = await content_agent.fetch_article(
                        story["link"],
                        fallback_text=story.get("summary", ""),
                    )
                    corroborating = await content_agent.search_corroborating(story["title"])
                    deep_research = {
                        "article_text": article_text[:5000],
                        "article_fetch_succeeded": fetch_ok,
                        "corroborating_sources": corroborating,
                        "key_data_points": [],
                    }

                    draft_content = await _draft(
                        story,
                        deep_research,
                        market_snapshot,
                        client=anthropic_client,
                    )
                    if draft_content is None:
                        continue

                    rationale = draft_content.pop("_rationale", "")
                    key_data_points = draft_content.pop("_key_data_points", [])
                    deep_research["key_data_points"] = key_data_points

                    review_result = await content_agent.review(draft_content)
                    compliance_ok = bool(review_result.get("compliance_passed", False))

                    bundle = ContentBundle(
                        story_headline=story["title"],
                        story_url=story["link"],
                        source_name=story.get("source_name"),
                        content_type=CONTENT_TYPE,
                        score=0.0,
                        deep_research=deep_research,
                        draft_content=draft_content,
                        compliance_passed=compliance_ok,
                    )
                    session.add(bundle)
                    await session.flush()

                    if compliance_ok:
                        item = content_agent.build_draft_item(bundle, rationale)
                        session.add(item)
                        await session.flush()
                        items_queued += 1
                        logger.info(
                            "%s analytical_fallback: queued '%s'",
                            AGENT_NAME,
                            story["title"][:60],
                        )
                except Exception as exc:
                    logger.error(
                        "%s analytical_fallback: error on story %r: %s",
                        AGENT_NAME,
                        story.get("title", "")[:60],
                        exc,
                        exc_info=True,
                    )

            agent_run.items_queued = items_queued
            agent_run.notes = json.dumps(
                {
                    "phase": "analytical_fallback",
                    "shortfall": shortfall,
                    "queued": items_queued,
                }
            )
            agent_run.status = "completed"
        except Exception as exc:
            agent_run.status = "failed"
            agent_run.errors = str(exc)
            logger.error("%s analytical_fallback failed: %s", AGENT_NAME, exc, exc_info=True)
        finally:
            agent_run.ended_at = datetime.now(timezone.utc)
            await session.commit()
    return items_queued


async def _draft(
    story: dict,
    deep_research: dict,
    market_snapshot: dict | None,
    *,
    client: AsyncAnthropic,
) -> dict | None:
    """Draft an infographic ContentBundle payload via Claude Sonnet."""
    article_text = deep_research.get("article_text", "")
    corroborating = deep_research.get("corroborating_sources", [])

    if corroborating:
        corr_lines = "\n".join(
            f"- {s.get('title', '')} ({s.get('source', '')}) — {s.get('snippet', '')}"
            for s in corroborating
        )
    else:
        corr_lines = "None found."

    article_block = (
        article_text
        if article_text
        else "Article text unavailable — use corroborating sources and headline."
    )

    snapshot_block = render_snapshot_block(market_snapshot) if market_snapshot else ""
    system_prompt = (
        f"{snapshot_block}\n\n"
        "You are a senior gold market analyst. Authoritative, inside-the-room perspective. "
        "Tone: Precise + punchy. Data-forward. Every sentence earns its place. "
        "Opening rule: First line is always the most impactful data point or fact. Lead with the number. "
        "Differentiation: Every draft must surface ONE non-obvious insight not in the original article — "
        "a pattern, implication, or comparison no one else made. "
        "You never mention Seva Mining. You never give financial advice. "
        "Produce an INFOGRAPHIC draft: a story with clear comparison, trend, or historical "
        "parallel with >=4 stats — better visualized than narrated. Produces a tweet caption "
        "plus three fields (suggested_headline, data_facts, image_prompt_direction) the "
        "operator will paste into claude.ai to render the visual."
    )
    user_prompt = f"""Based on the following research, produce an INFOGRAPHIC draft for X (Twitter).

## Story
Headline: {story.get("title", "")}
Source: {story.get("source_name", "")} ({story.get("link", "")})

## Full Article
{article_block}

## Corroborating Sources
{corr_lines}

## Instructions
1. Extract 5-8 key data points from the research.
2. Draft a 1-3 sentence tweet caption and the claude.ai render fields.
3. Provide a brief rationale for the format choice (1-2 sentences).

Respond in valid JSON with this structure:
{{
  "format": "infographic",
  "rationale": "...",
  "key_data_points": ["...", "..."],
  "draft_content": {{
    "format": "infographic",
    "twitter_caption": "1-3 sentences for X in senior analyst voice",
    "suggested_headline": "short editorial title for the artifact, ideally <=60 chars",
    "data_facts": ["1-5 key numbers, percentages, quotes, or data points the image should feature — each <=120 chars"],
    "image_prompt_direction": "2-4 sentences telling claude.ai what kind of visual to build: which chart type (bar / line / stat-callouts / comparison-table / timeline), what the X and Y axes should be, what specific numbers/labels to use, and what the visual hierarchy should be. DO NOT restate the brand palette or layout rules — those are applied automatically. Focus on the STORY-SPECIFIC visual direction."
  }}
}}"""

    try:
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```", 2)[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.rsplit("```", 1)[0].strip()
        parsed = json.loads(raw)
    except Exception as exc:
        logger.error("infographics._draft JSON parse failed: %s", exc)
        return None

    draft_content = parsed.get("draft_content", {}) or {}
    draft_content.setdefault("format", "infographic")

    # Build paste-ready image_prompt — parity with pre-split _research_and_draft
    # infographic handling.
    direction = str(draft_content.pop("image_prompt_direction", "")).strip()
    facts = draft_content.get("data_facts") or []
    if not isinstance(facts, list):
        facts = []
    draft_content["data_facts"] = facts[:5]
    headline = draft_content.get("suggested_headline", "")
    facts_block = "\n".join(f"- {f}" for f in draft_content["data_facts"])
    draft_content["image_prompt"] = (
        f"{BRAND_PREAMBLE}\n\n"
        f"HEADLINE FOR THIS VISUAL:\n{headline}\n\n"
        f"KEY FACTS TO FEATURE:\n{facts_block}\n\n"
        f"STORY-SPECIFIC DIRECTION:\n{direction}"
    )

    draft_content["_rationale"] = parsed.get("rationale", "")
    draft_content["_key_data_points"] = parsed.get("key_data_points", [])
    return draft_content


async def run_draft_cycle() -> None:
    """Two-phase pipeline — guarantees 2 infographics/day (quick-260423-lvp).

    Phase 1 (news): existing run_text_story_cycle with max_count=2, sort_by='score',
    dedup_scope='same_type' (per quick-260422-of3).

    Phase 2 (analytical-historical fallback): fires ONLY when phase 1 queued <2.
    Fetches via content_agent.fetch_analytical_historical_stories using a day-seeded
    rotation through ANALYTICAL_HISTORICAL_QUERIES. Runs stories through the SAME
    _draft function — no prompt changes.

    Configured per quick-260422-of3:
    - max_count=2: produce the 2 best infographics per day (D-04)
    - sort_by='score': pick best by quality/score (D-01)
    - dedup_scope='same_type': allow reuse of breaking_news stories (D-02)
    """
    news_items_queued = await run_text_story_cycle(
        agent_name=AGENT_NAME,
        content_type=CONTENT_TYPE,
        draft_fn=_draft,
        max_count=2,
        sort_by="score",
        dedup_scope="same_type",
    )
    if news_items_queued < 2:
        shortfall = 2 - news_items_queued
        analytical_queued = await _run_analytical_fallback(shortfall=shortfall)
        logger.info(
            "%s: two-phase summary — news=%d, analytical=%d, total=%d",
            AGENT_NAME,
            news_items_queued,
            analytical_queued,
            news_items_queued + analytical_queued,
        )
    else:
        logger.info(
            "%s: news phase queued %d items — fallback skipped",
            AGENT_NAME,
            news_items_queued,
        )
