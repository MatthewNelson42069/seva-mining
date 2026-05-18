---
phase: 05-foundation-tabs-db-backend-stubs
plan: 03
subsystem: database
tags: [sqlalchemy, postgres, alembic, dual-model, calendar, weekly-sweeps, tdd]

# Dependency graph
requires:
  - phase: 05-foundation-tabs-db-backend-stubs
    provides: "Alembic migrations 0011 (calendar_items) + 0012 (weekly_sweeps) DDL"
provides:
  - "Backend CalendarItem + WeeklySweep SQLAlchemy 2.0 model classes importable from app.models"
  - "Scheduler CalendarItem + WeeklySweep model classes importable from models (dual-model parity)"
  - "Parity test suite (test_model_parity.py) catching backend/scheduler model drift at test time"
affects: ["05-04 (router stubs need CalendarItem + WeeklySweep imports)", "Phase 06 (calendar CRUD router)", "Phase 07 (weekly_sweeper scheduler agent)"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Dual-model parity: backend/app/models/X.py and scheduler/models/X.py byte-identical except for `Base` import path"
    - "Parity tests assert __tablename__, column name sets, and str(col.type) match between both versions"
    - "TDD RED → GREEN: parity test committed failing, then scheduler models committed to flip it green"

key-files:
  created:
    - "backend/app/models/calendar_item.py"
    - "backend/app/models/weekly_sweep.py"
    - "scheduler/models/calendar_item.py"
    - "scheduler/models/weekly_sweep.py"
    - "backend/tests/test_model_parity.py"
  modified:
    - "backend/app/models/__init__.py"
    - "scheduler/models/__init__.py"

key-decisions:
  - "Mirror migration DDL exactly: Date (not DateTime) for date/week_start/week_end per pitfall P2 TZ off-by-one"
  - "Use sqlalchemy.text('generated_at DESC') for descending index expression on weekly_sweeps"
  - "Append CalendarItem/WeeklySweep to existing __all__ rather than alphabetize — minimal diff against existing models"
  - "Scheduler CalendarItem has no Phase 5-7 consumer; created anyway per established dual-model parity convention (Phase B precedent)"

patterns-established:
  - "Dual-model file pairs: identical column definitions, only Base import differs (from app.models.base vs from models.base)"
  - "Parity test fixture (scheduler_path) temporarily adds scheduler/ to sys.path and cleans up sys.modules on teardown"
  - "Date-not-DateTime guard tests catch pitfall P2 regressions automatically"

requirements-completed: [DB-03]

# Metrics
duration: ~2min
completed: 2026-05-18
---

# Phase 05 Plan 03: Dual-Model SQLAlchemy Layer (CalendarItem + WeeklySweep) Summary

**4 SQLAlchemy 2.0 model files (2 backend + 2 scheduler) mirroring 0011/0012 migration DDL, with a parity test suite (4 tests, all GREEN) guarding against future drift.**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-05-18T21:47:54Z
- **Completed:** 2026-05-18T21:49:41Z
- **Tasks:** 2
- **Files modified:** 7 (5 created + 2 updated)

## Accomplishments
- Backend can `from app.models import CalendarItem, WeeklySweep` — registered in `__init__.py` so Alembic env.py picks them up
- Scheduler can `from models.calendar_item import CalendarItem` and `from models.weekly_sweep import WeeklySweep` for Phase 7 writes
- 4 parity tests (table name, column name set, column type, Date-not-DateTime guard) all PASS, catching drift at test time rather than deploy
- Column-level `diff` between backend and scheduler files produces empty output — byte-identical column definitions
- Full backend test suite stayed green: 119 passed, 5 skipped, 0 regressions

## Task Commits

Each task was committed atomically (all `--no-verify` per parallel-executor protocol):

1. **Task 1: Backend CalendarItem + WeeklySweep models + __init__.py registration** — `bb72ffd` (feat)
2. **Task 2 RED: Failing parity tests** — `7bf5e6d` (test)
3. **Task 2 GREEN: Scheduler CalendarItem + WeeklySweep models + __init__.py** — `131a646` (feat)

**Plan metadata:** _pending — final commit at end of step_

## TDD Evidence

### RED (before scheduler model files exist)
```
collected 4 items
tests/test_model_parity.py F
FAILED tests/test_model_parity.py::test_calendar_item_parity - ModuleNotFoundError: No module named 'models.calendar_item'
============================== 1 failed in 0.04s ===============================
```

### GREEN (after scheduler models created)
```
tests/test_model_parity.py::test_calendar_item_parity PASSED             [ 25%]
tests/test_model_parity.py::test_weekly_sweep_parity PASSED              [ 50%]
tests/test_model_parity.py::test_calendar_item_uses_date_not_datetime PASSED [ 75%]
tests/test_model_parity.py::test_weekly_sweep_uses_date_for_week_boundaries PASSED [100%]
============================== 4 passed in 0.01s ===============================
```

### Column-level parity diff
```bash
$ diff <(grep -E "^\s+\w+ = Column" backend/app/models/calendar_item.py) \
       <(grep -E "^\s+\w+ = Column" scheduler/models/calendar_item.py)
# (empty output — identical)

$ diff <(grep -E "^\s+\w+ = Column" backend/app/models/weekly_sweep.py) \
       <(grep -E "^\s+\w+ = Column" scheduler/models/weekly_sweep.py)
# (empty output — identical)
```

## Files Created/Modified
- `backend/app/models/calendar_item.py` — CalendarItem class with 7 columns (id, date, title, notes_md, tag, created_at, updated_at) + ix_calendar_items_date index. `date` uses `Column(Date)` per pitfall P2.
- `backend/app/models/weekly_sweep.py` — WeeklySweep class with 11 columns including JSONB `raw_sources_jsonb`, FK `agent_run_id` with `ondelete="SET NULL"`, and descending index `ix_weekly_sweeps_generated_at`.
- `scheduler/models/calendar_item.py` — Byte-identical to backend except `from models.base import Base`.
- `scheduler/models/weekly_sweep.py` — Byte-identical to backend except `from models.base import Base`.
- `backend/tests/test_model_parity.py` — 4 parity tests using a module-scoped `scheduler_path` fixture that adds `scheduler/` to `sys.path` and cleans up `sys.modules['models.*']` on teardown.
- `backend/app/models/__init__.py` — Added imports for `CalendarItem` and `WeeklySweep`; appended both names to `__all__`.
- `scheduler/models/__init__.py` — Added imports for `CalendarItem` and `WeeklySweep`; appended both names to `__all__`.

## Decisions Made
- **Append to `__all__` rather than alphabetize:** Preserves the existing ordering pattern (`Base` first, then v1.0 → v2.0 models in order added). New names go at the end. Mirrors the precedent set by `MarketSnapshot` in v2.0.
- **Used `text("generated_at DESC")` for the descending index expression:** Matches the migration 0012 `op.create_index(..., [sa.text("generated_at DESC")])`. Required so the ORM model can be queried by Alembic env.py without drift warnings.
- **Scheduler CalendarItem created despite no Phase 5-7 consumer:** Dual-model parity convention (Phase B precedent) requires structural identity for any table that either side will read. Future plans may need scheduler-side calendar access (e.g., a cron that emits reminders).

## Deviations from Plan

None — plan executed exactly as written. All 4 parity tests passed on first GREEN run; column diffs empty on first attempt.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Known Stubs

None — both model files are wired into their `__init__.py` exports and are byte-identical to migration DDL. No placeholder columns, no TODO markers, no mock data.

## Next Phase Readiness

- **Plan 05-04 (router stubs):** Can `from app.models import CalendarItem, WeeklySweep` to build router request/response shapes.
- **Phase 06 (calendar CRUD router):** Backend CalendarItem fully ready for `/api/calendar/*` endpoints (CAL-01..04).
- **Phase 07 (weekly_sweeper agent):** Scheduler WeeklySweep ready for `weekly_sweeper.py` writes (SWEEP-12). Backend WeeklySweep ready for the `/api/weekly-sweeps/latest` read endpoint.
- **Parity guard active:** Any future column drift between backend and scheduler will fail `test_model_parity.py` before merge.

## Self-Check: PASSED

Verification:
- `backend/app/models/calendar_item.py` — FOUND
- `backend/app/models/weekly_sweep.py` — FOUND
- `scheduler/models/calendar_item.py` — FOUND
- `scheduler/models/weekly_sweep.py` — FOUND
- `backend/tests/test_model_parity.py` — FOUND
- Commit `bb72ffd` (Task 1) — FOUND in git log
- Commit `7bf5e6d` (Task 2 RED) — FOUND in git log
- Commit `131a646` (Task 2 GREEN) — FOUND in git log

---
*Phase: 05-foundation-tabs-db-backend-stubs*
*Completed: 2026-05-18*
