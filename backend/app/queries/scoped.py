"""Tenant-scoped query helpers (TENANT-03 per 09-CONTEXT.md D-03).

Every router that touches daily_summaries, calendar_items, or weekly_sweeps
MUST start its query from a scoped_*() helper below. CI grep gate at
scripts/verify-tenant-isolation.sh blocks any raw
``select(DailySummary | CalendarItem | WeeklySweep)`` outside this module +
its __init__.py re-export.

Returns a synchronous ``Select`` so callers compose .order_by()/.limit()/
.where() and execute via the existing AsyncSession (e.g. ``await
db.execute(stmt)``).
"""
from sqlalchemy import Select, select

from app.companies import CompanyId
from app.models.calendar_item import CalendarItem
from app.models.daily_summary import DailySummary
from app.models.weekly_sweep import WeeklySweep


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
