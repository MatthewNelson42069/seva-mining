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
    CONTENT_CRON_AGENTS,
    CONTENT_INTERVAL_AGENTS,
    JOB_LOCK_IDS,
    build_scheduler,
    reconcile_stale_runs,
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

def test_sub_agents_total_seven():
    """Interval + cron sub-agent lists together must still cover all 7 sub-agents (post-vxg: 3 interval + 4 cron)."""
    assert len(CONTENT_INTERVAL_AGENTS) + len(CONTENT_CRON_AGENTS) == 7
    assert len(CONTENT_INTERVAL_AGENTS) == 3
    assert len(CONTENT_CRON_AGENTS) == 4


def test_sub_agent_staggering():
    """Post quick-260422-vxg: only 3 interval agents remain. Offsets are [0, 17, 34] minutes — Breaking News (2h), Threads + Long-form (4h each)."""
    offsets = [t[4] for t in CONTENT_INTERVAL_AGENTS]
    assert offsets == [0, 17, 34]


def test_sub_agent_lock_ids():
    """Lock IDs cover 1010-1016 (inclusive) mapped to the sub_* job IDs across both schedule shapes."""
    sub_entries = {job_id: lock_id for job_id, _, _, lock_id, *_ in CONTENT_INTERVAL_AGENTS}
    for job_id, _, _, lock_id, *_ in CONTENT_CRON_AGENTS:
        sub_entries[job_id] = lock_id
    assert sub_entries == {
        "sub_breaking_news": 1010,
        "sub_threads":       1011,
        "sub_long_form":     1012,
        "sub_quotes":        1013,
        "sub_infographics":  1014,
        "sub_gold_media":    1015,
        "sub_gold_history":  1016,
    }
    # Also assert JOB_LOCK_IDS matches.
    for job_id, lock_id in sub_entries.items():
        assert JOB_LOCK_IDS[job_id] == lock_id


def test_quotes_is_daily_cron():
    """sub_quotes is registered as a cron sub-agent at 12:00 America/Los_Angeles (dict-shape post-vxg)."""
    quotes_entry = next(t for t in CONTENT_CRON_AGENTS if t[0] == "sub_quotes")
    assert quotes_entry[0] == "sub_quotes"
    assert quotes_entry[2] == "Quotes"
    assert quotes_entry[3] == 1013
    assert quotes_entry[4] == {"hour": 12, "minute": 0, "timezone": "America/Los_Angeles"}


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
        "sub_infographics", "sub_gold_media", "sub_gold_history",
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
            "sub_infographics", "sub_gold_media", "sub_gold_history",
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


def test_interval_agents_cadences():
    """Post-vxg interval cadences: BN=2h, Threads=4h, Long-form=4h."""
    cadences = {t[0]: t[5] for t in CONTENT_INTERVAL_AGENTS}
    assert cadences == {
        "sub_breaking_news": 2,
        "sub_threads":       4,
        "sub_long_form":     4,
    }


def test_cron_agents_count_four():
    """Post-vxg: 4 cron sub-agents (quotes / infographics / gold_media / gold_history)."""
    assert len(CONTENT_CRON_AGENTS) == 4
    ids = [t[0] for t in CONTENT_CRON_AGENTS]
    assert set(ids) == {
        "sub_quotes", "sub_infographics", "sub_gold_media", "sub_gold_history",
    }


def test_cron_agents_use_dict_shape():
    """Post-vxg: 5th tuple element is a CronTrigger kwargs dict."""
    for entry in CONTENT_CRON_AGENTS:
        assert len(entry) == 5
        assert isinstance(entry[4], dict)
        # All four fire at noon Pacific.
        assert entry[4]["hour"] == 12
        assert entry[4]["minute"] == 0
        assert entry[4]["timezone"] == "America/Los_Angeles"


def test_gold_history_is_every_other_day():
    """sub_gold_history uses day='*/2' so it fires every other day at noon PT."""
    entry = next(t for t in CONTENT_CRON_AGENTS if t[0] == "sub_gold_history")
    assert entry[3] == 1016
    assert entry[4] == {
        "day": "*/2",
        "hour": 12,
        "minute": 0,
        "timezone": "America/Los_Angeles",
    }


def test_infographics_is_daily_cron():
    entry = next(t for t in CONTENT_CRON_AGENTS if t[0] == "sub_infographics")
    assert entry[3] == 1014
    assert entry[4] == {"hour": 12, "minute": 0, "timezone": "America/Los_Angeles"}


def test_gold_media_is_daily_cron():
    entry = next(t for t in CONTENT_CRON_AGENTS if t[0] == "sub_gold_media")
    assert entry[3] == 1015
    assert entry[4] == {"hour": 12, "minute": 0, "timezone": "America/Los_Angeles"}


# ---------------------------------------------------------------------------
# Boot-time reconciler (quick-260422-l40)
# ---------------------------------------------------------------------------

def _make_mock_session_factory(rowcount: int):
    """Build a mock AsyncSessionLocal factory returning a session with the given rowcount."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.rowcount = rowcount
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()

    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(return_value=mock_session)
    session_cm.__aexit__ = AsyncMock(return_value=False)
    mock_factory = MagicMock(return_value=session_cm)
    return mock_factory, mock_session


@pytest.mark.asyncio
async def test_reconcile_stale_runs_updates_orphans():
    """reconcile_stale_runs() issues an UPDATE against agent_runs and returns rowcount."""
    mock_factory, mock_session = _make_mock_session_factory(rowcount=2)

    with patch("worker.AsyncSessionLocal", mock_factory):
        count = await reconcile_stale_runs()

    assert count == 2
    mock_session.execute.assert_called_once()
    mock_session.commit.assert_called_once()

    # Inspect the update() statement passed to session.execute
    stmt = mock_session.execute.call_args.args[0]
    compiled = str(stmt.compile(compile_kwargs={"literal_binds": False}))
    assert "agent_runs" in compiled
    assert "status" in compiled
    # Verify values set: status='failed', errors array with marker, ended_at
    params = stmt.compile().params
    assert params.get("status") == "failed" or "failed" in str(params)
    # errors should be a list (JSONB array)
    errors_val = params.get("errors")
    assert isinstance(errors_val, list), f"Expected errors to be a list, got {type(errors_val)}: {errors_val}"
    assert len(errors_val) == 1
    assert "scheduler restart" in errors_val[0]


@pytest.mark.asyncio
async def test_reconcile_stale_runs_skips_fresh_rows():
    """reconcile_stale_runs() returns 0 when no orphan rows exist (rowcount=0)."""
    mock_factory, mock_session = _make_mock_session_factory(rowcount=0)

    with patch("worker.AsyncSessionLocal", mock_factory):
        count = await reconcile_stale_runs()

    assert count == 0
    # Session was still called (UPDATE ran, just matched zero rows)
    mock_session.execute.assert_called_once()
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_reconcile_stale_runs_custom_threshold():
    """threshold_minutes kwarg is honoured — cutoff is ~60 min before now."""
    from datetime import datetime, timezone, timedelta

    mock_factory, mock_session = _make_mock_session_factory(rowcount=0)
    before = datetime.now(timezone.utc)

    with patch("worker.AsyncSessionLocal", mock_factory):
        await reconcile_stale_runs(threshold_minutes=60)

    after = datetime.now(timezone.utc)

    stmt = mock_session.execute.call_args.args[0]
    # Extract the WHERE clause criteria to find the cutoff value
    # The whereclause is a BooleanClauseList; iterate its clauses to find started_at
    found_cutoff = None
    for clause in stmt.whereclause.clauses:
        # Each clause is a BinaryExpression like AgentRun.started_at < <value>
        compiled_clause = str(clause.compile(compile_kwargs={"literal_binds": False}))
        if "started_at" in compiled_clause:
            # Get the right-hand side bound parameter value
            params = clause.compile().params
            if params:
                cutoff_val = list(params.values())[0]
                if isinstance(cutoff_val, datetime):
                    found_cutoff = cutoff_val
                    break

    assert found_cutoff is not None, "Could not find started_at cutoff in WHERE clause"
    expected_cutoff_low = before - timedelta(minutes=60) - timedelta(seconds=2)
    expected_cutoff_high = after - timedelta(minutes=60) + timedelta(seconds=2)
    assert expected_cutoff_low <= found_cutoff <= expected_cutoff_high, (
        f"Cutoff {found_cutoff} not within ±2s of 60 min ago "
        f"(range: {expected_cutoff_low} — {expected_cutoff_high})"
    )
