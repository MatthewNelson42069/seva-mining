"""Gold History sub-agent — online SerpAPI fetch + article-text fact source (quick-260424-e37).

Partially unwinds quick-260422-lbb (curated whitelist + Claude-from-training-data +
SerpAPI snippet-verify model). Reuses the day-seeded-shuffle + fetch-helper pattern from
quick-260423-lvp (sub_infographics analytical-historical fallback).

**Online-fetch model** (quick-260424-e37):
  1. ``_select_historical_gold_queries(count=3)`` picks 3 queries via a day-seeded
     deterministic shuffle of the 12-item ``HISTORICAL_GOLD_QUERIES`` list.
  2. ``content_agent.fetch_analytical_historical_stories(queries)`` fetches up to
     ~15 candidate articles via SerpAPI (5 results per query × 3 queries).
  3. Candidates are deduped against ``Config.gold_history_used_urls`` (all-time
     canonicalized URL set, replaces slug-based ``gold_history_used_topics``).
  4. Each fresh candidate passes the existing Haiku gold gate
     (``is_gold_relevant_or_systemic_shock``).
  5. ``content_agent.fetch_article(url)`` fetches the full article body.
  6. ``_draft_gold_history(article_text, headline, url, source_name)`` drafts via
     Sonnet using ``article_text`` as the sole authoritative fact source.
  7. ``content_agent.review()`` runs the Haiku compliance gate.
  8. ContentBundle + DraftItem are persisted. Loop breaks on first success
     (items-per-run cap = 1, CONTEXT Q5-A).

Cadence and cron are unchanged: every other day at 12:00 America/Los_Angeles via
CronTrigger(day='*/2', hour=12, minute=0, timezone='America/Los_Angeles')
(quick-260422-vxg). Advisory lock 1016 preserved in scheduler/worker.py.
DOES call ``content_agent.review()`` inline before writing each bundle.

Requirements: CONT-07, CONT-14, CONT-15, CONT-16, CONT-17.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from anthropic import AsyncAnthropic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agents import content_agent
from config import get_settings
from database import AsyncSessionLocal
from models.agent_run import AgentRun
from models.config import Config
from models.content_bundle import ContentBundle

logger = logging.getLogger(__name__)

CONTENT_TYPE: str = "gold_history"
AGENT_NAME: str = "sub_gold_history"

# Gold History is curated content — fixed baseline score (parity with pre-split).
GOLD_HISTORY_SCORE = 8.0

# ---------------------------------------------------------------------------
# Online-fetch plumbing (quick-260424-e37) — replaces curated JSON pool.
# ---------------------------------------------------------------------------

HISTORICAL_GOLD_QUERIES: list[str] = [
    "famous gold rushes in history",
    "gold standard history Bretton Woods Nixon",
    "biggest gold mining discoveries historical",
    "historical gold price cycles 1970s 1980s",
    "central bank gold repatriation Germany Venezuela history",
    "gold mining disasters historical events",
    "Hunt brothers silver gold corner 1980",
    "Klondike Yukon gold rush history",
    "Witwatersrand South Africa gold discovery 1886",
    "gold confiscation Roosevelt executive order 6102",
    "SPDR Gold ETF GLD launch history",
    "LBMA gold fix scandal history",
]


def _canonicalize_url(url: str) -> str:
    """Canonicalize a URL for all-time dedup.

    Rule (quick-260424-e37): lowercase, strip the query string (and fragment),
    strip any trailing slash. Idempotent. Pure function — easy to unit test.
    """
    lowered = url.lower()
    # split off query + fragment at the first '?' or '#'
    for sep in ("?", "#"):
        if sep in lowered:
            lowered = lowered.split(sep, 1)[0]
    return lowered.rstrip("/")


def _select_historical_gold_queries(count: int = 3) -> list[str]:
    """Pick `count` queries with a day-seeded deterministic shuffle.

    Rotation strategy (quick-260424-e37): seed random.Random with
    date.today().toordinal() so every invocation on the same day returns the
    same list, but the list differs across consecutive days. Clamped to
    len(HISTORICAL_GOLD_QUERIES). Mirrors sub_infographics._select_analytical_queries
    (quick-260423-lvp) — same day-seeded pattern, zero shared state.
    """
    import random as _random  # noqa: PLC0415 — local import keeps module surface minimal
    from datetime import date as _date  # noqa: PLC0415

    count = min(count, len(HISTORICAL_GOLD_QUERIES))
    rng = _random.Random(_date.today().toordinal())
    shuffled = list(HISTORICAL_GOLD_QUERIES)
    rng.shuffle(shuffled)
    return shuffled[:count]


async def _get_used_urls(session: AsyncSession) -> set[str]:
    """Read the all-time used-URL dedup set from Config.

    Key: 'gold_history_used_urls' (quick-260424-e37; replaces slug-based
    'gold_history_used_topics' from 260422-lbb — old key left dormant).
    Returns a set of already-canonicalized URL strings. Empty set if the
    key is missing or the stored value cannot be JSON-decoded.
    """
    result = await session.execute(select(Config).where(Config.key == "gold_history_used_urls"))
    row = result.scalar_one_or_none()
    if row is None:
        return set()
    try:
        data = json.loads(row.value)
        if isinstance(data, list):
            return set(data)
        return set()
    except (json.JSONDecodeError, TypeError):
        return set()


async def _record_used_url(session: AsyncSession, url: str) -> None:
    """Canonicalize `url` and append to the used-URL dedup set in Config.

    No-ops if already present. Upserts the Config row. Caller commits.
    """
    canonical = _canonicalize_url(url)
    existing = await _get_used_urls(session)
    if canonical in existing:
        return
    existing.add(canonical)
    result = await session.execute(select(Config).where(Config.key == "gold_history_used_urls"))
    row = result.scalar_one_or_none()
    payload = json.dumps(sorted(existing))
    if row is None:
        session.add(Config(key="gold_history_used_urls", value=payload))
    else:
        row.value = payload


async def _draft_gold_history(
    *,
    article_text: str,
    headline: str,
    url: str,
    source_name: str,
    client: AsyncAnthropic,
) -> dict | None:
    """Draft a gold_history ContentBundle via Claude Sonnet.

    Operates on the fetched article body (``article_text``) as the single
    authoritative fact source (quick-260424-e37 replaces the curated
    verified_facts/sources JSON shape from 260422-lbb). The drafter is
    instructed to use only claims that literally appear in ``article_text``.
    Drama-first narrative voice and 5-7 tweet thread / 4-7 slide carousel
    structure are preserved.

    Returns the parsed draft dict (with the required top-level ``sources``
    field populated from the single fetched ``url``/``source_name``), or None
    on parse/API failure.
    """
    system_prompt = (
        "You are a senior gold analyst and dramatic historian. "
        "Your storytelling is drama-first: lead with the most dramatic moment — "
        "the audacity, the risk, the payoff. Every sentence earns its place. "
        "No financial advice. No mention of Seva Mining. Return only valid JSON — "
        "no markdown, no prose outside the JSON structure.\n\n"
        "**FACT FIDELITY (CRITICAL):** Base every specific claim (names, dates, "
        "dollar figures, place names, other specifics) on statements LITERALLY "
        "PRESENT in `article_text` below. Do NOT fill in details from general "
        "historical knowledge. Narrative connective tissue ('this was shocking "
        "because', 'the stakes could not have been higher') is allowed. New "
        "specifics are NOT allowed. If `article_text` is thin, write a THINNER "
        "thread rather than embellishing — brevity over fabrication."
    )
    user_prompt = (
        f"Headline: {headline}\n"
        f"Source: {source_name}  ({url})\n\n"
        f"Article text (your single authoritative fact source):\n{article_text}\n\n"
        "Instagram design system: background #F0ECE4 (warm cream), "
        "text #0C1B32 (deep navy), gold accent #D4AF37 (metallic gold). "
        "a16z minimalist aesthetic. One key moment per slide. Max 15 words per slide body. "
        "Gold accent on 1-2 elements per slide.\n\n"
        "Return JSON with this exact structure:\n"
        "{\n"
        '  "format": "gold_history",\n'
        '  "story_title": "short editorial title (\u226460 chars)",\n'
        '  "story_slug": "kebab-case-title-slug",\n'
        '  "tweets": ["hook tweet", "tweet 2", "tweet 3", "tweet 4", "tweet 5"],\n'
        '  "instagram_carousel": [\n'
        '    {"slide": 1, "headline": "...", "body": "...(max 15 words)...", "visual_note": "..."},\n'
        '    {"slide": 2, "headline": "...", "body": "...", "visual_note": "..."}\n'
        "  ],\n"
        '  "instagram_caption": "full caption text",\n'
        '  "sources": [{"ref": "[1]", "url": "' + url + '", "publisher": "' + source_name + '"}]\n'
        "}\n\n"
        "Tweets: 5-7, hook tweet first (most dramatic moment). "
        "Carousel: 4-7 slides, one moment per slide. "
        "Sources: always a single-element list echoing the source URL above."
    )

    try:
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        data = json.loads(raw)
        required = (
            "format",
            "story_title",
            "story_slug",
            "tweets",
            "instagram_carousel",
            "instagram_caption",
            "sources",
        )
        if not all(k in data for k in required):
            logger.warning(
                "%s: _draft_gold_history missing required keys in response (got: %s)",
                AGENT_NAME,
                list(data.keys()),
            )
            return None
        return data
    except (json.JSONDecodeError, KeyError, IndexError) as exc:
        logger.warning("%s: _draft_gold_history parse failure — %s", AGENT_NAME, exc)
        return None
    except Exception as exc:
        logger.error(
            "%s: _draft_gold_history Claude call failed — %s",
            AGENT_NAME,
            exc,
            exc_info=True,
        )
        return None


async def run_draft_cycle() -> None:
    """Single-tick online-fetch pipeline (quick-260424-e37).

    Flow: fetch 3 SerpAPI queries → dedup by URL → gold gate (Haiku) → fetch
    article body → draft (Sonnet) → review (Haiku) → persist ContentBundle +
    DraftItem. Loop breaks on the first successful queue (items-per-run = 1,
    CONTEXT Q5-A). Every-other-day cadence (12:00 PT) and advisory-lock 1016
    are unchanged — this module is called from scheduler/worker.py exactly
    as before.

    Structured notes payload (CONTEXT Q9):
      candidates_fetched, after_dedup, gold_gate_passed, drafted,
      review_passed, queued, skipped_no_serpapi, skipped_insufficient_candidates.
    """
    settings = get_settings()

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

        notes: dict = {
            "candidates_fetched": 0,
            "after_dedup": 0,
            "gold_gate_passed": 0,
            "drafted": 0,
            "review_passed": 0,
            "queued": 0,
            "skipped_no_serpapi": False,
            "skipped_insufficient_candidates": False,
        }

        try:
            if not settings.serpapi_api_key:
                logger.warning("%s: SerpAPI key missing — skipping cycle", AGENT_NAME)
                notes["skipped_no_serpapi"] = True
                agent_run.status = "completed"
                return

            anthropic_client = AsyncAnthropic(api_key=settings.anthropic_api_key)
            queries = _select_historical_gold_queries(count=3)
            stories = await content_agent.fetch_analytical_historical_stories(queries)
            notes["candidates_fetched"] = len(stories)
            agent_run.items_found = len(stories)

            used_urls = await _get_used_urls(session)
            fresh_candidates = [
                s
                for s in stories
                if _canonicalize_url(s.get("link", "")) not in used_urls and s.get("link")
            ]
            notes["after_dedup"] = len(fresh_candidates)

            if not fresh_candidates:
                notes["skipped_insufficient_candidates"] = True
                agent_run.status = "completed"
                return

            gate_config = {
                "content_gold_gate_enabled": "true",
                "content_gold_gate_model": "claude-haiku-4-5",
                "content_bearish_filter_enabled": "true",
            }

            queued = 0
            for story in fresh_candidates:
                if queued >= 1:
                    break
                try:
                    gate = await content_agent.is_gold_relevant_or_systemic_shock(
                        story, gate_config, client=anthropic_client
                    )
                    if not gate["keep"]:
                        continue
                    notes["gold_gate_passed"] += 1

                    article_text, _fetch_ok = await content_agent.fetch_article(
                        story["link"], fallback_text=story.get("summary", "")
                    )
                    if not article_text:
                        article_text = story.get("summary", "") or story.get("title", "")

                    draft_content = await _draft_gold_history(
                        article_text=article_text[:8000],
                        headline=story.get("title", ""),
                        url=story["link"],
                        source_name=story.get("source_name", "unknown"),
                        client=anthropic_client,
                    )
                    if draft_content is None:
                        continue
                    notes["drafted"] += 1

                    review_result = await content_agent.review(draft_content)
                    compliance_ok = bool(review_result.get("compliance_passed", False))

                    bundle = ContentBundle(
                        story_headline=story.get("title", ""),
                        story_url=story["link"],
                        source_name=story.get("source_name"),
                        content_type=CONTENT_TYPE,
                        no_story_flag=False,
                        score=GOLD_HISTORY_SCORE,
                        deep_research={
                            "article_text": article_text[:5000],
                            "source_url": story["link"],
                            "source_name": story.get("source_name"),
                        },
                        draft_content=draft_content,
                        compliance_passed=compliance_ok,
                    )
                    session.add(bundle)
                    await session.flush()

                    # Record the URL regardless of compliance outcome — we
                    # do not want to retry the same article after a failed
                    # review. (Matches 260422-lbb's slug-record-on-failure
                    # semantics.)
                    await _record_used_url(session, story["link"])

                    if not compliance_ok:
                        logger.warning(
                            "%s: compliance blocked %r — %s",
                            AGENT_NAME,
                            story.get("title", "")[:60],
                            review_result.get("rationale"),
                        )
                        continue
                    notes["review_passed"] += 1

                    rationale = (
                        f"Gold History: {story.get('title', '')}. "
                        f"Drawn from {story.get('source_name', 'source')}."
                    )
                    item = content_agent.build_draft_item(bundle, rationale)
                    session.add(item)
                    await session.flush()

                    queued += 1
                    logger.info(
                        "%s: queued %r (bundle_id=%s)",
                        AGENT_NAME,
                        story.get("title", "")[:60],
                        bundle.id,
                    )
                except Exception as story_exc:
                    logger.error(
                        "%s: error on story %r: %s",
                        AGENT_NAME,
                        story.get("title", "")[:60],
                        story_exc,
                        exc_info=True,
                    )

            notes["queued"] = queued
            agent_run.items_queued = queued
            if queued == 0:
                notes["skipped_insufficient_candidates"] = True
            agent_run.status = "completed"

        except Exception as exc:
            agent_run.status = "failed"
            agent_run.errors = str(exc)
            logger.error("%s run failed: %s", AGENT_NAME, exc, exc_info=True)
        finally:
            agent_run.ended_at = datetime.now(timezone.utc)
            agent_run.notes = json.dumps(notes)
            await session.commit()
