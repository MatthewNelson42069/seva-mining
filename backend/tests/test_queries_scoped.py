"""Compiled-SQL assertions for scoped_*() query helpers (TENANT-03).

v3.0 Phase 9 Wave 1 — production code lives at:
    backend/app/queries/scoped.py
      - scoped_summaries(company_id: CompanyId) -> Select
      - scoped_calendar(company_id: CompanyId) -> Select
      - scoped_weekly_sweeps(company_id: CompanyId) -> Select

Each helper MUST return a SQLAlchemy Select pre-filtered by company_id so that
the compiled SQL contains `<table>.company_id = '<company_id>'`. This is the
contract the CI grep gate enforces (scripts/verify-tenant-isolation.sh).
"""
from __future__ import annotations

from sqlalchemy.sql import Select


def test_scoped_summaries_compiles_with_filter():
    """scoped_summaries('seva') returns a Select whose compiled SQL contains
    daily_summaries.company_id = 'seva'.
    """
    from app.queries.scoped import scoped_summaries

    stmt = scoped_summaries("seva")
    assert isinstance(stmt, Select), (
        f"scoped_summaries must return a SQLAlchemy Select, got {type(stmt).__name__}"
    )

    compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "daily_summaries" in compiled, (
        f"Compiled SQL must reference daily_summaries table; got: {compiled}"
    )
    assert "company_id" in compiled, (
        f"Compiled SQL must filter on company_id; got: {compiled}"
    )
    assert "'seva'" in compiled, (
        f"Compiled SQL must bind 'seva' literal; got: {compiled}"
    )


def test_scoped_calendar_compiles_with_filter():
    """scoped_calendar('seva') returns a Select with calendar_items.company_id = 'seva'."""
    from app.queries.scoped import scoped_calendar

    stmt = scoped_calendar("seva")
    assert isinstance(stmt, Select), (
        f"scoped_calendar must return a Select, got {type(stmt).__name__}"
    )

    compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "calendar_items" in compiled
    assert "company_id" in compiled
    assert "'seva'" in compiled


def test_scoped_weekly_sweeps_compiles_with_filter():
    """scoped_weekly_sweeps('seva') returns a Select with weekly_sweeps.company_id = 'seva'."""
    from app.queries.scoped import scoped_weekly_sweeps

    stmt = scoped_weekly_sweeps("seva")
    assert isinstance(stmt, Select), (
        f"scoped_weekly_sweeps must return a Select, got {type(stmt).__name__}"
    )

    compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "weekly_sweeps" in compiled
    assert "company_id" in compiled
    assert "'seva'" in compiled


def test_scoped_summaries_with_juno():
    """scoped_summaries('juno') binds 'juno', not 'seva' — symmetry guard."""
    from app.queries.scoped import scoped_summaries

    stmt = scoped_summaries("juno")
    compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "'juno'" in compiled, (
        f"scoped_summaries('juno') must bind 'juno' literal; got: {compiled}"
    )
    assert "'seva'" not in compiled, (
        f"scoped_summaries('juno') must NOT bind 'seva'; got: {compiled}"
    )
