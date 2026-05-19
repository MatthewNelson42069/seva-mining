---
phase: 07-weekly-viral-sweeper
plan: 06
subsystem: ui
tags: [react, tanstack-query, react-markdown, vitest, testing-library, date-fns, frontend]

# Dependency graph
requires:
  - phase: 05-foundation-tabs-db-backend-stubs
    provides: WeeklyViralSweeperPage stub at /viral + TabbedDashboard routing
  - phase: 07-weekly-viral-sweeper
    provides: GET /weekly-sweeps live read route (Plan 07-03), weekly_sweeps DB persistence (Plan 07-04), cron registration (Plan 07-05)
provides:
  - WeeklySweepCard + WeeklySweepFeedResponse TypeScript types matching backend WeeklySweepCard schema
  - getWeeklySweeps fetch helper + useWeeklySweeps TanStack Query hook (5-min refetch interval, no window-focus refetch)
  - SweeperCard component rendering 3 react-markdown sections (Top X Posts, Most Cross-Referenced Stories, 3 Content Angles) plus completed/partial/failed status banner
  - WeeklyViralSweeperPage replacing the Phase 5 stub with loading/error/empty/populated branches + history week-picker dropdown
  - Vitest spec covering empty state, populated render, week-picker visibility, loading + error branches, all 3 status banner states, and 3-section markdown rendering (9 tests)
affects: [08-ui-polish (will retheme amber/zinc tokens on these surfaces), v2.1 ship gate]

# Tech tracking
tech-stack:
  added: []  # all libraries (TanStack Query 5, react-markdown 10, date-fns 3, Vitest, @testing-library/react) already present from v2.0 + Phase 6
  patterns:
    - "Frontend feed mirror: 5-min staleTime + refetchInterval, refetchOnWindowFocus: false — identical to useSummaries pattern, deliberate to keep all feed hooks symmetric"
    - "Hook re-export shim under hooks/ to match scattered conventions (api/useWeeklySweeps is canonical; hooks/useWeeklySweeps re-exports for symmetry)"
    - "Empty-state copy + next-cron-fire computation lives client-side (nextSundayLabel) because the empty path only ever renders before the first DB row exists — boundary case is acceptable"
    - "Vitest pattern: vi.mock at module level + late import of mocked symbol, mock useWeeklySweeps but let react-markdown render real HTML so text assertions are meaningful"

key-files:
  created:
    - frontend/src/api/weeklySweeps.ts
    - frontend/src/hooks/useWeeklySweeps.ts
    - frontend/src/components/viral/SweeperCard.tsx
    - frontend/src/__tests__/weeklySweeps.test.tsx
  modified:
    - frontend/src/pages/WeeklyViralSweeperPage.tsx  # Phase 5 stub fully replaced with live UI

key-decisions:
  - "Used native <select> for the history week-picker rather than shadcn Select — avoids dependency-check on whether frontend/src/components/ui/select.tsx exists; native <select> is keyboard-accessible and styled to match the dark zinc palette. Phase 8 UI polish can swap to shadcn if needed."
  - "Mirrored useSummaries staleTime/refetchInterval exactly (5 min / 5 min, refetchOnWindowFocus: false). Weekly sweeps fire once per week — 5-min refetch is more than enough to catch the Sunday fire; we deliberately keep all feed hooks symmetric rather than tuning per-domain."
  - "Did NOT mock react-markdown in the Vitest spec. Real markdown rendering means the assertions (e.g., 'Top X Posts This Week' heading text) verify the full pipeline including ReactMarkdown's HTML output, not just our component logic."
  - "Empty-state next-Sunday computation is intentionally imperfect for the Sunday-before-08:00-PT boundary. The empty state ONLY renders when total === 0 — once the first cron fires (or manual `python -m agents.weekly_sweeper` invocation), this code path is unreachable. Boundary case acceptable per Plan 07-06 <action> note."
  - "Pivot enforcement: NO 'Reddit' string in user-visible copy. Section header is 'Top X Posts This Week' (matches 07-CONTEXT.md D-03 X-API pivot); the backend column name remains reddit_top_md for Phase 5 migration compatibility, but the frontend treats it as 'top X posts markdown' per the JSDoc in api/weeklySweeps.ts."

patterns-established:
  - "Card surface convention: rounded-lg border-zinc-800 bg-zinc-900/40 p-6 space-y-6 — Phase 8 UI polish should converge SummaryCard, calendar cells, and SweeperCard on this baseline"
  - "Status banner pattern: amber for partial (border-amber-800 bg-amber-950/40 text-amber-200), red for failed (border-red-800 bg-red-950/40 text-red-200), hidden for completed — reusable for any future telemetry-aware card"

requirements-completed: [SWEEP-13, SWEEP-14]

# Metrics
duration: ~10 min  # including the human-verify checkpoint round-trip the next morning
completed: 2026-05-19
---

# Phase 7 Plan 06: Weekly Viral Sweeper Frontend Summary

**Live React UI for Tab 3 — TanStack Query hook + SweeperCard rendering 3 react-markdown sections + status banner + history week-picker + SWEEP-14 empty-state copy, with 9 Vitest tests green; replaces the Phase 5 stub and consumes the live `GET /weekly-sweeps` endpoint from Plan 07-03.**

## Performance

- **Duration:** ~10 min (3 task commits within 2 min 10 sec; human-verify checkpoint approved next morning)
- **Started:** 2026-05-19T05:29:11Z (first task commit)
- **Last commit:** 2026-05-19T05:31:21Z (test commit)
- **Checkpoint approved:** 2026-05-19 (user "approved" after empty-state browser verification)
- **Completed:** 2026-05-19T (this summary)
- **Tasks:** 4 (3 `type="auto"` + 1 `type="checkpoint:human-verify"`)
- **Files modified:** 5 (4 created, 1 fully replaced)

## Accomplishments

- **Tab 3 is feature-complete.** The Phase 5 "Coming soon" stub is gone; visiting `/viral` now renders the empty-state copy (when `total: 0`) or the latest sweep card (once any DB row exists) with all 3 react-markdown sections plus status-specific banner copy.
- **TanStack Query integration symmetric with summaries feed.** `useWeeklySweeps(limit=12)` mirrors `useSummaries` exactly (5-min staleTime, no window-focus refetch) so the two feeds behave identically from the operator's perspective.
- **SWEEP-14 empty-state copy locked.** Exact string `"Sweeper has not run yet — first fire scheduled for Sunday {next_sunday} 08:00 PT."` rendered client-side using `date-fns startOfWeek` + `addDays` for the next-Sunday computation; verified in browser as part of the human-verify checkpoint.
- **9 Vitest tests green, full suite 121/121.** Component-level coverage of empty state, populated render, week-picker visibility (1 sweep vs 3 sweeps), loading branch, error branch, and all 3 status-banner states (completed/partial/failed).
- **TypeScript clean, production build succeeds.** `npx tsc --noEmit` reports 0 errors; `npm run build` exits 0; no regressions in other test suites.
- **Human-verify checkpoint approved.** User confirmed empty-state browser rendering on 2026-05-19; verification steps 2 and 3 (populated card + status banner) deferred to the Sunday cron fire — captured in "Awaited Future Validation" below for the verifier to thread into Phase 7 HUMAN-UAT.

## Task Commits

Each task was committed atomically:

1. **Task 1: API module + TanStack Query hook for `/weekly-sweeps`** — `e90e691` (feat) — `frontend/src/api/weeklySweeps.ts` (47 lines) + `frontend/src/hooks/useWeeklySweeps.ts` (5 lines re-export shim)
2. **Task 2: SweeperCard component + WeeklyViralSweeperPage live UI** — `1350467` (feat) — `frontend/src/components/viral/SweeperCard.tsx` (121 lines) + `frontend/src/pages/WeeklyViralSweeperPage.tsx` (98 lines, full replacement of the Phase 5 stub)
3. **Task 3: Vitest spec — 9 tests, all green** — `2bf8fcb` (test) — `frontend/src/__tests__/weeklySweeps.test.tsx` (138 lines)
4. **Task 4: Human-verify checkpoint** — APPROVED by user 2026-05-19 (no commit; checkpoints are non-code)

**Plan metadata commit:** appended to this SUMMARY (see "Self-Check" + final `commit` invocation).

## Files Created/Modified

- `frontend/src/api/weeklySweeps.ts` *(created, 47 lines)* — `WeeklySweepCard` + `WeeklySweepFeedResponse` TypeScript types mirroring backend `WeeklySweepCard` Pydantic schema; `getWeeklySweeps(limit=12)` fetch helper via `apiFetch`; `useWeeklySweeps` TanStack Query hook with 5-min refetch and no window-focus refetch.
- `frontend/src/hooks/useWeeklySweeps.ts` *(created, 5 lines)* — Re-export shim for consistency with other hooks under `/hooks` (canonical implementation lives in `api/weeklySweeps.ts`).
- `frontend/src/components/viral/SweeperCard.tsx` *(created, 121 lines)* — Renders the week title (`Weekly Sweep — May 11 – May 17, 2026`), conditional status badge (`partial`/`failed` only), conditional status banner (amber for partial / red for failed), and 3 sequential markdown sections via `react-markdown`. Uses Tailwind Typography `prose prose-invert prose-sm` classes for markdown styling.
- `frontend/src/pages/WeeklyViralSweeperPage.tsx` *(replaced, 98 lines)* — Live page replacing the Phase 5 stub. 4-way control flow: loading → error → empty (SWEEP-14 copy) → populated (latest sweep + optional history week-picker). `nextSundayLabel(now)` helper computes the next Sunday date for the empty-state copy using `date-fns startOfWeek({ weekStartsOn: 0 }) + addDays(7)`. History week-picker is a native `<select>` showing `May 11 – May 17, 2026 (completed)` labels; hidden when only 1 sweep exists.
- `frontend/src/__tests__/weeklySweeps.test.tsx` *(created, 138 lines)* — 9 Vitest + Testing Library tests mocking `useWeeklySweeps`, rendering inside `QueryClientProvider` + `MemoryRouter`. Asserts: empty-state copy renders, latest sweep is default selection, week-picker visible with 3+ sweeps and absent with 1, loading branch renders 'Loading...', error branch renders 'Failed to load...', completed status hides banner, partial status shows amber banner, failed status shows red banner, all 3 markdown sections render real HTML (not raw markdown text).

## Decisions Made

- **Native `<select>` over shadcn Select for the week-picker.** Avoids the dependency-check on `frontend/src/components/ui/select.tsx`; native `<select>` is fully keyboard-accessible. Phase 8 UI polish can swap to shadcn Select with a 5-minute refactor if a visual delta is desired.
- **Hook re-export shim.** `frontend/src/hooks/useWeeklySweeps.ts` is a thin re-export of the canonical implementation in `frontend/src/api/weeklySweeps.ts`. Matches the scattered convention where some hooks live under `/hooks` and others alongside their fetch helper under `/api`.
- **No `enabled: !!authToken` gate.** `apiFetch` handles auth via the `Authorization` header; if missing, a 401 propagates as a TanStack Query error which the page-level error branch renders cleanly. Adding an `enabled` gate would duplicate the auth machinery already in `apiFetch` + `ProtectedRoute`.
- **Real `react-markdown` rendering in tests.** Mocking `react-markdown` would have made the assertions trivially true (component renders the props it was given); rendering the real markdown lets the tests verify the full pipeline including heading-level HTML output.
- **Pivot enforcement at the boundary, not in the data model.** Backend column name remains `reddit_top_md` (Phase 5 migration compatibility per 07-CONTEXT.md D-03); frontend treats it as "top X posts markdown" with a clarifying JSDoc note in `api/weeklySweeps.ts`. User-visible copy never says "Reddit" — section header is "Top X Posts This Week" per Plan 07-04 prompt design.

## Deviations from Plan

None - plan executed exactly as written.

The 9-test count is one more than the plan's 8-test target (the plan listed 8 named tests; the executor added a 9th `renders the latest sweep as the default selection` test that combined two of the listed behaviors). This is additive coverage, not a deviation — all 8 named-behavior tests from the plan are present and green.

---

**Total deviations:** 0
**Impact on plan:** Zero scope creep. The plan was extremely well-specified (full code listings for every task); the executor lifted the listings verbatim, with only the test file slightly expanded for clearer arrange/act/assert separation.

## Issues Encountered

None during execution. One observation captured for downstream verification (see "Awaited Future Validation" below).

## Awaited Future Validation

The human-verify checkpoint approved verification step 1 (empty state) on 2026-05-19. Verification steps 2 and 3 from the plan's checkpoint cannot fire until either (a) the Sunday cron fires for the first time, or (b) the operator manually invokes `python -m agents.weekly_sweeper` from a Railway shell. These steps should be threaded into the Phase 7 HUMAN-UAT file the verifier creates:

- **Verification step 2 — populated card render:** After the first sweep produces a `weekly_sweeps` row with `status='completed'`, reload `/viral` and confirm: title row shows `Weekly Sweep — {start} – {end}`; no status badge; 3 react-markdown sections render with headings + bullets; if a 2nd sweep ever exists, the history week-picker dropdown appears with prior-week options.
- **Verification step 3 — status banner colors:** Manually set the DB row's `status` to `'partial'` and reload → amber banner with copy `"Sweeper had partial output — some sections may be empty"`. Set to `'failed'` and reload → red banner with copy `"Sweeper failed last run — see telemetry"`. Reset to `'completed'` when done.

Neither step blocks Phase 7 completion — Tab 3 is feature-complete as far as code-and-tests go. These are operational acceptance checks that depend on real production data being present.

## User Setup Required

None. No external service configuration required — the frontend consumes the existing JWT auth via `apiFetch` (already wired by v2.0) and the backend `GET /weekly-sweeps` endpoint (live since Plan 07-03). The Sunday 08:00 PT cron is registered (Plan 07-05) and will fire automatically on the next Railway deploy of the scheduler service.

## Next Phase Readiness

- **Phase 7 is complete.** All 6 plans (07-01 through 07-06) have SUMMARY files; SWEEP-03 through SWEEP-14 are all done (SWEEP-01 and SWEEP-02 dropped per the X-API pivot in 07-CONTEXT.md D-03). The 14-requirement SWEEP category is closed.
- **First production fire:** Whichever Sunday 08:00 PT comes after the next Railway deploy of the scheduler service. The operator can use `python -m agents.weekly_sweeper` from a Railway shell as a manual escape hatch (Plan 07-04 P13 documentation).
- **v2.1 status:** Phase 5 stubs, Phase 6 Content Calendar, and Phase 7 Weekly Viral Sweeper are all merged. The remaining v2.1 work is Phase 8 (UI Polish + Dead-Code Strip — 7 requirements, UI-01 through UI-07).
- **No blockers.** Plan 07-06 acceptance criteria all met; Vitest green; production build clean; checkpoint approved.

## Self-Check

**Created files (spot-checked on disk):**
- FOUND: `/Users/matthewnelson/seva-mining/frontend/src/api/weeklySweeps.ts`
- FOUND: `/Users/matthewnelson/seva-mining/frontend/src/hooks/useWeeklySweeps.ts`
- FOUND: `/Users/matthewnelson/seva-mining/frontend/src/components/viral/SweeperCard.tsx`
- FOUND: `/Users/matthewnelson/seva-mining/frontend/src/__tests__/weeklySweeps.test.tsx`

**Modified files:**
- FOUND: `/Users/matthewnelson/seva-mining/frontend/src/pages/WeeklyViralSweeperPage.tsx` (replaced — no longer the Phase 5 stub)

**Commits:**
- FOUND: `e90e691` (Task 1 — feat: weeklySweeps API module + useWeeklySweeps hook)
- FOUND: `1350467` (Task 2 — feat: SweeperCard component + replace WeeklyViralSweeperPage stub)
- FOUND: `2bf8fcb` (Task 3 — test: Vitest spec for WeeklyViralSweeperPage + SweeperCard)

**Automated verification (previous executor):**
- TypeScript: `npx tsc --noEmit` → 0 errors
- Vitest: `npx vitest run` → 121/121 tests pass, 19/19 files green
- Production build: `npm run build` → succeeds
- Grep acceptance criteria from Plan 07-06: all pass

## Self-Check: PASSED

---
*Phase: 07-weekly-viral-sweeper*
*Completed: 2026-05-19*
