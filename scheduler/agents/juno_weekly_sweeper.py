"""v3.1 Phase 15 — Juno Weekly Viral Sweeper.

Fires every Sunday 08:00 PT via APScheduler (registered in worker.py by
Plan 15-06 via _make_juno_weekly_sweeper_job factory + CronTrigger; gated
by JUNO_SWEEPER_CRON_ENABLED env var per Phase 10 precedent).

Orchestration shape mirrors scheduler/agents/weekly_sweeper.py (Seva)
structurally, with Juno-specific differences:

  1. X query: companies.juno.x_queries.JUNO_SWEEPER_X_QUERY (defence-sector
     11-handle + 2-hashtag query — see Plan 15-02 / CONTEXT D-02 final form)
  2. Virality substrate: 3-sub-array union from Juno daily_summaries
     raw_sources_jsonb (defence_news + canadian_procurement + world_events)
     — see Plan 15-01 / CONTEXT D-03 + D-03a substrate fix
  3. Sonnet prompt: companies.juno.prompts.JUNO_SWEEPER_SYSTEM_PROMPT
     (Janes/CSIS voice + verbatim anti-tactical clause per D-04)
  4. Anthropic client: get_anthropic_client('juno', timeout=...) per Phase
     12 D-07 hardcoded literal (bills to JUNO_ANTHROPIC_API_KEY)
  5. Refusal-detector wrap: call_with_refusal_guard from
     agents.juno_refusal_detector — defence content has higher refusal
     risk; Seva sweeper does not use this guard (D-05)
  6. Idempotency filter: scoped_weekly_sweeps('juno') with status filter
     ['running', 'completed', 'partial'] per Phase 9 critical-fix pattern
     (without 'partial' the cron would write duplicate rows on retry)

D-10 byte-identical contract: scheduler/agents/weekly_sweeper.py is
UNTOUCHED. This module imports `canonical_url` and `_sunday_of_this_week`
directly from agents.weekly_sweeper (Python's underscore convention is
advisory, not enforced; the import is read-only and does not modify Seva).

Manual escape hatch (operator smoke fire per D-07 step 2):
    python -m agents.juno_weekly_sweeper

Pitfall mitigations bundled here:
  P3  (NULL raw_sources_jsonb)  — _compute_juno_virality guards (row.raw_sources_jsonb or {}).get(...)
  P6  (Sonnet timeout missing)   — get_anthropic_client('juno', timeout=60.0)
  P7  (token-budget overflow)    — each X post text truncated to [:500] before Sonnet
  P10 (URL canonicalization)     — reuses canonical_url() from agents.weekly_sweeper (Seva-stable)
  P15 (insufficient signal)      — len(x_posts) < 3 OR len(viral_stories) < 3 → status='partial' + fallback copy
  D-03b (backfill window)        — empty substrate during first 0-2 sweeps post-deploy → 'partial' + diagnostic note
  Phase 9 (idempotency 'partial') — status.in_(['running', 'completed', 'partial']) — critical fix per Phase 10 precedent
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from agents.content_agent import deduplicate_stories
from agents.juno_refusal_detector import call_with_refusal_guard
# D-06 LOCKED — import helpers from Seva's weekly_sweeper module verbatim.
# Python's leading-underscore convention is advisory; the import does NOT
# modify weekly_sweeper.py (D-10 byte-identical contract held). This avoids
# ~50 LOC of helper duplication for zero behavioral benefit.
from agents.weekly_sweeper import canonical_url, _sunday_of_this_week
from agents.x_ingest import fetch_top_x_posts
from anthropic_client import get_anthropic_client
from companies.juno.prompts import JUNO_SWEEPER_SYSTEM_PROMPT
from companies.juno.x_queries import JUNO_SWEEPER_X_QUERY
from database import AsyncSessionLocal
from models.agent_run import AgentRun
from models.daily_summary import DailySummary
from models.weekly_sweep import WeeklySweep
# v3.0 Phase 9 (TENANT-03) — scheduler-side scoped helpers; CI grep gate at
# scripts/verify-tenant-isolation.sh requires every multi-tenant select to
# route through this module.
from queries.scoped import scoped_summaries, scoped_weekly_sweeps

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level constants (mirror weekly_sweeper.py shape with Juno tuning)
# ---------------------------------------------------------------------------

AGENT_NAME = "juno_weekly_sweeper"
LA_TZ = ZoneInfo("America/Los_Angeles")
JUNO_SWEEPER_SONNET_MODEL = "claude-sonnet-4-6"
JUNO_SWEEPER_SONNET_MAX_TOKENS = 1500  # matches JUNO_SONNET_MAX_DEFENCE
JUNO_SWEEPER_SONNET_TIMEOUT = 60.0
IDEMPOTENCY_WINDOW_MIN = 60
VIRALITY_LOOKBACK_DAYS = 7
VIRALITY_TOP_N = 5
SUFFICIENT_SIGNAL_MIN = 3
X_POST_TRUNCATE_CHARS = 500

INSUFFICIENT_SIGNAL_FALLBACK = (
    "Insufficient signal this week — angles not generated. "
    "Substrate may still be accumulating from new Phase 15 D-03a schema "
    "(first 0-2 sweeps post-deploy)."
)

REFUSAL_FALLBACK_COPY = (
    "Content angles unavailable this week — Sonnet refused on both attempts "
    "(refusal-detector second-attempt failure per D-05). See "
    "raw_sources_jsonb.refusal_diagnostic for the captured excerpts."
)


# ---------------------------------------------------------------------------
# Virality compute — Juno 3-sub-array union (D-03 + D-03a substrate fix)
# ---------------------------------------------------------------------------

async def _compute_juno_virality(session: AsyncSession) -> list[dict]:
    """Compute top-5 most-cross-referenced Juno stories from last 7 days.

    Differs from Seva's _compute_virality at scheduler/agents/weekly_sweeper.py
    line 119 in two ways:
      1. Tenant scope: scoped_summaries('juno') instead of ('seva')
      2. Substrate: union of 3 sub-arrays (defence_news + canadian_procurement
         + world_events) instead of Seva's single 'gold_news' key

    Algorithm:
      1. SELECT all Juno daily_summaries where generated_at >= now - 7 days
         AND status IN ('completed', 'partial')
      2. For each row: raw = row.raw_sources_jsonb or {} (P3 guard)
      3. stories = raw.get('defence_news', []) + raw.get('canadian_procurement', [])
                   + raw.get('world_events', [])  -- D-03 3-sub-array union
      4. Skip rows where union is empty
      5. Per-row dedup via deduplicate_stories (P9 — same-row dupes count once)
      6. For each story: canonicalize link via canonical_url(); group by
         canonical URL; count distinct source_names
      7. Sort by distinct_source_count DESC; return top-5

    Returns:
        List of up to 5 dicts (may be empty if no Juno rows or all empty).
        Each dict: {canonical_url, title, distinct_source_count,
        source_names, sample_published_at}.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=VIRALITY_LOOKBACK_DAYS)
    stmt = (
        scoped_summaries("juno")
        .where(DailySummary.generated_at >= cutoff)
        .where(DailySummary.status.in_(["completed", "partial"]))
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()

    # canonical_url → {"title": str, "source_names": set, "sample_published_at": str|None}
    agg: dict[str, dict] = {}

    for row in rows:
        # P3 guard — failed rows may have raw_sources_jsonb=None.
        raw = row.raw_sources_jsonb or {}
        # D-03 3-sub-array union (D-03a substrate keys persisted by Plan 15-01).
        stories = (
            (raw.get("defence_news") or [])
            + (raw.get("canadian_procurement") or [])
            + (raw.get("world_events") or [])
        )
        if not stories:
            continue

        # P9 — per-row dedup BEFORE cross-summary counting. Normalize entries
        # to the shape deduplicate_stories expects (link/title/source_name).
        row_stories = [
            {
                "link": s.get("link", ""),
                "title": s.get("title", ""),
                "source_name": s.get("source_name", ""),
                "published_at": s.get("published") or s.get("published_at"),
            }
            for s in stories
            if s.get("link")
        ]
        deduped = deduplicate_stories(row_stories)

        for s in deduped:
            canonical = canonical_url(s["link"])
            if not canonical:
                continue
            entry = agg.setdefault(
                canonical,
                {
                    "canonical_url": canonical,
                    "title": s["title"],
                    "source_names": set(),
                    "sample_published_at": s.get("published_at"),
                },
            )
            if s["source_name"]:
                entry["source_names"].add(s["source_name"])

    ranked = [
        {
            "canonical_url": v["canonical_url"],
            "title": v["title"],
            "distinct_source_count": len(v["source_names"]),
            "source_names": sorted(v["source_names"]),
            "sample_published_at": v["sample_published_at"],
        }
        for v in agg.values()
        if v["source_names"]
    ]
    ranked.sort(key=lambda r: r["distinct_source_count"], reverse=True)
    return ranked[:VIRALITY_TOP_N]


# ---------------------------------------------------------------------------
# Markdown builders (mirror Seva's _build_x_posts_md + _build_virality_md)
# ---------------------------------------------------------------------------

async def _build_x_posts_md(x_posts: list[dict]) -> str:
    """Format X posts as Markdown for weekly_sweeps.reddit_top_md column.

    Section header mirrors Seva's "Top X Posts This Week" — same shape so the
    multi-tenant Tab 3 renderer treats both companies' rows identically.
    """
    if not x_posts:
        return "### Top X Posts This Week\n\nNo X posts surfaced this week."

    lines = ["### Top X Posts This Week", ""]
    for p in x_posts:
        engagement = p["likes"] + p["retweets"] * 2 + int(p["replies"] * 1.5)
        text_preview = p["text"][:200].replace("\n", " ")
        lines.append(
            f"* **[@{p['author_username']}]({p['tweet_url']})** "
            f"(♥{p['likes']} ⟲{p['retweets']} 💬{p['replies']}, score={engagement}): "
            f"{text_preview}"
        )
    return "\n".join(lines)


async def _build_virality_md(viral_stories: list[dict]) -> str:
    """Format virality stories as Markdown for weekly_sweeps.story_virality_md."""
    if not viral_stories:
        return "### Most Cross-Referenced Stories\n\nNo cross-referenced stories this week."

    lines = ["### Most Cross-Referenced Stories", ""]
    for s in viral_stories:
        sources_str = ", ".join(s["source_names"][:5])
        lines.append(
            f"* **{s['title']}** — {s['distinct_source_count']} distinct sources "
            f"({sources_str}) — [link]({s['canonical_url']})"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Sonnet caller (wrapped by Phase 10 refusal-detector per D-05)
# ---------------------------------------------------------------------------

async def _call_sonnet_for_juno_angles(
    x_posts: list[dict],
    viral_stories: list[dict],
    anthropic_client,
) -> tuple[str | None, dict]:
    """Build user prompt + call Sonnet wrapped by call_with_refusal_guard.

    Returns (angles_md_or_None, refusal_diagnostic). On second-attempt
    refusal: angles_md is None and diagnostic carries refusal flags.

    P7 — each X post text is truncated to X_POST_TRUNCATE_CHARS before
    inclusion in the user prompt (token-budget overflow guard).
    """
    prompt_parts = [
        "Generate exactly 3 content angles connecting an X (Twitter) defence-sector "
        "signal with a mainstream defence-news signal from the past week.",
        "",
        "## Top X posts this week (top 10 by engagement, ranked):",
    ]
    for i, p in enumerate(x_posts, start=1):
        truncated = p["text"][:X_POST_TRUNCATE_CHARS].replace("\n", " ")  # P7
        prompt_parts.append(
            f"\n[X Post {i}] @{p['author_username']} "
            f"(♥{p['likes']} ⟲{p['retweets']} 💬{p['replies']})\n"
            f"URL: {p['tweet_url']}\n"
            f"Text: {truncated}"
        )

    prompt_parts.append(
        "\n\n## Most cross-referenced stories this week "
        "(top 5 by distinct-source count):"
    )
    for i, s in enumerate(viral_stories, start=1):
        sources = ", ".join(s["source_names"][:5])
        prompt_parts.append(
            f"\n[Story {i}] {s['title']}\n"
            f"URL: {s['canonical_url']}\n"
            f"Distinct sources: {s['distinct_source_count']} ({sources})"
        )
    user_prompt = "\n".join(prompt_parts)

    return await call_with_refusal_guard(
        anthropic_client,
        model=JUNO_SWEEPER_SONNET_MODEL,
        max_tokens=JUNO_SWEEPER_SONNET_MAX_TOKENS,
        system=JUNO_SWEEPER_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        section_name="sweeper",
    )


# ---------------------------------------------------------------------------
# Idempotency helper — Phase 9 critical-fix: status includes 'partial'
# ---------------------------------------------------------------------------

async def _idempotency_skip(session: AsyncSession, now_utc: datetime) -> bool:
    """Return True if a recent Juno weekly_sweeps row exists in the window.

    Phase 9 critical-fix pattern — status filter INCLUDES 'partial' (Seva's
    filter is ['running', 'completed']; Juno per Phase 10 D-01b precedent
    includes 'partial' so refusal-detector-tripped or substrate-empty
    sweeps don't get duplicated on retry within the 60-min window).

    Without 'partial' in the filter, every cron fire that landed
    status='partial' would write a duplicate row on the next retry.
    """
    sunday = _sunday_of_this_week(now_utc)
    cutoff = now_utc - timedelta(minutes=IDEMPOTENCY_WINDOW_MIN)
    stmt = (
        scoped_weekly_sweeps("juno")
        .with_only_columns(WeeklySweep.id)
        .where(WeeklySweep.week_start == sunday)
        .where(WeeklySweep.generated_at >= cutoff)
        .where(WeeklySweep.status.in_(["running", "completed", "partial"]))
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None


# ---------------------------------------------------------------------------
# run_juno_weekly_sweeper — orchestration entry point (JSWEEP-02/-03/-04)
# ---------------------------------------------------------------------------

async def run_juno_weekly_sweeper() -> None:
    """Juno weekly sweeper entry point. Called from worker.py via
    _make_juno_weekly_sweeper_job (Plan 15-06).

    Status mapping (mirrors Seva pattern + refusal-detector branch):
      completed: all sections returned non-None and signal sufficient
      partial:   (a) refusal-detector second-attempt failure (angles is None)
                 OR (b) X ingest returned 0 posts but virality+synthesis ok
                 OR (c) virality returned 0 cross-references but X+synthesis ok
                 OR (d) insufficient signal (sparse week — D-03b backfill)
      failed:    both X ingest crashed AND virality crashed (no markdown)

    Manual escape hatch (D-07 step 2):
      python -m agents.juno_weekly_sweeper
    """
    now_utc = datetime.now(timezone.utc)
    sunday = _sunday_of_this_week(now_utc)
    week_start = sunday
    week_end = sunday + timedelta(days=6)

    async with AsyncSessionLocal() as session:
        if await _idempotency_skip(session, now_utc):
            logger.info(
                "juno_weekly_sweeper idempotency_skip — recent Juno row exists "
                "for week_start=%s within %d min window",
                sunday,
                IDEMPOTENCY_WINDOW_MIN,
            )
            return

    agent_run = AgentRun(
        agent_name=AGENT_NAME,
        started_at=now_utc,
        items_found=0,
        items_queued=0,
        items_filtered=0,
        status="running",
        notes=json.dumps({"company_id": "juno"}),
    )
    async with AsyncSessionLocal() as session:
        session.add(agent_run)
        await session.commit()
        await session.refresh(agent_run)

    agent_run_id = agent_run.id
    x_posts: list[dict] = []
    viral_stories: list[dict] = []
    x_md: str | None = None
    virality_md: str | None = None
    angles_md: str | None = None
    sections_failed: list[str] = []
    per_section_errors: list[str] = []
    insufficient_signal_path = False
    refusal_diagnostic: dict = {}
    run_status = "failed"
    error_text: str | None = None

    # Phase 12 D-07 — HARDCODED 'juno' literal (NOT get_anthropic_client(company_id)
    # with a variable). Mitigates Phase 15 Hard Part P8 (sweeper Sonnet billing to
    # wrong Anthropic key) — a typo'd or accidentally-swapped variable would bill
    # Juno's synthesis to Seva's Anthropic dashboard. The hardcoded literal makes
    # this a compile-time-checkable invariant; the CI grep gate at
    # scripts/verify-anthropic-resolver.sh enforces no raw AsyncAnthropic(api_key=)
    # construction outside the resolver module.
    anthropic_client = get_anthropic_client("juno", timeout=JUNO_SWEEPER_SONNET_TIMEOUT)

    try:
        # --- Section 1: X ingest (defence-sector handles + hashtags) ---
        try:
            x_posts = await fetch_top_x_posts(
                query=JUNO_SWEEPER_X_QUERY, max_results=100
            )
            x_md = await _build_x_posts_md(x_posts)
            if not x_posts:
                sections_failed.append("x_ingest")
                per_section_errors.append(
                    "x_ingest: returned 0 posts (quota cap or empty result)"
                )
        except Exception as exc:
            logger.exception("juno_weekly_sweeper: x_ingest crashed")
            per_section_errors.append(
                f"x_ingest: {type(exc).__name__}: {str(exc)[:200]}"
            )
            sections_failed.append("x_ingest")
            x_md = "### Top X Posts This Week\n\nX ingest failed this week."

        # --- Section 2: Virality compute (3-sub-array union per D-03) ---
        try:
            async with AsyncSessionLocal() as session:
                viral_stories = await _compute_juno_virality(session)
            virality_md = await _build_virality_md(viral_stories)
            if not viral_stories:
                sections_failed.append("virality")
                per_section_errors.append(
                    "virality: 0 cross-referenced stories in last 7 days "
                    "(D-03b backfill window possible)"
                )
        except Exception as exc:
            logger.exception("juno_weekly_sweeper: virality compute crashed")
            per_section_errors.append(
                f"virality: {type(exc).__name__}: {str(exc)[:200]}"
            )
            sections_failed.append("virality")
            virality_md = (
                "### Most Cross-Referenced Stories\n\n"
                "Virality compute failed this week."
            )

        # --- Section 3: Sonnet content angles via refusal-guard (D-05) ---
        if (
            len(x_posts) < SUFFICIENT_SIGNAL_MIN
            or len(viral_stories) < SUFFICIENT_SIGNAL_MIN
        ):
            angles_md = f"### 3 Content Angles\n\n{INSUFFICIENT_SIGNAL_FALLBACK}"
            insufficient_signal_path = True
            logger.info(
                "juno_weekly_sweeper: insufficient signal (x_posts=%d, "
                "viral_stories=%d) — skipping Sonnet, writing fallback",
                len(x_posts),
                len(viral_stories),
            )
        else:
            angles_raw, refusal_diagnostic = await _call_sonnet_for_juno_angles(
                x_posts, viral_stories, anthropic_client
            )
            if angles_raw is None:
                sections_failed.append("sonnet")
                per_section_errors.append(
                    "sonnet: call_with_refusal_guard returned None "
                    "(second-attempt refusal or exception)"
                )
                angles_md = f"### 3 Content Angles\n\n{REFUSAL_FALLBACK_COPY}"
            else:
                angles_md = angles_raw

        # --- Status mapping (Seva pattern + refusal branch) ---
        # The insufficient-signal path is a designed-fallback (P15 + D-03b
        # backfill window) — but for Juno the backfill window is more
        # likely to fire than for Seva, so we tag it 'partial' (not
        # 'completed') with a diagnostic note. This makes the first 0-2
        # post-deploy sweeps visibly distinguish from steady-state.
        if "sonnet" in sections_failed:
            # Refusal-detector second-attempt failure → always 'partial'
            run_status = "partial"
        elif insufficient_signal_path:
            # D-03b backfill window OR sparse-week → 'partial' with note
            run_status = "partial"
        elif not sections_failed:
            run_status = "completed"
        elif x_md or virality_md or angles_md:
            run_status = "partial"
        else:
            run_status = "failed"

        # --- Write weekly_sweeps row ---
        raw_sources = {
            "x_posts": [dict(p) for p in x_posts[:10]],
            "viral_stories": viral_stories,
            "x_search_query": JUNO_SWEEPER_X_QUERY,
            "refusal_diagnostic": refusal_diagnostic,
            "substrate_summary": {
                "x_posts_count": len(x_posts),
                "viral_stories_count": len(viral_stories),
                "insufficient_signal_path": insufficient_signal_path,
            },
        }
        # JSON-safety: convert datetimes to isoformat strings.
        for p in raw_sources["x_posts"]:
            if hasattr(p.get("created_at"), "isoformat"):
                p["created_at"] = p["created_at"].isoformat()

        async with AsyncSessionLocal() as session:
            sweep_row = WeeklySweep(
                company_id="juno",
                generated_at=now_utc,
                week_start=week_start,
                week_end=week_end,
                reddit_top_md=x_md,  # column kept from Phase 5 schema
                story_virality_md=virality_md,
                content_angles_md=angles_md,
                raw_sources_jsonb=raw_sources,
                status=run_status,
                error_text=None,
                agent_run_id=agent_run_id,
            )
            session.add(sweep_row)
            await session.commit()

    except Exception as run_exc:
        logger.exception(
            "juno_weekly_sweeper run failed catastrophically: %s", run_exc
        )
        error_text = f"{type(run_exc).__name__}: {str(run_exc)[:500]}"
        run_status = "failed"
        try:
            async with AsyncSessionLocal() as session:
                failure_row = WeeklySweep(
                    company_id="juno",
                    generated_at=now_utc,
                    week_start=week_start,
                    week_end=week_end,
                    reddit_top_md=None,
                    story_virality_md=None,
                    content_angles_md=None,
                    raw_sources_jsonb={"error": error_text},
                    status="failed",
                    error_text=error_text,
                    agent_run_id=agent_run_id,
                )
                session.add(failure_row)
                await session.commit()
        except Exception:
            logger.exception(
                "juno_weekly_sweeper failure-row write ALSO failed"
            )

    finally:
        try:
            notes_payload = {
                "company_id": "juno",
                "x_posts_count": len(x_posts),
                "viral_stories_count": len(viral_stories),
                "sections_failed": sections_failed,
                "insufficient_signal_path": insufficient_signal_path,
                "refusal_detected": bool(refusal_diagnostic.get("refusal_detected")),
            }
            async with AsyncSessionLocal() as session:
                fresh = await session.get(AgentRun, agent_run_id)
                if fresh is not None:
                    fresh.status = (
                        "completed" if run_status != "failed" else "failed"
                    )
                    fresh.ended_at = datetime.now(timezone.utc)
                    fresh.items_found = len(x_posts)
                    fresh.items_queued = 3 if angles_md and "sonnet" not in sections_failed else 0
                    fresh.items_filtered = len(sections_failed)
                    fresh.notes = json.dumps(notes_payload, default=str)
                    combined_errors = [
                        e for e in ([error_text] + per_section_errors) if e
                    ]
                    if combined_errors:
                        fresh.errors = combined_errors
                    await session.commit()
        except Exception:
            logger.exception(
                "juno_weekly_sweeper agent_runs telemetry update failed"
            )


# ---------------------------------------------------------------------------
# Manual escape hatch (D-07 step 2) — python -m agents.juno_weekly_sweeper
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    asyncio.run(run_juno_weekly_sweeper())
