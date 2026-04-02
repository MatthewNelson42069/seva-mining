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
from sqlalchemy.ext.asyncio import create_async_engine, AsyncConnection
from sqlalchemy import text

from agents.twitter_agent import TwitterAgent
from agents.instagram_agent import InstagramAgent
from agents.senior_agent import SeniorAgent, seed_senior_config
from config import get_settings

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
    "expiry_sweep": 1004,
    "morning_digest": 1005,
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
    - instagram_agent: InstagramAgent().run()          [Phase 6 — INST-01]
    - expiry_sweep: SeniorAgent().run_expiry_sweep()   [Phase 5 — SENR-09]
    - morning_digest: SeniorAgent().run_morning_digest() [Phase 5 — SENR-01]
    - All other jobs use placeholder_job until their phases are built.
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
            elif job_name == "expiry_sweep":
                agent = SeniorAgent()
                await with_advisory_lock(
                    conn,
                    JOB_LOCK_IDS[job_name],
                    job_name,
                    agent.run_expiry_sweep,
                )
            elif job_name == "morning_digest":
                agent = SeniorAgent()
                await with_advisory_lock(
                    conn,
                    JOB_LOCK_IDS[job_name],
                    job_name,
                    agent.run_morning_digest,
                )
            else:
                await with_advisory_lock(
                    conn,
                    JOB_LOCK_IDS[job_name],
                    job_name,
                    lambda: placeholder_job(job_name),
                )
    return job


def build_scheduler(engine) -> AsyncIOScheduler:
    """
    Create and configure AsyncIOScheduler with all 5 placeholder jobs.

    Job schedule (D-14):
    - content_agent: daily at 6:00 AM (cron)
    - twitter_agent: every 2 hours (interval)
    - instagram_agent: every 4 hours (interval)
    - expiry_sweep: every 30 minutes (interval)
    - morning_digest: daily at 8:00 AM (cron)
    """
    scheduler = AsyncIOScheduler()

    scheduler.add_job(
        _make_job("content_agent", engine),
        trigger="cron",
        hour=6,
        minute=0,
        id="content_agent",
        name="Content Agent — daily at 6am",
    )
    scheduler.add_job(
        _make_job("twitter_agent", engine),
        trigger="interval",
        hours=2,
        id="twitter_agent",
        name="Twitter Agent — every 2 hours",
    )
    scheduler.add_job(
        _make_job("instagram_agent", engine),
        trigger="interval",
        hours=4,
        id="instagram_agent",
        name="Instagram Agent — every 4 hours",
    )
    scheduler.add_job(
        _make_job("expiry_sweep", engine),
        trigger="interval",
        minutes=30,
        id="expiry_sweep",
        name="Expiry Sweep — every 30 minutes",
    )
    scheduler.add_job(
        _make_job("morning_digest", engine),
        trigger="cron",
        hour=8,
        minute=0,
        id="morning_digest",
        name="Morning Digest — daily at 8am",
    )

    return scheduler


async def main() -> None:
    settings = get_settings()
    engine = create_async_engine(
        settings.database_url,
        pool_size=2,
        max_overflow=2,
        pool_pre_ping=True,
        pool_recycle=300,
    )

    # Seed Senior Agent config defaults (idempotent — safe to run on every startup)
    await seed_senior_config()

    scheduler = build_scheduler(engine)
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
