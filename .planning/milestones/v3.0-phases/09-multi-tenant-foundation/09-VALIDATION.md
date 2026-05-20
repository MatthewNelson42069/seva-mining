---
phase: 09
slug: multi-tenant-foundation
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-19
---

# Phase 09 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `09-RESEARCH.md` §Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Backend framework** | pytest 9.x + pytest-asyncio 1.3.x (asyncio_mode=auto) |
| **Backend config** | `backend/pyproject.toml` `[tool.pytest.ini_options]` |
| **Backend quick run** | `cd backend && uv run pytest tests/test_multitenant_isolation.py -x` |
| **Backend full suite** | `cd backend && uv run pytest -x` |
| **Scheduler framework** | pytest 9.x + pytest-asyncio 1.3.x |
| **Scheduler config** | `scheduler/pyproject.toml` `[tool.pytest.ini_options]` |
| **Scheduler quick run** | `cd scheduler && uv run pytest tests/test_worker.py -x` |
| **Scheduler full suite** | `cd scheduler && uv run pytest -x` |
| **Frontend framework** | Vitest 4.1.2 + @testing-library/react 16.3.2 + jsdom |
| **Frontend config** | `frontend/package.json` `"test": "vitest"` (defaults) |
| **Frontend quick run** | `cd frontend && npm test -- --run src/components/layout/CompanySwitcher.test.tsx` |
| **Frontend full suite** | `cd frontend && npm test -- --run` |
| **CI grep gate** | `bash scripts/verify-tenant-isolation.sh` (must exit 0) |
| **Estimated runtime (backend full)** | ~2-3 seconds (156 + new tests) |
| **Estimated runtime (scheduler full)** | ~5 seconds (264 + new tests) |
| **Estimated runtime (frontend full)** | ~6-9 seconds (141 + new tests) |

---

## Sampling Rate

- **After every task commit:** Quick-run the test file most tied to the task. E.g.:
  - W1 migration commit → `cd backend && uv run pytest tests/test_migration_0014.py -x`
  - W2 router commit → `cd backend && uv run pytest tests/test_multitenant_isolation.py -x`
  - W3 CompanySwitcher commit → `cd frontend && npm test -- --run src/components/layout/CompanySwitcher.test.tsx`
- **After every plan wave:**
  - W1: backend full + grep gate
  - W2: backend full + scheduler full + grep gate
  - W3: frontend full + grep gate
- **Before `/gsd:verify-work`:**
  - Backend full green, scheduler full green, frontend full green
  - CI grep gate (`scripts/verify-tenant-isolation.sh`) exits 0
  - Smoke deploy to Railway preview: `/seva/*` renders v2.1 byte-equivalent; `/juno/*` renders empty states; one manual APScheduler fire writes both Seva (`completed`) + Juno (`partial`) `daily_summaries` rows
- **Max feedback latency:** ~10 seconds (vitest full + pytest full)

---

## Per-Task Verification Map

Plan-task IDs assigned by the planner. The req→test mapping below shows what evidence each TENANT-* requirement needs at execution time.

| Req ID | Behavior | Test Type | Automated Command | File Exists |
|--------|----------|-----------|-------------------|-------------|
| TENANT-01 | Alembic 0014 adds `company_id` to 3 tables, backfills `'seva'` via `server_default` | unit (migration) | `cd backend && uv run pytest tests/test_migration_0014.py -x` | ❌ W0 |
| TENANT-01 | Dual-model parity: backend + scheduler models both carry `company_id` | unit (parity) | `cd backend && uv run pytest tests/test_model_parity.py -x` | ❌ W0 (extend existing) |
| TENANT-02 | CHECK constraint rejects invalid company_id | unit (DB) | `cd backend && uv run pytest tests/test_migration_0014.py::test_check_constraint -x` | ❌ W0 |
| TENANT-02 | Composite indexes exist on (company_id, sort_col) | unit (DB) | `cd backend && uv run pytest tests/test_migration_0014.py::test_composite_indexes -x` | ❌ W0 |
| TENANT-03 | `scoped_summaries(company)` returns `Select` with `company_id` filter | unit | `cd backend && uv run pytest tests/test_queries_scoped.py -x` | ❌ W0 |
| TENANT-03 | CI grep gate fails on raw `select(DailySummary\|CalendarItem\|WeeklySweep)` outside `queries/scoped.py` | shell | `bash scripts/verify-tenant-isolation.sh` | ❌ W0 |
| TENANT-04 | `get_current_company()` returns 404 on invalid slug | integration | `cd backend && uv run pytest tests/test_multitenant_isolation.py::test_invalid_company_returns_404 -x` | ❌ W0 |
| TENANT-04 | Router prefix `/api/{company}/summaries` reachable | integration | `cd backend && uv run pytest tests/test_multitenant_isolation.py -x` | ❌ W0 |
| TENANT-05 | `<CompanyScopedRoute>` redirects invalid slug to `/seva` | unit (RTL) | `cd frontend && npm test -- --run src/components/layout/CompanyScopedRoute.test.tsx` | ❌ W0 |
| TENANT-05 | Nested `:company` route mounts `<TabbedDashboard>` w/ useParams | unit (RTL) | `cd frontend && npm test -- --run src/App.test.tsx` | ❌ W0 |
| TENANT-06 | `/calendar` → `/seva/calendar`; `/queue` → `/seva`; `/agents/:slug` → `/seva` | unit (RTL) | `cd frontend && npm test -- --run src/App.test.tsx::bookmark_grace` | ❌ W0 |
| TENANT-07 | `<CompanySwitcher>` calls `queryClient.clear()` + `navigate('/${next}${subPath}')` on click | unit (RTL) | `cd frontend && npm test -- --run src/components/layout/CompanySwitcher.test.tsx` | ❌ W0 |
| TENANT-07 | Zustand `companySlice` persists `lastVisitedCompany` to existing app-state localStorage key | unit | `cd frontend && npm test -- --run src/stores/companySlice.test.ts` | ❌ W0 |
| TENANT-08 | `JOB_LOCK_IDS` has both `juno_daily_summary=1020` and `juno_weekly_sweeper=1021` | unit | `cd scheduler && uv run pytest tests/test_worker.py::test_job_lock_ids_v3 -x` | ❌ W0 (extend existing) |
| TENANT-08 | `build_scheduler()` registers `juno_daily_summary` with `CronTrigger(hour="8,12", minute=5, ...)` | unit | `cd scheduler && uv run pytest tests/test_worker.py::test_juno_daily_summary_registered -x` | ❌ W0 |
| TENANT-08 | `run_juno_daily_summary()` writes `daily_summaries` row with `company_id='juno'` + `status='partial'` | integration | `cd scheduler && uv run pytest tests/agents/test_juno_daily_summary.py -x` | ❌ W0 |
| TENANT-09 | `queryKeys.summaries('seva', 60)` returns `['summaries', 'seva', 60] as const` | unit | `cd frontend && npm test -- --run src/api/queryKeys.test.ts` | ❌ W0 |
| TENANT-09 | Switching tenant invokes `queryClient.clear()` | unit (RTL) | `cd frontend && npm test -- --run src/components/layout/CompanySwitcher.test.tsx::test_clears_cache_on_switch` | ❌ W0 |
| TENANT-10 | Parametrized cross-tenant leak: each tenant's API returns ONLY its own rows (3 endpoints × 2 tenants) | integration | `cd backend && uv run pytest tests/test_multitenant_isolation.py -x` | ❌ W0 |

*Status legend: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky — populated by executor.*

---

## Wave 0 Requirements

All test files for Phase 9 are NEW (or extensions of existing). Wave 0 must create the failing tests (RED phase of TDD) before any implementation lands.

- [ ] `scripts/verify-tenant-isolation.sh` — CI grep gate. Regex: `select\((DailySummary|CalendarItem|WeeklySweep)[\)\.]` outside `backend/app/queries/scoped.py` (and its `__init__.py` re-exports). Initially passes (no raw selects yet); fails mid-refactor; passes again at phase close.
- [ ] `backend/tests/test_migration_0014.py` — verifies `company_id` column exists; `server_default='seva'` applied; CHECK constraint enumerates `('seva','juno')`; composite indexes `(company_id, generated_at DESC)` etc. present.
- [ ] `backend/tests/test_queries_scoped.py` — verifies `scoped_summaries('seva')` returns a Select whose compiled SQL contains `daily_summaries.company_id = 'seva'`.
- [ ] `backend/tests/test_multitenant_isolation.py` — parametrized over `('seva', 'juno')` × `('summaries', 'calendar', 'weekly-sweeps')`. Creates rows for both tenants, asserts each endpoint returns ONLY its own. Plus `test_invalid_company_returns_404` test.
- [ ] **Extend** `backend/tests/test_model_parity.py` — add `test_daily_summary_parity()` mirroring existing CalendarItem/WeeklySweep parity tests.
- [ ] **Extend** `scheduler/tests/test_worker.py` — add `test_juno_lock_ids_present`, `test_juno_daily_summary_registered`, `test_scheduler_registers_4_jobs` (bump existing job-count assertion).
- [ ] `scheduler/tests/agents/test_juno_daily_summary.py` — verifies `run_juno_daily_summary()` (or equivalent factory wrapper) writes a `daily_summaries` row with `company_id='juno'` AND `status='partial'`.
- [ ] `frontend/src/api/queryKeys.test.ts` — verifies factory shape: `queryKeys.summaries('seva', 60)` ↔ `['summaries', 'seva', 60] as const`.
- [ ] `frontend/src/stores/companySlice.test.ts` — verifies `lastVisitedCompany` persists to localStorage under the existing `seva-mining-app-state-v3` key via `persist` + `partialize`.
- [ ] `frontend/src/components/layout/CompanyScopedRoute.test.tsx` — verifies invalid-slug routes redirect to `/seva` (or 404 if planner picks that route).
- [ ] `frontend/src/components/layout/CompanySwitcher.test.tsx` — verifies click triggers `queryClient.clear()` + `navigate('/${next}${subPath}')`; active state derived from `useParams<{company}>()`.
- [ ] `frontend/src/App.test.tsx` — verifies bookmark grace redirects (`/calendar` → `/seva/calendar`, `/queue` → `/seva/`, `/agents/:slug` → `/seva/`) + nested `:company` route mounts `<TabbedDashboard>`.

**Framework install:** none needed — pytest + vitest already configured.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Visual QA at 1440×900 across Seva + Juno tabs | UI-SPEC.md QA Checklist (30+ items) | Per Phase 8 D-10 — manual eyeball is mandated for visual QA | See `09-UI-SPEC.md §QA Checklist` reproduced into 09-PLAN.md human-verify checkpoint |
| Browser back/forward across company switch | TENANT-05 / TENANT-07 | Real browser history API behavior not testable in jsdom (no real navigation engine) | Click switcher Seva → Juno → Seva; press browser back twice; active state on switcher should track URL. Confirm no console errors. |
| Smoke deploy: one APScheduler fire writes both Seva + Juno rows | TENANT-08 | APScheduler in a separate worker process; needs real deployment to verify cron triggers fire as expected | Deploy to Railway preview; manually trigger or wait for 08:00 + 08:05 PT fire; query `SELECT company_id, status FROM daily_summaries WHERE generated_at > NOW() - INTERVAL '1 hour'` |
| Existing v2.x bookmarks survive | TENANT-06 | Browser-cached bookmarks behavior | Manually navigate to `/`, `/calendar`, `/viral`, `/queue`, `/agents/breaking_news`, `/digest`, `/settings` in browser → confirm grace redirects work + auth gate behaves identically to v2.1 |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (12 items above)
- [ ] No watch-mode flags (`--watch` forbidden)
- [ ] Feedback latency < 15s (pytest + vitest + grep)
- [ ] `nyquist_compliant: true` set in frontmatter at plan close

**Approval:** pending
