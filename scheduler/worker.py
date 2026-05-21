"""
APScheduler worker process for Seva Mining AI agents.

This module is the entry point for Railway service 2 (scheduler worker).
Phase 4 Plan 01: starts AsyncIOScheduler with 9 jobs:

- daily_summary (Phase 1 Plan 05): cron at 08:00 + 12:00 America/Los_Angeles
- daily_summary_prune (Phase 4 OPS-01): cron at 03:00 America/Los_Angeles — deletes
  daily_summaries rows older than 30 days under advisory lock 1018
- weekly_sweeper (Phase 7 Plan 05): cron Sun 08:00 America/Los_Angeles — viral
  sweep over X API recent search + cross-referenced news stories under advisory
  lock 1019

PostgreSQL advisory locks prevent duplicate execution during Railway
zero-downtime deploys.

Requirements: INFRA-04, INFRA-05, EXEC-03, EXEC-04, SENR-01, SENR-09
Decisions: D-12 (APScheduler 3.11.2), D-13 (advisory lock), D-14 (placeholder jobs)
Phase 5 (SENR): morning_digest job wired to SeniorAgent; expiry_sweep removed in
Phase 10; dedup/alerts/queue-cap/engagement surfaces removed in quick-260420-sn9.
quick-260421-eoe: Content Agent cron + gold_history_agent cron retired; replaced
by 7 independent sub-agent crons (later reduced to 6 by 260423-k8n's sub_long_form
purge, and fully retired by 260519 Phase 8 UI-06 — see notes below).
quick-260424-i8b: morning_digest → midday_digest (job id), retimed 07:00→12:30 PT,
digest scope filter added (DIGEST_EXCLUDED_CONTENT_TYPES excludes breaking_news +
thread content types already covered by the per-run firehose).
Phase 8 UI-06 (260519): All v1.0 content sub-agents (sub_breaking_news,
sub_threads, sub_quotes, sub_infographics, sub_gold_media, sub_gold_history)
fully retired — source files + tests + lock IDs (1010-1016) stripped.
Historical cron lineage (quick-260421-mos, quick-260422-vxg, quick-260424-j5i,
quick-260424-kqa, quick-260427-m49) preserved in CLAUDE.md historical notes
and git history; the precedent matches the 260420-sn9 + 260423-k8n purges
(source code stripped, DB rows preserved). See CLAUDE.md for full lineage.
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.ext.asyncio import AsyncConnection, async_sessionmaker
from sqlalchemy import text, select, update

from database import (
    engine,
    AsyncSessionLocal,
)  # single shared engine — avoids duplicate connection pools
from models.agent_run import AgentRun
from models.config import Config
# agents.content.* imports removed in Phase 4 Task 4 — CONTENT_CRON_AGENTS emptied.
# Phase 8 UI-06 (260519): source files + tests fully stripped — see CLAUDE.md.
from agents.senior_agent import SeniorAgent, seed_senior_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Module-level scheduler reference — promoted so agents can enqueue one-off jobs (Phase 11).
# Initialized to None; set to the running AsyncIOScheduler instance in main().
_scheduler: AsyncIOScheduler | None = None

# Digest scope filter — quick-260424-i8b: historically excluded breaking_news +
# threads from the 12:30 PT midday digest because they were covered by the per-run
# WhatsApp firehose in agents/content/__init__.py. Phase 8 UI-06 (260519) stripped
# both that firehose AND the midday_digest registration (Phase 1 CRIT-1) — the
# constant is preserved as harmless dead code consumed by the midday_digest factory
# (also preserved as dead code per D-07). Matches ContentBundle.content_type values
# verbatim (singular: "thread" not "threads").
DIGEST_EXCLUDED_CONTENT_TYPES: frozenset[str] = frozenset({"breaking_news", "thread"})


def get_scheduler() -> AsyncIOScheduler:
    """Return the running module-level scheduler. Raises RuntimeError if not started yet.

    Used by agents to enqueue one-off DateTrigger jobs (e.g. image render).
    """
    if _scheduler is None:
        raise RuntimeError("Scheduler has not been started yet")
    return _scheduler


# Stable integer lock IDs per job.
# NEVER reuse an ID across different jobs — advisory locks are process-global.
# These IDs are stable for the lifetime of the project.
# Phase 8 UI-06 (260519): v1.0 sub_* entries (1010-1016) stripped — those IDs
# MUST NEVER be reused for new jobs (see CLAUDE.md historical notes for the
# 260519 strip rationale; precedent: 260420-sn9 + 260423-k8n).
JOB_LOCK_IDS: dict[str, int] = {
    # midday_digest retained as dead code per Phase 1 Plan 05 (CRIT-1).
    # Registration removed from build_scheduler; factory + dict entry preserved.
    "midday_digest": 1005,

    # v2.0 daily_summary feed (Phase 1, Plan 05).
    "daily_summary": 1017,
    "daily_summary_prune": 1018,

    # v2.1 Phase 7 weekly_sweeper cron (lock reserved Phase 5 Plan 01).
    "weekly_sweeper": 1019,

    # v3.0 Phase 9 — D-01: per-company jobs with explicit lock IDs.
    # 1020 is REGISTERED in build_scheduler() below (juno_daily_summary).
    # 1021 is RESERVED only — registration deferred to v3.1+ when Juno
    # Weekly Sweeper lands. OPS-02 assertion still validates uniqueness.
    "juno_daily_summary": 1020,
    "juno_weekly_sweeper": 1021,
}

# OPS-02 — startup uniqueness assertion. Costs nothing and catches future
# collisions immediately (CRIT-2 mitigation). Runs at module import time so
# the worker process refuses to start if someone duplicates an ID. v1.0 sub_*
# entries (1010-1016) were stripped in Phase 8 UI-06 — those IDs MUST NEVER
# be reused for new jobs (see CLAUDE.md historical notes for the 260519 strip
# rationale).
assert len(set(JOB_LOCK_IDS.values())) == len(JOB_LOCK_IDS), (
    f"JOB_LOCK_IDS has duplicate values: {JOB_LOCK_IDS}"
)


# Cron-scheduled sub-agents — empty list since Phase 4 Task 4 deregistration
# (2026-04-27) and Phase 8 UI-06 source-file strip (260519). Retained as a
# typed list so the registration loop in build_scheduler() remains a no-op
# (and so any future revival can re-populate without refactor). Tuple shape
# was (job_id, run_fn, name, lock_id, cron_kwargs: dict). _make_sub_agent_job
# factory below is preserved as dead code (no callers when list is empty).
# v1.0 lock IDs 1010-1016 are now FREE of dict membership but MUST NEVER be
# reused — see JOB_LOCK_IDS comment above and CLAUDE.md historical notes.
CONTENT_CRON_AGENTS: list[tuple[str, object, str, int, dict]] = []


async def with_advisory_lock(
    conn: AsyncConnection,
    lock_id: int,
    job_name: str,
    job_fn,
) -> None:
    """
    Wrap an async job function with a PostgreSQL advisory lock.

    Acquires pg_try_advisory_lock(lock_id) before running job_fn.
    If the lock is already held (returns False), logs and returns without running.
    On exception from job_fn: logs, does NOT re-raise (EXEC-04 — worker must survive).
    Always releases lock in finally block.

    Args:
        conn: Active async SQLAlchemy connection.
        lock_id: Stable integer lock ID from JOB_LOCK_IDS.
        job_name: Human-readable job name for logging.
        job_fn: Async coroutine function to execute under the lock.
    """
    result = await conn.execute(
        text("SELECT pg_try_advisory_lock(:lock_id)"),
        {"lock_id": lock_id},
    )
    acquired = result.scalar()

    if not acquired:
        logger.info("Job %s: skipped (advisory lock held by another instance)", job_name)
        return

    try:
        await job_fn()
    except Exception as exc:
        # Log full traceback but do NOT re-raise.
        # Worker process must stay alive even if an individual job fails. (EXEC-04)
        logger.error(
            "Job %s: failed with %s: %s",
            job_name,
            type(exc).__name__,
            exc,
            exc_info=True,
        )
    finally:
        # Best-effort unlock. If Neon auto-suspended the connection mid-job
        # (e.g. during a long LLM call), this statement would fail on a dead
        # connection and crash APScheduler's job loop — killing all future
        # scheduled runs until the worker is manually restarted.
        # The advisory lock auto-releases when the connection is closed by
        # Postgres, so swallowing this error is safe.
        try:
            await conn.execute(
                text("SELECT pg_advisory_unlock(:lock_id)"),
                {"lock_id": lock_id},
            )
        except Exception as exc:
            logger.warning(
                "Job %s: advisory unlock failed (%s: %s) — "
                "lock will auto-release when connection closes",
                job_name,
                type(exc).__name__,
                exc,
            )


def _make_midday_digest_job(engine):
    """Create the midday_digest job callback (advisory-lock wrapped).

    Retained as a dedicated factory for clarity — midday_digest is the
    sole cron-scheduled job that isn't a content sub-agent.

    quick-260424-i8b: renamed from _make_morning_digest_job; SeniorAgent is now
    instantiated with DIGEST_EXCLUDED_CONTENT_TYPES so _assemble_digest filters
    out breaking_news + thread content (already in the per-run firehose).
    """

    async def job():
        async with engine.connect() as conn:
            agent = SeniorAgent(excluded_content_types=DIGEST_EXCLUDED_CONTENT_TYPES)
            await with_advisory_lock(
                conn,
                JOB_LOCK_IDS["midday_digest"],
                "midday_digest",
                agent.run_morning_digest,
            )

    return job


def _make_daily_summary_job(engine):
    """Create the daily_summary job callback (advisory-lock wrapped).

    v2.0 — Phase 1, Plan 05. Mirrors the _make_midday_digest_job factory
    shape (NOT in CONTENT_CRON_AGENTS — daily_summary is a complex job, not
    a simple sub-agent tuple).

    run_daily_summary is imported lazily at call time so worker.py module
    import does not pay the full daily_summary import cost on Railway boot.
    """

    async def job():
        async with engine.connect() as conn:
            from agents.daily_summary import run_daily_summary  # lazy
            await with_advisory_lock(
                conn,
                JOB_LOCK_IDS["daily_summary"],
                "daily_summary",
                run_daily_summary,
            )

    return job


def _make_juno_daily_summary_job(engine):
    """Create the juno_daily_summary job callback (advisory-lock wrapped).

    v3.0 Phase 9 (TENANT-08). Mirrors _make_daily_summary_job exactly,
    swapping the lock ID (1020 vs 1017) and the inner entry point
    (run_juno_daily_summary vs run_daily_summary). The Juno entry point is
    registered as a stub in Phase 9 (writes status='partial' row); Phase 10
    fills the actual feeds/prompts/Sonnet call.

    The factory CLOSES OVER the engine. company_id='juno' is baked into
    the entry point name; no APScheduler args= injection needed (matches
    D-01's "factory mirroring _make_daily_summary_job" pattern).

    run_juno_daily_summary is imported lazily at call time so worker.py
    module import does not pay the daily_summary import cost on Railway boot.
    """

    async def job():
        async with engine.connect() as conn:
            from agents.daily_summary import run_juno_daily_summary  # lazy
            await with_advisory_lock(
                conn,
                JOB_LOCK_IDS["juno_daily_summary"],
                "juno_daily_summary",
                run_juno_daily_summary,
            )

    return job


def _make_juno_weekly_sweeper_job(engine):
    """Create the juno_weekly_sweeper job callback (advisory-lock wrapped).

    v3.1 Phase 15 (JSWEEP-01). Mirrors _make_juno_daily_summary_job exactly,
    swapping the lock ID (1021 vs 1020) and the inner entry point
    (run_juno_weekly_sweeper vs run_juno_daily_summary).

    The factory CLOSES OVER the engine. company_id='juno' is baked into
    the entry point name; no APScheduler args= injection needed (matches
    the Phase 9 D-01 pattern for per-company jobs).

    run_juno_weekly_sweeper is imported lazily at call time so worker.py
    module import does not pay the juno_weekly_sweeper module's import
    cost on Railway boot.
    """

    async def job():
        async with engine.connect() as conn:
            from agents.juno_weekly_sweeper import run_juno_weekly_sweeper  # lazy
            await with_advisory_lock(
                conn,
                JOB_LOCK_IDS["juno_weekly_sweeper"],
                "juno_weekly_sweeper",
                run_juno_weekly_sweeper,
            )

    return job


def _make_daily_summary_prune_job(engine):
    """Create the daily_summary_prune job callback (advisory-lock wrapped).

    v2.0 — Phase 4, Plan 01 (OPS-01). Mirrors _make_daily_summary_job exactly.
    Lock ID 1018 was already reserved in Phase 1's JOB_LOCK_IDS dict (the OPS-02
    uniqueness assertion at module scope guarantees no collision).

    The prune function is imported lazily so worker.py module import does not
    pay the prune module's import cost on Railway boot.
    """

    async def job():
        async with engine.connect() as conn:
            from agents.daily_summary_prune import run_daily_summary_prune  # lazy
            await with_advisory_lock(
                conn,
                JOB_LOCK_IDS["daily_summary_prune"],
                "daily_summary_prune",
                run_daily_summary_prune,
            )

    return job


def _make_weekly_sweeper_job(engine):
    """Create the weekly_sweeper job callback (advisory-lock wrapped).

    v2.1 — Phase 7, Plan 05 (SWEEP-09). Mirrors _make_daily_summary_job
    exactly. Lock ID 1019 was reserved in Phase 5, Plan 05-01 (already in
    JOB_LOCK_IDS dict; OPS-02 uniqueness assertion guards against collision).

    run_weekly_sweeper is imported lazily so worker.py module import does
    not pay the weekly_sweeper module's import cost on Railway boot.
    """

    async def job():
        async with engine.connect() as conn:
            from agents.weekly_sweeper import run_weekly_sweeper  # lazy
            await with_advisory_lock(
                conn,
                JOB_LOCK_IDS["weekly_sweeper"],
                "weekly_sweeper",
                run_weekly_sweeper,
            )

    return job


def _make_sub_agent_job(job_id: str, lock_id: int, run_fn, engine):
    """Create a content sub-agent job callback (advisory-lock wrapped).

    Parameterized on ``run_fn`` so every sub-agent executes under its own
    advisory lock without needing a dispatch switch (quick-260421-eoe).
    """

    async def job():
        async with engine.connect() as conn:
            await with_advisory_lock(
                conn,
                lock_id,
                job_id,
                run_fn,
            )

    return job


async def _read_schedule_config(engine) -> dict[str, str]:
    """Read schedule-related config keys from DB at startup.

    Returns a dict of {key: value} for schedule config keys.
    Falls back to hardcoded defaults if DB is unreachable or keys are missing.

    quick-260421-eoe: the old content_agent and gold_history interval/cron
    config keys are no longer read (the 6 sub-agent crons that replaced them
    were themselves retired in Phase 8 UI-06 — 260519).
    """
    defaults = {
        # Hour is interpreted in America/Los_Angeles local time, NOT UTC.
        # 7 = 07:00 PT morning digest (user's expected delivery time).
        # Historical: this key was "8" with scheduler tz=UTC, which fired at
        # 01:00 PDT — silent mis-timing. Debug session
        # twilio-morning-digest-not-delivering (2026-04-24) attached an
        # explicit timezone to the CronTrigger and moved the default to 7 PT.
        "morning_digest_schedule_hour": "7",
    }
    try:
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            result = await session.execute(
                select(Config.key, Config.value).where(Config.key.in_(list(defaults.keys())))
            )
            rows = {row.key: row.value for row in result.all()}
        config = {}
        for key, default in defaults.items():
            value = rows.get(key, default)
            if key not in rows:
                logger.warning(
                    "Schedule config key '%s' not in DB — using default: %s", key, default
                )
            config[key] = value
        return config
    except Exception as exc:
        logger.error("Failed to read schedule config from DB: %s — using all defaults", exc)
        return defaults


async def build_scheduler(engine) -> AsyncIOScheduler:
    """Build the APScheduler instance with 4 jobs registered.

    - daily_summary: cron at 08:00 + 12:00 America/Los_Angeles (Phase 1 Plan 05).
    - daily_summary_prune: cron at 03:00 America/Los_Angeles (Phase 4 OPS-01).
    - weekly_sweeper: cron Sun 08:00 America/Los_Angeles (Phase 7 Plan 05).
    - juno_daily_summary: cron at 08:05 + 12:05 America/Los_Angeles
      (v3.0 Phase 9 — TENANT-08, 5-min stagger from Seva per D-01a; env-gated
      by JUNO_CRON_ENABLED).
    - juno_weekly_sweeper: cron Sun 08:00 America/Los_Angeles (v3.1 Phase 15
      JSWEEP-01; env-gated by JUNO_SWEEPER_CRON_ENABLED).

    Phase 8 UI-06 (260519): all v1.0 content sub-agent crons fully retired
    (source files + tests + lock IDs 1010-1016 stripped). Historical lineage:
    quick-260423-k8n removed sub_long_form (8→7 jobs); Phase 4 Task 4 emptied
    CONTENT_CRON_AGENTS (260427); Phase 8 UI-06 deleted the source files.
    See CLAUDE.md historical notes for the full cron lineage timeline.

    quick-260424-i8b: morning_digest → midday_digest (job id), retimed 07:00→12:30 PT.
    Phase 1 Plan 05 (CRIT-1): midday_digest registration removed; daily_summary
    replaces it. _read_schedule_config is still called for its side effect (DB
    seed parity) but morning_digest_schedule_hour is no longer consumed.
    """
    await _read_schedule_config(engine)  # reads DB config; morning_digest_schedule_hour no longer used

    logger.info(
        "Schedule config: 4 cron jobs (daily_summary 08:00+12:00 PT, "
        "juno_daily_summary 08:05+12:05 PT, daily_summary_prune 03:00 PT, "
        "weekly_sweeper Sun 08:00 PT). "
        "cron_sub_agents=%d (CONTENT_CRON_AGENTS empty post-Phase-8 UI-06 strip).",
        len(CONTENT_CRON_AGENTS),
    )

    scheduler = AsyncIOScheduler(
        job_defaults={
            "coalesce": True,
            "max_instances": 1,
            "misfire_grace_time": 1800,
        },
        timezone="UTC",
    )

    # midday_digest registration removed in Phase 1, Plan 05 (CRIT-1 / SUM-06).
    # The _make_midday_digest_job factory and JOB_LOCK_IDS["midday_digest"]=1005
    # entry are intentionally left in place as dead code per D-07 (Phase 8 UI-06
    # strip retained midday_digest; v1.0 sub_* lock IDs 1010-1016 were removed).

    # daily_summary — fires at 08:00 PT and 12:00 PT (SUM-01).
    # CronTrigger(hour="8,12") fires the same advisory-lock ID twice daily; the
    # 4-hour gap makes lock collision impossible. 08:00 and 12:00 are both
    # outside the DST-ambiguous 01:00-02:00 window (MOD-1 — safe).
    # If you change these hours, verify the new times are not 01:00-02:00 PT.
    scheduler.add_job(
        _make_daily_summary_job(engine),
        trigger=CronTrigger(
            hour="8,12",
            minute=0,
            timezone="America/Los_Angeles",
        ),
        id="daily_summary",
        name="Daily Summary — 08:00 + 12:00 America/Los_Angeles",
    )

    # v3.0 Phase 9 — TENANT-08 — Juno daily_summary at 08:05 + 12:05 PT.
    # v3.0 Phase 10 (Wave 3, 10-04-PLAN.md) — JUNO_CRON_ENABLED env var gate.
    # Registration is conditional on JUNO_CRON_ENABLED=true so production deploys
    # do NOT fire the Juno cron until the operator approves voice UAT
    # (.planning/phases/10-juno-defence-news-funnel/voice_calibration_uat.md).
    # Rollback is a single env-var unset (no redeploy needed).
    # 5-min stagger from Seva's hour="8,12", minute=0 (D-01a). Rationale:
    # spreads Anthropic API rate-limit pressure (PITFALLS.md §3) and avoids
    # simultaneous Sonnet calls. Lock ID 1020 (JOB_LOCK_IDS["juno_daily_summary"]).
    # juno_weekly_sweeper (lock 1021) is slot-only in v3.0 — registration
    # deferred to v3.1+ per D-01. 08:05 + 12:05 are both outside the
    # DST-ambiguous 01:00-02:00 window (MOD-1 — safe).
    juno_cron_enabled = os.getenv("JUNO_CRON_ENABLED", "false").lower() == "true"
    if juno_cron_enabled:
        logger.info(
            "juno_daily_summary cron ENABLED via JUNO_CRON_ENABLED=true env var"
        )
        scheduler.add_job(
            _make_juno_daily_summary_job(engine),
            trigger=CronTrigger(
                hour="8,12",
                minute=5,
                timezone="America/Los_Angeles",
            ),
            id="juno_daily_summary",
            name="Daily Summary — Juno — 08:05 + 12:05 America/Los_Angeles",
            max_instances=1,
            misfire_grace_time=1800,
        )
    else:
        logger.info(
            "juno_daily_summary cron DISABLED — set JUNO_CRON_ENABLED=true in "
            "Railway env after voice UAT approves "
            "(.planning/phases/10-juno-defence-news-funnel/voice_calibration_uat.md)"
        )

    # daily_summary_prune — fires at 03:00 PT daily (OPS-01).
    # 03:00 PT is outside both summary fire times (08:00 + 12:00 PT) so the
    # prune lock (1018) cannot contend with the summary lock (1017). Also
    # outside the DST-ambiguous 01:00-02:00 window (MOD-1 — safe).
    scheduler.add_job(
        _make_daily_summary_prune_job(engine),
        trigger=CronTrigger(hour=3, minute=0, timezone="America/Los_Angeles"),
        id="daily_summary_prune",
        name="Daily Summary Prune — 03:00 America/Los_Angeles",
    )

    # weekly_sweeper — fires Sunday 08:00 PT (SWEEP-09).
    # day_of_week='sun' uses APScheduler's named-day shorthand. 08:00 PT is
    # outside the DST-ambiguous 01:00-02:00 window (MOD-1 — safe). Lock 1019
    # is reserved in JOB_LOCK_IDS from Phase 5, Plan 05-01. misfire_grace_time
    # at the AsyncIOScheduler job_defaults level (1800s = 30 min) covers the
    # weekly sweeper's expected ~25s runtime (P12 — no override needed).
    scheduler.add_job(
        _make_weekly_sweeper_job(engine),
        trigger=CronTrigger(
            day_of_week='sun',
            hour=8,
            minute=0,
            timezone='America/Los_Angeles',
        ),
        id="weekly_sweeper",
        name="Weekly Viral Sweeper — Sun 08:00 America/Los_Angeles",
    )

    # v3.1 Phase 15 — Juno Weekly Viral Sweeper at Sunday 08:00 PT.
    # JSWEEP-01 — JUNO_SWEEPER_CRON_ENABLED env var gates registration.
    # Mirrors Phase 10's JUNO_CRON_ENABLED precedent verbatim (worker.py:458).
    # Production deploys default to DISABLED so the operator must explicitly
    # opt in AFTER voice UAT approves (.planning/phases/15-juno-weekly-viral-sweeper/15-07-PLAN.md).
    # Rollback is a single env-var unset (no redeploy needed).
    # Same-time fire as Seva weekly_sweeper (Sun 08:00 PT) is safe — independent
    # advisory locks (1019 Seva vs 1021 Juno) isolate them; max_instances=1 is
    # per-job-id not global. 08:00 PT is outside the DST-ambiguous 01:00-02:00
    # window (MOD-1 — safe). Lock ID 1021 (JOB_LOCK_IDS["juno_weekly_sweeper"])
    # was already reserved in Phase 9 D-01; OPS-02 uniqueness assertion holds.
    juno_sweeper_cron_enabled = os.getenv("JUNO_SWEEPER_CRON_ENABLED", "false").lower() == "true"
    if juno_sweeper_cron_enabled:
        logger.info(
            "juno_weekly_sweeper cron ENABLED via JUNO_SWEEPER_CRON_ENABLED=true env var"
        )
        scheduler.add_job(
            _make_juno_weekly_sweeper_job(engine),
            trigger=CronTrigger(
                day_of_week='sun',
                hour=8,
                minute=0,
                timezone='America/Los_Angeles',
            ),
            id="juno_weekly_sweeper",
            name="Weekly Viral Sweeper — Juno — Sun 08:00 America/Los_Angeles",
            max_instances=1,
            misfire_grace_time=1800,
        )
    else:
        logger.info(
            "juno_weekly_sweeper cron DISABLED — set JUNO_SWEEPER_CRON_ENABLED=true in "
            "Railway env after voice UAT approves "
            "(.planning/phases/15-juno-weekly-viral-sweeper/voice_calibration_uat.md)"
        )

    for job_id, run_fn, name, lock_id, cron_kwargs in CONTENT_CRON_AGENTS:
        scheduler.add_job(
            _make_sub_agent_job(job_id, lock_id, run_fn, engine),
            trigger=CronTrigger(**cron_kwargs),
            id=job_id,
            name=f"{name} — cron ({' '.join(f'{k}={v}' for k, v in cron_kwargs.items())})",
        )

    return scheduler


async def upsert_agent_config() -> None:
    """Upsert engagement thresholds and agent config on every startup.

    Unlike seed_senior_config (insert-only), this OVERWRITES existing values so
    code-level config changes take effect without manual DB edits.

    quick-260421-eoe: removed the old content_agent interval override (the
    sub-agents that replaced it were later retired in Phase 8 UI-06 — 260519).
    The DB row may remain for manual cleanup but is no longer authoritative.

    quick-260421-k9z: removed the content_agent_max_stories_per_run and
    content_agent_breaking_window_hours overrides — both were writes-only
    after eoe (post-split fetch_stories() takes no params and doesn't
    consult config); zero readers, so the startup upsert was zombie work.
    """
    overrides = {
        # Content quality threshold
        # Anthropic relevance scoring fallback is 0.5 — lower threshold so more stories pass.
        # With 0.5 relevance: (0.5*0.4 + recency*0.3 + cred*0.3)*10 = min 4.0 for old/unknown sources
        "content_quality_threshold": "7.0",  # restored — feed narrowing + gold gate replace this workaround
        "content_recency_weight": "0.40",  # bump from 0.30 — favours fresher stories
    }
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        for key, value in overrides.items():
            result = await session.execute(select(Config).where(Config.key == key))
            row = result.scalar_one_or_none()
            if row:
                row.value = value
            else:
                session.add(Config(key=key, value=value))
        await session.commit()
    logger.info("upsert_agent_config: engagement thresholds applied.")


async def reconcile_stale_runs(threshold_minutes: int = 30) -> int:
    """Mark any agent_runs with status='running' older than threshold as 'failed'.

    Handles the case where the scheduler process was hard-killed (Railway deploy,
    OOM, container crash) before the try/finally block in a sub-agent pipeline
    could update status. In-process exceptions are already handled by the
    try/finally in each sub-agent — this sweeps the orphans those blocks
    couldn't reach. Called once at scheduler startup, before any jobs are
    registered.

    Args:
        threshold_minutes: Rows with started_at older than now - threshold are
            swept. Default 30 min mirrors the APScheduler misfire_grace_time
            set in quick-260422-krz.

    Returns:
        Count of rows updated (0 if no orphans).
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=threshold_minutes)
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            update(AgentRun)
            .where(AgentRun.status == "running")
            .where(AgentRun.started_at < cutoff)
            .values(
                status="failed",
                errors=[
                    "scheduler restart — run abandoned (process killed before finally block)",
                ],
                ended_at=now,
            )
        )
        await session.commit()
        count = result.rowcount or 0
        if count > 0:
            logger.info(
                "reconcile_stale_runs: marked %d orphan 'running' agent_runs "
                "as 'failed' (older than %d min)",
                count,
                threshold_minutes,
            )
        return count


async def _validate_env() -> None:
    """Log critical env var status at startup so Railway logs show any missing keys.

    Does NOT raise — missing optional keys (e.g. SERPAPI) are fine.
    Logs ERROR for keys that will cause agent failures if absent.
    """
    from config import get_settings  # noqa: PLC0415

    settings = get_settings()

    critical = {
        "ANTHROPIC_API_KEY": bool(settings.anthropic_api_key),
        "X_API_BEARER_TOKEN": bool(settings.x_api_bearer_token),
        "DATABASE_URL": bool(settings.database_url),
    }
    optional = {
        "SERPAPI_API_KEY": bool(settings.serpapi_api_key),
        "TWILIO_ACCOUNT_SID": bool(settings.twilio_account_sid),
    }
    for key, present in critical.items():
        if present:
            logger.info("ENV %s: SET ✓", key)
        else:
            logger.error("ENV %s: MISSING — agents will fail without this key", key)
    for key, present in optional.items():
        logger.info("ENV %s: %s", key, "SET ✓" if present else "not set (optional)")

    # v3.1 Phase 12 — per-tenant Anthropic key resolver visibility (KEY-04).
    # Surfaces the 3 new env vars at scheduler boot so operator can confirm
    # Railway configuration without grepping the Anthropic console.
    # Logs WARNING (not ERROR) when per-tenant unset — the resolver falls
    # back to shared ANTHROPIC_API_KEY gracefully (D-01).
    per_tenant_anthropic = {
        "SEVA_ANTHROPIC_API_KEY": settings.seva_anthropic_api_key,
        "JUNO_ANTHROPIC_API_KEY": settings.juno_anthropic_api_key,
    }
    for key, value in per_tenant_anthropic.items():
        if value:
            logger.info("ENV %s: SET ✓", key)
        else:
            logger.warning(
                "ENV %s: not set — resolver will fall back to shared ANTHROPIC_API_KEY",
                key,
            )

    # STRICT mode is a boolean toggle, not a missing-key. Log unconditionally.
    logger.info(
        "ENV ANTHROPIC_RESOLVER_STRICT: %s",
        "true (resolver will RAISE on per-tenant key miss)"
        if settings.anthropic_resolver_strict
        else "false (resolver will fall back gracefully)",
    )

    # v3.1 Phase 15 — JUNO_SWEEPER_CRON_ENABLED gate visibility at boot (JSWEEP-01).
    # Mirrors the JUNO_CRON_ENABLED Phase 10 precedent. Read via os.getenv (NOT
    # Settings — pattern parity locked per RESEARCH §6 Open Question 4).
    # Surfaces the gate status at boot so the operator can confirm Railway
    # configuration without grepping the APScheduler job-registered log lines.
    juno_sweeper_cron_enabled = os.getenv("JUNO_SWEEPER_CRON_ENABLED", "false").lower() == "true"
    logger.info(
        "ENV JUNO_SWEEPER_CRON_ENABLED: %s",
        "true (juno_weekly_sweeper cron WILL register at Sun 08:00 PT)"
        if juno_sweeper_cron_enabled
        else "false (juno_weekly_sweeper cron disabled — flip after voice UAT)",
    )

    market_data = {
        "FRED_API_KEY": bool(settings.fred_api_key),
        "METALPRICEAPI_API_KEY": bool(settings.metalpriceapi_api_key),
    }
    for key, present in market_data.items():
        if present:
            logger.info("ENV %s: SET ✓", key)
        else:
            logger.warning(
                "ENV %s: MISSING — drafter will fall back to [UNAVAILABLE] for this source",
                key,
            )


async def main() -> None:
    # Log env var status to catch missing keys early (especially ANTHROPIC_API_KEY)
    await _validate_env()
    # Seed Senior Agent config defaults (idempotent — safe to run on every startup)
    await seed_senior_config()
    # Upsert engagement thresholds (overwrites existing values — code is source of truth)
    await upsert_agent_config()
    # Reconcile orphan 'running' agent_runs rows left over from hard kills
    # (Railway redeploy SIGKILL / OOM / crash). Must run BEFORE jobs register.
    await reconcile_stale_runs()

    global _scheduler
    _scheduler = await build_scheduler(engine)
    _scheduler.start()
    logger.info("Scheduler worker started. %d jobs registered.", len(_scheduler.get_jobs()))

    try:
        # Block forever — scheduler runs in background event loop
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler worker shutting down.")
        _scheduler.shutdown()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
