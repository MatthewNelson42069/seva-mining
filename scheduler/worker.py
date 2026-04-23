"""
APScheduler worker process for Seva Mining AI agents.

This module is the entry point for Railway service 2 (scheduler worker).
Post quick-260423-k8n, it starts AsyncIOScheduler with 7 jobs:

- morning_digest (daily cron, 08:00 UTC)
- 2 interval sub-agents on IntervalTrigger — sub_breaking_news every 2h,
  sub_threads every 4h — staggered across the 4h window
  with offsets [0, 17] minutes.
- 4 cron sub-agents — sub_quotes / sub_infographics / sub_gold_media all
  daily at 12:00 America/Los_Angeles; sub_gold_history every other day
  (``day='*/2'``) at 12:00 America/Los_Angeles.

PostgreSQL advisory locks prevent duplicate execution during Railway
zero-downtime deploys.

Requirements: INFRA-04, INFRA-05, EXEC-03, EXEC-04, SENR-01, SENR-09
Decisions: D-12 (APScheduler 3.11.2), D-13 (advisory lock), D-14 (placeholder jobs)
Phase 5 (SENR): morning_digest job wired to SeniorAgent; expiry_sweep removed in
Phase 10; dedup/alerts/queue-cap/engagement surfaces removed in quick-260420-sn9.
quick-260421-eoe: Content Agent cron + gold_history_agent cron retired; replaced
by 7 independent sub-agent crons under agents.content.*.
quick-260421-mos: sub_quotes moved from IntervalTrigger(2h) to
CronTrigger(12:00 America/Los_Angeles); other 6 sub-agents unchanged.
quick-260422-vxg: cadence rebalance — BN reverts 1h→2h, Threads+Long-form 2h→4h,
Infographics/Gold Media/Gold History moved off interval onto cron (daily noon PT,
except Gold History every-other-day noon PT via ``day='*/2'``).
CONTENT_CRON_AGENTS tuple shape changed to (job_id, run_fn, name, lock_id,
cron_kwargs: dict).
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.ext.asyncio import AsyncConnection, async_sessionmaker
from sqlalchemy import text, select, update

from database import engine, AsyncSessionLocal  # single shared engine — avoids duplicate connection pools
from models.agent_run import AgentRun
from models.config import Config
from agents.content import (
    breaking_news,
    threads,
    quotes,
    infographics,
    gold_media,
    gold_history,
)
from agents.senior_agent import SeniorAgent, seed_senior_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Module-level scheduler reference — promoted so agents can enqueue one-off jobs (Phase 11).
# Initialized to None; set to the running AsyncIOScheduler instance in main().
_scheduler: AsyncIOScheduler | None = None


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
# quick-260421-eoe: retired content_agent(1003) + gold_history_agent(1009);
# added sub_*(1010-1016) for the 7 content sub-agents.
JOB_LOCK_IDS: dict[str, int] = {
    "morning_digest":    1005,
    "sub_breaking_news": 1010,
    "sub_threads":       1011,
    "sub_quotes":        1013,
    "sub_infographics":  1014,
    "sub_gold_media":    1015,
    "sub_gold_history":  1016,
}


# Content sub-agent registration table — interval-scheduled (quick-260422-vxg).
# Tuple shape: (job_id, run_fn, name, lock_id, offset_minutes, interval_hours).
# Only 2 news-responsive agents run on interval now: sub_breaking_news every 2h,
# sub_threads every 4h. Stagger offsets [0, 17] minutes
# spread the two across the first 17 minutes of each hour to avoid thundering
# herds on SerpAPI + Anthropic. The other 4 sub-agents moved to
# CONTENT_CRON_AGENTS (daily / every-other-day).
# quick-260423-k8n: sub_long_form removed — topology reduced from 7 to 6 sub-agents.
# Lock ID 1012 (sub_long_form) retired, not reassigned. Stagger offsets [0,17,34] → [0,17].
CONTENT_INTERVAL_AGENTS: list[tuple[str, object, str, int, int, int]] = [
    ("sub_breaking_news", breaking_news.run_draft_cycle,  "Breaking News",  1010,   0, 2),
    ("sub_threads",       threads.run_draft_cycle,        "Threads",        1011,  17, 4),
]

# Cron-scheduled sub-agents (quick-260422-vxg).
# Tuple shape: (job_id, run_fn, name, lock_id, cron_kwargs: dict). `cron_kwargs`
# is unpacked directly into `CronTrigger(**cron_kwargs)` at registration time
# so heterogeneous patterns (daily noon PT vs every-other-day noon PT via
# `day='*/2'`) coexist without extra tuple columns. All 4 agents fire at
# 12:00 America/Los_Angeles — post US morning news, pre market close. Gold
# History fires every other day because the used-topics guard means most daily
# ticks no-op; halving cadence halves the Claude picker spend.
CONTENT_CRON_AGENTS: list[tuple[str, object, str, int, dict]] = [
    ("sub_quotes",        quotes.run_draft_cycle,       "Quotes",        1013, {"hour": 12, "minute": 0, "timezone": "America/Los_Angeles"}),
    ("sub_infographics",  infographics.run_draft_cycle, "Infographics",  1014, {"hour": 12, "minute": 0, "timezone": "America/Los_Angeles"}),
    ("sub_gold_media",    gold_media.run_draft_cycle,   "Gold Media",    1015, {"hour": 12, "minute": 0, "timezone": "America/Los_Angeles"}),
    ("sub_gold_history",  gold_history.run_draft_cycle, "Gold History",  1016, {"day": "*/2", "hour": 12, "minute": 0, "timezone": "America/Los_Angeles"}),
]


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


def _make_morning_digest_job(engine):
    """Create the morning_digest job callback (advisory-lock wrapped).

    Retained as a dedicated factory for clarity — morning_digest is the
    sole cron-scheduled job that isn't a content sub-agent.
    """
    async def job():
        async with engine.connect() as conn:
            agent = SeniorAgent()
            await with_advisory_lock(
                conn,
                JOB_LOCK_IDS["morning_digest"],
                "morning_digest",
                agent.run_morning_digest,
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
    config keys are no longer read — sub-agents run on a fixed 2h cadence
    with static offsets.
    """
    defaults = {
        "morning_digest_schedule_hour": "8",
    }
    try:
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            result = await session.execute(
                select(Config.key, Config.value).where(
                    Config.key.in_(list(defaults.keys()))
                )
            )
            rows = {row.key: row.value for row in result.all()}
        config = {}
        for key, default in defaults.items():
            value = rows.get(key, default)
            if key not in rows:
                logger.warning("Schedule config key '%s' not in DB — using default: %s", key, default)
            config[key] = value
        return config
    except Exception as exc:
        logger.error("Failed to read schedule config from DB: %s — using all defaults", exc)
        return defaults


async def build_scheduler(engine) -> AsyncIOScheduler:
    """Build the APScheduler instance with 7 jobs registered.

    - morning_digest: cron at morning_digest_schedule_hour (default 08:00 UTC).
    - 2 interval sub-agents: IntervalTrigger with per-agent hours
      (sub_breaking_news=2, sub_threads=4) and staggered
      start_date offsets [0, 17] minutes.
    - 4 cron sub-agents: sub_quotes / sub_infographics / sub_gold_media daily
      at 12:00 America/Los_Angeles; sub_gold_history every other day at
      12:00 America/Los_Angeles.

    quick-260423-k8n: sub_long_form removed; 8 jobs → 7 jobs.

    Config keys:
    - morning_digest_schedule_hour (default: 8)
    """
    cfg = await _read_schedule_config(engine)

    digest_hour = int(cfg["morning_digest_schedule_hour"])

    logger.info(
        "Schedule config: digest=cron(%d:00 UTC), interval_sub_agents=%d jobs (sub_breaking_news=2h, sub_threads=4h), cron_sub_agents=%d jobs (3× daily 12:00 America/Los_Angeles + 1× every-other-day 12:00 America/Los_Angeles via day='*/2')",
        digest_hour, len(CONTENT_INTERVAL_AGENTS), len(CONTENT_CRON_AGENTS),
    )

    scheduler = AsyncIOScheduler(
        job_defaults={
            "coalesce": True,
            "max_instances": 1,
            "misfire_grace_time": 1800,
        },
        timezone="UTC",
    )

    scheduler.add_job(
        _make_morning_digest_job(engine),
        trigger="cron",
        hour=digest_hour,
        minute=0,
        id="morning_digest",
        name=f"Morning Digest — daily at {digest_hour}am",
    )

    now = datetime.now(timezone.utc)
    for job_id, run_fn, name, lock_id, offset, interval_hours in CONTENT_INTERVAL_AGENTS:
        # +10s buffer ensures start_date > scheduler.start() wall clock for offset=0
        # (APScheduler IntervalTrigger skips first fire if start_date <= now).
        start_date = now + timedelta(minutes=offset) + timedelta(seconds=10)
        scheduler.add_job(
            _make_sub_agent_job(job_id, lock_id, run_fn, engine),
            trigger=IntervalTrigger(hours=interval_hours, start_date=start_date),
            id=job_id,
            name=f"{name} — every {interval_hours}h (offset +{offset}m)",
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

    quick-260421-eoe: removed the old content_agent interval override —
    sub-agents run on fixed cadences (sub_breaking_news=1h, others=2h). The
    DB row may remain for manual cleanup but is no longer authoritative.

    quick-260421-k9z: removed the content_agent_max_stories_per_run and
    content_agent_breaking_window_hours overrides — both were writes-only
    after eoe (post-split fetch_stories() takes no params and doesn't
    consult config); zero readers, so the startup upsert was zombie work.
    """
    overrides = {
        # Content quality threshold
        # Anthropic relevance scoring fallback is 0.5 — lower threshold so more stories pass.
        # With 0.5 relevance: (0.5*0.4 + recency*0.3 + cred*0.3)*10 = min 4.0 for old/unknown sources
        "content_quality_threshold": "7.0",    # restored — feed narrowing + gold gate replace this workaround
        "content_recency_weight": "0.40",      # bump from 0.30 — favours fresher stories
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
                    "scheduler restart — run abandoned (process killed "
                    "before finally block)",
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
                count, threshold_minutes,
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
