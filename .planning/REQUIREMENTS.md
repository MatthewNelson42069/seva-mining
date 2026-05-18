# Requirements: Seva Mining v2.1 — Three-Tab Content Engine + UI Polish

**Defined:** 2026-05-18
**Core Value:** Every piece of content the system produces or surfaces must be genuinely valuable to the gold conversation it enters — a data point, an insight, a connection no one else made. For v2.1 this expands beyond the v2.0 News Funnel into two new surfaces: a personal Content Calendar for planning what to publish, and a Weekly Viral Sweeper that surfaces what's getting traction in Reddit gold/silver communities plus the most cross-referenced news stories of the past 7 days — giving the operator a tactical content-strategy lens, not just an intelligence digest.

## v2.1 Requirements

Each requirement maps to exactly one phase. Categories follow the research SUMMARY.md phase build order.

### Tab Navigation Infrastructure (TAB)

The 3-tab shell that wraps News Funnel (Tab 1) + Content Calendar (Tab 2) + Weekly Viral Sweeper (Tab 3). Foundation for everything else.

- [ ] **TAB-01**: System installs the shadcn `Tabs` Radix primitive into `frontend/src/components/ui/` via `npx shadcn@latest add tabs` (Tailwind v4 branch); commits the resulting `tabs.tsx` component file alongside existing shadcn primitives
- [ ] **TAB-02**: System introduces `frontend/src/components/layout/TabbedDashboard.tsx` — a thin wrapper rendering `<TabNav />` then `<Outlet />` (analogous to AppShell rendering AppHeader + Outlet); placed under the existing `<AppShell />` route so tabs only appear inside the 3-tab surface, NOT on `/digest` or `/settings`
- [ ] **TAB-03**: System introduces `frontend/src/components/layout/TabNav.tsx` — a tab strip of 3 React Router `<NavLink>` elements styled to match shadcn Tabs visually; active-state driven by `useLocation()` (NEVER by local state) so browser Back/Forward navigation updates the tab highlight correctly
- [ ] **TAB-04**: System restructures `frontend/src/App.tsx` routes so `/` (index), `/calendar`, and `/viral` are nested children under `<TabbedDashboard />`; preserves all existing routes intact (`/queue`, `/agents/:slug`, `/digest`, `/settings`, `/login` + `Navigate` redirects)
- [ ] **TAB-05**: System leaves `frontend/src/components/layout/AppShell.tsx` and `AppHeader.tsx` structurally unchanged — TabbedDashboard handles the tab nav; existing wordmark + Log out button stay in AppHeader

### Database + Backend Foundation (DB)

Alembic migrations and dual-model parity for the two new tables. Backend router stubs (200 OK, empty payload) so frontend can develop against live endpoints.

- [ ] **DB-01**: System adds Alembic migration `0011_add_calendar_items.py` creating table `calendar_items` with columns: `id UUID PK gen_random_uuid()`, `date DATE NOT NULL` (Date, not DateTime), `title TEXT NOT NULL`, `notes_md TEXT NULL`, `tag VARCHAR(20) NULL` with CHECK `tag IN ('thread','video','podcast','tweet','idea','other')`, `created_at`/`updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`, index `ix_calendar_items_date` on `date`
- [ ] **DB-02**: System adds Alembic migration `0012_add_weekly_sweeps.py` creating table `weekly_sweeps` with columns: `id UUID PK`, `generated_at TIMESTAMPTZ NOT NULL`, `week_start DATE NOT NULL`, `week_end DATE NOT NULL`, `reddit_top_md TEXT NULL`, `story_virality_md TEXT NULL`, `content_angles_md TEXT NULL`, `raw_sources_jsonb JSONB NULL`, `status VARCHAR(20) NOT NULL DEFAULT 'completed'` with CHECK `status IN ('completed','failed','partial')`, `error_text TEXT NULL`, `agent_run_id UUID FK agent_runs.id ON DELETE SET NULL`, index `ix_weekly_sweeps_generated_at` on `(generated_at DESC)`
- [ ] **DB-03**: System creates dual-model parity — SQLAlchemy 2.0 model files `backend/app/models/calendar_item.py`, `backend/app/models/weekly_sweep.py`, `scheduler/models/calendar_item.py`, `scheduler/models/weekly_sweep.py`; structurally identical, each imports from its local `models/base.py`
- [ ] **DB-04**: System registers backend routes by adding `app.include_router(calendar_router)` and `app.include_router(weekly_sweeps_router)` to `backend/app/main.py`; both routers carry `dependencies=[Depends(get_current_user)]` at the router level so they inherit the existing JWT auth gate
- [ ] **DB-05**: System verifies `alembic heads` returns exactly one head before both migrations land; each migration sets the prior head as `down_revision`; `alembic upgrade head` + `alembic downgrade -1` round-trips cleanly in dev before commit

### Content Calendar (CAL)

Pure CRUD over `calendar_items`. Weekly grid UI (Mon-Sun) with click-to-edit. Date dropdown reschedule (no DnD). Optimistic mutations with rollback.

- [ ] **CAL-01**: System exposes `GET /calendar?start=YYYY-MM-DD&end=YYYY-MM-DD` returning `{items: CalendarItemResponse[], total: int}` ordered by `date ASC`; date params are `datetime.date` Pydantic fields parsed from `YYYY-MM-DD` strings (NEVER datetime — TZ off-by-one risk on Railway UTC)
- [ ] **CAL-02**: System exposes `POST /calendar` accepting `{date, title, notes_md?, tag?}` and returning `201 + CalendarItemResponse`; `tag` is a Pydantic `Literal['thread','video','podcast','tweet','idea','other'] | None`; backend writes `created_at = updated_at = datetime.utcnow()` explicitly
- [ ] **CAL-03**: System exposes `PATCH /calendar/{item_id}` accepting partial fields and returning `200 + CalendarItemResponse`; handler MUST set `updated_at = datetime.utcnow()` explicitly (not via DB trigger; `updated_at` is NOT exposed in the `CalendarItemUpdate` Pydantic schema)
- [ ] **CAL-04**: System exposes `DELETE /calendar/{item_id}` returning `204 No Content`; hard delete (no soft-delete column); `404` if not found
- [ ] **CAL-05**: System renders `ContentCalendarPage.tsx` with a 7-column weekly grid (Mon-Sun ISO week start) showing the current week by default, prev/next-week arrow navigation, and a "today" jump button; today cell highlighted via `ring-2 ring-amber-500 bg-amber-500/5`
- [ ] **CAL-06**: System renders calendar items as chips inside their day cell with tag-color-coded backgrounds (fixed Tailwind utility map: thread=blue, video=red, podcast=purple, image=green, article=amber, idea=zinc); clips at 3 items per cell with "+N more" overflow badge
- [ ] **CAL-07**: System renders a "+ Add" hover-reveal button on empty cells (`opacity-0 group-hover:opacity-100 transition-opacity`); click opens the create/edit dialog with the day pre-populated
- [ ] **CAL-08**: System renders an edit dialog (shadcn `Dialog`) when an item is clicked or a "+ Add" button fires, with fields: title text input, date `<select>` dropdown (for reschedule — NOT drag-and-drop), tag dropdown, markdown notes `<textarea>` (no editor library; plain textarea + on-save react-markdown render preview optional)
- [ ] **CAL-09**: System mutates calendar items via TanStack Query mutations with optimistic updates: `onMutate` snapshots query cache, applies optimistic write; `onError` restores the snapshot; `onSettled` invalidates `['calendar', start, end]` so the next refetch is authoritative
- [ ] **CAL-10**: System uses `staleTime: 0` + `refetchOnWindowFocus: false` on `useCalendar()` — calendar items are user-mutated, no stale tolerance, but no auto-refetch on tab switching either

### Weekly Viral Sweeper (SWEEP)

Sunday 08:00 PT cron, advisory lock 1019. Reddit ingestion via asyncpraw. Story virality compute over the past 7 days of `daily_summaries.raw_sources_jsonb.gold_news`. Sonnet generates 3 content angles. Frontend renders the latest sweep + history list.

- [ ] **SWEEP-01**: System adds `asyncpraw>=7.8.1` to `scheduler/pyproject.toml` (NOT `praw` — sync blocks AsyncIOScheduler event loop)
- [ ] **SWEEP-02**: System adds three env vars to Railway: `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USER_AGENT` (set per user setup at reddit.com/prefs/apps with type "script"); `REDDIT_USER_AGENT` defaults to `"SevaMiningSweeper/1.0 by sevabot"` if user has no preference
- [ ] **SWEEP-03**: System adds `"weekly_sweeper": 1019` to the `JOB_LOCK_IDS` dict in `scheduler/worker.py` **as the first task of the sweeper phase** — must precede any other weekly_sweeper code so the OPS-02 uniqueness assertion at line 118 can guard against collisions
- [ ] **SWEEP-04**: System creates `scheduler/agents/reddit_ingest.py` exposing `async def fetch_reddit_posts(subreddits: list[str], limit: int = 10, time_filter: str = "week") -> list[dict]`; uses `asyncpraw.Reddit(client_id=..., client_secret=..., user_agent=..., requestor_kwargs={"timeout": 15})` with `read_only = True`; wraps each `subreddit.top()` call in try/except so a single failing subreddit degrades gracefully (partial results > all-or-nothing)
- [ ] **SWEEP-05**: System fetches from 4 subreddits hardcoded in `weekly_sweeper.py`: `["gold", "Wallstreetsilver", "silverbugs", "Gold_and_Silver"]`; per-subreddit limit 10, time_filter "week"; each returned post dict has keys `{title, url, score, num_comments, subreddit, permalink}`
- [ ] **SWEEP-06**: System creates `scheduler/agents/weekly_sweeper.py` exposing `async def run_weekly_sweeper() -> None` that follows the daily_summary.py orchestration shape: idempotency check → `agent_runs` insert (status='running') → Reddit fetch → virality compute → Sonnet call → status mapping → `weekly_sweeps` INSERT → telemetry in `finally`
- [ ] **SWEEP-07**: System computes story virality by querying `daily_summaries` for `generated_at >= now() - INTERVAL '7 days' AND status IN ('completed','partial')`, flattening `raw_sources_jsonb.gold_news[]` (guarding `(row.raw_sources_jsonb or {}).get("gold_news", [])` against NULL on failed rows), canonicalizing each `link` (strip UTM/fbclid/gclid/ref params, lowercase host, sort query, no trailing slash), grouping by canonical URL, and returning top 5 stories sorted by distinct-source-name count DESC
- [ ] **SWEEP-08**: System calls `claude-sonnet-4-6` with `AsyncAnthropic(api_key=..., timeout=60.0)`, max_tokens=1000, with the tactical content-strategist system prompt that generates exactly 3 content angles each connecting a Reddit signal with a mainstream news signal; if `len(reddit_posts) < 3 OR len(viral_stories) < 3`, skip the Sonnet call and write "Insufficient signal this week — angles not generated" into `content_angles_md` (grounding guard against hallucination on sparse weeks)
- [ ] **SWEEP-09**: System registers the cron in `scheduler/worker.py` `build_scheduler()` via `_make_weekly_sweeper_job(engine)` factory (mirroring `_make_daily_summary_job`), using `CronTrigger(day_of_week='sun', hour=8, minute=0, timezone='America/Los_Angeles')`, with `id="weekly_sweeper"`, `max_instances=1`, `misfire_grace_time=1800`
- [ ] **SWEEP-10**: System idempotency-guards each fire by checking for an existing `weekly_sweeps` row with `week_start = sunday_of_this_week` and `status IN ('running','completed')` within a 60-minute window; on hit, log `idempotency_skip` and exit cleanly
- [ ] **SWEEP-11**: System sets `weekly_sweeps.status` to `'completed'` when Reddit + virality + Sonnet all succeed, `'partial'` when at least one of (Reddit, virality, Sonnet) fails but the row can still render with empty-state copy in the failed section, `'failed'` only when Reddit ingestion crashes before any output can be assembled; per-section errors written into `agent_runs.errors` list (post-jny pattern)
- [ ] **SWEEP-12**: System exposes `GET /weekly-sweeps?limit=12` returning `{sweeps: WeeklySweepCard[], total: int}` ordered by `generated_at DESC`; query param `limit` clamped to `ge=1, le=52`
- [ ] **SWEEP-13**: System renders `WeeklyViralSweeperPage.tsx` showing the latest sweep card by default and a history-week-picker for browsing prior weeks; sweep card renders three sections via react-markdown: "Top Reddit Posts This Week", "Most Cross-Referenced Stories", "3 Content Angles"
- [ ] **SWEEP-14**: System renders empty-state copy "Sweeper has not run yet — first fire scheduled for Sunday {next_sunday} 08:00 PT." when `GET /weekly-sweeps` returns `total: 0`; renders status-specific banner copy (failed: "Sweeper failed last run — see telemetry", partial: "Sweeper had partial output — some sections may be empty") on cards with non-completed status

### UI Polish (UI)

Linear-style dark theme with amber-500 accents applied across all 3 tabs. Existing Geist font stays. Dead-code v1.0 strip happens here.

- [ ] **UI-01**: System applies the amber-gold accent (`amber-500` / `amber-400`) to: active tab indicator in TabNav, primary CTA buttons, status badges on summary cards, today-cell highlight in calendar, accent borders on hover states; preserves dark theme baseline (zinc-950/zinc-900/zinc-800 hierarchy)
- [ ] **UI-02**: System refines spacing tokens — generous whitespace inside cards (`p-6` minimum), `gap-6` between card sections, `space-y-4` between section bullets in markdown rendering; matches the Linear/Vercel dashboard density target
- [ ] **UI-03**: System refines typography weights using existing Geist Variable font — headings 600, sub-headings 500, body 400, monospace numerics for upvote counts (Reddit posts) and source counts (virality stories); NO font swap to Inter
- [ ] **UI-04**: System refines subtle borders + hover states on all cards using `border border-zinc-800` baseline + `hover:border-zinc-700` transition; consistent across summary cards, calendar items, sweep card sections
- [ ] **UI-05**: System renders subreddit attribution on Reddit posts as monospace-styled pills (e.g., `r/gold` in `font-mono text-xs bg-zinc-800/60 px-2 py-0.5 rounded`)
- [ ] **UI-06**: System strips v1.0 dead-code content sub-agent source files (`scheduler/agents/content/*.py` for retired formats + dead-code lock-ID dict entries 1010-1016 + comments referencing them) once Phases 5-7 are merged and verifier confirms no surviving callers; runs as the final task of Phase 8
- [ ] **UI-07**: System completes a visual QA pass across all 3 tabs at desktop resolution (1440x900 minimum) — confirms no layout regressions, no dark-mode contrast failures (WCAG AA on text), and no broken shadcn primitive interactions; intentionally skips mobile-responsive (out of scope per single-user desktop constraint)

## v2.2+ Requirements

Deferred to future release. Tracked but NOT in v2.1 roadmap.

### Calendar Enhancements

- **CAL-DnD-v22**: Drag-and-drop calendar item reschedule via `@dnd-kit/core` (deferred — date dropdown ships in v2.1; revisit if user reports the dropdown feels slow)
- **CAL-WHATSAPP-v22**: Morning WhatsApp ping listing items planned for today (default off; user opts in via Settings)

### Sweeper Enhancements

- **SWEEP-WHATSAPP-v22**: Sunday-morning WhatsApp delivery of the weekly sweep card (deferred — web tab is primary surface for v2.1)
- **SWEEP-WSB-v22**: Cross-subreddit gold keyword filter on r/wallstreetbets / r/investing / r/stocks (keyword post-filter after `limit=100` fetch) — explored only if v2.1 sweeper signal needs broadening
- **SWEEP-FRED-v22**: Live FRED macro stat indicators in Tab 1 (deferred from v2.0 — would augment but not replace the existing Macro Economic Stats section)
- **SWEEP-KITCO-v22**: Kitco analyst-content scraping (deferred from v2.0 — augments Analyst & Bank Predictions section in Tab 1)
- **SWEEP-X-v22**: X/Twitter ingestion for gold-analyst accounts (deferred — would require X API revival)

## Out of Scope

Explicitly excluded from v2.1. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| AI content drafting (sub-agent revival) | v1.0 sub-agents retired and stay retired; v2.1 Calendar is plain-text personal planning |
| Autoposting to X / IG / LinkedIn / anywhere | Hard prohibition per CLAUDE.md; Phase B stays dormant |
| Phase B post-to-X reactivation | Out of v2.1 scope; user-initiated approve→post remains gated by `X_POSTING_ENABLED` env var unchanged |
| Instagram / LinkedIn integration | Not in user's content workflow per locked v2.1 decision |
| Mobile-responsive UI | Single-user desktop-only constraint preserved from v1.0 |
| Reddit comment ingestion | Top comments add disproportionate complexity for marginal value in a weekly summary |
| `r/wallstreetbets` direct subreddit ingestion | Signal-to-noise unacceptable at `limit=10` per FEATURES.md viability table |
| Drag-and-drop calendar reschedule | High complexity-to-value for single-user; date dropdown is functionally equivalent |
| Custom Tailwind color palette overhaul | Existing zinc + amber palette is the locked direction; no broader theming work |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| TAB-01 | Phase 5 | Pending |
| TAB-02 | Phase 5 | Pending |
| TAB-03 | Phase 5 | Pending |
| TAB-04 | Phase 5 | Pending |
| TAB-05 | Phase 5 | Pending |
| DB-01 | Phase 5 | Pending |
| DB-02 | Phase 5 | Pending |
| DB-03 | Phase 5 | Pending |
| DB-04 | Phase 5 | Pending |
| DB-05 | Phase 5 | Pending |
| CAL-01 | Phase 6 | Pending |
| CAL-02 | Phase 6 | Pending |
| CAL-03 | Phase 6 | Pending |
| CAL-04 | Phase 6 | Pending |
| CAL-05 | Phase 6 | Pending |
| CAL-06 | Phase 6 | Pending |
| CAL-07 | Phase 6 | Pending |
| CAL-08 | Phase 6 | Pending |
| CAL-09 | Phase 6 | Pending |
| CAL-10 | Phase 6 | Pending |
| SWEEP-01 | Phase 7 | Pending |
| SWEEP-02 | Phase 7 | Pending |
| SWEEP-03 | Phase 7 | Pending |
| SWEEP-04 | Phase 7 | Pending |
| SWEEP-05 | Phase 7 | Pending |
| SWEEP-06 | Phase 7 | Pending |
| SWEEP-07 | Phase 7 | Pending |
| SWEEP-08 | Phase 7 | Pending |
| SWEEP-09 | Phase 7 | Pending |
| SWEEP-10 | Phase 7 | Pending |
| SWEEP-11 | Phase 7 | Pending |
| SWEEP-12 | Phase 7 | Pending |
| SWEEP-13 | Phase 7 | Pending |
| SWEEP-14 | Phase 7 | Pending |
| UI-01 | Phase 8 | Pending |
| UI-02 | Phase 8 | Pending |
| UI-03 | Phase 8 | Pending |
| UI-04 | Phase 8 | Pending |
| UI-05 | Phase 8 | Pending |
| UI-06 | Phase 8 | Pending |
| UI-07 | Phase 8 | Pending |

**Coverage:**
- v2.1 requirements: 41 total (5 TAB + 5 DB + 10 CAL + 14 SWEEP + 7 UI)
- Mapped to phases: 41
- Unmapped: 0 ✓

---
*Requirements defined: 2026-05-18*
*Last updated: 2026-05-18 — traceability updated with v2.1 phase numbering (Phases 5-8)*
