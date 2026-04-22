"""Gold History sub-agent — curated-whitelist historical storytelling (quick-260422-lbb).

Part of the 7-agent split (quick-260421-eoe). Unlike the 5 text-story sub-agents,
gold_history does NOT call ``content_agent.fetch_stories()``: it has its own curated
historical-story whitelist stored as pre-researched JSON fact sheets in the
``gold_history_stories/`` directory (one file per canonical story, named by slug).

**Curated-whitelist model** (replaces the previous Claude-from-memory picker):
  1. Stories are pre-researched and committed as JSON fact sheets in
     ``scheduler/agents/content/gold_history_stories/``.
  2. ``_pick_fresh_slug`` selects a random unused slug from the whitelist filtered
     against ``gold_history_used_topics`` — no Claude call needed for story selection.
  3. ``_draft_gold_history`` receives the full fact sheet and is locked to the
     ``verified_facts`` list by an explicit FACT FIDELITY clause.
  4. The runtime never calls SerpAPI — facts are pre-verified at commit time
     (per decisions D-01 through D-05 in quick-260422-lbb CONTEXT.md).

Runs every other day at 12:00 America/Los_Angeles via
CronTrigger(day='*/2', hour=12, minute=0, timezone='America/Los_Angeles')
(quick-260422-vxg). Retires the standalone ``scheduler/agents/gold_history_agent.py``
module. DOES call ``content_agent.review()`` inline before writing each bundle.

Requirements: CONT-07, CONT-14, CONT-15, CONT-16, CONT-17.
"""
from __future__ import annotations

import json
import logging
import random
from datetime import datetime, timezone

from anthropic import AsyncAnthropic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agents import content_agent
from agents.content.gold_history_stories import load_all_stories, load_fact_sheet
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


async def _get_used_topics(session: AsyncSession) -> list[str]:
    """Read used Gold History story slugs from Config.

    Returns a list of slug strings. Returns empty list if key is missing or
    the value cannot be parsed as JSON. (EXP-6)
    """
    result = await session.execute(
        select(Config).where(Config.key == "gold_history_used_topics")
    )
    row = result.scalar_one_or_none()
    if row is None:
        return []
    try:
        return json.loads(row.value)
    except (json.JSONDecodeError, TypeError):
        return []


async def _add_used_topic(session: AsyncSession, slug: str) -> None:
    """Append a story slug to the used topics list in Config.

    No-ops if slug is already present. Upserts the Config row with the
    updated JSON-encoded list. Caller is responsible for committing. (EXP-6)
    """
    topics = await _get_used_topics(session)
    if slug not in topics:
        topics.append(slug)
    result = await session.execute(
        select(Config).where(Config.key == "gold_history_used_topics")
    )
    row = result.scalar_one_or_none()
    if row is None:
        session.add(Config(
            key="gold_history_used_topics",
            value=json.dumps(topics),
        ))
    else:
        row.value = json.dumps(topics)


def _pick_fresh_slug(used_topics: list[str], whitelist: list[dict]) -> str | None:
    """Return a random story slug from the whitelist that has not yet been used.

    Filters ``whitelist`` to entries whose ``story_slug`` is NOT in
    ``used_topics``, then returns a random selection. Uses ``random.choice``
    so the same story isn't always picked first — avoids deterministic
    "always starts at the top" behaviour across repeated whitelist additions.

    Returns None if every whitelisted slug has been used (whitelist exhausted).
    Pure function — no I/O, no async. Easy to unit test.
    """
    fresh = [s for s in whitelist if s.get("story_slug") not in used_topics]
    if not fresh:
        return None
    return random.choice(fresh)["story_slug"]


def _load_fact_sheet(slug: str) -> dict | None:
    """Thin wrapper around the loader's ``load_fact_sheet`` helper.

    Keeps the underscore-helper pattern consistent with gold_history.py's
    other private helpers so callers can mock ``gold_history._load_fact_sheet``
    in tests without patching the loader module directly.

    Returns the validated fact-sheet dict, or None if the slug is unknown.
    """
    return load_fact_sheet(slug)


async def _draft_gold_history(
    fact_sheet: dict,
    *,
    client: AsyncAnthropic,
) -> dict | None:
    """Draft a gold_history ContentBundle via Claude Sonnet.

    Takes the full fact_sheet dict (including verified_facts and sources).
    The drafter is locked to the verified_facts list by the FACT FIDELITY
    clause — it may reorder facts for dramatic pacing but may NOT invent
    new names, dates, dollar figures, place names, or other specifics.

    Uses a drama-first storytelling prompt. Produces a 5-7 tweet thread and
    a 4-7 slide Instagram carousel following the brand design system:
    background #F0ECE4 (warm cream), text #0C1B32 (deep navy),
    gold accent #D4AF37 (metallic gold).

    Returns the parsed draft dict (which includes a top-level ``sources``
    field mirrored from the fact sheet), or None on parse/API failure.
    """
    story_title = fact_sheet["story_title"]
    story_slug = fact_sheet["story_slug"]
    summary = fact_sheet.get("summary", "")
    recommended_arc = fact_sheet.get("recommended_arc", "")
    verified_facts = fact_sheet.get("verified_facts", [])
    sources = fact_sheet.get("sources", [])

    facts_block = "\n".join(
        f"- {f['claim']}  [source: {f['source_url']}]"
        for f in verified_facts
    )

    sources_block = "\n".join(
        f"  {s.get('ref', '')} {s.get('publisher', s.get('url', ''))} — {s.get('url', '')}"
        for s in sources
    )

    system_prompt = (
        "You are a senior gold analyst and dramatic historian. "
        "Your storytelling is drama-first: lead with the most dramatic moment — "
        "the audacity, the risk, the payoff. Every sentence earns its place. "
        "No financial advice. No mention of Seva Mining. Return only valid JSON — "
        "no markdown, no prose outside the JSON structure.\n\n"
        "**FACT FIDELITY (CRITICAL):** You may only use names, dates, dollar figures, "
        "place names, and other specifics that appear EXPLICITLY in the `verified_facts` "
        "list below. Do NOT invent or infer any new specifics. Narrative connective "
        "tissue (\"this was shocking because\", \"the stakes couldn't have been higher\") "
        "is allowed. New specifics are NOT allowed. If you need a specific detail the "
        "facts don't provide, write the sentence without it — do not fabricate."
    )

    user_prompt = (
        f"Story: {story_title}\n"
        f"Slug: {story_slug}\n\n"
        f"Summary / hook: {summary}\n\n"
        f"Recommended story arc: {recommended_arc}\n\n"
        f"Verified facts (use ONLY these specifics — do not invent):\n{facts_block}\n\n"
        f"Sources (copy verbatim into the output `sources` field):\n{sources_block}\n\n"
        "Instagram design system: background #F0ECE4 (warm cream), "
        "text #0C1B32 (deep navy), gold accent #D4AF37 (metallic gold). "
        "a16z minimalist aesthetic. One key moment per slide. Max 15 words per slide body. "
        "Gold accent on 1-2 elements per slide.\n\n"
        "Return JSON with this exact structure:\n"
        "{\n"
        '  "format": "gold_history",\n'
        f'  "story_title": "{story_title}",\n'
        f'  "story_slug": "{story_slug}",\n'
        '  "tweets": ["hook tweet", "tweet 2", "tweet 3", "tweet 4", "tweet 5"],\n'
        '  "instagram_carousel": [\n'
        '    {"slide": 1, "headline": "...", "body": "...(max 15 words)...", "visual_note": "..."},\n'
        '    {"slide": 2, "headline": "...", "body": "...", "visual_note": "..."}\n'
        '  ],\n'
        '  "instagram_caption": "full caption text",\n'
        '  "sources": [{"ref": "[1]", "url": "...", "publisher": "..."}]\n'
        "}\n\n"
        "Tweets: 5-7, hook tweet first (most dramatic moment). "
        "Carousel: 4-7 slides, one moment per slide. "
        "Sources: copy the full sources list from the fact sheet above."
    )

    try:
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=system_prompt,
            messages=[{
                "role": "user",
                "content": user_prompt,
            }],
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        data = json.loads(raw)
        required = (
            "format", "story_title", "story_slug",
            "tweets", "instagram_carousel", "instagram_caption",
            "sources",
        )
        if not all(k in data for k in required):
            logger.warning(
                "%s: _draft_gold_history missing required keys in response (got: %s)",
                AGENT_NAME, list(data.keys()),
            )
            return None
        return data
    except (json.JSONDecodeError, KeyError, IndexError) as exc:
        logger.warning("%s: _draft_gold_history parse failure — %s", AGENT_NAME, exc)
        return None
    except Exception as exc:
        logger.error(
            "%s: _draft_gold_history Claude call failed — %s",
            AGENT_NAME, exc, exc_info=True,
        )
        return None


async def run_draft_cycle() -> None:
    """Single-tick pipeline: pick fresh slug → load fact sheet → draft → review → write.

    Does NOT call ``content_agent.fetch_stories()`` — gold_history has its own
    curated historical-story source. DOES call ``content_agent.review()`` inline
    before writing each bundle. Whitelist exhaustion triggers a no-story-flag
    bundle (does NOT call Claude at all). The runtime never instantiates a SerpAPI
    client — runtime verification was removed in quick-260422-lbb.
    """
    settings = get_settings()
    anthropic_client = AsyncAnthropic(api_key=settings.anthropic_api_key)

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

        try:
            used_topics = await _get_used_topics(session)
            logger.info(
                "%s: %d stories already used, loading whitelist",
                AGENT_NAME, len(used_topics),
            )

            whitelist = load_all_stories()
            slug = _pick_fresh_slug(used_topics, whitelist)

            if slug is None:
                logger.info(
                    "%s: whitelist exhausted (%d slugs used, %d in whitelist) — no bundle created",
                    AGENT_NAME, len(used_topics), len(whitelist),
                )
                bundle = ContentBundle(
                    story_headline="Gold History: all curated stories used",
                    content_type=CONTENT_TYPE,
                    no_story_flag=True,
                    score=0.0,
                )
                session.add(bundle)
                agent_run.notes = json.dumps({"reason": "whitelist_exhausted"})
                agent_run.status = "completed"
                return

            fact_sheet = _load_fact_sheet(slug)
            if fact_sheet is None:
                # Belt-and-braces: slug came from whitelist so this shouldn't happen,
                # but handle gracefully if the JSON file is missing at runtime.
                logger.error(
                    "%s: fact sheet for slug %r not found — treating as draft failure",
                    AGENT_NAME, slug,
                )
                bundle = ContentBundle(
                    story_headline=f"Gold History: {slug}",
                    content_type=CONTENT_TYPE,
                    no_story_flag=False,
                    score=0.0,
                    deep_research={"story_slug": slug, "reason": "fact_sheet_load_failed"},
                    compliance_passed=False,
                )
                session.add(bundle)
                agent_run.notes = json.dumps({"reason": "fact_sheet_load_failed", "story_slug": slug})
                agent_run.status = "completed"
                return

            story_title = fact_sheet["story_title"]
            logger.info(
                "%s: picked story %r (slug=%s)",
                AGENT_NAME, story_title[:60], slug,
            )
            agent_run.items_found = 1

            draft_content = await _draft_gold_history(fact_sheet, client=anthropic_client)
            if draft_content is None:
                logger.error("%s: drafting failed for %r", AGENT_NAME, story_title[:60])
                bundle = ContentBundle(
                    story_headline=story_title,
                    content_type=CONTENT_TYPE,
                    no_story_flag=False,
                    score=0.0,
                    deep_research={
                        "story_slug": slug,
                        "sources": fact_sheet["sources"],
                    },
                    compliance_passed=False,
                )
                session.add(bundle)
                await _add_used_topic(session, slug)
                agent_run.notes = json.dumps({
                    "reason": "draft_failed",
                    "story_slug": slug,
                })
                agent_run.status = "completed"
                return

            review_result = await content_agent.review(draft_content)
            compliance_ok = bool(review_result.get("compliance_passed", False))

            bundle = ContentBundle(
                story_headline=story_title,
                content_type=CONTENT_TYPE,
                no_story_flag=False,
                score=GOLD_HISTORY_SCORE,
                deep_research={
                    "story_slug": slug,
                    "sources": fact_sheet["sources"],
                },
                draft_content=draft_content,
                compliance_passed=compliance_ok,
            )
            session.add(bundle)
            await session.flush()

            await _add_used_topic(session, slug)

            if not compliance_ok:
                logger.warning(
                    "%s: compliance blocked gold_history %r — reason=%s",
                    AGENT_NAME, story_title[:60], review_result.get("rationale"),
                )
                agent_run.notes = json.dumps({
                    "reason": "compliance_failed",
                    "story_slug": slug,
                    "story_title": story_title,
                })
                agent_run.status = "completed"
                return

            fact_count = len(fact_sheet.get("verified_facts", []))
            source_count = len(fact_sheet.get("sources", []))
            rationale = (
                f"Gold History: {story_title}. "
                f"Grounded in {fact_count} pre-verified facts from {source_count} sources."
            )
            item = content_agent.build_draft_item(bundle, rationale)
            session.add(item)
            await session.flush()

            agent_run.items_queued = 1
            agent_run.notes = json.dumps({
                "story_title": story_title,
                "story_slug": slug,
                "fact_count": fact_count,
                "source_count": source_count,
                "content_bundle_id": str(bundle.id),
            })
            agent_run.status = "completed"
            logger.info(
                "%s: queued gold_history story %r (bundle_id=%s)",
                AGENT_NAME, story_title[:60], bundle.id,
            )
        except Exception as exc:
            agent_run.status = "failed"
            agent_run.errors = str(exc)
            logger.error("%s run failed: %s", AGENT_NAME, exc, exc_info=True)
        finally:
            agent_run.ended_at = datetime.now(timezone.utc)
            await session.commit()
