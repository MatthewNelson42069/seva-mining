"""Gold History sub-agent — drama-first historical storytelling (quick-260421-eoe).

Part of the 7-agent split. Unlike the 5 text-story sub-agents, gold_history
does NOT call ``content_agent.fetch_stories()``: it has its own curated
historical-story source driven by a Claude Sonnet picker and a
``gold_history_used_topics`` Config guard so each story is surfaced at most
once. It DOES call ``content_agent.review()`` inline before writing the
ContentBundle.

Runs on the standard 2h sub-agent cadence; most ticks no-op because the
used-topics guard skips already-surfaced stories. Retires the standalone
``scheduler/agents/gold_history_agent.py`` module.

Requirements: CONT-07, CONT-14, CONT-15, CONT-16, CONT-17.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

import serpapi
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


async def _pick_story(
    used_topics: list[str], *, client: AsyncAnthropic
) -> dict | None:
    """Pick a fresh gold history story via Claude Sonnet.

    Uses the list of already-used slugs to ensure a fresh story is selected
    on each run. Asks Claude to return JSON with story_title, story_slug,
    and key_claims (3-5 claims to verify via SerpAPI).
    """
    used_list = json.dumps(used_topics) if used_topics else "[]"

    try:
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            system=(
                "You are a gold mining historian with a gift for dramatic storytelling. "
                "Pick a compelling, untold gold industry story. Lead with the most "
                "dramatic moment. Return only valid JSON — no markdown, no prose."
            ),
            messages=[{
                "role": "user",
                "content": (
                    f"Already-used story slugs (do NOT pick these): {used_list}\n\n"
                    "Story type suggestions: company builds, M&A, exploration discoveries, "
                    "notable characters, crashes/frauds, gold rushes. Examples: "
                    "Frank Giustra/GoldCorp, Barrick founding by Peter Munk, Bre-X fraud, "
                    "Newmont history, Nevada gold rush, Klondike.\n\n"
                    "Pick a story NOT in the used list. Return JSON:\n"
                    '{"story_title": "...", "story_slug": "giustra-goldcorp-1994", '
                    '"key_claims": ["claim1", "claim2", "claim3"]}'
                ),
            }],
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        data = json.loads(raw)
        if not all(k in data for k in ("story_title", "story_slug", "key_claims")):
            logger.warning("%s: _pick_story missing required keys in response", AGENT_NAME)
            return None
        return data
    except (json.JSONDecodeError, KeyError, IndexError) as exc:
        logger.warning("%s: _pick_story parse failure — %s", AGENT_NAME, exc)
        return None
    except Exception as exc:
        logger.error("%s: _pick_story Claude call failed — %s", AGENT_NAME, exc, exc_info=True)
        return None


async def _verify_facts(
    key_claims: list[str], *, serpapi_client: serpapi.Client
) -> list[dict]:
    """Verify up to 3 key claims via SerpAPI Google search.

    Runs each claim as a synchronous SerpAPI call in the executor to avoid
    blocking the event loop. Claims with no search results are noted as
    "unverified" but NOT discarded — the story proceeds regardless.
    """
    loop = asyncio.get_event_loop()
    verified: list[dict] = []

    for claim in key_claims[:3]:
        def _call(q=claim):
            return serpapi_client.search({
                "engine": "google",
                "q": q,
                "num": 3,
            })

        try:
            results = await loop.run_in_executor(None, _call)
            organic = results.get("organic_results", [])
            if organic:
                top = organic[0]
                verified.append({
                    "claim": claim,
                    "verified": True,
                    "source": top.get("link", ""),
                    "snippet": top.get("snippet", "")[:200],
                })
            else:
                verified.append({
                    "claim": claim,
                    "verified": False,
                    "source": "",
                    "snippet": "No corroborating results found",
                })
        except Exception as exc:
            logger.warning(
                "%s: _verify_facts SerpAPI error for claim %r: %s",
                AGENT_NAME, claim[:60], exc,
            )
            verified.append({
                "claim": claim,
                "verified": False,
                "source": "",
                "snippet": f"Verification error: {exc}",
            })

    return verified


async def _draft_gold_history(
    story_title: str,
    story_slug: str,
    verified_facts: list[dict],
    *,
    client: AsyncAnthropic,
) -> dict | None:
    """Draft a gold_history ContentBundle via Claude Sonnet.

    Uses a drama-first storytelling prompt. Produces a 5-7 tweet thread and
    a 4-7 slide Instagram carousel following the brand design system:
    background #F0ECE4 (warm cream), text #0C1B32 (deep navy),
    gold accent #D4AF37 (metallic gold).
    """
    facts_summary = "\n".join(
        f"- {f['claim']} ({'VERIFIED via ' + f['source'][:80] if f['verified'] else 'unverified'})"
        for f in verified_facts
    )

    try:
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=(
                "You are a senior gold analyst and dramatic historian. "
                "Your storytelling is drama-first: lead with the most dramatic moment — "
                "the audacity, the risk, the payoff. Every sentence earns its place. "
                "No financial advice. No mention of Seva Mining. Return only valid JSON — "
                "no markdown, no prose outside the JSON structure."
            ),
            messages=[{
                "role": "user",
                "content": (
                    f"Story: {story_title}\n\n"
                    f"Verified facts:\n{facts_summary}\n\n"
                    "Story arc: hook → rising action → climax → what it means today.\n\n"
                    "Instagram design system: background #F0ECE4 (warm cream), "
                    "text #0C1B32 (deep navy), gold accent #D4AF37 (metallic gold). "
                    "a16z minimalist aesthetic. One key moment per slide. Max 15 words per slide body. "
                    "Gold accent on 1-2 elements per slide.\n\n"
                    "Return JSON with this exact structure:\n"
                    "{\n"
                    '  "format": "gold_history",\n'
                    '  "story_title": "...",\n'
                    f'  "story_slug": "{story_slug}",\n'
                    '  "tweets": ["hook tweet", "tweet 2", "tweet 3", "tweet 4", "tweet 5"],\n'
                    '  "instagram_carousel": [\n'
                    '    {"slide": 1, "headline": "...", "body": "...(max 15 words)...", "visual_note": "..."},\n'
                    '    {"slide": 2, "headline": "...", "body": "...", "visual_note": "..."}\n'
                    '  ],\n'
                    '  "instagram_caption": "full caption text"\n'
                    "}\n\n"
                    "Tweets: 5-7, hook tweet first (most dramatic moment). "
                    "Carousel: 4-7 slides, one moment per slide."
                ),
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
        )
        if not all(k in data for k in required):
            logger.warning(
                "%s: _draft_gold_history missing required keys in response", AGENT_NAME
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
    """Single-tick pipeline: pick fresh story → verify facts → draft → review → write.

    Does NOT call ``content_agent.fetch_stories()`` — gold_history has its own
    historical-story source. DOES call ``content_agent.review()`` inline before
    writing each bundle. Most ticks no-op once all curated stories have been
    surfaced (guarded by gold_history_used_topics Config key).
    """
    settings = get_settings()
    anthropic_client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    serpapi_client = serpapi.Client(api_key=settings.serpapi_api_key)

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
                "%s: %d stories already used, picking a fresh one",
                AGENT_NAME, len(used_topics),
            )

            story = await _pick_story(used_topics, client=anthropic_client)
            if story is None:
                logger.warning("%s: _pick_story returned None — no bundle created", AGENT_NAME)
                bundle = ContentBundle(
                    story_headline="Gold History: no story selected",
                    content_type=CONTENT_TYPE,
                    no_story_flag=True,
                    score=0.0,
                )
                session.add(bundle)
                agent_run.notes = json.dumps({"reason": "story_pick_failed"})
                agent_run.status = "completed"
                return

            story_title = story["story_title"]
            story_slug = story["story_slug"]
            key_claims = story.get("key_claims", [])

            logger.info(
                "%s: picked story %r (slug=%s)",
                AGENT_NAME, story_title[:60], story_slug,
            )
            agent_run.items_found = 1

            verified_facts = await _verify_facts(key_claims, serpapi_client=serpapi_client)
            verified_count = sum(1 for f in verified_facts if f["verified"])
            logger.info(
                "%s: %d/%d claims verified for %s",
                AGENT_NAME, verified_count, len(verified_facts), story_slug,
            )

            draft_content = await _draft_gold_history(
                story_title, story_slug, verified_facts, client=anthropic_client
            )
            if draft_content is None:
                logger.error("%s: drafting failed for %r", AGENT_NAME, story_title[:60])
                bundle = ContentBundle(
                    story_headline=story_title,
                    content_type=CONTENT_TYPE,
                    no_story_flag=False,
                    score=0.0,
                    deep_research={
                        "verified_claims": verified_facts,
                        "story_slug": story_slug,
                    },
                    compliance_passed=False,
                )
                session.add(bundle)
                await _add_used_topic(session, story_slug)
                agent_run.notes = json.dumps({
                    "reason": "draft_failed",
                    "story_slug": story_slug,
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
                    "verified_claims": verified_facts,
                    "story_slug": story_slug,
                },
                draft_content=draft_content,
                compliance_passed=compliance_ok,
            )
            session.add(bundle)
            await session.flush()

            await _add_used_topic(session, story_slug)

            if not compliance_ok:
                logger.warning(
                    "%s: compliance blocked gold_history %r — reason=%s",
                    AGENT_NAME, story_title[:60], review_result.get("rationale"),
                )
                agent_run.notes = json.dumps({
                    "reason": "compliance_failed",
                    "story_slug": story_slug,
                    "story_title": story_title,
                })
                agent_run.status = "completed"
                return

            rationale = (
                f"Gold History: {story_title}. "
                f"{verified_count}/{len(verified_facts)} claims verified via SerpAPI."
            )
            item = content_agent.build_draft_item(bundle, rationale)
            session.add(item)
            await session.flush()

            agent_run.items_queued = 1
            agent_run.notes = json.dumps({
                "story_title": story_title,
                "story_slug": story_slug,
                "verified_count": verified_count,
                "total_claims": len(verified_facts),
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
