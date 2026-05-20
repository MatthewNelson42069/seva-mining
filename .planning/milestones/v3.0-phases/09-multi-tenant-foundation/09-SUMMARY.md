---
phase: 09-multi-tenant-foundation
type: phase-level-summary
status: GREEN
milestone: v3.0
shipped: 2026-05-19
plan_count: 5
plans_completed: 5
requirements_completed: [TENANT-01, TENANT-02, TENANT-03, TENANT-04, TENANT-05, TENANT-06, TENANT-07, TENANT-08, TENANT-09, TENANT-10]
decisions_implemented: [D-01, D-01a, D-01b, D-02, D-02a, D-03, D-04, D-05, D-06, D-07, D-08]
checkpoints:
  - 09-05 Task 3 — smoke-test (blocking) — APPROVED
  - 09-05 Task 4 — visual QA at 1440x900 (blocking) — APPROVED
tags: [multi-tenant, alembic-0014, scoped-helpers, fastapi-path-prefix, react-router-v7, company-switcher, freeze-lift, queryKeys-factory, zustand-persist, per-company-cron, juno-idempotency-fix, tenant-isolation-tests]
---

# Phase 9: Multi-Tenant Foundation Summary (v3.0)

**Outcome:** GREEN — atomic-deploy contract satisfied across 5 waves. The single-tenant Seva dashboard is now a two-tenant platform: `/seva/*` renders byte-equivalent to v2.1, `/juno/*` renders auth-gated empty-states on all 3 tabs, one scheduler fire produces both a Seva and a Juno `daily_summaries` row (Juno=`partial` until Phase 10 fills real content), and the cross-tenant isolation test suite (`test_multitenant_isolation.py`) is GREEN with 19 tests covering every list endpoint × tenant + 4 negative-case contracts. Every TENANT-01..10 requirement verified in code AND tests AND human eyeball.

## Phase Performance

- **Started:** 2026-05-19 (Wave 0)
- **Shipped:** 2026-05-19 (all 5 waves same-day)
- **Plans:** 5/5 complete
- **Tasks (across all 5 plans):** 14 auto + 2 blocking checkpoints (both APPROVED)
- **Net new code:** ~24 NEW files + ~35 MODIFIED files across backend + scheduler + frontend + tests + docs
- **Test count change (all 3 layers):** backend 156 → 184 (+28 net), scheduler 264 → 269 (+5 net), frontend 141 → 165 (+24 net) — total +57 tests net

## TENANT-01..10 Evidence Map

Every multi-tenant requirement is verified in code AND tests AND (where applicable) human eyeball.

| Req | What it is | Evidence (code) | Evidence (tests) | Plan |
|-----|------------|-----------------|------------------|------|
| TENANT-01 | `company_id` column on 3 multi-tenant tables, backfilled `'seva'` in same Alembic 0014 transaction | `backend/alembic/versions/0014_add_company_id.py` + `backend/app/models/{daily_summary,calendar_item,weekly_sweep}.py` + scheduler/models mirrors | `backend/tests/test_migration_0014.py` (Wave 0 RED → Wave 1 GREEN) | 09-02 |
| TENANT-02 | CHECK constraint `company_id IN ('seva', 'juno')` + composite indexes `(company_id, <sort>)` | Same 0014 migration — `ck_*_company_id` constraints + composite index DDL | `test_migration_0014.py` checks constraint + EXPLAIN ANALYZE uses composite | 09-02 |
| TENANT-03 | `backend/app/queries/scoped.py` helpers + CI grep gate | `backend/app/queries/scoped.py` (`scoped_summaries`, `scoped_calendar`, `scoped_weekly_sweeps`) + `scripts/verify-tenant-isolation.sh` | `backend/tests/test_queries_scoped.py` + grep gate exits 0 with empty PRE_WAVE_2_WHITELIST | 09-01 (gate), 09-02 (helpers) |
| TENANT-04 | `/api/{company}/...` path-prefix + `get_current_company` dep + 404 on unknown | `backend/app/main.py` router registration + `backend/app/dependencies.py::get_current_company` + 3 routers refactored | `test_multitenant_isolation.py` 6 parametrized tests + 3 invalid-company 404 + 5 invalid-uppercase 422 | 09-03 |
| TENANT-05 | `<Route path=":company">` wrapper + `useParams<{company}>` source of truth | `frontend/src/App.tsx` route tree + `frontend/src/components/layout/CompanyScopedRoute.tsx` | `frontend/src/__tests__/App.test.tsx` 7 tests + `CompanyScopedRoute.test.tsx` 4 tests | 09-04 |
| TENANT-06 | Bookmark grace: `/`, `/calendar`, `/viral`, `/queue`, `/agents/:slug` all redirect to `/seva/*` | `frontend/src/App.tsx` — 5 `<Navigate>` elements OUTSIDE `<ProtectedRoute>` | `App.test.tsx` 5 grace-redirect tests + 09-05 Task 4 visual QA "Bookmark grace" section (7 items PASS) | 09-04 |
| TENANT-07 | `CompanySwitcher` segmented control in formally freeze-lifted AppHeader | `frontend/src/components/layout/CompanySwitcher.tsx` + `frontend/src/components/layout/AppHeader.tsx` (5-line surgical insert) | `CompanySwitcher.test.tsx` 5 tests + 09-05 Task 4 visual QA "CompanySwitcher visual states" (8 items PASS) | 09-04 |
| TENANT-08 | Per-company cron — Juno `daily_summary` at 08:05+12:05 PT, 5-min stagger; OPS-02 lock IDs 1020/1021 added | `scheduler/worker.py` `JOB_LOCK_IDS['juno_daily_summary']=1020` + `_make_juno_daily_summary_job` factory + `scheduler/agents/daily_summary.py::run_juno_daily_summary` | `scheduler/tests/test_worker.py` + `test_juno_daily_summary.py` + 09-05 Task 3 smoke (live DB confirms 2 rows + 2 agent_runs + idempotency proof) | 09-03 |
| TENANT-09 | Centralized `queryKeys` factory with `companyId` slot in every tuple | `frontend/src/api/queryKeys.ts` — `summaries(c, limit)`, `calendar(c, start, end)`, `weeklySweeps(c, limit)` | `queryKeys.test.ts` 4 tests + cache-clear-on-switch verified visually in 09-05 Task 4 | 09-04 |
| TENANT-10 | Cross-tenant isolation regression test — every read endpoint, both tenants | `backend/tests/test_multitenant_isolation.py` (Wave 0 scaffold → Wave 4 fully populated) | 19 tests GREEN: 6 parametrized (3 endpoints × 2 tenants) + 3 invalid-company 404 + 5 invalid-uppercase 422 + 3 unprefixed-legacy 404 + POST persists company_id + PATCH cannot cross tenant | 09-05 |

All 10 TENANT-* requirements pass. The atomic-deploy contract holds.

## Decisions (D-01..D-08 outcomes)

This section documents how each CONTEXT.md decision was implemented and verified. **The D-02 entry below satisfies the first of three required D-02 documentation locations per CONTEXT.md (a = this Decisions section; b = inline comment in AppHeader.tsx; c = .planning/PROJECT.md Key Decisions table).**

### D-01: Per-company jobs with explicit lock IDs (RESOLVED — Approach B)

Implemented per-company APScheduler jobs with explicit lock IDs `JOB_LOCK_IDS['juno_daily_summary']=1020` + `JOB_LOCK_IDS['juno_weekly_sweeper']=1021` (slot reserved; registration deferred to v3.1+). Each job has its own `_make_juno_daily_summary_job(engine)` factory mirroring `_make_daily_summary_job`. OPS-02 advisory-lock uniqueness assertion preserved at scheduler boot.

**D-01a (5-min stagger):** Juno fires at `hour="8,12", minute=5` — 08:05 + 12:05 PT — while Seva stays at `hour="8,12"` (08:00 + 12:00 PT). Spreads Anthropic API rate-limit pressure; avoids simultaneous Sonnet calls.

**D-01b (per-company independent failure mode):** Seva failure does NOT block Juno (and vice versa). Each tenant has its own try/except + its own `agent_runs` row + its own `daily_summaries` row write.

**Verification:** 09-03 wave commit `75815b1` registered both lock IDs; 09-05 Task 3 smoke confirmed one scheduler fire produces 2 distinct `agent_run_id` rows (1 Seva + 1 Juno).

### D-02: AppHeader Phase 5 byte-freeze formally lifted (RESOLVED — Path A) — **freeze-lift**

The Phase 5 byte-freeze on `frontend/src/components/layout/AppHeader.tsx` was **formally lifted in v3.0 (Phase 9)** via a surgical 5-line insert of `<CompanySwitcher />` between the brand-mark `<div>` and the Logout `<button>`. AppHeader becomes the canonical home for the CompanySwitcher, matching Linear / Notion / Slack / Vercel convention. The v3.0 baseline becomes the new locked contract going forward; v2.1 visual QA baseline is re-baselined at Phase 9 verification (09-05 Task 4 PASSED at 1440x900).

The **AppHeader freeze-lift** is documented in three locations per the D-02 contract:

- **(a) This Decisions section** — first documentation location (enforced by plan-level grep gate in 09-05-PLAN verification).
- **(b) Inline code comment** in `frontend/src/components/layout/AppHeader.tsx`: `// v3.0 freeze-lift (Phase 9) — see 09-CONTEXT.md D-02` immediately above the 2-line `<CompanySwitcher />` insertion.
- **(c) `.planning/PROJECT.md` Key Decisions table** entry dated 2026-05-19 referencing 09-CONTEXT.md D-02 with rationale + status `Locked`.

The grep gate `grep -c "freeze-lift\|AppHeader freeze" .planning/phases/09-multi-tenant-foundation/09-SUMMARY.md` returns `>=1` against this section (multiple occurrences of "freeze-lift" and "AppHeader freeze" intentional).

**D-02a (brand mark + wordmark stay "Seva Mining" both tenants in v3.0):** the amber "S" 28x28 square + "Seva Mining" wordmark are byte-preserved on both `/seva/*` and `/juno/*`. Per-company branding is explicitly deferred to v3.1+ per `REQUIREMENTS.md → TENANT-BRAND-v31`. Visual QA confirmed at 1440x900 (09-05 Task 4 "AppHeader" section item 8).

**Verification:** 09-04 wave commits `eacbc23` + `cf3fb15` landed the freeze-lift + CompanySwitcher; 09-05 Task 4 visual QA at 1440x900 PASSED all 8 AppHeader items + 8 CompanySwitcher items.

### D-03: Hardcoded CHECK + Python Literal (RESOLVED — Approach A)

Alembic 0014 added `CHECK company_id IN ('seva', 'juno')` to all 3 multi-tenant tables. `ACTIVE_COMPANIES: tuple[str, ...] = ("seva", "juno")` lives in `backend/app/companies/__init__.py` and `scheduler/companies/__init__.py`. NO `companies` DB table in v3.0. Tech debt accepted: close in v3.2+ when N>2 tenants requires a `companies` table (tracked as `TENANT-N-v32` in REQUIREMENTS.md).

**Verification:** `test_migration_0014.py` asserts the CHECK constraint exists; `ACTIVE_COMPANIES` imported across backend + scheduler.

### D-04: Short tenant slugs `:company` (RESOLVED)

URLs are `/seva/...` and `/juno/...`. Slug regex `^[a-z][a-z0-9-]{1,19}$` enforced by FastAPI Path validator (returns 422 for uppercase/invalid; `test_multitenant_isolation.py` covers 5 such cases). React Router uses `:company`; FastAPI uses `{company}`.

**Verification:** `App.test.tsx` 7 routing tests + `test_multitenant_isolation.py` invalid-uppercase 422 tests.

### D-05: Bare `/` redirects to `/seva/` (HARDCODED, not last-visited) (RESOLVED)

Bare `/` always redirects to `/seva/` in v3.0. Last-visited persistence is deferred to v3.1+. Zustand `persist` middleware DOES populate `lastVisitedCompany` as a byproduct of the switcher action (D-08), but the bare `/` redirect ignores it. Open path to a v3.1+ "last-visited landing" feature without re-architecture.

**Verification:** `App.test.tsx` bare-`/`-redirects-to-`/seva/` test + 09-05 Task 4 "Persistence" section item 3 confirms behavior.

### D-06: v2.x bookmark grace redirects to Seva (RESOLVED)

All unprefixed legacy URLs auto-redirect:
- `/` → `/seva/`
- `/calendar` → `/seva/calendar`
- `/viral` → `/seva/viral`
- `/queue` → `/seva/`
- `/agents/:slug` → `/seva/`
- `/digest`, `/settings`, `/login` → unchanged (NOT tenant-scoped)

Grace redirects sit OUTSIDE `<ProtectedRoute>` in `App.tsx` (a Wave 3 decision; the v2.x pattern was INSIDE). Better UX (stale bookmarks redirect before login prompt) + simpler test setup.

**Verification:** 5 grace-redirect tests in `App.test.tsx` + 09-05 Task 4 "Bookmark grace" section (7 items PASS).

### D-07: CompanySwitcher segmented control (RESOLVED)

Two side-by-side `<button>` elements (Seva | Juno) with `border-zinc-800` baseline + active state `border-brand-accent text-brand-accent bg-brand-accent-subtle`. Uses semantic CSS tokens from v2.1 Phase 8 (`--color-brand-accent[-hover/-subtle]`), NOT literal `amber-500`. Active state derived from `useParams<{company: string}>()` — URL is canonical. Switching companies fires `navigate(`/${nextCompany}${currentSubPath}`)` to preserve the user's current tab.

**Verification:** `CompanySwitcher.test.tsx` 5 tests + 09-05 Task 4 "CompanySwitcher visual states" + "Tab preservation on switch" sections (8 + 5 items PASS).

### D-08: TanStack Query cache invalidation on switch (RESOLVED)

Switching tenants calls `queryClient.clear()` BEFORE `navigate()` — atomic ordering verified in CompanySwitcher.tsx onClick handler. Every query key includes a `companyId` slot via centralized `frontend/src/api/queryKeys.ts` factory. CI grep gate forbids `queryKey: [` outside that module.

**Verification:** `CompanySwitcher.test.tsx` order assertion via `mock.invocationCallOrder` + 09-05 Task 4 "Performance / cache behavior" section (3 items PASS — visible cache clear BEFORE new page renders, refetch fires for new tenant endpoints, no infinite refetch loop).

---

## Wave-by-Wave Plan Summaries

### Wave 0 (09-01) — Failing-tests-first scaffolding

Landed 12 Wave 0 test files (backend + scheduler + frontend) with module-level or per-test `pytest.skip` / `it.skip` decorators tied to Wave 1/2/3 dependencies. Each test encoded a RED contract that downstream waves' GREEN code MUST satisfy. CI grep gate `scripts/verify-tenant-isolation.sh` landed at Wave 0 with a `PRE_WAVE_2_WHITELIST` (5 entries, each tied to a Wave 2 refactor task). All 10 TENANT-* requirements have at least one RED test scaffolded. Plan duration: ~10 min; tasks: 3; files: 12.

### Wave 1 (09-02) — DB foundation + scoped helpers + companies module

Alembic 0014 added `company_id` column + CHECK constraint + composite indexes to 3 multi-tenant tables (`daily_summaries`, `calendar_items`, `weekly_sweeps`) with `server_default='seva'` backfill in same transaction (expand/contract pattern). Dual-model parity: 6 model files updated (3 backend + 3 scheduler). `backend/app/queries/scoped.py` + `scheduler/queries/scoped.py` exposed `scoped_summaries`, `scoped_calendar`, `scoped_weekly_sweeps` helpers. `backend/app/companies/__init__.py` exposed `ACTIVE_COMPANIES` + `CompanyId` Literal. Migration test `test_migration_0014.py` GREEN. Backend 165 pass / 6 skip. Plan duration: ~9 min; tasks: 3; files: 15.

### Wave 2 (09-03) — `/api/{company}` routers + scheduler Juno cron + scoped scheduler queries

3 backend routers (`summaries.py`, `calendar.py`, `weekly_sweeps.py`) refactored to mount under `/api/{company}` prefix with `get_current_company` dep; all raw `select()` calls replaced with `scoped_*()` helpers. Scheduler companies subpackage skeleton landed (`scheduler/companies/juno/{feeds,prompts,serpapi}.py` stubs). `_make_juno_daily_summary_job` factory + `JOB_LOCK_IDS['juno_daily_summary']=1020` + `juno_weekly_sweeper=1021` (slot only) registered in `scheduler/worker.py`. `run_juno_daily_summary` stub writes `status='partial'` Juno row with `notes={"company_id":"juno", "phase_10_pending": true}`. APScheduler registers Juno cron at 08:05+12:05 PT (5-min stagger per D-01a). CI grep gate runs clean with EMPTY `PRE_WAVE_2_WHITELIST`. Backend 175 pass; scheduler 269 pass. Plan duration: ~23 min; tasks: 3; files: 24.

### Wave 3 (09-04) — Frontend routing + CompanySwitcher + AppHeader freeze-lift

`frontend/src/App.tsx` restructured with `<Route path=":company" element={<CompanyScopedRoute />}>` wrapper + 5 bookmark grace `<Navigate>` redirects OUTSIDE `<ProtectedRoute>`. New: `queryKeys.ts` factory, `CompanyScopedRoute.tsx`, `CompanySwitcher.tsx`, `companySlice.ts` (with Zustand `persist` middleware on `lastVisitedCompany`). `AppHeader.tsx` formally freeze-lifted with 5-line surgical insert + inline `// v3.0 freeze-lift (Phase 9) — see 09-CONTEXT.md D-02` comment (D-02 second documentation location landed here). `TabNav.tsx` prepends `/${company}` to NavLink `to` props. 3 page components (`SummaryFeedPage`, `ContentCalendarPage`, `WeeklyViralSweeperPage`) gain Juno empty-state short-circuits before hooks fire. 5 Wave 0 frontend test files transitioned from SKIPPED → GREEN (23 tests). Frontend 165 pass / 0 skip. Plan duration: ~15 min; tasks: 3; files: 24.

### Wave 4 (09-05) — TENANT-10 isolation tests + smoke + visual QA

`backend/tests/test_multitenant_isolation.py` Wave 0 scaffold replaced with 19-test parametrized matrix (TENANT-10 closure). Smoke-test heredoc against live dev DB surfaced + auto-fixed (Rule 1) a Juno idempotency bug — filter was `status.in_(['running','completed'])` but Juno writes `'partial'`; without the fix every cron fire would have produced duplicate Juno rows in production. `.planning/PROJECT.md` Key Decisions entry recorded the AppHeader freeze-lift (D-02 third documentation location). Both blocking checkpoints — Task 3 smoke-test (DB row contracts) + Task 4 visual QA at 1440x900 (50+ item UI-SPEC checklist) — APPROVED by operator. Backend 184 pass; CI grep gate exits 0 with no temporary whitelists. Plan duration: ~45 min (Tasks 1+2 ~10 min execution; Tasks 3+4 ~30 min human walkthrough including idempotency bug-fix iteration); tasks: 4; files: 5.

---

## Lessons Learned / Pitfalls Hit

1. **Idempotency inclusion-list semantics differ per tenant** — the Juno bug surfaced because the original implementation copied Seva's `{running, completed}` filter verbatim, but Juno's steady-state in v3.0 is `partial`. Pre-prod catch via smoke-test gate. Future similar additions (e.g. Phase 10 might add a third tenant in v3.2+) MUST review whether the new tenant's normal status set matches Seva's or Juno's. Documented in `261b8fa` commit message + 09-05-SUMMARY.

2. **Test fixtures must reset `company_id` context between tests** — PITFALLS.md MEDIUM-6. The function-scoped `both_tenant_rows` fixture in `test_multitenant_isolation.py` seeds fresh rows per test; no ContextVar pollution.

3. **Zustand singleton state leaks between tests** — Wave 3 fix: `companySlice.test.ts` `beforeEach` now resets `useAppStore.setState({lastVisitedCompany: null})` because the module-level Zustand singleton retained state across tests even after `localStorage.clear()`. Single-line fix; documented in 09-04-SUMMARY Decision 1.

4. **React Router v7 rules-of-hooks chokepoint** — Wave 3 split `WeeklyViralSweeperPage` into a thin outer dispatcher + a child `SevaWeeklyViralSweeperPage` so the outer can branch on `useParams` BEFORE child hooks fire. Without the split, ESLint react-hooks/rules-of-hooks fires because the Juno early-return would skip hook calls.

5. **Bookmark grace OUTSIDE `<ProtectedRoute>` is a deliberate v3.0 change** — better UX (stale bookmarks redirect to canonical URL before login prompt) + simpler test setup (no auth state required for the redirect tests). The `:company` nested route + `/digest` + `/settings` stay INSIDE ProtectedRoute.

6. **Semantic CSS tokens, not literal amber-500, in new Phase 9 code** — `border-brand-accent / text-brand-accent / bg-brand-accent-subtle` throughout CompanySwitcher. Phase 8 D-05 contract preserved. Existing literals in frozen Phase 5/6/8 surfaces preserved untouched.

7. **`queryClient.clear()` BEFORE `navigate()` atomic ordering** — verified visually at 09-05 Task 4 (no flash of stale Seva content on Seva → Juno switches). Test asserts via `mock.invocationCallOrder`.

8. **The smoke-test gate (`checkpoint:smoke-test`) is essential** — it caught a critical idempotency bug that no unit test surfaced (the unit test mocked the DB; the bug only appeared against a real Postgres with real `IDEMPOTENCY_WINDOW_MIN` and real `status='partial'` rows). Iteration 2 Blocker 3 fix path validated.

## Handoff to Phase 10

Phase 10 (`10-juno-defence-news-funnel`) fills `scheduler/companies/juno/{feeds,prompts,serpapi}.py` with real defence-industry content. The infrastructure shipped in Phase 9 is byte-stable; Phase 10 is config-only:

- **Per-company cron is wired** — `scheduler/worker.py::JOB_LOCK_IDS['juno_daily_summary']=1020` + 08:05+12:05 PT cron. Phase 10 only needs to populate the stub `_run_juno_daily_summary()` body (it currently writes `status='partial'` with empty sections).
- **`/api/juno/*` routes are live** — every list endpoint already filters by `company_id='juno'` via `scoped_*()` helpers. Phase 10 only needs `daily_summaries` rows with `company_id='juno'` and populated `defence_news_md` / `canadian_procurement_md` / `world_events_md` columns (column adds happen in Phase 10 migration 0015 — not a Phase 9 concern).
- **`frontend/src/api/queryKeys.ts` factory already produces `['summaries', 'juno', limit]` keys** — Phase 10 needs no frontend refactor for cache routing.
- **`CompanySwitcher` already renders + functions** — Phase 10 swaps the Juno empty-state copy for live `SummaryCard` rendering once `daily_summaries` rows exist. The `SummaryCard.tsx` component tolerates missing-or-renamed section markdown fields per DEF-08 (Phase 10 concern).
- **Bookmark grace + auth + `:company` routing are stable** — Phase 10 introduces no new routes or auth changes.

The atomic-deploy contract held: partial multi-tenancy never shipped. Every read, every write, every cache key, every cron, and every route is tenant-scoped. The cross-tenant isolation test suite (`test_multitenant_isolation.py`) will catch any Phase 10 regression that forgets `WHERE company_id = ?`.

---

*Phase: 09-multi-tenant-foundation*
*Milestone: v3.0 — Multi-Tenant Dashboards (Juno Industries Onboarding)*
*Shipped: 2026-05-19*
*Outcome: GREEN — atomic-deploy contract satisfied*
