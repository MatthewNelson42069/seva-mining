"""
Tests for APScheduler worker process.
Covers: INFRA-05 (advisory lock), EXEC-03 (async jobs), EXEC-04 (graceful error handling)
"""
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
    await with_advisory_lock(mock_conn, 1003, "content_agent", job_fn)

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
    await with_advisory_lock(mock_conn, 1003, "content_agent", failing_job)

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
async def test_all_three_jobs_registered():
    """
    build_scheduler() must register exactly 3 jobs with the correct IDs.
    Covers: INFRA-05 (D-14 job schedule skeleton); updated in 07-10 for gold history jobs.
    Updated in Phase 10-03: expiry_sweep removed (run_expiry_sweep preserved but not scheduled).
    Updated in 260407-neq: content_agent_midday removed; content_agent uses interval trigger.
    Updated in 260419-lvy: instagram_agent removed (Instagram agent purged from codebase).
    Updated in 260420-sn9: twitter_agent removed (Twitter agent purged); Sevamining is now a
    single-agent system (Content only) with Senior trimmed to morning-digest-only.
    """
    mock_engine = MagicMock()
    scheduler = await build_scheduler(mock_engine)
    job_ids = {job.id for job in scheduler.get_jobs()}
    expected_ids = {
        "content_agent",
        "morning_digest", "gold_history_agent",
    }
    assert job_ids == expected_ids, f"Got job IDs: {job_ids}"
    assert "twitter_agent" not in job_ids
    # Scheduler is not started (just built), so only shutdown if running
    if scheduler.running:
        scheduler.shutdown()


# ---------------------------------------------------------------------------
# Phase 10-03 — Remove expiry_sweep tests
# ---------------------------------------------------------------------------

def test_expiry_sweep_removed_from_job_lock_ids():
    """expiry_sweep must not be in JOB_LOCK_IDS after Phase 10."""
    assert "expiry_sweep" not in JOB_LOCK_IDS


def test_twitter_agent_removed_from_job_lock_ids():
    """twitter_agent must not be in JOB_LOCK_IDS after quick-260420-sn9."""
    assert "twitter_agent" not in JOB_LOCK_IDS


@pytest.mark.asyncio
async def test_build_scheduler_has_3_jobs_no_twitter():
    """build_scheduler() returns 3 jobs; expiry_sweep, instagram_agent, and twitter_agent are absent."""
    mock_engine = AsyncMock()
    mock_session = AsyncMock()

    # _read_schedule_config reads from DB — mock the session result
    with patch("worker.async_sessionmaker") as mock_sm, \
         patch("worker.select"), \
         patch("worker._make_job", return_value=AsyncMock()):

        mock_sm.return_value.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_sm.return_value.return_value.__aexit__ = AsyncMock(return_value=False)

        # Simulate DB returning no rows (all defaults used)
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        scheduler = await build_scheduler(mock_engine)

    job_ids = {job.id for job in scheduler.get_jobs()}
    assert "expiry_sweep" not in job_ids
    assert "content_agent_midday" not in job_ids
    assert "instagram_agent" not in job_ids
    assert "twitter_agent" not in job_ids
    assert "morning_digest" in job_ids
    assert "content_agent" in job_ids
    assert "gold_history_agent" in job_ids
    assert len(job_ids) == 3
    if scheduler.running:
        scheduler.shutdown()


def test_read_schedule_config_defaults_no_twitter():
    """_read_schedule_config defaults dict must not contain twitter_interval_hours."""
    from worker import _read_schedule_config
    import inspect
    # Read the source to verify the defaults dict
    source = inspect.getsource(_read_schedule_config)
    assert "expiry_sweep_interval_minutes" not in source
    assert "content_agent_midday_hour" not in source
    assert "instagram_interval_hours" not in source
    assert "twitter_interval_hours" not in source
    assert "content_agent_interval_hours" in source
