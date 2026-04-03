---
phase: 08-dashboard-views-and-digest
plan: 02
subsystem: ui
tags: [react, tanstack-query, date-fns, msw, vitest, tailwind]

requires:
  - phase: 08-01
    provides: DailyDigestResponse type, getLatestDigest/getDigestByDate API functions, MSW handlers for /digests/latest and /digests/:date, DigestPage test stubs

provides:
  - Full DigestPage component with prev/next date navigation
  - 4-section daily digest view: top stories, queue snapshot, yesterday summary, priority alert
  - 9 component tests covering DGST-01, DGST-02, DGST-03

affects: [08-03, 08-04, 08-05, 08-06]

tech-stack:
  added: []
  patterns:
    - "localStorage mock in test beforeEach — required for apiFetch auth header calls in jsdom"
    - "useEffect for TanStack Query data → local state sync (not during render)"
    - "isAtLatest guard drives which query's data is displayed — no duplicate fetch for latest"

key-files:
  created:
    - frontend/src/pages/DigestPage.test.tsx
  modified:
    - frontend/src/pages/DigestPage.tsx
    - frontend/src/api/digests.ts
    - frontend/src/api/types.ts
    - frontend/src/mocks/handlers.ts
    - frontend/package.json

key-decisions:
  - "localStorage mock via vi.stubGlobal required for apiFetch tests — jsdom does not provide localStorage by default in this Vitest config"
  - "useEffect syncs latestQuery data to currentDate/latestDate state — direct render-time state updates (without useEffect) cause React warnings and silent failures in tests"
  - "isAtLatest = currentDate === latestDate drives which query data to show — avoids double-fetching when at latest"

patterns-established:
  - "Pattern: localStorage mock in beforeEach — any component that uses apiFetch on render needs vi.stubGlobal('localStorage', ...) in test beforeEach"
  - "Pattern: useEffect for query-data-to-state sync — never call setState directly during render body, use useEffect with data dependency"

requirements-completed:
  - DGST-01
  - DGST-02
  - DGST-03

duration: 32min
completed: 2026-04-02
---

# Phase 08 Plan 02: DigestPage — Daily Digest View Summary

**DigestPage fully implemented with top stories, queue snapshot, yesterday summary, priority alert banner, and date-fns-based prev/next navigation — 9 component tests passing**

## Performance

- **Duration:** 32 min
- **Started:** 2026-04-02T20:01:00Z
- **Completed:** 2026-04-02T20:33:00Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 6

## Accomplishments

- Replaced DigestPage stub with full daily digest view rendering 4 sections: top stories (ordered list with source links), queue snapshot (3-card grid), yesterday summary (inline counts), priority alert banner (amber)
- Prev/Next navigation using date-fns `parse`/`format`/`subDays`/`addDays` — Next disabled when at latest date, 404 dates show empty state with Calendar icon
- 9 component tests implemented covering DGST-01 (renders today digest), DGST-02 (all 4 sections), DGST-03 (prev/next navigation, disabled state, 404 empty state)

## Task Commits

1. **Task 1: Build DigestPage with prev/next navigation and all sections** - `1080551` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `frontend/src/pages/DigestPage.tsx` — Full implementation replacing stub: useQuery for latest/date-specific digests, useEffect for state sync, prev/next navigation, 4-section layout, defensive JSONB rendering, empty/loading states
- `frontend/src/pages/DigestPage.test.tsx` — 9 tests: renders today digest, top stories list, queue snapshot cards, yesterday summary, priority alert present/absent, prev/next navigation, next-disabled-at-latest, 404 empty state
- `frontend/src/api/digests.ts` — (cherry-picked from 08-01) getLatestDigest and getDigestByDate API functions
- `frontend/src/api/types.ts` — (cherry-picked from 08-01) DailyDigestResponse and other new types appended
- `frontend/src/mocks/handlers.ts` — (cherry-picked from 08-01) 15 new MSW handlers; fixed missing KeywordCreate import (Rule 1 bug fix)
- `frontend/package.json` — Added test script entry for vitest

## Decisions Made

- `localStorage` mock required in test `beforeEach` via `vi.stubGlobal` — jsdom in this Vitest config does not expose `localStorage.getItem`, causing `apiFetch` to throw on every call. Any component that calls `apiFetch` on render needs this mock.
- Used `useEffect` to sync `latestQuery.data.digest_date` to `currentDate`/`latestDate` state — React prohibits calling `setState` directly during render. Without `useEffect`, state updates triggered silent query failures during the re-render cycle.
- Added node_modules symlink from worktree to main repo — worktree doesn't have its own `node_modules`; symlink enables running `npm run test` from worktree directory.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed missing KeywordCreate import in handlers.ts**
- **Found during:** Task 1 (setup)
- **Issue:** `handlers.ts` line 302 uses `KeywordCreate` as a type assertion but it was not in the import list from Plan 01's cherry-pick
- **Fix:** Added `KeywordCreate` to the import statement
- **Files modified:** `frontend/src/mocks/handlers.ts`
- **Verification:** TypeScript compilation succeeds in test run
- **Committed in:** `1080551` (Task 1 commit)

**2. [Rule 2 - Missing Critical] Added localStorage mock in test beforeEach**
- **Found during:** Task 1 (TDD GREEN debugging)
- **Issue:** `apiFetch` calls `localStorage.getItem('access_token')` on every request. In this jsdom test environment, `localStorage` is not available, causing `TypeError: localStorage.getItem is not a function` which silently fails the query and left the component in loading state indefinitely
- **Fix:** Added `vi.stubGlobal('localStorage', { getItem: vi.fn().mockReturnValue(null), ... })` in `beforeEach`
- **Files modified:** `frontend/src/pages/DigestPage.test.tsx`
- **Verification:** All 9 tests pass after fix
- **Committed in:** `1080551` (Task 1 commit)

**3. [Rule 3 - Blocking] Added worktree node_modules symlink and test script**
- **Found during:** Task 1 (test run setup)
- **Issue:** Worktree had no `node_modules` directory; `npm run test` had no test script in `package.json`
- **Fix:** Symlinked main repo `node_modules` to worktree; added `"test": "vitest"` to `package.json` scripts
- **Files modified:** `frontend/package.json`; symlink created (not tracked in git)
- **Verification:** `npm run test -- --run DigestPage` exits 0
- **Committed in:** `1080551` (Task 1 commit)

---

**Total deviations:** 3 auto-fixed (1 Rule 1 bug, 1 Rule 2 missing critical, 1 Rule 3 blocking)
**Impact on plan:** All auto-fixes necessary for correctness/testability. No scope creep.

## Issues Encountered

- `localStorage.getItem is not a function` in jsdom — root cause of DigestPage never rendering after query resolved. Required investigation through debug test isolation to identify. All future components using `apiFetch` on render will need the same `vi.stubGlobal('localStorage', ...)` mock in tests.

## Known Stubs

None — DigestPage fully implements all required sections with real API data wired through TanStack Query.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- DigestPage complete and tested (DGST-01, DGST-02, DGST-03)
- localStorage mock pattern established for all future component tests that use `apiFetch` on render
- Ready for ContentPage (08-03) and SettingsPage (08-04/05) implementation

---
*Phase: 08-dashboard-views-and-digest*
*Completed: 2026-04-02*
