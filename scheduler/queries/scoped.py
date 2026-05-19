"""Tenant-scoped query helpers (TENANT-03 per 09-CONTEXT.md D-03) — scheduler side.

Every scheduler agent that touches daily_summaries, calendar_items, or
weekly_sweeps MUST start its query from a scoped_*() helper below. The CI
grep gate at scripts/verify-tenant-isolation.sh blocks any raw
``select(DailySummary | CalendarItem | WeeklySweep)`` outside this module +
its __init__.py re-export.

This is the scheduler-side mirror of ``backend/app/queries/scoped.py``. The
two modules are byte-equivalent except for the import paths
(``models.*`` here vs ``app.models.*`` in backend) — Phase 5 D-03 dual-model
parity policy.

Returns a synchronous ``Select`` so callers compose .order_by()/.limit()/
.where() and execute via the existing AsyncSession.
"""
from sqlalchemy import Select, select

from companies import CompanyId  # scheduler/companies/__init__.py
from models.calendar_item import CalendarItem
from models.daily_summary import DailySummary
from models.weekly_sweep import WeeklySweep


def scoped_summaries(company_id: CompanyId) -> Select:
    """SELECT statement pre-filtered to a single tenant's daily_summaries.

    Callers add .order_by()/.limit()/.where() and execute via AsyncSession.
    """
    return select(DailySummary).where(DailySummary.company_id == company_id)


def scoped_calendar(company_id: CompanyId) -> Select:
    """SELECT statement pre-filtered to a single tenant's calendar_items."""
    return select(CalendarItem).where(CalendarItem.company_id == company_id)


def scoped_weekly_sweeps(company_id: CompanyId) -> Select:
    """SELECT statement pre-filtered to a single tenant's weekly_sweeps."""
    return select(WeeklySweep).where(WeeklySweep.company_id == company_id)
