# Requirements: Seva Mining v2.1 — Three-Tab Content Engine + UI Polish

**Defined:** 2026-05-18
**Core Value:** Every piece of content the system produces or surfaces must be genuinely valuable to the gold conversation it enters — a data point, an insight, a connection no one else made. For v2.1 this expands beyond the v2.0 News Funnel into two new surfaces: a personal Content Calendar for planning what to publish, and a Weekly Viral Sweeper that surfaces what's getting traction in Reddit gold/silver communities plus the most cross-referenced news stories of the past 7 days — giving the operator a tactical content-strategy lens, not just an intelligence digest.

## v2.1 Requirements

Each requirement maps to exactly one phase. Categories follow the research SUMMARY.md phase build order.

### Tab Navigation Infrastructure (TAB)

The 3-tab shell that wraps News Funnel (Tab 1) + Content Calendar (Tab 2) + Weekly Viral Sweeper (Tab 3). Foundation for everything else.

- [x] **TAB-01**: System installs the shadcn `Tabs` Radix primitive into `frontend/src/components/ui/` via `npx shadcn@latest add tabs` (Tailwind v4 branch); commits the resulting `tabs.tsx` component file alongside existing shadcn primitives
- [x] **TAB-02**: System introduces `frontend/src/components/layout/TabbedDashboard.tsx` — a thin wrapper rendering `<TabNav />` then `<Outlet />` (analogous to AppShell rendering AppHeader + Outlet); placed under the existing `<AppShell />` route so tabs only appear inside the 3-tab surface, NOT on `/digest` or `/settings`
- [x] **TAB-03**: System introduces `frontend/src/components/layout/TabNav.tsx` — a tab strip of 3 React Router `<NavLink>` elements styled to match shadcn Tabs visually; active-state driven by `useLocation()` (NEVER by local state) so browser Back/Forward navigation updates the tab highlight correctly
- [x] **TAB-04**: System restructures `frontend/src/App.tsx` routes so `/` (index), `/calendar`, and `/viral` are nested children under `<TabbedDashboard />`; preserves all existing routes intact (`/queue`, `/agents/:slug`, `/digest`, `/settings`, `/login` + `Navigate` redirects)
- [x] **TAB-05**: System leaves `frontend/src/components/layout/AppShell.tsx` and `AppHeader.tsx` structurally unchanged — TabbedDashboard handles the tab nav; existing wordmark + Log out button stay in AppHeader

### Database + Backend Foundation (DB)

Alembic migrations and dual-model parity for the two new tables. Backend router stubs (200 OK, empty payload) so frontend can develop against live endpoints.

- [x] **DB-01**: System adds Alembic migration `0011_add_calendar_items.py` creating table `calendar_items` with columns: `id UUID PK gen_random_uuid()`, `date DATE NOT NULL` (Date, not DateTime), `title TEXT NOT NULL`, `notes_md TEXT NULL`, `tag VARCHAR(20) NULL` with CHECK `tag IN ('thread','video','podcast','tweet','idea','other')`, `created_at`/`updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`, index `ix_calendar_items_date` on `date`
- [x] **DB-02**: System adds Alembic migration `0012_add_weekly_sweeps.py` creating table `weekly_sweeps` with columns: `id UUID PK`, `generated_at TIMESTAMPTZ NOT NULL`, `week_start DATE NOT NULL`, `week_end DATE NOT NULL`, `reddit_top_md TEXT NULL`, `story_virality_md TEXT NULL`, `content_angles_md TEXT NULL`, `raw_sources_jsonb JSONB NULL`, `status VARCHAR(20) NOT NULL DEFAULT 'completed'` with CHECK `status IN ('completed','failed','partial')`, `error_text TEXT NULL`, `agent_run_id UUID FK agent_runs.id ON DELETE SET NULL`, index `ix_weekly_sweeps_generated_at` on `(generated_at DESC)`
- [x] **DB-03**: System creates dual-model parity — SQLAlchemy 2.0 model files `backend/app/models/calendar_item.py`, `backend/app/models/weekly_sweep.py`, `scheduler/models/calendar_item.py`, `scheduler/models/weekly_sweep.py`; structurally identical, each imports from its local `models/base.py`
- [x] **DB-04**: System registers backend routes by adding `app.include_router(calendar_router)` and `app.include_router(weekly_sweeps_router)` to `backend/app/main.py`; both routers carry `dependencies=[Depends(get_current_user)]` at the router level so they inherit the existing JWT auth gate
- [x] **DB-05**: System verifies `alembic heads` returns exactly one head before both migrations land; each migration sets the prior head as `down_revision`; `alembic upgrade head` + `alembic downgrade -1` round-trips cleanly in dev before commit

### Content Calendar (CAL)

Pure CRUD over `calendar_items`. Weekly grid UI (Mon-Sun) with click-to-edit. Date dropdown reschedule (no DnD). Optimistic mutations with rollback.

- [x] **CAL-01**: System exposes `GET /calendar?start=YYYY-MM-DD&end=YYYY-MM-DD` returning `{items: CalendarItemResponse[], total: int}` ordered by `date ASC`; date params are `datetime.date` Pydantic fields parsed from `YYYY-MM-DD` strings (NEVER datetime — TZ off-by-one risk on Railway UTC)
- [x] **CAL-02**: System exposes `POST /calendar` accepting `{date, body}` and returning `201 + CalendarItemResponse`; `body` is a non-empty `str` stored in `notes_md`; backend writes `created_at = updated_at = datetime.utcnow()` explicitly. No `tag`, no `title` in request body (server may write a synthetic title or leave null per migration 0013).
- [x] **CAL-03**: System exposes `PATCH /calendar/{item_id}` accepting `{body}` (only) and returning `200 + CalendarItemResponse`; handler MUST set `updated_at = datetime.utcnow()` explicitly (not via DB trigger; `updated_at` is NOT exposed in the `CalendarItemUpdate` Pydantic schema). No `tag`, no `date` rescheduling in this rescoped model.
- [x] **CAL-04**: System exposes `DELETE /calendar/{item_id}` returning `204 No Content`; hard delete (no soft-delete column); `404` if not found
- [x] **CAL-05**: System renders `ContentCalendarPage.tsx` with a 7-column weekly grid (Mon-Sun ISO week start) showing the current week by default, prev/next-week arrow navigation, and a "today" jump button; today cell highlighted via `ring-2 ring-amber-500 bg-amber-500/5`
- [x] **CAL-06**: System renders the per-day text body inside its day cell as plain text with `whitespace-pre-wrap` so line breaks are preserved; NO markdown rendering, NO react-markdown, NO tag color chips. Each day cell shows at most one text blob (single-row-per-date enforced via DB UNIQUE(date) constraint from migration 0013).
- [x] **CAL-07**: System makes every day cell click-to-focus — clicking anywhere inside the cell focuses its `<textarea>` so the operator can immediately start typing. No "+ Add" hover button, no separate create UI; the textarea IS the editing surface.
- [x] **CAL-08**: System auto-saves on textarea blur — on `onBlur`, if text differs from last-saved value: POST to `/calendar` if no row exists for that date, PATCH `/calendar/{item_id}` if a row exists, or DELETE the row if text is empty (`text.trim() === ""`) AND a row exists. No Save button. No shadcn Dialog. Success is silent; a sonner error toast surfaces only on failure.
- [x] **CAL-09**: System mutates calendar items via TanStack Query mutations with optimistic updates: `onMutate` snapshots query cache, applies optimistic write; `onError` restores the snapshot; `onSettled` invalidates `['calendar', start, end]` so the next refetch is authoritative
- [x] **CAL-10**: System uses `staleTime: 0` + `refetchOnWindowFocus: false` on `useCalendar()` — calendar items are user-mutated, no stale tolerance, but no auto-refetch on tab switching either

### Weekly Viral Sweeper (SWEEP)

Sunday 08:00 PT cron, advisory lock 1019. X-post ingestion via `tweepy.asynchronous.AsyncClient` recent search (X-API pivot per 07-CONTEXT.md D-03 — replaces the originally specced Reddit/~~asyncpraw~~ source). Story virality compute over the past 7 days of `daily_summaries.raw_sources_jsonb.gold_news`. Sonnet generates 3 content angles. Frontend renders the latest sweep + history list.

- [x] **SWEEP-01** *(DROPPED — X-API pivot per 07-CONTEXT.md D-03)*: ~~System adds `asyncpraw>=7.8.1` to `scheduler/pyproject.toml`~~ — Reddit ingestion replaced by X API recent search. `tweepy[async]>=4.14` already in stack from v1.0 (see CLAUDE.md historical note 2026-04-20). No dependency change needed.
- [x] **SWEEP-02** *(DROPPED — X-API pivot per 07-CONTEXT.md D-03)*: ~~System adds three env vars to Railway: `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USER_AGENT`~~ — X API env vars (`x_api_bearer_token`) already set in Railway from the Content Agent's video_clip pipeline. No env change needed.
- [x] **SWEEP-03**: System adds `"weekly_sweeper": 1019` to the `JOB_LOCK_IDS` dict in `scheduler/worker.py` **as the first task of the sweeper phase** — must precede any other weekly_sweeper code so the OPS-02 uniqueness assertion at line 118 can guard against collisions
- [x] **SWEEP-04**: System creates `scheduler/agents/x_ingest.py` exposing `async def fetch_top_x_posts(query: str, max_results: int = 100) -> list[dict]`; uses `tweepy.asynchronous.AsyncClient(bearer_token=settings.x_api_bearer_token, wait_on_rate_limit=True)` with `search_recent_tweets(query=query, max_results=max_results, sort_order="relevancy", tweet_fields=[...], expansions=["author_id"], user_fields=["username"])`; quota gate at top of function reads `twitter_monthly_tweet_count` and `twitter_monthly_quota_limit` from `bot_config` and returns `[]` (with status='partial' caller signal) if within 500 of cap; increments counter by fetched-tweet count at end. Mirrors the auth + quota-gate + result-processing shape of `scheduler/agents/content/gold_media.py::_search_gold_media_clips`.
- [x] **SWEEP-05**: System uses a single combined X recent-search query hardcoded in `weekly_sweeper.py`: `("gold price" OR "gold market" OR "gold mining" OR "central bank gold" OR $GOLD OR $GLD OR $GDX OR $NEM OR $AEM OR #gold OR #goldprice OR #goldmining) -is:retweet -is:reply lang:en`; `max_results=100` (X API recent-search ceiling); post-fetch top-10 selected by engagement re-rank score `likes + retweets*2 + replies*1.5`; each returned post dict has keys `{tweet_id, text, author_username, tweet_url, likes, retweets, replies, created_at}`.
- [x] **SWEEP-06**: System creates `scheduler/agents/weekly_sweeper.py` exposing `async def run_weekly_sweeper() -> None` that follows the daily_summary.py orchestration shape: idempotency check → `agent_runs` insert (status='running') → Reddit fetch → virality compute → Sonnet call → status mapping → `weekly_sweeps` INSERT → telemetry in `finally`
- [x] **SWEEP-07**: System computes story virality by querying `daily_summaries` for `generated_at >= now() - INTERVAL '7 days' AND status IN ('completed','partial')`, flattening `raw_sources_jsonb.gold_news[]` (guarding `(row.raw_sources_jsonb or {}).get("gold_news", [])` against NULL on failed rows), canonicalizing each `link` (strip UTM/fbclid/gclid/ref params, lowercase host, sort query, no trailing slash), grouping by canonical URL, and returning top 5 stories sorted by distinct-source-name count DESC
- [x] **SWEEP-08**: System calls `claude-sonnet-4-6` with `AsyncAnthropic(api_key=..., timeout=60.0)`, max_tokens=1000, with the tactical content-strategist system prompt that generates exactly 3 content angles each connecting an X signal with a mainstream news signal; if `len(x_posts) < 3 OR len(viral_stories) < 3`, skip the Sonnet call and write "Insufficient signal this week — angles not generated" into `content_angles_md` (grounding guard against hallucination on sparse weeks). System prompt enforces gold bull thesis bias and grounding rule ("Use ONLY facts present in supplied inputs"). Each X post body truncated to 500 chars before injection into user prompt (token budget defense, mirrors `content_agent.py [:500]`).
- [x] **SWEEP-09**: System registers the cron in `scheduler/worker.py` `build_scheduler()` via `_make_weekly_sweeper_job(engine)` factory (mirroring `_make_daily_summary_job`), using `CronTrigger(day_of_week='sun', hour=8, minute=0, timezone='America/Los_Angeles')`, with `id="weekly_sweeper"`, `max_instances=1`, `misfire_grace_time=1800`
- [x] **SWEEP-10**: System idempotency-guards each fire by checking for an existing `weekly_sweeps` row with `week_start = sunday_of_this_week` and `status IN ('running','completed')` within a 60-minute window; on hit, log `idempotency_skip` and exit cleanly
- [x] **SWEEP-11**: System sets `weekly_sweeps.status` to `'completed'` when Reddit + virality + Sonnet all succeed, `'partial'` when at least one of (Reddit, virality, Sonnet) fails but the row can still render with empty-state copy in the failed section, `'failed'` only when Reddit ingestion crashes before any output can be assembled; per-section errors written into `agent_runs.errors` list (post-jny pattern)
- [x] **SWEEP-12**: System exposes `GET /weekly-sweeps?limit=12` returning `{sweeps: WeeklySweepCard[], total: int}` ordered by `generated_at DESC`; query param `limit` clamped to `ge=1, le=52`
- [x] **SWEEP-13**: System renders `WeeklyViralSweeperPage.tsx` showing the latest sweep card by default and a history-week-picker dropdown for browsing prior weeks; sweep card renders three stacked sections via react-markdown in order: "Top X Posts This Week", "Most Cross-Referenced Stories", "3 Content Angles". Mirrors the SummaryFeedPage `max-w-[720px]` content width.
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
| TAB-01 | Phase 5 | Complete |
| TAB-02 | Phase 5 | Complete |
| TAB-03 | Phase 5 | Complete |
| TAB-04 | Phase 5 | Complete |
| TAB-05 | Phase 5 | Complete |
| DB-01 | Phase 5 | Complete |
| DB-02 | Phase 5 | Complete |
| DB-03 | Phase 5 | Complete |
| DB-04 | Phase 5 | Complete |
| DB-05 | Phase 5 | Complete |
| CAL-01 | Phase 6 | Complete |
| CAL-02 | Phase 6 | Complete |
| CAL-03 | Phase 6 | Complete |
| CAL-04 | Phase 6 | Complete |
| CAL-05 | Phase 6 | Complete |
| CAL-06 | Phase 6 | Complete |
| CAL-07 | Phase 6 | Complete |
| CAL-08 | Phase 6 | Complete |
| CAL-09 | Phase 6 | Complete |
| CAL-10 | Phase 6 | Complete |
| SWEEP-01 | Phase 7 | Dropped (X-API pivot) |
| SWEEP-02 | Phase 7 | Dropped (X-API pivot) |
| SWEEP-03 | Phase 7 | Complete |
| SWEEP-04 | Phase 7 | Complete |
| SWEEP-05 | Phase 7 | Complete |
| SWEEP-06 | Phase 7 | Complete |
| SWEEP-07 | Phase 7 | Complete |
| SWEEP-08 | Phase 7 | Complete |
| SWEEP-09 | Phase 7 | Complete |
| SWEEP-10 | Phase 7 | Complete |
| SWEEP-11 | Phase 7 | Complete |
| SWEEP-12 | Phase 7 | Complete |
| SWEEP-13 | Phase 7 | Complete |
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
