---
phase: 06-content-calendar
plan: 02
subsystem: api
tags: [fastapi, sqlalchemy, pydantic-v2, pytest, calendar, crud]

# Dependency graph
requires:
  - phase: 06-content-calendar (Plan 01)
    provides: Pydantic v2 schemas (CalendarItemCreate/Update/Response, CalendarRangeResponse), CalendarItem ORM model with title nullable + UNIQUE(date), Alembic migration 0013
provides:
  - Full CRUD calendar router (GET range / POST / PATCH / DELETE) replacing the Phase 5 stub
  - 15 end-to-end pytest tests covering CAL-01..CAL-04 + P1 (TZ round-trip) + P4 (explicit updated_at) + D-02 (UNIQUE(date) 409) + router-level auth gate
  - response_model_by_alias=False pattern so CalendarItemResponse emits `body` (field name) not `notes_md` (ORM alias)
affects: [06-03 (frontend useCalendar/mutations consume this API), 06-04 (calendar grid wires to these endpoints), 06-05 (Mon-Sun week navigation hooks)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "FastAPI router-level auth via Depends(get_current_user) at APIRouter() level (mirrors summaries.py); per-route deps unnecessary"
    - "response_model_by_alias=False on alias-bearing response models so the API contract surfaces field names, not ORM column aliases"
    - "Test fixtures own their SQLite engine + table creation when conftest.client lacks Base.metadata.create_all (mirrors test_crud_endpoints.py)"
    - "P1 defense pattern: import-time os.environ['TZ']='UTC' + time.tzset() before any app imports to lock the test process timezone"
    - "P4 defense pattern: explicit item.updated_at = datetime.utcnow() inside PATCH handler; schema deliberately excludes updated_at from request body"
    - "D-02 enforcement: catch IntegrityError on UNIQUE(date) violation, translate to 409 Conflict with date in detail"

key-files:
  created:
    - backend/tests/test_calendar_router.py
  modified:
    - backend/app/routers/calendar.py
    - backend/tests/test_stubs.py

key-decisions:
  - "Added response_model_by_alias=False to all response-returning routes — without it, FastAPI emits the alias (`notes_md`) instead of the field name (`body`), breaking the documented API contract"
  - "Test fixtures own their SQLite engine + create only the calendar_items table (mirrors test_crud_endpoints.py pattern). Conftest's `client`/`authed_client` do not call Base.metadata.create_all, so a self-contained fixture is required for any router that hits the DB"
  - "Removed the two test_calendar_*_stub tests from test_stubs.py — their coverage is now provided by the new module; weekly_sweeps stub tests are preserved for Phase 7 to supersede"

patterns-established:
  - "Async CRUD router pattern: GET (range query with date.asc()), POST (IntegrityError → 409), PATCH (explicit updated_at), DELETE (204 on hit, 404 on miss) — replicable shape for any single-row-per-key resource"
  - "TZ-safe pytest module: os.environ['TZ']='UTC' + time.tzset() AT MODULE TOP before any app imports, then date-string round-trip assertions to prove no silent datetime conversion"

requirements-completed: [CAL-01, CAL-02, CAL-03, CAL-04]

# Metrics
duration: ~20min
completed: 2026-05-19
---

# Phase 6 Plan 2: Calendar CRUD Router + End-to-End Tests Summary

**Full async CRUD calendar router (GET range / POST / PATCH / DELETE) with router-level auth, plus 15 pytest tests asserting P1 (TZ-safe date round-trip), P4 (explicit updated_at on PATCH), D-02 (UNIQUE(date) → 409), and the router-level 401 gate.**

## Performance

- **Duration:** ~20 min (wall-clock; parallel agent context)
- **Started:** 2026-05-19T02:55Z (approx, from agent invocation)
- **Completed:** 2026-05-19T03:01Z
- **Tasks:** 2 (both completed; one task spawned 1 auto-fix sub-commit)
- **Files modified:** 3 (router, test_stubs.py) + 1 created (test_calendar_router.py)

## Accomplishments

- **CAL-01:** `GET /calendar?start=&end=` returns `CalendarRangeResponse` (items ordered by `date ASC`).
- **CAL-02:** `POST /calendar` returns 201 + `CalendarItemResponse`; duplicate date → 409 (D-02).
- **CAL-03:** `PATCH /calendar/{item_id}` returns 200; handler explicitly sets `item.updated_at = datetime.utcnow()` (P4 defense).
- **CAL-04:** `DELETE /calendar/{item_id}` returns 204 on hit, 404 on miss.
- Router-level `Depends(get_current_user)` gates all 4 routes (verified by 2 dedicated 401 tests).
- 15 end-to-end async pytest tests pass; full backend suite is 150 passed + 5 skipped (was 137 + 5 before this plan; +15 new − 2 superseded stubs = +13 net).

## Task Commits

1. **Task 1: Replace stub router with full CRUD** — `7fb4aec` (feat)
2. **Task 2 (deviation auto-fix): Emit response by field name not alias** — `d3028ed` (fix, Rule 1)
3. **Task 2: Write end-to-end pytest coverage** — `02a2397` (test)

_Note: Task 2 produced two commits — the test suite caught a serialization bug (`notes_md` vs `body`) immediately on first run, which was fixed in a separate `fix(06-02): ...` commit before the test commit landed._

## Files Created/Modified

- `backend/app/routers/calendar.py` (147 lines) — replaces the Phase 5 stub; implements all 4 verbs with router-level auth, P1/P4/D-02 defenses, and `response_model_by_alias=False` on response-returning routes.
- `backend/tests/test_calendar_router.py` (321 lines, 15 tests) — self-contained SQLite fixture (`calendar_client` / `authed_calendar_client`) with TZ=UTC guard at module top; covers every verb + each pitfall defense + the auth gate.
- `backend/tests/test_stubs.py` (-13 lines) — removed `test_calendar_stub_returns_empty_with_auth` and `test_calendar_stub_returns_401_without_auth`; weekly_sweeps stubs intact for Phase 7.

## Pitfall Coverage Table

| Pitfall | Defense | Test name | Proof |
|---|---|---|---|
| **P1** — DATE vs DateTime TZ off-by-one | `start: date_type = Query(...)` + UTC-locked test process | `test_create_then_get_round_trips_date_in_utc` | `grep -q "start: date_type = Query" backend/app/routers/calendar.py` + `grep -q 'os.environ\["TZ"\] = "UTC"' backend/tests/test_calendar_router.py` |
| **P4** — `updated_at` not set on PATCH | Handler explicitly assigns `item.updated_at = datetime.utcnow()`; `CalendarItemUpdate` has no `updated_at` field | `test_patch_updates_body_and_bumps_updated_at` (sleeps 50ms then asserts `body["updated_at"] > original_updated`) | `grep -q "item.updated_at = datetime.utcnow()" backend/app/routers/calendar.py` |
| **D-02** — single-row-per-date | UNIQUE(date) from migration 0013; router catches `IntegrityError` → 409 | `test_post_duplicate_date_returns_409` (asserts 409 + date in detail) | `grep -q "IntegrityError" backend/app/routers/calendar.py` |

## Decisions Made

1. **`response_model_by_alias=False` on every response-returning route.** FastAPI's default is `True`, which would emit `notes_md` (the alias) in JSON instead of `body` (the field name). The API contract documented in the Pydantic schema (and consumed by the frontend in 06-03..06-05) uses `body`. Without this flag the contract would silently break — caught immediately by the round-trip test.
2. **Self-contained test fixtures (don't reuse conftest's `authed_client`).** The shared `conftest.client` fixture does NOT call `Base.metadata.create_all()` — it only sets up a session. Tests that hit real DB tables (like `test_crud_endpoints.py`) create their own engine + tables. New test module follows that established pattern with a dedicated `calendar_client` fixture that creates only the `calendar_items` table.
3. **Delete superseded stub tests rather than rewriting them.** Plan recommended this; weekly_sweeps stubs preserved for Phase 7.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] FastAPI emitted `notes_md` instead of `body` in JSON responses**
- **Found during:** Task 2 (running the new test file for the first time — `test_get_calendar_returns_items_in_date_asc` failed with `KeyError: 'body'`).
- **Issue:** `CalendarItemResponse` declares `body: str | None = Field(default=None, alias="notes_md")` with `populate_by_name=True`. FastAPI defaults `response_model_by_alias=True`, which causes the JSON output to use the alias (`notes_md`) instead of the field name (`body`). This broke the documented contract — the frontend in 06-03..06-05 consumes `body`, not `notes_md`.
- **Fix:** Added `response_model_by_alias=False` to `@router.get`, `@router.post`, and `@router.patch`. Also added a "Serialization note" block to the module docstring explaining why.
- **Files modified:** `backend/app/routers/calendar.py`
- **Verification:** All 15 new tests pass (`pytest tests/test_calendar_router.py -x` → 15 passed); full suite green (`pytest -x` → 150 passed, 5 skipped).
- **Committed in:** `d3028ed` (separate `fix(06-02): ...` commit).

**2. [Rule 3 - Blocking] Plan asserted conftest had `Base.metadata.create_all()` — it does not**
- **Found during:** Task 2 setup (writing the test fixtures).
- **Issue:** The plan's `<interfaces>` section claimed: "conftest uses `Base.metadata.create_all()` with the SQLAlchemy model definition (which DOES declare UniqueConstraint('date')), so SQLite will enforce it for inserts." After reading `backend/tests/conftest.py` end-to-end, no `create_all` call exists there. The shared `client` / `authed_client` fixtures only set up sessions; tests that need real tables must create them locally (as `test_crud_endpoints.py` does).
- **Fix:** Built a dedicated `calendar_client` / `authed_calendar_client` fixture pair inside the new test module that creates a SQLite in-memory engine, calls `await conn.run_sync(lambda c: CalendarItem.__table__.create(c))` to materialize only the calendar table, and overrides `app.dependency_overrides[get_db]`. Mirrors the proven `test_crud_endpoints.py` pattern.
- **Files modified:** `backend/tests/test_calendar_router.py` (fixture block, lines ~40-72).
- **Verification:** All tests pass; D-02 UNIQUE(date) enforcement test (`test_post_duplicate_date_returns_409`) confirms SQLite is correctly applying the constraint declared on the ORM model.
- **Committed in:** `02a2397` (part of Task 2 test commit).

---

**Total deviations:** 2 auto-fixed (1 Rule 1 bug, 1 Rule 3 blocking).
**Impact on plan:** Both fixes were necessary for the plan's success criteria to hold (correct contract emission, real DB-backed test coverage). No scope creep — every change was directly required by the documented goals.

## Issues Encountered

- The `datetime.utcnow()` DeprecationWarning fires (Python 3.12 deprecates it in favor of `datetime.now(UTC)`). The migration to timezone-aware datetimes is project-wide (15 warnings already exist across `test_crud_endpoints.py`); switching the calendar router unilaterally would create inconsistency. Deferred to a future cross-cutting refactor — logged here so it's not lost.

## User Setup Required

None — no external service configuration needed. The full backend test suite proves the API works end-to-end against an in-memory SQLite that mirrors the production schema (UNIQUE(date) enforced, Date column type round-tripping, `updated_at` bump observed).

## Manual Smoke (Live Server)

Skipped per parallel-execution context — the orchestrator runs the dev server validation after Wave 2. Acceptance is fully proven by the 15-test pytest module against the same FastAPI app instance via ASGITransport.

## Self-Check: PASSED

- [x] `backend/app/routers/calendar.py` exists with 4 verbs + P1/P4/D-02 defenses (FOUND on disk)
- [x] `backend/tests/test_calendar_router.py` exists with 15 async test functions (FOUND on disk)
- [x] `backend/tests/test_stubs.py` no longer contains calendar stub test functions
- [x] Commits exist in git log: `7fb4aec` (Task 1 feat), `d3028ed` (Rule 1 fix), `02a2397` (Task 2 test) — all verified via `git log --oneline --all | grep`
- [x] `pytest -x` exits 0: **150 passed, 5 skipped, 30 warnings in 1.42s**
- [x] `ruff check app/routers/calendar.py tests/test_calendar_router.py` → "All checks passed!"
- [x] Acceptance grep checks all pass: `@router.get|post|patch|delete`, `item.updated_at = datetime.utcnow()`, `IntegrityError`, `start: date_type = Query`, `os.environ["TZ"] = "UTC"`, no Pydantic `tag: str|Literal` field, all 4 router methods present.

## Next Phase Readiness

- **Plan 06-03 (frontend useCalendar hook):** The 4 endpoints are live, fully tested, and emit the documented `{id, date, body, created_at, updated_at}` shape. The sibling agent's frontend work in Wave 2 can integrate directly.
- **Plan 06-04 (calendar grid):** UI can call POST / PATCH / DELETE with confidence — 409 on duplicate date, 404 on missing id, 422 on blank body, 401 unauthenticated are all behaviorally locked in.
- **Plan 06-05 (week navigation):** GET range query with `start`/`end` typed as `datetime.date` is exactly the contract the Mon-Sun week boundary computation needs.

---
*Phase: 06-content-calendar*
*Completed: 2026-05-19*
