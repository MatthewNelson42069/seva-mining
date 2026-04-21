"""Tests for APScheduler worker process (quick-260421-eoe topology).

Covers:
- INFRA-05 (advisory lock semantics)
- EXEC-04 (graceful error handling)
- quick-260421-eoe: 8-job topology (morning_digest + 7 content sub-agents)
  with stagger offsets [0, 17, 34, 51, 68, 85, 102] minutes and lock IDs
  1010-1016.
"""
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

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

from worker import (  # noqa: E402
    CONTENT_SUB_AGENTS,
    JOB_LOCK_IDS,
    build_scheduler,
    with_advisory_lock,
)


# ---------------------------------------------------------------------------
# Advisory lock semantics (INFRA-05, EXEC-04)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_advisory_lock_prevents_duplicate_run():
    """pg_try_advisory_lock returning False must NOT invoke job_fn."""
    mock_conn = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar.return_value = False
    mock_conn.execute.return_value = mock_result

    job_fn = AsyncMock()
    await with_advisory_lock(mock_conn, 1010, "sub_breaking_news", job_fn)
    job_fn.assert_not_called()


@pytest.mark.asyncio
async def test_job_exception_does_not_propagate():
    """Exceptions inside job_fn must NOT propagate; lock still released."""
    mock_conn = AsyncMock()
    acquire = MagicMock()
    acquire.scalar.return_value = True
    release = MagicMock()
    mock_conn.execute.side_effect = [acquire, release]

    async def failing_job():
        raise RuntimeError("Agent crashed")

    await with_advisory_lock(mock_conn, 1010, "sub_breaking_news", failing_job)
    assert mock_conn.execute.call_count == 2


# ---------------------------------------------------------------------------
# quick-260421-eoe: 8-job topology
# ---------------------------------------------------------------------------

def test_content_sub_agents_has_seven_entries():
    """CONTENT_SUB_AGENTS registration table must contain exactly 7 sub-agents."""
    assert len(CONTENT_SUB_AGENTS) == 7


def test_sub_agent_staggering():
    """Offsets are exactly [0, 17, 34, 51, 68, 85, 102] minutes in priority order."""
    offsets = [t[4] for t in CONTENT_SUB_AGENTS]
    assert offsets == [0, 17, 34, 51, 68, 85, 102]


def test_sub_agent_lock_ids():
    """Lock IDs cover 1010-1016 (inclusive) mapped to the sub_* job IDs."""
    sub_entries = {job_id: lock_id for job_id, _, _, lock_id, _ in CONTENT_SUB_AGENTS}
    assert sub_entries == {
        "sub_breaking_news": 1010,
        "sub_threads":       1011,
        "sub_long_form":     1012,
        "sub_quotes":        1013,
        "sub_infographics":  1014,
        "sub_video_clip":    1015,
        "sub_gold_history":  1016,
    }
    # Also assert JOB_LOCK_IDS matches.
    for job_id, lock_id in sub_entries.items():
        assert JOB_LOCK_IDS[job_id] == lock_id


def test_retired_crons_absent_from_job_lock_ids():
    """content_agent (1003) and gold_history_agent (1009) must NOT appear."""
    assert "content_agent" not in JOB_LOCK_IDS
    assert "gold_history_agent" not in JOB_LOCK_IDS
    assert "twitter_agent" not in JOB_LOCK_IDS
    assert "expiry_sweep" not in JOB_LOCK_IDS
    # Exactly 8 keys total: morning_digest + 7 sub-agents.
    assert len(JOB_LOCK_IDS) == 8
    assert set(JOB_LOCK_IDS.keys()) == {
        "morning_digest",
        "sub_breaking_news", "sub_threads", "sub_long_form", "sub_quotes",
        "sub_infographics", "sub_video_clip", "sub_gold_history",
    }


@pytest.mark.asyncio
async def test_scheduler_registers_8_jobs():
    """build_scheduler() registers exactly 8 jobs with the expected IDs."""
    mock_engine = MagicMock()
    with patch("worker._read_schedule_config",
               new=AsyncMock(return_value={"morning_digest_schedule_hour": "8"})):
        scheduler = await build_scheduler(mock_engine)

    try:
        jobs = scheduler.get_jobs()
        ids = sorted(j.id for j in jobs)
        expected = sorted([
            "morning_digest",
            "sub_breaking_news", "sub_threads", "sub_long_form", "sub_quotes",
            "sub_infographics", "sub_video_clip", "sub_gold_history",
        ])
        assert ids == expected, f"expected {expected}, got {ids}"
        assert len(jobs) == 8
    finally:
        if scheduler.running:
            scheduler.shutdown(wait=False)


def test_read_schedule_config_has_no_retired_keys():
    """_read_schedule_config no longer reads content_agent_interval_hours or gold_history_hour."""
    import inspect
    from worker import _read_schedule_config
    source = inspect.getsource(_read_schedule_config)
    assert "content_agent_interval_hours" not in source
    assert "gold_history_hour" not in source
    assert "twitter_interval_hours" not in source
    assert "expiry_sweep_interval_minutes" not in source
    assert "morning_digest_schedule_hour" in source
