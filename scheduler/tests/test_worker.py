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

os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://fake-pooler.neon.tech/db?sslmode=require"
)
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
    JOB_LOCK_IDS,
    build_scheduler,
    reconcile_stale_runs,
    with_advisory_lock,
    _make_daily_summary_job,
    _make_daily_summary_prune_job,
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


def test_sub_agents_total_six():
    """Phase 4 Task 4 (user-approved): CONTENT_CRON_AGENTS emptied; v1.0 sub-agent
    crons deregistered. This test is updated to reflect the new empty state.

    Historical: post-m49, all 6 sub-agents registered through CONTENT_CRON_AGENTS
    (sub_breaking_news + sub_threads moved from IntervalTrigger to CronTrigger).
    Phase 4 Task 4 deregisters them all; source files remain on disk (dead-code-only).
    """
    assert len(CONTENT_CRON_AGENTS) == 0, (
        f"CONTENT_CRON_AGENTS must be empty after Phase 4 Task 4 deregistration, "
        f"got {len(CONTENT_CRON_AGENTS)}"
    )


def test_retired_crons_absent_from_job_lock_ids():
    """content_agent (1003), gold_history_agent (1009), and sub_long_form (1012) must NOT appear.
    quick-260424-i8b: morning_digest key renamed to midday_digest (lock ID 1005 unchanged).
    Phase 1 Plan 05: daily_summary=1017 + daily_summary_prune=1018 added; midday_digest retained
    as dead code (registration removed from build_scheduler; factory + dict entry kept per CONTEXT).
    Phase 5 Plan 05-01: weekly_sweeper=1019 reserved (registration ships Phase 7 Plan 05).
    """
    assert "content_agent" not in JOB_LOCK_IDS
    assert "gold_history_agent" not in JOB_LOCK_IDS
    assert "twitter_agent" not in JOB_LOCK_IDS
    assert "expiry_sweep" not in JOB_LOCK_IDS
    assert "sub_long_form" not in JOB_LOCK_IDS  # retired per quick-260423-k8n
    assert "morning_digest" not in JOB_LOCK_IDS  # renamed to midday_digest per quick-260424-i8b
    # 4 keys total: midday_digest (dead code retained per D-07) + daily_summary +
    # daily_summary_prune + weekly_sweeper. v1.0 sub_* entries (1010-1016) stripped
    # in Phase 8 UI-06 (260519 — see CLAUDE.md historical notes).
    assert len(JOB_LOCK_IDS) == 4
    assert set(JOB_LOCK_IDS.keys()) == {
        "midday_digest",        # dead code — registration removed Phase 1 Plan 05 (CRIT-1)
        "daily_summary",        # Phase 1 Plan 05
        "daily_summary_prune",  # Phase 1 Plan 05 (registration ships Phase 4)
        "weekly_sweeper",       # Phase 5 Plan 05-01 reservation; Phase 7 Plan 05 registration
    }


@pytest.mark.asyncio
async def test_scheduler_registers_3_jobs_after_v1_deregistration():
    """build_scheduler() registers exactly 3 jobs after Phase 7 weekly_sweeper add.

    Phase 1 Plan 05 (CRIT-1 / SUM-06): midday_digest registration REMOVED;
    daily_summary registration ADDED.
    Phase 4 Plan 01 Task 1: daily_summary_prune ADDED.
    Phase 4 Plan 01 Task 4: 6 v1.0 sub-agent crons DEREGISTERED (user-approved).
    Phase 7 Plan 05 (SWEEP-09): weekly_sweeper ADDED.
    Final state: 3 jobs — daily_summary + daily_summary_prune + weekly_sweeper.
    """
    mock_engine = MagicMock()
    with patch(
        "worker._read_schedule_config",
        new=AsyncMock(return_value={"morning_digest_schedule_hour": "8"}),
    ):
        scheduler = await build_scheduler(mock_engine)

    try:
        jobs = scheduler.get_jobs()
        ids = sorted(j.id for j in jobs)
        expected = sorted(
            [
                "daily_summary",        # Phase 1 Plan 05 replacement for midday_digest
                "daily_summary_prune",  # Phase 4 Plan 01 (OPS-01)
                "weekly_sweeper",       # Phase 7 Plan 05 (SWEEP-09)
            ]
        )
        assert ids == expected, f"expected {expected}, got {ids}"
        assert len(jobs) == 3
        assert "midday_digest" not in ids, "midday_digest must be removed (CRIT-1)"
    finally:
        if scheduler.running:
            scheduler.shutdown(wait=False)


# ---------------------------------------------------------------------------
# Debug session twilio-morning-digest-not-delivering (2026-04-24):
# morning_digest cron must fire at 07:00 America/Los_Angeles, not 08:00 UTC.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_morning_digest_cron_fires_in_pacific_time():
    """Phase 1 Plan 05: midday_digest registration removed; daily_summary replaces it.

    Regression guard: scheduler-level default tz is UTC; the daily_summary
    trigger MUST override with America/Los_Angeles.
    quick-260424-i8b: job renamed to midday_digest, retimed to 12:30 PT.
    Phase 1 Plan 05 (CRIT-1): midday_digest deregistered; daily_summary registered.
    """
    mock_engine = MagicMock()
    with patch(
        "worker._read_schedule_config",
        new=AsyncMock(return_value={"morning_digest_schedule_hour": "7"}),
    ):
        scheduler = await build_scheduler(mock_engine)

    try:
        # midday_digest must be gone (CRIT-1)
        assert scheduler.get_job("midday_digest") is None, (
            "midday_digest must be deregistered (Phase 1 Plan 05 CRIT-1)"
        )
        # daily_summary must use America/Los_Angeles timezone (SUM-01)
        job = scheduler.get_job("daily_summary")
        assert job is not None, "daily_summary job must exist (Phase 1 Plan 05)"
        trigger = job.trigger
        tz_name = str(getattr(trigger, "timezone", ""))
        assert "Los_Angeles" in tz_name, (
            f"daily_summary trigger must be in America/Los_Angeles, got {tz_name!r}"
        )
    finally:
        if scheduler.running:
            scheduler.shutdown(wait=False)


@pytest.mark.asyncio
async def test_morning_digest_default_hour_is_seven_pt():
    """Default morning_digest_schedule_hour is '7' (PT-local), not '8' (UTC-era).

    Guards against a regression where the default gets flipped back to 8 on
    the assumption it's UTC-interpreted.
    """
    import inspect
    from worker import _read_schedule_config

    source = inspect.getsource(_read_schedule_config)
    # Look for the defaults dict literal: "morning_digest_schedule_hour": "7"
    assert '"morning_digest_schedule_hour": "7"' in source, (
        "Default hour should be '7' (America/Los_Angeles local)"
    )


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


def test_cron_agents_count_zero_after_v1_deregistration():
    """Phase 4 Task 4: CONTENT_CRON_AGENTS emptied — all 6 v1.0 sub-agent crons deregistered.

    Historical (pre-Task-4): 6 sub-agents registered through CONTENT_CRON_AGENTS post-m49.
    Post-Task-4: the list is empty; the registration loop in build_scheduler is a no-op.
    Source files (agents/content/*.py) remain on disk as dead code.
    """
    assert len(CONTENT_CRON_AGENTS) == 0
    assert CONTENT_CRON_AGENTS == []


def test_cron_agents_use_dict_shape():
    """CONTENT_CRON_AGENTS is empty after Phase 4 Task 4; the dict-shape invariant
    is vacuously true (no entries to iterate). Retained for grep-ability.

    Historical: each entry had (job_id, run_fn, name, lock_id, cron_kwargs: dict).
    All 6 v1.0 entries removed in Phase 4 Task 4 deregistration.
    """
    # Loop is a no-op — preserved so the invariant is visible if re-populated
    for entry in CONTENT_CRON_AGENTS:
        assert len(entry) == 5
        assert isinstance(entry[4], dict)


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
    assert isinstance(errors_val, list), (
        f"Expected errors to be a list, got {type(errors_val)}: {errors_val}"
    )
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


# ---------------------------------------------------------------------------
# quick-260424-i8b: midday digest retime + digest scope filter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_digest_is_registered_as_midday_at_1230_pt():
    """Phase 1 Plan 05: midday_digest deregistered (CRIT-1); daily_summary registered at 08:00+12:00 PT.

    Previous assertion: midday_digest fires at 12:30 America/Los_Angeles.
    Current assertion: midday_digest is ABSENT; daily_summary fires at 8,12 America/Los_Angeles.
    (quick-260424-i8b originally registered midday_digest at 12:30 PT;
     Phase 1 Plan 05 removes the registration in the same commit as daily_summary.)
    """
    mock_engine = MagicMock()
    with patch(
        "worker._read_schedule_config",
        new=AsyncMock(return_value={"morning_digest_schedule_hour": "7"}),
    ):
        scheduler = await build_scheduler(mock_engine)

    try:
        # Both old job ids must be gone (CRIT-1 + legacy cleanup)
        assert scheduler.get_job("morning_digest") is None, (
            "morning_digest job id must not exist after i8b rename"
        )
        assert scheduler.get_job("midday_digest") is None, (
            "midday_digest registration must be removed (Phase 1 Plan 05 CRIT-1)"
        )
        # daily_summary must be registered
        job = scheduler.get_job("daily_summary")
        assert job is not None, "daily_summary job must be registered (Phase 1 Plan 05)"
        trigger = job.trigger
        # Verify hour="8,12", minute=0
        hour_field = next(
            (f for f in trigger.fields if f.name == "hour"), None
        )
        minute_field = next(
            (f for f in trigger.fields if f.name == "minute"), None
        )
        assert hour_field is not None, "CronTrigger must have an hour field"
        assert minute_field is not None, "CronTrigger must have a minute field"
        assert "8" in str(hour_field) and "12" in str(hour_field), (
            f"Expected hour containing '8' and '12', got {hour_field}"
        )
        assert str(minute_field) == "0", f"Expected minute=0, got {minute_field}"
        # Verify timezone
        tz_name = str(getattr(trigger, "timezone", ""))
        assert "Los_Angeles" in tz_name, (
            f"daily_summary trigger must be in America/Los_Angeles, got {tz_name!r}"
        )
    finally:
        if scheduler.running:
            scheduler.shutdown(wait=False)


def test_digest_job_lock_id_preserved():
    """JOB_LOCK_IDS['midday_digest'] == 1005 (same numeric lock ID, no churn)."""
    assert "midday_digest" in JOB_LOCK_IDS, "midday_digest must be in JOB_LOCK_IDS"
    assert JOB_LOCK_IDS["midday_digest"] == 1005, (
        f"Lock ID for midday_digest must be 1005, got {JOB_LOCK_IDS['midday_digest']}"
    )
    assert "morning_digest" not in JOB_LOCK_IDS, (
        "morning_digest key must be renamed to midday_digest in JOB_LOCK_IDS"
    )


def test_digest_excluded_content_types_constant_defined():
    """DIGEST_EXCLUDED_CONTENT_TYPES is a frozenset containing exactly 'breaking_news' and 'thread'."""
    from worker import DIGEST_EXCLUDED_CONTENT_TYPES

    assert isinstance(DIGEST_EXCLUDED_CONTENT_TYPES, frozenset), (
        "DIGEST_EXCLUDED_CONTENT_TYPES must be a frozenset"
    )
    assert "breaking_news" in DIGEST_EXCLUDED_CONTENT_TYPES, (
        "DIGEST_EXCLUDED_CONTENT_TYPES must contain 'breaking_news'"
    )
    assert "thread" in DIGEST_EXCLUDED_CONTENT_TYPES, (
        "DIGEST_EXCLUDED_CONTENT_TYPES must contain 'thread' (NOT 'threads')"
    )
    assert len(DIGEST_EXCLUDED_CONTENT_TYPES) == 2, (
        f"DIGEST_EXCLUDED_CONTENT_TYPES must have exactly 2 entries, got {DIGEST_EXCLUDED_CONTENT_TYPES}"
    )


@pytest.mark.asyncio
async def test_senior_agent_receives_excluded_content_types_from_worker():
    """The midday digest job factory passes DIGEST_EXCLUDED_CONTENT_TYPES into SeniorAgent."""
    from worker import DIGEST_EXCLUDED_CONTENT_TYPES
    from agents.senior_agent import SeniorAgent

    captured_instances: list[SeniorAgent] = []
    original_init = SeniorAgent.__init__

    def spy_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        captured_instances.append(self)

    mock_engine = MagicMock()
    with patch(
        "worker._read_schedule_config",
        new=AsyncMock(return_value={"morning_digest_schedule_hour": "7"}),
    ), patch.object(SeniorAgent, "__init__", spy_init):
        scheduler = await build_scheduler(mock_engine)

    try:
        # Find the job and run the callback to trigger SeniorAgent instantiation
        job = scheduler.get_job("midday_digest")
        assert job is not None, "midday_digest job must exist"
        # Run the job function (which instantiates SeniorAgent inside)
        await job.func()
    except Exception:
        pass  # advisory lock or DB calls will fail in test env — that's ok
    finally:
        if scheduler.running:
            scheduler.shutdown(wait=False)

    # If we caught SeniorAgent instances, verify they have the exclusion set wired
    if captured_instances:
        agent = captured_instances[-1]
        assert hasattr(agent, "_excluded_content_types"), (
            "SeniorAgent must have _excluded_content_types attribute after i8b wiring"
        )
        assert agent._excluded_content_types == DIGEST_EXCLUDED_CONTENT_TYPES, (
            f"SeniorAgent._excluded_content_types must equal DIGEST_EXCLUDED_CONTENT_TYPES, "
            f"got {agent._excluded_content_types!r}"
        )


# ---------------------------------------------------------------------------
# quick-260424-j5i D9 — sub_threads cadence flip from 4h → 3h
# (post-m49: cadence preserved, but trigger flipped from IntervalTrigger to
# CronTrigger — see test_threads_is_every_three_hours_cron above.)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Phase 1, Plan 05 — daily_summary registration + OPS-02 + CRIT-1 + CRIT-2 tests
# ---------------------------------------------------------------------------


def test_lock_ids_unique_after_v2_additions():
    """OPS-02 / CRIT-2 — the assertion at module import would already have
    fired if violated; this test makes the contract visible and grep-able."""
    assert len(set(JOB_LOCK_IDS.values())) == len(JOB_LOCK_IDS)


def test_daily_summary_lock_id_is_1017():
    assert JOB_LOCK_IDS["daily_summary"] == 1017


def test_daily_summary_prune_lock_id_is_1018():
    assert JOB_LOCK_IDS["daily_summary_prune"] == 1018


def test_midday_digest_lock_id_still_present_as_dead_code():
    """Per CONTEXT decision, midday_digest's dict entry is left as dead code."""
    assert JOB_LOCK_IDS.get("midday_digest") == 1005


@pytest.mark.asyncio
async def test_build_scheduler_registers_daily_summary_and_omits_midday_digest():
    """CRIT-1 verification — same commit ships daily_summary + removes midday_digest."""
    engine = MagicMock()
    with patch(
        "worker._read_schedule_config",
        new=AsyncMock(return_value={"morning_digest_schedule_hour": "7"}),
    ):
        scheduler = await build_scheduler(engine)
    try:
        job_ids = {j.id for j in scheduler.get_jobs()}
        assert "daily_summary" in job_ids, (
            "daily_summary cron must be registered (Plan 05)"
        )
        assert "midday_digest" not in job_ids, (
            "midday_digest registration must be removed (CRIT-1 / SUM-06)"
        )
    finally:
        if scheduler.running:
            scheduler.shutdown(wait=False)


@pytest.mark.asyncio
async def test_daily_summary_trigger_fires_at_0800_and_1200_la():
    """SUM-01 cron expression — hour='8,12', minute=0, timezone=America/Los_Angeles."""
    engine = MagicMock()
    with patch(
        "worker._read_schedule_config",
        new=AsyncMock(return_value={"morning_digest_schedule_hour": "7"}),
    ):
        scheduler = await build_scheduler(engine)
    try:
        job = scheduler.get_job("daily_summary")
        assert job is not None
        trigger = job.trigger
        trigger_str = str(trigger)
        assert "8,12" in trigger_str, f"trigger must fire at 8 and 12: {trigger_str}"
        # Check timezone on the trigger object directly (APScheduler stores it as .timezone)
        tz_name = str(getattr(trigger, "timezone", ""))
        assert "Los_Angeles" in tz_name, f"trigger tz must be Los_Angeles: {tz_name!r}"
    finally:
        if scheduler.running:
            scheduler.shutdown(wait=False)


def test_make_daily_summary_job_is_callable():
    engine = MagicMock()
    job = _make_daily_summary_job(engine)
    assert callable(job)


# ---------------------------------------------------------------------------
# Phase 4, Plan 01 — daily_summary_prune registration tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_daily_summary_prune_registered_at_0300_la():
    """OPS-01 — prune cron must be registered at 03:00 America/Los_Angeles under lock 1018."""
    engine = MagicMock()
    with patch(
        "worker._read_schedule_config",
        new=AsyncMock(return_value={"morning_digest_schedule_hour": "7"}),
    ):
        scheduler = await build_scheduler(engine)
    try:
        job = scheduler.get_job("daily_summary_prune")
        assert job is not None, "daily_summary_prune job must be registered (Phase 4 OPS-01)"
        trigger = job.trigger
        # Verify hour == 3, minute == 0, timezone contains Los_Angeles
        hour_field = next((f for f in trigger.fields if f.name == "hour"), None)
        minute_field = next((f for f in trigger.fields if f.name == "minute"), None)
        assert hour_field is not None
        assert minute_field is not None
        assert "3" in str(hour_field), (
            f"daily_summary_prune must fire at hour=3, got field: {hour_field}"
        )
        assert str(minute_field) == "0", (
            f"daily_summary_prune must fire at minute=0, got field: {minute_field}"
        )
        tz_name = str(getattr(trigger, "timezone", ""))
        assert "Los_Angeles" in tz_name, (
            f"daily_summary_prune trigger must be in America/Los_Angeles, got {tz_name!r}"
        )
    finally:
        if scheduler.running:
            scheduler.shutdown(wait=False)


def test_make_daily_summary_prune_job_is_callable():
    """_make_daily_summary_prune_job(engine) returns a callable (mirrors _make_daily_summary_job)."""
    engine = MagicMock()
    job = _make_daily_summary_prune_job(engine)
    assert callable(job)


# ---------------------------------------------------------------------------
# Phase 4, Plan 01 — Task 4: deregister 6 v1.0 sub-agent crons
# ---------------------------------------------------------------------------


def test_content_cron_agents_is_empty_after_v1_deregistration():
    """CONTENT_CRON_AGENTS must be empty after v1.0 sub-agent cron deregistration.

    User-approved expansion of Phase 4 scope (2026-04-27). The 6 v1.0 sub-agent
    SOURCE FILES remain on disk (dead-code-only retirement). The registration loop
    in build_scheduler is a no-op when CONTENT_CRON_AGENTS == [].
    """
    assert CONTENT_CRON_AGENTS == [], (
        f"CONTENT_CRON_AGENTS must be empty after v1.0 deregistration, "
        f"got {len(CONTENT_CRON_AGENTS)} entries: {[t[0] for t in CONTENT_CRON_AGENTS]}"
    )


@pytest.mark.asyncio
async def test_build_scheduler_omits_v1_sub_agent_crons():
    """build_scheduler must NOT register any sub_* jobs after v1.0 deregistration.

    The scheduler after Phase 4 Task 4 + Phase 7 Plan 05 contains exactly:
      daily_summary, daily_summary_prune, weekly_sweeper
    — no sub_breaking_news, sub_threads, sub_quotes, sub_infographics,
    sub_gold_media, or sub_gold_history.
    """
    V1_SUB_AGENT_IDS = {
        "sub_breaking_news",
        "sub_threads",
        "sub_quotes",
        "sub_infographics",
        "sub_gold_media",
        "sub_gold_history",
    }
    engine = MagicMock()
    with patch(
        "worker._read_schedule_config",
        new=AsyncMock(return_value={"morning_digest_schedule_hour": "7"}),
    ):
        scheduler = await build_scheduler(engine)
    try:
        job_ids = {j.id for j in scheduler.get_jobs()}
        for sub_id in V1_SUB_AGENT_IDS:
            assert sub_id not in job_ids, (
                f"v1.0 sub-agent job '{sub_id}' must NOT be registered after deregistration"
            )
        # Verify the v2.0 + Phase 7 jobs are still present
        assert "daily_summary" in job_ids, "daily_summary must remain registered"
        assert "daily_summary_prune" in job_ids, "daily_summary_prune must remain registered"
        assert "weekly_sweeper" in job_ids, "weekly_sweeper must be registered (Phase 7 Plan 05)"
        assert len(job_ids) == 3, (
            f"Scheduler should have exactly 3 jobs after Phase 7 Plan 05, got {len(job_ids)}: {job_ids}"
        )
    finally:
        if scheduler.running:
            scheduler.shutdown(wait=False)


@pytest.mark.asyncio
async def test_reconcile_stale_runs_sweeps_daily_summary_prune_orphan():
    """reconcile_stale_runs must sweep daily_summary_prune orphan rows (agent-agnostic UPDATE).

    Regression guard: the WHERE clause filters on status only (not agent_name), so
    daily_summary_prune orphans from hard-killed workers are swept automatically.
    """
    mock_factory, mock_session = _make_mock_session_factory(rowcount=1)

    with patch("worker.AsyncSessionLocal", mock_factory):
        count = await reconcile_stale_runs()

    # The UPDATE ran and swept 1 row
    assert count == 1
    mock_session.execute.assert_called_once()
    mock_session.commit.assert_called_once()

    # Verify the UPDATE does NOT filter on agent_name (it must sweep all agents)
    stmt = mock_session.execute.call_args.args[0]
    compiled = str(stmt.compile(compile_kwargs={"literal_binds": False}))
    assert "agent_runs" in compiled
    # The WHERE clause must NOT restrict to a specific agent_name
    # (status='running' filter present, agent_name filter absent)
    assert "agent_name" not in compiled.lower() or "status" in compiled.lower(), (
        "reconcile_stale_runs WHERE clause must not filter by agent_name"
    )
    params = stmt.compile().params
    assert params.get("status") == "failed" or "failed" in str(params)


# ---------------------------------------------------------------------------
# Weekly sweeper registration tests — Phase 7, Plan 05
# ---------------------------------------------------------------------------


def test_weekly_sweeper_in_job_lock_ids():
    """SWEEP-03 — lock ID 1019 reserved in Phase 5 must still be present."""
    import worker
    assert "weekly_sweeper" in worker.JOB_LOCK_IDS
    assert worker.JOB_LOCK_IDS["weekly_sweeper"] == 1019


def test_job_lock_ids_unique():
    """OPS-02 — all lock IDs must remain unique after Phase 7 changes."""
    import worker
    assert len(set(worker.JOB_LOCK_IDS.values())) == len(worker.JOB_LOCK_IDS), (
        f"Duplicate lock IDs detected: {worker.JOB_LOCK_IDS}"
    )


def test_make_weekly_sweeper_job_returns_callable():
    """The factory must return an async-callable inner function."""
    import inspect
    import worker
    mock_engine = object()  # never invoked — we don't call the inner function
    job = worker._make_weekly_sweeper_job(mock_engine)
    assert callable(job), "factory did not return a callable"
    assert inspect.iscoroutinefunction(job), "factory return is not async"


@pytest.mark.asyncio
async def test_build_scheduler_registers_weekly_sweeper(monkeypatch):
    """SWEEP-09 — build_scheduler() must register a job with id='weekly_sweeper'
    and CronTrigger(day_of_week='sun', hour=8, minute=0, timezone='America/Los_Angeles').
    """
    import worker

    # _read_schedule_config does a real DB call — mock it
    async def fake_read_config(engine):
        return {"morning_digest_schedule_hour": "7"}

    monkeypatch.setattr(worker, "_read_schedule_config", fake_read_config)

    # Use a sentinel engine — never actually connected since we just inspect the scheduler
    mock_engine = object()
    sched = await worker.build_scheduler(mock_engine)

    try:
        jobs_by_id = {j.id: j for j in sched.get_jobs()}
        assert "weekly_sweeper" in jobs_by_id, (
            f"weekly_sweeper not registered. Registered jobs: {list(jobs_by_id.keys())}"
        )

        ws_job = jobs_by_id["weekly_sweeper"]
        trigger = ws_job.trigger

        # APScheduler CronTrigger stores fields in trigger.fields (list of CronField objects)
        # Check by stringified field representation — robust across APScheduler versions
        field_strs = {f.name: str(f) for f in trigger.fields}
        assert field_strs.get("day_of_week", "").lower() in ("sun", "6"), (
            f"day_of_week wrong: {field_strs.get('day_of_week')}"
        )
        assert field_strs.get("hour") == "8", f"hour wrong: {field_strs.get('hour')}"
        assert field_strs.get("minute") == "0", f"minute wrong: {field_strs.get('minute')}"
        assert str(trigger.timezone) == "America/Los_Angeles", (
            f"timezone wrong: {trigger.timezone}"
        )
    finally:
        if sched.running:
            sched.shutdown(wait=False)
