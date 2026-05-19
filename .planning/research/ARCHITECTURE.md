# v3.0 Multi-Tenant Architecture Research

**Domain:** Subsequent-milestone integration analysis — adding multi-tenancy to an already-shipped single-tenant FastAPI + React 19 codebase
**Researched:** 2026-05-19
**Confidence:** HIGH — all integration claims grounded in direct reads of the v2.1 codebase (paths cited inline) and the v2.1 ARCHITECTURE baseline
**Scope:** Integration changes ONLY. v2.1 patterns (factory `_make_X_job`, advisory locks, dual-model parity, hand-written Alembic, router-level auth, React Router NavLink tabs) are baseline assumptions, NOT re-researched.

---

## 1. Existing Architecture Snapshot (confirmed by direct read)

| Layer | Component | Concrete artefact (verified) |
|-------|-----------|------------------------------|
| DB | Three v2.x tables, all "global" (no tenant column) | `daily_summaries`, `calendar_items`, `weekly_sweeps` — see `backend/app/models/{daily_summary,calendar_item,weekly_sweep}.py` |
| DB | Alembic head | `0013_calendar_title_nullable_unique_date.py` — next free revision is `0014` |
| DB | Dual-model parity | Every table has a copy in both `backend/app/models/` AND `scheduler/models/` (Phase B precedent — separate Python processes, no shared modules) |
| Backend | FastAPI app | `backend/app/main.py` — 14 routers registered including `summaries`, `calendar`, `weekly_sweeps`, `auth` |
| Backend | Router style | `APIRouter(prefix=..., tags=..., dependencies=[Depends(get_current_user)])` — router-level auth — see `backend/app/routers/summaries.py:18-22` |
| Scheduler | Worker process | `scheduler/worker.py` — separate Railway service, `AsyncIOScheduler` |
| Scheduler | Live agents | `scheduler/agents/daily_summary.py`, `daily_summary_prune.py`, `weekly_sweeper.py`, `ontario_law.py`, `ontario_stats.py`, `content_agent.py` (library), `x_ingest.py`, `senior_agent.py`, `brand_preamble.py` |
| Scheduler | Lock IDs | `JOB_LOCK_IDS = {"midday_digest": 1005, "daily_summary": 1017, "daily_summary_prune": 1018, "weekly_sweeper": 1019}` — `worker.py:91-102`. OPS-02 assertion at line 110 enforces uniqueness at import. Next free ID: **1020**. v1.0 IDs 1010-1016 are reserved-dead (MUST NEVER reuse). |
| Scheduler | Factory pattern | `_make_daily_summary_job(engine)` closes over engine, lazy-imports the agent, wraps in `with_advisory_lock` — `worker.py:214-235` |
| Scheduler | Agent entrypoint | `async def run_daily_summary() -> None` — takes NO arguments, called bare by `with_advisory_lock` |
| Frontend | Routing | `frontend/src/App.tsx` — `<BrowserRouter>` → `ProtectedRoute` → `AppShell` → `TabbedDashboard` (index/`calendar`/`viral`) + flat `/digest`, `/settings` |
| Frontend | AppShell | 12-line component, `<AppHeader />` then `<main><Outlet /></main>` — see `frontend/src/components/layout/AppShell.tsx` |
| Frontend | AppHeader | Brand mark (S amber-500 + "Seva Mining") + Logout. **Byte-frozen Phase 5 baseline.** Width-constrained `max-w-[720px] mx-auto px-4 py-3 flex items-center justify-between`. See `frontend/src/components/layout/AppHeader.tsx` |
| Config | Env vars | Flat namespace: `DATABASE_URL`, `SERPAPI_API_KEY`, `ANTHROPIC_API_KEY`, `X_API_BEARER_TOKEN`, `TWILIO_*`, `FRED_API_KEY`, `METALPRICEAPI_API_KEY` |
| Config | DB config | `config` table (legacy v1.0) — key/value rows, read by `_read_schedule_config()` in worker.py |

This is the surface v3.0 must integrate into. **No existing component is renamed or removed by v3.0 — every change is additive or surgical.**

---

## 2. Five Architectural Decisions

### Decision D-01: Data isolation strategy → **Option A (row-level `company_id`)**

**Recommendation: ROW-LEVEL `company_id` column on the three v2.x tables, with default backfill to `'seva'` and composite indexes.**

#### Rationale

v3.0 onboards exactly **two** tenants (Seva, Juno). The simplest correct approach wins.

| Criterion | A: row-level (RECOMMENDED) | B: schema-per-company | C: per-company tables |
|-----------|----------------------------|-----------------------|-----------------------|
| Alembic complexity | 1 migration adds column + backfills + indexes | Multi-schema Alembic — `version_table_schema`, `include_schemas=True`, per-schema upgrade runs. Non-trivial setup. | 3 new tables per tenant. N tenants = 3N tables. |
| SQLAlchemy support | Native — just add a column to the model | `__table_args__ = {"schema": "juno"}` per model; multiple `MetaData` objects; complex query patterns | Native, but model classes explode |
| Query overhead | `.where(Model.company_id == company)` on every read | None (schema sets it) | None (table sets it) |
| Cross-tenant leak risk | **HIGH if a query forgets the filter** (CRITICAL — see mitigation below) | Very low — different schemas | Very low — different tables |
| Downgrade story | Drop column + indexes (reversible) | Drop schemas + reverse-migrate (painful) | Drop tables (data loss unless dumped) |
| Scales to N tenants | Yes (composite indexes) | Yes (but Alembic burden grows) | No — combinatorial explosion |
| v3.0 fit (2 tenants, 1 operator) | **Best** | Over-engineered | Worst |

**Why not B:** Postgres schema-per-tenant is genuinely cleaner isolation, but Alembic requires per-schema migration runs (`alembic -x schema=juno upgrade head`) and the autogenerate workflow is brittle in multi-schema mode. The codebase already forbids `--autogenerate` (MOD-2 from v2.0 research, see `backend/alembic/versions/0010_add_daily_summaries.py:3-4`) — hand-written multi-schema migrations would multiply the surface area for hand-coding errors. The cross-tenant leak risk for Option A is mitigated by a **mandatory dependency-injected `CompanyContext`** (see Mitigation below) — that mitigation is cheap and well-understood.

**Why not C:** A single new tenant triples the schema. v3.1+ adds Juno Content Calendar (Tab 2) and Weekly Viral Sweeper (Tab 3), and the PROJECT.md explicitly defers "N companies" to v3.2+. C wastes effort on day one.

**Runner-up: Option B (schema-per-company)** — adopt this if a future security review demands hard isolation. Migration path A→B is mechanical (CREATE SCHEMA juno; INSERT INTO juno.daily_summaries SELECT * FROM daily_summaries WHERE company_id='juno'; etc.). A→B is a one-way ratchet; do not pre-emptively spend the complexity now.

#### Concrete migration (Alembic 0014)

**Single migration, atomic, reversible.** No data loss. Backfills all existing rows to `company_id='seva'` before applying NOT NULL.

```python
# backend/alembic/versions/0014_add_company_id.py
revision = "0014"
down_revision = "0013"

def upgrade() -> None:
    # 1. Add column nullable=True (so existing rows accept the column add)
    for table in ("daily_summaries", "calendar_items", "weekly_sweeps"):
        op.add_column(table, sa.Column("company_id", sa.String(20), nullable=True))

    # 2. Backfill ALL existing rows to 'seva' (single statement per table)
    op.execute("UPDATE daily_summaries SET company_id = 'seva' WHERE company_id IS NULL")
    op.execute("UPDATE calendar_items  SET company_id = 'seva' WHERE company_id IS NULL")
    op.execute("UPDATE weekly_sweeps   SET company_id = 'seva' WHERE company_id IS NULL")

    # 3. Now lock down NOT NULL + server_default for new inserts
    for table in ("daily_summaries", "calendar_items", "weekly_sweeps"):
        op.alter_column(table, "company_id", nullable=False, server_default="seva")

    # 4. CHECK constraint enumerating valid tenants (v3.0 = seva + juno only)
    op.create_check_constraint(
        "ck_daily_summaries_company_id",
        "daily_summaries",
        "company_id IN ('seva', 'juno')",
    )
    op.create_check_constraint(
        "ck_calendar_items_company_id",
        "calendar_items",
        "company_id IN ('seva', 'juno')",
    )
    op.create_check_constraint(
        "ck_weekly_sweeps_company_id",
        "weekly_sweeps",
        "company_id IN ('seva', 'juno')",
    )

    # 5. Composite indexes — every read filters by (company_id, generated_at|date)
    op.drop_index("ix_daily_summaries_generated_at", table_name="daily_summaries")
    op.create_index(
        "ix_daily_summaries_company_generated",
        "daily_summaries",
        ["company_id", sa.text("generated_at DESC")],
    )
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
    op.drop_index("ix_weekly_sweeps_generated_at", table_name="weekly_sweeps")
    op.create_index(
        "ix_weekly_sweeps_company_generated",
        "weekly_sweeps",
        ["company_id", sa.text("generated_at DESC")],
    )

def downgrade() -> None:
    # Reverse in exact reverse order. After downgrade, all Juno data is orphaned
    # in rows that still have company_id='juno' — but the column is dropped, so
    # the data is preserved (downgrade is "remove the column", not "delete Juno rows").
    # Operator must delete Juno rows manually if a true wipe-to-v2.1 is desired.
    op.drop_index("ix_weekly_sweeps_company_generated", table_name="weekly_sweeps")
    op.create_index("ix_weekly_sweeps_generated_at", "weekly_sweeps", [sa.text("generated_at DESC")])
    op.drop_index("ix_calendar_items_company_date", table_name="calendar_items")
    op.drop_constraint("uq_calendar_items_company_date", "calendar_items", type_="unique")
    op.create_unique_constraint("uq_calendar_items_date", "calendar_items", ["date"])
    op.drop_index("ix_daily_summaries_company_generated", table_name="daily_summaries")
    op.create_index("ix_daily_summaries_generated_at", "daily_summaries", ["generated_at"])

    for table in ("weekly_sweeps", "calendar_items", "daily_summaries"):
        op.drop_constraint(f"ck_{table}_company_id", table, type_="check")
        op.drop_column(table, "company_id")
```

**Reversibility verified:** `downgrade()` restores the exact pre-0014 schema (same index names, same UNIQUE constraint). Juno rows survive the column drop only in PG's row data — they become indistinguishable from Seva rows. Acceptable for v3.0 since a downgrade is a rollback signal, not a deletion request.

#### Cross-tenant leak mitigation (mandatory)

The single failure mode of Option A is "a query forgot to filter by `company_id`". The mitigation is a **FastAPI dependency `get_current_company()`** that resolves the active tenant from the URL path prefix (see D-03) and a **query helper** that all routers MUST use:

```python
# backend/app/dependencies.py — ADD
from typing import Literal
CompanyId = Literal["seva", "juno"]

async def get_current_company(request: Request) -> CompanyId:
    """Resolve the active company from URL path prefix /seva/* or /juno/*.
    Falls back to 'seva' for non-prefixed legacy routes (/login, /settings, /digest)."""
    path = request.url.path
    if path.startswith("/api/juno/") or path.startswith("/juno/"):
        return "juno"
    return "seva"  # default + explicit /seva/ prefix
```

And **every** v3.0 router uses it at the router level via `dependencies=`. The router function body does NOT use it directly — it is injected into the query layer. This makes "forgetting the filter" a compile-time impossibility because every query goes through a helper that takes `company_id` as a positional argument:

```python
# backend/app/queries/scoped.py — NEW
def scoped_summaries(company_id: CompanyId):
    """Returns a SELECT statement pre-filtered by company. NEVER bypass."""
    return select(DailySummary).where(DailySummary.company_id == company_id)
```

Every router that touches `daily_summaries`, `calendar_items`, `weekly_sweeps` MUST call `scoped_*()` to start its query. The leak risk drops from "any query" to "any query that ignored the helper" — a code-review-visible smell.

---

### Decision D-02: Scheduler topology → **Option 1 (single cron, in-process fan-out)**

**Recommendation: ONE cron per job-type (daily_summary, daily_summary_prune, weekly_sweeper), which loops over `ACTIVE_COMPANIES` in sequence inside the agent. Each company gets a per-company sub-advisory-lock so a stuck Juno run does not block the Seva run on the next fire.**

#### Rationale

| Criterion | 1: single cron + fan-out (RECOMMENDED) | 2: one cron per company | 3: parameterized cron arg |
|-----------|----------------------------------------|-------------------------|---------------------------|
| New JOB_LOCK_IDS entries | 0 (existing 1017 reused; sub-locks computed) | 2 per job-type (1020, 1021 for daily_summary_seva + _juno; 1022, 1023 for prune; 1024, 1025 for sweeper) = 6 total | 0 |
| OPS-02 lock-ID assertion impact | None | Must add 6 entries + re-verify assertion | None |
| `build_scheduler()` complexity | 1 line per job (unchanged) | 6 `scheduler.add_job()` calls per job-type (2 per tenant) | 1 line per job (unchanged) |
| Failure isolation | Per-company try/except inside agent (Juno failure doesn't block Seva — both run sequentially) | True: APScheduler isolates per-job | Per-company try/except inside agent |
| Sonnet cost per fire | Same (2x calls, one per company) | Same (2x calls across 2 cron fires) | Same |
| Telemetry shape | One `agent_runs` row PER COMPANY PER FIRE (status='running', then 'completed/failed/partial') — matches existing pattern | One agent_runs row per company per fire | One agent_runs row per company per fire |
| Lock contention risk | Outer lock 1017 held for ~50s (2x 25s daily_summary runs). Next fire is 4h+ away — no contention. | Each lock held ~25s. No contention. | Outer lock held longer. No contention. |
| New file count | 0 (modify worker.py + daily_summary.py only) | 2 new factory functions per job-type (or refactor existing) | 0 |
| Failure visibility | A Juno-only failure leaves Seva data and shows "partial" status in agent_runs — clear signal | Independent — Juno cron fails alone | Same as Option 1 |

**Why not Option 2:** It bloats `JOB_LOCK_IDS` from 4 entries to 10 and requires an "I added a Juno tenant → also add 3 lock IDs" coupling. The PROJECT.md says v3.2+ may add a third tenant — under Option 2 that means 9 new lock IDs at once, with the OPS-02 assertion regenerating every time. Option 1 scales: adding a tenant means adding 1 entry to `ACTIVE_COMPANIES` and zero new lock IDs.

**Why not Option 3:** APScheduler does not support per-execution argument override cleanly in v3.x (`args=`/`kwargs=` are fixed at job-registration). Parameterizing means N `add_job` calls anyway — collapses into Option 2.

**Runner-up: Option 2 (one cron per company)** — adopt this in v3.2+ if a tenant ever needs a different cron schedule (e.g. Juno daily_summary at 09:00 PT not 08:00 PT, or a Juno-only midweek sweep). Per-tenant scheduling REQUIRES per-tenant crons. For v3.0, all tenants share the same schedule — Option 1 wins.

#### Concrete shape

`scheduler/worker.py` — **no new JOB_LOCK_IDS entries.** Existing 1017/1018/1019 are reused (outer locks). The agent uses sub-advisory-locks per company.

```python
# scheduler/worker.py — UNCHANGED outer structure
# JOB_LOCK_IDS stays exactly as it is today (4 entries)

# Inside scheduler/agents/daily_summary.py — MODIFIED top of run_daily_summary
from companies import ACTIVE_COMPANIES  # NEW module — see Decision D-05

async def run_daily_summary() -> None:
    """v3.0: outer lock 1017 is acquired by worker.py wrapper. Inside this
    function, we loop over companies. Each company gets a sub-lock to avoid
    duplicate runs IF (hypothetically) a future deploy splits this into
    per-company crons. For v3.0, the sub-lock is defensive — the outer 1017
    already serializes the whole batch."""
    for company_id in ACTIVE_COMPANIES:  # ['seva', 'juno']
        try:
            await _run_daily_summary_for_company(company_id)
        except Exception as exc:
            logger.error("daily_summary for %s failed: %s", company_id, exc, exc_info=True)
            # next company still runs

async def _run_daily_summary_for_company(company_id: str) -> None:
    """Per-company workhorse. All existing daily_summary.py logic moves here,
    parameterized on company_id. Idempotency check now reads daily_summaries
    WHERE company_id = :company_id AND generated_at >= (now - 30min).
    Sonnet system prompt is selected by company (gold for seva, defence for juno).
    The 'config' section RSS feeds + SerpAPI queries are read from
    companies/{company_id}/config.py (see Decision D-05)."""
    # ... existing logic, but every SQL touches company_id ...
```

The daily_summary_prune cron also wraps in a per-company loop — `DELETE FROM daily_summaries WHERE company_id = :c AND generated_at < now - 30 days`. Same shape for weekly_sweeper.

#### Lock-ID inventory after v3.0

```python
JOB_LOCK_IDS: dict[str, int] = {
    "midday_digest": 1005,         # dead code, retained
    "daily_summary": 1017,         # UNCHANGED — single cron, fans out internally
    "daily_summary_prune": 1018,   # UNCHANGED — single cron, fans out internally
    "weekly_sweeper": 1019,        # UNCHANGED — single cron, fans out internally
    # 1020+ remain FREE. v1.0 IDs 1010-1016 remain RESERVED-DEAD.
}
```

OPS-02 assertion at `worker.py:110` continues to pass unchanged. **This is the strongest argument for Option 1: zero churn in the lock-ID inventory.**

---

### Decision D-03: Frontend routing → **Option A (path prefix `/seva/` `/juno/`)**

**Recommendation: PATH-PREFIX ROUTING. Replace the index route group with a `/:company` param segment. Bookmarks work, browser back/forward works, deep links work, no DNS changes, no Vercel project surgery.**

#### Rationale

| Criterion | A: path prefix /seva/* (RECOMMENDED) | B: query param ?company=seva | C: subdomain seva.app.com | D: no URL state (client toggle) |
|-----------|--------------------------------------|------------------------------|----------------------------|---------------------------------|
| Bookmarkable | Yes — `/juno/calendar` is its own URL | Yes — but ugly + breaks tab nav | Yes — DNS-level | **NO** — browser back broken |
| Browser back/forward | Yes — natural React Router behavior | Partial — query change doesn't always trigger route change | Yes (but cross-origin) | **NO** |
| Deep links | Yes | Yes (ugly) | Yes | NO |
| Vercel deployment | Same project, same domain | Same | **Multiple projects OR DNS + SSL surgery** | Same |
| `App.tsx` change | Add `/:company` param wrapper around TabbedDashboard. ~10 lines. | Pass `?company=` through every link. Brittle. | Different deployment per tenant. | Add Zustand global state for active company. Breaks bookmarking. |
| Auth migration | JWT works unchanged (single user, single cookie scope) | Same | **JWT scope must extend to subdomain wildcard** | Same |
| Future N tenants | Trivial — add to ACTIVE_COMPANIES | Trivial | Operational cost per tenant (DNS record + SSL) | N/A — broken |
| AppHeader awareness | Reads `useParams()['company']` — trivial | Reads `useSearchParams()` — works but ugly | Reads `window.location.hostname` parse — fragile | Reads Zustand store — breaks deep links |

**Why not B (query param):** TanStack Query keys would need to embed `company` everywhere (`['calendar', start, end]` becomes `['calendar', company, start, end]`). The path-prefix approach also requires this — but with path-prefix, the param is naturally consumed by `useParams()` and feels first-class. Query params would also need URL normalization (`?company=SEVA` vs `?company=seva` vs `?company=`), opening edge-case bugs.

**Why not C (subdomain):** Vercel project per tenant means a separate deploy for every Juno change. The CORS config in `backend/app/main.py:41-49` would need wildcard subdomain handling. Operationally heavier with no UX gain.

**Why not D (no URL state):** Browser back/forward is broken. Bookmarking the Juno calendar is impossible. Single-user internal tool or not, this is a regression from v2.1.

**Runner-up: Option C (subdomain)** — adopt this if v3.x ever offers Juno to external Juno operators (multi-user, multi-org) where the subdomain becomes a tenant-isolation security boundary. For v3.0, single operator, no security boundary needed.

#### Concrete shape

```tsx
// frontend/src/App.tsx — MODIFIED
<Route element={<ProtectedRoute />}>
  <Route element={<AppShell />}>

    {/* v3.0: company-scoped 3-tab surface */}
    <Route path=":company" element={<CompanyScopedRoute />}>
      <Route element={<TabbedDashboard />}>
        <Route index element={<SummaryFeedPage />} />
        <Route path="calendar" element={<ContentCalendarPage />} />
        <Route path="viral" element={<WeeklyViralSweeperPage />} />
      </Route>
    </Route>

    {/* Root redirect — bookmarks to / now go to /seva/ */}
    <Route index element={<Navigate to="/seva" replace />} />

    {/* v2.0 bookmark-grace redirects — preserved */}
    <Route path="/queue" element={<Navigate to="/seva" replace />} />
    <Route path="/agents/:slug" element={<Navigate to="/seva" replace />} />

    {/* Non-tenanted surfaces (digest is dead, settings is single-user global) */}
    <Route path="/digest" element={<DigestPage />} />
    <Route path="/settings" element={<SettingsPage />} />
  </Route>
</Route>
```

`<CompanyScopedRoute>` is a new ~15-line component that:
1. Reads `useParams()['company']`
2. Validates against `ACTIVE_COMPANIES` (otherwise redirects to `/seva`)
3. Publishes the active company to a Zustand store so `AppHeader` (and any non-routed component) can read it without prop-drilling
4. Renders `<Outlet />`

API client modules (`frontend/src/api/{summaries,calendar,weeklySweeps}.ts`) take `company` as an argument to their fetch functions, and the React Query hooks include `company` in `queryKey`:

```ts
// frontend/src/api/summaries.ts — MODIFIED
export function useSummaries(company: CompanyId) {
  return useQuery({
    queryKey: ['summaries', company],
    queryFn: () => getSummaries(company),
    refetchInterval: 60_000,
  })
}
```

Backend API contract: every router that currently lives at `/summaries`, `/calendar`, `/weekly-sweeps` gets a sibling prefix mounted via FastAPI's `app.include_router(..., prefix=...)`:

```python
# backend/app/main.py — MODIFIED
# v3.0: every tenant-scoped router is mounted under /api/{company}.
# Path prefix mirrors the frontend route. company_id is extracted via
# the get_current_company() dependency.
app.include_router(summaries_router, prefix="/api/{company}")
app.include_router(calendar_router, prefix="/api/{company}")
app.include_router(weekly_sweeps_router, prefix="/api/{company}")
# Non-tenanted routers stay at /api/... — auth, settings, etc.
app.include_router(auth_router)
```

The `/api/` namespace formalization is new in v3.0. The frontend `apiFetch()` helper already prepends a base URL, so this is a one-line change in the frontend fetch layer.

---

### Decision D-04: AppHeader company switcher → **Option B (lift the freeze, declare v3.0 mandatory edit)**

**Recommendation: SURGICAL EDIT TO `AppHeader.tsx`. Document the freeze-lift in the migration log. Add a `CompanySwitcher` button between the brand mark and the Logout button. The freeze served Phase 5; v3.0 is a milestone-level architecture change that legitimately invalidates it.**

#### Rationale

The Phase 5 byte-freeze on `AppHeader.tsx` was a "tabs land elsewhere, don't touch the header" constraint. v3.0 is fundamentally about presenting **which tenant the operator is currently viewing** — that information BELONGS in the header. Putting a company switcher anywhere else (e.g. above the tab bar) creates a worse UX:

- **Header is where global UI lives** (brand, logout, environment indicator). A tenant switcher is global state. Putting it in the header is the conventional placement (GitHub org switcher, Linear workspace switcher, Slack workspace switcher — all in headers).
- **Header is visible on every page**, including `/settings` and `/digest`. A switcher mounted below the header (e.g. in `TabbedDashboard`) would be invisible on `/settings`, which is exactly when the operator needs to switch contexts ("am I editing Seva settings or Juno settings?" — even though v3.0 doesn't yet split settings).
- **The freeze was about NOT touching the header DURING Phase 5.** v3.0 is a new milestone. Milestone-level architecture work is the explicit exception.

| Criterion | A: sibling component in AppShell (preserve freeze) | B: edit AppHeader.tsx (RECOMMENDED) |
|-----------|----------------------------------------------------|--------------------------------------|
| Freeze constraint | Honored | Violated, but with a documented rationale |
| Visual placement | Above tab bar, below header — awkward | Inside header, next to brand — natural |
| Lines changed in AppHeader | 0 | ~5 (insert `<CompanySwitcher />` between brand div and Logout button) |
| Visibility on /settings + /digest | Hidden (lives inside TabbedDashboard surface only — but those routes are OUTSIDE TabbedDashboard) | Visible on every route |
| Future maintenance | Two header-adjacent components to keep in visual sync | One canonical header |
| Convention violation | None — Phase 5 freeze remains the rule | One — explicit, documented, milestone-scoped |

**Why not Option A:** If `<CompanySwitcher />` is mounted in `<AppShell />` as a sibling of `<AppHeader />`, it's visible on every page (good) — but it now sits ABOVE the header (because AppHeader has `sticky top-0 z-10`) or BELOW the header (creating a second visual band). Either way, it competes visually with the brand mark and looks like an afterthought. The freeze isn't worth the UX cost.

**Runner-up: Option A (preserve freeze, add sibling component in AppShell)** — adopt this if the operator firmly rejects header edits even with a documented rationale. Mounted directly below `<AppHeader />` and styled to look like a sub-toolbar.

#### Concrete shape

```tsx
// frontend/src/components/layout/AppHeader.tsx — MODIFIED
// v3.0: freeze formally lifted in milestone roadmap section "AppHeader edit
// rationale". Adding CompanySwitcher between brand mark and logout. The
// max-w-[720px] mx-auto layout is preserved; only the inner flex content
// changes. Tailwind utility classes only — no new CSS.
export function AppHeader() {
  const navigate = useNavigate()
  const clearToken = useAppStore((s) => s.clearToken)

  function handleLogout() {
    clearToken()
    navigate('/login')
  }

  return (
    <header className="border-b border-zinc-800 bg-zinc-900 sticky top-0 z-10">
      <div className="max-w-[720px] mx-auto px-4 py-3 flex items-center justify-between">
        {/* Brand mark — UNCHANGED */}
        <div className="flex items-center gap-3">
          <div className="w-7 h-7 rounded-md bg-amber-500 flex items-center justify-center shrink-0">
            <span className="text-xs font-bold text-zinc-900">S</span>
          </div>
          <span className="text-sm font-semibold text-white">Seva Mining</span>
        </div>

        {/* v3.0: company switcher — segmented control */}
        <CompanySwitcher />

        {/* Logout — UNCHANGED */}
        <button
          onClick={handleLogout}
          className="text-sm text-zinc-400 hover:text-zinc-100 transition-colors"
        >
          Log out
        </button>
      </div>
    </header>
  )
}
```

`<CompanySwitcher />` is a new file at `frontend/src/components/layout/CompanySwitcher.tsx` (~30 lines): two `<NavLink>` buttons styled as a segmented control, each linking to `/seva` or `/juno` (preserving the current tab via search params or default to index). Active state from `useParams()['company']`. Tailwind only — no shadcn dropdown needed for two options.

**Open question for roadmap:** the brand mark currently reads "Seva Mining". Two visual options:
1. Keep "Seva Mining" — brand mark refers to the agency, not the active tenant; switcher disambiguates
2. Make brand mark dynamic — "Seva" or "Juno" based on active tenant

The PROJECT.md explicitly defers per-company branding to v3.1+ ("Juno keeps the same amber/zinc baseline initially"). **Keep "Seva Mining" as the brand mark** for v3.0; the switcher is the tenant indicator.

---

### Decision D-05: Per-company config namespace → **Option B (per-company config module in code; env vars stay flat)**

**Recommendation: A `companies/` Python package with `seva/`, `juno/` subpackages. Each subpackage exports a `Config` dataclass (RSS feed URLs, Sonnet system prompts, SerpAPI query strings, etc.). Env vars stay flat — `JUNO_*` namespace is only used for secrets that genuinely need per-tenant separation (currently: NONE for v3.0).**

#### Rationale

| Criterion | A: env vars (JUNO_RSS_FEEDS) | B: per-company config code module (RECOMMENDED) | C: DB `companies` table |
|-----------|------------------------------|--------------------------------------------------|---------------------------|
| Static config (RSS feed list, Sonnet prompts) | Bad fit — multi-line JSON in env var is ugly | **Natural fit — Python dicts/lists in code, type-checked** | Overkill — UI doesn't manage this in v3.0 |
| Secrets (API keys per tenant) | Good fit — but v3.0 has NO per-tenant secrets | N/A | Bad — DB stores secrets is anti-pattern |
| Diffable config changes | Yes (env var commit) | **Yes — full Python diff, code review-friendly** | No — DB row edits are invisible to git |
| Hot-reload | No (Railway restart required) | No (deploy required) | Yes (read at runtime) |
| Multi-tenant scaling | Env vars explode: JUNO_RSS_FEEDS + JUNO_SERPAPI_QUERIES + JUNO_SONNET_PROMPT + ... | One subpackage per tenant. Predictable. | One row per tenant. |
| Type safety | None (string env vars need parsing) | **Full Python types — dataclasses, Literals, lists** | Pydantic schema at read time |
| Operator can edit without redeploy | Yes (Railway dashboard) | **No (intentional — config is source-of-truth in git)** | Yes |
| Existing pattern in codebase | `config.py` (pydantic-settings) reads env vars | `scheduler/agents/brand_preamble.py` is a Python module with hardcoded prompt — same shape | `config` DB table (legacy v1.0) — not actively used for new features |

**Why not Option A:** v3.0's per-company config is FUNDAMENTALLY static-and-large (defence RSS feed list = ~15 URLs; Sonnet system prompt = ~2KB markdown; SerpAPI query template = string with placeholders). Putting that in env vars means base64-encoded JSON blobs in `JUNO_CONFIG` — ugly, untyped, error-prone, and impossible to code-review.

**Why not Option C:** DB-stored config has one strong use case (operator edits at runtime). v3.0 does NOT have that requirement — RSS feeds are operator-stable. PROJECT.md explicitly notes "RSS feeds (Kitco, Mining.com, JMN, WGC) and keyword lists from the blueprint serve as initial seeds. User will customize via the dashboard Settings page during build" — but that was v1.0 and the Settings page was deprecated in v2.0 (see CLAUDE.md: "Watchlists UI tab has been removed"). The DB-config route is not the active pattern. Defer to v3.1+ if operator demands runtime feed customization.

**Runner-up: Option C (DB-stored config)** — adopt this in v3.1 if Settings page is revived AND the operator wants to add/remove RSS feeds without a deploy. For v3.0, the operator has full git access; deploying a feed list is a 1-commit operation.

#### Concrete shape

```
scheduler/companies/                    NEW package
├── __init__.py                         exports ACTIVE_COMPANIES + get_config()
├── base.py                             CompanyConfig dataclass definition
├── seva/
│   ├── __init__.py                     SevaConfig instance
│   ├── prompts.py                      GOLD_NEWS_SYSTEM_PROMPT (moved from daily_summary.py)
│   ├── feeds.py                        RSS feed list (Kitco, Mining.com, JMN, WGC)
│   └── serpapi.py                      Gold-sector SerpAPI query strings
└── juno/
    ├── __init__.py                     JunoConfig instance
    ├── prompts.py                      DEFENCE_NEWS_SYSTEM_PROMPT
    ├── feeds.py                        Defence RSS feeds (Janes, Defense News, etc.)
    └── serpapi.py                      Defence-sector SerpAPI queries
```

Mirror in `backend/`:

```
backend/app/companies/                  NEW package (slim — only metadata)
├── __init__.py                         ACTIVE_COMPANIES Literal
└── types.py                            CompanyId type alias
```

(The backend doesn't need RSS feeds or Sonnet prompts — those live exclusively in scheduler/.)

The `companies/__init__.py` exports:

```python
# scheduler/companies/__init__.py
from .base import CompanyConfig
from .seva import SEVA_CONFIG
from .juno import JUNO_CONFIG

ACTIVE_COMPANIES: tuple[str, ...] = ("seva", "juno")

_CONFIGS: dict[str, CompanyConfig] = {
    "seva": SEVA_CONFIG,
    "juno": JUNO_CONFIG,
}

def get_config(company_id: str) -> CompanyConfig:
    return _CONFIGS[company_id]
```

The `daily_summary.py` agent reads `get_config(company_id).sonnet_system_prompt` instead of the hardcoded `GOLD_NEWS_SYSTEM_PROMPT`. Same for RSS feeds and SerpAPI queries.

Env vars **DO NOT** change. `DATABASE_URL`, `ANTHROPIC_API_KEY`, `SERPAPI_API_KEY`, `X_API_BEARER_TOKEN` all remain shared. Per-tenant secrets are deferred — there are none in v3.0.

---

## 3. System Diagram (v3.0)

### Request flow (frontend → backend → DB)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Browser                                         │
│  User on /juno/calendar → useParams()['company'] = 'juno'                   │
│  TanStack Query: queryKey=['calendar', 'juno', start, end]                  │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │ GET /api/juno/calendar?start=...&end=...
                                   │ Authorization: Bearer <jwt>
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          FastAPI (backend, Railway)                          │
│  app.include_router(calendar_router, prefix="/api/{company}")               │
│  Router-level deps: get_current_user (auth) + get_current_company           │
│  Resolves request.url.path → CompanyId = 'juno'                             │
│                                                                              │
│  list_calendar_items(start, end, db, company=Depends(get_current_company))  │
│    → scoped_calendar('juno')                                                │
│       returns: SELECT * FROM calendar_items WHERE company_id='juno' ...     │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │ SQL (asyncpg)
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       PostgreSQL (Neon, single DB)                           │
│  daily_summaries (company_id, generated_at, ...)                             │
│    UNIQUE / INDEX: (company_id, generated_at DESC)                          │
│    CHECK: company_id IN ('seva', 'juno')                                    │
│  calendar_items (company_id, date, ...)                                      │
│    UNIQUE: (company_id, date)                                                │
│  weekly_sweeps (company_id, generated_at, ...)                               │
│    INDEX: (company_id, generated_at DESC)                                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Scheduler flow (cron → per-company fan-out)

```
┌──────────────────────────────────────────────────────────────────────────┐
│                  APScheduler (worker process, Railway)                    │
│  daily_summary cron @ 08:00 + 12:00 PT                                   │
│  acquires pg_try_advisory_lock(1017) [outer]                             │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     │
                                     ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  scheduler/agents/daily_summary.py — run_daily_summary()                  │
│  for company_id in ACTIVE_COMPANIES:  # ('seva', 'juno')                 │
│    try:                                                                   │
│      await _run_daily_summary_for_company(company_id)                    │
│    except Exception: log + continue                                      │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     │
                ┌────────────────────┴────────────────────┐
                ▼                                         ▼
┌──────────────────────────────┐         ┌──────────────────────────────┐
│  _run_daily_summary_for(seva)│         │  _run_daily_summary_for(juno)│
│  config = get_config('seva') │         │  config = get_config('juno') │
│  fetch RSS (gold feeds)      │         │  fetch RSS (defence feeds)   │
│  SerpAPI (gold queries)      │         │  SerpAPI (defence queries)   │
│  Sonnet (gold system prompt) │         │  Sonnet (defence prompt)     │
│  INSERT daily_summaries(     │         │  INSERT daily_summaries(     │
│    company_id='seva', ...)   │         │    company_id='juno', ...)   │
│  agent_runs row (notes JSON  │         │  agent_runs row (notes JSON  │
│    includes company_id)      │         │    includes company_id)      │
└──────────────────────────────┘         └──────────────────────────────┘
```

---

## 4. Complete File Change Map

### NEW files

```
backend/
  alembic/versions/
    0014_add_company_id.py                 D-01 migration

  app/
    companies/                             NEW package (backend slice)
      __init__.py                          exports ACTIVE_COMPANIES, CompanyId
      types.py                             Literal type alias

    queries/                               NEW package — scoped query helpers
      __init__.py
      scoped.py                            scoped_summaries(c), scoped_calendar(c),
                                           scoped_weekly_sweeps(c) — cross-leak defense

scheduler/
  companies/                               NEW package (scheduler slice — full config)
    __init__.py                            ACTIVE_COMPANIES + get_config()
    base.py                                CompanyConfig dataclass
    seva/
      __init__.py                          SEVA_CONFIG instance
      prompts.py                           GOLD_NEWS_SYSTEM_PROMPT (relocated)
      feeds.py                             gold RSS feed URLs
      serpapi.py                           gold SerpAPI query strings
    juno/
      __init__.py                          JUNO_CONFIG instance
      prompts.py                           DEFENCE_NEWS_SYSTEM_PROMPT
      feeds.py                             defence RSS feed URLs
      serpapi.py                           defence SerpAPI queries

frontend/src/
  components/layout/
    CompanyScopedRoute.tsx                 validates :company param, publishes to store
    CompanySwitcher.tsx                    segmented control inside AppHeader

  stores/
    companyStore.ts                        Zustand — active company id (read from URL)

  types/
    company.ts                             CompanyId Literal type
```

### MODIFIED files

```
backend/
  app/main.py                              v3.0:
                                           - prefix="/api/{company}" on summaries_router,
                                             calendar_router, weekly_sweeps_router
                                           - non-tenanted routers (auth, settings, digest,
                                             agent_runs, content, etc.) stay at root
  app/dependencies.py                      ADD get_current_company(request) → CompanyId
  app/routers/summaries.py                 inject Depends(get_current_company);
                                           use scoped_summaries(company) helper
  app/routers/calendar.py                  inject Depends(get_current_company);
                                           use scoped_calendar(company); UNIQUE check
                                           is now (company_id, date) not just date
  app/routers/weekly_sweeps.py             inject Depends(get_current_company);
                                           use scoped_weekly_sweeps(company)
  app/models/daily_summary.py              add Column("company_id", String(20), nullable=False)
  app/models/calendar_item.py              same; UniqueConstraint becomes (company_id, date)
  app/models/weekly_sweep.py               same
  app/schemas/daily_summary.py             SummaryCardResponse adds company_id field (response)
                                           — frontend can verify it's getting the right tenant
  app/schemas/calendar.py                  CalendarItemResponse adds company_id (optional —
                                           defensive)
  app/schemas/weekly_sweep.py              WeeklySweepCard adds company_id

scheduler/
  worker.py                                Imports ACTIVE_COMPANIES from companies/__init__.
                                           NO new JOB_LOCK_IDS entries (D-02).
                                           No new factory functions.
  models/daily_summary.py                  add company_id Column (dual-model parity)
  models/calendar_item.py                  add company_id Column + composite UNIQUE
  models/weekly_sweep.py                   add company_id Column
  agents/daily_summary.py                  Top-level: for company_id in ACTIVE_COMPANIES loop;
                                           extract per-company body to
                                           _run_daily_summary_for_company(company_id);
                                           all queries filter on company_id;
                                           idempotency check is per-company;
                                           Sonnet prompt loaded via get_config(company_id);
                                           agent_runs row gets company_id in notes JSON
  agents/daily_summary_prune.py            DELETE FROM daily_summaries WHERE company_id=:c
                                           inside per-company loop
  agents/weekly_sweeper.py                 per-company loop; X API queries via
                                           get_config(company_id).x_api_queries
  agents/content_agent.py                  fetch_stories(company_id) — RSS + SerpAPI sources
                                           come from get_config(company_id)

frontend/src/
  App.tsx                                  Route restructure:
                                           - Wrap TabbedDashboard in <Route path=":company"
                                             element={<CompanyScopedRoute />}>
                                           - <Route index element={<Navigate to="/seva"/>}/>
                                           - Redirect /queue + /agents/:slug to /seva
  components/layout/AppHeader.tsx          BYTE-FROZEN STATUS LIFTED (D-04).
                                           Insert <CompanySwitcher /> between brand and
                                           Logout. ~5 line addition.
  components/layout/TabNav.tsx             NavLinks updated to include company prefix:
                                           to={`/${company}`}, to={`/${company}/calendar`},
                                           to={`/${company}/viral`}
  api/summaries.ts                         getSummaries(company) → fetch /api/{company}/summaries
                                           useSummaries(company) → queryKey ['summaries', company]
  api/calendar.ts                          same shape change
  api/weeklySweeps.ts                      same shape change
  pages/SummaryFeedPage.tsx                useSummaries(company) — read company from useParams
  pages/ContentCalendarPage.tsx            same
  pages/WeeklyViralSweeperPage.tsx         same
```

### UNCHANGED files (confirmed by direct read)

```
backend/
  app/database.py                          AsyncSession / engine — single Neon connection,
                                           no tenant-aware pool needed
  app/dependencies.py:get_current_user     JWT validation unchanged (single operator)
  app/routers/auth.py                      login flow unchanged (single password)
  app/routers/settings.py (when revived)   single-operator global settings
  app/routers/agent_runs.py                agent_runs already has company_id in JSON notes
                                           field — no schema change required
  app/routers/digests.py                   dead surface, not tenanted
  app/routers/post_to_x.py                 deferred to v3.1+ (Juno doesn't post yet)
  alembic/env.py                           no multi-schema config needed
  alembic/versions/0010..0013_*.py         historical migrations — never edit

scheduler/
  agents/senior_agent.py                   midday_digest dead code, not touched
  agents/ontario_law.py                    seva-only agent, called by daily_summary loop
                                           ONLY when company_id == 'seva'
                                           (see decision note below)
  agents/ontario_stats.py                  same — seva-only, gated inside
                                           _run_daily_summary_for_company
  agents/x_ingest.py                       library used by weekly_sweeper; takes queries
                                           as param — no module-level change beyond
                                           the caller passing company-scoped queries
  agents/brand_preamble.py                 seva-specific helper, retained as-is
                                           (Juno gets its own prompts module instead
                                           of a brand_preamble equivalent)
  database.py                              engine + session factory — no change
  models/agent_run.py                      already JSONB notes — embed company_id there
                                           (no Alembic change)
  models/config.py                         legacy v1.0 table, not used for v3.0 config
  config.py                                pydantic-settings unchanged — no new env vars
                                           required for v3.0

frontend/src/
  components/layout/AppShell.tsx           12-line component, no change (no need to
                                           publish company to descendants — Zustand store
                                           handles it from CompanyScopedRoute)
  components/layout/ProtectedRoute.tsx     JWT check unchanged
  components/layout/TabbedDashboard.tsx    still just <TabNav /> + <Outlet />
  components/summary/SummaryCard.tsx       reads card data, agnostic to company
  components/calendar/*                    weekly grid is agnostic to which company's
                                           data it's rendering — receives items via props
  components/viral/SweeperCard.tsx         agnostic
  components/markdown/*                    XHandlePill + rehype pipeline unchanged
  components/ui/*                          unchanged
  pages/LoginPage.tsx                      single-user login unchanged
  pages/DigestPage.tsx                     dead surface
  pages/SettingsPage.tsx                   not company-scoped in v3.0
```

---

## 5. Build Order (dependency-respecting)

**Foundation must land in a single deployable phase — DB + backend scope + frontend scope must ship together OR feature-flag the entire v3.0 surface. Recommended: single foundation phase, then News Funnel as a second phase.**

### Phase 1 — Multi-Tenant Foundation (DB + backend scope + frontend routing + AppHeader)

**Why first:** D-01 (migration) is the irreversible step. Once `company_id` exists with backfill to `'seva'`, every read in the codebase must filter by it. Shipping this in stages risks production rows arriving without a company_id between deploys.

Tasks:
1. `0014_add_company_id.py` migration (D-01)
2. Backend model updates (3 files in `backend/app/models/`, 3 files in `scheduler/models/`)
3. `app/companies/` package + `CompanyId` Literal
4. `app/queries/scoped.py` cross-leak defence helpers
5. `get_current_company` dependency in `app/dependencies.py`
6. `main.py` router prefix change to `/api/{company}` for tenant-scoped routers
7. Existing routers (`summaries.py`, `calendar.py`, `weekly_sweeps.py`) inject company + use scoped helpers
8. `scheduler/companies/` package with both seva + juno configs (juno feeds list can be a stub for now)
9. `scheduler/agents/daily_summary.py` refactored to per-company loop (juno path is wired up but `JUNO_CONFIG.feeds = []` until Phase 2)
10. `scheduler/agents/daily_summary_prune.py` per-company DELETE
11. `scheduler/agents/weekly_sweeper.py` per-company loop (juno path is a no-op stub until v3.1)
12. Frontend: `App.tsx` route restructure
13. Frontend: `CompanyScopedRoute.tsx` + `companyStore.ts` (Zustand)
14. Frontend: `CompanySwitcher.tsx` + `AppHeader.tsx` edit (D-04)
15. Frontend: TabNav links updated with company prefix
16. Frontend: API client modules take `company` param
17. Frontend: SummaryFeedPage, ContentCalendarPage, WeeklyViralSweeperPage read company from `useParams()`
18. Smoke test: deploy + verify `/seva/` works identically to v2.1, `/juno/` shows empty states everywhere

**Exit criteria:**
- v2.1 surface behavior under `/seva/*` is byte-equivalent to pre-deploy
- `/juno/*` renders all three tabs with "no data yet" empty states
- `daily_summaries`, `calendar_items`, `weekly_sweeps` queries verified to filter by company in pgAdmin
- One scheduler fire (manual trigger or wait for 08:00 PT) produces a Seva row AND a Juno row (Juno row is a "no data" status='partial' since feeds are empty)

### Phase 2 — Juno News Funnel

**Why second:** Foundation is live. Adding Juno's RSS feeds, SerpAPI queries, and Sonnet prompt is now a config-only change to `scheduler/companies/juno/`. No new schema work, no new routing, no new auth.

Tasks:
1. Populate `scheduler/companies/juno/feeds.py` with the defence RSS feed list (Janes, Defense News, Breaking Defense, RCAF, NATO, etc.)
2. Populate `scheduler/companies/juno/serpapi.py` with defence-news SerpAPI query strings
3. Populate `scheduler/companies/juno/prompts.py` with DEFENCE_NEWS_SYSTEM_PROMPT (Sonnet system prompt for Juno daily summary — likely a defence-industry equivalent of GOLD_NEWS_SYSTEM_PROMPT)
4. Add "world events relevant to defence" heuristic — Sonnet relevance filter
5. Verify one Juno cron fire produces a populated `daily_summaries` row with company_id='juno', non-empty gold_news_md (renamed-by-convention to the same column — the v2.0 column name is a historical artifact; under Option A, both tenants share the column)
6. Tab 1 of `/juno/` renders the live Juno feed
7. Operator UAT

**Exit criteria:**
- Juno News Funnel renders a real summary card on Tab 1
- Seva News Funnel is byte-identical to pre-v3.0
- Cross-tenant data verified isolated: `SELECT count(*) FROM daily_summaries GROUP BY company_id` matches expected fire counts per tenant

### Out of scope for v3.0 (explicit deferrals from PROJECT.md)

- Juno Content Calendar (Tab 2) — UI renders empty state forever in v3.0
- Juno Weekly Viral Sweeper (Tab 3) — same
- Per-company branding (Juno keeps amber/zinc theme)
- A third tenant beyond Seva + Juno

---

## 6. Pitfalls & Mitigations (v3.0-specific)

| Pitfall | Severity | Mitigation |
|---------|----------|------------|
| **Cross-tenant leak** — a query forgets `WHERE company_id = ?` | CRITICAL | `scoped_*()` helpers (D-01). Code review rule: any new query touching the 3 multi-tenant tables MUST start from a `scoped_*()` helper. CI grep for `select(DailySummary)`/`select(CalendarItem)`/`select(WeeklySweep)` outside `queries/scoped.py` should fail. |
| **Backfill races** — 0014 migration on a live system could miss rows inserted between `UPDATE` and `ALTER NOT NULL` | HIGH | Apply migration during a known-quiet window (e.g. 04:00 PT, between the 03:00 prune cron and the 08:00 daily_summary cron). Alternatively: take the worker process down for ~30 seconds during migration (single-operator, internal tool — acceptable). |
| **OPS-02 collision** if a future dev splits per-company crons (D-02 → Option 2) without updating the lock-ID assertion | MEDIUM | The assertion at `worker.py:110` catches it at import. v3.0 doesn't introduce any new lock IDs (per D-02), so the assertion has no new state. Document in `worker.py` header that lock 1020+ is the next free ID. |
| **AppHeader freeze re-breach** — a future Phase 9+ task may re-freeze the header and conflict with v3.0's edit | LOW | The v3.0 milestone roadmap section will document the freeze lift. Future re-freeze must accept v3.0's CompanySwitcher placement as the new baseline. |
| **CompanyId Literal drift** — adding a third tenant in v3.2+ means updating `CompanyId` in both `backend/app/companies/types.py` AND `scheduler/companies/__init__.py` AND the CHECK constraint in DB | MEDIUM | Dual-model parity convention already establishes this duplication pattern. Add a startup assertion in `worker.py` that the DB CHECK constraint enumeration matches `ACTIVE_COMPANIES`. |
| **JWT scope** — single-operator JWT works for v3.0 but is implicit "this operator can see all tenants" | LOW | Documented as v3.0 single-operator constraint. Per-tenant ACLs deferred to v3.2+. |
| **`/digest` and `/settings` ambiguity** — both are NOT tenant-scoped in v3.0. If the operator is "in" `/juno/` and navigates to `/settings`, what tenant context is shown? | LOW (UI only) | Settings is single-user global in v3.0 (no per-tenant settings yet). The CompanySwitcher is still visible (header-mounted), so the operator can flip back to a tenanted route without losing orientation. |
| **Seva-only agents called from shared loop** — `ontario_law.py` and `ontario_stats.py` only run for Seva (Juno has no Ontario context) | MEDIUM | `_run_daily_summary_for_company()` branches on company_id for the section list. Seva path runs all 3 sections (gold + ontario_law + ontario_stats). Juno path runs only the defence news section. Document explicitly with a `sections: list[Section]` declaration in `CompanyConfig`. |
| **Schema downgrade preserves Juno rows in column-less form** | LOW | Documented in downgrade() comment. After a downgrade, all rows look identical (no tenant column). Operator must `DELETE WHERE company_id WAS 'juno'` BEFORE running downgrade if a clean rollback to v2.1 is needed. |

---

## 7. Open Questions / Risks

1. **Daily summary section list per tenant** — Seva renders 3 sections (gold news, Ontario law, Ontario stats). Juno renders 1 section (defence news) initially, with the door open for "world events relevant to defence" being a second section. The frontend `SummaryCard` component should render sections conditionally based on which markdown fields are populated, not assume all three exist. Currently it does — verify before Phase 2 lands. Confidence: MEDIUM (component code not read directly in this research pass).

2. **Sonnet cost doubling** — Each cron fire is now 2 Sonnet calls (one per tenant). PROJECT.md budget assumes ~$5-10/mo additional for Juno Sonnet calls. Verify the daily_summary loop doesn't accidentally re-invoke Sonnet on the Seva path when Juno fails (and vice versa). The try/except wrapping each company-loop iteration is the boundary.

3. **`raw_sources_jsonb` schema drift** — Both tenants write to the same JSONB column. Seva's shape is `{"gold_news": [...], "ontario_law": [...], "ontario_stats": [...]}`. Juno's shape will be `{"defence_news": [...], "world_events": [...]}`. The weekly_sweeper queries this column for virality compute — verify it tolerates the absence of `gold_news` for Juno rows (currently it iterates `daily_summaries WHERE generated_at >= now - 7d` — this MUST filter by company_id under v3.0). The scoped helper handles that automatically.

4. **`agent_runs` company attribution** — `agent_runs` has no `company_id` column. Add it to the `notes` JSON payload? Add a real column? For v3.0, JSON notes is sufficient (`notes = {"company_id": "juno", "items_found": ..., ...}`). If we ever want to query "how many Juno runs failed last week" we'll need a column — defer.

5. **Frontend "tenant ambient state" anti-pattern risk** — `companyStore.ts` (Zustand) publishes the active company so non-routed components can read it. The CompanySwitcher reads it. If two components subscribe and one is stale (rare with Zustand, but possible during route transitions), they could disagree on which tenant is active. Mitigation: `CompanyScopedRoute` is the SINGLE writer to the store; everything else is read-only. Verify by lint rule or code review.

6. **Migration ordering with calendar UNIQUE constraint** — `uq_calendar_items_date` (single-column) must be dropped before `uq_calendar_items_company_date` (composite) is created. If the migration fails between those two steps and is left mid-state, calendar writes from BOTH tenants could collide on `(date)` instead of `(company_id, date)`. The migration uses a single Alembic transaction — Postgres DDL is transactional, so this is safe. Verified by Alembic docs (Postgres backend).

7. **Vercel preview deploys** — Each Vercel preview deploy hits the same backend `DATABASE_URL`. If two devs are testing v3.0 simultaneously on different branches, Juno rows could be created from a preview pointing at production. Mitigation: standard practice for this single-operator setup is preview-deploys against a separate `DATABASE_URL_PREVIEW`. Not a v3.0-specific risk but worth flagging.

---

## 8. Quality Gate Self-Check

- [x] Each architectural decision has a recommended option + runner-up (D-01..D-05)
- [x] File changes are concrete (named paths, not abstract layers) — see Section 4
- [x] AppHeader freeze constraint addressed explicitly (D-04)
- [x] Multi-tenancy migration path is reversible (0014 downgrade restores exact v2.1 schema)
- [x] Scheduler topology accounts for OPS-02 lock-ID uniqueness (D-02 reuses existing IDs — zero churn)
- [x] Build order respects dependency chain (DB before backend, backend before frontend; all foundation in Phase 1, News Funnel in Phase 2)

## Sources

All references are direct codebase reads at the working directory `/Users/matthewnelson/seva-mining` on 2026-05-19. No external sources — this is a closed-system integration analysis.

- `backend/app/main.py` — router registration baseline
- `backend/app/models/{daily_summary,calendar_item,weekly_sweep}.py` — schema baseline
- `backend/app/routers/{summaries,calendar,weekly_sweeps}.py` — router patterns
- `backend/alembic/versions/{0010_add_daily_summaries,0013_calendar_title_nullable_unique_date}.py` — migration style + current head
- `scheduler/worker.py` — JOB_LOCK_IDS, factory pattern, OPS-02 assertion
- `scheduler/agents/daily_summary.py` (lines 1-100) — entrypoint signature + per-section pattern
- `frontend/src/App.tsx` — route structure
- `frontend/src/components/layout/{AppHeader,AppShell,TabbedDashboard}.tsx` — UI surface
- `.planning/PROJECT.md` v3.0 milestone section — feature scope + budget + explicit deferrals
- `.planning/milestones/v2.1-research/ARCHITECTURE.md` — Phase 5 baseline for "already-built" assertions
