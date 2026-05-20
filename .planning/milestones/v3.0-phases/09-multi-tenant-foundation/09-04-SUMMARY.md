---
phase: 09-multi-tenant-foundation
plan: 04
subsystem: frontend-routing-companyswitcher-appheader-freeze-lift
tags: [react-router-v7, tanstack-query, zustand-persist, multi-tenant, frontend, appheader-freeze-lift, semantic-css-tokens, juno-empty-state]

# Dependency graph
requires:
  - phase: 09-multi-tenant-foundation
    plan: 03
    provides: backend routers under /api/{company}/* prefix + scheduler Juno cron registered
provides:
  - frontend/src/api/queryKeys.ts — centralized TanStack key factory; every key includes companyId slot (TENANT-09)
  - frontend/src/components/layout/CompanyScopedRoute.tsx — :company slug validator + Zustand publisher + <Outlet />
  - frontend/src/components/layout/CompanySwitcher.tsx — segmented control; clears TanStack cache BEFORE navigate; preserves sub-path on switch
  - frontend/src/components/layout/AppHeader.tsx — FORMAL FREEZE-LIFT with inline `// v3.0 freeze-lift (Phase 9) — see 09-CONTEXT.md D-02` comment
  - frontend/src/stores/slices/companySlice.ts — lastVisitedCompany slice (default null per D-05)
  - frontend/src/stores/index.ts — wrapped in persist({ name: 'seva-mining-app-state-v3', partialize: state => ({lastVisitedCompany}) })
  - frontend/src/App.tsx — exported <AppRoutes /> with :company nested route + bookmark grace <Navigate> elements (5 redirects)
  - 5 Wave 0 frontend test files transitioned from SKIPPED → GREEN (queryKeys, companySlice, CompanyScopedRoute, CompanySwitcher, App)
affects: [09-05-PLAN.md]

# Tech tracking
tech-stack:
  added: []  # no new deps — uses existing react-router-dom v7, @tanstack/react-query v5, zustand v5
  patterns:
    - "TanStack queryKey factory with companyId slot in every tuple: `['summaries', companyId, limit] as const` — `as const` makes the tuple literal so structural key equality is sound"
    - "React Router v7 nested `:company` route with type narrowing chokepoint: CompanyScopedRoute is the SINGLE place where `string | undefined` → `'seva' | 'juno'` narrows; child pages cast directly (`as CompanyId`) per Pitfall 3 mitigation"
    - "Zustand persist({name, partialize}) middleware — only `lastVisitedCompany` is persisted; queueUi + auth slices stay in memory (auth has its own localStorage write inside authSlice, no double-write)"
    - "CompanySwitcher onClick atomic side-effect ordering: `queryClient.clear()` runs BEFORE `navigate()` so the new tenant's first queries never read stale rows from the previous tenant's cache (D-08)"
    - "Bookmark grace <Navigate> elements OUTSIDE <ProtectedRoute> so stale v2.x bookmarks (`/`, `/calendar`, `/viral`, `/queue`, `/agents/:slug`) redirect to /seva/* BEFORE the auth gate — better UX + simpler test setup"
    - "Two-component dispatcher pattern in WeeklyViralSweeperPage: outer reads useParams + branches; child SevaWeeklyViralSweeperPage owns useWeeklySweeps + useState. Keeps rules-of-hooks straight when one branch needs no data hooks"
    - "Semantic CSS token consumption strict-mode: every new CompanySwitcher class string uses `border-brand-accent / text-brand-accent / bg-brand-accent-subtle` (Phase 8 D-05 contract). Zero literal `amber-*` introduced in NEW Phase 9 code. Existing literals in frozen Phase 5/6/8 surfaces preserved untouched."
    - "AppRoutes self-contained QueryClientProvider — embedded so tests can mount <AppRoutes /> without their own client. Production main.tsx ALSO wraps in QueryClientProvider; TanStack allows nested providers (innermost wins)."

key-files:
  created:
    - frontend/src/api/queryKeys.ts
    - frontend/src/components/layout/CompanyScopedRoute.tsx
    - frontend/src/components/layout/CompanySwitcher.tsx
    - frontend/src/stores/slices/companySlice.ts
  modified:
    - frontend/src/api/summaries.ts
    - frontend/src/api/calendar.ts
    - frontend/src/api/weeklySweeps.ts
    - frontend/src/hooks/useCalendar.ts
    - frontend/src/hooks/useCalendarMutations.ts
    - frontend/src/stores/index.ts
    - frontend/src/components/layout/AppHeader.tsx
    - frontend/src/components/layout/TabNav.tsx
    - frontend/src/components/calendar/WeeklyGrid.tsx
    - frontend/src/components/calendar/DayCell.tsx
    - frontend/src/pages/SummaryFeedPage.tsx
    - frontend/src/pages/ContentCalendarPage.tsx
    - frontend/src/pages/WeeklyViralSweeperPage.tsx
    - frontend/src/App.tsx
    - frontend/src/test/setup.ts
    - frontend/src/api/queryKeys.test.ts                           # it.skip removed (5 tests GREEN)
    - frontend/src/stores/__tests__/companySlice.test.ts           # it.skip removed (4 tests GREEN)
    - frontend/src/components/layout/__tests__/CompanyScopedRoute.test.tsx  # it.skip removed (4 tests GREEN)
    - frontend/src/components/layout/__tests__/CompanySwitcher.test.tsx     # it.skip removed (5 tests GREEN)
    - frontend/src/__tests__/App.test.tsx                          # it.skip removed (7 tests GREEN)
    - frontend/src/components/layout/__tests__/AppHeader.test.tsx  # QueryClientProvider + :company route wrapping (Rule 3 fix)
    - frontend/src/api/__tests__/summaries.test.tsx                # updated to pass companyId (Rule 3 fix)
    - frontend/src/components/calendar/__tests__/DayCell.test.tsx  # updated to pass companyId (Rule 3 fix)
    - frontend/src/hooks/__tests__/useCalendarMutations.test.tsx   # updated QK shape + WEEK companyId (Rule 3 fix)

key-decisions:
  - "companySlice default lastVisitedCompany = null (NOT 'seva') — the Wave 0 test contract (`expect(useAppStore.getState().lastVisitedCompany).toBeNull()`) was authoritative; matches CONTEXT D-05 'bare / redirect is HARDCODED to /seva, NOT last-visited'. The persisted lastVisitedCompany field is reserved as a byproduct for v3.1+ 'last-visited landing' feature."
  - "Bookmark grace <Navigate> elements moved OUTSIDE <ProtectedRoute> (v3.0 change from v2.x 'INSIDE ProtectedRoute' pattern). Reason: tests need the redirects to fire without auth state; production UX also improves (stale bookmarks redirect to canonical URL before login prompt). The :company nested route + /digest + /settings stay inside ProtectedRoute."
  - "AppRoutes export includes its own QueryClientProvider wrapper so tests don't need to manually provide one. Production main.tsx still wraps App in a QueryClientProvider — TanStack supports nested providers, and the inner one wins. Net effect: production unchanged, tests simpler."
  - "WeeklyViralSweeperPage refactored into outer dispatcher + inner SevaWeeklyViralSweeperPage to satisfy React rules-of-hooks. The outer reads :company and branches; the inner owns useWeeklySweeps + useState. Without this split, ESLint react-hooks/rules-of-hooks fires because Juno's early return would skip hook calls."
  - "JunoEmptyState helper NOT extracted — inlined the 5-line div in each of 3 pages per planner discretion (UI-SPEC §Component Inventory NEW components). Trade-off: ~12 lines duplication, but each tab's copy varies and Phase 10 will replace the News Funnel inline state with real content. Helper extraction is a v3.1+ refactor opportunity if a 4th empty-state surface emerges."
  - "test/setup.ts now calls `cleanup()` in afterEach. Vitest 4 + @testing-library/react 16 did not auto-cleanup between tests, which caused two simultaneous CompanySwitcher instances in DOM and broke the `getByRole('button', {name: /seva/i})` selector (multi-match). Single-line fix; affects all tests uniformly."
  - "AppHeader.test.tsx renderHeader now wraps in QueryClientProvider + MemoryRouter `:company/*` route. Required because AppHeader now embeds <CompanySwitcher /> which calls useQueryClient + useParams. Rule 3 deviation — test infra fix caused by the freeze-lift insert."

metrics:
  duration: 15  # minutes (wall clock)
  completed_date: 2026-05-19
  tasks_completed: 3
  task_count: 3
  files_modified: 24    # 4 new + 20 modified (incl. 5 Wave 0 tests + 4 collateral test fixes + 1 setup file)
  tests_unblocked: 23   # 4 queryKeys + 4 companySlice + 4 CompanyScopedRoute + 5 CompanySwitcher + 7 App
  tests_passed_frontend: 165
  build_status: pass    # cd frontend && npm run build → exit 0
  tsc_status: pass      # cd frontend && npx tsc -b → exit 0
  ci_grep_gate: pass    # bash scripts/verify-tenant-isolation.sh → exit 0 (backend untouched in this plan)

requirements:
  closed: [TENANT-05, TENANT-06, TENANT-07, TENANT-09]
---

# Phase 09 Plan 04: Wave 3 — Frontend Routing + CompanySwitcher + AppHeader Freeze-Lift Summary

**One-liner:** Wired the frontend to consume the multi-tenant backend — `:company` nested route + segmented `CompanySwitcher` inside the formally freeze-lifted `AppHeader` + bookmark grace redirects + centralized TanStack `queryKeys` factory + Zustand `persist` for `lastVisitedCompany` + tenant-aware page components with Juno empty-state short-circuits — and all 5 Wave 0 frontend test files now PASS (skip decorators removed).

## What was built

### Task 1 — Foundation layer (queryKeys + persist + CompanyScopedRoute)

- **`frontend/src/api/queryKeys.ts`** (NEW, 22 lines) — Centralized TanStack key factory. Three methods returning `as const` tuples with `companyId` in the second slot: `summaries(companyId, limit)`, `calendar(companyId, start, end)`, `weeklySweeps(companyId, limit)`. Type `CompanyId = 'seva' | 'juno'` exported alongside.
- **`frontend/src/api/{summaries,calendar,weeklySweeps}.ts`** refactored to take `companyId: CompanyId` as the first parameter. URLs become `/api/${companyId}/summaries`, `/api/${companyId}/calendar`, `/api/${companyId}/weekly-sweeps`. Query keys consume the factory. Mutation functions (POST/PATCH/DELETE) all gain the `companyId` parameter.
- **`frontend/src/hooks/{useCalendar,useCalendarMutations}.ts`** refactored to thread `companyId` through to the new API signatures + queryKey factory. MutationOptions interface gains a `companyId` field. `useCalendar(companyId, start, end)`, `useCreateCalendarItem({companyId, start, end})`, etc.
- **`frontend/src/components/calendar/{WeeklyGrid,DayCell}.tsx`** updated to accept + thread `companyId: CompanyId` props.
- **`frontend/src/stores/slices/companySlice.ts`** (NEW, 26 lines) — `lastVisitedCompany: CompanyId | null` field with default `null` (per D-05 contract — bare `/` redirect is hardcoded to `/seva`, NOT last-visited in v3.0). `setLastVisitedCompany(c)` setter. Mirrors `createAuthSlice`/`createQueueUiSlice` shape.
- **`frontend/src/stores/index.ts`** wrapped in `persist((set) => ..., { name: 'seva-mining-app-state-v3', partialize: state => ({lastVisitedCompany: state.lastVisitedCompany}) })`. Only `lastVisitedCompany` is persisted to localStorage — queueUi stays in-memory; auth has its own localStorage write inside authSlice.
- **`frontend/src/components/layout/CompanyScopedRoute.tsx`** (NEW, 42 lines) — validates `useParams<{company}>` against `ACTIVE_COMPANIES = ['seva', 'juno'] as const`. Invalid slug → `<Navigate to="/seva" replace />`. Valid slug → publishes via `setLastVisitedCompany(company)` in `useEffect` + renders `<Outlet />`. Single chokepoint for the `string | undefined` → `'seva' | 'juno'` narrowing.
- **3 Wave 0 frontend test files** had `it.skip()` decorators replaced with `it()` and the historical-Wave-0 doc-comments simplified. All 12 tests GREEN.
  - `queryKeys.test.ts` (4 tests pass)
  - `companySlice.test.ts` (4 tests pass) — Required adding a `useAppStore.setState({lastVisitedCompany: null})` to beforeEach because the module-level Zustand singleton leaks state between tests (Rule 3 fix; the existing `localStorage.clear()` only cleared the localStorage side, not the in-memory state).
  - `CompanyScopedRoute.test.tsx` (4 tests pass — wraps in `<MemoryRouter><Routes><Route path=":company" element={<CompanyScopedRoute />}>...`)

### Task 2 — Shell layer (CompanySwitcher + AppHeader freeze-lift + TabNav + App routes)

- **`frontend/src/components/layout/CompanySwitcher.tsx`** (NEW, 71 lines) — Segmented control with 2 `<button type="button">` elements (NOT `<NavLink>` — must call `queryClient.clear()` BEFORE `navigate()` atomically inside one onClick handler). Active state derived from `useParams().company`. onClick:
  1. Already-active click → no-op (no clear, no navigate).
  2. Strip current tenant prefix from `useLocation().pathname` (e.g. `/seva/calendar` → `/calendar`, `/seva` → `''`).
  3. `queryClient.clear()` — defence-in-depth (D-08).
  4. `navigate(`/${next}${subPath || '/'}`)` — preserves sub-path; empty sub-path becomes `/juno/` (per test contract).
  
  All amber styling uses **semantic CSS tokens VERBATIM from 09-UI-SPEC**: `border-brand-accent text-brand-accent bg-brand-accent-subtle`. Inactive state: `border-zinc-800 text-zinc-400 hover:border-zinc-700 hover:text-zinc-100`. Focus-visible: `focus-visible:ring-2 focus-visible:ring-brand-accent`. Inter-button gap: `gap-1` (4px). **Zero literal `amber-*` introduced in new Phase 9 code.**

- **`frontend/src/components/layout/AppHeader.tsx`** — **FORMAL FREEZE LIFT** per CONTEXT D-02. Exactly 2 new lines inserted between brand-mark `</div>` and Logout `<button>`:
  ```tsx
  {/* v3.0 freeze-lift (Phase 9) — see 09-CONTEXT.md D-02 */}
  <CompanySwitcher />
  ```
  Plus 1 new import line: `import { CompanySwitcher } from './CompanySwitcher'`. The frozen `border-b border-zinc-800 bg-zinc-900` header chrome + the frozen `w-7 h-7 rounded-md bg-amber-500` brand-mark square + the frozen "Seva Mining" wordmark + the frozen Logout button all preserved byte-equivalent (D-02a — wordmark stays "Seva Mining" on both tenants in v3.0). Final file: 35 lines (was 30 lines + 5-line surgical insert).

- **`frontend/src/components/layout/TabNav.tsx`** — `<NavLink>` `to` props now use `useParams<{company: string}>().company` to compute `/${company}`, `/${company}/calendar`, `/${company}/viral`. `end={true}` retained on the index tab. Tabs array moved inside the component function (was module-scope) so it can close over the dynamic `company` value. NavLink hover + active-state styling preserved unchanged.

- **`frontend/src/App.tsx`** — Restructured. Now exports both `default App` (with `<BrowserRouter>`) AND named `AppRoutes` (route tree only). `AppRoutes` embeds its own `<QueryClientProvider>` so tests can mount it under `<MemoryRouter>` without providing one. Route structure per RESEARCH §Code Example 4:
  ```tsx
  <Routes>
    <Route path="/login" element={<LoginPage />} />
    {/* Bookmark grace OUTSIDE ProtectedRoute (5 redirects) */}
    <Route index element={<Navigate to="/seva" replace />} />
    <Route path="/calendar" element={<Navigate to="/seva/calendar" replace />} />
    <Route path="/viral" element={<Navigate to="/seva/viral" replace />} />
    <Route path="/queue" element={<Navigate to="/seva" replace />} />
    <Route path="/agents/:slug" element={<Navigate to="/seva" replace />} />
    <Route element={<ProtectedRoute />}>
      <Route element={<AppShell />}>
        <Route path=":company" element={<CompanyScopedRoute />}>
          <Route element={<TabbedDashboard />}>
            <Route index element={<SummaryFeedPage />} />
            <Route path="calendar" element={<ContentCalendarPage />} />
            <Route path="viral" element={<WeeklyViralSweeperPage />} />
          </Route>
        </Route>
        <Route path="/digest" element={<DigestPage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Route>
    </Route>
  </Routes>
  ```

- **2 remaining Wave 0 test files** had `it.skip()` decorators removed:
  - `CompanySwitcher.test.tsx` (5 tests pass — renders both buttons with active class on current tenant, click clears cache THEN navigates with ordering assert via `mock.invocationCallOrder`, preserves sub-path, switches at index → `/juno/`, no-op on already-active).
  - `App.test.tsx` (7 tests pass — bare `/` → `/seva`, `/calendar` → `/seva/calendar`, `/viral` → `/seva/viral`, `/queue` → `/seva`, `/agents/breaking_news` → `/seva`, `/digest` stays at `/digest`, `:company` route mounts TabbedDashboard with "calendar" text visible).

- **`frontend/src/test/setup.ts`** — Added `cleanup()` from `@testing-library/react` to `afterEach`. Vitest 4 + @testing-library/react 16 do NOT auto-cleanup between tests, which caused two simultaneous CompanySwitcher renders to leak into the next test's DOM and break `getByRole('button', {name: /seva/i})` multi-match selectors. Single-line fix affecting all tests uniformly.

- **`frontend/src/components/layout/__tests__/AppHeader.test.tsx`** — `renderHeader()` updated to wrap in `<QueryClientProvider>` + `<MemoryRouter initialEntries={['/seva']}>` mounting `<Routes><Route path=":company/*" element={<AppHeader />} /></Routes>`. Required because AppHeader now embeds CompanySwitcher which calls `useQueryClient` + `useParams`. All 4 existing AppHeader tests still pass.

### Task 3 — Page layer (3 tenant-aware pages + Juno empty-state short-circuits)

- **`frontend/src/pages/SummaryFeedPage.tsx`** — reads `useParams<{company}>` + casts to `CompanyId`. Replaces `useSummaries(60)` with `useSummaries(companyId, 60)`. When `summaries.length === 0`, branches on `companyId === 'juno'` to render the v3.0 Juno News Funnel empty-state copy: `Coming in Phase 10 — Defence-sector ingestion not yet enabled.` Seva empty-state ("Waiting for first summary…") preserved unchanged.

- **`frontend/src/pages/ContentCalendarPage.tsx`** — reads `useParams<{company}>`. Short-circuits `if (companyId === 'juno')` rendering the v3.1 Juno Calendar empty-state copy: `Coming in v3.1 — Juno Calendar not yet enabled.` Short-circuit fires BEFORE `<WeeklyGrid>` mounts → neither `useCalendar` nor any of the mutation hooks fire for Juno. Seva path passes `companyId` to WeeklyGrid (which threads it into useCalendar + useCalendarMutations).

- **`frontend/src/pages/WeeklyViralSweeperPage.tsx`** — refactored into a thin outer dispatcher `WeeklyViralSweeperPage` that reads `useParams<{company}>` + branches to either the inline Juno empty-state OR a child `SevaWeeklyViralSweeperPage` component. The dispatcher pattern keeps rules-of-hooks straight (without it, eslint react-hooks/rules-of-hooks fires because the Juno early-return would skip the `useWeeklySweeps` + `useState` calls). Juno copy: `Coming in v3.1 — Juno Sweeper not yet enabled.` Seva path calls `useWeeklySweeps('seva', 12)` + preserves all existing week-picker + SweeperCard behavior unchanged.

- **JunoEmptyState helper NOT extracted** — planner discretion per UI-SPEC §Component Inventory NEW components. Inlined the 5-line `<div className="max-w-[720px] mx-auto py-8 px-4"><p className="text-sm text-muted-foreground">{copy}</p></div>` in each of 3 pages. Trade-off: ~12 lines duplication, but each tab's copy varies AND Phase 10 will replace the News Funnel inline state with real content. Helper extraction is a v3.1+ refactor opportunity.

## Verification

- **`cd frontend && npx tsc -b`** → exit 0 (no TypeScript errors).
- **`cd frontend && npm test -- --run`** → 28 test files, **165 passed / 0 failed / 0 skipped**.
- **`cd frontend && npm run build`** → exit 0; bundle size 810.66 kB raw / 246.11 kB gzipped (no regression).
- **`grep -c "it\.skip" frontend/src/{api/queryKeys.test.ts,stores/__tests__/companySlice.test.ts,components/layout/__tests__/CompanyScopedRoute.test.tsx,components/layout/__tests__/CompanySwitcher.test.tsx,__tests__/App.test.tsx}`** → 0/0/0/0/0 across all 5 Wave 0 test files (no skip decorators OR doc-comment references remaining).
- **`grep -c "v3.0 freeze-lift" frontend/src/components/layout/AppHeader.tsx`** → 1 (inline freeze-lift comment present per D-02).
- **`bash scripts/verify-tenant-isolation.sh`** → exit 0 (CI grep gate still passes — backend untouched in Wave 3).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Test contract] companySlice default lastVisitedCompany = null (not 'seva')**
- **Found during:** Task 1 step 5
- **Issue:** The plan/research §Code Example 5 sets default `lastVisitedCompany: 'seva'`. But the Wave 0 test file `companySlice.test.ts` test #4 asserts `expect(useAppStore.getState().lastVisitedCompany).toBeNull()` (with the inline comment `D-05: bare / redirects to /seva/ (hardcoded, NOT last-visited in v3.0)`).
- **Fix:** Changed the slice's default to `null` and the type to `CompanyId | null`. Matches CONTEXT D-05 letter-perfect.
- **Files modified:** `frontend/src/stores/slices/companySlice.ts`
- **Commit:** 7235cb1

**2. [Rule 3 — Test isolation] companySlice test beforeEach needed Zustand state reset**
- **Found during:** Task 1 step 8 (test run)
- **Issue:** Module-level Zustand singleton leaks state across tests; the existing `beforeEach(() => localStorage.clear())` only cleared the persisted side, not the in-memory state. Test #4 (`default lastVisitedCompany is null`) failed because test #1 had previously set it to `'juno'`.
- **Fix:** Added `useAppStore.setState({ lastVisitedCompany: null })` to beforeEach.
- **Files modified:** `frontend/src/stores/__tests__/companySlice.test.ts`
- **Commit:** 7235cb1

**3. [Rule 3 — Test infra] Updated existing tests for the new companyId API signatures**
- **Found during:** Task 1 (post-refactor full test run)
- **Issue:** After refactoring `getSummaries(companyId, limit)`, `useSummaries(companyId, limit)`, `useCreateCalendarItem({companyId, start, end})` etc., existing tests calling them with the OLD signatures broke compilation and assertions.
- **Fix:** Updated `summaries.test.tsx` to call with `('seva')` / `('juno', 30)`. Updated `useCalendarMutations.test.tsx`'s `WEEK` constant + `QK` tuple to include `companyId: 'seva'`. Updated `DayCell.test.tsx` to pass `companyId: 'seva'` in renderCell props.
- **Files modified:** `frontend/src/api/__tests__/summaries.test.tsx`, `frontend/src/hooks/__tests__/useCalendarMutations.test.tsx`, `frontend/src/components/calendar/__tests__/DayCell.test.tsx`
- **Commit:** 7235cb1

**4. [Rule 3 — Test infra] App.test.tsx needed auth setup (token + isAuthenticated)**
- **Found during:** Task 2 step 5
- **Issue:** Test 7 (`:company route mounts TabbedDashboard with useParams`) reaches `/seva/calendar` which is inside `<ProtectedRoute>` — without auth, the user redirects to `/login` and the test's `getByText(/calendar/i)` would never find the Calendar tab label.
- **Fix:** Added a `beforeEach` to `App.test.tsx` that sets `localStorage.access_token` + calls `useAppStore.setState({ token: 'test-token', isAuthenticated: true })`. Tests 1-6 (bookmark grace redirects) work either way because the redirects now sit OUTSIDE ProtectedRoute, but setting auth uniformly keeps the test setup simple.
- **Files modified:** `frontend/src/__tests__/App.test.tsx`
- **Commit:** eacbc23

**5. [Rule 3 — Architecture] Bookmark grace <Navigate> elements moved OUTSIDE <ProtectedRoute>**
- **Found during:** Task 2 step 4
- **Issue:** v2.x had the bookmark grace `<Navigate>` redirects INSIDE `<ProtectedRoute>` (per `frontend/src/App.tsx` Phase 5 baseline). Per the Wave 0 App.test.tsx contract, those redirects must fire WITHOUT an auth token (tests 1-6 don't set auth). Also a better UX — a user with a stale v2.x bookmark gets redirected to the canonical `/seva/*` URL before being prompted to log in.
- **Fix:** Moved all 5 grace `<Navigate>` elements (`/`, `/calendar`, `/viral`, `/queue`, `/agents/:slug`) OUTSIDE the `<ProtectedRoute>` wrapper in App.tsx. The `:company` nested route + `/digest` + `/settings` stay inside ProtectedRoute.
- **Files modified:** `frontend/src/App.tsx`
- **Commit:** eacbc23

**6. [Rule 3 — Test cleanup] Added cleanup() to test/setup.ts afterEach**
- **Found during:** Task 2 (CompanySwitcher.test.tsx run)
- **Issue:** Vitest 4 + @testing-library/react 16 did not auto-cleanup the DOM between tests, which caused two simultaneous `<CompanySwitcher />` instances to coexist in the DOM. `screen.getByRole('button', { name: /seva/i })` then threw "found multiple elements".
- **Fix:** Added `import { cleanup } from '@testing-library/react'` + `cleanup()` call in `afterEach`. Single-line change; affects all tests uniformly + makes the rest of the suite more robust to future test additions.
- **Files modified:** `frontend/src/test/setup.ts`
- **Commit:** eacbc23

**7. [Rule 3 — Test infra] AppHeader.test.tsx wrapped in QueryClientProvider + `:company/*` route**
- **Found during:** Task 2 (post freeze-lift full test run)
- **Issue:** AppHeader now embeds `<CompanySwitcher />` which calls `useQueryClient` + `useParams`. The existing AppHeader tests didn't provide a QueryClient OR mount inside a `:company` route, so all 4 tests threw.
- **Fix:** `renderHeader()` now wraps in `<QueryClientProvider>` + `<MemoryRouter initialEntries={['/seva']}><Routes><Route path=":company/*" element={<AppHeader />} /></Routes></MemoryRouter>`. All 4 existing AppHeader tests still pass.
- **Files modified:** `frontend/src/components/layout/__tests__/AppHeader.test.tsx`
- **Commit:** eacbc23

**8. [Rule 1 — Bug] WeeklyViralSweeperPage rules-of-hooks violation**
- **Found during:** Task 3 step 3 (lint check)
- **Issue:** Initial implementation put `if (companyId === 'juno') return ...` BEFORE `useWeeklySweeps` + `useState` calls. ESLint react-hooks/rules-of-hooks correctly flagged this — the early return causes different hook counts between Seva and Juno renders.
- **Fix:** Refactored into a thin outer dispatcher `WeeklyViralSweeperPage` (reads useParams + branches) + a child `SevaWeeklyViralSweeperPage` (owns useWeeklySweeps + useState). The dispatcher calls only `useParams`; the child only ever mounts for Seva.
- **Files modified:** `frontend/src/pages/WeeklyViralSweeperPage.tsx`
- **Commit:** cf3fb15

### Authentication Gates
None — Wave 3 is pure frontend, no external auth flows.

### Architectural Changes (Rule 4 — Checkpoint)
None — all deviations were Rule 1/3 fixes (bugs, blocking issues, test infra).

## Notable Refactor Decisions

- **JunoEmptyState helper NOT extracted.** Per planner discretion (UI-SPEC marks this OPTIONAL). Inlined the 5-line div in each of 3 pages. Net duplication: ~12 lines. Trade-off: each tab's copy varies, AND the News Funnel inline state goes away in Phase 10. Helper extraction is a v3.1+ refactor opportunity.

- **Default `lastVisitedCompany: null` (NOT 'seva').** Resolves a subtle conflict between RESEARCH §Code Example 5 (which has `'seva'` default) and the Wave 0 test contract (`.toBeNull()`) + CONTEXT D-05 ("bare / redirects to /seva/ — HARDCODED, NOT last-visited"). The test + the CONTEXT decision agree, so the implementation follows them.

- **AppRoutes embeds its own QueryClientProvider.** Production main.tsx already wraps App; the second provider inside AppRoutes is harmless (TanStack uses the innermost). Net: production unchanged, tests don't need to set up their own QueryClient. Alternative considered (require tests to wrap in QueryClientProvider) was rejected — it would have required modifying every existing test that uses AppRoutes, AND would have made the test files less ergonomic.

## Confirmations

- **AppHeader edit is exactly the 2-line insert.** Final file: 35 lines (was 30). The 5-line growth is: 1 import line + 1 blank line + 1 comment line + 1 `<CompanySwitcher />` line + 1 blank line between brand and switcher. Brand-mark `<div>` and Logout `<button>` byte-equivalent to v2.x baseline.
- **CompanySwitcher uses semantic CSS tokens VERBATIM from 09-UI-SPEC.** Active state: `border-brand-accent text-brand-accent bg-brand-accent-subtle`. Focus-visible: `focus-visible:ring-brand-accent`. **Zero literal `amber-500` / `amber-400` introduced** in new Phase 9 code. Existing literals on the brand-mark square (`bg-amber-500` per Phase 5 D-04 frozen baseline) and TabNav active tab (`border-amber-500 text-white` per Phase 5 frozen contract) preserved untouched per Phase 8 D-05 "do not sweepingly refactor existing usages."
- **D-02 documentation status:** This plan handles (b) inline comment in AppHeader.tsx. PROJECT.md "Key Decisions" update + Phase 9 SUMMARY.md "Decisions" section (the third documentation location) are for plan 09-05 to land. CONTEXT D-02 (a) is documented in the Phase 9 SUMMARY.md (this file).
- **No backend or scheduler edits in this plan** — Wave 3 is frontend-only. The CI grep gate `bash scripts/verify-tenant-isolation.sh` still exits 0.

## Handoff to Wave 4 (09-05)

Plan 09-05 runs the cross-tenant isolation integration suite, the 30+ item UI-SPEC manual visual QA checklist at 1440×900 (per UI-SPEC §Manual Visual QA Checklist), and verifies one manual scheduler fire produces both a Seva (`completed`) and a Juno (`partial`) `daily_summaries` row. Wave 4 is the human verification + end-to-end smoke + PROJECT.md/SUMMARY.md "Decisions" section finalization.

## Self-Check: PASSED

- FOUND: frontend/src/api/queryKeys.ts
- FOUND: frontend/src/components/layout/CompanySwitcher.tsx
- FOUND: frontend/src/components/layout/CompanyScopedRoute.tsx
- FOUND: frontend/src/stores/slices/companySlice.ts
- FOUND: commit 7235cb1 (Task 1)
- FOUND: commit eacbc23 (Task 2)
- FOUND: commit cf3fb15 (Task 3)
- 165/165 frontend tests pass (Wave 0 frontend tests now GREEN)
- `npx tsc -b` exits 0
- `npm run build` exits 0
- `grep -c "it.skip"` returns 0 across all 5 Wave 0 test files
- `grep -c "v3.0 freeze-lift" frontend/src/components/layout/AppHeader.tsx` returns 1
- `bash scripts/verify-tenant-isolation.sh` exits 0
