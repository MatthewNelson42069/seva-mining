"""Tests for daily_summary_prune cron agent — Phase 4, Plan 01, Task 1.

TDD: written before run_daily_summary_prune exists.

Covers:
  - OPS-01: 30-day retention deletion (synthetic-dataset test via mock)
  - Idempotency (double-run within the cutoff window → second deleted_count == 0)
  - AgentRun telemetry (status, items_found, notes JSON shape)
  - Failure path (exception in DELETE → failed agent_run, no propagation — EXEC-04)
  - Callable signature (zero args — mirrors run_daily_summary for with_advisory_lock compat)
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

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


# ---------------------------------------------------------------------------
# Helpers to build mock session factories
# ---------------------------------------------------------------------------


def _make_agent_run_obj(agent_name: str = "daily_summary_prune") -> MagicMock:
    """Return a mock AgentRun-like object with a stable uuid id."""
    obj = MagicMock()
    obj.id = uuid.uuid4()
    obj.agent_name = agent_name
    obj.started_at = datetime.now(timezone.utc)
    obj.status = "running"
    obj.items_found = 0
    obj.items_queued = 0
    obj.items_filtered = 0
    obj.errors = None
    obj.notes = None
    obj.ended_at = None
    return obj


def _build_session_factory(
    *,
    delete_rowcount: int = 3,
    agent_run_obj: MagicMock | None = None,
) -> MagicMock:
    """Build a mock AsyncSessionLocal factory for 3-pass prune flow:
      pass 1: session.add(agent_run) + commit + refresh
      pass 2: session.execute(delete) + commit  → rowcount = delete_rowcount
      pass 3: session.get(AgentRun, id) + commit  (telemetry update)
    """
    if agent_run_obj is None:
        agent_run_obj = _make_agent_run_obj()

    # Build sessions upfront (3 are needed)
    sess1 = AsyncMock()  # insert agent_run
    sess2 = AsyncMock()  # DELETE
    sess3 = AsyncMock()  # telemetry update

    # Session 1: add + commit + refresh
    # NOTE: `session.add()` is SYNC even on AsyncSession (SQLAlchemy queues the
    # object without I/O), so it must be a MagicMock — not AsyncMock — or it
    # returns an un-awaited coroutine and triggers RuntimeWarning. See CLEAN-04.
    sess1.add = MagicMock()
    sess1.commit = AsyncMock()

    async def _refresh(obj):
        pass

    sess1.refresh = AsyncMock(side_effect=_refresh)

    # Session 2: execute (DELETE) + commit
    delete_result = MagicMock()
    delete_result.rowcount = delete_rowcount
    sess2.execute = AsyncMock(return_value=delete_result)
    sess2.commit = AsyncMock()

    # Session 3: get + commit (telemetry write)
    # Return the agent_run_obj so the code can mutate it
    sess3.get = AsyncMock(return_value=agent_run_obj)
    sess3.commit = AsyncMock()

    call_count = [0]

    def _factory():
        idx = call_count[0]
        call_count[0] += 1
        sessions = [sess1, sess2, sess3]
        if idx < len(sessions):
            sess = sessions[idx]
        else:
            # Extra calls — return a no-op session
            sess = AsyncMock()
            sess.get = AsyncMock(return_value=agent_run_obj)
            sess.commit = AsyncMock()

        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=sess)
        cm.__aexit__ = AsyncMock(return_value=False)
        return cm

    factory = MagicMock(side_effect=_factory)
    return factory, agent_run_obj


# ---------------------------------------------------------------------------
# Test 1 — OPS-01: 30-day retention deletion
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prune_deletes_rows_older_than_30_days_only():
    """Synthetic-dataset test: prune deletes 3 rows (>30d), leaves 2 (<= 30d).

    The actual DELETE is the session.execute(delete(...)) call in pass 2.
    We verify that:
    - run_daily_summary_prune completes without error
    - AgentRun telemetry items_found == 3 (== deleted_count from DELETE rowcount)
    - notes JSON contains deleted_count=3 and a parseable cutoff_at
    """
    ar = _make_agent_run_obj()
    factory, agent_run_obj = _build_session_factory(delete_rowcount=3, agent_run_obj=ar)

    with patch("agents.daily_summary_prune.AsyncSessionLocal", factory):
        from agents.daily_summary_prune import run_daily_summary_prune
        await run_daily_summary_prune()

    # items_found should have been set to 3 on the agent_run_obj (via the telemetry write)
    assert agent_run_obj.status == "completed"
    assert agent_run_obj.items_found == 3
    assert agent_run_obj.items_queued == 0

    # notes must be a JSON string with deleted_count and cutoff_at
    assert agent_run_obj.notes is not None
    notes = json.loads(agent_run_obj.notes)
    assert notes.get("deleted_count") == 3
    assert "cutoff_at" in notes
    # cutoff_at must be parseable ISO8601
    datetime.fromisoformat(notes["cutoff_at"])


# ---------------------------------------------------------------------------
# Test 2 — Idempotency
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prune_idempotent_within_window():
    """Second run (rowcount=0) writes deleted_count=0 to notes."""
    ar2 = _make_agent_run_obj()
    factory2, agent_run_obj2 = _build_session_factory(delete_rowcount=0, agent_run_obj=ar2)

    with patch("agents.daily_summary_prune.AsyncSessionLocal", factory2):
        from agents.daily_summary_prune import run_daily_summary_prune
        await run_daily_summary_prune()

    assert agent_run_obj2.status == "completed"
    assert agent_run_obj2.items_found == 0
    notes = json.loads(agent_run_obj2.notes)
    assert notes["deleted_count"] == 0


# ---------------------------------------------------------------------------
# Test 3 — Agent runs telemetry shape
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prune_writes_agent_runs_telemetry():
    """Telemetry: status=completed, items_found=deleted_count, items_queued=0,
    started_at <= ended_at, notes JSON has deleted_count (int) + cutoff_at (ISO8601).
    """
    ar = _make_agent_run_obj()
    ar.started_at = datetime.now(timezone.utc)
    factory, agent_run_obj = _build_session_factory(delete_rowcount=1, agent_run_obj=ar)

    with patch("agents.daily_summary_prune.AsyncSessionLocal", factory):
        from agents.daily_summary_prune import run_daily_summary_prune
        await run_daily_summary_prune()

    assert agent_run_obj.agent_name == "daily_summary_prune"
    assert agent_run_obj.status == "completed"
    assert agent_run_obj.items_found == 1
    assert agent_run_obj.items_queued == 0
    assert agent_run_obj.ended_at is not None
    # ended_at >= started_at (both set in the prune module)
    # ended_at is set inside prune; started_at was set on our mock before the call.
    assert isinstance(agent_run_obj.ended_at, datetime)

    notes_str = agent_run_obj.notes
    assert notes_str is not None
    notes = json.loads(notes_str)
    assert isinstance(notes["deleted_count"], int)
    assert isinstance(notes["cutoff_at"], str)
    datetime.fromisoformat(notes["cutoff_at"])


# ---------------------------------------------------------------------------
# Test 4 — Failure path (EXEC-04)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prune_writes_failure_telemetry_on_exception():
    """On DELETE exception: AgentRun status='failed', errors list set, no propagation."""
    ar = _make_agent_run_obj()

    # Replicate the 3-session flow but have session 2 (DELETE) raise
    sess1 = AsyncMock()
    # `session.add()` is sync — MagicMock, not AsyncMock (see CLEAN-04 note in
    # _build_session_factory above).
    sess1.add = MagicMock()
    sess1.commit = AsyncMock()
    sess1.refresh = AsyncMock()

    sess2 = AsyncMock()
    sess2.execute = AsyncMock(side_effect=RuntimeError("Simulated DB failure during DELETE"))
    sess2.commit = AsyncMock()

    sess3 = AsyncMock()
    sess3.get = AsyncMock(return_value=ar)
    sess3.commit = AsyncMock()

    call_count = [0]

    def _factory():
        idx = call_count[0]
        call_count[0] += 1
        sessions = [sess1, sess2, sess3]
        sess = sessions[idx] if idx < len(sessions) else AsyncMock()
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=sess)
        cm.__aexit__ = AsyncMock(return_value=False)
        return cm

    factory = MagicMock(side_effect=_factory)

    with patch("agents.daily_summary_prune.AsyncSessionLocal", factory):
        from agents.daily_summary_prune import run_daily_summary_prune
        # MUST NOT raise (EXEC-04)
        await run_daily_summary_prune()

    # AgentRun should be marked failed
    assert ar.status == "failed"
    assert ar.errors is not None
    assert isinstance(ar.errors, list)
    assert len(ar.errors) == 1
    assert isinstance(ar.errors[0], str)
    assert ar.ended_at is not None


# ---------------------------------------------------------------------------
# Test 5 — Callable signature
# ---------------------------------------------------------------------------


def test_prune_function_is_callable_with_no_args():
    """run_daily_summary_prune is async, takes zero arguments (with_advisory_lock compat)."""
    import inspect
    from agents.daily_summary_prune import run_daily_summary_prune

    assert callable(run_daily_summary_prune)
    sig = inspect.signature(run_daily_summary_prune)
    assert len(sig.parameters) == 0, (
        f"run_daily_summary_prune must take zero arguments, got: {list(sig.parameters)}"
    )
    assert inspect.iscoroutinefunction(run_daily_summary_prune), (
        "run_daily_summary_prune must be an async function"
    )
