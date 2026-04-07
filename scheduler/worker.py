"""
APScheduler worker process for Seva Mining AI agents.

This module is the entry point for Railway service 2 (scheduler worker).
It starts AsyncIOScheduler with 5 jobs and uses PostgreSQL advisory locks
to prevent duplicate execution during Railway zero-downtime deploys.

Requirements: INFRA-04, INFRA-05, EXEC-03, EXEC-04, TWIT-01, SENR-01, SENR-09
Decisions: D-12 (APScheduler 3.11.2), D-13 (advisory lock), D-14 (placeholder jobs)
Phase 5 (SENR): expiry_sweep and morning_digest jobs wired to SeniorAgent.
"""
import asyncio
import inspect
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import AsyncConnection, async_sessionmaker
from sqlalchemy import text, select

from database import engine  # single shared engine — avoids duplicate connection pools
from models.config import Config
from agents.content_agent import ContentAgent
from agents.gold_history_agent import GoldHistoryAgent
from agents.twitter_agent import TwitterAgent
from agents.instagram_agent import InstagramAgent
from agents.senior_agent import SeniorAgent, seed_senior_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Stable integer lock IDs per job.
# NEVER reuse an ID across different jobs — advisory locks are process-global.
# These IDs are stable for the lifetime of the project.
JOB_LOCK_IDS: dict[str, int] = {
    "twitter_agent": 1001,
    "instagram_agent": 1002,
    "content_agent": 1003,
    "morning_digest": 1005,
    "gold_history_agent": 1009,
}


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
        await conn.execute(
            text("SELECT pg_advisory_unlock(:lock_id)"),
            {"lock_id": lock_id},
        )


async def placeholder_job(job_name: str) -> None:
    """
    Async placeholder for agent jobs wired in later phases (D-14).

    Each agent phase will replace this with the real agent function.
    This placeholder satisfies EXEC-03 (all agent functions are async).
    """
    logger.info("Job %s: placeholder executed (Phase 1 skeleton)", job_name)


def _make_job(job_name: str, engine):
    """
    Create a job callback for APScheduler that wraps the appropriate agent
    or placeholder with the advisory lock.

    - twitter_agent: TwitterAgent().run()
    - instagram_agent: InstagramAgent().run()            [Phase 6 — INST-01]
    - morning_digest: SeniorAgent().run_morning_digest() [Phase 5 — SENR-01]
    - All other jobs use placeholder_job until their phases are built.

    Note: expiry_sweep was removed in Phase 10. run_expiry_sweep() is preserved
    in senior_agent.py but no longer scheduled.
    """
    async def job():
        async with engine.connect() as conn:
            if job_name == "twitter_agent":
                agent = TwitterAgent()
                await with_advisory_lock(
                    conn,
                    JOB_LOCK_IDS[job_name],
                    job_name,
                    agent.run,
                )
            elif job_name == "instagram_agent":
                agent = InstagramAgent()
                await with_advisory_lock(
                    conn,
                    JOB_LOCK_IDS[job_name],
                    job_name,
                    agent.run,
                )
            elif job_name == "morning_digest":
                agent = SeniorAgent()
                await with_advisory_lock(
                    conn,
                    JOB_LOCK_IDS[job_name],
                    job_name,
                    agent.run_morning_digest,
                )
            elif job_name == "content_agent":
                agent = ContentAgent()
                await with_advisory_lock(
                    conn,
                    JOB_LOCK_IDS[job_name],
                    job_name,
                    agent.run,
                )
            elif job_name == "gold_history_agent":
                agent = GoldHistoryAgent()
                await with_advisory_lock(
                    conn,
                    JOB_LOCK_IDS[job_name],
                    job_name,
                    agent.run,
                )
            else:
                await with_advisory_lock(
                    conn,
                    JOB_LOCK_IDS[job_name],
                    job_name,
                    lambda: placeholder_job(job_name),
                )
    return job


async def _read_schedule_config(engine) -> dict[str, str]:
    """Read schedule-related config keys from DB at startup.

    Returns a dict of {key: value} for schedule config keys.
    Falls back to hardcoded defaults if DB is unreachable or keys are missing.
    """
    defaults = {
        "twitter_interval_hours": "2",
        "instagram_interval_hours": "4",
        "content_agent_interval_hours": "2",
        "morning_digest_schedule_hour": "8",
        "gold_history_hour": "9",
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
    """Build the APScheduler instance with jobs registered.

    Job schedule intervals read from DB config (EXEC-02).
    Falls back to hardcoded defaults if config keys are missing.

    Config keys:
    - twitter_interval_hours (default: 2)
    - instagram_interval_hours (default: 4)
    - content_agent_interval_hours (default: 2)
    - morning_digest_schedule_hour (default: 8)
    """
    cfg = await _read_schedule_config(engine)

    twitter_hours = int(cfg["twitter_interval_hours"])
    instagram_hours = int(cfg["instagram_interval_hours"])
    content_hours = int(cfg["content_agent_interval_hours"])
    digest_hour = int(cfg["morning_digest_schedule_hour"])
    gold_history_hour = int(cfg["gold_history_hour"])

    logger.info(
        "Schedule config: twitter=%dh, instagram=%dh, content=%dh, "
        "digest=cron(%d:00 UTC), gold_history=cron(%d:00 bi-weekly Sun)",
        twitter_hours, instagram_hours, content_hours,
        digest_hour, gold_history_hour,
    )

    scheduler = AsyncIOScheduler()

    scheduler.add_job(
        _make_job("content_agent", engine),
        trigger="interval",
        hours=content_hours,
        id="content_agent",
        name=f"Content Agent — every {content_hours} hours",
    )
    scheduler.add_job(
        _make_job("twitter_agent", engine),
        trigger="interval",
        hours=twitter_hours,
        id="twitter_agent",
        name=f"Twitter Agent — every {twitter_hours} hours",
    )
    scheduler.add_job(
        _make_job("instagram_agent", engine),
        trigger="interval",
        hours=instagram_hours,
        id="instagram_agent",
        name=f"Instagram Agent — every {instagram_hours} hours",
    )
    scheduler.add_job(
        _make_job("morning_digest", engine),
        trigger="cron",
        hour=digest_hour,
        minute=0,
        id="morning_digest",
        name=f"Morning Digest — daily at {digest_hour}am",
    )
    # NOTE: week="*/2" fires on alternating ISO weeks. At ISO week 52/53 → week 1 rollover,
    # two consecutive Sunday firings may occur (one extra Gold History post in early January).
    # Low-stakes for this content type — acceptable edge case.
    scheduler.add_job(
        _make_job("gold_history_agent", engine),
        trigger="cron",
        day_of_week="sun",
        week="*/2",
        hour=gold_history_hour,
        minute=0,
        id="gold_history_agent",
        name="Gold History Agent — bi-weekly Sunday",
        timezone="UTC",
    )

    return scheduler


async def main() -> None:
    # Seed Senior Agent config defaults (idempotent — safe to run on every startup)
    await seed_senior_config()

    scheduler = await build_scheduler(engine)
    scheduler.start()
    logger.info("Scheduler worker started. %d jobs registered.", len(scheduler.get_jobs()))

    try:
        # Block forever — scheduler runs in background event loop
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler worker shutting down.")
        scheduler.shutdown()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
