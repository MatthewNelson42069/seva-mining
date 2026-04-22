"""Content sub-agents package — one module per content_type (quick-260421-eoe).

The 7 sub-agents (breaking_news, threads, long_form, quotes, infographics,
video_clip, gold_history) each expose ``run_draft_cycle()`` and a
``CONTENT_TYPE`` constant. 5 of the 7 text-story sub-agents share the same
fetch → filter → gold-gate → deep-research → draft → review → persist flow,
factored here into ``run_text_story_cycle(...)`` so each sub-agent module
only needs to supply a single-format drafter.

``video_clip`` and ``gold_history`` have their own flow (X API search +
tweepy client, and historical-story picker with used-topics guard,
respectively) and implement ``run_draft_cycle()`` directly without calling
into this helper.
"""
from __future__ import annotations

import difflib
import json
import logging
from datetime import date, datetime, timezone

from anthropic import AsyncAnthropic
from sqlalchemy import func, select

from agents import content_agent
from config import get_settings
from database import AsyncSessionLocal
from models.agent_run import AgentRun
from models.content_bundle import ContentBundle
from services.market_snapshot import fetch_market_snapshot

logger = logging.getLogger(__name__)


async def _is_already_covered_today(session, story_url: str, story_headline: str) -> bool:
    """Cross-run dedup — skip stories already covered earlier today.

    Mirrors the pre-split ContentAgent._is_already_covered_today check so
    functional parity holds after the split.
    """
    today_utc = date.today()
    result = await session.execute(
        select(ContentBundle).where(
            func.date(ContentBundle.created_at) == today_utc,
            ContentBundle.no_story_flag.is_(False),
        )
    )
    existing_bundles = result.scalars().all()

    headline_lower = story_headline.lower()
    for bundle in existing_bundles:
        if bundle.story_url and bundle.story_url == story_url:
            return True
        if bundle.story_headline:
            ratio = difflib.SequenceMatcher(
                None, headline_lower, bundle.story_headline.lower()
            ).ratio()
            if ratio >= 0.85:
                return True
    return False


async def run_text_story_cycle(
    *,
    agent_name: str,
    content_type: str,
    draft_fn,
    max_count: int | None = None,
    source_whitelist: frozenset[str] | None = None,
) -> None:
    """Shared fetch → filter → draft → review → persist pipeline.

    Used by 5 of the 7 sub-agents (breaking_news, threads, long_form, quotes,
    infographics). The other 2 (video_clip, gold_history) implement
    ``run_draft_cycle()`` directly.

    Args:
        agent_name: agent_run.agent_name value (e.g. "sub_breaking_news").
        content_type: ContentBundle.content_type value (e.g. "breaking_news").
        draft_fn: Async drafter(story, deep_research, market_snapshot, *, client)
                  that returns a draft_content dict or None on failure. The
                  drafter may stash ``_rationale`` and ``_key_data_points`` on
                  the returned dict; the pipeline pops these before persistence.
        max_count: If not None, cap candidates to the top N by published_at desc
                   AFTER the predicted_format filter and AFTER the whitelist filter.
                   None (default) = no cap — existing behavior.
        source_whitelist: If not None, drop candidates whose source_name does not
                          contain (case-insensitive) any pattern in the set.
                          None (default) = no filter — existing behavior.
    """
    settings = get_settings()
    anthropic_client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    async with AsyncSessionLocal() as session:
        agent_run = AgentRun(
            agent_name=agent_name,
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
                    "%s: market snapshot fetch failed (%s) — continuing without",
                    agent_name, type(exc).__name__,
                )
                market_snapshot = None

            stories = await content_agent.fetch_stories()
            agent_run.items_found = len(stories)
            # All gold-gate-passing stories are candidates for every content type.
            # The predicted_format classifier label was removed as a routing gate
            # (debug 260422-zid): the classifier assigned most gold-sector stories
            # to "breaking_news", starving the other 4 content buckets.
            # predicted_format is retained as metadata on stories for analytics only.
            candidates = list(stories)

            # Reputable-source whitelist (case-insensitive substring match on source_name).
            # Opt-in via source_whitelist kwarg; None (default) = no filter.
            if source_whitelist is not None:
                before = len(candidates)

                def _is_reputable(story: dict) -> bool:
                    source = (story.get("source_name") or "").lower()
                    return bool(source) and any(p in source for p in source_whitelist)

                candidates = [s for s in candidates if _is_reputable(s)]
                logger.info(
                    "%s: reputable filter: %d -> %d (dropped %d non-whitelisted sources)",
                    agent_name, before, len(candidates), before - len(candidates),
                )

            # Cap to top max_count by published_at desc (after whitelist).
            # Opt-in via max_count kwarg; None (default) = no cap.
            if max_count is not None and len(candidates) > max_count:
                candidates.sort(key=lambda s: s.get("published_at", ""), reverse=True)
                candidates = candidates[:max_count]
                logger.info(
                    "%s: max_count cap: trimmed to top %d by recency",
                    agent_name, max_count,
                )

            if not candidates:
                logger.info(
                    "%s: no %s candidates this cycle", agent_name, content_type,
                )
                agent_run.status = "completed"
                return

            gate_config = {
                "content_gold_gate_enabled": "true",
                "content_gold_gate_model": "claude-haiku-4-5",
            }

            for story in candidates:
                try:
                    if await _is_already_covered_today(
                        session, story["link"], story["title"]
                    ):
                        logger.info(
                            "%s: skipping (already covered today): %r",
                            agent_name, story["title"][:60],
                        )
                        continue

                    gate = await content_agent.is_gold_relevant_or_systemic_shock(
                        story, gate_config, client=anthropic_client
                    )
                    if not gate["keep"]:
                        logger.info(
                            "%s: gold gate rejected: %r (reason=%s)",
                            agent_name, story["title"][:60], gate.get("reject_reason"),
                        )
                        continue

                    article_text, fetch_ok = await content_agent.fetch_article(
                        story["link"], fallback_text=story.get("summary", "")
                    )
                    corroborating = await content_agent.search_corroborating(story["title"])
                    deep_research = {
                        "article_text": article_text[:5000],
                        "article_fetch_succeeded": fetch_ok,
                        "corroborating_sources": corroborating,
                        "key_data_points": [],
                    }

                    draft_content = await draft_fn(
                        story, deep_research, market_snapshot, client=anthropic_client
                    )
                    if draft_content is None:
                        bundle = ContentBundle(
                            story_headline=story["title"],
                            story_url=story["link"],
                            source_name=story.get("source_name"),
                            content_type=content_type,
                            score=story.get("score", 0.0),
                            deep_research=deep_research,
                            compliance_passed=False,
                        )
                        session.add(bundle)
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
                        content_type=content_type,
                        score=story.get("score", 0.0),
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
                            "%s: queued %s '%s' (score=%.1f)",
                            agent_name, content_type, story["title"][:60],
                            float(story.get("score", 0.0)),
                        )
                    else:
                        logger.warning(
                            "%s: compliance blocked %s '%s' — reason=%s",
                            agent_name, content_type, story["title"][:60],
                            review_result.get("rationale"),
                        )
                except Exception as exc:
                    logger.error(
                        "%s: error processing story %r: %s",
                        agent_name, story.get("title", "")[:60], exc, exc_info=True,
                    )

            agent_run.items_queued = items_queued
            agent_run.notes = json.dumps({"candidates": len(candidates)})
            agent_run.status = "completed"
        except Exception as exc:
            agent_run.status = "failed"
            agent_run.errors = str(exc)
            logger.error("%s run failed: %s", agent_name, exc, exc_info=True)
        finally:
            agent_run.ended_at = datetime.now(timezone.utc)
            await session.commit()
