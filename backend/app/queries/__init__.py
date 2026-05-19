"""Tenant-scoped query helpers (TENANT-03).

Re-exports the scoped_*() functions from app.queries.scoped so callers
use `from app.queries import scoped_summaries` rather than the longer
`from app.queries.scoped import scoped_summaries`. CI grep gate at
scripts/verify-tenant-isolation.sh whitelists THIS file + scoped.py.
"""
from app.queries.scoped import (
    scoped_calendar,
    scoped_summaries,
    scoped_weekly_sweeps,
)

__all__ = ["scoped_summaries", "scoped_calendar", "scoped_weekly_sweeps"]
