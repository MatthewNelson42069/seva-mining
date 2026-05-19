"""Juno daily_summary stub entry point (TENANT-08).

v3.0 Phase 9 Wave 2 — production code lives at
``scheduler/agents/daily_summary.py::run_juno_daily_summary``.

The stub writes a `daily_summaries` row with:
    company_id='juno'
    status='partial'
    gold_news_md=None
    error_text containing 'Juno content pipeline pending' or 'Phase 10'
and a corresponding `agent_runs` row:
    agent_name='juno_daily_summary'
    status='completed' (not 'running'/'failed' — writing the partial row IS success)
    notes JSONB containing {"company_id": "juno"}

Idempotency: a second call within the same 30-minute window must NOT create
a second row (per-company check via scoped_summaries('juno')).

Test approach (matches scheduler/tests/agents/test_daily_summary.py): mock
AsyncSessionLocal so the test runs against captured ORM constructor args
without needing a real Neon Postgres. The scheduler test layer doesn't have
a SQLite fixture (Postgres-only types JSONB + UUID); mocking matches the
existing daily_summary test pattern.
"""
from __future__ import annotations

import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://fake-pooler.neon.tech/db?sslmode=require"
)
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test-fake")
os.environ.setdefault("TWILIO_ACCOUNT_SID", "x")
os.environ.setdefault("TWILIO_AUTH_TOKEN", "x")
os.environ.setdefault("TWILIO_WHATSAPP_FROM", "whatsapp:+1x")
os.environ.setdefault("DIGEST_WHATSAPP_TO", "whatsapp:+1x")
os.environ.setdefault("X_API_BEARER_TOKEN", "x")
os.environ.setdefault("X_API_KEY", "x")
os.environ.setdefault("X_API_SECRET", "x")
os.environ.setdefault("SERPAPI_API_KEY", "x")
os.environ.setdefault("FRONTEND_URL", "https://x.com")


def _mock_session_factory(idempotency_returns_existing: bool = False):
    """Build a mock AsyncSessionLocal that:

    - Returns ``some-uuid`` from idempotency_skip's SELECT when
      ``idempotency_returns_existing=True`` (forces a skip path).
    - Otherwise returns None from idempotency check + captures every
      session.add() call so the test can inspect the ORM rows constructed.

    Both pathways use a single shared MagicMock as the AgentRun row
    (`session.get(AgentRun, ...)` returns it) so the test can assert
    `.status` was updated to 'completed' or 'failed'.
    """
    added_rows: list = []

    # Mock the AgentRun row returned by session.get(AgentRun, ...) after
    # session.refresh(). Track its mutations.
    agent_run_mock = MagicMock()
    agent_run_mock.id = "fake-agent-run-uuid"
    agent_run_mock.status = "running"
    agent_run_mock.errors = None
    agent_run_mock.notes = None
    agent_run_mock.ended_at = None

    # Idempotency SELECT result
    idempotency_result = MagicMock()
    idempotency_result.scalar_one_or_none.return_value = (
        "some-existing-uuid" if idempotency_returns_existing else None
    )

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=idempotency_result)
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()
    mock_session.get = AsyncMock(return_value=agent_run_mock)

    def add(row):
        added_rows.append(row)

    mock_session.add = MagicMock(side_effect=add)

    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(return_value=mock_session)
    session_cm.__aexit__ = AsyncMock(return_value=False)
    factory = MagicMock(return_value=session_cm)
    return factory, mock_session, added_rows, agent_run_mock


@pytest.mark.asyncio
async def test_run_juno_daily_summary_writes_partial_row():
    """After run_juno_daily_summary() returns, exactly 1 Juno daily_summaries
    row and 1 agent_runs row were constructed with the expected fields.
    """
    from agents.daily_summary import run_juno_daily_summary
    from models.agent_run import AgentRun
    from models.daily_summary import DailySummary

    factory, _session, added_rows, agent_run_mock = _mock_session_factory(
        idempotency_returns_existing=False
    )

    with patch("agents.daily_summary.AsyncSessionLocal", factory):
        await run_juno_daily_summary()

    # Find the AgentRun + DailySummary rows that were session.add()-ed.
    agent_run_rows = [r for r in added_rows if isinstance(r, AgentRun)]
    summary_rows = [r for r in added_rows if isinstance(r, DailySummary)]

    assert len(agent_run_rows) == 1, (
        f"Expected 1 AgentRun row added; got {len(agent_run_rows)}"
    )
    assert len(summary_rows) == 1, (
        f"Expected 1 DailySummary row added; got {len(summary_rows)}"
    )

    summary = summary_rows[0]
    assert summary.company_id == "juno", (
        f"Juno stub must set company_id='juno', got {summary.company_id!r}"
    )
    assert summary.status == "partial", (
        f"Juno stub must write status='partial' (Phase 10 fills real content); "
        f"got {summary.status!r}"
    )
    assert summary.gold_news_md is None, (
        "Juno stub must NOT write gold_news_md (Seva-specific section)"
    )
    assert summary.ontario_law_md is None
    assert summary.ontario_stats_md is None
    error_text = (summary.error_text or "").lower()
    assert (
        "juno content pipeline pending" in error_text
        or "phase 10" in error_text
    ), (
        "Juno stub must mark error_text with 'Juno content pipeline pending' "
        f"or 'Phase 10'; got {summary.error_text!r}"
    )

    # AgentRun row carries the correct agent_name + notes JSON.
    agent_run = agent_run_rows[0]
    assert agent_run.agent_name == "juno_daily_summary", (
        f"agent_name must be 'juno_daily_summary', got {agent_run.agent_name!r}"
    )
    notes_payload = json.loads(agent_run.notes)
    assert notes_payload.get("company_id") == "juno", (
        f"agent_runs.notes must carry company_id='juno' (D-08 per-tenant "
        f"telemetry); got {notes_payload}"
    )
    assert notes_payload.get("phase_10_pending") is True

    # The mocked AgentRun returned by session.get() must have been
    # transitioned to 'completed' (writing the partial row IS success).
    assert agent_run_mock.status == "completed", (
        f"juno_daily_summary agent_runs.status must be 'completed' "
        f"(stub completes successfully — writing the partial row IS success); "
        f"got {agent_run_mock.status!r}"
    )


@pytest.mark.asyncio
async def test_run_juno_daily_summary_idempotency(caplog):
    """When idempotency check returns an existing row, run_juno_daily_summary
    must log 'idempotency_skip' and return WITHOUT inserting any row.

    Mirrors the Phase 7 D-15 idempotency guard for the Seva daily_summary —
    the per-period uniqueness check applies per-company because the SELECT
    is filtered by company_id via scoped_summaries('juno').
    """
    import logging

    from agents.daily_summary import run_juno_daily_summary
    from models.agent_run import AgentRun
    from models.daily_summary import DailySummary

    factory, _session, added_rows, _agent_run_mock = _mock_session_factory(
        idempotency_returns_existing=True
    )

    with patch("agents.daily_summary.AsyncSessionLocal", factory), caplog.at_level(
        logging.INFO, logger="agents.daily_summary"
    ):
        await run_juno_daily_summary()

    # Must log idempotency_skip
    assert any(
        "juno_daily_summary idempotency_skip" in record.message
        for record in caplog.records
    ), (
        "Expected 'juno_daily_summary idempotency_skip' in log messages, got: "
        + str([r.message for r in caplog.records])
    )

    # Must NOT have added any new rows
    agent_run_rows = [r for r in added_rows if isinstance(r, AgentRun)]
    summary_rows = [r for r in added_rows if isinstance(r, DailySummary)]
    assert len(agent_run_rows) == 0, (
        f"Idempotency violation: AgentRow added despite recent row; "
        f"got {len(agent_run_rows)}"
    )
    assert len(summary_rows) == 0, (
        f"Idempotency violation: DailySummary row added despite recent row; "
        f"got {len(summary_rows)}"
    )
