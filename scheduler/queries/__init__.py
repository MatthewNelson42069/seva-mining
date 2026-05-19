"""Tenant-scoped query helpers (TENANT-03) — scheduler side mirror.

Re-exports the scoped_*() functions from queries.scoped so callers use
``from queries import scoped_summaries`` rather than the longer
``from queries.scoped import scoped_summaries``. The CI grep gate at
scripts/verify-tenant-isolation.sh whitelists THIS file + scoped.py.

v3.0 Phase 9 — the scheduler runs as a separate Railway service with its own
pyproject.toml + python path; importing ``app.queries.scoped`` (the backend
mirror of this module) is not available here. We duplicate the helpers
intentionally — dual-model parity per Phase 5 D-03.
"""
from queries.scoped import (
    scoped_calendar,
    scoped_summaries,
    scoped_weekly_sweeps,
)

__all__ = ["scoped_summaries", "scoped_calendar", "scoped_weekly_sweeps"]
