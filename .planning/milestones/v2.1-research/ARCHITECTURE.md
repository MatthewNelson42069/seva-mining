# v2.1 Three-Tab Content Engine — ARCHITECTURE Research

**Project:** seva-mining v2.1 Three-Tab Content Engine + UI Polish
**Mode:** Architecture (integration analysis)
**Confidence:** HIGH — all findings based on direct codebase reads
**Researched:** 2026-05-18

---

## Architecture Integration: v2.1 into seva-mining

### Existing Patterns Confirmed (HIGH confidence, read directly)

**Scheduler factory pattern** (`worker.py` lines 232-277): Every complex job uses a `_make_X_job(engine)` factory that closes over `engine`, defines an inner `async def job()` that does `async with engine.connect() as conn:` then calls `with_advisory_lock(conn, lock_id, name, run_fn)`. The actual agent function is imported lazily inside the inner job to avoid boot-time import costs. `weekly_sweeper` must follow this exactly.

**JOB_LOCK_IDS dict** (`worker.py` lines 100-113): Next free ID is `1019`. The dict has an ORM-level assertion at line 118 (`assert len(set(JOB_LOCK_IDS.values())) == len(JOB_LOCK_IDS)`) — adding `"weekly_sweeper": 1019` is sufficient; the assertion will catch any future collision at import time.

**Agent entrypoint signature** (`daily_summary.py` line 426): `async def run_daily_summary() -> None`. Takes no arguments. `run_weekly_sweeper()` must be the same shape — no params, called as a bare coroutine by `with_advisory_lock`.

**Idempotency guard pattern** (`daily_summary.py` lines 142-152): Query the target table for a recent row within `IDEMPOTENCY_WINDOW_MIN` before writing anything. For `weekly_sweeper`, query `weekly_sweeps WHERE generated_at >= (now - 60min) AND status IN ('running', 'completed')` using `week_start = sunday_of_current_week`. The window should be 60 min (wider than daily_summary's 30 min because the sweeper runs weekly — a Railway redeploy on Sunday morning is the failure scenario).

**agent_runs row lifecycle** (`daily_summary.py` lines 456-469): Insert with `status='running'` before any work. In `finally`, fetch fresh via `session.get(AgentRun, id)` and update `status`, `ended_at`, `items_found`, `items_queued`, `items_filtered`, `notes` (JSON string), `errors` (list of strings). The `reconcile_stale_runs()` in `worker.py` sweeps orphaned 'running' rows on restart.

**Telemetry into notes JSONB** (`daily_summary.py` lines 666-718): `fresh.notes = json.dumps(notes_payload)` where `notes_payload` is a flat dict of scalar telemetry. Per quick-260514-jny: per-section errors go into `fresh.errors = ["section: ExcType: message"]` — NOT just Railway logs.

**Sonnet timeout** (`daily_summary.py` line 502-504): `AsyncAnthropic(api_key=..., timeout=60.0)`. The weekly sweeper's Sonnet call must use the same `timeout=60.0` per the quick-260514-ii6 rationale (bull-thesis prompt structure; 60s gives headroom on heavy-news days).

**SQLAlchemy model style** (`scheduler/models/daily_summary.py`): `Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)`, `Column(DateTime(timezone=True), nullable=False)`, `Column(JSONB, nullable=True)`, FK to `agent_runs.id` with `ondelete="SET NULL"`. `__table_args__` tuple with `Index(...)`.

**Backend router style** (`summaries.py`): `APIRouter(prefix="/...", tags=["..."], dependencies=[Depends(get_current_user)])` at router level so all routes inherit auth. Use `select(Model).order_by(...).limit(...)` pattern. Return Pydantic `model_validate(r)` from ORM rows.

**Backend route registration** (`main.py` lines 53-63): Import router, call `app.include_router(...)` at module level. Two new lines needed for `calendar_router` and `weekly_sweeps_router`.

**Migration style** (`0010_add_daily_summaries.py`): Hand-written only. `op.create_table(...)` with explicit `sa.Column` definitions + `server_default=sa.text("gen_random_uuid()")` for UUID PKs. `op.create_check_constraint(...)` for status columns. `op.create_index(...)` separately. `downgrade()` reverses in exact reverse order. Never `--autogenerate`.

**Frontend API client pattern** (`summaries.ts`): TypeScript interface mirroring Pydantic schema, `async function getX()` calling `apiFetch<ResponseType>(url)`, `useX()` hook using `useQuery({queryKey, queryFn, refetchInterval, refetchOnWindowFocus, staleTime})`.

**Frontend route structure** (`App.tsx`): `<BrowserRouter>` → `<Routes>` → public `<Route path="/login">` + `<Route element={<ProtectedRoute />}>` wrapping `<Route element={<AppShell />}>` wrapping all authenticated routes. Keep `/queue`, `/agents/:slug`, `/digest`, `/settings` intact.

**AppShell** (`AppShell.tsx`): 12-line component. `AppHeader` then `<main className="flex-1 overflow-auto"><Outlet /></main>`. `<TabNav>` goes between `AppHeader` and `main`.

---

### Database Layer

**calendar_items schema:**

```sql
CREATE TABLE calendar_items (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    date         DATE NOT NULL,                      -- day-level, no time-of-day
    title        TEXT NOT NULL,
    notes_md     TEXT,                               -- nullable markdown, no size limit
    tag          VARCHAR(20),                        -- nullable; CHECK constraint below
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()  -- no DB-level ON UPDATE; app sets it
);
CREATE INDEX ix_calendar_items_date ON calendar_items (date);
CHECK CONSTRAINT: tag IN ('thread', 'video', 'podcast', 'tweet', 'idea', 'other')
```

Note on `updated_at`: Postgres does not have `ON UPDATE` for columns (that is MySQL syntax). The application layer must set `updated_at=datetime.utcnow()` on every PATCH. The migration uses `server_default=sa.text("now()")` and the PATCH handler sets it explicitly. Do not use a Postgres trigger — consistent with the existing codebase which has no triggers.

**weekly_sweeps schema:**

```sql
CREATE TABLE weekly_sweeps (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    generated_at      TIMESTAMPTZ NOT NULL,
    week_start        DATE NOT NULL,                 -- Sunday of the week
    week_end          DATE NOT NULL,                 -- Saturday (Sun-Sat window)
    reddit_top_md     TEXT,
    story_virality_md TEXT,
    content_angles_md TEXT,
    raw_sources_jsonb JSONB,
    status            VARCHAR(20) NOT NULL DEFAULT 'completed',
    error_text        TEXT,
    agent_run_id      UUID REFERENCES agent_runs(id) ON DELETE SET NULL
);
CREATE INDEX ix_weekly_sweeps_generated_at ON weekly_sweeps (generated_at DESC);
CHECK CONSTRAINT: status IN ('completed', 'failed', 'partial')
```

**Week boundary convention:** Sun-Sat. `week_start` = Sunday 00:00 of the firing week (LA local date), `week_end` = Saturday of the same week. This is consistent with cron firing Sunday 08:00 PT — the sweeper summarizes the week just ending (Mon-Sat) plus Sunday itself. When the Sunday cron fires, `week_start = now_la.date()` and `week_end = week_start + timedelta(days=6)`.

**Markdown rendering:** Render client-side. The frontend already renders `gold_news_md`, `ontario_law_md`, `ontario_stats_md` client-side. `reddit_top_md`, `story_virality_md`, `content_angles_md` follow the same pattern — store raw markdown in Postgres, render in React with a markdown renderer.

**Migration ordering:** Two separate migrations. `0011_add_calendar_items.py` first, `0012_add_weekly_sweeps.py` second. Rationale: `weekly_sweeps` has no dependency on `calendar_items`, but splitting keeps each migration atomic and independently reversible.

---

### Dual-Model Parity

Both new DB tables need SQLAlchemy models in TWO locations (established Phase B precedent):

- `scheduler/models/calendar_item.py` — used by any scheduler code that reads/writes calendar (currently none in v2.1, but parity is required by convention)
- `scheduler/models/weekly_sweep.py` — used by `weekly_sweeper.py`
- `backend/app/models/calendar_item.py` — used by calendar CRUD router
- `backend/app/models/weekly_sweep.py` — used by weekly-sweeps read router

Both model files import from their local `models/base.py`. Models are structurally identical between scheduler and backend; they are not shared modules because the two Railway services are separate Python processes with separate dependencies.

---

### Scheduler Layer

**Lock ID:** Add `"weekly_sweeper": 1019` to `JOB_LOCK_IDS` dict in `worker.py`. The existing uniqueness assertion at line 118 will catch any collision at module import time.

**Factory function:** `_make_weekly_sweeper_job(engine)` — same shape as `_make_daily_summary_job`. Lazy import of `run_weekly_sweeper` inside the inner `async def job()`.

**Registration:** In `build_scheduler()` (after the `daily_summary_prune` block), add:
```python
scheduler.add_job(
    _make_weekly_sweeper_job(engine),
    trigger=CronTrigger(
        day_of_week='sun',
        hour=8,
        minute=0,
        timezone='America/Los_Angeles',
    ),
    id="weekly_sweeper",
    name="Weekly Viral Sweeper — 08:00 Sunday America/Los_Angeles",
)
```
`CronTrigger(day_of_week='sun', hour=8, minute=0, timezone='America/Los_Angeles')` is the correct APScheduler 3.x format.

**`reddit_ingest.py` placement:** Separate module `scheduler/agents/reddit_ingest.py`. Rationale: mirrors how `content_agent.py` is a separate ingestion module called by `daily_summary.py`. Keeping Reddit ingestion isolated makes it testable independently and keeps `weekly_sweeper.py` readable.

**`weekly_sweeper.py` structure:**
```python
async def run_weekly_sweeper() -> None:
    # 1. Idempotency check against weekly_sweeps table
    # 2. Insert agent_runs row (status='running')
    # 3. Fetch Reddit posts via reddit_ingest.fetch_reddit_posts()
    # 4. Compute story virality via _compute_virality() — queries daily_summaries
    # 5. Sonnet call: content angles (timeout=60.0, same as daily_summary)
    # 6. Compose status (completed/partial/failed)
    # 7. Insert weekly_sweeps row
    # 8. In finally: update agent_runs telemetry
```

**Story virality query:** Query `daily_summaries.raw_sources_jsonb` for the past 7 days' `gold_news` arrays. Extract all `.link` values. Group by URL similarity (SequenceMatcher threshold 0.85, same as existing `deduplicate_stories()` in `content_agent.py`). Stories appearing in ≥3 summaries are "viral". This is a pure Python computation over JSONB data — no new DB schema needed.

**`reddit_ingest.py` signature:**
```python
async def fetch_reddit_posts(
    subreddits: list[str],
    limit: int = 10,
    time_filter: str = "week",
) -> list[dict]:
    ...
```
Returns list of `{"title", "url", "score", "num_comments", "subreddit", "permalink"}` dicts. Uses `asyncpraw.Reddit(...)` in read-only mode (no user credentials needed — client_credentials flow with `REDDIT_CLIENT_ID` + `REDDIT_CLIENT_SECRET` + `REDDIT_USER_AGENT`). `asyncpraw` is recommended over `praw` (async-native, same API surface, avoids executor wrapping).

**Subreddits to target:** `r/Gold`, `r/Wallstreetsilver`, `r/silverbugs`, `r/investing` (gold filter), `r/Economics` (macro). Hardcode in `weekly_sweeper.py` constants — not DB-configurable in v2.1.

---

### Backend / API Layer

**`backend/app/routers/calendar.py`:**
```python
router = APIRouter(
    prefix="/calendar",
    tags=["calendar"],
    dependencies=[Depends(get_current_user)],
)

@router.get("", response_model=CalendarRangeResponse)
async def list_calendar_items(
    start: date = Query(...),
    end: date = Query(...),
    db: AsyncSession = Depends(get_db),
) -> CalendarRangeResponse:
    # SELECT * FROM calendar_items WHERE date BETWEEN start AND end ORDER BY date ASC

@router.post("", response_model=CalendarItemResponse, status_code=201)
async def create_calendar_item(
    body: CalendarItemCreate,
    db: AsyncSession = Depends(get_db),
) -> CalendarItemResponse:

@router.patch("/{item_id}", response_model=CalendarItemResponse)
async def update_calendar_item(
    item_id: UUID,
    body: CalendarItemUpdate,
    db: AsyncSession = Depends(get_db),
) -> CalendarItemResponse:
    # Partial update: only set fields where body.field is not None
    # Must set updated_at = datetime.utcnow() explicitly

@router.delete("/{item_id}", status_code=204)
async def delete_calendar_item(
    item_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
```

**`backend/app/schemas/calendar.py`:**
```python
class CalendarItemBase(BaseModel):
    date: date
    title: str
    notes_md: str | None = None
    tag: Literal['thread', 'video', 'podcast', 'tweet', 'idea', 'other'] | None = None

class CalendarItemCreate(CalendarItemBase):
    pass

class CalendarItemUpdate(BaseModel):
    model_config = ConfigDict(extra='ignore')
    date: date | None = None
    title: str | None = None
    notes_md: str | None = None
    tag: Literal['thread', 'video', 'podcast', 'tweet', 'idea', 'other'] | None = None

class CalendarItemResponse(CalendarItemBase):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    created_at: datetime
    updated_at: datetime

class CalendarRangeResponse(BaseModel):
    items: list[CalendarItemResponse]
    total: int
```

**`backend/app/routers/weekly_sweeps.py`:**
```python
router = APIRouter(
    prefix="/weekly-sweeps",
    tags=["weekly-sweeps"],
    dependencies=[Depends(get_current_user)],
)

@router.get("", response_model=WeeklySweepFeedResponse)
async def list_weekly_sweeps(
    limit: int = Query(12, ge=1, le=52),
    db: AsyncSession = Depends(get_db),
) -> WeeklySweepFeedResponse:
    # SELECT * FROM weekly_sweeps ORDER BY generated_at DESC LIMIT limit
```

**`backend/app/schemas/weekly_sweep.py`:**
```python
class WeeklySweepCard(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    generated_at: datetime
    week_start: date
    week_end: date
    reddit_top_md: str | None
    story_virality_md: str | None
    content_angles_md: str | None
    status: Literal['completed', 'failed', 'partial']
    error_text: str | None

class WeeklySweepFeedResponse(BaseModel):
    sweeps: list[WeeklySweepCard]
    total: int
```

**`main.py` additions:**
```python
from app.routers.calendar import router as calendar_router
from app.routers.weekly_sweeps import router as weekly_sweeps_router
# ...
app.include_router(calendar_router)     # v2.1 Content Calendar CRUD
app.include_router(weekly_sweeps_router)  # v2.1 Weekly Viral Sweeper feed
```

---

### Frontend Layer

**Route restructure in `App.tsx`:**

The current `/` → `<SummaryFeedPage>` becomes the tab container. Cleanest approach: introduce a `<TabbedDashboard>` component at `/` that renders `<TabNav>` + `<Outlet>`, with sub-routes `/`, `/calendar`, `/viral`. React Router `<NavLink>` handles active-state URL tracking; shadcn `Tabs` handles visual active-state styling.

```tsx
// App.tsx after restructure
<Route element={<AppShell />}>
  {/* Tab container — "/" renders TabbedDashboard with default tab */}
  <Route element={<TabbedDashboard />}>
    <Route index element={<SummaryFeedPage />} />          // Tab 1: News Funnel
    <Route path="calendar" element={<ContentCalendarPage />} />  // Tab 2
    <Route path="viral" element={<WeeklyViralSweeperPage />} />  // Tab 3
  </Route>

  {/* Unchanged v2.0 routes */}
  <Route path="/queue" element={<Navigate to="/" replace />} />
  <Route path="/agents/:slug" element={<Navigate to="/" replace />} />
  <Route path="/digest" element={<DigestPage />} />
  <Route path="/settings" element={<SettingsPage />} />
</Route>
```

`TabbedDashboard` is a thin wrapper that renders `<TabNav />` then `<Outlet />` — analogous to how `AppShell` renders `<AppHeader />` then `<Outlet />`. `AppShell` itself does NOT need a `<TabNav>` insertion — tabs only appear inside the main 3-tab surface, not on `/digest` or `/settings`.

**shadcn Tabs vs React Router NavLink:** Use React Router `<NavLink>` for the tab strip, styled to look like shadcn Tabs. Reason: actual URL routing per tab makes bookmarking work and browser back/forward work. shadcn `Tabs` component is a controlled component (tracks active state internally) — combining it with URL routing requires lifting state up and syncing with router, which adds complexity. NavLink with Tailwind styling matching shadcn's tab visual is simpler and more correct.

**`AppShell.tsx` change:** No structural change needed.

**`SummaryFeedPage.tsx` change:** No functional change. The page renders inside the tab container and its `max-w-[720px] mx-auto` width constraint continues to work inside `<Outlet>`.

---

### New Frontend Files

| File | Purpose |
|------|---------|
| `frontend/src/components/layout/TabbedDashboard.tsx` | Thin wrapper: `<TabNav />` + `<Outlet />` |
| `frontend/src/components/layout/TabNav.tsx` | Tab strip: NavLink × 3, active-state via `isActive` className |
| `frontend/src/pages/ContentCalendarPage.tsx` | Weekly grid + item management |
| `frontend/src/pages/WeeklyViralSweeperPage.tsx` | Current sweep card + history list |
| `frontend/src/components/calendar/WeeklyGrid.tsx` | 7-column week grid, renders `CalendarItem` slots |
| `frontend/src/components/calendar/CalendarItemDialog.tsx` | Add/edit modal (shadcn `Dialog` primitive) |
| `frontend/src/components/calendar/CalendarItem.tsx` | Individual day-cell item chip |
| `frontend/src/components/viral/SweeperCard.tsx` | Weekly sweep card (3 markdown sections) |
| `frontend/src/api/calendar.ts` | `getCalendar`, `createCalendarItem`, `updateCalendarItem`, `deleteCalendarItem`, `useCalendar()` |
| `frontend/src/api/weeklySweeps.ts` | `getWeeklySweeps`, `useWeeklySweeps()` |

**`calendar.ts` hook pattern:**
```typescript
export function useCalendar(start: string, end: string) {
  return useQuery({
    queryKey: ['calendar', start, end],
    queryFn: () => getCalendar(start, end),
    staleTime: 0,              // calendar items are user-mutated — no stale tolerance
    refetchOnWindowFocus: false,
  })
}
// Plus useMutation hooks for create/update/delete with optimistic updates
```

**Drag-and-drop decision:** Use date-dropdown fallback (not `@dnd-kit/core`). The PROJECT.md explicitly flags DnD complexity. For a single-user internal tool with a weekly grid, a date-picker dropdown on each item is functionally equivalent with zero additional dependencies. `@dnd-kit/core` is ~20KB gzipped and adds non-trivial implementation complexity for minimal UX gain in this context.

---

### Phase Build Order Recommendation

**Recommended: Foundation-first (DB + routes + shell, then features, UI polish last)**

**Phase 1 — Foundation (DB + API scaffolding + frontend shell):**
- Migrations 0011 + 0012
- Dual-model parity for both new tables (4 new model files)
- `JOB_LOCK_IDS["weekly_sweeper"] = 1019` in worker.py
- Backend schemas + router stubs (GET returns empty list, POST returns 501)
- `main.py` router registration
- `App.tsx` route restructure with stub pages
- `TabbedDashboard` + `TabNav` components
- `AppShell.tsx` unchanged (no modification needed)
- Stub `ContentCalendarPage` + `WeeklyViralSweeperPage` (renders "Coming soon")

**Why first:** DB migrations must precede any feature work. Route restructure must precede both calendar and sweeper UI. Doing this in Phase 1 means Phases 2 and 3 can be developed without restructuring. The stub pages confirm routing works before adding business logic.

**Phase 2 — Content Calendar (self-contained CRUD feature):**
- Full calendar router (GET/POST/PATCH/DELETE) + Pydantic schemas
- `WeeklyGrid.tsx` + `CalendarItemDialog.tsx` + `CalendarItem.tsx`
- `calendar.ts` API client + TanStack Query hooks (including mutations with optimistic updates)
- `ContentCalendarPage.tsx` with live data

**Why second:** Calendar is pure CRUD — no scheduler changes, no Sonnet, no new env vars. Highest confidence of the two new features. Ships value immediately.

**Phase 3 — Weekly Viral Sweeper (scheduler + Reddit + Sonnet):**
- `asyncpraw` install in `scheduler/requirements.txt` + `REDDIT_CLIENT_ID/SECRET/USER_AGENT` env vars
- `reddit_ingest.py` module
- `weekly_sweeper.py` agent (full orchestration matching daily_summary.py style)
- `_make_weekly_sweeper_job(engine)` factory + `build_scheduler()` registration
- `weeklySweeps.ts` API client + hook
- `WeeklyViralSweeperPage.tsx` + `SweeperCard.tsx` with live data

**Why third:** Has external dependency (Reddit API setup), scheduler changes, and the most complex business logic (virality compute + Sonnet). Sequencing after Calendar means the full backend is live before tackling the hardest feature.

**Phase 4 — UI Polish + Cleanup:**
- Linear-style aesthetic pass: color tokens, typography, hover states, border refinements
- Remove dead-code v1.0 content sub-agent source files (strip per the "strip in v2.1+" comments throughout worker.py)
- Visual QA pass across all 3 tabs

**Why last:** UI polish is inherently iterative and cannot be "done" until all features exist to polish. Doing it first (the alternative ordering) means polishing stub pages that will be replaced, wasting effort. The dead-code strip belongs here because it requires confidence that nothing references the deleted files.

---

### Complete File Change Map

**NEW files:**

```
scheduler/
  agents/
    reddit_ingest.py          (Reddit asyncpraw wrapper)
    weekly_sweeper.py         (run_weekly_sweeper entrypoint)
  models/
    calendar_item.py          (CalendarItem SQLAlchemy model)
    weekly_sweep.py           (WeeklySweep SQLAlchemy model)

backend/
  alembic/versions/
    0011_add_calendar_items.py
    0012_add_weekly_sweeps.py
  app/
    models/
      calendar_item.py
      weekly_sweep.py
    routers/
      calendar.py
      weekly_sweeps.py
    schemas/
      calendar.py
      weekly_sweep.py

frontend/src/
  components/
    layout/
      TabbedDashboard.tsx
      TabNav.tsx
    calendar/
      WeeklyGrid.tsx
      CalendarItemDialog.tsx
      CalendarItem.tsx
    viral/
      SweeperCard.tsx
  pages/
    ContentCalendarPage.tsx
    WeeklyViralSweeperPage.tsx
  api/
    calendar.ts
    weeklySweeps.ts
```

**MODIFIED files:**

```
scheduler/worker.py
  - JOB_LOCK_IDS: add "weekly_sweeper": 1019
  - build_scheduler(): add _make_weekly_sweeper_job registration
  - Add _make_weekly_sweeper_job(engine) factory function

backend/app/main.py
  - Import calendar_router + weekly_sweeps_router
  - app.include_router() × 2

frontend/src/App.tsx
  - Add TabbedDashboard import
  - Restructure routes: nest SummaryFeedPage + 2 new pages under TabbedDashboard
  - Add /calendar and /viral Route entries
  - Preserve all existing routes intact
```

**UNCHANGED files (confirmed):**
- `AppShell.tsx` — no modification needed (TabbedDashboard handles tabs)
- `AppHeader.tsx` — no modification needed
- `SummaryFeedPage.tsx` — no functional change; renders inside Outlet
- `summaries.py` router — no change
- All v1.0 dead-code files — strip deferred to Phase 4

---

### Open Questions / Risks

1. **`asyncpraw` vs `praw` + executor:** `asyncpraw` is the recommended choice (async-native, same API as praw). Verify Python 3.12 compatibility before Phase 3 begins.

2. **Reddit API rate limits:** Public read-only OAuth client credentials flow is free but rate-limited at 60 requests/minute. A weekly cron fetching 10 posts per subreddit (5 subreddits = 5 requests) is well within limits.

3. **Story virality query performance:** `SELECT raw_sources_jsonb FROM daily_summaries WHERE generated_at >= now() - interval '7 days'` returns ~14 rows (2/day × 7 days). JSONB extraction in Python over 14 rows is negligible. No index needed beyond existing `ix_daily_summaries_generated_at`.

4. **`updated_at` on `calendar_items`:** No DB-level trigger; application must set it. Forgetting in any PATCH handler is a silent bug. The Pydantic `CalendarItemUpdate` schema should NOT set `updated_at` — the router handler sets it explicitly so it is never accidentally omitted.

5. **shadcn Tabs install:** The Tailwind v4 branch of shadcn is already confirmed in v2.0 (`CLAUDE.md` stack section). Adding the `Tabs` component: `npx shadcn@latest add tabs`. Confirm this works on the existing shadcn v4 installation before Phase 1 code lands.
