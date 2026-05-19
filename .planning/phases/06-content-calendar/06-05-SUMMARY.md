---
phase: 06-content-calendar
plan: 05
subsystem: frontend-content-calendar-page
tags: [calendar, frontend, react, week-nav, page-shell, human-verify, phase-close-out]

# Dependency graph
requires:
  - phase: 05-foundation-tabs-db-backend-stubs
    provides: "TabbedDashboard chrome (TabNav + Outlet) + Phase 5 ContentCalendarPage stub mounted at /calendar"
  - phase: 06-04
    provides: "WeeklyGrid (7-cell Mon-Sun coordinator) + DayCell auto-save + ISO week helpers"
  - phase: 06-03
    provides: "useCalendar query + 3 optimistic mutation hooks (create/update/delete with rollback)"
  - phase: 06-02
    provides: "Full CRUD /calendar router (GET range / POST 201 / PATCH 200 / DELETE 204)"
  - phase: 06-01
    provides: "calendar_items schema + Pydantic body alias contract + UNIQUE(date) constraint"
provides:
  - "frontend/src/components/calendar/WeekNav.tsx — stateless 3-button + week-range-label header"
  - "frontend/src/pages/ContentCalendarPage.tsx — live page composing WeekNav + WeeklyGrid"
  - "End-to-end verified Content Calendar tab at /calendar (POST + PATCH + DELETE + refresh-persist + auth-gate)"
affects:
  - "Phase 07 (Weekly Viral Sweeper) — same TabbedDashboard chrome will host /viral; no calendar coupling"
  - "Phase 08 (UI Polish) — WeekNav buttons + week-range label are surfaces UI-01..UI-04 will restyle"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Stateless presentational components driven by parent-owned weekAnchor state via callback props"
    - "useCallback handlers + lazy useState initializer for date-based default state"
    - "globalThis over global in Vitest test files (Web-standard, avoids Node @types dependency)"

key-files:
  created:
    - frontend/src/components/calendar/WeekNav.tsx
    - frontend/src/components/calendar/__tests__/WeekNav.test.tsx
  modified:
    - frontend/src/pages/ContentCalendarPage.tsx
    - frontend/src/hooks/__tests__/useCalendarMutations.test.tsx

key-decisions:
  - "ContentCalendarPage owns weekAnchor state (lazy useState(() => new Date())); WeekNav is stateless"
  - "Prev/Next mutate via setWeekAnchor((d) => addDays(d, ±7)) functional updater — never read stale state"
  - "Today resets via setWeekAnchor(new Date()) — not getWeekStart(new Date()) — because WeeklyGrid+DayCell already canonicalize via getWeekStart internally"
  - "Year-boundary safe range label: shows year on both halves when start/end years differ; only end-year otherwise"
  - "globalThis swap in useCalendarMutations.test.tsx (Rule 3 deviation) — unblocked acceptance criterion 'npm run build exits 0' which started failing on tsc -b strict project ref check"

patterns-established:
  - "Page-level state ownership: parent (ContentCalendarPage) holds weekAnchor; children (WeekNav, WeeklyGrid) are stateless"
  - "Phase 5 stub replacement contract: keep `export default function ContentCalendarPage` signature so App.tsx import is untouched"

requirements-completed: [CAL-05]

# Metrics
duration: 4min
completed: 2026-05-19
---

# Phase 06 Plan 05: WeekNav + Live ContentCalendarPage Summary

Stitches Phase 6 together at the page level: replaces the Phase 5 "Coming soon" stub with a real `/calendar` page that holds `weekAnchor` state, renders a `WeekNav` header (prev / Today / next + year-aware range label), and renders the `WeeklyGrid` from Plan 06-04 — closing the loop on every CAL-* requirement and shipping Phase 6 to verified-in-browser status.

## Performance

- **Duration:** 4 min (continuation agent included)
- **Started:** 2026-05-19T03:16:46Z (Task 1 first commit)
- **Completed:** 2026-05-19T03:24:00Z (post-checkpoint metadata flush)
- **Tasks:** 3 (2 code + 1 human-verify checkpoint)
- **Files modified:** 4 (2 created, 2 modified)

## Accomplishments

- WeekNav component shipped with 4 TDD-driven vitest tests (RED → GREEN, all green on first GREEN run)
- ContentCalendarPage stub fully replaced with live composition; default export contract with App.tsx preserved
- Phase 6 closed: every CAL-01..CAL-10 requirement has a shipping surface verified end-to-end in the operator's browser
- Drive-by Rule 3 fix unblocked `tsc -b` so `npm run build` now exits 0 cleanly

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: failing WeekNav tests** — `9b3a63a` (test)
2. **Task 1 GREEN: WeekNav implementation** — `e7c1c24` (feat)
3. **Task 2: ContentCalendarPage live + globalThis Rule 3 fix** — `5310f5e` (feat)
4. **Task 3: human-verify checkpoint** — no code commit (verification gate; user approval recorded in this SUMMARY's Verification Transcript section below)

**Plan metadata commit:** (created with this SUMMARY).

## Files Created/Modified

| File | LOC | Change | Purpose |
|---|---|---|---|
| `frontend/src/components/calendar/WeekNav.tsx` | 69 | created | Stateless 3-button + year-aware range label header (`onPrev` / `onToday` / `onNext` callback props) |
| `frontend/src/components/calendar/__tests__/WeekNav.test.tsx` | 63 | created | 4 vitest cases: prev-fires, next-fires, today-fires, range-label-renders |
| `frontend/src/pages/ContentCalendarPage.tsx` | 49 | replaced | Phase 5 stub → live page; owns `weekAnchor: Date` state; 3 useCallback handlers; renders WeekNav + WeeklyGrid |
| `frontend/src/hooks/__tests__/useCalendarMutations.test.tsx` | -3 / +3 | modified | Rule 3: `global` → `globalThis` (3 occurrences) to satisfy `tsc -b` strict project ref check |

## ContentCalendarPage State Shape

```ts
const [weekAnchor, setWeekAnchor] = useState<Date>(() => new Date())

const handlePrev  = useCallback(() => setWeekAnchor((d) => addDays(d, -7)), [])
const handleNext  = useCallback(() => setWeekAnchor((d) => addDays(d,  7)), [])
const handleToday = useCallback(() => setWeekAnchor(new Date()), [])
```

- **Single source of truth:** `weekAnchor` is a `Date` *inside* the visible week; children canonicalize via `getWeekStart` / `getWeekEnd` from `lib/week.ts`.
- **Functional updaters** (`(d) => addDays(d, ±7)`) prevent stale-closure bugs when the operator clicks prev/next rapidly.
- **Lazy initializer** (`() => new Date()`) ensures the default fires once at mount, not on every render.

## WeekNav Tests → Behavior Map

| Test | Verifies |
|---|---|
| `fires onPrev when prev button clicked` | Click on `aria-label="Previous week"` invokes `onPrev` exactly once |
| `fires onNext when next button clicked` | Click on `aria-label="Next week"` invokes `onNext` exactly once |
| `fires onToday when Today button clicked` | Click on `aria-label="Jump to today"` invokes `onToday` exactly once |
| `renders the week range label "May 18 – May 24, 2026"` | Given `weekAnchor = Wed May 20 2026`, `data-testid="week-range-label"` matches `/May 18.*May 24.*2026/` |

## Verification Transcript (Task 3 — Human-Verify Checkpoint)

The operator ran both dev servers (`uv run uvicorn app.main:app --reload --port 8000` + `npm run dev` at port 5173), logged in, and exercised the 15-step protocol. Operator response: **"approved"**.

| # | Step | Result |
|---|---|---|
| 1 | Tab routing: clicking "Content Calendar" navigates to `/calendar` and renders the 7-cell grid + WeekNav strip | PASS |
| 2 | Today highlight: today's cell shows `ring-2 ring-amber-500` + `bg-amber-500/5` | PASS |
| 3 | Week range label: right side of WeekNav shows current week's range (e.g. "May 18 – May 24, 2026") | PASS |
| 4 | POST flow: type in a non-today cell + blur → `POST /calendar` 201, text persists in cell | PASS |
| 5 | Refresh persists: hard-refresh round-trips the typed text (no TZ off-by-one); line breaks preserved | PASS |
| 6 | PATCH flow: edit existing cell + blur → `PATCH /calendar/{id}` 200, new text persists | PASS |
| 7 | DELETE flow: clear all text + blur → `DELETE /calendar/{id}` 204, cell empty after refresh | PASS |
| 8 | Noop on idle: focus + blur with no edits → zero network requests (idle save guard intact) | PASS |
| 9 | Noop on empty + no row: focus empty cell + blur immediately → zero network requests | PASS |
| 10 | Prev / Next / Today navigation: arrows shift visible week ±7d; Today resets to current week + re-highlights today's cell | PASS |
| 11 | Optimistic update feels instant: text appears in cell BEFORE network completes (visible while request pending) | PASS |
| 12 | Failure rollback (P2 defense, optional): operator-skipped (rollback path is proven in vitest in Plan 06-03) | n/a |
| 13 | Auth gate: incognito window → `/calendar` redirects to `/login` (Phase 5 auth gate intact) | PASS |
| 14 | Other tabs unaffected: `/` (News Funnel) and `/viral` (Weekly Viral Sweeper) still render correctly | PASS |
| 15 | TabbedDashboard nav still works: browser back/forward updates active tab indicator (Phase 5 P4 prevention intact) | PASS |

**14 of 14 required steps PASS; step 12 optional and skipped by operator.**

## Decisions Made

- **Stateless WeekNav** — Centralizing `weekAnchor` ownership in the page (not the nav) keeps the WeeklyGrid and WeekNav reading from the same source of truth, eliminating any sync risk between the visible week label and the grid contents.
- **`new Date()` (not `getWeekStart(new Date())`) for Today** — DayCell and WeeklyGrid both canonicalize to the Monday of the containing week internally via `getWeekStart`, so passing the raw `Date` is equivalent and avoids a redundant computation in the parent.
- **`useCallback` for all three handlers** — Even though WeekNav doesn't currently `React.memo`, the callbacks are passed as props on every render; pinning identities now means Phase 8 UI Polish can wrap WeekNav in `memo` without changing this file.
- **Year-aware range label** — When `start.getFullYear() === end.getFullYear()` show the year only on the end half ("May 18 – May 24, 2026"); when years differ (Dec 30 — Jan 5 spans), show year on both halves. Quietly correct for the year-boundary edge case.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] `global` → `globalThis` in useCalendarMutations.test.tsx**

- **Found during:** Task 2 (replace ContentCalendarPage stub)
- **Issue:** Plan 06-03's test file used the unqualified identifier `global` (Node-style). When Task 2 ran the acceptance criterion `cd frontend && npm run build`, Vite's `tsc -b` invocation hit the project-reference TypeScript build (stricter than the standalone `tsc --noEmit`), which lacks `@types/node`. `global` is not a Web-standard identifier and triggered TS2304 "Cannot find name 'global'" — blocking `npm run build exits 0`.
- **Fix:** Replaced 3 occurrences of `global` with `globalThis` (Web-standard, available without `@types/node`). Behavior identical; no test logic changed.
- **Files modified:** `frontend/src/hooks/__tests__/useCalendarMutations.test.tsx`
- **Verification:** `npx tsc --noEmit` exits 0; `npm run build` exits 0; vitest 18 files / 112 tests pass.
- **Committed in:** `5310f5e` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Necessary to satisfy the Task 2 acceptance criterion. Net scope creep: zero (test-only edit, identical behavior).

## Issues Encountered

None.

## Phase 6 End-to-End Wrap-Up

With Plan 06-05 shipping, **Phase 6 — Content Calendar is closed end-to-end**. Every CAL-* requirement has a shipping surface and one-line evidence:

| Req | Status | Evidence | Plan |
|---|---|---|---|
| **CAL-01** | Complete | `GET /calendar?start=&end=` returns `{items, total}` ordered by `date ASC`; `datetime.date` Pydantic field parses `YYYY-MM-DD` | 06-02 (router) + 06-01 (schema) |
| **CAL-02** | Complete | `POST /calendar` accepts `{date, body}`, returns 201 + CalendarItemResponse; backend writes `created_at = updated_at = datetime.utcnow()` explicitly | 06-02 |
| **CAL-03** | Complete | `PATCH /calendar/{item_id}` accepts `{body}` only, returns 200; handler sets `updated_at = datetime.utcnow()` explicitly; `updated_at` not exposed in `CalendarItemUpdate` schema (P4 defense) | 06-02 |
| **CAL-04** | Complete | `DELETE /calendar/{item_id}` returns 204 No Content; hard delete; 404 if not found | 06-02 |
| **CAL-05** | Complete | `ContentCalendarPage.tsx` renders 7-column Mon-Sun grid via `WeeklyGrid` (default current week, prev/next/Today via `WeekNav`); today's cell has `ring-2 ring-amber-500 bg-amber-500/5` | 06-04 (grid) + **06-05 (page + nav)** |
| **CAL-06** | Complete | `DayCell` renders `notes_md` with `whitespace-pre-wrap`; no markdown rendering, no react-markdown; single text blob per day enforced via DB `UNIQUE(date)` constraint from migration 0013 | 06-04 + 06-01 (UNIQUE constraint) |
| **CAL-07** | Complete | `DayCell` click-to-focus: clicking the cell body focuses the native `<textarea>` via `textareaRef.current?.focus`; native textarea over shadcn primitive specifically to make this work | 06-04 |
| **CAL-08** | Complete | Auto-save on blur via 4-way branch (POST / PATCH / DELETE / noop) + idle save guard; sonner error toast on failure; no Save button | 06-04 + 06-03 (mutations) |
| **CAL-09** | Complete | `useCreateCalendarItem` / `useUpdateCalendarItem` / `useDeleteCalendarItem` all implement `onMutate` snapshot → optimistic write → `onError` restore → `onSettled` invalidate `['calendar', start, end]` | 06-03 |
| **CAL-10** | Complete | `useCalendar()` configured with `staleTime: 0` + `refetchOnWindowFocus: false` | 06-03 |

**All 10 CAL-* requirements closed. REQUIREMENTS.md traceability table: 10/10 Complete.**

The Content Calendar tab is now production-ready for the single operator: the auth gate from Phase 5 still protects the route, the optimistic mutations from Plan 06-03 feel instant in the operator's browser (verified Step 11), and the round-trip via Neon survives a hard refresh (verified Step 5) including TZ-safe `YYYY-MM-DD` date handling (P1 defense holds — no Railway UTC off-by-one).

## Known Stubs

None. ContentCalendarPage is fully wired to the live data layer (`useCalendar` + 3 optimistic mutation hooks from Plan 06-03 → live CRUD router from Plan 06-02 → live `calendar_items` table from Plan 06-01). The Phase 5 "Coming soon" stub is fully replaced — `grep -q "Coming soon" frontend/src/pages/ContentCalendarPage.tsx` exits 1 (acceptance criterion satisfied).

## User Setup Required

None — no external service configuration. The Reddit API setup (`REDDIT_CLIENT_ID` / `_SECRET` / `_USER_AGENT`) is a Phase 7 dependency, not Phase 6.

## Next Phase Readiness

- **Phase 7 (Weekly Viral Sweeper)**: Unblocked. Foundation (advisory lock 1019 in `JOB_LOCK_IDS`, `weekly_sweeps` table from migration 0012, stub `/viral` route) is already in place from Phase 5. Phase 7 needs Reddit app credentials added to Railway (manual one-time gate) before scheduler module code can be tested.
- **Phase 8 (UI Polish + Dead-Code Strip)**: Blocked on Phase 7 completion (UI pass cannot finish until all 3 tabs render live data; dead-code strip needs grep-confirmation that no Phase 6/7 caller references retired v1.0 sub-agents).

## Commits

| Hash | Subject |
|---|---|
| `9b3a63a` | test(06-05): add failing WeekNav tests (RED) for prev/next/Today + week range label |
| `e7c1c24` | feat(06-05): implement WeekNav header with prev/Today/next + week range label |
| `5310f5e` | feat(06-05): replace ContentCalendarPage stub with live WeekNav + WeeklyGrid composition |

## Self-Check: PASSED

- All 4 affected files verified on disk
  - FOUND: frontend/src/components/calendar/WeekNav.tsx
  - FOUND: frontend/src/components/calendar/__tests__/WeekNav.test.tsx
  - FOUND: frontend/src/pages/ContentCalendarPage.tsx (no "Coming soon" — stub replaced)
  - FOUND: frontend/src/hooks/__tests__/useCalendarMutations.test.tsx (globalThis swap applied)
- All 3 per-task commits verified in `git log --oneline` (9b3a63a, e7c1c24, 5310f5e)
- Full vitest suite 18/18 files, 112/112 tests passing
- `npx tsc --noEmit` exits 0
- `npm run build` exits 0
- Operator approved 14/14 required verification steps + skipped optional step 12

---
*Phase: 06-content-calendar*
*Completed: 2026-05-19*
