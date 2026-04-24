"""Content sub-agents package — one module per content_type (quick-260421-eoe).

The 6 sub-agents (breaking_news, threads, quotes, infographics,
gold_media, gold_history) each expose ``run_draft_cycle()`` and a
``CONTENT_TYPE`` constant. 4 of the 6 text-story sub-agents share the same
fetch → filter → gold-gate → deep-research → draft → review → persist flow,
factored here into ``run_text_story_cycle(...)`` so each sub-agent module
only needs to supply a single-format drafter.

``gold_media`` and ``gold_history`` have their own flow (X API search +
tweepy client, and historical-story picker with used-topics guard,
respectively) and implement ``run_draft_cycle()`` directly without calling
into this helper.

quick-260423-k8n: sub_long_form removed — topology reduced from 7 to 6 sub-agents.
"""

from __future__ import annotations

import difflib
import json
import logging
from datetime import date, datetime, timezone
from typing import Literal

from anthropic import AsyncAnthropic
from sqlalchemy import func, select

from agents import content_agent
from config import get_settings
from database import AsyncSessionLocal
from models.agent_run import AgentRun
from models.content_bundle import ContentBundle
from services import whatsapp
from services.market_snapshot import fetch_market_snapshot

logger = logging.getLogger(__name__)


async def _is_already_covered_today(
    session,
    story_url: str,
    story_headline: str,
    *,
    content_type: str | None = None,
) -> bool:
    """Cross-run dedup — skip stories already covered earlier today.

    Mirrors the pre-split ContentAgent._is_already_covered_today check so
    functional parity holds after the split.

    Args:
        session: Async SQLAlchemy session.
        story_url: Exact URL of the story to check.
        story_headline: Headline to fuzzy-match against existing bundles.
        content_type: When set, scope the SELECT to only ContentBundles of this
                      content_type (same-type dedup). When None (default), the
                      SELECT is cross-type — blocking the story regardless of
                      which sub-agent previously drafted it (existing behavior).
    """
    today_utc = date.today()
    query = select(ContentBundle).where(
        func.date(ContentBundle.created_at) == today_utc,
        ContentBundle.no_story_flag.is_(False),
    )
    if content_type is not None:
        query = query.where(ContentBundle.content_type == content_type)
    result = await session.execute(query)
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
    sort_by: Literal["published_at", "score"] = "published_at",
    dedup_scope: Literal["cross_agent", "same_type"] = "cross_agent",
) -> int:
    """Shared fetch → filter → draft → review → persist pipeline.

    Used by 4 of the 6 sub-agents (breaking_news, threads, quotes,
    infographics). The other 2 (gold_media, gold_history) implement
    ``run_draft_cycle()`` directly.

    Returns:
        int — items_queued (0 if no candidates, fetch failure, or all
        candidates filtered/compliance-blocked). Callers other than
        sub_infographics may ignore this value; it is preserved for
        sub_infographics' two-phase fallback (quick-260423-lvp).

    Args:
        agent_name: agent_run.agent_name value (e.g. "sub_breaking_news").
        content_type: ContentBundle.content_type value (e.g. "breaking_news").
        draft_fn: Async drafter(story, deep_research, market_snapshot, *, client)
                  that returns a draft_content dict or None on failure. The
                  drafter may stash ``_rationale`` and ``_key_data_points`` on
                  the returned dict; the pipeline pops these before persistence.
        max_count: If not None, break out of the draft loop after N successful
                   compliance-passing persists. Iteration order is set by
                   ``sort_by`` so the loop evaluates best-first. None (default)
                   = iterate all candidates (existing breaking_news behavior).
                   (quick-260423-hq7: changed from pre-loop trim to post-persist
                   break so dedup-blocked stories do not consume the cap.)
        source_whitelist: If not None, drop candidates whose source_name does not
                          contain (case-insensitive) any pattern in the set.
                          None (default) = no filter — existing behavior.
        sort_by: Determines the sort key used when ``max_count`` trims candidates.
                 "published_at" (default) = most recent first — preserves existing
                 behavior for breaking_news, threads, quotes.
                 "score" = composite (score desc, published_at desc) so the
                 highest-quality stories win and ties break toward recency (D-01).
                 Default preserves byte-for-byte identical behavior for the 4
                 other callers that do not pass this kwarg.
        dedup_scope: Controls which existing bundles block re-drafting of a story.
                     "cross_agent" (default) = block if ANY sub-agent drafted the
                     story today — existing behavior.
                     "same_type" = block only if THIS content_type drafted the
                     story today — allows infographics to reuse stories already
                     drafted by breaking_news (D-02).
                     Default preserves byte-for-byte identical behavior for the 4
                     other callers that do not pass this kwarg.
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
        _persisted_items: list[str] = []  # quick-260424-i8b: accumulator for per-run firehose
        try:
            try:
                market_snapshot = await fetch_market_snapshot(session=session)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "%s: market snapshot fetch failed (%s) — continuing without",
                    agent_name,
                    type(exc).__name__,
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
                    agent_name,
                    before,
                    len(candidates),
                    before - len(candidates),
                )

            # When max_count is set, sort candidates so the loop processes best-first
            # (per sort_by). The break-after-N-successes is applied INSIDE the loop
            # after a successful persist — no pre-loop slice. This ensures that if
            # the top N are dedup-blocked, the loop continues to candidates N+1, N+2,
            # ... until max_count successes OR the candidate list is exhausted
            # (quick-260423-hq7).
            if max_count is not None and len(candidates) > 1:
                if sort_by == "score":
                    # D-01: composite sort — score desc, published_at desc tiebreaker.
                    candidates.sort(
                        key=lambda s: (
                            float(s.get("score", 0.0)),
                            s.get("published_at", ""),
                        ),
                        reverse=True,
                    )
                else:
                    candidates.sort(key=lambda s: s.get("published_at", ""), reverse=True)
                logger.info(
                    "%s: sorted %d candidates by %s (max_count=%d, break-after-N)",
                    agent_name,
                    len(candidates),
                    sort_by,
                    max_count,
                )

            if not candidates:
                logger.info(
                    "%s: no %s candidates this cycle",
                    agent_name,
                    content_type,
                )
                if content_type == "infographic":
                    agent_run.notes = json.dumps(
                        {
                            "candidates": 0,
                            "top_by_score": max_count if max_count is not None else 0,
                            "drafted": 0,
                            "compliance_blocked": 0,
                            "queued": 0,
                        }
                    )
                agent_run.status = "completed"
                return items_queued

            gate_config = {
                "content_gold_gate_enabled": "true",
                "content_gold_gate_model": "claude-haiku-4-5",
                "content_bearish_filter_enabled": "true",
            }

            drafted_count = 0
            compliance_blocked_count = 0

            for story in candidates:
                try:
                    if await _is_already_covered_today(
                        session,
                        story["link"],
                        story["title"],
                        content_type=(content_type if dedup_scope == "same_type" else None),
                    ):
                        logger.info(
                            "%s: skipping (already covered today): %r",
                            agent_name,
                            story["title"][:60],
                        )
                        continue

                    gate = await content_agent.is_gold_relevant_or_systemic_shock(
                        story, gate_config, client=anthropic_client
                    )
                    if not gate["keep"]:
                        logger.info(
                            "%s: gold gate rejected: %r (reason=%s)",
                            agent_name,
                            story["title"][:60],
                            gate.get("reject_reason"),
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

                    drafted_count += 1
                    rationale = draft_content.pop("_rationale", "")
                    key_data_points = draft_content.pop("_key_data_points", [])
                    deep_research["key_data_points"] = key_data_points

                    review_result = await content_agent.review(draft_content)
                    compliance_ok = bool(review_result.get("compliance_passed", False))
                    if not compliance_ok:
                        compliance_blocked_count += 1

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
                        # quick-260424-i8b: accumulate approved item text for per-run firehose.
                        # Only breaking_news and threads are sent via WhatsApp; other agents skip.
                        if agent_name in {"sub_breaking_news", "sub_threads"}:
                            if content_type == "breaking_news":
                                _persisted_items.append(str(draft_content.get("tweet", "")))
                            elif content_type == "thread":
                                tweets = draft_content.get("tweets", [])
                                _persisted_items.append("\n\n".join(str(t) for t in tweets if t))
                        logger.info(
                            "%s: queued %s '%s' (score=%.1f)",
                            agent_name,
                            content_type,
                            story["title"][:60],
                            float(story.get("score", 0.0)),
                        )
                        if max_count is not None and items_queued >= max_count:
                            logger.info(
                                "%s: reached max_count=%d successful drafts — exiting loop",
                                agent_name,
                                max_count,
                            )
                            break
                    else:
                        logger.warning(
                            "%s: compliance blocked %s '%s' — reason=%s",
                            agent_name,
                            content_type,
                            story["title"][:60],
                            review_result.get("rationale"),
                        )
                except Exception as exc:
                    logger.error(
                        "%s: error processing story %r: %s",
                        agent_name,
                        story.get("title", "")[:60],
                        exc,
                        exc_info=True,
                    )

            agent_run.items_queued = items_queued
            # D-04: richer telemetry for infographics (consumed by no4 UI subtitle);
            # D-05: other callers retain their existing minimal payload.
            if content_type == "infographic":
                agent_run.notes = json.dumps(
                    {
                        "candidates": len(candidates),
                        "top_by_score": max_count if max_count is not None else 0,
                        "drafted": drafted_count,
                        "compliance_blocked": compliance_blocked_count,
                        "queued": items_queued,
                    }
                )
            else:
                agent_run.notes = json.dumps({"candidates": len(candidates)})
            agent_run.status = "completed"
            # ---- Per-run WhatsApp firehose (quick-260424-i8b) ----
            # Fires for sub_breaking_news + sub_threads only, and only when items
            # were persisted this run. Silent on empty runs. Failures are recorded
            # into agent_run.notes (JSON-merged) and never fail the agent_run.
            if agent_name in {"sub_breaking_news", "sub_threads"} and items_queued > 0:
                whatsapp_status_key: str
                whatsapp_status_val: str
                try:
                    sids = await whatsapp.send_agent_run_notification(
                        agent_name=agent_name,
                        items=_persisted_items,
                        run_id=agent_run.id,
                    )
                    if not sids:
                        whatsapp_status_key = "whatsapp_per_run_skipped"
                        whatsapp_status_val = "credentials missing"
                    else:
                        whatsapp_status_key = "whatsapp_per_run_sent"
                        whatsapp_status_val = ",".join(sids)
                except Exception as wa_exc:  # noqa: BLE001
                    logger.error(
                        "%s: per-run WhatsApp dispatch failed: %s",
                        agent_name,
                        wa_exc,
                    )
                    whatsapp_status_key = "whatsapp_per_run_failed"
                    whatsapp_status_val = f"{type(wa_exc).__name__}: {wa_exc}"

                # MERGE into existing JSON notes — never string-concatenate.
                existing_notes = json.loads(agent_run.notes) if agent_run.notes else {}
                existing_notes[whatsapp_status_key] = whatsapp_status_val
                agent_run.notes = json.dumps(existing_notes)
            # ---- end per-run firehose ----
        except Exception as exc:
            agent_run.status = "failed"
            agent_run.errors = str(exc)
            logger.error("%s run failed: %s", agent_name, exc, exc_info=True)
        finally:
            agent_run.ended_at = datetime.now(timezone.utc)
            await session.commit()
    return items_queued
