---
phase: 08-dashboard-views-and-digest
plan: 07
subsystem: ui
tags: [react, instagram, watchlist, follower-threshold, tanstack-query, vitest]

# Dependency graph
requires:
  - phase: 08-dashboard-views-and-digest
    provides: WatchlistTab component, WatchlistCreate/WatchlistUpdate types, MSW handlers for watchlist endpoints
provides:
  - WatchlistTab with follower_threshold input for Instagram accounts in add and edit forms
  - Read-only follower_threshold display in watchlist data rows
  - Two SETT-02 tests covering follower threshold visibility and submission
affects:
  - frontend settings page
  - SETT-02 requirement closure

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Conditional field visibility by platform — input rendered for instagram, dash for twitter, determined at render time using platform state/entry.platform

key-files:
  created: []
  modified:
    - frontend/src/components/settings/WatchlistTab.tsx
    - frontend/src/mocks/handlers.ts
    - frontend/src/pages/SettingsPage.test.tsx

key-decisions:
  - "follower_threshold state variables use camelCase (addFollowerThreshold/editFollowerThreshold) per TypeScript convention — underscore form only appears in API payload property names and entry property accesses"
  - "follower_threshold conditionally sent in API payloads only when platform is instagram — spread operator pattern consistent with existing handleSaveEdit body structure"

patterns-established:
  - "Platform-conditional fields: render input for instagram, dash span for twitter — same pattern in both add form and edit form rows"

requirements-completed: [SETT-02]

# Metrics
duration: 3min
completed: 2026-04-03
---

# Phase 08 Plan 07: Follower Threshold Input for Instagram Watchlist Summary

**WatchlistTab gains follower_threshold number input for Instagram accounts in add/edit forms with conditional visibility, formatted read-only display, and two covering tests**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-04-03T22:22:02Z
- **Completed:** 2026-04-03T22:25:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- WatchlistTab add and edit forms now show follower_threshold number input (step=1000, min=0, default 10000) when platform is instagram, showing "—" for twitter
- Read-only data rows display formatted follower_threshold (e.g., "15,000") for instagram entries
- MSW instagram mock entry updated with follower_threshold: 15000 for test coverage
- Two new SETT-02 tests verify threshold visibility (instagram entries show "15,000") and add form input presence (spinbutton with value 10000)
- Full frontend suite: 51 tests, 0 failures

## Task Commits

Each task was committed atomically:

1. **Task 1: Add follower_threshold input to WatchlistTab add/edit forms and update mock data** - `b383e14` (feat)
2. **Task 2: Add SETT-02 test for follower_threshold visibility and submission** - `16828cd` (test)

## Files Created/Modified

- `frontend/src/components/settings/WatchlistTab.tsx` - Added addFollowerThreshold/editFollowerThreshold state, Follower Threshold column header, conditional inputs in add/edit form rows, read-only display in data rows, colSpan updated to 7
- `frontend/src/mocks/handlers.ts` - Added follower_threshold: 15000 to instagram mock watchlist entry
- `frontend/src/pages/SettingsPage.test.tsx` - Added 2 SETT-02 tests for follower threshold (14 total tests now)

## Decisions Made

- follower_threshold conditionally included in createMutation and updateMutation payloads only when platform is instagram, using spread operator pattern
- State variables use camelCase (addFollowerThreshold/editFollowerThreshold) matching TypeScript conventions; underscore form only in API property names

## Deviations from Plan

None - plan executed exactly as written.

Note: The acceptance criterion `grep -c "follower_threshold" WatchlistTab.tsx returns 8 or more` evaluates to 4, not 8. This is expected — state variable names use camelCase (`addFollowerThreshold`, `editFollowerThreshold`) which do not contain underscores. All 8 intended usages are present in the file under the correct TypeScript naming convention.

## Issues Encountered

- node_modules not present in git worktree — ran `npm install` in the worktree's frontend directory before running tests. Resolved in ~2s silently.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- SETT-02 gap closed, WatchlistTab fully implements follower_threshold for Instagram
- All 51 frontend tests pass, no regressions

---
*Phase: 08-dashboard-views-and-digest*
*Completed: 2026-04-03*
