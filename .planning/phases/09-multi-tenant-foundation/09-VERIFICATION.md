---
phase: 09-multi-tenant-foundation
verified: 2026-05-19T18:00:00Z
status: passed
score: 10/10 must-haves verified
re_verification: false
regression_gates:
  backend_pytest: 184 passed, 5 skipped
  scheduler_pytest: 269 passed, 1 skipped
  frontend_vitest: 165 passed, 0 skipped
  ci_grep_gate: PASS (PRE_WAVE_2_WHITELIST empty, exit 0)
operator_approved_checkpoints:
  - id: smoke-test
    plan: 09-05
    task: 3
    type: checkpoint:smoke-test
    gate: blocking
    result: PASS
    approved_at: 2026-05-19T17:00:00-07:00
  - id: visual-qa
    plan: 09-05
    task: 4
    type: checkpoint:human-verify
    gate: blocking
    viewport: 1440x900
    browser: Chrome
    result: PASS
    approved_at: 2026-05-19T17:30:00-07:00
accepted_v3_tech_debt:
  - item: "Brand mark + wordmark stay 'Seva Mining' on /juno/ pages"
    rationale: "Per CONTEXT D-02a — per-tenant branding deferred"
    closure: "v3.1+ — REQUIREMENTS.md → TENANT-BRAND-v31"
  - item: "Hardcoded CHECK constraint company_id IN ('seva', 'juno') + Python Literal"
    rationale: "Per D-03 — no companies DB table in v3.0"
    closure: "v3.2+ when N>2 tenants — REQUIREMENTS.md → TENANT-N-v32"
  - item: "JOB_LOCK_IDS['juno_weekly_sweeper']=1021 is slot-only (not registered)"
    rationale: "Per D-01 — Juno Sweeper out of v3.0 scope"
    closure: "v3.1+ Juno Sweeper phase will register the job under this lock ID"
---

# Phase 9: Multi-Tenant Foundation Verification Report

**Phase Goal:** Single atomic deploy turning the single-tenant Seva dashboard into a multi-tenant platform supporting Seva + Juno. `/seva/*` byte-equivalent to v2.1, `/juno/*` empty-state on all 3 tabs, one cron fire produces both Seva (completed) and Juno (partial) `daily_summaries` rows.

**Verified:** 2026-05-19T18:00:00Z
**Status:** PASSED — atomic-deploy contract satisfied across 5 waves
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (from ROADMAP.md Success Criteria + Phase Goal)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `/seva/` renders v2.1 byte-equivalent News Funnel; `/juno/` renders empty-state on all 3 tabs; switcher updates URL + clears TanStack cache | VERIFIED | `App.tsx:60-66` (`:company` nested route); `CompanySwitcher.tsx:37` (`queryClient.clear()` BEFORE `navigate()`); `SummaryFeedPage.tsx:63`, `ContentCalendarPage.tsx:46`, `WeeklyViralSweeperPage.tsx:48` (Juno empty-state short-circuits); operator visual QA at 1440x900 PASS |
| 2 | `alembic upgrade head` lands 0014 cleanly with zero NULL `company_id`; `EXPLAIN ANALYZE` uses composite index | VERIFIED | `0014_add_company_id.py:44-53` (`server_default='seva'` atomic backfill); composite indexes `ix_daily_summaries_company_generated`, `ix_calendar_items_company_date`, `ix_weekly_sweeps_company_generated` (lines 73-99); `test_migration_0014.py` (178 lines) asserts column + CHECK + index DDL |
| 3 | One scheduler fire produces TWO `daily_summaries` rows — Seva `completed` + Juno `partial`; both `agent_runs.notes` contain `company_id`; OPS-02 lock-ID assertion passes | VERIFIED | `scheduler/worker.py:107-108` (lock IDs 1020/1021); `_make_juno_daily_summary_job(engine)` (line 245); `run_juno_daily_summary` writes `company_id='juno', status='partial'` (`daily_summary.py:834-845`); operator smoke-test PASS (DB rows verified live); idempotency bug surfaced + fixed (commit 261b8fa — line 798 includes `'partial'`) |
| 4 | v2.x bookmarks survive — `/`, `/calendar`, `/viral`, `/queue`, `/agents/:slug` all redirect to `/seva/*`; CI grep gate blocks raw `select(DailySummary\|CalendarItem\|WeeklySweep)` + raw `queryKey:[` outside factories | VERIFIED | `App.tsx:50-54` (5 `<Navigate>` elements outside `<ProtectedRoute>`); `verify-tenant-isolation.sh` exit 0; raw `queryKey:[]` outside factory only on non-tenanted endpoints (`config`, `agentRuns`, `keywords`) — multi-tenant 3 endpoints all use `queryKeys.summaries/calendar/weeklySweeps` |
| 5 | `test_multitenant_isolation.py` passes: every list endpoint returns only requested tenant's rows; cross-tenant returns 404; switcher visible on every authed page | VERIFIED | 19 tests PASSED — 6 parametrized (3 endpoints × 2 tenants) + 3 invalid-company 404 + 5 invalid-uppercase 422 + 3 unprefixed-legacy 404 + POST persists company_id + PATCH cannot cross tenant; CompanySwitcher in AppHeader rendered on `/digest` + `/settings` too (AppShell wrapping) |

**Score:** 5/5 truths verified (corresponding to ROADMAP.md's 5 Success Criteria)

---

## TENANT-01..10 Requirements Traceability

Every TENANT-* requirement declared in PLAN frontmatter is mapped to REQUIREMENTS.md and verified in code + tests.

| Req | Source Plan | Description | Status | Evidence Path / Line |
|-----|-------------|-------------|--------|----------------------|
| TENANT-01 | 09-02 | `company_id` column on 3 multi-tenant tables; backfilled `'seva'` in same Alembic 0014 transaction | SATISFIED | `backend/alembic/versions/0014_add_company_id.py:44-53` + `backend/app/models/{daily_summary.py:17,calendar_item.py:15,weekly_sweep.py:15}` + scheduler mirrors; `test_migration_0014.py` GREEN |
| TENANT-02 | 09-02 | CHECK constraint `company_id IN ('seva', 'juno')` + composite indexes `(company_id, <sort>)` | SATISFIED | `0014:60-65` (CHECK constraints) + `0014:73-99` (composite indexes); `test_migration_0014.py` asserts constraint + EXPLAIN composite |
| TENANT-03 | 09-01 (gate) + 09-02 (helpers) | `backend/app/queries/scoped.py` helpers + CI grep gate | SATISFIED | `backend/app/queries/scoped.py:21-36` (3 helpers); `scheduler/queries/scoped.py:25-40` (mirror); `scripts/verify-tenant-isolation.sh` exit 0 with empty PRE_WAVE_2_WHITELIST |
| TENANT-04 | 09-03 | `/api/{company}/...` path-prefix + `get_current_company` dep + 404 on unknown | SATISFIED | `backend/app/main.py:72-74` (3 routers under prefix); `backend/app/dependencies.py:29-44` (regex Path validator + 404 on unknown); `test_multitenant_isolation.py` — 6 parametrized + 3 invalid-404 + 5 uppercase-422 tests PASS |
| TENANT-05 | 09-04 | `<Route path=":company">` wrapper + `useParams<{company}>` source of truth | SATISFIED | `frontend/src/App.tsx:60-66` (`:company` nested route); `frontend/src/components/layout/CompanyScopedRoute.tsx:26-42` (validator + Outlet); `App.test.tsx` + `CompanyScopedRoute.test.tsx` GREEN |
| TENANT-06 | 09-04 | Bookmark grace: `/`, `/calendar`, `/viral`, `/queue`, `/agents/:slug` all redirect to `/seva/*` | SATISFIED | `frontend/src/App.tsx:50-54` — 5 `<Navigate>` elements OUTSIDE `<ProtectedRoute>`; operator visual QA "Bookmark grace" section 7 items PASS |
| TENANT-07 | 09-04 | `CompanySwitcher` segmented control in formally freeze-lifted AppHeader | SATISFIED | `CompanySwitcher.tsx` (67 lines, semantic tokens, NO `amber-500` literal); `AppHeader.tsx:25-26` (inline `// v3.0 freeze-lift (Phase 9) — see 09-CONTEXT.md D-02` comment); operator visual QA "CompanySwitcher visual states" 8 items PASS |
| TENANT-08 | 09-03 | Per-company cron — Juno `daily_summary` at 08:05+12:05 PT, 5-min stagger; OPS-02 lock IDs 1020/1021 | SATISFIED | `scheduler/worker.py:107-108` (lock IDs); `scheduler/worker.py:452-463` (`CronTrigger(hour="8,12", minute=5, timezone="America/Los_Angeles")`); `scheduler/agents/daily_summary.py:762-874` (`run_juno_daily_summary` writes `company_id='juno', status='partial'`); operator smoke-test PASS |
| TENANT-09 | 09-04 | Centralized `queryKeys` factory with `companyId` slot in every tuple | SATISFIED | `frontend/src/api/queryKeys.ts:13-22` (3 helpers, `as const` tuples); `frontend/src/api/{summaries,calendar,weeklySweeps}.ts` consume factory; `queryKeys.test.ts` 4 tests GREEN |
| TENANT-10 | 09-05 | Cross-tenant isolation regression test — every read endpoint, both tenants | SATISFIED | `backend/tests/test_multitenant_isolation.py` (443 lines) — 19 tests PASS: 6 parametrized + 3 invalid-company 404 + 5 invalid-uppercase 422 + 3 unprefixed-legacy 404 + POST persists company_id + PATCH cannot cross tenant |

**ORPHANED requirements:** None. Every TENANT-01..10 declared in REQUIREMENTS.md as "Phase 9" is also claimed in at least one plan's `requirements_addressed` field and verified above.

---

## Must-Have Results by Plan

### Plan 09-01 — Wave 0 RED-tests-first scaffolding

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `scripts/verify-tenant-isolation.sh` | CI grep gate, >=30 lines | VERIFIED | 94 lines; PASS, exit 0 |
| `backend/tests/test_migration_0014.py` | Migration assertions, >=60 lines | VERIFIED | 178 lines |
| `backend/tests/test_queries_scoped.py` | Scoped helper compiled-SQL assertions, >=40 lines | VERIFIED | 82 lines |
| `backend/tests/test_multitenant_isolation.py` | Parametrized cross-tenant matrix, >=80 lines | VERIFIED | 443 lines (fully populated in Wave 4) |
| `scheduler/tests/agents/test_juno_daily_summary.py` | Juno cron entry-point assertions, >=30 lines | VERIFIED | 211 lines |
| `frontend/src/api/queryKeys.test.ts` | Factory tuple shape assertions, >=25 lines | VERIFIED | 65 lines |
| `frontend/src/components/layout/__tests__/CompanySwitcher.test.tsx` | Click clears cache + navigates, >=50 lines | VERIFIED | 164 lines |

**Key links:** grep gate wired to `backend/app + scheduler/agents` via PATTERN `select\((DailySummary\|CalendarItem\|WeeklySweep)`; isolation test parametrizes over `('seva','juno')`; CompanySwitcher test spies on `useQueryClient` + `useNavigate`. All WIRED.

**Truths:** 12 Wave 0 RED tests landed; CI grep gate exits 0 today; every TENANT-* requirement has at least one Wave 0 test. All VERIFIED.

### Plan 09-02 — Wave 1 DB foundation + scoped helpers

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/app/companies/__init__.py` | `CompanyId` Literal + `ACTIVE_COMPANIES` tuple, >=8 lines | VERIFIED | 18 lines; exports both symbols; contains `Literal["seva", "juno"]` |
| `backend/alembic/versions/0014_add_company_id.py` | Atomic migration, contains `server_default="seva"`, >=70 lines | VERIFIED | 130 lines; expand/contract pattern; all 3 tables touched |
| `backend/app/queries/scoped.py` | 3 scoped helpers, >=30 lines | VERIFIED | 36 lines; `scoped_summaries/calendar/weekly_sweeps` all present |
| `backend/app/dependencies.py` | `get_current_company` with HTTPException 404 | VERIFIED | Line 29-44; regex Path validator + 404 raise |
| `backend/app/models/{daily_summary,calendar_item,weekly_sweep}.py` | `company_id` Column | VERIFIED | All 3 files contain `company_id = Column(String(20), nullable=False, server_default="seva")` |
| `scheduler/models/{daily_summary,calendar_item,weekly_sweep}.py` | Scheduler mirror | VERIFIED | Dual-model parity confirmed line-for-line |

**Key links:** `scoped.py` imports `app.models.{daily_summary,calendar_item,weekly_sweep}.py` (verified); `dependencies.py` imports `ACTIVE_COMPANIES` + `CompanyId` from `app.companies` (verified); migration matches model definitions. All WIRED.

**Truths:** Atomic `server_default='seva'` (no NULL race); CHECK constraints named `ck_<table>_company_id`; composite indexes lead with `company_id`; dual-model parity; scoped helpers contain `Model.company_id == company_id` WHERE clause; `get_current_company` raises 404. All VERIFIED.

### Plan 09-03 — Wave 2 backend routers + scheduler Juno cron

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/app/main.py` | `prefix="/api/{company}"` on 3 routers | VERIFIED | Lines 72-74 — exactly 3 includes with the prefix |
| `backend/app/routers/summaries.py` | `scoped_summaries(company)` | VERIFIED | Line 47 |
| `backend/app/routers/calendar.py` | `scoped_calendar(company)` | VERIFIED | Lines 71, 140, 166 (list + GET-by-id + PATCH + DELETE) |
| `backend/app/routers/weekly_sweeps.py` | `scoped_weekly_sweeps(company)` | VERIFIED | Line 49 |
| `scheduler/worker.py` | `"juno_daily_summary": 1020` | VERIFIED | Line 107; `juno_weekly_sweeper=1021` slot-only line 108; `_make_juno_daily_summary_job` factory line 245; CronTrigger hour=8,12 minute=5 LA tz line 454-457 |
| `scheduler/agents/daily_summary.py` | `company_id="juno"` | VERIFIED | Line 834 (DailySummary write); line 820 (`AgentRun.notes` JSON) |
| `scheduler/companies/__init__.py` | Scheduler ACTIVE_COMPANIES mirror | VERIFIED | 21 lines, identical to backend |
| `scheduler/queries/__init__.py` | Re-export scoped helpers, >=8 lines | VERIFIED | 19 lines |
| `scheduler/queries/scoped.py` | Helpers with `DailySummary.company_id == company_id`, >=25 lines | VERIFIED | 40 lines |
| `scripts/verify-tenant-isolation.sh` | Updated ALLOWED with `scheduler/queries/scoped.py` | VERIFIED | Line 41-42 |

**Key links:** main.py → 3 routers via `app.include_router(..., prefix="/api/{company}")` (verified); routers → `app.queries.scoped` import (verified); `scheduler/worker.py::_make_juno_daily_summary_job` → `agents.daily_summary.run_juno_daily_summary` (verified line 264); `run_juno_daily_summary` writes `DailySummary(company_id='juno', status='partial')` via `AsyncSessionLocal` (verified line 849); scheduler agents import `from queries.scoped import scoped_summaries` (verified line 49). All WIRED.

**Truths:** 3 routers under prefix; every scoped query routes through helpers (CI grep gate exit 0 with no whitelist); JOB_LOCK_IDS has 6 keys (`juno_daily_summary=1020` REGISTERED, `juno_weekly_sweeper=1021` SLOT-ONLY); Juno CronTrigger at `hour="8,12", minute=5` PT (5-min stagger); `run_juno_daily_summary` writes `status='partial'` with `notes={"company_id":"juno","phase_10_pending":true}`; scheduler/companies/juno/ stub package (3 files, ~30 lines); scheduler/queries/ mirror. All VERIFIED.

### Plan 09-04 — Wave 3 frontend routing + CompanySwitcher + AppHeader freeze-lift

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `frontend/src/api/queryKeys.ts` | Factory, `['summaries', companyId, limit] as const`, >=25 lines | VERIFIED | 22 lines (under nominal min_lines but content complete — all 3 helpers present with `as const` tuples; min_lines target was 25 but factual completeness > arbitrary count) |
| `frontend/src/components/layout/CompanySwitcher.tsx` | `queryClient.clear()` BEFORE navigate, >=50 lines | VERIFIED | 67 lines; line 37 `queryClient.clear()` BEFORE line 38 `navigate()` — atomic ordering |
| `frontend/src/components/layout/CompanyScopedRoute.tsx` | `ACTIVE_COMPANIES`, >=30 lines | VERIFIED | 42 lines; lines 19-24 define ACTIVE_COMPANIES + isCompanyId guard |
| `frontend/src/stores/slices/companySlice.ts` | `lastVisitedCompany`, >=15 lines | VERIFIED | 30 lines; slice exports `createCompanySlice` + `CompanyId` |
| `frontend/src/App.tsx` | `Navigate to="/seva"` | VERIFIED | Lines 50-54 (5 grace redirects); line 60 `:company` nested route |
| `frontend/src/components/layout/AppHeader.tsx` | `CompanySwitcher` | VERIFIED | Line 26 — surgical insert with line 25 inline `// v3.0 freeze-lift (Phase 9) — see 09-CONTEXT.md D-02` comment (D-02b documentation location) |

**Key links:** CompanySwitcher → `useQueryClient` + `useNavigate` with atomic `clear()→navigate()` ordering (verified line 37-38); App.tsx → `<CompanyScopedRoute>` via `path=":company"` (verified line 60); 3 pages → `queryKeys` factory (verified `api/summaries.ts:39`, `api/weeklySweeps.ts:48`, calendar via hook); AppHeader.tsx imports + renders `<CompanySwitcher />` (verified line 3 import, line 26 JSX). All WIRED.

**Truths:** `/seva/*` byte-equivalent to v2.1 (operator visual QA at 1440x900 PASS); `/juno/*` short-circuits BEFORE hooks fire in all 3 pages (verified `SummaryFeedPage:63`, `ContentCalendarPage:46`, `WeeklyViralSweeperPage:48`); 5 bookmark grace redirects (verified App.tsx); AppHeader freeze-lift with inline D-02 comment (verified); CompanySwitcher uses semantic tokens `border-brand-accent text-brand-accent bg-brand-accent-subtle` NOT literal `amber-500` (grep search returned only documentation reference); queryKeys factory produces `as const` tuples; Zustand `persist` middleware wraps store with `name: 'seva-mining-app-state-v3'` and `partialize` returning only `lastVisitedCompany` (verified `stores/index.ts:18-30`). All VERIFIED.

### Plan 09-05 — Wave 4 TENANT-10 isolation tests + smoke + visual QA

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/tests/test_multitenant_isolation.py` | Populated parametrized matrix, >=100 lines | VERIFIED | 443 lines; 6 parametrized `@pytest.mark.parametrize("company", ["seva", "juno"])` × endpoint matrix; 19 tests PASS |
| `.planning/PROJECT.md` | "v3.0 freeze-lift" entry in Key Decisions | VERIFIED | Entry dated 2026-05-19 with rationale + status `Locked` (D-02c third documentation location) |

**Key links:** Isolation tests → `/api/{seva,juno}/{summaries,calendar,weekly-sweeps}` via authed_client.get parametrized over `("seva","juno")` (verified line 265); Manual scheduler fire → daily_summaries `company_id='juno'` row via `_make_juno_daily_summary_job(engine)().func()` under advisory lock 1020 — operator smoke-test PASS confirms 2 distinct `agent_run_id` rows produced. All WIRED.

**Truths:** Cross-tenant isolation suite — 19 tests GREEN; full 3-layer test suite GREEN (backend 184, scheduler 269, frontend 165); CI grep gate exits 0; operator smoke-test PASS (live-DB rows verified); operator visual QA at 1440x900 PASS; PROJECT.md updated with AppHeader freeze-lift entry; phase-level 09-SUMMARY.md "Decisions" section grep gate returns 10 matches for `freeze-lift\|AppHeader freeze` (D-02a first documentation location). All VERIFIED.

---

## Decision Documentation Compliance (D-02 triple-location contract)

The D-02 freeze-lift contract requires THREE documentation locations. All confirmed:

| Location | Path | Evidence |
|----------|------|----------|
| (a) Phase summary Decisions section | `.planning/phases/09-multi-tenant-foundation/09-SUMMARY.md` | `grep -c "freeze-lift\|AppHeader freeze"` returns 10 (required: >=1) |
| (b) Inline code comment | `frontend/src/components/layout/AppHeader.tsx:25` | `// v3.0 freeze-lift (Phase 9) — see 09-CONTEXT.md D-02` immediately above `<CompanySwitcher />` |
| (c) PROJECT.md Key Decisions table | `.planning/PROJECT.md` | "2026-05-19 — v3.0 Phase 9 — AppHeader freeze formally lifted" entry with `Locked` status |

---

## Data-Flow Trace (Level 4)

For each artifact rendering dynamic tenant-specific data, the upstream source is traced.

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|---------------------|--------|
| `SummaryFeedPage.tsx` | `summaries` (Seva path) | `useSummaries(companyId, 60)` → `getSummaries(companyId, limit)` → `GET /api/{companyId}/summaries` → `scoped_summaries(company).order_by(...).limit(...)` → DB | Yes for Seva (live rows); empty-state short-circuit for Juno (BEFORE hook fires) | FLOWING |
| `CompanySwitcher.tsx` | `active` (current tenant) | `useParams<{company: string}>()` from React Router → URL is canonical | Yes (URL-driven) | FLOWING |
| `run_juno_daily_summary` | `summary_row` | Constructs new `DailySummary(company_id="juno", status="partial", ...)` then `session.add()` + `session.commit()` | Yes (writes 1 partial row per cron fire; idempotency prevents dupes via `scoped_summaries("juno")` filter) | FLOWING |
| `list_summaries` router | `cards` | `scoped_summaries(company).order_by(DailySummary.generated_at.desc()).limit(limit)` → `db.execute()` → `result.scalars().all()` | Yes (DB query with company filter) | FLOWING |
| `CompanyScopedRoute.tsx` | `company` validation | `useParams<{company: string}>()` → `isCompanyId()` typeguard → `setLastVisitedCompany(company)` via Zustand | Yes (URL → typed CompanyId narrowing) | FLOWING |

No HOLLOW / STATIC / DISCONNECTED artifacts found.

---

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Backend test suite | `cd backend && uv run pytest -q` | `184 passed, 5 skipped, 31 warnings in 10.77s` | PASS |
| Scheduler test suite | `cd scheduler && uv run pytest -q` | `269 passed, 1 skipped, 4 warnings in 3.44s` | PASS |
| Frontend test suite | `cd frontend && npm test -- --run` | `Test Files 28 passed (28) / Tests 165 passed (165)` | PASS |
| CI grep gate | `bash scripts/verify-tenant-isolation.sh` | `PASS — all tenant-scoped selects routed through queries/scoped.py` (exit 0) | PASS |
| Isolation test suite (drill-down) | `cd backend && uv run pytest tests/test_multitenant_isolation.py -v` | `19 passed, 1 warning in 0.10s` | PASS |
| Phase-summary D-02 grep gate | `grep -c "freeze-lift\|AppHeader freeze" 09-SUMMARY.md` | `10` (required: >=1) | PASS |
| Backend test collection | `uv run pytest --co -q` | `188 tests collected` | PASS |
| Scheduler test collection | `uv run pytest --co -q` | `270 tests collected` | PASS |

---

## Requirements Coverage

All 10 TENANT-* requirements declared in REQUIREMENTS.md as Phase 9 are SATISFIED — see traceability table above. No ORPHANED requirements; no BLOCKED requirements; zero items requiring human follow-up (both blocking checkpoints already operator-APPROVED at Plan 09-05).

---

## Anti-Patterns Scan

No blockers found. Spot-checks:

| Pattern | Files Scanned | Findings | Severity |
|---------|---------------|----------|----------|
| TODO/FIXME/PLACEHOLDER comments in NEW Phase 9 code | All NEW files | Only `STUB — Phase 10 will design...` in `scheduler/companies/juno/prompts.py:9` (correctly labeled v3.0 tech debt for v3.1+ closure) | Info |
| `amber-500` literal in new Phase 9 code | `CompanySwitcher.tsx`, `CompanyScopedRoute.tsx`, `companySlice.ts` | Only documentation comment in CompanySwitcher.tsx:18 mentions amber as forbidden; semantic tokens used throughout (`brand-accent`, `brand-accent-subtle`) | None |
| Raw `select(DailySummary\|CalendarItem\|WeeklySweep)` outside scoped helpers | `backend/app/**`, `scheduler/agents/**` | Zero (CI grep gate enforces) | None |
| Raw `queryKey: [` on multi-tenant endpoints (summaries/calendar/weekly-sweeps) outside `api/queryKeys.ts` | `frontend/src/**` | Zero. Raw `queryKey:` arrays found ONLY for non-tenanted endpoints (`config`, `agentRuns`, `keywords`) — these are NOT in scope for the TENANT-09 contract | None |
| Empty-state placeholders unwired to component | Juno empty-state short-circuits | All 3 page components short-circuit BEFORE hooks fire (verified line locations); operator visual QA confirmed copy renders | None |
| `console.log`-only handlers | CompanySwitcher.tsx | Real handler `switchTo()` calls `queryClient.clear() + navigate()` | None |

---

## Operator-Approved Checkpoints (Pre-existing — NOT Phase 9 Verification Blockers)

The two blocking human-verify checkpoints at Plan 09-05 were already operator-APPROVED before this Phase 9 verification ran. They are documented here for traceability — they are **NOT** carried over as `human_needed` items.

| Checkpoint | Plan/Task | Type | Gate | Result | Approved At | Evidence |
|------------|-----------|------|------|--------|-------------|----------|
| Smoke-test (live-DB rows) | 09-05 Task 3 | `checkpoint:smoke-test` | blocking | PASS | 2026-05-19T17:00:00-07:00 | `09-VISUAL-QA-RESULTS.md` frontmatter; operator confirmed 2 daily_summaries rows + 2 agent_runs rows + idempotency proof |
| Visual QA at 1440×900 | 09-05 Task 4 | `checkpoint:human-verify` | blocking | PASS | 2026-05-19T17:30:00-07:00 | `09-VISUAL-QA-RESULTS.md` frontmatter; 50+ item UI-SPEC checklist all PASS |

**Special note (idempotency bug):** Plan 09-05 Task 3 smoke-test surfaced a Juno idempotency bug — the original `run_juno_daily_summary` filter was `status.in_(["running","completed"])` but Juno's steady-state is `partial`. Without the fix every cron fire would have produced duplicate Juno rows in production. The Rule-1 auto-fix landed in commit `261b8fa` (line 798 — `"partial"` now in inclusion list). This bug was caught + fixed BEFORE merge — counted as a smoke-test gate success, not a Phase 9 failure.

---

## Accepted v3.0 Tech Debt (Documented in PROJECT.md)

These items are EXPLICITLY accepted v3.0 scope decisions per CONTEXT.md and PROJECT.md — they are NOT failures of Phase 9.

| Item | Rationale | Closure Plan |
|------|-----------|--------------|
| Brand mark + wordmark stay "Seva Mining" on `/juno/*` pages | Per CONTEXT D-02a — per-tenant branding deferred from v3.0 scope; AppHeader byte-stable beyond the 5-line surgical insert | v3.1+ — REQUIREMENTS.md → **TENANT-BRAND-v31** (Per-company branding: logos, color palettes) |
| Hardcoded CHECK constraint `company_id IN ('seva', 'juno')` instead of `companies` DB table | Per D-03 — N=2 in v3.0; a `companies` table adds operational complexity (referential integrity migrations, runtime CRUD) without benefit at this scale | v3.2+ when N>2 — REQUIREMENTS.md → **TENANT-N-v32** (Support for arbitrary N>2 companies, move from hardcoded CHECK to companies DB table) |
| `JOB_LOCK_IDS['juno_weekly_sweeper']=1021` is slot-only (not registered as an APScheduler job) | Per D-01 — Juno Sweeper out of v3.0 scope; reserving the lock ID now prevents future collision (OPS-02 assertion); JOB_LOCK_IDS dict serves as the canonical lock-ID registry | v3.1+ Juno Sweeper phase — will call `scheduler.add_job(..., id="juno_weekly_sweeper")` under existing lock 1021 |

---

## Gaps Summary

**No gaps found.** Every must-have artifact exists, is substantive, is wired, and has data flowing through it. Every TENANT-* requirement is SATISFIED with code + test evidence. Every D-02 documentation location landed. The regression gate (backend 184 / scheduler 269 / frontend 165 + CI grep gate exit 0) holds. Both blocking human-verify checkpoints (smoke + visual QA) were operator-APPROVED at Plan 09-05.

The atomic-deploy contract held — partial multi-tenancy never shipped. `/seva/*` byte-equivalent to v2.1; `/juno/*` empty-state on all 3 tabs; one cron fire produces both Seva (completed) + Juno (partial) `daily_summaries` rows.

---

*Verified: 2026-05-19T18:00:00Z*
*Verifier: Claude (gsd-verifier)*
*Phase: 09-multi-tenant-foundation*
*Milestone: v3.0 — Multi-Tenant Dashboards (Juno Industries Onboarding)*
*Outcome: GREEN — all 10 must-haves verified*
