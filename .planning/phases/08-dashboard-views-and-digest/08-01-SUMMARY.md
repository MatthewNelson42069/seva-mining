---
phase: 08-dashboard-views-and-digest
plan: "01"
subsystem: frontend-api-layer, backend-config-api
tags:
  - typescript-types
  - api-modules
  - msw-handlers
  - backend-config-crud
  - test-stubs
dependency_graph:
  requires:
    - 03-approval-dashboard (frontend api/client.ts pattern)
    - 02-fastapi-backend (backend config model, router infrastructure)
  provides:
    - TypeScript types for all Phase 8 API responses
    - API client modules for digests, content, settings
    - MSW handlers for all 15+ new routes
    - Backend GET /config and PATCH /config/{key} endpoints
    - Test stubs for DigestPage, ContentPage, SettingsPage
  affects:
    - 08-02 (DigestPage component — depends on types and MSW handlers)
    - 08-03 (ContentPage component — depends on types and MSW handlers)
    - 08-04 (SettingsPage component — depends on types and MSW handlers)
    - 08-05 (DigestPage tests — unskips stubs created here)
tech_stack:
  added: []
  patterns:
    - apiFetch wrapper pattern extended to digests, content, settings modules
    - MSW handler extension pattern (append to handlers array, keep all existing)
    - SQLAlchemy upsert pattern with scalar_one_or_none + refresh
key_files:
  created:
    - frontend/src/api/digests.ts
    - frontend/src/api/content.ts
    - frontend/src/api/settings.ts
    - frontend/src/pages/DigestPage.test.tsx
    - frontend/src/pages/ContentPage.test.tsx
    - frontend/src/pages/SettingsPage.test.tsx
  modified:
    - frontend/src/api/types.ts
    - frontend/src/mocks/handlers.ts
    - backend/app/routers/config.py
    - backend/tests/test_crud_endpoints.py
decisions:
  - "MSW /config/quota handler listed before /config/:key handler to prevent generic param from matching quota path"
  - "Backend /config GET and PATCH/{key} added before /quota route in source but FastAPI routes by method so no conflict"
  - "KeywordCreate uses term field throughout (not keyword) — matches backend schema exactly"
metrics:
  duration: 8
  completed_date: "2026-04-02"
  tasks_completed: 2
  files_modified: 10
---

# Phase 8 Plan 01: TypeScript Types, API Modules, MSW Handlers, and Backend Config CRUD Summary

Foundation layer for Phase 8 dashboard views: TypeScript types, typed API client modules for digests/content/settings, MSW mock handlers covering all 15 new routes, backend GET /config and PATCH /config/{key} upsert endpoints with string primary key, and test stubs for all three new page components.

## What Was Built

**Task 1 — Frontend types, API modules, and MSW handlers:**

- Appended 9 new interfaces to `frontend/src/api/types.ts`: DailyDigestResponse, AgentRunResponse, WatchlistCreate, WatchlistUpdate, WatchlistResponse, KeywordCreate (term field), KeywordUpdate, KeywordResponse (term field), ConfigEntry, QuotaResponse
- Created `frontend/src/api/digests.ts` — getLatestDigest, getDigestByDate
- Created `frontend/src/api/content.ts` — getTodayContent
- Created `frontend/src/api/settings.ts` — full CRUD for watchlists, keywords, agent-runs, config, quota (12 exported functions)
- Extended `frontend/src/mocks/handlers.ts` with 15 new route handlers (digests/latest, digests/:date, content/today, watchlists GET/POST/PATCH/DELETE, keywords GET/POST/PATCH/DELETE, agent-runs, config GET, config/quota GET, config/:key PATCH)
- Created 3 test stub files with all tests skipped — DigestPage (8 stubs), ContentPage (8 stubs), SettingsPage (10 stubs)

**Task 2 — Backend config CRUD endpoints:**

- Added `GET /config` (list_config) — returns all config key-value pairs
- Added `PATCH /config/{key}` (update_config) — upserts by string key, not UUID
- Added ConfigUpdate Pydantic schema
- Added `_Config` SQLite test model to test_crud_endpoints.py
- Added 3 backend config tests: list_config_empty, patch_config_create, patch_config_update

## Verification Results

- Frontend: 3 test files pass, 12 tests pass, 26 skipped (all stubs)
- Backend: 19 tests pass (includes 3 new config tests)
- `grep 'term: string' frontend/src/api/types.ts` — matches (not keyword)
- `grep 'digests/latest' frontend/src/mocks/handlers.ts` — matches

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Added missing platform_user_id column to _Watchlist test model**
- **Found during:** Task 2 — first test run of test_crud_endpoints.py
- **Issue:** The `_Watchlist` SQLite test model was missing `platform_user_id` which the production watchlist router queries via SELECT. All watchlist tests were failing with `OperationalError: no such column: watchlists.platform_user_id`.
- **Fix:** Added `platform_user_id = Col(String(50))` to `_Watchlist` in test_crud_endpoints.py to mirror the production model.
- **Files modified:** backend/tests/test_crud_endpoints.py
- **Commit:** 5e94006

## Known Stubs

The 26 skipped tests in DigestPage.test.tsx, ContentPage.test.tsx, and SettingsPage.test.tsx are intentional stubs — no component code exists yet. Plans 02-04 create the components and unskip these tests.

## Self-Check: PASSED

Files created/modified verified:
- frontend/src/api/types.ts — FOUND (contains DailyDigestResponse, term: string)
- frontend/src/api/digests.ts — FOUND (exports getLatestDigest, getDigestByDate)
- frontend/src/api/content.ts — FOUND (exports getTodayContent)
- frontend/src/api/settings.ts — FOUND (exports getWatchlists, getConfig, updateConfig, getQuota)
- frontend/src/mocks/handlers.ts — FOUND (contains digests/latest, content/today, config/:key, agent-runs)
- frontend/src/pages/DigestPage.test.tsx — FOUND (describe('DigestPage'))
- frontend/src/pages/ContentPage.test.tsx — FOUND (describe('ContentPage'))
- frontend/src/pages/SettingsPage.test.tsx — FOUND (describe('SettingsPage'))
- backend/app/routers/config.py — FOUND (list_config, update_config, ConfigUpdate)
- backend/tests/test_crud_endpoints.py — FOUND (_Config, test_list_config_empty, test_patch_config_create, test_patch_config_update)

Commits verified:
- ad625fb — feat(08-01): TypeScript types, API modules, and MSW handlers
- 5e94006 — feat(08-01): backend config CRUD endpoints and tests
