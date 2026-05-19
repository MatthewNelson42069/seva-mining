"""Juno daily_summary stub entry point (TENANT-08).

Phase 9 Wave 0 RED — production code lands in Wave 2 (09-03-PLAN.md).
Entry point expected at:
    scheduler/agents/daily_summary.py::run_juno_daily_summary

The stub MUST write a `daily_summaries` row with:
    company_id='juno'
    status='partial'
    gold_news_md=None
    error_text containing 'Juno content pipeline pending' or 'Phase 10'
and a corresponding `agent_runs` row:
    agent_name='juno_daily_summary'
    status='completed' (not 'running'/'failed')
    notes JSONB containing {"company_id": "juno"}

Idempotency: a second call within the same 30-minute window must NOT
create a second row.

The module-level pytest.skip below is the canonical Phase-9 Wave-0 idiom
(this is a brand-new file with no pre-existing tests — module-level skip
is safe; removal in Wave 2 is a single-line edit).
"""
from __future__ import annotations

import pytest

pytest.skip(
    "scheduler/agents/daily_summary.py:run_juno_daily_summary lands in "
    "Wave 2 (09-03-PLAN.md). Remove this line in Wave 2 Task 2 step 6 to "
    "turn tests GREEN.",
    allow_module_level=True,
)

# ---------------------------------------------------------------------------
# Unreachable until Wave 2 removes the skip line above. Lazy imports inside
# each test so the module collects cleanly even before run_juno_daily_summary
# exists in scheduler/agents/daily_summary.py.
# ---------------------------------------------------------------------------

from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_run_juno_daily_summary_writes_partial_row(
    async_db_session: AsyncSession,
):
    """After run_juno_daily_summary() returns, exactly 1 Juno row exists with
    status='partial' AND a matching agent_runs row exists.
    """
    from agents.daily_summary import run_juno_daily_summary  # lazy
    from models.daily_summary import DailySummary

    await run_juno_daily_summary()

    # Exactly 1 daily_summaries row with company_id='juno'.
    result = await async_db_session.execute(
        select(DailySummary).where(DailySummary.company_id == "juno")
    )
    rows = result.scalars().all()
    assert len(rows) == 1, (
        f"Expected exactly 1 Juno daily_summaries row; got {len(rows)}"
    )

    row = rows[0]
    assert row.company_id == "juno"
    assert row.status == "partial", (
        f"Juno stub must write status='partial' (Phase 10 fills real content); "
        f"got {row.status!r}"
    )
    assert row.gold_news_md is None, (
        "Juno stub must NOT write gold_news_md (Seva-specific section)"
    )
    error_text = (row.error_text or "").lower()
    assert (
        "juno content pipeline pending" in error_text
        or "phase 10" in error_text
    ), (
        "Juno stub must mark error_text with 'Juno content pipeline pending' "
        f"or 'Phase 10'; got {row.error_text!r}"
    )

    # agent_runs row asserted via raw SQL (telemetry table).
    runs_result = await async_db_session.execute(
        text(
            """
            SELECT status, notes
            FROM agent_runs
            WHERE agent_name = 'juno_daily_summary'
            ORDER BY started_at DESC
            LIMIT 1
            """
        )
    )
    run_row = runs_result.fetchone()
    assert run_row is not None, (
        "agent_runs must have a juno_daily_summary entry"
    )
    status, notes = run_row
    assert status == "completed", (
        f"juno_daily_summary agent_runs.status must be 'completed' "
        f"(stub completes successfully — writing the partial row IS success); "
        f"got {status!r}"
    )
    # notes is JSONB — adapter returns dict
    if isinstance(notes, str):
        import json
        notes = json.loads(notes)
    assert isinstance(notes, dict), (
        f"agent_runs.notes must be a JSONB object, got {type(notes).__name__}"
    )
    assert notes.get("company_id") == "juno", (
        f"agent_runs.notes must carry company_id='juno' (D-08 per-tenant "
        f"telemetry); got {notes}"
    )


@pytest.mark.asyncio
async def test_run_juno_daily_summary_idempotency(
    async_db_session: AsyncSession,
):
    """Calling run_juno_daily_summary() twice in the same 30-minute window
    does NOT create a second row.

    Mirrors the Phase 7 D-15 idempotency guard for the Seva daily_summary —
    the per-period uniqueness check applies per-company because the SELECT
    is filtered by company_id.
    """
    from agents.daily_summary import run_juno_daily_summary  # lazy
    from models.daily_summary import DailySummary

    await run_juno_daily_summary()
    await run_juno_daily_summary()  # second call inside the same window

    result = await async_db_session.execute(
        select(DailySummary).where(DailySummary.company_id == "juno")
    )
    rows = result.scalars().all()
    assert len(rows) == 1, (
        f"Idempotency violation: 2 Juno rows written within same window; "
        f"expected 1, got {len(rows)} — rows: "
        f"{[(r.generated_at, r.period_label) for r in rows]}"
    )
