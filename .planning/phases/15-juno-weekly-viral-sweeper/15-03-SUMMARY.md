---
phase: 15-juno-weekly-viral-sweeper
plan: 03
subsystem: ui
tags: [react, tanstack-query, vitest, rtl, multi-tenant, juno, weekly-sweeper]

# Dependency graph
requires:
  - phase: 09-multi-tenant-foundation
    provides: useWeeklySweeps(companyId, limit) hook + queryKeys.weeklySweeps factory (the multi-tenant scaffolding the Juno sweeper UI needed)
  - phase: 07-weekly-viral-sweeper (v2.1)
    provides: SweeperCard component + WeeklyViralSweeperPage Seva render path
  - phase: 14-juno-content-calendar
    provides: D-01 + D-04 pattern (frontend short-circuit deletion + per-tenant TanStack Query key isolation test) — mirrored verbatim for Phase 15
provides:
  - /juno/sweeper now renders the same SweeperCard render path as /seva/sweeper (no placeholder)
  - TenantWeeklyViralSweeperPage — tenant-agnostic inner component accepting companyId as a prop
  - WeeklyViralSweeperPage.test.tsx — 3 RTL tests asserting per-tenant TanStack Query key isolation
affects: [phase-15 verifier, phase-15-04 backend-isolation, future juno-feature-parity phases]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Tenant-agnostic component pattern: outer wrapper reads companyId from useParams and forwards as prop to inner component (replaces hardcoded literal at useWeeklySweeps('seva',12) callsite)"
    - "Vitest mock pattern for per-tenant TanStack Query key validation: re-implement the hook in vi.mock to defer to real useQuery + real queryKeys factory; stub only the queryFn so cache key registers while no network IO fires"

key-files:
  created:
    - frontend/src/pages/__tests__/WeeklyViralSweeperPage.test.tsx
  modified:
    - frontend/src/pages/WeeklyViralSweeperPage.tsx

key-decisions:
  - "Used the alternative vi.mock pattern (re-implement useWeeklySweeps inline calling useQuery + queryKeys.weeklySweeps directly) instead of the actual-spread pattern; the latter failed because the real useWeeklySweeps closure-binds getWeeklySweeps so mocking the export alone doesn't redirect the fetch"
  - "Renamed SevaWeeklyViralSweeperPage to TenantWeeklyViralSweeperPage (explicit tenant-agnostic signaling) per D-08 — propagates companyId as a prop instead of branching at the dispatch boundary"
  - "Both render-path empty-state tests assert the legacy 'Coming in v3.1 — Juno Sweeper not yet enabled' copy is gone via screen.queryByText(/Coming in v3\\.1/i).not.toBeInTheDocument() — surfaces a regression if anyone re-introduces the short-circuit"

patterns-established:
  - "BRAND-05 branchlessness in Phase 15 sweeper page: zero `if (companyId === 'juno')` branches survive in WeeklyViralSweeperPage.tsx — single shared render path"
  - "D-09 cross-tenant test pattern (mirror of Phase 14 D-04): fresh QueryClient per render, assert `findAll({ queryKey: ['weekly-sweeps', X] })` registers for the mounted tenant AND the opposing tenant's key has length 0 in the fresh client"

requirements-completed:
  - JSWEEP-05
  - JSWEEP-06

# Metrics
duration: 4min
completed: 2026-05-20
---

# Phase 15 Plan 03: Frontend Juno Sweeper Short-Circuit Removal Summary

**Deleted the Phase 9 D-09 Juno sweeper short-circuit and added 3 RTL tests asserting per-tenant TanStack Query key isolation between `/seva/sweeper` and `/juno/sweeper` (BRAND-05 branchlessness contract preserved; D-10 zero-regression on Seva render path)**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-05-21T00:39:21Z
- **Completed:** 2026-05-21T00:42:49Z
- **Tasks:** 2
- **Files modified:** 1 modified + 1 created
- **Tests added:** 3 (frontend RTL)
- **Frontend test pass count:** 181 / 181 (178 Phase 14 baseline + 3 new Phase 15 D-09 tests)

## Accomplishments

- **The ~13-line deletion** at `frontend/src/pages/WeeklyViralSweeperPage.tsx:48-60` — the Phase 9 D-09 short-circuit (`if (companyId === 'juno') { return ... "Coming in v3.1 — Juno Sweeper not yet enabled." }`) is GONE. D-08 satisfied.
- **The refactor** — `SevaWeeklyViralSweeperPage` (inner Seva-only component) renamed to `TenantWeeklyViralSweeperPage` and accepts `companyId: CompanyId` as a prop. The hardcoded `useWeeklySweeps('seva', 12)` callsite is now `useWeeklySweeps(companyId, 12)`. Outer wrapper (`WeeklyViralSweeperPage` default export) reads `companyId` from `useParams<{ company: string }>()` (narrowed by `CompanyScopedRoute`) and forwards it.
- **The new test file** — `frontend/src/pages/__tests__/WeeklyViralSweeperPage.test.tsx` with 3 RTL tests covering:
  1. `/juno/sweeper` registers `['weekly-sweeps', 'juno', ...]` query key AND empty-state copy renders (proves the short-circuit deletion took effect — also negatively asserts the legacy "Coming in v3.1" placeholder is gone)
  2. `/seva/sweeper` registers `['weekly-sweeps', 'seva', ...]` query key AND empty-state copy renders (D-10 parity proof)
  3. Cross-tenant key isolation: fresh QueryClient per render, Juno cache contains the Juno key but ZERO Seva entries (JSWEEP-06 contract)

## Task Commits

Each task was committed atomically with `--no-verify` per parallel-execution flag:

1. **Task 1: Delete Juno short-circuit + refactor inner component to tenant-agnostic** — `177ba68` (feat)
   - 1 file changed, 6 insertions(+), 21 deletions(-)
   - 130 lines → 115 lines (`wc -l`)
2. **Task 2: Add WeeklyViralSweeperPage TanStack Query key isolation tests** — `a335abd` (test, TDD: RED-then-GREEN with one mock-strategy iteration)
   - 1 file changed, 159 insertions(+)

## Files Created/Modified

- `frontend/src/pages/WeeklyViralSweeperPage.tsx` — **MODIFIED**: deleted 13-line short-circuit at lines 48-60; renamed inner `SevaWeeklyViralSweeperPage` → `TenantWeeklyViralSweeperPage`; replaced hardcoded `useWeeklySweeps('seva', 12)` with prop-driven `useWeeklySweeps(companyId, 12)`; outer wrapper forwards companyId from useParams
- `frontend/src/pages/__tests__/WeeklyViralSweeperPage.test.tsx` — **CREATED** (159 lines): 3 RTL tests mirroring Phase 14 D-04 (`ContentCalendarPage.test.tsx`) verbatim; uses vi.mock re-implementation pattern for `useWeeklySweeps` to keep the real `useQuery` + `queryKeys.weeklySweeps()` registration intact

## D-10 Zero-Regression Evidence (files NOT touched)

`git status --porcelain` showed empty output for these files throughout Plan 15-03 execution:

- `frontend/src/api/weeklySweeps.ts` (the hook + fetch helper — already multi-tenant from Phase 9)
- `frontend/src/api/queryKeys.ts` (the `queryKeys.weeklySweeps(companyId, limit)` factory — already 3-tuple)
- `frontend/src/components/viral/SweeperCard.tsx` (content-agnostic card; verified by direct read — no gold/defence sector literals)
- `frontend/src/__tests__/weeklySweeps.test.tsx` (existing 9 integration tests — all 9 pass byte-identically post-refactor)

`frontend/src/pages/__tests__/ContentCalendarPage.test.tsx` (Phase 14 D-04): 3/3 tests still pass, unaffected by Phase 15.

## Decisions Made

- **Mock strategy choice**: First tried the `actual` spread pattern (`vi.importActual` then spread + override `getWeeklySweeps`); test 2 failed because the real `useWeeklySweeps` closure-binds `getWeeklySweeps` inside the module, so mocking the export alone doesn't redirect the fetch. Switched to the alternative pattern (re-implement `useWeeklySweeps` in the `vi.mock` factory to call the real `useQuery` + `queryKeys.weeklySweeps()` factory) — keeps the per-tenant cache key registration real while bypassing the network entirely. The plan explicitly authorized this fallback under "If the spread pattern doesn't work due to ESM interop, the alternative is to mock both."
- **No "Coming in v3.1" residue tolerated**: Each empty-state test also negatively asserts `screen.queryByText(/Coming in v3\.1/i).not.toBeInTheDocument()` so a future regression that re-introduces the placeholder would fail loudly.
- **Tenant-agnostic naming**: Per the plan's D-08 preference, used `TenantWeeklyViralSweeperPage` (explicit signaling) over alternatives like `WeeklyViralSweeperBody`.

## Deviations from Plan

None - plan executed exactly as written. The mock-strategy fallback was pre-authorized by the plan (action step explicitly listed both patterns as acceptable; pattern 2 was selected after pattern 1 failed the first test run).

## Issues Encountered

- **Mock-strategy first attempt failed**: The `vi.importActual` + spread + override pattern resulted in tests rendering "Failed to load weekly sweeps." because the real `useWeeklySweeps` closure-binds `getWeeklySweeps` at module-load time. Resolved by switching to the alternative pattern the plan pre-authorized (re-implement the hook in the vi.mock factory). Single iteration; no scope creep.
- **Pre-existing lint errors in unrelated files**: `npm run lint` reports 15 errors in `PerAgentQueuePage.tsx`, `SummaryFeedPage.test.tsx`, etc. — these pre-date this plan and are out of scope. Confirmed via `npx eslint` on the 2 plan-touched files: both lint-clean.
- **BRAND-05 grep gate**: The plan asks "no NEW hits beyond pre-existing." Confirmed: post-edit, only 1 hit remains (`SummaryFeedPage.tsx:63` — a Phase 9-era short-circuit elsewhere in the codebase that pre-existed this plan and is out of scope per Phase 15's narrow file set). The Phase 15 deletion REMOVED a sweeper-side hit, net count decreased by 1 — contract honored.

## User Setup Required

None - no external service configuration required. This plan is pure frontend deletion + test addition. The /juno/sweeper UI render is unblocked at runtime as soon as this commit lands; the Juno sweeper cron (env-gated by `JUNO_SWEEPER_CRON_ENABLED`) is the separate Wave 3 plan (15-06) gate before any real Juno sweep row is produced.

## Next Phase Readiness

- **Wave 1 parallel plans (15-01 / 15-02 / 15-04) progressing**: at execution time, observed `e06e570 feat(15-01)`, `2a9b0b4 test(15-02)`, `3c2a2ee feat(15-02)`, `472cfca test(15-04)` had already landed in parallel. No file conflicts with Plan 15-03 (file-disjoint).
- **Phase 15 verifier**: When the Plan 15-07 verifier runs, JSWEEP-05 and JSWEEP-06 frontend portions are satisfied by this plan. The 3 RTL tests + 9 existing weeklySweeps tests cover the cross-tenant cache isolation + render parity contract.
- **No blockers** for downstream waves. Plan 15-06 (worker.py cron registration) is independent.

## Self-Check: PASSED

Verified each claim against disk:
- `frontend/src/pages/WeeklyViralSweeperPage.tsx` — FOUND
- `frontend/src/pages/__tests__/WeeklyViralSweeperPage.test.tsx` — FOUND
- Commit `177ba68` (Task 1: feat) — FOUND in `git log`
- Commit `a335abd` (Task 2: test) — FOUND in `git log`

---
*Phase: 15-juno-weekly-viral-sweeper*
*Completed: 2026-05-20*
