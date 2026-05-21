"""Parity tests for v2.1 dual-model architecture.

Phase 5, Plan 03 — Verifies that scheduler/models/* and backend/app/models/*
have identical __tablename__ values, column name sets, and column types for
CalendarItem and WeeklySweep. Catches drift at test time rather than at
deploy time (Phase B precedent).

To run scheduler imports, this test temporarily adds scheduler/ to sys.path.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from sqlalchemy import Date


@pytest.fixture(scope="module")
def scheduler_path():
    scheduler_dir = Path(__file__).resolve().parents[2] / "scheduler"
    added = False
    if str(scheduler_dir) not in sys.path:
        sys.path.insert(0, str(scheduler_dir))
        added = True
    yield scheduler_dir
    if added:
        sys.path.remove(str(scheduler_dir))
        # Drop cached scheduler-side modules so test ordering stays clean
        for key in [k for k in list(sys.modules) if k.startswith("models")]:
            sys.modules.pop(key, None)


def _columns_by_name(model_cls) -> dict[str, str]:
    return {c.name: str(c.type) for c in model_cls.__table__.columns}


def test_calendar_item_parity(scheduler_path):
    # Import scheduler version after sys.path patch
    from models.calendar_item import CalendarItem as SchedulerCI

    from app.models.calendar_item import CalendarItem as BackendCI

    assert BackendCI.__tablename__ == SchedulerCI.__tablename__ == "calendar_items"

    backend_cols = _columns_by_name(BackendCI)
    scheduler_cols = _columns_by_name(SchedulerCI)

    assert set(backend_cols.keys()) == set(scheduler_cols.keys()), (
        f"Column name mismatch: backend={set(backend_cols)} scheduler={set(scheduler_cols)}"
    )
    for name in backend_cols:
        assert backend_cols[name] == scheduler_cols[name], (
            f"Column {name}: backend type={backend_cols[name]!r} "
            f"scheduler type={scheduler_cols[name]!r}"
        )


def test_weekly_sweep_parity(scheduler_path):
    from models.weekly_sweep import WeeklySweep as SchedulerWS

    from app.models.weekly_sweep import WeeklySweep as BackendWS

    assert BackendWS.__tablename__ == SchedulerWS.__tablename__ == "weekly_sweeps"

    backend_cols = _columns_by_name(BackendWS)
    scheduler_cols = _columns_by_name(SchedulerWS)

    assert set(backend_cols.keys()) == set(scheduler_cols.keys())
    for name in backend_cols:
        assert backend_cols[name] == scheduler_cols[name], (
            f"Column {name}: backend type={backend_cols[name]!r} "
            f"scheduler type={scheduler_cols[name]!r}"
        )


def test_calendar_item_uses_date_not_datetime(scheduler_path):
    """Pitfall P2: `date` column MUST be Date (NOT DateTime) on both sides."""
    from models.calendar_item import CalendarItem as SchedulerCI

    from app.models.calendar_item import CalendarItem as BackendCI

    assert isinstance(BackendCI.__table__.c.date.type, Date), (
        f"Backend CalendarItem.date type is "
        f"{type(BackendCI.__table__.c.date.type).__name__}; expected Date"
    )
    assert isinstance(SchedulerCI.__table__.c.date.type, Date), (
        f"Scheduler CalendarItem.date type is "
        f"{type(SchedulerCI.__table__.c.date.type).__name__}; expected Date"
    )


def test_weekly_sweep_uses_date_for_week_boundaries(scheduler_path):
    """week_start and week_end MUST be Date, not DateTime (same TZ off-by-one risk)."""
    from models.weekly_sweep import WeeklySweep as SchedulerWS

    from app.models.weekly_sweep import WeeklySweep as BackendWS

    for cls, label in [(BackendWS, "backend"), (SchedulerWS, "scheduler")]:
        for col_name in ("week_start", "week_end"):
            col = cls.__table__.c[col_name]
            assert isinstance(col.type, Date), (
                f"{label} WeeklySweep.{col_name} type is {type(col.type).__name__}; expected Date"
            )


# ---------------------------------------------------------------------------
# Phase 9 Wave 0 RED — DailySummary parity (TENANT-01)
#
# Mirrors the CalendarItem + WeeklySweep parity tests above. DailySummary
# parity is added in v3.0 because Phase 9 dual-edits the backend AND
# scheduler models to add `company_id`. This was not covered by the
# pre-existing parity suite (which only covered CalendarItem + WeeklySweep).
#
# (Iteration 2 — Warning 1 EXCEPTION) Per-function skip is used here
# instead of module-level skip — otherwise the existing CalendarItem +
# WeeklySweep parity tests above would also skip, regressing Phase 5 GREEN
# coverage. Wave 1 (09-02-PLAN.md Task 2 step 7) removes the per-function
# skip below to turn this test GREEN.
# ---------------------------------------------------------------------------


def test_daily_summary_parity(scheduler_path):
    """v3.0 Phase 9 Wave 1 — DailySummary parity across backend + scheduler.

    Asserts both DailySummary models share the same __tablename__, column
    names, and column types — including the v3.0 Phase 9 addition of
    `company_id VARCHAR(20) NOT NULL DEFAULT 'seva'`.
    """
    from models.daily_summary import DailySummary as SchedulerDS

    from app.models.daily_summary import DailySummary as BackendDS

    assert BackendDS.__tablename__ == SchedulerDS.__tablename__ == "daily_summaries"

    backend_cols = _columns_by_name(BackendDS)
    scheduler_cols = _columns_by_name(SchedulerDS)

    assert set(backend_cols.keys()) == set(scheduler_cols.keys()), (
        f"Column name mismatch: backend={set(backend_cols)} scheduler={set(scheduler_cols)}"
    )
    for name in backend_cols:
        assert backend_cols[name] == scheduler_cols[name], (
            f"Column {name}: backend type={backend_cols[name]!r} "
            f"scheduler type={scheduler_cols[name]!r}"
        )

    # Explicit v3.0 Phase 9 — both sides MUST carry the new company_id column.
    assert "company_id" in backend_cols, (
        "v3.0 Phase 9: backend DailySummary must carry company_id column"
    )
    assert "company_id" in scheduler_cols, (
        "v3.0 Phase 9: scheduler DailySummary must carry company_id column"
    )
