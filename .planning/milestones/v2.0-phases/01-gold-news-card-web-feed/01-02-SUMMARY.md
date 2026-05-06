---
phase: 01-gold-news-card-web-feed
plan: 02
subsystem: ui
tags: [react, tanstack-query, vitest, react-markdown, rehype-sanitize, api-client]

# Dependency graph
requires: []
provides:
  - react-markdown ^10.1.0 + rehype-sanitize ^6.0.0 installed as package deps
  - frontend/src/api/summaries.ts with SummaryCard, SummaryFeedResponse, getSummaries, useSummaries
  - useSummaries() TanStack Query hook with 5-min refetchInterval, no window-focus refetch
affects:
  - 01-06 (SummaryFeedPage — imports useSummaries + types from this plan)

# Tech tracking
tech-stack:
  added:
    - react-markdown@10.1.0
    - rehype-sanitize@6.0.0
  patterns:
    - TanStack Query hook with refetchInterval + refetchOnWindowFocus: false (FEED-06 pattern)
    - apiFetch<T>('/path?param=value') URL pattern for parameterized fetches
    - vi.spyOn(client, 'apiFetch').mockResolvedValue(...) for testing API calls without MSW

key-files:
  created:
    - frontend/src/api/summaries.ts
    - frontend/src/api/__tests__/summaries.test.tsx
  modified:
    - frontend/package.json
    - frontend/package-lock.json

key-decisions:
  - "react-markdown + rehype-sanitize installed in single npm install invocation (locked decision — prevents build that imports markdown without sanitizer)"
  - "useSummaries refetchInterval = 5 * 60 * 1000 (FEED-06 — per-fire freshness without manual reload)"
  - "refetchOnWindowFocus: false — read-only intelligence, no hyperactive freshness (locked CONTEXT decision)"
  - "queryKey: ['summaries', limit] — limit-parameterized cache keys for future multi-limit usage"
  - "Test file uses .tsx extension (not .ts) because JSX wrapper component requires JSX transform"

patterns-established:
  - "React hook test pattern: vi.spyOn(client, 'apiFetch') for direct spy without MSW, .tsx extension for JSX in tests"
  - "TanStack Query hook shape: queryKey includes all params, staleTime matches refetchInterval"

requirements-completed: [FEED-06]

# Metrics
duration: 8min
completed: 2026-05-06
---

# Phase 1 Plan 02: Summaries API Client + Markdown Packages Summary

**react-markdown ^10.1.0 + rehype-sanitize ^6.0.0 installed; getSummaries(limit) + useSummaries() hook wired to GET /summaries with 5-min refetch interval and no window-focus refetch**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-05-06T16:05:00Z
- **Completed:** 2026-05-06T16:13:09Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Both npm packages installed together in single invocation (locked requirement met)
- `SummaryCard` and `SummaryFeedResponse` TypeScript interfaces mirror backend schema
- `getSummaries(limit=60)` calls `GET /summaries?limit={limit}` via `apiFetch`
- `useSummaries()` hook: `refetchInterval: 5 * 60 * 1000`, `refetchOnWindowFocus: false`, `staleTime: 5 * 60 * 1000`
- 3 Vitest tests pass, build clean, tsc --noEmit clean

## Task Commits

Each task was committed atomically:

1. **Task 1: npm install react-markdown + rehype-sanitize** - `f5ea4d5` (chore)
2. **Task 2 RED: failing summaries tests** - `e50aee5` (test)
3. **Task 2 GREEN: summaries.ts implementation** - `d135298` (feat)

**Plan metadata:** (to be added in final commit)

_Note: TDD task had test → feat commits (no refactor needed — implementation was clean)_

## Files Created/Modified
- `frontend/package.json` - Added react-markdown ^10.1.0 + rehype-sanitize ^6.0.0 dependencies
- `frontend/package-lock.json` - Lock file updated (79 packages added)
- `frontend/src/api/summaries.ts` - SummaryCard, SummaryFeedResponse interfaces; getSummaries(); useSummaries() hook
- `frontend/src/api/__tests__/summaries.test.tsx` - 3 tests: default URL, custom limit, hook result shape

## Decisions Made
- Test file uses `.tsx` extension (not `.ts` as the plan specified) because the `makeWrapper` function uses JSX (`<QueryClientProvider>`) which requires the JSX transform. The plan specified `.ts` but the JSX content requires `.tsx`.
- Direct `vi.spyOn(client, 'apiFetch')` approach used instead of MSW (content-bundle pattern) — more appropriate for unit-testing a thin API function; avoids MSW server handler setup for simple call-shape tests.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed ReactNode type-only import for verbatimModuleSyntax compliance**
- **Found during:** Task 2 (build verification after GREEN)
- **Issue:** `import { ReactNode } from 'react'` fails build with `error TS1484: 'ReactNode' is a type and must be imported using a type-only import when 'verbatimModuleSyntax' is enabled`
- **Fix:** Changed to `import type { ReactNode } from 'react'`
- **Files modified:** `frontend/src/api/__tests__/summaries.test.tsx`
- **Verification:** `npm run build` exits 0
- **Committed in:** d135298 (Task 2 feat commit, staged with the implementation)

**2. [Rule 1 - Bug] Test file extension corrected from .ts to .tsx**
- **Found during:** Task 2 TDD RED phase
- **Issue:** Test file written as `.ts` but contains JSX; Vite/OXC parser rejects JSX in `.ts` files with "Expected `>` but found `Identifier`"
- **Fix:** Renamed file to `.tsx` before committing RED
- **Files modified:** renamed `summaries.test.ts` → `summaries.test.tsx`
- **Verification:** Vitest runs and all 3 tests pass
- **Committed in:** e50aee5 (RED commit)

---

**Total deviations:** 2 auto-fixed (2x Rule 1 — build/parse bugs from plan's example code)
**Impact on plan:** Both fixes are correctness requirements; zero scope change. The plan's example used `.ts` extension for a JSX-containing file — corrected during execution.

## Issues Encountered
- Plan specified test file as `summaries.test.ts` but example code contains JSX — file must be `.tsx` for the OXC transform. Caught in RED phase, fixed by rename.
- `verbatimModuleSyntax` in tsconfig requires type-only imports for type re-exports — `ReactNode` needed `import type`.

## User Setup Required
None — no external service configuration required.

## Known Stubs
None — `getSummaries` and `useSummaries` are complete implementations. The actual backend endpoint `GET /summaries` is built in plan 01-04 (backend router). Until that plan completes, the hook will return API errors in dev, but the implementation is correct.

## Next Phase Readiness
- Plan 06 (SummaryFeedPage) can now `import { useSummaries, SummaryCard, SummaryFeedResponse } from '@/api/summaries'` directly
- react-markdown and rehype-sanitize available for `SummaryCard.tsx` component rendering
- No blockers

---
*Phase: 01-gold-news-card-web-feed*
*Completed: 2026-05-06*
