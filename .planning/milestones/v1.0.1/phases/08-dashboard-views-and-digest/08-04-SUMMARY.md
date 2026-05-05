---
phase: 08-dashboard-views-and-digest
plan: "04"
subsystem: frontend
tags: [settings, watchlist, keywords, crud, tanstack-query, msw, testing]
dependency_graph:
  requires: [08-01]
  provides: [settings-page-shell, watchlist-tab, keywords-tab]
  affects: [frontend/src/pages/SettingsPage.tsx, frontend/src/components/settings/]
tech_stack:
  added: []
  patterns: [tanstack-query-mutations, msw-node-testing, jsdom-localstorage-stub, vitest-jsdom-url]
key_files:
  created:
    - frontend/src/pages/SettingsPage.tsx
    - frontend/src/components/settings/WatchlistTab.tsx
    - frontend/src/components/settings/KeywordsTab.tsx
    - frontend/src/api/settings.ts
    - frontend/src/pages/SettingsPage.test.tsx
  modified:
    - frontend/src/api/types.ts
    - frontend/src/mocks/handlers.ts
    - frontend/src/test/setup.ts
    - frontend/vite.config.ts
    - frontend/package.json
decisions:
  - "JSDOM URL must be set to http://localhost:3000 in vitest config so MSW relative path handlers resolve to matching URLs"
  - "localStorage stub required in test setup because JSDOM --localstorage-file warning indicates Storage not fully initialized"
  - "MSW relative path handlers (/watchlists) resolve using location.href as base URL — JSDOM default of about:blank was causing no-match errors"
metrics:
  duration: "612 seconds (~10 minutes)"
  completed_date: "2026-04-03"
  tasks_completed: 2
  files_modified: 9
requirements: [SETT-01, SETT-02, SETT-03]
---

# Phase 08 Plan 04: Settings Page — Watchlists and Keywords Summary

SettingsPage with 6-tab Tabs layout, full WatchlistTab CRUD with platform filter and delete confirmation, KeywordsTab with inline active toggle + weight-on-blur save — all wired to TanStack Query using MSW mock data, 7/7 tests pass.

## Tasks Completed

| Task | Description | Commit | Files |
|------|-------------|--------|-------|
| 1 | SettingsPage shell (6 tabs) + WatchlistTab | 761c3d9 | SettingsPage.tsx, WatchlistTab.tsx, KeywordsTab.tsx (initial), settings.ts, types.ts, handlers.ts, SettingsPage.test.tsx (stub) |
| 2 | KeywordsTab + SettingsPage tests | eeda13c | SettingsPage.test.tsx (full), setup.ts, vite.config.ts, package.json |

## What Was Built

### SettingsPage.tsx
6-tab layout using shadcn `<Tabs>` with `defaultValue="watchlists"`. Tab triggers: Watchlists, Keywords, Scoring, Notifications, Agent Runs, Schedule. Plans 02-05 replace the "Coming soon" placeholders.

### WatchlistTab.tsx
- Platform sub-filter: Twitter/Instagram toggle buttons (active = `variant="default"`, inactive = `variant="outline"`)
- TanStack Query fetches watchlists filtered by platform: `queryKey: ['watchlists', platform]`
- Table columns: Account Handle, Platform, Relationship Value, Notes, Active, Actions
- Inline add form row: handle input, relationship_value number (1-5), notes textarea
- Inline edit row: pre-populated fields for relationship_value and notes
- Delete confirmation dialog: "Remove Account" / "Remove @{handle} from the {platform} watchlist?" / "Keep Account" + "Remove" (destructive)
- Empty state when no entries

### KeywordsTab.tsx
- TanStack Query fetches all keywords: `queryKey: ['keywords']`
- Table columns: Term, Platform, Weight, Active, Actions
- `Active` column: `<input type="checkbox">` with `accent-blue-600` — fires PATCH immediately on change
- `Weight` column: number input (0-1, step 0.1) — saves on blur via PATCH
- Inline add form: term text input, platform select (twitter/instagram/content), weight number input
- Delete confirmation dialog: "Remove Keyword" / "Remove '{term}' from {platform} keywords?" / "Keep Keyword" + "Remove" (destructive)

### Prerequisite API layer (from plan 08-01, created here as blocking dependency)
- `frontend/src/api/settings.ts`: getWatchlists, createWatchlist, updateWatchlist, deleteWatchlist, getKeywords, createKeyword, updateKeyword, deleteKeyword, getAgentRuns, getConfig, updateConfig, getQuota
- `frontend/src/api/types.ts`: Added WatchlistCreate/Update/Response, KeywordCreate/Update/Response, ConfigEntry, QuotaResponse, AgentRunResponse, DailyDigestResponse
- `frontend/src/mocks/handlers.ts`: Added 15 new MSW handlers for watchlists, keywords, config, agent-runs, digests/latest, digests/:date, content/today, config/quota

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Created prerequisite settings.ts API module**
- **Found during:** Task 1 start
- **Issue:** Plan 08-04 depends on 08-01 which creates settings.ts, but 08-01 hadn't been run yet (parallel execution)
- **Fix:** Created frontend/src/api/settings.ts, extended types.ts, extended mocks/handlers.ts, created SettingsPage.test.tsx stub — all matching the 08-01 PLAN.md specification exactly
- **Files modified:** frontend/src/api/settings.ts, frontend/src/api/types.ts, frontend/src/mocks/handlers.ts, frontend/src/pages/SettingsPage.test.tsx
- **Commit:** 761c3d9

**2. [Rule 3 - Blocking] Fixed JSDOM location URL for MSW path matching**
- **Found during:** Task 2 (test execution)
- **Issue:** MSW relative path handlers (/watchlists) resolve using `location.href` as base URL. JSDOM default was `http://localhost:3000/` while `apiFetch` sends requests to `http://localhost/watchlists` — mismatch caused all API-dependent tests to timeout
- **Root cause:** `getAbsoluteUrl()` in MSW uses `location.href` as base. JSDOM environment had `location.href = http://localhost:3000/` but the fetch resolves to the same host — the fix was ensuring the JSDOM URL is explicitly set to match
- **Fix:** Added `environmentOptions.jsdom.url: 'http://localhost:3000'` to vitest config (ensures both fetch and MSW path resolution use the same base URL)
- **Files modified:** frontend/vite.config.ts
- **Commit:** eeda13c

**3. [Rule 3 - Blocking] Fixed localStorage not available in test environment**
- **Found during:** Task 2 (test execution)
- **Issue:** `apiFetch` calls `localStorage.getItem('access_token')` but JSDOM localStorage was not properly initialized (`--localstorage-file` warning indicates Storage object missing `getItem` method)
- **Fix:** Added minimal localStorage stub in test setup.ts — only activates if `localStorage.getItem` is not a function
- **Files modified:** frontend/src/test/setup.ts
- **Commit:** eeda13c

**4. [Rule 3 - Blocking] Added test script to package.json**
- **Found during:** Task 2 verification
- **Issue:** No `test` script in package.json — vitest was installed but not configured as a script
- **Fix:** Added `"test": "vitest"` to scripts in package.json
- **Files modified:** frontend/package.json
- **Commit:** eeda13c

## Known Stubs

None — all tab content for Watchlists and Keywords is fully wired to real API calls via MSW. Scoring, Notifications, Agent Runs, Schedule tabs show "Coming soon" placeholders intentionally — these are replaced in Plan 05.

## Self-Check: PASSED

All created files exist on disk. Both task commits found in git log:
- 761c3d9: feat(08-04): SettingsPage 6-tab shell with WatchlistTab and KeywordsTab
- eeda13c: test(08-04): SettingsPage tests with KeywordsTab — all 7 tests pass

Test suite: 19 passed, 5 skipped, 0 failed.
