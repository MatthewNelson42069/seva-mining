# Phase 9: Multi-Tenant Foundation - Research

**Researched:** 2026-05-19
**Domain:** Multi-tenant pivot (row-level `company_id` + path-prefix routing + per-company scheduler) on FastAPI + SQLAlchemy 2.0 async + APScheduler + React 19 + react-router-dom v7
**Confidence:** HIGH — all patterns grounded in v2.x codebase reads + CONTEXT.md locked decisions; LOW only where react-router-dom v7 nested-Outlet idiom is asserted (mitigation noted)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Scheduler topology (D-01):** Per-company jobs with explicit lock IDs. Add `juno_daily_summary=1020` AND `juno_weekly_sweeper=1021` to `JOB_LOCK_IDS` in `scheduler/worker.py`. Both slots reserved in Phase 9; `juno_daily_summary` is REGISTERED in Phase 9; `juno_weekly_sweeper` is the SLOT ONLY (registered in v3.1+). Each Juno job gets its own `add_job(..., args=[company_id])` factory mirroring `_make_daily_summary_job`. OPS-02 advisory-lock uniqueness assertion preserved.

**D-01a — Stagger:** Seva `daily_summary` at 07:00 PT (existing). Juno `daily_summary` at 07:05 PT (5-min stagger). Wait — the actual existing Seva fires are 08:00 PT and 12:00 PT (per `scheduler/worker.py` line 391-400, `hour="8,12"`). CONTEXT.md D-01a says Seva stays at 07:00 PT which appears to be a typo — planner MUST resolve before commitment. **Research assumption:** the Seva fires stay at their current 08:00 + 12:00 PT cadence; Juno mirrors with a 5-min stagger (08:05 + 12:05 PT) — this matches both the "5-min stagger" intent and the existing twice-daily v2.1 reality.

**D-01b — Per-company independent failure:** Seva failure does NOT block Juno (and vice versa). Each tenant's job has its own try/except + its own `agent_runs` row + its own `daily_summaries` row write. One APScheduler fire writes 0/1/2 `daily_summaries` rows depending on per-company success.

**AppHeader (D-02):** Path A — formally LIFT Phase 5 byte-freeze with documented v3.0 rationale. Surgical 5-line `<CompanySwitcher />` insert between brand mark `<div>` and Logout `<button>`. Document in (a) Phase 9 SUMMARY.md, (b) inline comment, (c) `.planning/PROJECT.md` Key Decisions.

**D-02a — Branding:** Brand mark + wordmark stay "Seva Mining" on both tenants in v3.0. Per-company branding deferred to v3.1+ per TENANT-BRAND-v31.

**Tenant ID source (D-03):** Hardcoded CHECK constraint + Python Literal. Alembic 0014 adds `CHECK company_id IN ('seva', 'juno')` to all three multi-tenant tables. `ACTIVE_COMPANIES: Literal["seva", "juno"]` in `backend/app/companies/__init__.py` AND mirrored in `scheduler/companies/__init__.py`. NO `companies` DB table in v3.0. Tech debt closed in v3.2+ via TENANT-N-v32.

**URLs (D-04):** Short tenant slugs `/seva/...` and `/juno/...`. Slug regex: `^[a-z][a-z0-9-]{1,19}$`. Path parameter is `:company` in React Router and `{company}` in FastAPI.

**Bare-/ redirect (D-05):** Bare `/` redirects to `/seva/` HARDCODED (NOT last-visited). Last-visited persistence is deferred to v3.1+. Zustand `persist` still stores `lastVisitedCompany` as byproduct of switch action — bare `/` ignores it for v3.0.

**Bookmark grace (D-06):** Auto-prefix to `/seva/`:
- `/` → `/seva/`
- `/calendar` → `/seva/calendar`
- `/viral` → `/seva/viral`
- `/queue` → `/seva/` (legacy v2.0 target preserved)
- `/agents/:slug` → `/seva/` (legacy v2.0 target preserved)
- `/digest`, `/settings`, `/login` UNCHANGED (NOT tenant-scoped — stay at root)
- Implementation: React Router `<Navigate>` elements. NO 404 for legacy bookmarks.

**CompanySwitcher visual (D-07):** Segmented control. Two side-by-side buttons (Seva | Juno) with `border-zinc-800` baseline + active state `border-brand-accent text-brand-accent`. Uses semantic CSS tokens from Phase 8 (`--color-brand-accent[-hover/-subtle]`), NOT literal `amber-500`. Active state derived from `useParams<{company: string}>()` — URL is canonical. Switch fires `navigate(`/${nextCompany}${currentSubPath}`)` to preserve current tab.

**TanStack cache (D-08):** Switching tenants calls `queryClient.clear()` as defence-in-depth. Every query key gains a `company_id` slot via centralized factory at `frontend/src/api/queryKeys.ts`.

### Claude's Discretion

1. **Login post-auth redirect target.** Default: hardcoded `/seva/`. Planner may instead route to last-visited if `intended URL` was tenant-scoped — matches existing `<ProtectedRoute>` "intended destination" pattern. Recommendation: match existing behavior.
2. **Tab state preservation across switch.** D-07 says "preserve current sub-path". Planner picks exact behavior when target tenant has no content for that sub-path (e.g. switching to `/juno/viral` lands on empty-state, which is fine).
3. **`scheduler/companies/juno/` skeleton in Phase 9.** Recommended: minimal `scheduler/companies/juno/{feeds.py, prompts.py, serpapi.py}` skeleton (~30 lines) with empty lists + no-op Sonnet call returning canned partial markdown. So Phase 10 is purely "fill the lists."
4. **CI grep gate.** Recommended: shell script `scripts/verify-tenant-isolation.sh` mirroring v2.1 grep verification pattern. Grep for `select(DailySummary)` / `select(CalendarItem)` / `select(WeeklySweep)` outside `backend/app/queries/scoped.py` and `backend/app/queries/__init__.py`. Wired into Wave 0.
5. **Zustand persist naming.** `lastVisitedCompany` (camelCase) stored under EXISTING localStorage key — add to existing Zustand store, don't create new persist target. Note: the existing `useAppStore` does NOT currently use `persist` middleware (verified by reading `frontend/src/stores/index.ts` + slice files — `authSlice` rolls its own `localStorage.setItem('access_token', ...)`). Adding `persist` middleware to `useAppStore` is a new pattern in Phase 9 (planner picks key name).

### Deferred Ideas (OUT OF SCOPE)

- Per-company branding (TENANT-BRAND-v31)
- `companies` DB table (TENANT-N-v32)
- Last-visited tenant for bare `/` redirect (v3.1+)
- Per-tenant Anthropic API key (v3.1+)
- Cmd+K command palette (v3.1+)
- Per-company RBAC (TENANT-RBAC-v32)
- Real Juno content — Defence News + Canadian Procurement + World Events (Phase 10 / DEF-01..10)
- Juno Calendar (Tab 2) + Juno Weekly Viral Sweeper (Tab 3) (JUNO-CAL-v31 + JUNO-SWEEP-v31)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TENANT-01 | Add `company_id VARCHAR(20)` to 3 tables via Alembic 0014, backfill `'seva'` in same transaction; expand/contract (DEFAULT in 0014, drop in v3.0.1) | §Alembic Pattern + Code Example 1 |
| TENANT-02 | CHECK constraint `company_id IN ('seva', 'juno')` + composite indexes `(company_id, <sort-col>)` on all 3 tables | §Alembic Pattern + Code Example 1 |
| TENANT-03 | `backend/app/queries/scoped.py` with `scoped_summaries(company_id)`, `scoped_calendar(company_id)`, `scoped_weekly_sweeps(company_id)` helpers; CI grep gate | §Scoped Repository Pattern + Code Example 2 + §CI Grep Gate + Code Example 7 |
| TENANT-04 | Router prefix `/api/{company}/...` with `get_current_company()` FastAPI dep validating `company in ('seva', 'juno')` and returning 404 otherwise | §FastAPI Dependency + Code Example 3 |
| TENANT-05 | `<Route path=":company">` wrapper around `<TabbedDashboard>`; `useParams<{company: string}>()` is source of truth | §React Router Nested Pattern + Code Example 4 |
| TENANT-06 | Bare `/` redirects to `/seva/` (hardcoded per D-05); grace redirects for `/calendar`, `/viral`, `/queue`, `/agents/:slug` to `/seva/*` | §React Router Nested Pattern + §Bookmark Grace |
| TENANT-07 | `CompanySwitcher` segmented control inside AppHeader, semantic CSS tokens, `queryClient.clear()` on switch + Zustand persist | §CompanySwitcher + Code Example 5 |
| TENANT-08 | Per-company scheduler — Juno `daily_summary` registered in Phase 9 with `status='partial'` row; lock ID 1020 used + 1021 reserved | §APScheduler Per-Company Factory + Code Example 8 + §Juno Skeleton + Code Example 9 |
| TENANT-09 | Centralized TanStack key factory at `frontend/src/api/queryKeys.ts` — every key includes `companyId` | §TanStack Key Factory + Code Example 6 |
| TENANT-10 | `backend/tests/test_multitenant_isolation.py` — both-tenant rows, parametrized over ('seva', 'juno'), asserts no cross-tenant leakage | §Multi-Tenant Test Fixtures + Code Example 10 |
</phase_requirements>

## Summary

Phase 9 is an additive multi-tenant pivot on a stable v2.x foundation. CONTEXT.md D-01..D-08 lock every architectural decision (scheduler topology, AppHeader freeze treatment, tenant ID source-of-truth, URL shape, redirect behavior, switcher visual, cache invalidation). This research focuses on **implementation patterns only** — how to write the migration, how to shape the scoped helpers, what the React Router nested `<Outlet>` looks like, and how to wire up the validation architecture (Nyquist) for Phase 9's 10 requirements.

Three findings drive the plan shape:

1. **Migration 0014 must use `server_default='seva'` in the SAME ALTER COLUMN that adds the column** so that the cron firing during deploy gets `'seva'` automatically (PITFALLS.md HIGH-3 backfill race). The DEFAULT stays in 0014; a follow-up v3.0.1 migration drops it once all callers pass `company_id` explicitly. **NO `CREATE INDEX CONCURRENTLY`** needed here — at v3.0's row count (~60 rows total across all 3 tables), inline `op.create_index` inside the migration transaction is fast enough that the lock-table window is sub-millisecond. CONCURRENTLY only matters when the existing table has millions of rows.

2. **The `scoped_*()` helpers return `Select` statements (not pre-executed results)**, so callers compose `.order_by()`, `.where()`, `.limit()` on top. This matches v2.x router style and keeps the helper API surface tiny.

3. **react-router-dom is v7.13** in this repo (NOT v6 as research files said). v7 is API-compatible with v6 for `<Route>`, `<Navigate>`, `useParams`, `<Outlet>` patterns — but the planner should NOT assume v6-specific quirks. v7's `useParams<T>()` requires explicit type assertion because v7 returns `Readonly<Params<string>>` with all string values.

**Primary recommendation:** Implement in 4 waves: (W0) test scaffolding + CI grep gate + failing tests, (W1) DB migration + dual-model parity + scoped helpers, (W2) backend router prefix + `get_current_company` dep + per-company scheduler refactor, (W3) frontend routing + CompanySwitcher + queryKey factory + Zustand persist.

## Project Constraints (from CLAUDE.md)

These directives from `/Users/matthewnelson/seva-mining/CLAUDE.md` MUST be honored by all Phase 9 plans:

- **Stack locked:** FastAPI 0.135.x + Python 3.12+ + SQLAlchemy 2.0 async + asyncpg + Alembic 1.14.x + APScheduler 3.11.2 (NOT v4 alpha) + React 19 + Vite 6 + Tailwind v4 + Zustand 5.x + TanStack Query 5.x + shadcn (tailwind-v4 branch).
- **Async-only Python:** No `requests` in async code; no sync `Session`. Use `httpx.AsyncClient` + `AsyncSession`.
- **Pydantic v2 only:** `model_config = ConfigDict(from_attributes=True)` — never v1 patterns.
- **NO Alembic --autogenerate:** Phase 9's 0014 migration is hand-written (continuing the 0010-0013 pattern). Pitfall MOD-2 from v2.0 — autogenerate emits spurious DDL.
- **Single APScheduler worker process:** Never spawn multi-worker Gunicorn for the scheduler. Advisory locks defend against accidental duplicates.
- **NO autoposting:** Hard prohibition. Phase 9 does not touch the X posting path. (Not relevant to Phase 9 scope — flagged for completeness.)
- **GSD Workflow:** All file edits flow through GSD commands. Planner should use `/gsd:execute-phase`.
- **Dual-model parity:** Every multi-tenant table edit happens in BOTH `backend/app/models/` AND `scheduler/models/`. Parity is enforced at test time via `backend/tests/test_model_parity.py`.

## Standard Stack

### Core (already installed — verified via `scheduler/pyproject.toml` + `frontend/package.json`)

| Library | Version (verified) | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SQLAlchemy | 2.0.x | ORM + Select composition | Locked stack; `select(Model).where(...)` is the v2.x idiom for every router |
| asyncpg | 0.30.x | Async PG driver | Locked; powers `AsyncSession` |
| Alembic | 1.14.x | DB migrations | Hand-written migrations only (0010-0013 precedent) |
| APScheduler | 3.11.2 | Job scheduler | NOT v4 alpha. Advisory-lock pattern established. |
| FastAPI | 0.135.x | HTTP framework | `Depends()` for `get_current_company`; `APIRouter(prefix=)` for `/api/{company}` |
| Pydantic | 2.x | Validation | `model_config = ConfigDict(from_attributes=True)` |
| react-router-dom | 7.13.x | Routing | **NOTE: v7, not v6** — API-compatible for nested routes, but `useParams<T>()` generics differ |
| zustand | 5.0.x | Client state | `zustand/middleware.persist` for `lastVisitedCompany` |
| @tanstack/react-query | 5.96.x | Server state | `queryClient.clear()` on tenant switch; centralized key factory |

### No new dependencies

Phase 9 introduces **zero** new pip or npm dependencies. All capabilities (Zustand persist middleware, React Router nested routes, TanStack key invalidation, SQLAlchemy event listeners) ride on packages already shipped.

**Version verification:** Versions confirmed via direct file reads (`scheduler/pyproject.toml`, `frontend/package.json` on 2026-05-19). No upgrades required.

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Row-level `company_id` | Postgres RLS (`SET app.current_tenant`) | RLS requires connection-pool checkin handler to RESET; asyncpg + SQLAlchemy 2.0 async pool needs careful wiring. PITFALLS.md CRITICAL-1 documents the leak failure mode. ROW-LEVEL is correct for v3.0 (locked D-03). |
| Hardcoded CHECK | `companies` DB table | Locked OUT per D-03; deferred to v3.2+ (TENANT-N-v32) |
| Path prefix `/seva/` | Subdomain (`juno.seva-mining-smm.vercel.app`) | Locked OUT — Vercel + DNS overhead; cross-origin JWT scope. Path-prefix is correct for v3.0 |
| `<Route path=":company">` wrapper | `<Routes>` per tenant | Wrapper composes naturally with nested `<Outlet>`; per-tenant routes duplicate every leaf |
| SQLAlchemy `event.listen(Session, "do_orm_execute", ...)` global guard | Repository class with `__init__(company_id)` | Both are defence-in-depth. PITFALLS.md mentions event listener; plan can ship either. **Recommended: ship the explicit-parameter `scoped_*()` helpers in W1, defer the event listener as a v3.1+ hardening item** unless the planner finds time in W3. The event listener catches "forgot to use the helper" mistakes that the CI grep gate also catches. Belt + suspenders. |

**Installation:** None — all deps already present.

## Architecture Patterns

### Recommended Project Structure (NEW files added in Phase 9)

```
backend/app/
├── companies/                           # NEW package — backend slim (Literal type only)
│   ├── __init__.py                      # ACTIVE_COMPANIES tuple + CompanyId Literal
│   └── types.py                         # re-export for cleaner imports (optional)
├── queries/                             # NEW package — scoped helpers (cross-leak defence)
│   ├── __init__.py                      # re-export scoped_*() functions
│   └── scoped.py                        # scoped_summaries, scoped_calendar, scoped_weekly_sweeps
└── alembic/versions/
    └── 0014_add_company_id.py           # NEW — expand/contract migration

scheduler/
├── companies/                           # NEW package — scheduler-side (mirrors backend)
│   ├── __init__.py                      # ACTIVE_COMPANIES + get_config()
│   ├── base.py                          # CompanyConfig dataclass
│   ├── seva/
│   │   ├── __init__.py                  # SEVA_CONFIG
│   │   ├── prompts.py                   # GOLD_NEWS_SYSTEM_PROMPT (relocated from daily_summary.py)
│   │   ├── feeds.py                     # gold RSS feed URLs (placeholder — Seva continues to use content_agent.py)
│   │   └── serpapi.py                   # gold SerpAPI queries (placeholder)
│   └── juno/
│       ├── __init__.py                  # JUNO_CONFIG (empty stub — Phase 10 fills)
│       ├── prompts.py                   # DEFENCE_NEWS_SYSTEM_PROMPT stub
│       ├── feeds.py                     # [] empty list — Phase 10 fills
│       └── serpapi.py                   # [] empty list — Phase 10 fills

frontend/src/
├── api/
│   └── queryKeys.ts                     # NEW — centralized TanStack key factory
├── components/layout/
│   ├── CompanySwitcher.tsx              # NEW — segmented control
│   └── CompanyScopedRoute.tsx           # NEW — :company param validator + Zustand publish
└── stores/slices/
    └── companySlice.ts                  # NEW — lastVisitedCompany + persist

scripts/
└── verify-tenant-isolation.sh           # NEW — CI grep gate

backend/tests/
└── test_multitenant_isolation.py        # NEW — TENANT-10 cross-tenant leak detection
```

### Pattern 1: Alembic 0014 Expand/Contract Migration (TENANT-01, TENANT-02)

**What:** Add `company_id` column with `server_default='seva'` so the column is NOT NULL immediately and existing rows + concurrent cron writes both get `'seva'` automatically. Drop the DEFAULT in a follow-up v3.0.1 migration once all callers pass `company_id` explicitly.

**When to use:** Any time a NOT NULL column is added to a live table that an unstoppable writer (cron, request handler) touches mid-deploy.

**Key reference:** Mirror the style of `backend/alembic/versions/0013_calendar_title_nullable_unique_date.py` (single-step alter + constraint) and `0010_add_daily_summaries.py` (hand-written, no autogenerate, no `from sqlalchemy.dialects import postgresql` unless UUID/JSONB needed).

**Code:** See Code Example 1 below.

### Pattern 2: SQLAlchemy 2.0 Scoped Repository Helpers (TENANT-03)

**What:** Module `backend/app/queries/scoped.py` exports synchronous helper functions that RETURN `Select` statements pre-filtered by `company_id`. Routers compose `.order_by()` + `.limit()` on top and execute via the existing `AsyncSession.execute()` pattern.

**When to use:** Every read of `daily_summaries`, `calendar_items`, `weekly_sweeps` after Phase 9.

**Signature shape (recommended — synchronous helpers returning Select, NOT async):**

```python
# backend/app/queries/scoped.py
from typing import Literal
from sqlalchemy import Select, select
from app.models.daily_summary import DailySummary
from app.models.calendar_item import CalendarItem
from app.models.weekly_sweep import WeeklySweep

CompanyId = Literal["seva", "juno"]

def scoped_summaries(company_id: CompanyId) -> Select:
    """Return a SELECT pre-filtered by company. Callers add .order_by()/.limit()/.where()."""
    return select(DailySummary).where(DailySummary.company_id == company_id)

def scoped_calendar(company_id: CompanyId) -> Select:
    return select(CalendarItem).where(CalendarItem.company_id == company_id)

def scoped_weekly_sweeps(company_id: CompanyId) -> Select:
    return select(WeeklySweep).where(WeeklySweep.company_id == company_id)
```

**Router integration:** See Code Example 2. The router function unchanged in shape — just replaces `select(DailySummary)` with `scoped_summaries(company)`.

**Defence-in-depth — SQLAlchemy event listener (OPTIONAL for Phase 9):** The planner CAN ship a `do_orm_execute` event listener that asserts every SELECT against the three multi-tenant tables has a `company_id` clause. This is belt + suspenders on top of the scoped helpers + CI grep gate. Reference shape:

```python
# backend/app/database.py — OPTIONAL addition
from sqlalchemy import event
from sqlalchemy.orm import Session

_TENANT_SCOPED_TABLES = {"daily_summaries", "calendar_items", "weekly_sweeps"}

@event.listens_for(Session, "do_orm_execute")
def _enforce_tenant_filter(orm_execute_state):
    """Defence-in-depth: every SELECT on a tenant-scoped table MUST include
    company_id in its WHERE clause. Raises if a helper-bypass slipped through.
    Skip in test mode via state.execution_options.get('skip_tenant_check')."""
    if orm_execute_state.execution_options.get("skip_tenant_check"):
        return
    if not orm_execute_state.is_select:
        return
    # Walk the compiled statement; check if any FROM clause is a tenant-scoped table
    # AND ensure 'company_id' appears in the WHERE clause text.
    # ... (implementation depth depends on planner — sketch only here)
```

**Recommendation:** Ship the helpers + CI grep gate in W1-W2. Defer the event listener to a v3.1+ task UNLESS the planner has spare cycles in W3 — it requires careful integration with the test suite (every test fixture must call `.execution_options(skip_tenant_check=True)` or include the filter).

### Pattern 3: FastAPI `get_current_company()` Dependency (TENANT-04)

**What:** Router-level dependency that extracts `company` from the URL path parameter, validates against `ACTIVE_COMPANIES`, returns 404 on miss. Used as `dependencies=[Depends(get_current_user), Depends(get_current_company)]` at the router level + the route function receives it as `company: CompanyId = Depends(get_current_company)` for use in `scoped_*()` calls.

**Router prefix:** `app.include_router(summaries_router, prefix="/api/{company}")`. FastAPI's path-parameter prefix injects `company` into every route in the router; the dependency reads it.

**Code:** See Code Example 3.

### Pattern 4: React Router v7 Nested `:company` Segment with Outlet (TENANT-05, TENANT-06)

**What:** Wrap `<TabbedDashboard />` in a parent `<Route path=":company" element={<CompanyScopedRoute />}>`. `<CompanyScopedRoute>` validates the param against `ACTIVE_COMPANIES`, redirects to `/seva/` on invalid slug, publishes the active company to Zustand, then renders `<Outlet />`. The nested tab routes (`<Route index>`, `<Route path="calendar">`, `<Route path="viral">`) inherit the param via `useParams<{company: string}>()` in child pages.

**Critical react-router-dom v7 detail:** `useParams<T>()` accepts a generic but returns `Readonly<Partial<T>>`. The TypeScript pattern is:

```tsx
const { company } = useParams<{ company: string }>();
// company is `string | undefined` — narrow before use
if (!company) return <Navigate to="/seva" replace />;
```

**Bookmark grace redirects (D-06):** Use sibling `<Route>` definitions before the `:company` wrapper. React Router matches in declaration order with longest-prefix-wins, so the explicit `/calendar`, `/viral`, `/queue`, `/agents/:slug` routes hit BEFORE the `:company` wrapper would interpret `calendar` as a tenant slug. Defensive — `<CompanyScopedRoute>` also redirects invalid slugs to `/seva/`.

**Code:** See Code Example 4.

### Pattern 5: Zustand `persist` Middleware — Adding `lastVisitedCompany` (TENANT-07)

**What:** The existing `useAppStore` (`frontend/src/stores/index.ts`) does NOT use `persist` middleware. Phase 9 adds a new slice `companySlice.ts` AND wraps the entire store with `persist({ partialize: (state) => ({ lastVisitedCompany: state.lastVisitedCompany }) })` so ONLY the company slot is persisted (the queue UI state stays in memory).

**Naming:** localStorage key per CONTEXT.md Claude's-discretion: planner picks; recommended `seva-mining-app-state-v3` (matches existing app-store naming convention).

**Code:** See Code Example 5.

### Pattern 6: TanStack Query Key Factory with Company Namespace (TENANT-09)

**What:** Centralized factory `frontend/src/api/queryKeys.ts` exports a single `queryKeys` object whose methods produce keys. All hooks (`useSummaries`, `useCalendar`, `useWeeklySweeps`) consume the factory. On tenant switch, `queryClient.clear()` evicts everything as defence-in-depth on top of the company-prefixed keys.

**Code:** See Code Example 6.

**Interaction with `staleTime` / `refetchOnWindowFocus`:** `queryClient.clear()` evicts ALL queries (every key + every observer) and immediately re-fires every active mount's `queryFn`. The existing `useSummaries` has `staleTime: 5 * 60 * 1000` and `refetchOnWindowFocus: false`. After `clear()`, the next mount re-fetches because the cache is empty — `staleTime` is irrelevant when there's no cached value. `refetchOnWindowFocus: false` only matters for already-cached queries. Net: `clear()` is the correct hammer; no surprising interaction.

### Pattern 7: APScheduler Per-Company Job Factory (TENANT-08)

**What:** Mirror `_make_daily_summary_job(engine)` (line 214 of `scheduler/worker.py`) as `_make_juno_daily_summary_job(engine, company_id)`. The factory closes over `company_id`; the inner `async def job()` calls `with_advisory_lock(conn, JOB_LOCK_IDS["juno_daily_summary"], "juno_daily_summary", run_juno_daily_summary)` where `run_juno_daily_summary` is a thin wrapper that calls a parameterized `_run_daily_summary_for_company('juno')`.

**5-min stagger:** `CronTrigger(hour="8,12", minute=5, timezone="America/Los_Angeles")` for Juno. Seva keeps `CronTrigger(hour="8,12", minute=0, ...)` unchanged. Note: CONTEXT.md D-01a says "07:00 PT" / "07:05 PT" — appears to be a documentation typo since the live Seva crons are at 08:00 + 12:00 PT (verified in `scheduler/worker.py:394`). Research assumption locks Juno at 08:05 + 12:05 PT (preserving twice-daily cadence + 5-min stagger). Planner should sanity-check with the operator if the discrepancy matters.

**Code:** See Code Example 8.

### Pattern 8: Juno Daily Summary Stub (TENANT-08, Phase 10 prep)

**What:** Phase 9 ships a minimal `scheduler/companies/juno/` package + a `run_juno_daily_summary()` entry point that writes a `daily_summaries` row with `company_id='juno'`, `status='partial'`, empty section markdown, and `agent_runs.notes` JSON containing `{"company_id": "juno", "phase_10_pending": true}`. Phase 10 fills the actual feeds/prompts.

**Code:** See Code Example 9.

### Anti-Patterns to Avoid

- **`select(DailySummary)` anywhere outside `backend/app/queries/scoped.py`** — CI grep gate fails the build. PITFALLS.md CRITICAL-1 / CRITICAL-2.
- **Middleware ContextVar tenant** — PITFALLS.md CRITICAL — leaks across asyncio Tasks when connection is reused. Use explicit `company_id` parameter on every helper instead. (Already locked by D-03 + D-04.)
- **`CREATE INDEX CONCURRENTLY` in Alembic 0014** — adds operational complexity (cannot run inside a transaction) without benefit at v3.0's row count. Plain `op.create_index` inside the migration transaction is correct.
- **Backfilling `company_id` in a separate `UPDATE` step before ALTER NOT NULL** — race window with the cron. Use `server_default='seva'` in the ADD COLUMN itself so the default applies atomically. PITFALLS.md HIGH-3.
- **Forgetting to mirror `models/` changes in `scheduler/models/`** — dual-model parity tests at `backend/tests/test_model_parity.py` catch this at test time.
- **Storing active tenant in Zustand as primary source** — URL + `useParams()` is canonical (D-07). Zustand mirrors for "last visited" only.
- **Adding `company_id` to query param `?company=juno` instead of path** — locked OUT by D-04.
- **Hardcoding the literal string `'amber-500'` in CompanySwitcher** — D-07 says use semantic tokens `--color-brand-accent[-hover/-subtle]` from Phase 8 D-05.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Tenant resolution from request | Custom middleware reading `request.url.path` | FastAPI path parameter + `Depends(get_current_company)` | Path param is auto-extracted; no string parsing |
| Persisted client state | localStorage + manual JSON serialize/deserialize on every read | `zustand/middleware.persist` (already in zustand 5.x package) | Battle-tested rehydration, SSR-safe |
| Query cache eviction on tenant switch | Manual key enumeration + per-key `removeQueries()` | `queryClient.clear()` | One call, evicts everything, safe |
| Alembic backfill race avoidance | Pause cron during migration + manual restart | `server_default='seva'` in ALTER COLUMN | Atomic — no operational coordination |
| Route param validation in React | Inline `if (company !== 'seva' && company !== 'juno')` everywhere | Single `<CompanyScopedRoute>` parent route | One validation site, naturally inherited |
| Multi-line "is this select pre-filtered" check | Custom AST parser | shell `grep -nE 'select\((DailySummary|CalendarItem|WeeklySweep)\)'` | Cheap, fast, runs in seconds |
| Composite FK across tenants | Composite PRIMARY KEY + composite FK | Application-layer assert in write path | Postgres FK doesn't support multi-col equality without subquery; v3.0 scale doesn't need it (PITFALLS.md MEDIUM-5) |
| Per-tenant cron registration loop | `for company in ACTIVE_COMPANIES: scheduler.add_job(...)` | Two explicit `scheduler.add_job()` calls (per D-01) | D-01 locked explicit per-company jobs |

**Key insight:** Phase 9 is overwhelmingly about *integration* — picking which existing pattern (Alembic style, scoped repository, FastAPI dependency, React Router nested, Zustand persist, APScheduler factory) to apply where. Almost nothing needs to be invented.

## Runtime State Inventory

Phase 9 is a rename/refactor phase (adding a column + scoping queries + restructuring routes). Per Step 2.5, here is the explicit inventory:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `daily_summaries`, `calendar_items`, `weekly_sweeps` rows in prod Neon DB (~60 rows total across all 3 tables at v3.0 scale) — all currently lack `company_id` | Alembic 0014 backfills `'seva'` via `server_default` on ADD COLUMN. Single transaction. No separate data migration needed. |
| Live service config | APScheduler jobs registered at worker startup via `build_scheduler()` — no DB-stored schedule that requires reconfiguration. `config` table (legacy v1.0) holds `morning_digest_schedule_hour` + `content_quality_threshold` + `content_recency_weight` but NONE of these are company-scoped. | None for the config table. Worker restart on Phase 9 deploy registers the new Juno job naturally. |
| OS-registered state | None — Railway containers are immutable; restart picks up new job registrations. | None. |
| Secrets/env vars | Shared across tenants in v3.0 per D-03 + Deferred Ideas. No new env vars in Phase 9. The single `ANTHROPIC_API_KEY` + `SERPAPI_API_KEY` continue to serve both tenants. | None. |
| Build artifacts | Frontend `dist/` rebuild on Vercel deploy; backend `__pycache__` rebuild on Railway deploy. No stale package metadata (no `egg-info`, no `node_modules` cache concerns). | None — standard deploy refreshes everything. |

**Special note — TanStack Query cache in active browser sessions:** When the v3.0 deploy goes live, any currently-open browser tab will have an old TanStack cache keyed by `['summaries', limit]` (no `company_id` slot). After the deploy, hard-refresh the tab triggers `App.tsx` to re-mount with the new code paths. Any pre-existing data in the cache becomes stale and is evicted on next mount. The Zustand `localStorage` JWT token survives (token auth unaffected by v3.0). **No action required** — the operator simply refreshes once.

## Common Pitfalls

### Pitfall 1: Alembic 0014 backfill race (CRITICAL — PITFALLS.md HIGH-3)

**What goes wrong:** Cron fires `daily_summary` at 08:00 PT mid-deploy, writing a row with `company_id=NULL`. Then `ALTER COLUMN ... SET NOT NULL` fails because at least one row violates the constraint.

**Why it happens:** Naive migrations do `ADD COLUMN NULL` → `UPDATE backfill` → `ALTER SET NOT NULL` in three steps. Race window between step 1 and step 3.

**How to avoid:** ADD COLUMN with `server_default='seva'` AND `nullable=False` in ONE statement. Postgres applies the default to existing rows during ALTER, so the column is NEVER NULL. Any cron INSERT during the deploy gets `'seva'` automatically.

**Warning signs:**
- Alembic log shows `WARNING: ... contains null values` — migration aborted.
- Post-deploy `SELECT count(*) FROM daily_summaries WHERE company_id IS NULL` > 0.

### Pitfall 2: Forgot to use `scoped_*()` helper (CRITICAL — PITFALLS.md CRITICAL-2)

**What goes wrong:** A new route (or a refactor of an existing route) does `select(DailySummary).order_by(...)` directly, omitting the `company_id` filter. Cross-tenant data leaks to whichever tenant's page mounted the query first.

**Why it happens:** Single-tenant muscle memory; copy-paste from older code.

**How to avoid:**
1. CI grep gate at `scripts/verify-tenant-isolation.sh` blocks any raw `select(DailySummary|CalendarItem|WeeklySweep)` outside `backend/app/queries/scoped.py`.
2. Optional: SQLAlchemy event listener (see Pattern 2 defence-in-depth).
3. Required: `test_multitenant_isolation.py` parametrized over `('seva', 'juno')` asserting per-tenant read endpoints return only the tenant's rows.

**Warning signs:**
- CI red on the grep step.
- Test failure in `test_multitenant_isolation.py` showing cross-tenant rows in response.
- Manual smoke test: switch tenants in dashboard, see Juno headlines in Seva card.

### Pitfall 3: react-router-dom v7 `useParams` type narrowing (MEDIUM)

**What goes wrong:** `const { company } = useParams<{ company: string }>()` returns `string | undefined`. If a developer destructures and passes `company` to `scoped_summaries(company)` without the `if (!company)` check, TypeScript may allow it (depending on `strict` config) and the runtime call fails with a 404 or undefined behavior.

**Why it happens:** v7 doesn't narrow params even when the parent route has the `:company` segment (because hooks can be called anywhere).

**How to avoid:** Single chokepoint — `<CompanyScopedRoute>` validates + redirects on invalid; child pages always assume non-undefined `company`. Pattern: child pages do `const { company } = useParams<{ company: string }>(); if (!company) throw new Error('...');` as a defensive assert. Or use a custom hook `useCompany()` that throws.

### Pitfall 4: Composite index not used by Postgres (MEDIUM — PITFALLS.md HIGH-4)

**What goes wrong:** Migration 0014 creates `ix_daily_summaries_company_generated` on `(company_id, generated_at DESC)`. But a router query `WHERE generated_at > X AND company_id = 'seva'` may not use it if the query planner picks a different index (e.g. an existing `ix_daily_summaries_generated_at`).

**Why it happens:** Postgres picks the index by cost estimate; at v3.0's low row count (~60 rows total) the planner may sequential-scan anyway.

**How to avoid:** Drop the old `ix_daily_summaries_generated_at` in 0014 (replace, don't accumulate). Run `EXPLAIN ANALYZE` on the post-migration query to confirm `Index Cond: company_id = 'seva' AND generated_at < ...`. The composite index becomes meaningful at >10K rows — the goal in v3.0 is to teach the right habit, not chase performance.

### Pitfall 5: `dual-model parity` drift on `company_id` (HIGH)

**What goes wrong:** Engineer adds `company_id` to `backend/app/models/daily_summary.py` but forgets `scheduler/models/daily_summary.py`. Cron writes succeed but the column is unknown to the scheduler-side ORM; some queries silently lose the column.

**Why it happens:** Two separate Python processes, no shared module — established convention from Phase B.

**How to avoid:** `backend/tests/test_model_parity.py` (existing) already enforces parity for `CalendarItem` and `WeeklySweep`. Phase 9 W1 must EXTEND the parity tests to cover `DailySummary` (currently absent — parity tests only cover the two Phase 5 tables). Add `test_daily_summary_parity` mirroring the existing pattern.

### Pitfall 6: APScheduler `args=[company_id]` vs the `with_advisory_lock` shape (MEDIUM)

**What goes wrong:** The existing `_make_daily_summary_job(engine)` factory creates a no-arg `async def job()` closure. Trying to pass `args=[company_id]` to `scheduler.add_job(_make_juno_daily_summary_job(engine, 'juno'), ...)` would attempt to inject `company_id` into the no-arg `job()`, raising `TypeError`.

**Why it happens:** Confusion between factory-closure pattern and APScheduler's `args=` pattern.

**How to avoid:** Use the factory closure pattern (CONTEXT.md D-01 explicitly says "each Juno job gets its own `add_job(..., args=[company_id])` factory mirroring `_make_daily_summary_job`"). The factory CLOSES OVER `company_id` rather than relying on APScheduler's `args=`. See Code Example 8 — the factory takes `engine, company_id`, and the inner `async def job()` calls `run_juno_daily_summary` with no args (the function internally uses `'juno'` since this factory was made for Juno).

**Alternative shape:** Single parameterized factory `_make_daily_summary_for_company_job(engine, company_id)` that returns a closure. Cleaner if planner anticipates a 3rd tenant.

## Code Examples

### Code Example 1: Alembic 0014 — expand/contract with backfill (TENANT-01, TENANT-02)

```python
# backend/alembic/versions/0014_add_company_id.py
"""Multi-tenant foundation — add company_id to 3 tenant-scoped tables.

Phase 9 (v3.0). Expand step of expand/contract pattern (PITFALLS.md HIGH-3):
- ADD COLUMN with server_default='seva' makes existing rows + concurrent
  cron writes both default to 'seva' atomically. No backfill UPDATE needed.
- DROP DEFAULT happens in a follow-up v3.0.1 migration once all callers
  pass company_id explicitly.

Revision ID: 0014
Revises: 0013
Create Date: 2026-05-19
"""
import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. ADD COLUMN with server_default='seva' AND nullable=False in one ALTER.
    #    Postgres applies the default to all existing rows during the ALTER.
    #    Any cron INSERT during the deploy window also gets 'seva' (HIGH-3).
    for table in ("daily_summaries", "calendar_items", "weekly_sweeps"):
        op.add_column(
            table,
            sa.Column(
                "company_id",
                sa.String(length=20),
                nullable=False,
                server_default="seva",
            ),
        )

    # 2. CHECK constraint enumerating valid tenants (D-03 — hardcoded list).
    for table in ("daily_summaries", "calendar_items", "weekly_sweeps"):
        op.create_check_constraint(
            f"ck_{table}_company_id",
            table,
            "company_id IN ('seva', 'juno')",
        )

    # 3. Composite indexes — company_id LEADS every multi-tenant index.
    #    Drop old single-column indexes that no longer match the query shape.

    # daily_summaries: replace ix_daily_summaries_generated_at with composite
    op.drop_index("ix_daily_summaries_generated_at", table_name="daily_summaries")
    op.create_index(
        "ix_daily_summaries_company_generated",
        "daily_summaries",
        ["company_id", sa.text("generated_at DESC")],
    )

    # calendar_items: replace uq_calendar_items_date with composite UNIQUE
    op.drop_constraint("uq_calendar_items_date", "calendar_items", type_="unique")
    op.create_unique_constraint(
        "uq_calendar_items_company_date",
        "calendar_items",
        ["company_id", "date"],
    )
    op.create_index(
        "ix_calendar_items_company_date",
        "calendar_items",
        ["company_id", "date"],
    )

    # weekly_sweeps: replace ix_weekly_sweeps_generated_at with composite
    op.drop_index("ix_weekly_sweeps_generated_at", table_name="weekly_sweeps")
    op.create_index(
        "ix_weekly_sweeps_company_generated",
        "weekly_sweeps",
        ["company_id", sa.text("generated_at DESC")],
    )


def downgrade() -> None:
    # Reverse exact order. After downgrade, all rows lose the company_id
    # column — Juno rows become indistinguishable from Seva rows. Operator
    # must manually DELETE WHERE company_id='juno' BEFORE downgrade if a
    # clean v2.1 rollback is desired (documented in PR description).
    op.drop_index("ix_weekly_sweeps_company_generated", table_name="weekly_sweeps")
    op.create_index(
        "ix_weekly_sweeps_generated_at",
        "weekly_sweeps",
        [sa.text("generated_at DESC")],
    )

    op.drop_index("ix_calendar_items_company_date", table_name="calendar_items")
    op.drop_constraint(
        "uq_calendar_items_company_date", "calendar_items", type_="unique"
    )
    op.create_unique_constraint(
        "uq_calendar_items_date", "calendar_items", ["date"]
    )

    op.drop_index("ix_daily_summaries_company_generated", table_name="daily_summaries")
    op.create_index(
        "ix_daily_summaries_generated_at", "daily_summaries", ["generated_at"]
    )

    for table in ("weekly_sweeps", "calendar_items", "daily_summaries"):
        op.drop_constraint(f"ck_{table}_company_id", table, type_="check")
        op.drop_column(table, "company_id")
```

**Note on `CREATE INDEX CONCURRENTLY`:** Not used here. At v3.0's row counts (~60 rows total across 3 tables), the inline `op.create_index` inside the Alembic transaction completes in microseconds. CONCURRENTLY adds operational complexity (cannot run inside a transaction; requires explicit transaction-per-statement handling) without benefit. Document the threshold in 0014's docstring: "CONCURRENTLY threshold ~100K rows; revisit at v3.x+."

### Code Example 2: Scoped query helpers + router integration (TENANT-03, TENANT-04)

```python
# backend/app/queries/__init__.py
from app.queries.scoped import (
    scoped_calendar,
    scoped_summaries,
    scoped_weekly_sweeps,
)

__all__ = ["scoped_summaries", "scoped_calendar", "scoped_weekly_sweeps"]


# backend/app/queries/scoped.py
"""Tenant-scoped query helpers (TENANT-03).

Every router that touches daily_summaries, calendar_items, or weekly_sweeps
MUST start its query from a scoped_*() helper. CI grep gate at
scripts/verify-tenant-isolation.sh blocks any raw select(DailySummary|
CalendarItem|WeeklySweep) outside this module + __init__.py re-exports.
"""
from typing import Literal

from sqlalchemy import Select, select

from app.models.calendar_item import CalendarItem
from app.models.daily_summary import DailySummary
from app.models.weekly_sweep import WeeklySweep

CompanyId = Literal["seva", "juno"]


def scoped_summaries(company_id: CompanyId) -> Select:
    """SELECT statement pre-filtered to a single tenant's daily_summaries.

    Callers add .order_by()/.limit()/.where() and execute via AsyncSession.
    """
    return select(DailySummary).where(DailySummary.company_id == company_id)


def scoped_calendar(company_id: CompanyId) -> Select:
    return select(CalendarItem).where(CalendarItem.company_id == company_id)


def scoped_weekly_sweeps(company_id: CompanyId) -> Select:
    return select(WeeklySweep).where(WeeklySweep.company_id == company_id)
```

```python
# backend/app/routers/summaries.py — MODIFIED for Phase 9
"""GET /api/{company}/summaries — multi-tenant daily summary feed."""
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_company, get_current_user
from app.models.daily_summary import DailySummary
from app.queries.scoped import scoped_summaries
from app.schemas.daily_summary import SummaryCardResponse, SummaryFeedResponse

router = APIRouter(
    prefix="/summaries",
    tags=["summaries"],
    dependencies=[Depends(get_current_user)],  # router-level auth (unchanged)
)


@router.get("", response_model=SummaryFeedResponse)
async def list_summaries(
    limit: int = Query(60, ge=1, le=120),
    db: AsyncSession = Depends(get_db),
    company: Literal["seva", "juno"] = Depends(get_current_company),
) -> SummaryFeedResponse:
    """Return up to `limit` summaries for the active tenant, newest first."""
    stmt = (
        scoped_summaries(company)
        .order_by(DailySummary.generated_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()
    cards = [SummaryCardResponse.model_validate(r) for r in rows]
    return SummaryFeedResponse(summaries=cards, total=len(cards))
```

### Code Example 3: `get_current_company` FastAPI dependency (TENANT-04)

```python
# backend/app/companies/__init__.py
"""Backend-side tenant identity. Source of truth: Python Literal (D-03)."""
from typing import Literal

CompanyId = Literal["seva", "juno"]

ACTIVE_COMPANIES: tuple[CompanyId, ...] = ("seva", "juno")
```

```python
# backend/app/dependencies.py — ADD this function
from fastapi import HTTPException, Path
from typing import Literal

from app.companies import ACTIVE_COMPANIES, CompanyId


async def get_current_company(
    company: str = Path(..., pattern=r"^[a-z][a-z0-9-]{1,19}$"),
) -> CompanyId:
    """Validate :company path parameter against ACTIVE_COMPANIES (D-04, D-03).

    Returns the company slug as a typed Literal so downstream callers
    get type-narrowed access (CompanyId, not raw str).
    """
    if company not in ACTIVE_COMPANIES:
        raise HTTPException(status_code=404, detail=f"Unknown company: {company}")
    return company  # type: ignore[return-value]
```

```python
# backend/app/main.py — MODIFIED router registration
# v3.0: tenant-scoped routers gain /api/{company} prefix.
app.include_router(summaries_router, prefix="/api/{company}")
app.include_router(calendar_router, prefix="/api/{company}")
app.include_router(weekly_sweeps_router, prefix="/api/{company}")
# Non-tenanted routers stay at /api/...:
app.include_router(auth_router)
app.include_router(settings_router)
# digests, agent_runs, etc. — same (not tenant-scoped)
```

### Code Example 4: React Router v7 nested `:company` + Outlet + grace redirects (TENANT-05, TENANT-06)

```tsx
// frontend/src/App.tsx — MODIFIED for Phase 9
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { ProtectedRoute } from '@/components/layout/ProtectedRoute'
import { AppShell } from '@/components/layout/AppShell'
import { TabbedDashboard } from '@/components/layout/TabbedDashboard'
import { CompanyScopedRoute } from '@/components/layout/CompanyScopedRoute'
import { LoginPage } from '@/pages/LoginPage'
import { DigestPage } from '@/pages/DigestPage'
import { SettingsPage } from '@/pages/SettingsPage'
import { SummaryFeedPage } from '@/pages/SummaryFeedPage'
import ContentCalendarPage from '@/pages/ContentCalendarPage'
import WeeklyViralSweeperPage from '@/pages/WeeklyViralSweeperPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<ProtectedRoute />}>
          <Route element={<AppShell />}>

            {/* v3.0: tenant-scoped 3-tab surface (TENANT-05) */}
            <Route path=":company" element={<CompanyScopedRoute />}>
              <Route element={<TabbedDashboard />}>
                <Route index element={<SummaryFeedPage />} />
                <Route path="calendar" element={<ContentCalendarPage />} />
                <Route path="viral" element={<WeeklyViralSweeperPage />} />
              </Route>
            </Route>

            {/* Bare / → /seva/ (D-05 — hardcoded, NOT last-visited) */}
            <Route index element={<Navigate to="/seva" replace />} />

            {/* Bookmark grace redirects (D-06) — declared BEFORE :company match */}
            {/* Note: React Router matches all routes; explicit paths win over :company match */}
            <Route path="/calendar" element={<Navigate to="/seva/calendar" replace />} />
            <Route path="/viral" element={<Navigate to="/seva/viral" replace />} />
            <Route path="/queue" element={<Navigate to="/seva" replace />} />
            <Route path="/agents/:slug" element={<Navigate to="/seva" replace />} />

            {/* Non-tenanted retained surfaces (D-06 — these stay at root) */}
            <Route path="/digest" element={<DigestPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Route>
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
```

```tsx
// frontend/src/components/layout/CompanyScopedRoute.tsx — NEW
import { useEffect } from 'react'
import { Navigate, Outlet, useParams } from 'react-router-dom'
import { useAppStore } from '@/stores'

const ACTIVE_COMPANIES = ['seva', 'juno'] as const
type CompanyId = (typeof ACTIVE_COMPANIES)[number]

function isCompanyId(value: string | undefined): value is CompanyId {
  return value !== undefined && (ACTIVE_COMPANIES as readonly string[]).includes(value)
}

/**
 * Wrapper route at /:company — validates the param, publishes to Zustand
 * for non-routed component reads, and renders <Outlet /> for nested tabs.
 *
 * Pitfall #3 mitigation: this is the single chokepoint where 'company' is
 * narrowed from string|undefined to CompanyId. Nested pages get a guarantee
 * the param is valid.
 */
export function CompanyScopedRoute() {
  const { company } = useParams<{ company: string }>()
  const setLastVisitedCompany = useAppStore((s) => s.setLastVisitedCompany)

  useEffect(() => {
    if (isCompanyId(company)) {
      setLastVisitedCompany(company)
    }
  }, [company, setLastVisitedCompany])

  if (!isCompanyId(company)) {
    // Invalid slug — graceful redirect to /seva/ (D-06)
    return <Navigate to="/seva" replace />
  }

  return <Outlet />
}
```

```tsx
// frontend/src/pages/SummaryFeedPage.tsx — MODIFIED snippet
import { useParams } from 'react-router-dom'
import { useSummaries } from '@/api/summaries'

export function SummaryFeedPage() {
  // useParams returns Readonly<Partial<{company: string}>> in v7.
  // CompanyScopedRoute already validated, so '!' is safe here.
  const { company } = useParams<{ company: string }>()
  const companyId = company as 'seva' | 'juno'  // narrowed by parent route

  const { data } = useSummaries(companyId, 60)
  // ... render
}
```

### Code Example 5: Zustand persist + companySlice (TENANT-07)

```ts
// frontend/src/stores/slices/companySlice.ts — NEW
export type CompanyId = 'seva' | 'juno'

export interface CompanySlice {
  lastVisitedCompany: CompanyId
  setLastVisitedCompany: (c: CompanyId) => void
}

export function createCompanySlice(
  set: (fn: (state: CompanySlice) => Partial<CompanySlice>) => void
): CompanySlice {
  return {
    lastVisitedCompany: 'seva',  // default before any visit
    setLastVisitedCompany: (c) => set(() => ({ lastVisitedCompany: c })),
  }
}
```

```ts
// frontend/src/stores/index.ts — MODIFIED
import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { createQueueUiSlice, type QueueUiSlice } from './slices/queueUiSlice'
import { createAuthSlice, type AuthSlice } from './slices/authSlice'
import { createCompanySlice, type CompanySlice } from './slices/companySlice'

type AppStore = QueueUiSlice & AuthSlice & CompanySlice

export const useAppStore = create<AppStore>()(
  persist(
    (set) => ({
      ...createQueueUiSlice(set as Parameters<typeof createQueueUiSlice>[0]),
      ...createAuthSlice(set as Parameters<typeof createAuthSlice>[0]),
      ...createCompanySlice(set as Parameters<typeof createCompanySlice>[0]),
    }),
    {
      name: 'seva-mining-app-state-v3',  // locked per CONTEXT.md Claude's-discretion
      // Only persist the company slot — queue UI + auth stay in memory
      // (auth has its own localStorage write inside authSlice; no double-write)
      partialize: (state) => ({
        lastVisitedCompany: state.lastVisitedCompany,
      }),
    }
  )
)
```

### Code Example 6: TanStack queryKey factory + invalidation (TENANT-09)

```ts
// frontend/src/api/queryKeys.ts — NEW
/**
 * Centralized TanStack Query key factory (TENANT-09).
 *
 * Every multi-tenant query MUST go through these helpers so the cache
 * never accidentally serves Juno data to a Seva-tab observer (or vice
 * versa). Defence-in-depth on top of company-prefixed URLs.
 *
 * The `as const` makes the tuple literal so TanStack's structural key
 * equality is sound.
 */
export type CompanyId = 'seva' | 'juno'

export const queryKeys = {
  summaries: (companyId: CompanyId, limit: number) =>
    ['summaries', companyId, limit] as const,

  calendar: (companyId: CompanyId, start: string, end: string) =>
    ['calendar', companyId, start, end] as const,

  weeklySweeps: (companyId: CompanyId, limit: number) =>
    ['weekly-sweeps', companyId, limit] as const,
}
```

```ts
// frontend/src/api/summaries.ts — MODIFIED for Phase 9
import { useQuery } from '@tanstack/react-query'
import { apiFetch } from './client'
import { queryKeys, type CompanyId } from './queryKeys'

export async function getSummaries(
  companyId: CompanyId,
  limit = 60,
): Promise<SummaryFeedResponse> {
  return apiFetch<SummaryFeedResponse>(
    `/api/${companyId}/summaries?limit=${limit}`,
  )
}

export function useSummaries(companyId: CompanyId, limit = 60) {
  return useQuery({
    queryKey: queryKeys.summaries(companyId, limit),
    queryFn: () => getSummaries(companyId, limit),
    refetchInterval: 5 * 60 * 1000,
    refetchOnWindowFocus: false,
    staleTime: 5 * 60 * 1000,
  })
}
```

```tsx
// frontend/src/components/layout/CompanySwitcher.tsx — NEW
import { useNavigate, useParams, useLocation } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'

const COMPANIES = [
  { id: 'seva', label: 'Seva' },
  { id: 'juno', label: 'Juno' },
] as const

export function CompanySwitcher() {
  const { company: active } = useParams<{ company: string }>()
  const navigate = useNavigate()
  const location = useLocation()
  const queryClient = useQueryClient()

  function switchTo(next: 'seva' | 'juno') {
    if (next === active) return
    // Preserve current sub-path (D-07): /seva/calendar → /juno/calendar
    const subPath = location.pathname.replace(/^\/(seva|juno)/, '')
    // Defence-in-depth (D-08): clear TanStack cache on switch
    queryClient.clear()
    navigate(`/${next}${subPath}`)
  }

  return (
    <div
      role="tablist"
      className="inline-flex rounded-md border border-zinc-800 overflow-hidden"
    >
      {COMPANIES.map((c) => {
        const isActive = active === c.id
        return (
          <button
            key={c.id}
            role="tab"
            aria-selected={isActive}
            onClick={() => switchTo(c.id)}
            className={
              isActive
                ? 'px-3 py-1 text-sm border-brand-accent text-brand-accent ' +
                  'bg-brand-accent-subtle transition-colors'
                : 'px-3 py-1 text-sm text-zinc-400 hover:text-zinc-100 transition-colors'
            }
          >
            {c.label}
          </button>
        )
      })}
    </div>
  )
}
```

### Code Example 7: CI grep gate (Claude's discretion → recommended) (TENANT-03)

```bash
#!/usr/bin/env bash
# scripts/verify-tenant-isolation.sh
# Phase 9 TENANT-03 — CI grep gate enforcing the scoped_*() helper contract.
#
# PASS: every select() against a tenant-scoped Model is INSIDE
#       backend/app/queries/scoped.py (or its __init__.py re-export).
# FAIL: any raw select(DailySummary | CalendarItem | WeeklySweep) elsewhere.
#
# Mirrors v2.1 Phase 8 grep verification scripts
# (scripts/verify-ui-04-hover-transitions.sh pattern).
set -euo pipefail
cd /Users/matthewnelson/seva-mining

echo "=== TENANT-03 scoped helper grep gate ==="

# Scope: backend/app (router + service code) and scheduler/agents (cron code).
# Tests are excluded — they may legitimately construct ad-hoc selects in
# fixtures using .execution_options(skip_tenant_check=True) for negative
# assertions.
TARGETS=(
  "backend/app"
  "scheduler/agents"
)

# The scoped_*() helpers are the ONLY allowed sites for raw select(Model).
ALLOWED=(
  "backend/app/queries/scoped.py"
  "backend/app/queries/__init__.py"
)

PATTERN='select\((DailySummary|CalendarItem|WeeklySweep)[\)]'

violations=$(grep -rnE "$PATTERN" "${TARGETS[@]}" 2>/dev/null || true)

# Strip allowed paths from the result
filtered="$violations"
for path in "${ALLOWED[@]}"; do
  filtered=$(echo "$filtered" | grep -v "^$path:" || true)
done

if [ -n "$filtered" ]; then
  echo "FAIL — raw select() against tenant-scoped Model found outside scoped helpers:"
  echo "$filtered"
  echo ""
  echo "Fix: replace with scoped_summaries(company_id) / scoped_calendar(company_id)"
  echo "     / scoped_weekly_sweeps(company_id) from backend/app/queries/scoped.py"
  exit 1
fi

echo "PASS — all tenant-scoped selects routed through queries/scoped.py"
```

**Note on `select(DailySummary.id)` and `select(DailySummary.raw_sources_jsonb)`:** The existing `scheduler/agents/daily_summary.py` has TWO call sites at lines 146 and 521 that select specific columns (not the full model). These are technically tenant-scoped queries that the planner must update in W2 to use `scoped_summaries(company_id)` (with `.with_only_columns(...)` or `.add_columns(...)` for the column-projection cases). The grep pattern above catches `select(DailySummary)` but the planner may want to tighten the regex to also catch `select(DailySummary\.` to flag column-specific selects. **Recommended regex (final):** `select\((DailySummary|CalendarItem|WeeklySweep)[\)\.]`.

### Code Example 8: APScheduler per-company job factory (TENANT-08)

```python
# scheduler/worker.py — MODIFIED JOB_LOCK_IDS and build_scheduler()

# 1. Extend JOB_LOCK_IDS — Phase 9 reserves both 1020 and 1021 per D-01.
JOB_LOCK_IDS: dict[str, int] = {
    "midday_digest": 1005,
    "daily_summary": 1017,
    "daily_summary_prune": 1018,
    "weekly_sweeper": 1019,
    # v3.0 Phase 9 — D-01: per-company jobs with explicit lock IDs.
    # 1020 is REGISTERED in build_scheduler() below (juno_daily_summary).
    # 1021 is RESERVED only — registration deferred to v3.1+ when Juno
    # Weekly Sweeper lands. OPS-02 assertion still validates uniqueness.
    "juno_daily_summary": 1020,
    "juno_weekly_sweeper": 1021,
}

# (OPS-02 assertion line 110 unchanged — still works.)


# 2. Add the Juno daily_summary factory mirroring _make_daily_summary_job.
def _make_juno_daily_summary_job(engine):
    """Create the juno_daily_summary job callback (advisory-lock wrapped).

    v3.0 Phase 9 (TENANT-08). Mirrors _make_daily_summary_job exactly,
    swapping the lock ID and the inner entry point. The Juno entry point
    is registered as a stub in Phase 9 (writes status='partial' row);
    Phase 10 fills the actual feeds/prompts/Sonnet call.

    The factory CLOSES OVER the engine. company_id='juno' is baked into
    the entry point name; no APScheduler args= injection needed (the
    closure pattern matches D-01's "factory mirroring _make_daily_summary_job").
    """

    async def job():
        async with engine.connect() as conn:
            from agents.daily_summary import run_juno_daily_summary  # lazy
            await with_advisory_lock(
                conn,
                JOB_LOCK_IDS["juno_daily_summary"],
                "juno_daily_summary",
                run_juno_daily_summary,
            )

    return job


# 3. Register in build_scheduler() — 5-min stagger after Seva fires.
async def build_scheduler(engine) -> AsyncIOScheduler:
    # ... existing setup ...

    # Seva daily_summary — unchanged (08:00 + 12:00 PT).
    scheduler.add_job(
        _make_daily_summary_job(engine),
        trigger=CronTrigger(hour="8,12", minute=0, timezone="America/Los_Angeles"),
        id="daily_summary",
        name="Daily Summary — Seva — 08:00 + 12:00 PT",
    )

    # v3.0 Phase 9 — Juno daily_summary at 08:05 + 12:05 PT (5-min stagger).
    # Note: CONTEXT.md D-01a writes "07:00 PT" + "07:05 PT" but the existing
    # Seva cron is at hour="8,12" — research interprets D-01a as
    # "preserve cadence, stagger by 5 min" → 08:05 + 12:05 PT for Juno.
    # Planner should sanity-check with operator if the discrepancy matters.
    scheduler.add_job(
        _make_juno_daily_summary_job(engine),
        trigger=CronTrigger(hour="8,12", minute=5, timezone="America/Los_Angeles"),
        id="juno_daily_summary",
        name="Daily Summary — Juno — 08:05 + 12:05 PT",
    )

    # daily_summary_prune unchanged (Phase 9 does NOT add a Juno prune cron;
    # the existing prune deletes rows older than 30 days regardless of
    # company_id; v3.0.1 may add per-company prune if data growth diverges).
    # ... rest unchanged ...
```

**Important: parity test impact.** Adding `juno_daily_summary` to `JOB_LOCK_IDS` invalidates any hardcoded count assertion in `scheduler/tests/test_worker.py` (per STATE.md note: "[Phase 07] bumped 3 pre-existing test_worker.py assertions ... pattern: any new job registration in build_scheduler MUST update test_retired_crons_absent_from_job_lock_ids + test_scheduler_registers_N_jobs + test_build_scheduler_omits_v1_sub_agent_crons"). Phase 9 W2 plan must include this test bump.

### Code Example 9: Juno daily_summary stub package + entry point (TENANT-08)

```python
# scheduler/companies/__init__.py — NEW
"""Scheduler-side tenant config (D-03 + D-05 from ARCHITECTURE.md).

Mirrors backend/app/companies/__init__.py's ACTIVE_COMPANIES Literal.
"""
from typing import Literal

CompanyId = Literal["seva", "juno"]

ACTIVE_COMPANIES: tuple[CompanyId, ...] = ("seva", "juno")


# scheduler/companies/juno/__init__.py — NEW
"""Juno tenant config (Phase 9 stub — Phase 10 fills the lists).

Phase 9 ships a minimal stub so the Juno daily_summary cron can fire and
write a status='partial' daily_summaries row. Phase 10 replaces the empty
lists with real defence RSS feeds + SerpAPI queries + Sonnet system prompt.
"""
from .feeds import JUNO_DEFENCE_FEEDS
from .prompts import DEFENCE_NEWS_SYSTEM_PROMPT
from .serpapi import JUNO_SERPAPI_QUERIES


# scheduler/companies/juno/feeds.py — NEW (stub)
"""Juno defence RSS feeds — Phase 10 deliverable (currently empty)."""
JUNO_DEFENCE_FEEDS: list[tuple[str, str]] = []  # (source_name, feed_url) tuples


# scheduler/companies/juno/serpapi.py — NEW (stub)
"""Juno SerpAPI google_news queries — Phase 10 deliverable."""
JUNO_SERPAPI_QUERIES: list[str] = []  # query strings


# scheduler/companies/juno/prompts.py — NEW (stub)
"""Juno Sonnet system prompt — Phase 10 designs from scratch (DEF-03)."""
DEFENCE_NEWS_SYSTEM_PROMPT: str = (
    "STUB — Phase 10 will design the defence-industry Sonnet system prompt "
    "from scratch per DEF-03. Do not use this prompt for real synthesis."
)
```

```python
# scheduler/agents/daily_summary.py — ADD at module bottom (Phase 9)
async def run_juno_daily_summary() -> None:
    """Phase 9 stub entry point — writes a status='partial' Juno row.

    Phase 10 will replace this with the full ingestion + Sonnet synthesis
    pipeline. For Phase 9, the goal is "one APScheduler fire produces a
    Juno daily_summaries row" so the multi-tenant cron topology is wired
    end-to-end before any real Juno content lands.

    Mirrors run_daily_summary() shape but skips the gold/ontario sections.
    """
    now_utc = datetime.now(timezone.utc)
    now_la = now_utc.astimezone(LA_TZ)
    period_label = _derive_period_label(now_la)

    # Idempotency — per-company check (uses scoped_summaries equivalent)
    async with AsyncSessionLocal() as session:
        cutoff = now_utc - timedelta(minutes=IDEMPOTENCY_WINDOW_MIN)
        stmt = (
            select(DailySummary.id)
            .where(DailySummary.company_id == "juno")
            .where(DailySummary.generated_at >= cutoff)
            .where(DailySummary.status.in_(["running", "completed"]))
            .limit(1)
        )
        result = await session.execute(stmt)
        if result.scalar_one_or_none() is not None:
            logger.info("juno_daily_summary idempotency_skip period=%s", period_label)
            return

    # Insert agent_runs row (status='running')
    agent_run = AgentRun(
        agent_name="juno_daily_summary",
        started_at=now_utc,
        items_found=0,
        items_queued=0,
        items_filtered=0,
        status="running",
        notes=json.dumps({"company_id": "juno", "phase_10_pending": True}),
    )
    async with AsyncSessionLocal() as session:
        session.add(agent_run)
        await session.commit()
        await session.refresh(agent_run)

    try:
        # Write the Juno daily_summary row with empty sections + partial status.
        # Phase 10 will populate gold_news_md (defence_news_md semantically),
        # ontario_law_md (canadian_procurement_md semantically), and
        # ontario_stats_md (world_events_md semantically) per DEF-08.
        async with AsyncSessionLocal() as session:
            summary_row = DailySummary(
                company_id="juno",
                generated_at=now_utc,
                period_label=period_label,
                gold_news_md=None,
                ontario_law_md=None,
                ontario_stats_md=None,
                raw_sources_jsonb={
                    "company_id": "juno",
                    "phase_10_pending": True,
                    "note": "Juno Defence News Funnel ships in Phase 10",
                },
                status="partial",
                error_text="Juno content pipeline pending — Phase 10",
                agent_run_id=agent_run.id,
            )
            session.add(summary_row)
            await session.commit()

        # Update agent_run to completed
        async with AsyncSessionLocal() as session:
            fresh = await session.get(AgentRun, agent_run.id)
            if fresh is not None:
                fresh.status = "completed"
                fresh.ended_at = datetime.now(timezone.utc)
                fresh.notes = json.dumps({"company_id": "juno", "phase_10_pending": True})
                await session.commit()

    except Exception as exc:
        logger.exception("juno_daily_summary failed: %s", exc)
        async with AsyncSessionLocal() as session:
            fresh = await session.get(AgentRun, agent_run.id)
            if fresh is not None:
                fresh.status = "failed"
                fresh.ended_at = datetime.now(timezone.utc)
                fresh.errors = [f"{type(exc).__name__}: {str(exc)[:200]}"]
                await session.commit()
```

### Code Example 10: Multi-tenant isolation test fixture (TENANT-10)

```python
# backend/tests/test_multitenant_isolation.py — NEW
"""Cross-tenant leak detection (TENANT-10).

Creates rows for BOTH tenants, then asserts each tenant's API returns
ONLY its own rows. Parametrized over ('seva', 'juno') so symmetry is
explicit. Catches any router that bypasses scoped_*() helpers.

Sources: PITFALLS.md CRITICAL-2 — "Query without company_id filter is
the #1 multi-tenancy bug"; CONTEXT.md TENANT-10.
"""
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.calendar_item import CalendarItem
from app.models.daily_summary import DailySummary
from app.models.weekly_sweep import WeeklySweep


@pytest_asyncio.fixture
async def both_tenant_rows(async_db_session: AsyncSession):
    """Seed one row per tenant per multi-tenant table."""
    now = datetime.now(timezone.utc)
    rows = [
        DailySummary(
            id=uuid.uuid4(),
            company_id="seva",
            generated_at=now,
            period_label="08:00 PT",
            gold_news_md="Seva gold news",
            raw_sources_jsonb={"company": "seva"},
            status="completed",
            created_at=now,
        ),
        DailySummary(
            id=uuid.uuid4(),
            company_id="juno",
            generated_at=now,
            period_label="08:05 PT",
            gold_news_md=None,
            raw_sources_jsonb={"company": "juno"},
            status="partial",
            created_at=now,
        ),
        CalendarItem(
            id=uuid.uuid4(),
            company_id="seva",
            date=now.date(),
            notes_md="Seva calendar item",
            created_at=now,
            updated_at=now,
        ),
        CalendarItem(
            id=uuid.uuid4(),
            company_id="juno",
            date=now.date(),
            notes_md="Juno calendar item",
            created_at=now,
            updated_at=now,
        ),
        WeeklySweep(
            id=uuid.uuid4(),
            company_id="seva",
            generated_at=now,
            week_start=now.date(),
            week_end=now.date(),
            status="completed",
        ),
        WeeklySweep(
            id=uuid.uuid4(),
            company_id="juno",
            generated_at=now,
            week_start=now.date(),
            week_end=now.date(),
            status="partial",
        ),
    ]
    for row in rows:
        async_db_session.add(row)
    await async_db_session.commit()
    return rows


@pytest.mark.parametrize("company", ["seva", "juno"])
@pytest.mark.parametrize(
    "endpoint",
    [
        "/api/{company}/summaries",
        "/api/{company}/calendar?start=2026-01-01&end=2026-12-31",
        "/api/{company}/weekly-sweeps",
    ],
)
async def test_tenant_isolation(
    authed_client, both_tenant_rows, company, endpoint
):
    """Each tenant's endpoint returns ONLY its own rows."""
    url = endpoint.format(company=company)
    response = await authed_client.get(url)
    assert response.status_code == 200
    payload = response.json()

    # Iterate every top-level list field in the response, assert no row
    # from the OTHER tenant appears. Schema-agnostic check: walk the JSON
    # for any dict that has a "company_id" field, assert it matches.
    other = "juno" if company == "seva" else "seva"

    def walk(node):
        if isinstance(node, dict):
            if node.get("company_id") == other:
                pytest.fail(
                    f"Cross-tenant leak: {company} endpoint returned a "
                    f"{other} row: {node}"
                )
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(payload)


@pytest.mark.parametrize("invalid_slug", ["nonsense", "SEVA", "seva!", "", "x" * 30])
async def test_invalid_company_returns_404(authed_client, invalid_slug):
    """get_current_company validation rejects malformed/unknown slugs."""
    response = await authed_client.get(f"/api/{invalid_slug}/summaries")
    assert response.status_code in (404, 422)  # 422 if regex fails first
```

## State of the Art

| Old Approach (v2.x) | Current Approach (v3.0 Phase 9) | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `select(DailySummary)` directly in router | `scoped_summaries(company)` helper | Phase 9 W2 | All 3 routers + 2 scheduler call sites updated; CI grep gate enforces |
| Router prefix `/summaries` | `/api/{company}/summaries` | Phase 9 W2 | Frontend API client base URL pattern: `/api/${company}/summaries` |
| Frontend `<Route index>` flat | `<Route path=":company">` nested | Phase 9 W3 | All tenant-scoped pages read `useParams().company` |
| Hardcoded brand mark amber-500 | Semantic CSS tokens `--color-brand-accent` | v2.1 Phase 8 (already done) | CompanySwitcher inherits the tokens — no new CSS work |
| `useAppStore` plain `create<T>` | `create<T>(persist(...))` | Phase 9 W3 | Selective `partialize` — only `lastVisitedCompany` persisted |
| Single `daily_summary` cron | `daily_summary` + `juno_daily_summary` (2 explicit jobs) | Phase 9 W2 | OPS-02 lock-ID assertion validates both 1017 + 1020 unique |
| TanStack key `['summaries', limit]` | `['summaries', companyId, limit]` via factory | Phase 9 W3 | `queryClient.clear()` on tenant switch as defence-in-depth |

**Deprecated/outdated:**
- The naive 3-step migration (ADD NULL → UPDATE backfill → ALTER NOT NULL) — replaced by the single-step `server_default='seva'` pattern (PITFALLS.md HIGH-3 mitigation).

## Open Questions

1. **CONTEXT.md D-01a "07:00 PT" vs existing 08:00 + 12:00 PT cron schedule**
   - What we know: D-01a writes "Seva daily_summary stays at 07:00 PT (existing). Juno daily_summary fires at 07:05 PT." But `scheduler/worker.py:394` registers `CronTrigger(hour="8,12", minute=0, ...)` — the actual Seva cron fires twice daily at 08:00 + 12:00 PT, not once at 07:00 PT.
   - What's unclear: Did the operator intend to change Seva's schedule to 07:00 PT? Or is "07:00" a documentation typo for "08:00"?
   - Recommendation: Planner asks the operator at plan-phase commitment. **Research locks Juno at 08:05 + 12:05 PT** to preserve cadence + 5-min stagger. If operator clarifies "actually I want single-fire at 07:00", planner adjusts both jobs.

2. **Should `agent_runs` gain a `company_id` column or use `notes` JSON?**
   - What we know: ARCHITECTURE.md D-08 says "embed in `notes` JSONB" (no schema change). CONTEXT.md doesn't override this. PITFALLS.md MEDIUM-5 says "if we ever want to query 'how many Juno runs failed last week' we'll need a column — defer."
   - What's unclear: Whether telemetry queries by company are anticipated in v3.0 or v3.1.
   - Recommendation: Stay with `notes` JSON for Phase 9 (matches existing pattern). If operator wants a per-company telemetry dashboard in v3.1, add a column then. Document the deferral in PROJECT.md.

3. **SQLAlchemy event listener defence-in-depth — ship in Phase 9 or defer?**
   - What we know: PITFALLS.md mentions it. CONTEXT.md doesn't require it. The scoped helpers + CI grep gate + test_multitenant_isolation.py provide three layers already.
   - What's unclear: Whether the planner has budget in W3 for a 4th layer.
   - Recommendation: Defer to v3.1+ hardening unless W3 finishes early. Three layers is sufficient for v3.0.

4. **Calendar `notes_md` body vs new sections — does Juno calendar use the same column?**
   - What we know: `calendar_items.notes_md` holds the text body. Juno renders empty-state on Tab 2 in v3.0 (DEF-09). v3.1+ JUNO-CAL-v31 lights up Juno calendar.
   - What's unclear: Whether Phase 9 needs to do anything for Juno calendar beyond "the row infrastructure is in place".
   - Recommendation: Phase 9 ships the migration + scoped helper for `calendar_items` so v3.1+ can drop in the Juno UI without schema work. No Juno calendar writes happen in Phase 9 — the Juno tab 2 simply shows empty-state because there are no Juno rows.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12 | Backend + scheduler | ✓ | 3.12+ | — |
| Node.js + npm | Frontend | ✓ | (Vercel-provisioned) | — |
| PostgreSQL | Data layer | ✓ | Neon-managed | — |
| Anthropic API key | Sonnet calls | ✓ | shared `ANTHROPIC_API_KEY` | — |
| Railway CLI | Deploy | ✓ | operator-installed | — |
| `pytest` + `pytest-asyncio` | Test infrastructure | ✓ | already configured | — |
| `vitest` | Frontend tests | ✓ | already configured | — |
| `grep` | CI grep gate | ✓ | bash builtin | — |

**No external dependencies missing or unavailable for Phase 9.** All work is code/config + schema migration on existing infrastructure.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Backend framework | `pytest>=9.0.2` + `pytest-asyncio>=1.3.0` (asyncio_mode=auto) |
| Backend config file | `backend/pyproject.toml` `[tool.pytest.ini_options]` |
| Backend quick run | `cd backend && uv run pytest tests/test_multitenant_isolation.py -x` |
| Backend full suite | `cd backend && uv run pytest -x` |
| Scheduler framework | `pytest>=9.0.2` + `pytest-asyncio>=1.3.0` |
| Scheduler config file | `scheduler/pyproject.toml` `[tool.pytest.ini_options]` |
| Scheduler quick run | `cd scheduler && uv run pytest tests/agents/test_daily_summary.py -x` |
| Scheduler full suite | `cd scheduler && uv run pytest -x` |
| Frontend framework | `vitest@4.1.2` |
| Frontend config file | `frontend/vite.config.ts` + `frontend/vitest.config.ts` |
| Frontend quick run | `cd frontend && npm run test -- --run src/components/layout/CompanySwitcher.test.tsx` |
| Frontend full suite | `cd frontend && npm run test -- --run` |
| CI grep gate | `bash scripts/verify-tenant-isolation.sh` (must exit 0) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TENANT-01 | Alembic 0014 adds `company_id` to 3 tables, backfills `'seva'` via `server_default` | unit (migration) | `cd backend && uv run pytest tests/test_migration_0014.py -x` | ❌ Wave 0 |
| TENANT-01 | Dual-model parity: backend + scheduler models both have `company_id` column | unit (parity) | `cd backend && uv run pytest tests/test_model_parity.py::test_daily_summary_parity -x` | ❌ Wave 0 (extend existing test_model_parity.py to cover DailySummary) |
| TENANT-02 | CHECK constraint rejects invalid company_id | unit (DB) | `cd backend && uv run pytest tests/test_migration_0014.py::test_check_constraint -x` | ❌ Wave 0 |
| TENANT-02 | Composite indexes exist (verify via `inspect(engine).get_indexes('daily_summaries')`) | unit (DB) | `cd backend && uv run pytest tests/test_migration_0014.py::test_composite_indexes -x` | ❌ Wave 0 |
| TENANT-03 | `scoped_summaries(company)` returns a `Select` with `company_id` filter | unit | `cd backend && uv run pytest tests/test_queries_scoped.py -x` | ❌ Wave 0 |
| TENANT-03 | CI grep gate fails on any raw `select(DailySummary)` outside `queries/scoped.py` | shell | `bash scripts/verify-tenant-isolation.sh` | ❌ Wave 0 |
| TENANT-04 | `get_current_company()` returns 404 on invalid slug | integration | `cd backend && uv run pytest tests/test_multitenant_isolation.py::test_invalid_company_returns_404 -x` | ❌ Wave 0 |
| TENANT-04 | Router prefix `/api/{company}/summaries` is reachable | integration | `cd backend && uv run pytest tests/test_multitenant_isolation.py -x` | ❌ Wave 0 |
| TENANT-05 | `<CompanyScopedRoute>` redirects invalid slug to `/seva` | unit (RTL) | `cd frontend && npm run test -- --run src/components/layout/CompanyScopedRoute.test.tsx` | ❌ Wave 0 |
| TENANT-05 | Nested route mounts `<TabbedDashboard>` with `:company` param available via `useParams` | unit (RTL) | `cd frontend && npm run test -- --run src/App.test.tsx` | ❌ Wave 0 (likely missing) |
| TENANT-06 | `/calendar` redirects to `/seva/calendar`; `/queue` redirects to `/seva` | unit (RTL) | `cd frontend && npm run test -- --run src/App.test.tsx::bookmark_grace` | ❌ Wave 0 |
| TENANT-07 | `<CompanySwitcher>` calls `queryClient.clear()` + `navigate('/${next}${subPath}')` on click | unit (RTL) | `cd frontend && npm run test -- --run src/components/layout/CompanySwitcher.test.tsx` | ❌ Wave 0 |
| TENANT-07 | Zustand `companySlice` persists `lastVisitedCompany` to localStorage key `seva-mining-app-state-v3` | unit | `cd frontend && npm run test -- --run src/stores/companySlice.test.ts` | ❌ Wave 0 |
| TENANT-08 | `JOB_LOCK_IDS` has both `juno_daily_summary=1020` and `juno_weekly_sweeper=1021` | unit | `cd scheduler && uv run pytest tests/test_worker.py::test_job_lock_ids_v3 -x` | ❌ Wave 0 (extend existing test_worker.py) |
| TENANT-08 | `build_scheduler()` registers `juno_daily_summary` job with `CronTrigger(hour="8,12", minute=5, ...)` | unit | `cd scheduler && uv run pytest tests/test_worker.py::test_juno_daily_summary_registered -x` | ❌ Wave 0 |
| TENANT-08 | `run_juno_daily_summary()` writes a `daily_summaries` row with `company_id='juno'` and `status='partial'` | integration | `cd scheduler && uv run pytest tests/agents/test_juno_daily_summary.py -x` | ❌ Wave 0 |
| TENANT-09 | `queryKeys.summaries('seva', 60)` returns `['summaries', 'seva', 60] as const` | unit | `cd frontend && npm run test -- --run src/api/queryKeys.test.ts` | ❌ Wave 0 |
| TENANT-09 | Switching tenant clears cache (`queryClient.clear()` called) | unit (RTL) | `cd frontend && npm run test -- --run src/components/layout/CompanySwitcher.test.tsx::test_clears_cache_on_switch` | ❌ Wave 0 |
| TENANT-10 | Cross-tenant leak detection — Seva endpoint returns NO Juno rows + vice versa, parametrized over both tenants and 3 endpoints | integration | `cd backend && uv run pytest tests/test_multitenant_isolation.py -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** quick run of the test file most directly tied to the task (e.g. W1 migration commit → `pytest tests/test_migration_0014.py -x`; W2 router commit → `pytest tests/test_multitenant_isolation.py -x`; W3 CompanySwitcher commit → `npm run test -- --run src/components/layout/CompanySwitcher.test.tsx`).
- **Per wave merge:** Full suite of the affected layer.
  - W1: `cd backend && uv run pytest -x` (model parity + migration tests)
  - W2: `cd backend && uv run pytest -x` AND `cd scheduler && uv run pytest -x`
  - W3: `cd frontend && npm run test -- --run`
- **Per phase merge gate:** ALL three suites + `bash scripts/verify-tenant-isolation.sh` must exit 0.
- **Phase gate (final):** Full suite green before `/gsd:verify-work`. Includes a smoke deploy to Railway preview env + manual check that `/seva/*` renders + `/juno/*` renders empty states + one APScheduler fire produces both a Seva and a Juno `daily_summaries` row.

### Wave 0 Gaps

All test files for Phase 9 are NEW. Wave 0 must create the failing tests (Red phase of TDD) before any implementation lands. Specifically:

- [ ] `scripts/verify-tenant-isolation.sh` — CI grep gate (TENANT-03). Initially passes (no raw selects exist yet); will fail when a Phase 9 plan adds `select(DailySummary)` mid-refactor; must pass again at phase close.
- [ ] `backend/tests/test_migration_0014.py` — verifies column exists, server_default applied, CHECK constraint enumerates seva+juno, composite indexes present (TENANT-01, TENANT-02).
- [ ] `backend/tests/test_queries_scoped.py` — verifies `scoped_summaries('seva')` returns a Select with `company_id == 'seva'` in WHERE clause (TENANT-03).
- [ ] `backend/tests/test_multitenant_isolation.py` — parametrized cross-tenant leak test + invalid-slug 404 test (TENANT-04, TENANT-10).
- [ ] `backend/tests/test_model_parity.py` — extend existing file with `test_daily_summary_parity()` mirroring CalendarItem/WeeklySweep pattern (Pitfall 5).
- [ ] `scheduler/tests/test_worker.py` — extend with `test_juno_lock_ids_present`, `test_juno_daily_summary_registered`, `test_scheduler_registers_4_jobs` (count bump from 3 → 4 jobs) (TENANT-08).
- [ ] `scheduler/tests/agents/test_juno_daily_summary.py` — verifies `run_juno_daily_summary()` writes a `daily_summaries` row with `company_id='juno'` + `status='partial'` (TENANT-08).
- [ ] `frontend/src/api/queryKeys.test.ts` — verifies factory shape (TENANT-09).
- [ ] `frontend/src/stores/companySlice.test.ts` — verifies persist + partialize (TENANT-07).
- [ ] `frontend/src/components/layout/CompanyScopedRoute.test.tsx` — verifies invalid-slug redirect to `/seva` (TENANT-05).
- [ ] `frontend/src/components/layout/CompanySwitcher.test.tsx` — verifies click triggers `queryClient.clear()` + `navigate(...)` + active-state from `useParams` (TENANT-07).
- [ ] `frontend/src/App.test.tsx` — verifies bookmark grace redirects work + nested `:company` route mounts TabbedDashboard (TENANT-05, TENANT-06).
- [ ] `frontend/src/conftest`-equivalent — vitest setup may need MSW handler updates for `/api/seva/*` and `/api/juno/*` URL patterns.
- [ ] Framework install: NONE required — pytest + vitest already configured. `cd backend && uv sync` + `cd scheduler && uv sync` + `cd frontend && npm install` happen on dev-env setup, not Phase 9.

## Sources

### Primary (HIGH confidence)

- Direct codebase reads (2026-05-19):
  - `backend/app/models/daily_summary.py` — existing schema baseline
  - `backend/app/routers/summaries.py` — router pattern baseline
  - `backend/alembic/versions/0010_add_daily_summaries.py` — hand-written migration style
  - `backend/alembic/versions/0013_calendar_title_nullable_unique_date.py` — most recent migration style
  - `backend/tests/conftest.py` — test fixture pattern (SQLite in-memory, auth helpers)
  - `backend/tests/test_model_parity.py` — dual-model parity test pattern
  - `scheduler/worker.py` — JOB_LOCK_IDS, `_make_daily_summary_job`, OPS-02 assertion
  - `scheduler/agents/daily_summary.py` — entry point + per-section pattern (810 lines)
  - `scheduler/pyproject.toml` — verified dependency versions
  - `frontend/src/App.tsx` — current route structure
  - `frontend/src/stores/index.ts` + slices — Zustand pattern (no persist currently)
  - `frontend/src/api/summaries.ts` — TanStack query hook pattern
  - `frontend/package.json` — verified react-router-dom@7.13, zustand@5.0, @tanstack/react-query@5.96
  - `scripts/verify-ui-04-hover-transitions.sh` — v2.1 grep gate pattern
- `.planning/phases/09-multi-tenant-foundation/09-CONTEXT.md` — locked decisions D-01..D-08
- `.planning/REQUIREMENTS.md` — TENANT-01..10 full text
- `.planning/research/SUMMARY.md` — research synthesis
- `.planning/research/STACK.md` — multi-tenancy strategy
- `.planning/research/ARCHITECTURE.md` — full file change map + 5 architectural decisions
- `.planning/research/PITFALLS.md` — pitfall taxonomy + mitigations

### Secondary (MEDIUM confidence)

- `.planning/STATE.md` — accumulated phase decisions (informs CI grep gate style + test count bump pattern)
- React Router v6 / v7 docs (asserted v7 API compatibility with v6 nested-route patterns based on existing v7.13 install in `frontend/package.json` + Zustand persist GitHub discussions): https://reactrouter.com/start/data/routing
- Zustand persist middleware docs (already in installed zustand@5.x): https://github.com/pmndrs/zustand/blob/main/docs/integrations/persisting-store-data.md

### Tertiary (LOW confidence — needs validation)

- `react-router-dom@7.13` exact `useParams<T>()` generic behavior — asserted from training knowledge of v6 → v7 changelog; planner should sanity-check during W3 implementation by running a small test against the actual installed library.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all versions verified via direct file reads
- Architecture patterns: HIGH — every pattern grounded in v2.x codebase + CONTEXT.md lock
- Code examples: HIGH for Alembic + scoped helpers + APScheduler factory (mirror existing patterns); MEDIUM for react-router-dom v7 specifics (asserted v6→v7 compatibility; planner verifies in W3)
- Pitfalls: HIGH — all 6 pitfalls grounded in PITFALLS.md or direct code reads
- Validation architecture: HIGH — leverages existing pytest + vitest configs

**Research date:** 2026-05-19
**Valid until:** 2026-06-18 (30-day window — stack is stable; revisit if any new release of react-router-dom, zustand, or @tanstack/react-query)
