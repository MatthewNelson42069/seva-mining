"""Compiled-SQL assertions for scoped_*() query helpers (TENANT-03).

Phase 9 Wave 0 RED — production code lands in Wave 1 (09-02-PLAN.md).
Helpers expected at:
    backend/app/queries/scoped.py
      - scoped_summaries(company_id: CompanyId) -> Select
      - scoped_calendar(company_id: CompanyId) -> Select
      - scoped_weekly_sweeps(company_id: CompanyId) -> Select

Each helper MUST return a SQLAlchemy Select pre-filtered by company_id so that
the compiled SQL contains `<table>.company_id = '<company_id>'`. This is the
contract the CI grep gate enforces (scripts/verify-tenant-isolation.sh).

The module-level pytest.skip below is the canonical Phase-9 Wave-0 idiom:
removing this single line in Wave 1 (after scoped.py is created) turns the
whole module GREEN.
"""
from __future__ import annotations

import pytest

pytest.skip(
    "backend/app/queries/scoped.py lands in Wave 1 (09-02-PLAN.md). "
    "Remove this line in Wave 1 Task 3 step 4 to turn tests GREEN.",
    allow_module_level=True,
)

# ---------------------------------------------------------------------------
# Unreachable until Wave 1 removes the skip line. Lazy imports inside each
# test so the module collects cleanly even before app.queries.scoped exists.
# ---------------------------------------------------------------------------

from sqlalchemy.sql import Select


def test_scoped_summaries_compiles_with_filter():
    """scoped_summaries('seva') returns a Select whose compiled SQL contains
    daily_summaries.company_id = 'seva'.
    """
    from app.queries.scoped import scoped_summaries  # lazy

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
    from app.queries.scoped import scoped_calendar  # lazy

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
    from app.queries.scoped import scoped_weekly_sweeps  # lazy

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
    from app.queries.scoped import scoped_summaries  # lazy

    stmt = scoped_summaries("juno")
    compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "'juno'" in compiled, (
        f"scoped_summaries('juno') must bind 'juno' literal; got: {compiled}"
    )
    assert "'seva'" not in compiled, (
        f"scoped_summaries('juno') must NOT bind 'seva'; got: {compiled}"
    )
