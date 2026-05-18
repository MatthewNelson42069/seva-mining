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
from sqlalchemy import Date, DateTime


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
    from app.models.calendar_item import CalendarItem as BackendCI

    # Import scheduler version after sys.path patch
    from models.calendar_item import CalendarItem as SchedulerCI

    assert BackendCI.__tablename__ == SchedulerCI.__tablename__ == "calendar_items"

    backend_cols = _columns_by_name(BackendCI)
    scheduler_cols = _columns_by_name(SchedulerCI)

    assert set(backend_cols.keys()) == set(scheduler_cols.keys()), (
        f"Column name mismatch: backend={set(backend_cols)} scheduler={set(scheduler_cols)}"
    )
    for name in backend_cols:
        assert backend_cols[name] == scheduler_cols[name], (
            f"Column {name}: backend type={backend_cols[name]!r} scheduler type={scheduler_cols[name]!r}"
        )


def test_weekly_sweep_parity(scheduler_path):
    from app.models.weekly_sweep import WeeklySweep as BackendWS

    from models.weekly_sweep import WeeklySweep as SchedulerWS

    assert BackendWS.__tablename__ == SchedulerWS.__tablename__ == "weekly_sweeps"

    backend_cols = _columns_by_name(BackendWS)
    scheduler_cols = _columns_by_name(SchedulerWS)

    assert set(backend_cols.keys()) == set(scheduler_cols.keys())
    for name in backend_cols:
        assert backend_cols[name] == scheduler_cols[name], (
            f"Column {name}: backend type={backend_cols[name]!r} scheduler type={scheduler_cols[name]!r}"
        )


def test_calendar_item_uses_date_not_datetime(scheduler_path):
    """Pitfall P2: `date` column MUST be Date (NOT DateTime) on both sides."""
    from app.models.calendar_item import CalendarItem as BackendCI
    from models.calendar_item import CalendarItem as SchedulerCI

    assert isinstance(BackendCI.__table__.c.date.type, Date), (
        f"Backend CalendarItem.date type is {type(BackendCI.__table__.c.date.type).__name__}; expected Date"
    )
    assert isinstance(SchedulerCI.__table__.c.date.type, Date), (
        f"Scheduler CalendarItem.date type is {type(SchedulerCI.__table__.c.date.type).__name__}; expected Date"
    )


def test_weekly_sweep_uses_date_for_week_boundaries(scheduler_path):
    """week_start and week_end MUST be Date, not DateTime (same TZ off-by-one risk)."""
    from app.models.weekly_sweep import WeeklySweep as BackendWS
    from models.weekly_sweep import WeeklySweep as SchedulerWS

    for cls, label in [(BackendWS, "backend"), (SchedulerWS, "scheduler")]:
        for col_name in ("week_start", "week_end"):
            col = cls.__table__.c[col_name]
            assert isinstance(col.type, Date), (
                f"{label} WeeklySweep.{col_name} type is {type(col.type).__name__}; expected Date"
            )
