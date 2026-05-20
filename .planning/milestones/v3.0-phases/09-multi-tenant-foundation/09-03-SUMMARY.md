---
phase: 09-multi-tenant-foundation
plan: 03
subsystem: backend-routers-scheduler-juno
tags: [fastapi, apscheduler, multi-tenant, tenant-isolation, scoped-queries, juno-stub, dual-model-parity, ci-grep-gate]

# Dependency graph
requires:
  - phase: 09-multi-tenant-foundation
    plan: 02
    provides: backend/app/queries/scoped.py + get_current_company dep + company_id column on 3 multi-tenant tables (dual-model parity)
provides:
  - 3 backend routers (summaries / calendar / weekly_sweeps) mounted under /api/{company} prefix; every endpoint takes Depends(get_current_company) + routes through scoped_*() helpers
  - scheduler/companies/__init__.py — CompanyId Literal + ACTIVE_COMPANIES tuple (byte-equivalent to backend mirror per Phase 5 D-03 dual-model parity)
  - scheduler/companies/juno/{__init__,feeds,prompts,serpapi}.py — minimal stub package so Phase 10 fills the lists without re-architecture
  - scheduler/queries/{__init__,scoped}.py — scheduler-side scoped helpers mirror (imports from scheduler.models.* since scheduler is a separate Railway service)
  - scheduler/agents/daily_summary.py:run_juno_daily_summary() — TENANT-08 stub entry point that writes status='partial' Juno row; per-company idempotency
  - scheduler/worker.py: JOB_LOCK_IDS 1020 (registered) + 1021 (slot-only); _make_juno_daily_summary_job factory; build_scheduler registers Juno cron with 5-min stagger
  - CI grep gate PASSES with EMPTY PRE_WAVE_2_WHITELIST — all 5 prior raw select() call sites now route through scoped helpers
affects: [09-04-PLAN.md, 09-05-PLAN.md]

# Tech tracking
tech-stack:
  added: []  # no new deps — uses existing fastapi, apscheduler, sqlalchemy 2.x
  patterns:
    - "FastAPI per-router /api/{company} prefix via include_router(prefix=...) — path parameter inherited by every endpoint; get_current_company dep narrows to typed CompanyId Literal"
    - "Defence-in-depth scoped lookup on mutation endpoints: PATCH + DELETE call `scoped_calendar(company).where(CalendarItem.id == item_id)` BEFORE mutating, so cross-tenant mutations return 404 even if the operator guesses a foreign UUID"
    - "APScheduler per-company job factory: _make_juno_daily_summary_job(engine) closes over engine + lazy-imports the entry point; mirrors _make_daily_summary_job exactly; advisory-lock-wrapped under JOB_LOCK_IDS[\"juno_daily_summary\"]=1020"
    - "5-min cron stagger between tenants: Seva hour=\"8,12\", minute=0 + Juno hour=\"8,12\", minute=5 (same twice-daily cadence, 5-min offset) — spreads Anthropic API rate-limit pressure"
    - "Slot-only lock ID reservation: juno_weekly_sweeper=1021 in JOB_LOCK_IDS but NOT registered in build_scheduler — preserves OPS-02 inventory clarity + saves a future surgical edit"
    - "@compiles(JSONB, 'sqlite') hook for in-memory test fixture: SQLite has no JSONB; the hook downgrades to JSON for test compilation while production (Postgres) is unaffected"
    - "Scheduler-side dual-model parity for query helpers: scheduler/queries/scoped.py mirrors backend/app/queries/scoped.py byte-for-byte except for the `models.*` vs `app.models.*` import path — the scheduler is a separate Railway process without `app.*` on its python path"

key-files:
  created:
    - scheduler/companies/__init__.py
    - scheduler/companies/juno/__init__.py
    - scheduler/companies/juno/feeds.py
    - scheduler/companies/juno/prompts.py
    - scheduler/companies/juno/serpapi.py
    - scheduler/queries/__init__.py
    - scheduler/queries/scoped.py
  modified:
    - backend/app/main.py
    - backend/app/routers/summaries.py
    - backend/app/routers/calendar.py
    - backend/app/routers/weekly_sweeps.py
    - backend/app/schemas/daily_summary.py
    - backend/app/schemas/calendar.py
    - backend/app/schemas/weekly_sweep.py
    - backend/tests/test_multitenant_isolation.py
    - backend/tests/test_calendar_router.py
    - backend/tests/test_weekly_sweeps_router.py
    - backend/tests/routers/test_summaries.py
    - scheduler/agents/daily_summary.py
    - scheduler/agents/weekly_sweeper.py
    - scheduler/worker.py
    - scheduler/tests/test_worker.py
    - scheduler/tests/agents/test_juno_daily_summary.py
    - scripts/verify-tenant-isolation.sh

key-decisions:
  - "Juno cron schedule corrected to hour=\"8,12\", minute=5 (08:05 + 12:05 PT, twice daily) per CONTEXT.md D-01a as-corrected — the prior CONTEXT typo of 07:05 PT was rejected because the existing Seva cron is at hour=\"8,12\" + the 5-min-stagger principle preserves cadence (TENANT-08)"
  - "PATCH/DELETE calendar endpoints use scoped_calendar(company) lookup BEFORE mutation (defence-in-depth on top of URL prefix); cross-tenant ID guesses return 404, not silent foreign-tenant mutation"
  - "test_multitenant_isolation.py uses a NEW dedicated tenant_test_engine + tenant_authed_client fixture pair (one shared engine; @compiles JSONB→JSON for SQLite) — the conftest stock async_db_session / authed_client fixtures use per-fixture engines and would never share data under SQLite :memory: semantics (Rule 2 critical-functionality fix)"
  - "scheduler/tests/agents/test_juno_daily_summary.py rewritten to use AsyncSessionLocal mock pattern (matches existing test_daily_summary.py) — the scheduler test layer has no SQLite fixture since models carry Postgres JSONB+UUID; mock pattern captures session.add() calls + asserts on constructor args"
  - "Pydantic response schemas (SummaryCardResponse / CalendarItemResponse / WeeklySweepCard) gain optional `company_id: str | None = None` for debug visibility — operator can see the tenant in curl output / network inspector even though URL is authoritative"
  - "PRE_WAVE_2_WHITELIST emptied AND grep gate still exits 0 — all 5 prior raw select() call sites (3 routers + scheduler/agents/daily_summary.py + scheduler/agents/weekly_sweeper.py) now route through canonical scoped helpers"

metrics:
  duration: 23 # minutes (estimated)
  completed_date: 2026-05-19
  tasks_completed: 3
  task_count: 3
  files_modified: 24  # 7 new + 17 modified
  tests_added: 12     # 10 multitenant (6 parametrized + 4 invalid-slug) + 2 juno
  tests_unblocked: 4  # 4 worker juno tests
  tests_passed_backend: 175
  tests_passed_scheduler: 269

requirements:
  closed: [TENANT-04, TENANT-08]
---

# Phase 09 Plan 03: Wave 2 — Backend Routers + Scheduler Juno Cron Summary

**One-liner:** Wired backend's 3 multi-tenant routers to `/api/{company}/...` prefix + `scoped_*()` helpers, mirrored the tenant module + scoped helpers on the scheduler side, registered `juno_daily_summary` cron at 08:05+12:05 PT with 5-min stagger from Seva, and closed the CI grep gate with an empty whitelist.

## What was built

### Task 1 — backend routers refactored (commit `af65f1c`)

Three multi-tenant routers + main.py registration + Pydantic schemas + test URL updates:

- **`summaries.py`**: GET → `scoped_summaries(company)`; mounted at `/api/{company}/summaries`.
- **`calendar.py`**: all 4 endpoints (GET/POST/PATCH/DELETE) take `company: CompanyId = Depends(get_current_company)`. POST seeds `company_id=company` on the new row. PATCH/DELETE use `scoped_calendar(company).where(CalendarItem.id == item_id)` lookup so cross-tenant mutations return 404 (defence-in-depth).
- **`weekly_sweeps.py`**: GET → `scoped_weekly_sweeps(company)`; count query filtered by `WeeklySweep.company_id == company`.
- **`main.py`**: 3 `include_router(...)` calls gain `prefix="/api/{company}"`. Other routers (auth, queue, watchlists, keywords, agent_runs, digests, content, config, content_bundles, post_to_x) UNCHANGED — they're not tenant-scoped in v3.0.
- **Schemas**: `SummaryCardResponse`, `CalendarItemResponse`, `WeeklySweepCard` each gain optional `company_id: str | None = None` for debug visibility.
- **Test URL rewrites**: `test_calendar_router.py` (28 sites) + `test_weekly_sweeps_router.py` (9 sites) + `test_summaries.py` (7 sites) — every `/summaries` / `/calendar` / `/weekly-sweeps` URL became `/api/seva/{...}`. MagicMock-based tests gain `.company_id = "seva"` so Pydantic `str | None` validation passes.
- **`test_multitenant_isolation.py`**: skip removed AND fixture rewired — new `tenant_test_engine` + `tenant_session_factory` + `tenant_authed_client` fixtures so seeding session + HTTP client share one engine. `@compiles(JSONB, "sqlite")` hook downgrades JSONB → JSON at test compile time.

**Commit:** `af65f1c` — `feat(09-03): refactor 3 backend routers to /api/{company} prefix + scoped helpers`

### Task 2 — scheduler companies + queries + Juno stub (commit `c413cfe`)

Scheduler-side multi-tenant plumbing + Juno stub package + `run_juno_daily_summary` entry point + raw-select refactors:

- **`scheduler/companies/__init__.py`**: `CompanyId = Literal["seva", "juno"]` + `ACTIVE_COMPANIES = ("seva", "juno")`. Byte-equivalent to `backend/app/companies/__init__.py` per Phase 5 D-03 dual-model parity.
- **`scheduler/companies/juno/{__init__,feeds,prompts,serpapi}.py`**: ~30-line stub package per CONTEXT.md Claude's Discretion #3. `JUNO_DEFENCE_FEEDS=[]`, `JUNO_SERPAPI_QUERIES=[]`, `DEFENCE_NEWS_SYSTEM_PROMPT="STUB — Phase 10 will design..."`. Each file marked as Phase 10 deliverable (DEF-01 / DEF-02 / DEF-03).
- **`scheduler/queries/{__init__,scoped}.py`**: mirror of `backend/app/queries/scoped.py`, but imports from `models.*` (the scheduler is a separate Railway process; `app.*` is not on its python path). Same 3 helpers: `scoped_summaries / scoped_calendar / scoped_weekly_sweeps`.
- **`scheduler/agents/daily_summary.py`**:
  - `_idempotency_skip()` now uses `scoped_summaries("seva").with_only_columns(DailySummary.id)`.
  - The previous-summary read for LAW-04 continuity + Phase 3 stats snapshot also routes through `scoped_summaries("seva")`.
  - `DailySummary(...)` constructors (success + failure paths) now set `company_id="seva"` explicitly.
  - **NEW**: `async def run_juno_daily_summary() -> None` appended at bottom — per-company idempotency via `scoped_summaries("juno")`, then inserts a `daily_summaries` row with `company_id="juno"`, `status="partial"`, all section markdown NULL, `raw_sources_jsonb={"company_id":"juno","phase_10_pending":true,"note":"Juno Defence News Funnel ships in Phase 10"}`, `error_text="Juno content pipeline pending — Phase 10"`. AgentRun row written with `agent_name="juno_daily_summary"`, `notes` JSON containing `{"company_id":"juno","phase_10_pending":true}`, transitions running → completed.
- **`scheduler/agents/weekly_sweeper.py`**: `_compute_virality()` virality scan + `_idempotency_skip()` Sweep lookup route through `scoped_summaries("seva")` + `scoped_weekly_sweeps("seva")`. WeeklySweep constructors set `company_id="seva"` explicitly.
- **`scripts/verify-tenant-isolation.sh`**: ALLOWED array gains `scheduler/queries/scoped.py` + `scheduler/queries/__init__.py`. `set -u`-safe empty-array expansion idiom (`${arr[@]+"${arr[@]}"}`).
- **`scheduler/tests/agents/test_juno_daily_summary.py`**: rewritten to use the AsyncSessionLocal mock pattern (matches existing `test_daily_summary.py`). Two tests verify the partial-row write + per-company idempotency.

**Commit:** `c413cfe` — `feat(09-03): add scheduler companies + queries + Juno daily_summary stub`

### Task 3 — JOB_LOCK_IDS + Juno cron registration (commit `75815b1`)

APScheduler topology + tests:

- **`scheduler/worker.py`**:
  - `JOB_LOCK_IDS` gains `"juno_daily_summary": 1020` (REGISTERED) + `"juno_weekly_sweeper": 1021` (SLOT-ONLY). OPS-02 uniqueness assertion still passes — 6 distinct keys.
  - `_make_juno_daily_summary_job(engine)` factory placed immediately after `_make_daily_summary_job(engine)` — mirrors it exactly; closes over engine; lazy-imports `agents.daily_summary.run_juno_daily_summary`; wraps in `with_advisory_lock(conn, JOB_LOCK_IDS["juno_daily_summary"], "juno_daily_summary", run_juno_daily_summary)`.
  - `build_scheduler()` registers `juno_daily_summary` at `CronTrigger(hour="8,12", minute=5, timezone="America/Los_Angeles")` — 5-min stagger from Seva. Includes `max_instances=1, misfire_grace_time=1800`.
  - **`juno_weekly_sweeper` is NOT registered** — slot-only per D-01 (registration ships in v3.1+ when Juno Sweeper lands).
- **`scheduler/tests/test_worker.py`**:
  - 4 Wave-0 RED tests unblocked (skip lines removed): `test_juno_lock_ids_present`, `test_juno_daily_summary_registered`, `test_scheduler_registers_4_jobs_after_juno_add`, `test_juno_weekly_sweeper_NOT_registered`.
  - Existing `test_retired_crons_absent_from_job_lock_ids` updated: `len(JOB_LOCK_IDS) == 4 → 6`; expected set gains `juno_daily_summary` + `juno_weekly_sweeper`.
  - `test_scheduler_registers_3_jobs_after_v1_deregistration` renamed to `test_scheduler_registers_4_jobs_after_juno_add`; expected job set + `len(jobs) == 4`.
  - `test_build_scheduler_omits_v1_sub_agent_crons`: `assert len(job_ids) == 4` + explicit `juno_daily_summary` membership check.

**Commit:** `75815b1` — `feat(09-03): register juno_daily_summary cron + add JOB_LOCK_IDS 1020/1021`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 — Missing critical functionality] `test_multitenant_isolation.py` fixture wiring**
- **Found during:** Task 1
- **Issue:** The Wave 0 RED test was written using `async_db_session` (to seed rows) + `authed_client` (to call endpoints) from the stock conftest. Those fixtures instantiate SEPARATE per-fixture in-memory SQLite engines, so under SQLite `:memory:` semantics rows added via the seeding session would never be visible to the HTTP route. The test would always fail with "row not found" even if the routers were correct.
- **Fix:** Wrote a new dedicated fixture set in the test file itself — `tenant_test_engine` creates ONE engine + creates the 3 tenant-scoped tables on it; `tenant_session_factory` is bound to that engine; `tenant_authed_client` overrides `get_db` to yield sessions from the same factory. Added `@compiles(JSONB, "sqlite")` hook so the JSONB columns compile against SQLite via JSON.
- **Files modified:** `backend/tests/test_multitenant_isolation.py`
- **Commit:** `af65f1c`

**2. [Rule 1 — Bug] MagicMock vs Pydantic `str | None` schema field**
- **Found during:** Task 1 (revealed by router test failures after adding `company_id: str | None` to response schemas)
- **Issue:** `test_summaries.py` + `test_weekly_sweeps_router.py` use `MagicMock` to mimic ORM rows. After adding `company_id: str | None` to the Pydantic response schemas, Pydantic validation tripped on `<MagicMock name='mock.company_id' ...>` returning a MagicMock instance (not a string).
- **Fix:** Each `make_summary()` / `make_sweep()` helper explicitly sets `.company_id = "seva"` so Pydantic str validation passes. Matches DB `server_default="seva"`.
- **Files modified:** `backend/tests/routers/test_summaries.py`, `backend/tests/test_weekly_sweeps_router.py`
- **Commit:** `af65f1c`

**3. [Rule 1 — Bug] `set -u` empty-array expansion in grep gate**
- **Found during:** Task 2 (first grep gate run after emptying whitelist)
- **Issue:** `verify-tenant-isolation.sh` uses `set -euo pipefail`. After Task 1 emptied `PRE_WAVE_2_WHITELIST=()`, the for-loop `for path in "${PRE_WAVE_2_WHITELIST[@]}"` tripped `unbound variable` under bash's `-u` strictness mode.
- **Fix:** Replaced with the standard `${arr[@]+"${arr[@]}"}` idiom — safely expands to nothing when the array is empty.
- **Files modified:** `scripts/verify-tenant-isolation.sh`
- **Commit:** `c413cfe`

**4. [Rule 1 — Bug] Docstring text trips own grep gate**
- **Found during:** Task 2 (grep gate ran on refactored daily_summary.py)
- **Issue:** Two comment/docstring lines in `scheduler/agents/daily_summary.py` mentioned the literal text `select(DailySummary)` (in describing what was rewritten + what the grep gate blocks). The grep pattern `select\((DailySummary|CalendarItem|WeeklySweep)[\)\.]` matched those documentation strings.
- **Fix:** Rephrased to "raw select-of-DailySummary" — same meaning, no false-positive trigger.
- **Files modified:** `scheduler/agents/daily_summary.py`, `backend/app/routers/calendar.py`, `backend/app/routers/weekly_sweeps.py`
- **Commit:** `af65f1c` (router fix) + `c413cfe` (daily_summary fix)

**5. [Rule 2 — Out-of-scope extension] `tests/routers/test_summaries.py` URL rewrites**
- **Found during:** Task 1
- **Issue:** The plan only mentioned updating `test_calendar_router.py` + `test_weekly_sweeps_router.py` URL paths in step 7. But `tests/routers/test_summaries.py` also uses `/summaries` URLs (7 sites) and would 404 after the `main.py` prefix change.
- **Fix:** Same `sed`-based rewrite (`/summaries` → `/api/seva/summaries`). Test now passes against the new prefix.
- **Files modified:** `backend/tests/routers/test_summaries.py`
- **Commit:** `af65f1c`

**6. [Rule 2 — Scheduler-agent invariant] Explicit `company_id="seva"` on Seva-side ORM writes**
- **Found during:** Task 2 (per plan's "must_haves > truths" item: every write to multi-tenant tables should carry an explicit company_id even though server_default would cover the omission)
- **Issue:** Existing `run_daily_summary()` + `run_weekly_sweeper()` constructed `DailySummary(...)` and `WeeklySweep(...)` without setting `company_id`. Postgres `server_default='seva'` would fill it in, but explicit is grep-able.
- **Fix:** Both success + failure paths now set `company_id="seva"` in the constructor. Failure-row constructors too.
- **Files modified:** `scheduler/agents/daily_summary.py`, `scheduler/agents/weekly_sweeper.py`
- **Commit:** `c413cfe`

### Out of scope — none deferred

No items deferred to a future plan. The grep gate passes with an empty whitelist; both backend + scheduler full test suites are GREEN.

## Authentication gates

None. Plan 09-03 is pure refactor + new code; no third-party auth required.

## Self-Check: PASSED

- All 7 created files exist (verified via `ls`).
- All 3 commit hashes resolve (`af65f1c`, `c413cfe`, `75815b1`).
- Backend suite: 175 passed, 5 skipped (was 165 — net +10 from new TENANT-10 tests).
- Scheduler suite: 269 passed, 1 skipped (was 264 + 2 new juno + 3 unblocked worker juno tests).
- CI grep gate: `bash scripts/verify-tenant-isolation.sh` exits 0 with empty PRE_WAVE_2_WHITELIST.
- OPS-02 invariant verified: `len(set(JOB_LOCK_IDS.values())) == len(JOB_LOCK_IDS) == 6`.
- Precheck (step 0): both `test_calendar_router.py` + `test_weekly_sweeps_router.py` exist at the planned paths — no alternate paths needed.

## Handoff to Wave 3 (09-04 / 09-05)

Wave 3 wires the frontend:
- `<Route path=":company">` wrapper around `<TabbedDashboard />` in `frontend/src/App.tsx`.
- `<CompanySwitcher />` inside `AppHeader.tsx` (Phase 5 byte-freeze formally lifted in v3.0 per D-02).
- Bookmark grace redirects: `/calendar` → `/seva/calendar`, `/queue` → `/seva/`, `/agents/:slug` → `/seva/`, etc.
- `queryKeys.ts` factory with `company_id` slot in every query key.
- Zustand `persist` middleware for `lastVisitedCompany` field on the existing app store.
- Page-level `useParams<{company: string}>()` + new API client paths (`/api/${company}/calendar`, `/api/${company}/summaries`, `/api/${company}/weekly-sweeps`).
