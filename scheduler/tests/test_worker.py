"""
Tests for APScheduler worker process.
Covers: INFRA-05 (advisory lock), EXEC-03 (async jobs), EXEC-04 (graceful error handling)
"""
import pytest


@pytest.mark.asyncio
async def test_advisory_lock_prevents_duplicate_run():
    """
    When one instance holds the advisory lock, a second call to with_advisory_lock()
    must skip execution (not raise, not execute job_fn).
    Covers: INFRA-05
    """
    pytest.skip("Requires worker.py with_advisory_lock — will be enabled in Plan 06")


@pytest.mark.asyncio
async def test_job_exception_does_not_propagate():
    """
    When a job function raises an exception, with_advisory_lock() must:
    - Log the error
    - Release the advisory lock
    - NOT re-raise the exception
    Covers: EXEC-04
    """
    pytest.skip("Requires worker.py with_advisory_lock — will be enabled in Plan 06")


@pytest.mark.asyncio
async def test_placeholder_job_is_async():
    """
    placeholder_job() must be an async function (coroutine).
    Covers: EXEC-03
    """
    pytest.skip("Requires worker.py placeholder_job — will be enabled in Plan 06")


@pytest.mark.asyncio
async def test_all_five_jobs_registered():
    """
    Scheduler must register jobs with IDs:
    content_agent, twitter_agent, instagram_agent, expiry_sweep, morning_digest
    Covers: INFRA-05 (scheduler skeleton with D-14 job list)
    """
    pytest.skip("Requires worker.py scheduler setup — will be enabled in Plan 06")
