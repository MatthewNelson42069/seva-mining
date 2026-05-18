---
phase: 05-foundation-tabs-db-backend-stubs
plan: 04
subsystem: api

tags: [fastapi, routing, auth, jwt, stub, pytest, httpbearer]

# Dependency graph
requires:
  - phase: 05-foundation-tabs-db-backend-stubs
    provides: "calendar_items + weekly_sweeps tables (Plan 02) and SQLAlchemy models (Plan 03) that future GET routes will query — Phase 5 stubs return constants, no model queries yet"
provides:
  - "GET /calendar endpoint stub — 200 OK + {items: [], total: 0} with router-level JWT gate"
  - "GET /weekly-sweeps endpoint stub — 200 OK + {sweeps: [], total: 0} with router-level JWT gate"
  - "Router registration pattern for Phase 6/7 to extend (CRUD verbs + Pydantic schemas)"
  - "Smoke test fixtures (client_with_auth, client_no_auth) reusable for future stub-based tests"
affects: [06-calendar-crud, 07-weekly-sweeper-cron]

# Tech tracking
tech-stack:
  added: []  # No new libraries — pure FastAPI/SQLAlchemy already in stack
  patterns:
    - "Stub-first router contract: ship empty payload + auth gate in Phase N, defer Pydantic response_model and CRUD verbs to Phase N+1 to avoid throwaway signatures"
    - "Test fixture pair (client_with_auth via dependency_overrides + client_no_auth) for auth-gated endpoint smoke coverage"

key-files:
  created:
    - "backend/app/routers/calendar.py"
    - "backend/app/routers/weekly_sweeps.py"
    - "backend/tests/test_stubs.py"
  modified:
    - "backend/app/main.py"

key-decisions:
  - "Stubs return raw dict (no response_model) so Phase 6/7 can ship full Pydantic schemas without rewriting an incomplete signature"
  - "Auth enforced at router level via dependencies=[Depends(get_current_user)] (mirrors summaries.py — not per-route Depends)"
  - "Imports in main.py alphabetized (calendar before summaries; weekly_sweeps after watchlists) to match existing block ordering — minor stylistic adjustment from plan's literal sequence"
  - "Test fixture uses TestClient + app.dependency_overrides per plan spec; synthetic user returns str (matches get_current_user's actual return type — JWT 'sub' claim, not a dict)"

patterns-established:
  - "Stub-first router: Phase N ships GET-only + auth gate + empty payload; Phase N+1 replaces with full CRUD + Pydantic schemas"
  - "Auth gate at router level (not per-route) for consistency with summaries.py / digests.py"

requirements-completed: [DB-04]

# Metrics
duration: 2m 26s
completed: 2026-05-18
---

# Phase 05 Plan 04: Backend Router Stubs Summary

**Two auth-gated FastAPI stubs (GET /calendar, GET /weekly-sweeps) returning empty payloads, registered in main.py with router-level JWT auth — backend HTTP surface ready for Phase 6/7 to replace with full CRUD + Pydantic schemas.**

## Performance

- **Duration:** 2 min 26 sec
- **Started:** 2026-05-18T21:52:52Z
- **Completed:** 2026-05-18T21:55:18Z
- **Tasks:** 2
- **Files modified:** 4 (3 created, 1 modified)

## Accomplishments

- GET /calendar returns 200 OK + `{"items": [], "total": 0}` through JWT auth; 401 without auth (verified against live server with real JWT)
- GET /weekly-sweeps returns 200 OK + `{"sweeps": [], "total": 0}` through JWT auth; 401 without auth (verified against live server)
- Both routers registered in `backend/app/main.py` with router-level `Depends(get_current_user)` matching the established summaries.py pattern
- 4 new pytest smoke tests in `backend/tests/test_stubs.py` covering both endpoints in both auth states — full backend suite (127 tests) remains green
- DB-04 fulfilled (router registration + auth gating) — frontend tab shell can now confirm endpoint contracts before Phase 6/7

## Task Commits

Each task was committed atomically:

1. **Task 1: Create calendar.py + weekly_sweeps.py stub routers + wire into main.py** — `ea3ad91` (feat)
2. **Task 2: Add backend smoke test confirming 200 OK with auth + 401 without auth** — `3a4503f` (test)

_TDD note: Task 2 was a single commit (test + GREEN) because the implementation (routers) already existed from Task 1 — there was no RED phase needed since the routers landed first. The tests landed green on first run._

## Files Created/Modified

- `backend/app/routers/calendar.py` (created, 26 lines) — Phase 5 GET stub with router-level auth
- `backend/app/routers/weekly_sweeps.py` (created, 26 lines) — Phase 5 GET stub with router-level auth
- `backend/app/main.py` (modified, +4 lines) — 2 imports + 2 `include_router` calls (alphabetized within existing block)
- `backend/tests/test_stubs.py` (created, 62 lines) — 4 smoke tests via `TestClient` + `app.dependency_overrides[get_current_user]`

## Decisions Made

- **Raw dict return type, no `response_model`:** Stubs return `{"items": [], "total": 0}` / `{"sweeps": [], "total": 0}` directly. Adding Pydantic schemas now would create incomplete signatures (no item shape defined yet — that's Phase 6/7 work) that Phase 6/7 would have to fully rewrite. Better to defer.
- **Router-level auth, not per-route:** `APIRouter(... dependencies=[Depends(get_current_user)])` matches the existing `summaries.py` template (FEED-05 reference in research). All future routes added in Phase 6/7 will inherit the gate automatically.
- **Synthetic test user shape:** `get_current_user` actually returns the JWT `sub` claim as a string (per `backend/app/dependencies.py:14`), so the test fixture returns `"test-user"` not a dict. Plan example showed `{"id": "test-user", ...}` — adjusted to match actual return type. Stub endpoints don't use the returned value so either works at runtime, but matching the real signature is cleaner.
- **Alphabetical import ordering preserved:** Plan said "insert after summaries import" but `main.py` keeps imports alphabetized (auth, agent_runs, config, content, ... summaries, watchlists). New imports placed at correct alphabetical positions: `calendar` before `summaries`, `weekly_sweeps` after `watchlists`. The `include_router` calls themselves were appended after the `summaries_router` line per plan (those are not alphabetical in main.py — they reflect Phase order).

## Deviations from Plan

### Stylistic adjustments (not auto-fixes)

**1. Import alphabetization in main.py**
- **Plan said:** Add new imports "immediately AFTER the existing line `from app.routers.summaries import router as summaries_router`"
- **Did instead:** Placed `from app.routers.calendar import ...` before `summaries` import (alphabetically correct) and `from app.routers.weekly_sweeps import ...` after `watchlists` import (alphabetically correct).
- **Why:** The existing import block is strictly alphabetical (agent_runs, auth, config, content, content_bundles, digests, keywords, post_to_x, queue, summaries, watchlists). Project uses ruff which enforces isort ordering — placing them per the plan literal would either be re-sorted by the next ruff run or fail a lint hook.
- **Net effect:** Same behavior. Both imports land in the import block, no functional difference.

**2. Test fixture user shape**
- **Plan example:** `async def _fake_user(): return {"id": "test-user", "username": "test"}`
- **Did instead:** `async def _fake_user(): return "test-user"`
- **Why:** Inspection of `backend/app/dependencies.py` confirmed `get_current_user` returns a `str` (the JWT `sub` claim), not a dict. Stubs don't use the value but matching the real signature avoids confusing future readers.
- **Net effect:** Tests pass identically.

### Auto-fixed Issues

None. No Rule 1/2/3 conditions triggered.

---

**Total deviations:** 0 auto-fixes; 2 stylistic adjustments documented above (both within plan intent — neither changes behavior or scope).
**Impact on plan:** No scope creep. All must-have truths satisfied. All artifacts produced as specified. All acceptance criteria met.

## Issues Encountered

None. Tests passed on first run. Live server returned correct status codes immediately after `--reload` picked up the new files.

## Verification Evidence

**Live server (port 8000, JWT login with `seva2026`):**
```
GET /calendar (Bearer)       → 200 {"items":[],"total":0}
GET /weekly-sweeps (Bearer)  → 200 {"sweeps":[],"total":0}
GET /calendar (no auth)      → 401 {"detail":"Not authenticated"}
GET /weekly-sweeps (no auth) → 401 {"detail":"Not authenticated"}
```

**FastAPI app routes** (from `app.routes` inspection):
```
['/agent-runs', '/auth/login', '/calendar', '/config', '/config/{key}',
 '/content-bundles/{bundle_id}', '/content/today', '/digests/latest',
 '/digests/news-feed', '/digests/{digest_date}', '/docs',
 '/docs/oauth2-redirect', '/health', '/items/{item_id}/approve',
 '/items/{item_id}/post-to-x', '/items/{item_id}/reject', '/keywords',
 '/keywords/{keyword_id}', '/openapi.json', '/queue', '/redoc',
 '/summaries', '/watchlists', '/watchlists/{watchlist_id}', '/weekly-sweeps']
```

**Pytest output:**
```
tests/test_stubs.py::test_calendar_stub_returns_empty_with_auth PASSED   [ 25%]
tests/test_stubs.py::test_calendar_stub_returns_401_without_auth PASSED  [ 50%]
tests/test_stubs.py::test_weekly_sweeps_stub_returns_empty_with_auth PASSED [ 75%]
tests/test_stubs.py::test_weekly_sweeps_stub_returns_401_without_auth PASSED [100%]
============================== 4 passed in 0.01s ===============================
```

**Full backend suite:**
```
======= 127 passed, 5 skipped, 15 warnings in 1.32s =======
```

## Explicit Deferrals (Phase 6/7 Scope)

The following were deliberately NOT shipped in Phase 5 — they are Phase 6/7 deliverables:

- **No Pydantic schemas:** `backend/app/schemas/calendar.py` and `backend/app/schemas/weekly_sweep.py` do NOT exist. Phase 6 (calendar CRUD) and Phase 7 (sweeper read) will add full request/response schemas with proper item shapes. Adding stub schemas now would commit to incomplete signatures.
- **No POST/PATCH/DELETE handlers** on `/calendar`: Phase 6 ships full CRUD (CAL-01..05).
- **No DB queries:** Both stubs return constants. The SQLAlchemy models (Plan 03) and tables (Plan 02) exist but are not yet queried — Phase 6/7 will wire them in.

## Next Phase Readiness

- **Phase 6 (Calendar CRUD):** Can extend `backend/app/routers/calendar.py` by adding POST/PATCH/DELETE handlers + a Pydantic schema module. The router prefix + auth gate are already in place.
- **Phase 7 (Weekly Sweeper):** Can extend `backend/app/routers/weekly_sweeps.py` with the real GET implementation that queries the `weekly_sweeps` table.
- **Phase 5 Plan 05 (frontend tabs):** Already shipped (Wave 1) and can hit both endpoints immediately to confirm the routing contract.

## Self-Check

Verifying claims before completion.

**Files exist:**
- FOUND: backend/app/routers/calendar.py
- FOUND: backend/app/routers/weekly_sweeps.py
- FOUND: backend/tests/test_stubs.py

**Commits exist:**
- FOUND: ea3ad91 (Task 1 — feat)
- FOUND: 3a4503f (Task 2 — test)

## Self-Check: PASSED

---
*Phase: 05-foundation-tabs-db-backend-stubs*
*Plan: 04*
*Completed: 2026-05-18*
