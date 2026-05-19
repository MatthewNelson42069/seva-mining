"""Phase 5 stub smoke tests — historical placeholder.

Phase 5, Plan 04 originally verified DB-04 (router registration + auth gating)
for two stub endpoints. Both have since been superseded by full implementations
with dedicated test suites:

- The calendar stub tests were removed in Phase 6, Plan 02 when the calendar
  router was promoted to full CRUD. Coverage now lives in
  `test_calendar_router.py` (auth gate, empty range, full CRUD).
- The weekly_sweeps stub tests were removed in Phase 7, Plan 03 when the
  weekly_sweeps router was fleshed out (GET /weekly-sweeps with limit clamp,
  DESC ordering, total count). Coverage now lives in
  `test_weekly_sweeps_router.py` (auth gate, empty DB, populated DB, limit
  clamp, status serialization, response shape).

This file is intentionally kept (rather than deleted) so the supersession
trail stays visible in the repository history.
"""
from __future__ import annotations
