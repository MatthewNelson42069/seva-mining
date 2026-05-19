---
phase: 09-multi-tenant-foundation
plan: 01
subsystem: testing
tags: [pytest, vitest, tdd, red-tests, multi-tenant, ci-grep-gate, alembic, sqlalchemy, react-router, zustand, tanstack-query]

# Dependency graph
requires:
  - phase: 08-ui-polish-dead-code-strip
    provides: semantic CSS tokens (--color-brand-accent[-hover/-subtle]); CompanySwitcher will inherit these in Wave 3
  - phase: 07-content-agent (v2.1)
    provides: APScheduler advisory-lock pattern + JOB_LOCK_IDS dict; Wave 2 extends with juno_daily_summary=1020 + juno_weekly_sweeper=1021
provides:
  - 12 Wave 0 RED test files (4 backend + 2 scheduler + 5 frontend + 1 extended existing scheduler file)
  - 1 CI grep gate (scripts/verify-tenant-isolation.sh) — chmod +x; EXIT 0 today via PRE_WAVE_2_WHITELIST
  - Module-level pytest.skip idiom (Iteration 2 — Warning 1 standardization) enforced on 4 NEW backend/scheduler files
  - Per-function skip exception documented for 2 existing-file extensions (test_model_parity.py, test_worker.py)
  - Indirect-path vite-import-analysis workaround pattern for Vitest RED scaffolds (documented inline)
affects: [09-02-PLAN.md, 09-03-PLAN.md, 09-04-PLAN.md, 09-05-PLAN.md]

# Tech tracking
tech-stack:
  added: []  # no new deps — uses existing pytest, vitest, @testing-library/react, react-router-dom, zustand, @tanstack/react-query
  patterns:
    - "Module-level pytest.skip(allow_module_level=True) at top of NEW Wave 0 RED files for single-line removal in later waves"
    - "Per-function pytest.skip(allow_module_level=False) EXCEPTION for extensions to files with pre-existing GREEN tests"
    - "Indirect-path module loading in Vitest tests: `const modPath='@/missing'; await import(/* @vite-ignore */ modPath)` defers unresolved-module errors from TRANSFORM time to TEST RUN time"
    - "CI grep gate PRE_WAVE_2_WHITELIST array: temporary whitelist entries paired with Wave 2 refactor tasks; each entry deleted in the same commit that refactors its call site"

key-files:
  created:
    - scripts/verify-tenant-isolation.sh
    - backend/tests/test_migration_0014.py
    - backend/tests/test_queries_scoped.py
    - backend/tests/test_multitenant_isolation.py
    - scheduler/tests/agents/test_juno_daily_summary.py
    - frontend/src/api/queryKeys.test.ts
    - frontend/src/stores/__tests__/companySlice.test.ts
    - frontend/src/components/layout/__tests__/CompanyScopedRoute.test.tsx
    - frontend/src/components/layout/__tests__/CompanySwitcher.test.tsx
    - frontend/src/__tests__/App.test.tsx
  modified:
    - backend/tests/test_model_parity.py
    - scheduler/tests/test_worker.py

key-decisions:
  - "PRE_WAVE_2_WHITELIST in CI grep gate: pre-existing raw select() call sites (5 of them) temporarily whitelisted with TODO(Wave2) markers so the gate exits 0 today; Wave 2 refactor tasks MUST delete each entry in the same commit that replaces the call site with scoped_*() helpers."
  - "Per-function skip (NOT module-level) for the 2 existing-file extensions (test_model_parity.py + test_worker.py) — documented EXCEPTION to the Iteration 2 Warning 1 standardization, because module-level skip would falsely skip pre-existing GREEN tests."
  - "Indirect-path Vitest dynamic-import pattern: vite:import-analysis fails at TRANSFORM time for unresolved `@/missing-module` imports even inside it.skip() blocks. Storing the module path in a const + `/* @vite-ignore */` defers the error to TEST RUN, where it's never reached because the test is skipped."
  - "NEW Wave 0 test for scheduler bump-by-one job count is a SEPARATE test (test_scheduler_registers_4_jobs_after_juno_add) gated by per-function skip — the EXISTING test_scheduler_registers_3_jobs_after_v1_deregistration is NOT modified in Wave 0, because changing the literal 3->4 would break the GREEN test today. Wave 2 will reconcile both."

patterns-established:
  - "Wave 0 RED scaffolding skip-idiom (Phase 9 Iteration 2 Warning 1): all NEW backend pytest files use module-level skip; extensions to existing files use per-function skip."
  - "CI grep gate temporary-whitelist pattern: PRE_WAVE_x_WHITELIST array with inline TODO(Wavex) comments tied to specific refactor tasks for orderly removal."
  - "Vitest dynamic-import dodge: const-path + /* @vite-ignore */ to defer unresolved-module errors past transform time."

requirements-completed: [TENANT-01, TENANT-02, TENANT-03, TENANT-04, TENANT-05, TENANT-06, TENANT-07, TENANT-08, TENANT-09, TENANT-10]
# Note: Wave 0 LOCKS THE CONTRACT for each TENANT-* requirement via RED tests.
# Waves 1/2/3 turn the tests GREEN by implementing the production code each
# test asserts. The contract — what shape each requirement must satisfy — is
# documented in code in this plan, not just in prose.

# Metrics
duration: 10m
completed: 2026-05-19
---

# Phase 9 Plan 1: Wave 0 RED-tests Scaffolding + CI Grep Gate Summary

**12 Wave 0 RED test files + 1 CI grep gate (`scripts/verify-tenant-isolation.sh`) locking the TENANT-01..10 contract in code; module-level skip idiom (Iteration 2 — Warning 1) enforced on 4 NEW backend/scheduler files; pre-existing raw-select call sites temporarily whitelisted in the gate for orderly Wave 2 removal.**

## Performance

- **Duration:** 10 min
- **Started:** 2026-05-19T22:31:20Z
- **Completed:** 2026-05-19T22:41:21Z
- **Tasks:** 3
- **Files modified:** 12 (10 created + 2 extended)

## Accomplishments

- All 10 TENANT-* requirements (TENANT-01..10) have at least one RED test that — once Wave 1/2/3 lands — will turn GREEN. Nyquist Dim 8 contract closed.
- CI grep gate (`scripts/verify-tenant-isolation.sh`) chmod +x, EXIT 0 today, ready to FAIL mid-Wave-2 (as planned) and PASS again at phase close once all PRE_WAVE_2_WHITELIST entries are deleted.
- Module-level skip idiom standardized on all 4 NEW backend/scheduler pytest files (grep verification: all 4 files contain `allow_module_level=True`).
- Zero production code touched — Wave 0 is tests + scripts only.
- Pre-existing test counts unchanged: backend 156 PASS, scheduler 264 PASS, frontend 141 PASS. New Wave 0 tests collect as SKIPPED (NOT errored, NOT failed).

## Task Commits

Each task was committed atomically:

1. **Task 1: CI grep gate + backend RED tests** — `1f08461` (test)
   - 5 files: scripts/verify-tenant-isolation.sh + test_migration_0014.py + test_queries_scoped.py + test_multitenant_isolation.py + test_model_parity.py
2. **Task 2: Scheduler RED tests + Juno agent test scaffold** — `5269165` (test)
   - 2 files: scheduler/tests/test_worker.py (extended) + scheduler/tests/agents/test_juno_daily_summary.py (new)
3. **Task 3: Frontend RED test scaffolds (Vitest)** — `53b6e52` (test)
   - 5 files: queryKeys.test.ts + companySlice.test.ts + CompanyScopedRoute.test.tsx + CompanySwitcher.test.tsx + App.test.tsx

**Plan metadata commit:** (final commit after this SUMMARY.md is written)

## Files Created/Modified

### Created (10)
- `scripts/verify-tenant-isolation.sh` — CI grep gate enforcing TENANT-03 scoped helper contract. Regex: `select\((DailySummary|CalendarItem|WeeklySweep)[\)\.]`. PRE_WAVE_2_WHITELIST covers 5 pre-existing raw-select sites. chmod +x.
- `backend/tests/test_migration_0014.py` — 4 tests asserting company_id column shape, CHECK ('seva','juno'), composite indexes, server_default backfill. Module-level skip until Wave 1.
- `backend/tests/test_queries_scoped.py` — 4 tests asserting scoped_summaries/scoped_calendar/scoped_weekly_sweeps return Select with company_id filter compiled in. Module-level skip until Wave 1.
- `backend/tests/test_multitenant_isolation.py` — parametrized (seva|juno) × (summaries|calendar|weekly-sweeps) cross-tenant leak guard + invalid-slug 404 test. Module-level skip until Wave 2.
- `scheduler/tests/agents/test_juno_daily_summary.py` — 2 tests asserting run_juno_daily_summary writes 1 row company_id='juno' status='partial' + idempotency. Module-level skip until Wave 2.
- `frontend/src/api/queryKeys.test.ts` — 4 it.skip tests for queryKeys factory shape (TENANT-09).
- `frontend/src/stores/__tests__/companySlice.test.ts` — 4 it.skip tests for setLastVisitedCompany + localStorage persist + partialize (TENANT-07).
- `frontend/src/components/layout/__tests__/CompanyScopedRoute.test.tsx` — 4 it.skip tests for invalid-slug redirect + Outlet render + setLastVisitedCompany on mount (TENANT-05).
- `frontend/src/components/layout/__tests__/CompanySwitcher.test.tsx` — 5 it.skip tests for segmented-control render + click triggers queryClient.clear() BEFORE navigate (D-07, D-08) + sub-path preservation + no-op when active (TENANT-07).
- `frontend/src/__tests__/App.test.tsx` — 7 it.skip tests for bookmark grace redirects (D-06) + :company nested route mount (TENANT-05, TENANT-06).

### Modified (2)
- `backend/tests/test_model_parity.py` — appended `test_daily_summary_parity` with per-function skip (EXCEPTION to module-level idiom — pre-existing CalendarItem + WeeklySweep parity tests stay GREEN).
- `scheduler/tests/test_worker.py` — appended 4 new tests (test_juno_lock_ids_present, test_juno_daily_summary_registered, test_scheduler_registers_4_jobs_after_juno_add, test_juno_weekly_sweeper_NOT_registered) each with per-function skip until Wave 2.

## Pre-existing Test Count Baseline

| Stack | Pre-existing GREEN | Wave 0 added (SKIPPED) | Wave 0 total collected |
|-------|--------------------|-----------------------|-----------------------|
| Backend (pytest) | 156 | 9 (test_daily_summary_parity + module-level skips for 3 NEW files) | 165 |
| Scheduler (pytest) | 264 | 6 (5 per-function skips in test_worker.py + 1 module-level for test_juno_daily_summary.py) | 270 |
| Frontend (vitest) | 141 | 24 (5 files, all it.skip per Vitest idiom) | 165 |

Net invariant: NO pre-existing test changed status from PASS to anything else.

## Decisions Made

1. **Module-level skip standardization (Iteration 2 — Warning 1):** All 4 NEW backend/scheduler pytest Wave 0 RED files use `pytest.skip("...", allow_module_level=True)` at the top. The 2 existing-file extensions (test_model_parity.py, test_worker.py) use per-function skip because module-level would falsely skip pre-existing GREEN tests. Grep verification confirms `allow_module_level=True` present in all 4 NEW files (test_migration_0014.py, test_queries_scoped.py, test_multitenant_isolation.py, test_juno_daily_summary.py).
2. **Vitest doesn't have a module-level skip equivalent**, so the 5 frontend test files use the per-test `it.skip()` pattern (Vitest canonical). Wave 3 grep-verifies each `.skip` removal.
3. **NEW separate `test_scheduler_registers_4_jobs_after_juno_add` test** instead of mutating the literal `3 -> 4` in the existing `test_scheduler_registers_3_jobs_after_v1_deregistration`. Rationale: bumping the literal today would break GREEN; bumping it in Wave 2 (when juno_daily_summary is actually registered) is the right time. Wave 2 reconciliation note included in the new test's docstring.
4. **PRE_WAVE_2_WHITELIST temporary whitelist** in the grep gate (5 entries). Each entry has an inline `TODO(Wave2): ...` comment pointing at the refactor task that must delete it. Wave 2's `09-03-PLAN.md` tasks MUST delete each entry in the same commit that refactors its call site.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 — Missing Critical] CI grep gate could not EXIT 0 with naive RESEARCH §Code Example 7**

- **Found during:** Task 1 verification (running `bash scripts/verify-tenant-isolation.sh` after copying RESEARCH §Code Example 7 verbatim).
- **Issue:** The plan's objective says "Today's pre-Wave-1 state should EXIT 0 (no raw selects yet)" but a quick pre-flight `grep -rnE 'select\((DailySummary|CalendarItem|WeeklySweep)[\)\.]' backend/app scheduler/agents` finds 7 hits across 5 files (backend/app/routers/{summaries,calendar,weekly_sweeps}.py + scheduler/agents/{daily_summary,weekly_sweeper}.py). Without intervention the gate FAILS today, which contradicts the objective.
- **Fix:** Added `PRE_WAVE_2_WHITELIST` array (5 entries) to the gate script with inline `TODO(Wave2): ...` comments. Each entry corresponds to a refactor task in 09-03-PLAN.md (Wave 2). Removing each entry is a single-line edit per Wave 2 task — same surgical pattern as the per-function pytest.skip removal in Wave 1/2. The plan's `<done>` block explicitly authorized this workaround: "if Wave 0 finds existing violations in scheduler/agents/daily_summary.py, document them in the plan summary and tighten the script to whitelist those existing call sites with a TODO comment".
- **Files modified:** scripts/verify-tenant-isolation.sh
- **Verification:** `bash scripts/verify-tenant-isolation.sh` EXITS 0 with output "PASS — all tenant-scoped selects routed through queries/scoped.py (5 pre-Wave-2 call sites whitelisted — see PRE_WAVE_2_WHITELIST)".
- **Committed in:** 1f08461 (Task 1 commit).

**2. [Rule 3 — Blocking] Vite import-analysis fails transform on `@/missing-module` even inside `it.skip()` blocks**

- **Found during:** Task 3 verification (first run of `npm test -- --run` on the 5 new Vitest files).
- **Issue:** vite:import-analysis runs at TRANSFORM time and statically analyzes all `import(...)` calls in the file — including those nested inside `it.skip()` async callbacks. When `@/components/layout/CompanySwitcher` doesn't exist yet (Wave 3 lands it), the transform fails with `Error: Failed to resolve import "@/components/layout/CompanySwitcher"`. This blocks the entire test file from running, defeating the purpose of `it.skip()`.
- **Fix:** Indirect-path pattern — store the module path in a `const` and use `/* @vite-ignore */` in the dynamic import:
  ```ts
  const companySwitcherPath = '@/components/layout/CompanySwitcher'
  // ...
  const { CompanySwitcher } = await import(/* @vite-ignore */ companySwitcherPath)
  ```
  vite:import-analysis sees `import(variable)` and skips static resolution. The unresolved-module error happens AT TEST RUN inside the skipped test (which never runs), not at transform time.
- **Files modified:** All 5 Vitest test files in Task 3 (queryKeys.test.ts, companySlice.test.ts, CompanyScopedRoute.test.tsx, CompanySwitcher.test.tsx, App.test.tsx) — pattern documented inline at the top of each file.
- **Verification:** `npm test -- --run` collects all 5 files, 24 tests SKIPPED, 0 failures, 141 pre-existing tests still PASS. `npx tsc --noEmit` clean.
- **Committed in:** 53b6e52 (Task 3 commit).

---

**Total deviations:** 2 auto-fixed (1 missing-critical, 1 blocking)
**Impact on plan:** Both fixes were required to satisfy the plan's own done criteria. No scope creep. Both are documented inline in the deliverable files so Wave 2/3 maintainers see the rationale and the cleanup tasks.

## Issues Encountered

None beyond the two deviations above.

## Known Stubs

None — all Wave 0 RED test bodies contain real assertions (not placeholder `pass` / `it('TODO')` stubs). They are intentionally unreachable today via skip, but the assertion bodies they gate are the contract Wave 1/2/3 must satisfy.

## User Setup Required

None — no external service configuration required for Wave 0.

## Plan Handoff Note to Wave 1 (09-02-PLAN.md)

Wave 1 must implement these contracts in this exact order:
1. `backend/app/companies/__init__.py` — `CompanyId = Literal["seva", "juno"]` + `ACTIVE_COMPANIES = ("seva", "juno")`.
2. `backend/alembic/versions/0014_add_company_id.py` — adds `company_id VARCHAR(20) NOT NULL DEFAULT 'seva'` + CHECK constraint + composite indexes on `daily_summaries`, `calendar_items`, `weekly_sweeps`.
3. Backend models + scheduler models — dual-edit `daily_summary.py`, `calendar_item.py`, `weekly_sweep.py` to add the `company_id` column. test_model_parity.py's new `test_daily_summary_parity` flips GREEN once both sides carry the column.
4. `backend/app/queries/scoped.py` — `scoped_summaries(company_id) -> Select` etc.

Each Wave 1 task that needs to flip a Wave 0 test GREEN should DELETE the single `pytest.skip(..., allow_module_level=True)` line at the top of the corresponding test module (single-line edit per file):
- After step 2: delete line ~28 of `backend/tests/test_migration_0014.py`
- After step 3: delete the per-function skip inside `test_daily_summary_parity` in `backend/tests/test_model_parity.py`
- After step 4: delete line ~22 of `backend/tests/test_queries_scoped.py`

## Plan Handoff Note to Wave 2 (09-03-PLAN.md)

When Wave 2 refactors the 5 pre-existing raw-select call sites to use `scoped_*()` helpers, EACH refactor commit MUST also delete the corresponding entry from `PRE_WAVE_2_WHITELIST` in `scripts/verify-tenant-isolation.sh`. The gate is designed to FAIL mid-Wave-2 (when one site is refactored but the whitelist entry not yet removed — or vice versa) — that's the intended forcing function for atomic refactor commits. Phase close MUST restore EXIT 0 with an empty `PRE_WAVE_2_WHITELIST`.

Wave 2 also:
- Adds `juno_daily_summary=1020` + `juno_weekly_sweeper=1021` to `JOB_LOCK_IDS` in `scheduler/worker.py` (flips `test_juno_lock_ids_present` skip).
- Registers `juno_daily_summary` in `build_scheduler` with `CronTrigger(hour="8,12", minute=5, timezone="America/Los_Angeles")` (flips `test_juno_daily_summary_registered` skip).
- Adds `run_juno_daily_summary` to `scheduler/agents/daily_summary.py` (flips module-level skip in `scheduler/tests/agents/test_juno_daily_summary.py`).
- Adds `/api/{company}/*` router prefix + `get_current_company()` dependency (flips module-level skip in `backend/tests/test_multitenant_isolation.py`).
- Updates existing `test_scheduler_registers_3_jobs_after_v1_deregistration` to expect 4 jobs (or removes that assertion in favor of the new bumped-count test).

## Plan Handoff Note to Wave 3 (09-04-PLAN.md)

Wave 3 must:
1. Create `frontend/src/api/queryKeys.ts` (flips queryKeys.test.ts).
2. Create `frontend/src/stores/slices/companySlice.ts` + wire into `useAppStore` via persist + partialize (flips companySlice.test.ts).
3. Create `frontend/src/components/layout/CompanyScopedRoute.tsx` (flips CompanyScopedRoute.test.tsx).
4. Create `frontend/src/components/layout/CompanySwitcher.tsx` (flips CompanySwitcher.test.tsx).
5. Refactor `frontend/src/App.tsx` to export `AppRoutes` (so tests can mount inside `<MemoryRouter>` without the embedded `<BrowserRouter>`) + add nested `:company` route + bookmark grace `<Navigate>` elements per D-06 (flips App.test.tsx).

For each frontend file, removing the per-test `it.skip()` is a multi-line edit (one per test). Plan 09-04 task 1 step 8 + task 2 step 5 should include grep verification: `! grep -rn 'it\.skip' frontend/src/**/companySlice.test.ts frontend/src/**/queryKeys.test.ts ...` to enforce the removal.

## Next Phase Readiness

- All Wave 0 deliverables shipped; contracts locked in code; CI grep gate wired (exits 0 today, ready to enforce as Wave 1/2 ship).
- No blockers. Ready to spawn Wave 1 (09-02-PLAN.md).
- Pre-existing test suites (156 backend + 264 scheduler + 141 frontend = 561 tests) remain GREEN.

## Self-Check: PASSED

- All 10 created files exist on disk (verified post-creation).
- All 2 modified files contain the new Wave 0 additions (verified via grep).
- All 3 task commits exist in git log (`1f08461`, `5269165`, `53b6e52`).
- Backend, scheduler, and frontend test suites all run cleanly with expected pass+skip counts.
- CI grep gate exits 0 as required.
- Module-level skip idiom present in all 4 NEW backend/scheduler files (grep confirmed).

---
*Phase: 09-multi-tenant-foundation*
*Completed: 2026-05-19*
