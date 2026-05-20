---
phase: 05-foundation-tabs-db-backend-stubs
plan: 05
subsystem: ui
tags: [react, react-router, navlink, tabs, frontend, vite, tailwind, route-restructure]

# Dependency graph
requires:
  - phase: 02-fastapi-backend
    provides: "frontend AppShell/AppHeader baseline (TAB-05 freeze targets)"
  - phase: 04-prune-cron-operations-hardening
    provides: "v2.0 shipped route tree in App.tsx (the structure that needed restructuring)"
provides:
  - "v2.1 3-tab frontend shell — `/` (News Funnel index), `/calendar`, `/viral` nested under TabbedDashboard"
  - "TabNav.tsx — URL-driven (NavLink isActive) 3-tab strip; P3 CRITICAL pitfall prevented by `end={to === '/'}` on index NavLink"
  - "TabbedDashboard.tsx — thin wrapper (`<TabNav />` + `<Outlet />`) nested under AppShell"
  - "Two stub pages with default exports for future React.lazy compatibility (ContentCalendarPage, WeeklyViralSweeperPage)"
  - "Restructured App.tsx — 3 tab routes nested under `<TabbedDashboard />`; v2.0 routes (/queue, /agents/:slug, /digest, /settings, /login) all preserved inside ProtectedRoute"
  - "URL contract locked (P7 prevention): Tab 1=`/`, Tab 2=`/calendar`, Tab 3=`/viral`"
affects:
  - 06-content-calendar (replaces ContentCalendarPage stub with live CRUD UI)
  - 07-weekly-viral-sweeper (replaces WeeklyViralSweeperPage stub with live sweep card)
  - 08-ui-polish (TabNav active-state styling locked here; amber-500 indicator is the v2.1 design baseline)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "URL-driven tab active state via React Router NavLink `isActive` (NEVER local state) — prevents P3 CRITICAL: tab desync from browser Back/Forward"
    - "`end={to === '/'}` on index NavLink — prevents the `/` NavLink from matching every path prefix and lighting all tabs simultaneously"
    - "Tab routes nested as children of `<Route element={<TabbedDashboard />}>` under AppShell — tabs only appear on the 3-tab surface, NOT on /digest or /settings (TAB-02)"
    - "v2.0 redirect routes (/queue, /agents/:slug) preserved INSIDE `<ProtectedRoute />` subtree — prevents P4 HIGH auth bypass"
    - "Stub pages use default exports — forward-compatible with future React.lazy() adoption in Phase 6/7 without an export-style migration"
    - "Reuse of pre-existing `@base-ui/react` Tabs primitive at frontend/src/components/ui/tabs.tsx — TAB-01 satisfied via verification, NO `npx shadcn@latest add tabs` run"

key-files:
  created:
    - frontend/src/components/layout/TabNav.tsx
    - frontend/src/components/layout/TabbedDashboard.tsx
    - frontend/src/pages/ContentCalendarPage.tsx
    - frontend/src/pages/WeeklyViralSweeperPage.tsx
  modified:
    - frontend/src/App.tsx

key-decisions:
  - "Stub pages use default exports (planner decision 1) — keeps the door open for React.lazy() in Phase 6/7 without an export-style migration"
  - "Eager imports in App.tsx for Phase 5 (planner decision 2) — stubs are tiny; React.lazy/Suspense deferred to Phase 6/7 if bundle size matters then"
  - "No `<Suspense>` boundary in Phase 5 (planner decision 3, paired with decision 2)"
  - "TabNav inner container uses `max-w-[720px] mx-auto` to align with AppHeader and SummaryFeedPage content widths (planner decision 4)"
  - "TAB-01 reframed: verify existing tabs.tsx (`@base-ui/react/tabs`) is sufficient and use NavLink for the strip instead of shadcn Tabs `value`/`onValueChange` — eliminates the P3 CRITICAL desync class of bug at the architecture level (planner decision 5)"
  - "Human-verify checkpoint (Task 3) executed in real browser by operator — all 10 verification steps PASSED, confirming P3, P4, P5, P6 pitfalls prevented in production-shape build"

patterns-established:
  - "Tab strip implementation: 3 `<NavLink>` elements with `isActive` className callback, `end` prop on index, no local state, no `defaultValue`. Locked as the v2.1 tab idiom — Phase 8 UI polish will adjust colors/borders/typography but MUST NOT replace NavLink-isActive with state-driven tabs."
  - "Tab shell composition: `<Route element={<AppShell />}>` parent; `<Route element={<TabbedDashboard />}>` child wrapping the 3 tab routes; v2.0 routes are siblings of TabbedDashboard so they share AppShell + ProtectedRoute but NOT the TabNav."
  - "v2.0 bookmark grace + auth gate: `/queue` and `/agents/:slug` `<Navigate to=\"/\" replace />` redirects stay INSIDE ProtectedRoute — must redirect through auth, not around it."

requirements-completed: [TAB-01, TAB-02, TAB-03, TAB-04, TAB-05]

# Metrics
duration: ~14m
completed: 2026-05-18
---

# Phase 05 Plan 05: Frontend Tab Shell (TabbedDashboard + TabNav + Stub Pages + App.tsx Restructure) Summary

**v2.1 3-tab frontend shell wired in: TabbedDashboard wraps `/`, `/calendar`, `/viral` under AppShell with URL-driven NavLink active state; v2.0 routes /digest /settings /queue /agents/:slug all preserved; AppShell.tsx and AppHeader.tsx byte-unchanged.**

## Performance

- **Duration:** ~14 min wall clock (Tasks 1+2 batched at ~14:35 PDT, human-verify checkpoint approved at ~14:48 PDT)
- **Started:** 2026-05-18T21:34:30Z (approx — first task commit ab10c02 at 21:35:04Z)
- **Completed:** 2026-05-18T21:48:35Z
- **Tasks:** 3 (Task 1 = file creation, Task 2 = App.tsx restructure, Task 3 = human-verify checkpoint)
- **Files modified:** 5 (4 created + 1 modified) — AppShell.tsx and AppHeader.tsx byte-unchanged per TAB-05 freeze

## Accomplishments

- **TAB-01 satisfied (reframed):** `frontend/src/components/ui/tabs.tsx` (pre-existing `@base-ui/react/tabs`) verified present and sufficient. NO `npx shadcn@latest add tabs` run — eliminating the P3 CRITICAL desync class of bug at the architecture level by routing tab state through React Router NavLink instead of a `value`/`onValueChange` Tabs primitive.
- **TAB-02 shipped:** `TabbedDashboard.tsx` created as a thin wrapper rendering `<TabNav />` + `<Outlet />`; nested under `<AppShell />` so tabs only appear on the 3-tab surface. Confirmed in real browser (Step 6) that `/digest` and `/settings` do NOT render the TabNav strip.
- **TAB-03 shipped:** `TabNav.tsx` created with 3 React Router `<NavLink>` elements; active state driven by NavLink's own `isActive` className callback (URL-driven, never local state). `end={to === '/'}` on the index NavLink. Confirmed in real browser (Step 4) that browser Back/Forward correctly updates the active highlight — P3 CRITICAL prevented.
- **TAB-04 shipped:** `App.tsx` restructured. 3 tab routes (`<Route index>`, `path="calendar"`, `path="viral"`) nested under `<Route element={<TabbedDashboard />}>`. v2.0 routes (`/queue`, `/agents/:slug`, `/digest`, `/settings`, `/login`) all preserved. URL contract locked: Tab 1=`/`, Tab 2=`/calendar`, Tab 3=`/viral` (P7 prevention).
- **TAB-05 shipped:** `git diff --exit-code frontend/src/components/layout/AppShell.tsx frontend/src/components/layout/AppHeader.tsx` exits 0 — both files byte-unchanged. Existing wordmark + Log out button stay in AppHeader untouched.

## Task Commits

Each task was committed atomically (with `--no-verify` per Wave 1 parallel executor protocol):

1. **Task 1: Create TabNav.tsx, TabbedDashboard.tsx, ContentCalendarPage stub, WeeklyViralSweeperPage stub** — `ab10c02` (feat)
2. **Task 2: Restructure App.tsx to nest tab routes under TabbedDashboard** — `c336500` (feat)
3. **Task 3: Human-verify checkpoint** — NO CODE COMMIT (this task is the manual verification gate itself; the operator exercised the running dev servers and approved all 10 steps)

**Plan metadata commit:** (this commit — `docs(05-05): complete tabbed-dashboard plan`)

## Files Created/Modified

- `frontend/src/components/layout/TabNav.tsx` (31 lines) — 3 NavLink elements; URL-driven active state via `isActive` className callback; `end={to === '/'}` on index NavLink (mandatory for `/` not to match every path); `max-w-[720px] mx-auto` inner container aligned with AppHeader + SummaryFeedPage; amber-500 active bottom border + zinc-400/100 inactive colors.
- `frontend/src/components/layout/TabbedDashboard.tsx` (11 lines) — `<TabNav />` then `<Outlet />`. No outer wrapper div (AppShell's `<main className="flex-1 overflow-auto">` already provides container). Named export `TabbedDashboard` (matches eager-import pattern in App.tsx).
- `frontend/src/pages/ContentCalendarPage.tsx` (7 lines) — Default export. Renders "Content Calendar — coming soon (v2.1 Phase 6)" in a `max-w-[720px]` `text-zinc-400` block. Default export so a future Phase 6/7 React.lazy() swap-in doesn't require export-style migration.
- `frontend/src/pages/WeeklyViralSweeperPage.tsx` (7 lines) — Default export. Renders "Weekly Viral Sweeper — coming soon (v2.1 Phase 7)" in the matching layout.
- `frontend/src/App.tsx` (40 lines, restructured) — 3 tab routes (`<Route index>`, `path="calendar"`, `path="viral"`) nested under `<Route element={<TabbedDashboard />}>` inside AppShell inside ProtectedRoute. v2.0 redirects (`/queue` → `/`, `/agents/:slug` → `/`) preserved INSIDE ProtectedRoute. `/digest` and `/settings` are siblings of TabbedDashboard so they share AppShell but NOT the TabNav strip.

## Decisions Made

Five planner decisions baked in at plan time and honored verbatim during execution:

1. **Stub pages use default exports** — forward-compatibility with future React.lazy() without an export-style migration.
2. **Eager imports in App.tsx for Phase 5** — stubs are tiny; React.lazy() deferred to Phase 6/7 if/when bundle size matters.
3. **No `<Suspense>` boundary in Phase 5** — paired with decision 2.
4. **TabNav inner container uses `max-w-[720px] mx-auto`** — aligns with AppHeader and SummaryFeedPage content widths.
5. **TAB-01 reframed to verification only** — pre-existing `frontend/src/components/ui/tabs.tsx` (`@base-ui/react/tabs`) satisfies the primitive; TabNav uses NavLink, not the Tabs primitive's `value`/`onValueChange`. This single architectural choice eliminates the entire P3 CRITICAL desync class of bug.

One execution-time decision:

6. **Human-verify checkpoint signal: operator typed "approved"** — all 10 steps of the verification protocol passed in real browser, confirming P3/P4/P5/P6 pitfalls prevented behaviorally (not just structurally).

## Deviations from Plan

None — plan executed exactly as written. No Rule 1/2/3 auto-fixes were needed during Tasks 1 and 2. The `--no-verify` flag on per-task commits is the documented Wave 1 parallel-executor protocol (orchestrator will run hooks once after the wave converges); not a deviation from the plan.

## Issues Encountered

None during execution.

The verification environment for Task 3 (the dev servers `cd backend && uv run uvicorn ...` + `cd frontend && npm run dev`) was started by the operator per the checkpoint protocol. No automation gaps were discovered — the plan correctly scoped Task 3 as a behavioral verification gate (not an automation gap).

## Human-Verify Checkpoint Transcript (Task 3)

The operator exercised the running dev servers and reported back on all 10 steps. **All 10 steps PASSED.** Operator signal: "approved".

| # | Step | Pitfall guarded | Result |
|---|------|-----------------|--------|
| 1 | `/` renders News Funnel + "News Funnel" tab highlighted | (baseline) | PASS |
| 2 | `/calendar` renders stub + "Content Calendar" highlighted; News Funnel NOT highlighted | P3 CRITICAL (the `end={to === '/'}` guard) | PASS |
| 3 | `/viral` renders stub + "Weekly Viral" highlighted | (baseline) | PASS |
| 4 | Browser Back/Forward updates the active tab to match URL | P3 CRITICAL (NavLink isActive URL-driven, not local state) | PASS |
| 5 | Direct URL entry highlights correct tab without flash | P3 CRITICAL (same mechanism) | PASS |
| 6 | `/digest` and `/settings` render WITHOUT the TabNav strip | TAB-02 (TabbedDashboard scopes to the 3 tab routes only) | PASS |
| 7 | `/queue` and `/agents/:slug` redirect to `/` while authenticated | TAB-04 (bookmark grace) | PASS |
| 8 | `/queue` redirects to `/login` from incognito (no auth) | P4 HIGH (auth gate preserved on v2.0 redirect routes) | PASS |
| 9 | TabNav sits below AppHeader as its own `<nav>` strip; no overflow at 1440x900 | P5 HIGH (AppHeader's `max-w-[720px]` row not crowded by tabs) | PASS |
| 10 | Browser DevTools Network: no `/calendar` or `/weekly-sweeps` fetches on stub pages | (sanity check; stubs have no data fetching) | PASS |

**Behavioral pitfall coverage confirmed in production-shape build:** P3 CRITICAL (URL-driven tab highlight), P4 HIGH (auth gate preservation through restructure), P5 HIGH (TabNav placement below AppHeader, no overflow), P6 HIGH (pre-existing `tabs.tsx` reused — no Tailwind v4 branch mismatch from re-running shadcn).

## Verification Receipts

- `cd frontend && npx tsc --noEmit` — exits 0 (no TypeScript errors)
- `cd frontend && npm run build` — exits 0; Vite build produces `dist/assets/index-*.js` 624.23 kB (gzip 190.50 kB) + `index-*.css` 57.34 kB (gzip 10.32 kB), built in 190 ms
- `git diff --exit-code frontend/src/components/layout/AppShell.tsx frontend/src/components/layout/AppHeader.tsx` — exits 0 (TAB-05 byte-frozen)
- `git log --oneline | head -5` — confirms `ab10c02` (Task 1) and `c336500` (Task 2) commits both present

## User Setup Required

None — no external service configuration required. (Verification was a local dev-server browser exercise.)

## Next Phase Readiness

- **Phase 6 (Content Calendar) unblocked:** the `/calendar` route now renders a placeholder page that Phase 6 will replace with the live weekly grid. The route contract, TabbedDashboard wiring, and AppShell composition are all locked.
- **Phase 7 (Weekly Viral Sweeper) unblocked:** the `/viral` route renders a placeholder; Phase 7 replaces it with the live SweeperCard.
- **Phase 8 (UI Polish) baseline locked:** the amber-500 active tab indicator + zinc-800/900 baseline + Geist font are already in place from this plan. Phase 8 will refine; the structural tab idiom (NavLink-isActive) is the contract Phase 8 MUST NOT replace with state-driven tabs.

## Self-Check: PASSED

- `frontend/src/components/layout/TabNav.tsx` — FOUND
- `frontend/src/components/layout/TabbedDashboard.tsx` — FOUND
- `frontend/src/pages/ContentCalendarPage.tsx` — FOUND
- `frontend/src/pages/WeeklyViralSweeperPage.tsx` — FOUND
- `frontend/src/App.tsx` — modified as planned (TabbedDashboard + index/calendar/viral routes + v2.0 routes preserved)
- Commit `ab10c02` — FOUND in `git log`
- Commit `c336500` — FOUND in `git log`
- AppShell.tsx + AppHeader.tsx — byte-unchanged (TAB-05 freeze confirmed)
- `npx tsc --noEmit` — exits 0
- `npm run build` — exits 0
- Human-verify checkpoint — operator approved all 10 steps

---
*Phase: 05-foundation-tabs-db-backend-stubs*
*Completed: 2026-05-18*
