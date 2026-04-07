"""
Tests for APScheduler worker process.
Covers: INFRA-05 (advisory lock), EXEC-03 (async jobs), EXEC-04 (graceful error handling)
"""
import asyncio
import inspect
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# worker.py is at scheduler root, not in a package
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Set required env vars before importing worker (Settings validates at import)
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://fake-pooler.neon.tech/db?sslmode=require")
os.environ.setdefault("ANTHROPIC_API_KEY", "x")
os.environ.setdefault("TWILIO_ACCOUNT_SID", "x")
os.environ.setdefault("TWILIO_AUTH_TOKEN", "x")
os.environ.setdefault("TWILIO_WHATSAPP_FROM", "whatsapp:+1x")
os.environ.setdefault("DIGEST_WHATSAPP_TO", "whatsapp:+1x")
os.environ.setdefault("X_API_BEARER_TOKEN", "x")
os.environ.setdefault("X_API_KEY", "x")
os.environ.setdefault("X_API_SECRET", "x")
os.environ.setdefault("APIFY_API_TOKEN", "x")
os.environ.setdefault("SERPAPI_API_KEY", "x")
os.environ.setdefault("FRONTEND_URL", "https://x.com")

from worker import with_advisory_lock, placeholder_job, build_scheduler, JOB_LOCK_IDS


@pytest.mark.asyncio
async def test_advisory_lock_prevents_duplicate_run():
    """
    When pg_try_advisory_lock returns False, job_fn must NOT be called.
    Covers: INFRA-05
    """
    mock_conn = AsyncMock()
    # Simulate lock already held (pg_try_advisory_lock returns False)
    mock_result = MagicMock()
    mock_result.scalar.return_value = False
    mock_conn.execute.return_value = mock_result

    job_fn = AsyncMock()
    await with_advisory_lock(mock_conn, 1001, "twitter_agent", job_fn)

    job_fn.assert_not_called()


@pytest.mark.asyncio
async def test_job_exception_does_not_propagate():
    """
    When job_fn raises an exception, with_advisory_lock must NOT re-raise.
    Lock must be released even on failure.
    Covers: EXEC-04
    """
    mock_conn = AsyncMock()
    # Simulate lock acquired
    mock_result_acquire = MagicMock()
    mock_result_acquire.scalar.return_value = True
    mock_result_release = MagicMock()
    mock_conn.execute.side_effect = [mock_result_acquire, mock_result_release]

    async def failing_job():
        raise RuntimeError("Agent crashed")

    # Must not raise — worker process must survive
    await with_advisory_lock(mock_conn, 1002, "instagram_agent", failing_job)

    # Lock release must have been called (finally block)
    assert mock_conn.execute.call_count == 2  # acquire + release


@pytest.mark.asyncio
async def test_placeholder_job_is_async():
    """
    placeholder_job must be an async function (coroutine).
    Covers: EXEC-03
    """
    assert inspect.iscoroutinefunction(placeholder_job), (
        "placeholder_job must be an async def (coroutine function)"
    )
    # Must be awaitable without error
    await placeholder_job("test_job")


@pytest.mark.asyncio
async def test_all_five_jobs_registered():
    """
    build_scheduler() must register exactly 7 jobs with the correct IDs.
    Covers: INFRA-05 (D-14 job schedule skeleton); updated in 07-10 for midday + gold history jobs.
    """
    mock_engine = MagicMock()
    scheduler = await build_scheduler(mock_engine)
    job_ids = {job.id for job in scheduler.get_jobs()}
    expected_ids = {
        "content_agent", "twitter_agent", "instagram_agent",
        "expiry_sweep", "morning_digest",
        "content_agent_midday", "gold_history_agent",
    }
    assert job_ids == expected_ids, f"Got job IDs: {job_ids}"
    # Scheduler is not started (just built), so only shutdown if running
    if scheduler.running:
        scheduler.shutdown()
