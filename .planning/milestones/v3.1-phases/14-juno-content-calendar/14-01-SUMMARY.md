---
phase: 14-juno-content-calendar
plan: 01
subsystem: multi-tenant / frontend page / backend cross-tenant testing
tags: [react, tanstack-query, vitest, rtl, fastapi, pytest, multi-tenant, JCAL, juno-calendar, D-01, D-04, D-05, D-06, D-07]

# Dependency graph
requires:
  - phase: 06-content-calendar (v2.1)
    provides: WeeklyGrid + DayCell + WeekNav + useCalendar/useCalendarMutations + scoped_calendar helper + /api/{company}/calendar router
  - phase: 09-multi-tenant-foundation (v3.0)
    provides: company_id row-level isolation + URL prefix routing + queryKeys.calendar factory + scoped_*() helpers + CI grep gate
  - phase: 13-per-company-branding (v3.1)
    provides: CSS-token cascade that auto-applies Juno navy palette to calendar surfaces (no new design contract needed)
provides:
  - "/juno/calendar now renders the full Mon-Sun WeeklyGrid (Phase 9 D-09 short-circuit lifted; single shared render path for both tenants)"
  - "TanStack Query key isolation contract verified at the cache level via 3 new RTL tests (JCAL-03)"
  - "Cross-tenant CRUD 404 contract verified via 4 new backend pytests in both directions (PATCH + DELETE; Seva UUID via /api/juno/ + Juno UUID via /api/seva/) — JCAL-05"
  - "REQUIREMENTS.md JCAL-01 relaxed per D-06: em-dash placeholder pattern replaces literal banner copy; tenant-asymmetric banner permanently out of scope; *(D-06)* provenance annotation in place"
  - "Phase 14 acceptance criteria 100% met; all 5 JCAL requirements behaviorally satisfied"
affects:
  - "phase-14 verifier (next gate)"
  - "phase 15 (Juno Weekly Viral Sweeper — no direct dependency, but Phase 14 closes the last v3.0-leftover Juno UI gate)"
  - "future calendar feature work (banner copy now permanently routed through em-dash pattern; tenant-asymmetric prose forbidden by REQUIREMENTS.md JCAL-01 wording)"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Per-tenant TanStack Query key isolation verification via getQueryCache().findAll({ queryKey: ['calendar', tenant] }) partial-match predicate"
    - "Self-contained backend test fixture (own SQLite engine + Model.__table__.create + get_db override) mirroring test_calendar_router.py pattern — preferred over reusing conftest's shared client fixture when a test module needs its own table-create"
    - "Tenant existence isolation (404, NOT 403) for cross-tenant CRUD attempts — defence-in-depth contract validated end-to-end"

key-files:
  created:
    - frontend/src/pages/__tests__/ContentCalendarPage.test.tsx
    - backend/tests/test_calendar_cross_tenant.py
    - .planning/phases/14-juno-content-calendar/14-01-SUMMARY.md
  modified:
    - frontend/src/pages/ContentCalendarPage.tsx
    - .planning/REQUIREMENTS.md

key-decisions:
  - "Applied D-01 verbatim: deleted the entire 13-line Phase 9 D-09 short-circuit block (comment + if + return + brace) at ContentCalendarPage.tsx:42-54 with no replacement scaffolding — no EmptyWeekState wrapper, no dead-code marker, no per-tenant branching of any kind"
  - "Applied D-04 with 3 tests (≥3 floor): Juno mount registers ['calendar', 'juno', ...]; Seva mount registers ['calendar', 'seva', ...]; cross-mount isolation via two fresh QueryClients (preferred over single-client BothInCache variant for cleanest isolation proof)"
  - "Applied D-05 with 4 tests (≥4 floor): 2 PATCH directions + 2 DELETE directions; self-contained fixture; assertion 404 NOT 403; row-mutation-readback after each attack to prove the row was untouched"
  - "Applied D-06 surgically: 1-for-1 line swap in REQUIREMENTS.md with *(D-06)* provenance annotation; preserved Traceability table row (flips to Complete only after phase-level verifier signoff)"
  - "Applied D-07 byte-identically: 12 critical files have ZERO diff lines across the 4-commit window (test_multitenant_isolation.py, test_calendar_router.py, routers/calendar.py, queries/scoped.py, useCalendar.ts, useCalendarMutations.ts, calendar.ts api client, queryKeys.ts, WeeklyGrid.tsx, DayCell.tsx, WeekNav.tsx, AppHeader.tsx)"

patterns-established:
  - "Cache-key isolation testing: use getQueryCache().findAll({ queryKey: ['key', tenant] }) for per-tenant entries; assert >= 1 (not == 1) since TanStack v5 may register pre-resolution metadata; assert == 0 on the opposite tenant in a fresh QueryClient for the isolation proof"
  - "Cross-tenant 404 contract tests: POST as Seva to seed row, capture UUID, PATCH/DELETE via /api/juno/{seva_uuid}, assert 404, then GET back on /api/seva/ to confirm row untouched (round-trip is the security-correctness proof, not just the 404)"
  - "Self-contained backend test module: when a test needs its own engine + table-create, mirror test_calendar_router.py shape (own create_async_engine + run_sync table-create + override get_db + AsyncClient) — do NOT reuse conftest's `client` (no calendar_items table) or import tenant_test_engine from test_multitenant_isolation.py (private to that module)"

requirements-completed:
  - JCAL-01
  - JCAL-02
  - JCAL-03
  - JCAL-04
  - JCAL-05

# Metrics
duration: 6min
completed: 2026-05-20
---

# Phase 14 Plan 01: Juno Content Calendar Gate Removal Summary

**Deleted the 13-line Phase 9 D-09 Juno calendar short-circuit, added 3 frontend RTL tests asserting TanStack Query key isolation between tenants, added 4 backend pytests asserting cross-tenant CRUD attempts return 404 (both directions; PATCH + DELETE), and surgically relaxed REQUIREMENTS.md JCAL-01 wording per D-06 — closing the last v3.0-leftover Juno UI gate with zero Seva-side regressions.**

## Performance

- **Duration:** 6 min
- **Started:** 2026-05-20T22:16:46Z
- **Completed:** 2026-05-20T22:23:00Z (approx)
- **Tasks:** 4 completed
- **Files modified:** 2 (ContentCalendarPage.tsx, REQUIREMENTS.md)
- **Files created:** 2 test files + this summary

## Accomplishments

- **D-01 deletion:** Lines 42-54 of `frontend/src/pages/ContentCalendarPage.tsx` removed verbatim; file dropped from 67 → 53 lines; `<WeeklyGrid companyId={companyId} weekAnchor={weekAnchor} />` now renders for BOTH `/seva/calendar` and `/juno/calendar` via the single shared return path
- **D-04 frontend test (new):** `frontend/src/pages/__tests__/ContentCalendarPage.test.tsx` (144 lines, 3 tests). Asserts Juno mount registers `['calendar', 'juno', ...]` key + WeeklyGrid mounts; Seva mount registers `['calendar', 'seva', ...]` + WeeklyGrid mounts; cross-mount isolation across fresh QueryClients
- **D-05 backend test (new):** `backend/tests/test_calendar_cross_tenant.py` (219 lines, 4 tests). 2 PATCH directions + 2 DELETE directions; all 4 assert `status_code == 404` (NOT 403); each attack followed by a readback to prove the targeted row is byte-untouched
- **D-06 REQUIREMENTS.md edit:** Surgical 1-for-1 line swap of JCAL-01 with `*(D-06)*` provenance annotation; removed banner copy ("No content planned for this week...") + stale "Currently this page renders a Phase 9 placeholder" prose; added "matches Seva em-dash placeholder pattern" canonical wording
- **D-07 zero-regression contract preserved:** 12 critical files have ZERO diff across the 4 commits (AppHeader.tsx, WeeklyGrid.tsx, DayCell.tsx, WeekNav.tsx, useCalendar.ts, useCalendarMutations.ts, api/calendar.ts, queryKeys.ts, backend/app/routers/calendar.py, backend/app/queries/scoped.py, backend/tests/test_calendar_router.py, backend/tests/test_multitenant_isolation.py)
- **Test count progression:** Frontend 175 → 178 (+3 new; 30/30 test files pass). Backend 184 → 188 (+4 new; 5 unchanged Postgres-only skips; 0 failures)
- **All 5 JCAL requirements behaviorally satisfied** (see "Next Phase Readiness" below)

## Task Commits

Each task was committed atomically (`--no-verify` per parallel-executor protocol):

1. **Task 1: Delete the Phase 9 D-09 Juno short-circuit** — `1ec09ae` (feat)
2. **Task 2: Add frontend TanStack Query key isolation test** — `75a3039` (test)
3. **Task 3: Add backend cross-tenant CRUD isolation test** — `6c7674d` (test)
4. **Task 4: Relax JCAL-01 wording in REQUIREMENTS.md per D-06** — `f063426` (docs)

## Files Created/Modified

### Created
- `frontend/src/pages/__tests__/ContentCalendarPage.test.tsx` — 144 lines, 3 RTL tests asserting per-tenant TanStack Query cache key isolation; mocks `@/api/calendar` + `@/hooks/useCalendarMutations` for zero network IO; uses `waitFor` for async query registration (NOT `vi.useFakeTimers` — Phase 11-05 v5 deadlock pitfall avoided)
- `backend/tests/test_calendar_cross_tenant.py` — 219 lines, 4 pytest tests asserting cross-tenant CRUD attempts return 404 (NOT 403); self-contained fixture mirroring `test_calendar_router.py`'s engine + table-create pattern (NOT reusing conftest's `client` fixture which lacks `calendar_items` table)
- `.planning/phases/14-juno-content-calendar/14-01-SUMMARY.md` — this file

### Modified
- `frontend/src/pages/ContentCalendarPage.tsx` — 13 lines deleted (lines 42-54: comment block + `if (companyId === 'juno') { return <placeholder /> }` block); file 67 → 53 lines; nothing else touched (useParams/companyId derivation, useState/useCallback handlers, main render block, header docstring all byte-identical)
- `.planning/REQUIREMENTS.md` — 1-for-1 line swap on JCAL-01 with `*(D-06)*` annotation; net line-count delta: 0

## Decisions Made

All key decisions documented in `frontmatter.key-decisions` above. Summary:

- **D-01 enforcement:** Verbatim deletion of 13-line block; no replacement scaffolding; surrounding context (useCallback handlers + main return block) untouched
- **D-04 test shape:** Two fresh QueryClients (variant 1 from plan) preferred over single-client both-in-cache variant (variant 2) for cleanest isolation proof
- **D-05 test shape:** Self-contained fixture per `test_calendar_router.py` pattern (NOT reusing `tenant_test_engine` from `test_multitenant_isolation.py` since that's a private module-scoped fixture)
- **D-06 enforcement:** Pure 1-for-1 line swap; Traceability table row NOT flipped to "Complete" (that's the phase-level verifier's prerogative after they sign off)
- **D-07 enforcement:** All 12 critical files byte-identical; `git diff HEAD~4 -- <file>` returns 0 lines for each

## Deviations from Plan

None — plan executed exactly as written. All 4 tasks landed on first attempt with zero deviation rule triggers. The plan was well-specified (10/10 plan-check dimensions PASS first iteration per critical-context note); acceptance criteria mapped 1:1 to grep-checkable assertions; no architectural surprises surfaced.

## Issues Encountered

**Cosmetic adjustment (Task 2):** The first draft of the test file had a docstring mention of `vi.useFakeTimers` (warning future readers NOT to use it). The acceptance criterion `grep -c "vi.useFakeTimers" → 0` is a strict literal-string check, so the docstring was rephrased to "Vitest fake-timer helpers" without altering any actual test logic. Zero impact on test behavior or count.

## Deferred Issues (Out of Scope per Scope Boundary)

Pre-existing lint warnings in unmodified files surfaced when running the wider `npm run lint` / `uv run ruff check` gates. Per the scope boundary rule, these are NOT fixed in this plan (only Phase-14-touched files are in scope):

1. **Frontend ESLint (15 errors)** — all in `frontend/src/pages/__tests__/SummaryFeedPage.test.tsx` (last touched in `feat(01-06)` — way before Phase 14). `react/display-name` + `@typescript-eslint/no-explicit-any` warnings. Independent of Phase 14.
2. **Backend Ruff (17 errors)** — `UP017 Use datetime.UTC alias` warnings in `app/main.py`, `app/models/weekly_sweep.py`, `app/routers/calendar.py`, `app/schemas/calendar.py`, `tests/test_calendar_schemas.py`, `tests/test_model_parity.py`, `tests/test_multitenant_isolation.py`, plus 1 line-length warning in `alembic/versions/0013_*.py`. All pre-existing. `uv run ruff check tests/test_calendar_cross_tenant.py` passes clean — my new file is the only one ruff-conformant.

**Verification that Phase 14 files are lint-clean in isolation:**
- `npx eslint frontend/src/pages/__tests__/ContentCalendarPage.test.tsx frontend/src/pages/ContentCalendarPage.tsx` → 0 errors
- `uv run ruff check backend/tests/test_calendar_cross_tenant.py` → "All checks passed!"

## User Setup Required

None — no external service configuration required. Phase 14 is purely a UI gate removal + test addition. The next 08:05 PT cron and the existing CSS-token cascade from Phase 13 (Juno navy palette) automatically apply to the now-mounted WeeklyGrid surface on `/juno/calendar`.

## D-07 Zero-Regression Evidence

The following 12 critical files have ZERO diff lines across commits `1ec09ae..f063426`:

```
backend/tests/test_multitenant_isolation.py: 0 diff lines
backend/tests/test_calendar_router.py:        0 diff lines
backend/app/routers/calendar.py:              0 diff lines
backend/app/queries/scoped.py:                0 diff lines
frontend/src/hooks/useCalendar.ts:            0 diff lines
frontend/src/hooks/useCalendarMutations.ts:   0 diff lines
frontend/src/api/calendar.ts:                 0 diff lines
frontend/src/api/queryKeys.ts:                0 diff lines
frontend/src/components/calendar/WeeklyGrid.tsx: 0 diff lines
frontend/src/components/calendar/DayCell.tsx:    0 diff lines
frontend/src/components/calendar/WeekNav.tsx:    0 diff lines
frontend/src/components/layout/AppHeader.tsx:    0 diff lines
```

Plus targeted regression-test runs:

- `npm test -- --run src/components/calendar/__tests__/ src/components/layout/__tests__/AppHeader.brand.test.tsx` → **16/16 tests pass** (calendar component tests + AppHeader brand tests untouched + GREEN)
- `uv run pytest tests/test_multitenant_isolation.py -q` → **19/19 tests pass**
- `uv run pytest tests/test_calendar_router.py -q` → all pass (baseline unchanged)

## Phase-Level Verification (per plan §<verification>)

1. **Production change landed** — `grep -c "if (companyId === 'juno')" frontend/src/pages/ContentCalendarPage.tsx` = 0; `grep -c "<WeeklyGrid"` = 1; net diff −13 lines
2. **Tests added & passing** — both new test files exist; full frontend suite 178/178 GREEN (175 baseline + 3 new); full backend suite 188 passed / 5 skipped (184 baseline + 4 new)
3. **REQUIREMENTS.md updated** — `grep -c "matches Seva em-dash placeholder pattern"` = 1; `grep -c "No content planned for this week"` = 0; `grep -c "\\*(D-06)\\*"` = 1
4. **D-07 zero-regression** — see evidence section above
5. **Lint + typecheck green for Phase 14 files** — `npx tsc --noEmit` exits 0; `eslint` clean on Phase 14 files; `ruff check` clean on Phase 14 backend file (pre-existing warnings in other files documented in Deferred Issues)
6. **CI grep gate (`scripts/verify-tenant-isolation.sh`)** — PASS: "all tenant-scoped selects routed through queries/scoped.py"

## Next Phase Readiness

**All 5 JCAL requirements behaviorally satisfied:**

- **JCAL-01** — User opens `/juno/calendar` and sees the same weekly Mon-Sun paper-planner grid Seva users see, with em-dash placeholder per DayCell. REQUIREMENTS.md JCAL-01 line reworded per D-06 (*(D-06)* annotation present)
- **JCAL-02** — DayCell autosave fires on blur with optimistic UI; persisted row carries `company_id='juno'` via existing `scoped_calendar` helpers (Phase 9 invariant — unchanged). Existing DayCell.test.tsx + scoped_calendar contract proves this; no Phase 14 test addition needed
- **JCAL-03** — User switches Juno ↔ Seva via URL; calendar view reflects the correct tenant's content via TanStack Query keys keyed on `company_id`. **Asserted by 3 tests in `ContentCalendarPage.test.tsx`** — per-tenant query key isolation verified at the cache level
- **JCAL-04** — User week-navigates prev/next/today on Juno calendar identically to Seva. WeekNav component handles this; gate removal in Task 1 exposes it for Juno. No new wiring needed
- **JCAL-05** — All Juno calendar CRUD routes through `/api/juno/calendar/*` with `Depends(get_current_company)` enforcing `company_id='juno'` server-side. Cross-tenant mutate attempts return 404 (BOTH directions). **Asserted by 4 tests in `test_calendar_cross_tenant.py`** — PATCH + DELETE in both directions

**Ready for:** Phase-14 verifier (next gate). After verifier PASS, update `.planning/REQUIREMENTS.md` Traceability table rows for JCAL-01..05 from "Pending" → "Complete".

**No blockers.**

## Self-Check: PASSED

- All 5 claimed files exist on disk
- All 4 claimed commits exist in git log (1ec09ae, 75a3039, 6c7674d, f063426)

---
*Phase: 14-juno-content-calendar*
*Plan: 01*
*Completed: 2026-05-20*
