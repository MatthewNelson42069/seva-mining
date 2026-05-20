# Roadmap: Seva Mining

## Milestones

- ✅ **v1.0.1 — Approval Dashboard (deprecated by v2.0 pivot)** — Phases 1-11, shipped 2026-04-25 → archive: [`milestones/v1.0.1/ROADMAP.md`](milestones/v1.0.1/ROADMAP.md)
- ✅ **v2.0 — Daily Summary Feed** — Phases 1-4 (reset numbering), shipped 2026-05-06 → archive: [`milestones/v2.0-ROADMAP.md`](milestones/v2.0-ROADMAP.md)
- ✅ **v2.1 — Three-Tab Content Engine + UI Polish** — Phases 5-8 (project-wide counter continues), shipped 2026-05-19
- 🚧 **v3.0 — Multi-Tenant Dashboards (Juno Industries Onboarding)** — Phases 9-10 (project-wide counter continues), initiated 2026-05-19

## Phases

<details>
<summary>✅ v2.0 Daily Summary Feed (Phases 1-4) — SHIPPED 2026-05-06</summary>

- [x] Phase 1: Gold News Card + Web Feed (6/6 plans) — completed 2026-05-06
- [x] Phase 2: Ontario Law Ingestion (1/1 plan) — completed 2026-05-06
- [x] Phase 3: Ontario Stats Ingestion (1/1 plan) — completed 2026-05-06
- [x] Phase 4: Prune Cron + Operations Hardening (1/1 plan, 4 tasks) — completed 2026-05-06

Phase artifacts archived to `milestones/v2.0-phases/`. Full roadmap detail: `milestones/v2.0-ROADMAP.md`.

</details>

<details>
<summary>✅ v1.0.1 Approval Dashboard (Phases 1-11) — DEPRECATED by v2.0 pivot</summary>

11 phases shipped between 2026-03-30 and 2026-04-25 covering FastAPI backend, React approval dashboard, Twitter Agent (later deprecated), Senior Agent (later deprecated), Instagram Agent (later deprecated), Content Agent + 6 sub-agents, dashboard views + WhatsApp digest, agent execution polish, and content preview / rendered images. Source files retained as dead code per v2.0 retirement intent. Full archive: `milestones/v1.0.1/ROADMAP.md`.

</details>

### v2.1 — Three-Tab Content Engine + UI Polish

- [x] **Phase 5: Foundation — Tabs + DB + Backend Stubs** — DB migrations, dual-model parity, backend router stubs, frontend tab shell with route restructure
- [x] **Phase 6: Content Calendar** — Full CRUD over `calendar_items`: backend routes, Pydantic schemas, weekly grid UI, optimistic mutations (completed 2026-05-19)
- [x] **Phase 7: Weekly Viral Sweeper** — Scheduler + X API ingestion (pivoted from Reddit per 07-CONTEXT.md D-03) + virality compute + Sonnet call + sweep card UI (completed 2026-05-19)
- [x] **Phase 8: UI Polish + Dead-Code Strip** — Linear dark/amber-500 pass across all 3 tabs, WCAG audit, v1.0 dead-code removal (completed 2026-05-19)

### v3.0 — Multi-Tenant Dashboards (Juno Industries Onboarding)

- [x] **Phase 9: Multi-Tenant Foundation** — Atomic deploy adding row-level `company_id` to the 3 multi-tenant tables, `scoped_*()` query helpers, `/api/{company}` router prefix, `/:company/` frontend routing, AppHeader/CompanyBar switcher, TanStack key factory, per-company cron fan-out (juno path wired as stub) — `/seva/*` byte-equivalent to v2.1; `/juno/*` empty-state (completed 2026-05-19, verifier 10/10 passed)
- [ ] **Phase 10: Juno Defence News Funnel** — Config-only after Phase 9: defence Tier-1 RSS feeds + SerpAPI fallback for paywalled sources + Canadian-procurement queries + defence Sonnet 4.6 system prompt (designed from scratch) + Haiku 4.5 world-events relevance classifier + refusal-detector + voice-calibration UAT — Tab 1 of `/juno/` renders live defence/procurement/world-events summary

---

## Phase Details

### Phase 5: Foundation — Tabs + DB + Backend Stubs

**Goal:** Everything downstream phases need exists but nothing is "real" yet — two Alembic migrations land, four SQLAlchemy model files maintain dual-model parity, two auth-gated backend routers return stubs, the frontend route tree is restructured to host three tabs, and stub page components confirm the routing contract before any feature logic is written.

**Depends on:** Nothing (first phase of v2.1; builds on v2.0 shipped codebase)

**Requirements:** TAB-01, TAB-02, TAB-03, TAB-04, TAB-05, DB-01, DB-02, DB-03, DB-04, DB-05

**Inputs:**
- Shipped v2.0 codebase with confirmed Alembic head at `0010_add_daily_summaries`
- Existing `scheduler/worker.py` with `JOB_LOCK_IDS` dict and OPS-02 uniqueness assertion at line 118
- Tailwind v4 shadcn installation confirmed (existing shadcn primitives in `frontend/src/components/ui/`)
- React Router v6 + `AppShell.tsx` + `AppHeader.tsx` (12-line, structurally frozen)

**Outputs:**
- `backend/alembic/versions/0011_add_calendar_items.py` + `0012_add_weekly_sweeps.py` (two hand-written migrations; see Pitfall: down_revision chain)
- Four model files: `backend/app/models/calendar_item.py`, `backend/app/models/weekly_sweep.py`, `scheduler/models/calendar_item.py`, `scheduler/models/weekly_sweep.py`
- Two backend router stubs: `backend/app/routers/calendar.py` (GET returns `{items:[], total:0}`, POST returns 501), `backend/app/routers/weekly_sweeps.py` (GET returns `{sweeps:[], total:0}`)
- `backend/app/main.py` updated with `app.include_router(calendar_router)` + `app.include_router(weekly_sweeps_router)`
- `scheduler/worker.py` updated: `"weekly_sweeper": 1019` added to `JOB_LOCK_IDS` (FIRST change in this phase — before any other sweeper code)
- `frontend/src/components/ui/tabs.tsx` from `npx shadcn@latest add tabs` (Tailwind v4 branch)
- `frontend/src/components/layout/TabbedDashboard.tsx` + `frontend/src/components/layout/TabNav.tsx`
- `frontend/src/App.tsx` restructured: `/`, `/calendar`, `/viral` nested under `TabbedDashboard`; all v2.0 routes preserved
- Stub `ContentCalendarPage.tsx` + `WeeklyViralSweeperPage.tsx` rendering "Coming soon" inside the tab layout

**Success Criteria** (what must be TRUE when this phase completes):
1. `alembic upgrade head` runs cleanly in dev and `alembic downgrade -1` round-trips without error for both 0011 and 0012
2. Visiting `/`, `/calendar`, and `/viral` in the browser all render the correct tab highlighted without page reload (browser Back/Forward also updates the active tab indicator)
3. `GET /calendar` and `GET /weekly-sweeps` return `200 OK` with empty-list payloads through the existing JWT auth gate
4. The v2.0 routes `/queue → /`, `/agents/:slug → /`, `/digest`, `/settings` continue to work correctly; tabs do NOT appear on `/digest` or `/settings`
5. The OPS-02 uniqueness assertion passes on scheduler boot (no import error after adding lock 1019)

**Plans:** 5 plans
- [x] 05-01-PLAN.md — Reserve weekly_sweeper advisory lock ID 1019 in scheduler/worker.py JOB_LOCK_IDS (Phase 7 pre-req)
- [x] 05-02-PLAN.md — Hand-write Alembic migrations 0011 (calendar_items) + 0012 (weekly_sweeps) with round-trip verification (DB-01, DB-02, DB-05)
- [x] 05-03-PLAN.md — Create 4 dual-parity SQLAlchemy models + parity test (DB-03)
- [x] 05-04-PLAN.md — Backend stub routers calendar.py + weekly_sweeps.py + main.py wiring + smoke tests (DB-04)
- [x] 05-05-PLAN.md — Frontend tab shell: TabbedDashboard, TabNav (NavLink isActive), stub pages, App.tsx restructure (TAB-01..05)

**UI hint**: yes

**Complexity:** M
**Estimated duration:** 2-3 hours

**Dependencies:**
- `alembic heads` must confirm exactly one head (`0010`) before writing migration files (Pitfall DB-01, DB-05)
- Lock ID 1019 added to `JOB_LOCK_IDS` before any other sweeper code (Pitfall SWEEP-03)

**Hard parts (cross-ref PITFALLS.md):**

| # | Pitfall | Severity | Prevention |
|---|---------|----------|-----------|
| P1 | `down_revision` chain mismatch breaks Railway deploy | CRITICAL | Run `alembic heads` first; set `down_revision` to exact output |
| P2 | Two tables in separate migrations within the same deploy atomicity risk | HIGH | Phase 5 ships both in the same deploy; each migration is reversible independently; if Neon times out mid-run, downgrade and retry |
| P3 | shadcn Tabs from v3 branch renders with wrong Tailwind classes | HIGH | Confirm `npx shadcn@latest add tabs` targets the Tailwind v4 branch; verify generated `tabs.tsx` uses CSS custom property color refs |
| P4 | Tabs `value` driven by local state desyncs from URL on browser nav | CRITICAL | Wire `value` prop from `useLocation()` in `TabNav.tsx`; never use `defaultValue` or local state for active tab |
| P5 | v2.0 redirect routes escape `ProtectedRoute` during restructure | HIGH | Keep `/queue` and `/agents/:slug` redirects inside the `<ProtectedRoute />` subtree; test authenticated redirect works post-restructure |
| P6 | AppHeader `max-w-[720px]` constraint overflows with 3-tab strip | HIGH | `TabNav` sits in its own `<nav>` bar between `AppHeader` and `<main>` (`border-b border-zinc-800`); AppHeader width unchanged |
| P7 | Tab URL contract decided too late causes routing conflicts | MEDIUM | Lock URL mapping in this phase: Tab 1 = `/`, Tab 2 = `/calendar`, Tab 3 = `/viral` |
| P8 | Vite bundle size grows without lazy loading | MEDIUM | Lazy-load `ContentCalendarPage` and `WeeklyViralSweeperPage` with `React.lazy()` + `<Suspense>` from day one |
| P9 | Dual-model parity silently diverges | HIGH | Add parity tests asserting `__tablename__` + column names match between scheduler and backend model for both tables |

**Architecture reference:** ARCHITECTURE.md — "Database Layer", "Dual-Model Parity", "Backend Route Registration", "Frontend Route Structure", "New Frontend Files"

---

### Phase 6: Content Calendar

**Goal:** The Content Calendar tab is fully functional — the operator can create, reschedule, tag, and delete planning items in a weekly grid view with optimistic mutations that roll back cleanly on failure.

**Depends on:** Phase 5 (migrations run, table exists, stub router wired into main.py, `/calendar` route renders a real page, `TabbedDashboard` routing confirmed)

**Requirements:** CAL-01, CAL-02, CAL-03, CAL-04, CAL-05, CAL-06, CAL-07, CAL-08, CAL-09, CAL-10

**Inputs:**
- `calendar_items` table live in Neon (from Phase 5 migration)
- Stub `calendar.py` router wired at `GET /calendar` returning empty list
- `ContentCalendarPage.tsx` stub rendering "Coming soon" (placeholder for replacement)
- shadcn `Dialog` primitive already in `components/ui/` (confirm; if not present, add alongside `tabs.tsx` in Phase 5)
- `react-markdown ^10.1.0` already in `package.json` (for optional notes preview)

**Outputs:**
- `backend/app/schemas/calendar.py` — full Pydantic schemas (`CalendarItemCreate`, `CalendarItemUpdate`, `CalendarItemResponse`, `CalendarRangeResponse`)
- `backend/app/routers/calendar.py` — full CRUD: `GET /calendar?start=&end=`, `POST /calendar` (201), `PATCH /calendar/{item_id}` (sets `updated_at` explicitly), `DELETE /calendar/{item_id}` (204)
- `frontend/src/api/calendar.ts` — `getCalendar`, `createCalendarItem`, `updateCalendarItem`, `deleteCalendarItem`, `useCalendar()` hook with `staleTime: 0`, `refetchOnWindowFocus: false`
- Mutation hooks for create/update/delete with full optimistic update + `onMutate` snapshot + `onError` rollback + `onSettled` invalidation
- `frontend/src/components/calendar/WeeklyGrid.tsx` — 7-column Mon-Sun ISO grid, current week default, prev/next navigation, today-jump button
- `frontend/src/components/calendar/CalendarItem.tsx` — day-cell chip with tag-color-coded background, clips at 3 items + "+N more" badge
- `frontend/src/components/calendar/CalendarItemDialog.tsx` — create/edit modal (shadcn `Dialog`): title input, date `<select>` dropdown, tag dropdown, markdown notes `<textarea>`; "+ Add" hover button on empty cells
- `frontend/src/pages/ContentCalendarPage.tsx` — live data replacing stub

**Success Criteria** (what must be TRUE when this phase completes):
1. Operator can create a calendar item via the "+ Add" hover button on any day cell, and the item appears in the grid immediately without page reload
2. Clicking an existing item opens the edit dialog; changing the date via dropdown moves the chip to the correct day cell; failure (simulated 500 from devtools) restores the item to its original day
3. Deleting an item removes it from the grid immediately; a 204 from the backend confirms the hard delete
4. Today's cell is visually distinguished (amber-500 ring + background tint); items display tag-color-coded chips; cells with more than 3 items show a "+N more" badge
5. `GET /calendar` with `start=` and `end=` date params returns items in `date ASC` order; dates round-trip as `"YYYY-MM-DD"` strings regardless of Railway timezone (no UTC off-by-one)

**Plans:** 5/5 plans complete
- [x] 06-01-PLAN.md — Requirements rephrase + Migration 0013 (title nullable + UNIQUE(date)) + Pydantic schemas (Wave 1)
- [x] 06-02-PLAN.md — Full CRUD router replace + pytest coverage including P1/P4 defenses (Wave 2, depends on 06-01)
- [x] 06-03-PLAN.md — Frontend API module + useCalendar hook + 3 optimistic mutation hooks with rollback (Wave 2, depends on 06-01)
- [x] 06-04-PLAN.md — ISO week helpers + DayCell (textarea + auto-save 4-way branch) + WeeklyGrid (Wave 3, depends on 06-02 + 06-03)
- [x] 06-05-PLAN.md — WeekNav + live ContentCalendarPage + human-verify checkpoint (Wave 4, depends on 06-04)

**UI hint**: yes

**Complexity:** M
**Estimated duration:** 3-5 hours

**Parallelism note:** Logically independent of Phase 7 (shares no code or DB tables). Can be developed in parallel with Phase 7 if bandwidth permits. Calendar first is the recommendation because it is pure CRUD with no external dependencies.

**Dependencies:**
- Phase 5: `calendar_items` table + stub router + `TabbedDashboard` routing

**Hard parts (cross-ref PITFALLS.md):**

| # | Pitfall | Severity | Prevention |
|---|---------|----------|-----------|
| P1 | `DATE` vs `DateTime` TZ off-by-one invisible in local dev, breaks on Railway UTC | CRITICAL | SQLAlchemy `Column(Date)`, Pydantic `datetime.date` field, frontend sends `"YYYY-MM-DD"` string; add `TZ=UTC pytest` test that creates item with `date="YYYY-MM-DD"` and reads it back |
| P2 | Optimistic rollback not wired: orphaned UI state after failed mutation | HIGH | `onMutate` snapshot + `onError` restore required for ALL three mutations (create, update, delete); test rollback path with mocked 500 |
| P3 | Empty title passes frontend validation but is rejected as 422 by backend — silent failure | HIGH | Frontend: disable submit when `title.trim() === ""`; backend: `@field_validator("title")` raises on blank |
| P4 | `updated_at` silently not set on PATCH | HIGH | Router handler sets `updated_at = datetime.utcnow()` explicitly; `CalendarItemUpdate` schema does NOT expose `updated_at` |
| P5 | `staleTime` set too high causes stale calendar data after mutation in same session | MEDIUM | `staleTime: 0` (no tolerance); `refetchOnWindowFocus: false` (no auto-refetch on tab switch) |

**Architecture reference:** ARCHITECTURE.md — "Database Layer" (calendar_items DDL), "Backend / API Layer" (calendar router + schemas), "New Frontend Files" (WeeklyGrid, CalendarItemDialog, CalendarItem, calendar.ts)
**Feature reference:** FEATURES.md — "CONTENT CALENDAR UX — Detailed Findings"

---

### Phase 7: Weekly Viral Sweeper

**Goal:** Every Sunday at 08:00 PT a cron job ingests the top X (Twitter) posts via the X API recent-search endpoint (combined keyword + cashtag + hashtag query for gold-sector chatter), computes story virality across the past 7 days of `daily_summaries`, calls Sonnet for 3 content angles, persists a `weekly_sweeps` row, and the frontend's Tab 3 renders the latest sweep card with all three sections plus an empty state for the first deploy.

**Pivot note (2026-05-19, per `phases/07-weekly-viral-sweeper/07-CONTEXT.md` D-03):** Reddit ingestion was replaced with X API recent-search ingestion. The X API Basic tier ($100/mo) is already wired for the Content Agent's `video_clip` pipeline; reusing it avoids a new vendor + 3 env vars + asyncpraw dependency. SWEEP-01 and SWEEP-02 are Dropped; SWEEP-04 and SWEEP-05 are reworded to reference X API + tweepy; SWEEP-08 and SWEEP-13 rephrase "Reddit posts" → "X posts".

**Depends on:** Phase 5 (migrations run, `weekly_sweeps` table exists, `JOB_LOCK_IDS["weekly_sweeper"] = 1019` confirmed, `/viral` route renders a page)

**Requirements:** SWEEP-01, SWEEP-02, SWEEP-03, SWEEP-04, SWEEP-05, SWEEP-06, SWEEP-07, SWEEP-08, SWEEP-09, SWEEP-10, SWEEP-11, SWEEP-12, SWEEP-13, SWEEP-14

**Inputs:**
- `weekly_sweeps` table live in Neon (from Phase 5 migration)
- `"weekly_sweeper": 1019` in `JOB_LOCK_IDS` (from Phase 5 — MUST precede any sweeper module code)
- `daily_summaries` table with at least 7 days of rows with `raw_sources_jsonb.gold_news[]` populated (v2.0 shipped 2026-05-06 — ample history by Phase 7 execution)
- Stub `WeeklyViralSweeperPage.tsx` from Phase 5
- `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USER_AGENT` added to Railway (manual one-time env setup, documented as first step of Phase 7 planning)

**Outputs:**
- `scheduler/pyproject.toml` — `asyncpraw>=7.8.1` added (not `praw`)
- `scheduler/agents/reddit_ingest.py` — `async def fetch_reddit_posts(subreddits, limit, time_filter) -> list[dict]`; `asyncpraw.Reddit(requestor_kwargs={"timeout": 15})`; per-subreddit try/except; presence-only logging for `REDDIT_CLIENT_SECRET` in `_validate_env()`
- `scheduler/agents/weekly_sweeper.py` — `async def run_weekly_sweeper() -> None`; full orchestration: idempotency check → `agent_runs` INSERT → Reddit fetch → virality compute → Sonnet call (timeout=60.0, max_tokens=1000) → status mapping → `weekly_sweeps` INSERT → `finally` telemetry
- `scheduler/worker.py` — `_make_weekly_sweeper_job(engine)` factory + `build_scheduler()` registration via `CronTrigger(day_of_week='sun', hour=8, minute=0, timezone='America/Los_Angeles')`; `max_instances=1`, `misfire_grace_time=1800`
- `backend/app/schemas/weekly_sweep.py` — `WeeklySweepCard` + `WeeklySweepFeedResponse`
- `backend/app/routers/weekly_sweeps.py` — full `GET /weekly-sweeps?limit=12` (limit clamped `ge=1, le=52`)
- `frontend/src/api/weeklySweeps.ts` — `getWeeklySweeps`, `useWeeklySweeps()` hook
- `frontend/src/components/viral/SweeperCard.tsx` — three react-markdown sections: "Top Reddit Posts This Week", "Most Cross-Referenced Stories", "3 Content Angles"; status-specific banner copy for `failed`/`partial`
- `frontend/src/pages/WeeklyViralSweeperPage.tsx` — live data, latest sweep by default, history week-picker dropdown, empty-state copy when `total: 0`

**Success Criteria** (what must be TRUE when this phase completes):
1. The `weekly_sweeper` advisory lock (1019) appears in `JOB_LOCK_IDS` and the OPS-02 assertion passes on scheduler boot; `build_scheduler()` logs the `weekly_sweeper` job as registered
2. A manual trigger of `run_weekly_sweeper()` (via Railway shell: `python -m agents.weekly_sweeper`) produces a `weekly_sweeps` row with `status='completed'` or `status='partial'` (not `failed`) when Reddit and Sonnet are reachable; the `agent_runs` row transitions from `running` to the final status
3. Tab 3 renders the sweep card with all three sections populated from the latest `weekly_sweeps` row; react-markdown renders the content without raw markdown leaking into the DOM
4. When `GET /weekly-sweeps` returns `total: 0`, the tab renders "Sweeper has not run yet — first fire scheduled for Sunday {next_sunday} 08:00 PT." without a runtime error
5. A second call to `run_weekly_sweeper()` within 60 minutes of the first logs `idempotency_skip` and does NOT insert a duplicate `weekly_sweeps` row
6. If one of the 4 subreddits returns 403, the sweeper completes with the remaining subreddits' posts and writes the subreddit error into `agent_runs.errors`; `status` is `partial`, not `failed`

**Plans:** 6 plans
- [x] 07-01-PLAN.md — Wave 1: REQUIREMENTS.md X-API rescoping (drop SWEEP-01/02; replace SWEEP-04/05; rephrase SWEEP-08/13) + Pydantic schemas `WeeklySweepCard` + `WeeklySweepFeedResponse`
- [x] 07-02-PLAN.md — Wave 2: `scheduler/agents/x_ingest.py` — `fetch_top_x_posts(query, max_results=100)` via tweepy AsyncClient + quota gate (twitter_monthly_tweet_count, 500 safety margin) + engagement re-rank, with pytest coverage of 7+ branches (SWEEP-04/05)
- [x] 07-03-PLAN.md — Wave 2: `backend/app/routers/weekly_sweeps.py` — replace Phase 5 stub with full `GET /weekly-sweeps?limit=12` (ge=1 le=52, generated_at DESC, auth-gated) + pytest coverage (SWEEP-12)
- [x] 07-04-PLAN.md — Wave 3: `scheduler/agents/weekly_sweeper.py` — `run_weekly_sweeper()` orchestrator with `_compute_virality` (P3 NULL guard + P10 URL canonicalization + P9 per-row dedup), Sonnet call (P6/P7/P8/P14 defenses), P15 insufficient-signal fallback, SWEEP-11 status mapping, P13 `__main__` escape hatch + pytest coverage of 8+ branches (SWEEP-06/07/08/10/11)
- [x] 07-05-PLAN.md — Wave 4: `scheduler/worker.py` — `_make_weekly_sweeper_job(engine)` factory + `scheduler.add_job` registration with `CronTrigger(day_of_week='sun', hour=8, minute=0, timezone='America/Los_Angeles')` (consumes lock 1019 already reserved in Phase 5) + smoke test (SWEEP-03/09)
- [x] 07-06-PLAN.md — Wave 5: Frontend — `api/weeklySweeps.ts` + `hooks/useWeeklySweeps.ts` + `components/viral/SweeperCard.tsx` (3 react-markdown sections + status banner) + `pages/WeeklyViralSweeperPage.tsx` replacing Phase 5 stub (empty state, week-picker, live data) + Vitest coverage + human-verify checkpoint (SWEEP-13/14)

**UI hint**: yes

**Complexity:** L (heaviest phase — external Reddit dependency, scheduler changes, idempotency guard, virality compute, Sonnet integration, status state machine, frontend card)
**Estimated duration:** 4-6 hours

**Parallelism note:** Logically independent of Phase 6 (shares no code or DB tables). Can be developed in parallel with Phase 6 if bandwidth permits. Phase 7 is the recommended second feature phase because it has more external dependencies (Reddit API setup, scheduler restart) and the most complex logic.

**Split consideration:** Phase 7 has 14 requirements and is the highest-complexity phase. A natural split exists at the scheduler/frontend boundary:
- **7a** (scheduler-only): SWEEP-01 through SWEEP-11 — asyncpraw install, env vars, `reddit_ingest.py`, `weekly_sweeper.py`, factory + registration, idempotency, status mapping
- **7b** (frontend + backend read route): SWEEP-12 through SWEEP-14 — `GET /weekly-sweeps`, frontend page + card + empty state

Keeping Phase 7 as a single phase is recommended (scheduler + frontend in one execution cycle) because the frontend is only usable with a real DB row to render, and the manual trigger escape hatch lets you verify the scheduler before Sunday. If the user finds Phase 7 execution too long in a single session, split at the 7a/7b boundary and treat 7b as a quick follow-on.

**Dependencies:**
- Phase 5: `weekly_sweeps` table + lock 1019 in dict + `/viral` route exists
- Reddit app created at reddit.com/prefs/apps (manual, one-time; must precede writing `reddit_ingest.py`)
- 3 env vars set in Railway (`REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USER_AGENT`)

**Hard parts (cross-ref PITFALLS.md):**

| # | Pitfall | Severity | Prevention |
|---|---------|----------|-----------|
| P1 | `praw` (sync) blocks `AsyncIOScheduler` event loop | CRITICAL | Use `asyncpraw>=7.8.1` exclusively; never import bare `praw` |
| P2 | Lock ID 1019 hardcoded outside `JOB_LOCK_IDS` evades OPS-02 assertion | CRITICAL | Lock entry added in Phase 5 as the very first task; confirmed before any sweeper module code lands |
| P3 | `raw_sources_jsonb=None` on failed `daily_summary` rows raises `TypeError` in virality compute | HIGH | Guard: `(row.raw_sources_jsonb or {}).get("gold_news", [])` on every row; unit test with None row |
| P4 | Single failing subreddit (403/quarantine) cascades and aborts all subreddit fetches | HIGH | Per-subreddit try/except; partial results > all-or-nothing; errors into `agent_runs.errors` |
| P5 | asyncpraw client construction has no timeout; hung OAuth hangs the event loop | HIGH | `asyncpraw.Reddit(requestor_kwargs={"timeout": 15})` on client construction |
| P6 | Sonnet timeout missing (SDK default 600s); hung call stalls worker process | HIGH | `AsyncAnthropic(api_key=..., timeout=60.0)` — identical to post-ii6 `daily_summary.py` pattern |
| P7 | Reddit post body blows Sonnet token budget | HIGH | Truncate each post body to 500 chars before injecting into user prompt (mirrors `content_agent.py [:500]`) |
| P8 | Sonnet produces bearish gold angles from bearish Reddit posts | HIGH | System prompt: "All three content angles MUST support the gold bull thesis... reframe bearish signals through the bull lens or discard them" |
| P9 | Title-based dedup must apply within each row before cross-summary counting | HIGH | Run `deduplicate_stories(stories_for_row)` per row before adding to aggregate cross-reference dict |
| P10 | URL canonicalization: UTM params inflate virality by splitting identical stories | MEDIUM | `canonical_url()` strips UTM/fbclid/gclid/ref/source/_ga; lowercase host; no trailing slash; sorted remaining query |
| P11 | `REDDIT_CLIENT_SECRET` value logged in `_validate_env()` | MEDIUM | Add to `optional` dict (presence-only boolean check); never log the value |
| P12 | `reconcile_stale_runs()` 30-min threshold must cover sweeper expected runtime | HIGH | Expected runtime ~25s; 30-min threshold is fine; document in `reconcile_stale_runs()` comment |
| P13 | First Railway deploy on a Sunday after 08:30 PT misses the sweep entirely | HIGH | Document manual escape hatch in sweeper file: `python -m agents.weekly_sweeper` runs directly from Railway shell |
| P14 | Hallucinated facts in content angles | MEDIUM | Grounding rule in system prompt: "Use ONLY facts, figures, and claims present in the supplied inputs" |
| P15 | Insufficient signal week (Reddit < 3 posts OR viral stories < 3) | MEDIUM | Skip Sonnet call; write "Insufficient signal this week — angles not generated" into `content_angles_md` |

**Architecture reference:** ARCHITECTURE.md — "Scheduler Layer" (factory pattern, lock dict, `build_scheduler()` registration), "Backend / API Layer" (weekly_sweeps router + schemas), "New Frontend Files" (weeklySweeps.ts, SweeperCard.tsx, WeeklyViralSweeperPage.tsx)
**Feature reference:** FEATURES.md — "REDDIT INGESTION", "STORY VIRALITY COMPUTE", "SONNET CONTENT-ANGLE GENERATION", "SUNDAY CRON DESIGN"

---

### Phase 8: UI Polish + Dead-Code Strip

**Goal:** The Linear-style dark/amber-500 design language is applied consistently across all three tabs, typography weights are refined using the existing Geist Variable font, subtle border and hover states are unified across every card surface, and the v1.0 dead-code sub-agent source files are stripped once there is no surviving caller.

**Depends on:** Phases 5, 6, and 7 all merged and verified (UI polish cannot be "done" until all surfaces exist; dead-code strip requires confidence that nothing references deleted files)

**Requirements:** UI-01, UI-02, UI-03, UI-04, UI-05, UI-06, UI-07

**Inputs:**
- All three tabs rendering live data (Phases 5-7 merged)
- Existing dark theme baseline: `zinc-950/zinc-900/zinc-800` hierarchy + Geist Variable font
- `AppHeader.tsx` with existing `border-zinc-800`, `bg-zinc-900`, `text-zinc-400/100` classes (frozen — UI pass must not break these)
- v1.0 dead-code files: `scheduler/agents/content/*.py` (retired format sub-agents) + lock-ID dict entries 1010-1016 in `worker.py` + comments referencing them

**Outputs:**
- Amber-500/amber-400 accent applied to: active tab indicator in `TabNav`, primary CTA buttons, status badges on summary cards, today-cell ring in calendar, hover accent borders
- Spacing tokens refined: `p-6` minimum inside cards, `gap-6` between card sections, `space-y-4` between section bullets in react-markdown rendering
- Typography: headings weight-600, sub-headings weight-500, body weight-400, monospace numerics for upvote counts + source counts
- `border border-zinc-800` baseline + `hover:border-zinc-700` transition applied consistently across summary cards, calendar items, sweep card sections
- Reddit subreddit attribution rendered as monospace pills: `r/gold` in `font-mono text-xs bg-zinc-800/60 px-2 py-0.5 rounded`
- v1.0 dead-code removed: `scheduler/agents/content/*.py` retired format files + lock-ID dict entries 1010-1016 + referencing comments — stripped as final task of this phase
- Visual QA pass confirmed: all 3 tabs at 1440x900; no layout regressions; no dark-mode contrast failures (WCAG AA on text)

**Success Criteria** (what must be TRUE when this phase completes):
1. All three tabs use a visually consistent amber-500/zinc hierarchy — the active tab indicator, today cell, and primary buttons all use amber-500; no stray blue or gray primary accents remain
2. All card surfaces (summary cards, calendar chips, sweep card sections) share identical border (`border-zinc-800`) and hover transition (`hover:border-zinc-700`) behavior
3. Typography weights are consistent across the UI: headings are visually heavier than sub-headings, body text reads cleanly, Reddit scores and virality source counts render in monospace
4. The v1.0 dead-code strip completes without a scheduler import error on restart — confirming no surviving caller referenced the deleted files; lock-ID dict entries 1010-1016 are removed and OPS-02 assertion still passes
5. A visual QA pass at 1440x900 finds no layout overflow, no invisible text (WCAG AA contrast), and no broken shadcn interactive primitives (Dialog, tab strip, dropdown)

**Plans:** 4 plans
- [x] 08-01-PLAN.md — Wave 0 validation scaffolding: vitest test stubs (XHandlePill, MarkdownContent, rehypeHandleMentions) + index.css token test + 4 grep scripts (UI-02/03/04 + pre-strip safety)
- [x] 08-02-PLAN.md — Wave 1 UI polish: add 3 semantic amber tokens to index.css; apply hover:border-zinc-700 transition-colors to SummaryCard + SweeperCard; verify DayCell + SectionBlock (UI-01 / UI-02 / UI-03 / UI-04)
- [x] 08-03-PLAN.md — Wave 2 UI-05 X-handle pill: create XHandlePill + rehypeHandleMentions + MarkdownContent; wire into SweeperCard (3 sections) + SectionBlock; rephrase REQUIREMENTS UI-05; human-verify UI-07 visual QA checkpoint (UI-05 / UI-07) (completed 2026-05-19)
- [x] 08-04-PLAN.md — Wave 3 UI-06 dead-code strip: update test_worker.py assertions, shrink JOB_LOCK_IDS to 4 keys, delete 6 sub-agent source + 8 test files, remove scheduler/agents/content/ directory; runs LAST per D-09 (UI-06)

**UI hint**: yes

**Complexity:** M
**Estimated duration:** 2-4 hours

**Dependencies:**
- Phases 5, 6, 7 all merged: cannot polish surfaces that don't exist; cannot strip dead code until sure no caller survives in new feature code

**Hard parts (cross-ref PITFALLS.md):**

| # | Pitfall | Severity | Prevention |
|---|---------|----------|-----------|
| P1 | Tailwind v4 dark mode strategy — class-based vs media-query — may have changed from v3 | HIGH | Audit Tailwind config: if dark mode is class-based, add `@custom-variant dark (&:is(.dark *))` to CSS config; if media-query, amber token additions must use CSS custom properties only |
| P2 | New color tokens redefine `zinc-*` values and break `AppHeader.tsx` existing classes | MEDIUM | UI pass done in a single comprehensive sweep (not piecemeal); prefer adding semantic tokens (`--color-surface`, `--color-surface-elevated`) over redefining the zinc scale |
| P3 | Dead-code strip references: Phases 6 or 7 accidentally re-introduced a caller | MEDIUM | `grep -r "content/" scheduler/agents/` before stripping; grep for lock IDs 1010-1016 in `worker.py`; only strip after confident no survivors |

**Architecture reference:** ARCHITECTURE.md — "Complete File Change Map" (MODIFIED + UNCHANGED files); confirmed `AppShell.tsx` and `AppHeader.tsx` are structurally unchanged
**Feature reference:** FEATURES.md — "LINEAR-STYLE UI REDESIGN" (dark + amber-500 token direction); PITFALLS.md section 6 "shadcn Tabs + Linear UI Redesign"

---

### Phase 9: Multi-Tenant Foundation

**Goal:** The single-tenant Seva dashboard becomes a two-tenant platform in a single atomic deploy. `/seva/*` renders byte-equivalent to v2.1; `/juno/*` renders auth-gated empty-state pages on all 3 tabs; one scheduler fire produces a Seva `daily_summaries` row AND a Juno `daily_summaries` row (Juno is `status='partial'` because feeds are empty until Phase 10). Partial multi-tenancy is worse than none — every read, every write, every cache key, every cron, and every route must be tenant-scoped before merge.

**Depends on:** v2.1 Phase 8 merged and verified (UI baseline locked, dead-code stripped, OPS-02 assertion at 4 lock-ID keys)

**Requirements:** TENANT-01, TENANT-02, TENANT-03, TENANT-04, TENANT-05, TENANT-06, TENANT-07, TENANT-08, TENANT-09, TENANT-10

**Inputs:**
- v2.1 codebase post-Phase 8 with Alembic head at `0013_calendar_title_nullable_unique_date`; next free revision is `0014`
- `JOB_LOCK_IDS` dict at 4 keys post-UI-06 strip (`midday_digest: 1005`, `daily_summary: 1017`, `daily_summary_prune: 1018`, `weekly_sweeper: 1019`); IDs 1010-1016 are reserved-dead and MUST NEVER be reused
- `frontend/src/components/layout/AppHeader.tsx` byte-frozen at v2.1 baseline (UI-07 visual QA passed 2026-05-19); freeze treatment is a discuss-phase decision (Path A vs Path B)
- Three v2.x tenant-scoped tables (`daily_summaries`, `calendar_items`, `weekly_sweeps`) — all rows owned implicitly by Seva
- `scheduler/agents/daily_summary.py` orchestrator + `scheduler/agents/daily_summary_prune.py` + `scheduler/agents/weekly_sweeper.py` (Seva-only call sites; ~20+ raw `select(DailySummary|CalendarItem|WeeklySweep)` sites in backend + scheduler require audit)
- `frontend/src/App.tsx` with v2.1 route shape: `/` → `<TabbedDashboard>`, plus `/queue` `/agents/:slug` `/digest` `/settings` `/login` grace redirects
- TanStack Query keys currently scalar (`['summaries', limit]`, `['calendar', start, end]`, `['weekly-sweeps', limit]`) — leak risk on tenant switch
- `.planning/research/{STACK,ARCHITECTURE,PITFALLS,FEATURES}.md` for all five architectural decisions D-01..D-05 (discuss-phase agenda)

**Outputs:**
- `backend/alembic/versions/0014_add_company_id.py` — adds `company_id VARCHAR(20)` with `DEFAULT 'seva'` (expand/contract pattern — closes backfill race) to all 3 tenant-scoped tables; backfills existing rows in same transaction; adds CHECK constraint `company_id IN ('seva', 'juno')`; drops + recreates indexes as composite `(company_id, <existing-sort>)`; recreates `uq_calendar_items_date` as `uq_calendar_items_company_date`; reversible `downgrade()`
- `backend/app/queries/scoped.py` NEW — `scoped_summaries(company_id)`, `scoped_calendar(company_id)`, `scoped_weekly_sweeps(company_id)` helpers; CI grep gate blocks raw `select(DailySummary|CalendarItem|WeeklySweep)` outside this module
- `backend/app/companies/` NEW package — `__init__.py` exports `ACTIVE_COMPANIES: tuple[str, ...] = ("seva", "juno")` + `CompanyId` Literal type
- `backend/app/dependencies.py` MODIFIED — adds `get_current_company(company: str) -> CompanyId` resolving from URL path param; raises 404 on unknown company
- `backend/app/main.py` MODIFIED — `app.include_router(..., prefix="/api/{company}")` for summaries/calendar/weekly-sweeps; auth/settings/digest stay at root
- `backend/app/routers/{summaries,calendar,weekly_sweeps}.py` MODIFIED — inject `company: CompanyId = Depends(get_current_company)`; replace raw `select()` with `scoped_*()` helpers
- `backend/app/models/{daily_summary,calendar_item,weekly_sweep}.py` MODIFIED — add `Column("company_id", String(20), nullable=False)`; calendar_item UniqueConstraint becomes `(company_id, date)`
- `scheduler/companies/` NEW package — `__init__.py` exports `ACTIVE_COMPANIES` + `get_config(company_id)`; `base.py` defines `CompanyConfig` dataclass (sections list, RSS feeds, SerpAPI queries, sonnet_system_prompt); `seva/` subpackage relocates `GOLD_NEWS_SYSTEM_PROMPT` + gold RSS + gold SerpAPI queries; `juno/` subpackage created with stub `feeds.py = []`, stub `serpapi.py`, stub `prompts.py` (populated in Phase 10)
- `scheduler/models/{daily_summary,calendar_item,weekly_sweep}.py` MODIFIED — dual-model parity; add `company_id` Column matching backend
- `scheduler/agents/daily_summary.py` MODIFIED — `run_daily_summary()` becomes `for company_id in ACTIVE_COMPANIES: try: await _run_daily_summary_for_company(company_id) except: log+continue`; `_run_daily_summary_for_company()` extracts per-company body parameterized on `company_id`; idempotency check is per-company (`exists(SELECT 1 FROM daily_summaries WHERE company_id=$1 AND date=today AND status='completed')`); `agent_runs.notes` JSON includes `company_id`
- `scheduler/agents/daily_summary_prune.py` MODIFIED — per-company `DELETE FROM daily_summaries WHERE company_id=$1 AND generated_at < now()-30days`
- `scheduler/agents/weekly_sweeper.py` MODIFIED — per-company loop (Juno path is a no-op stub gated by `JUNO_CONFIG.sweeper_enabled = False`; v3.1+ flips the flag); X API queries via `get_config(company_id).x_api_queries`
- `scheduler/worker.py` MODIFIED — imports `ACTIVE_COMPANIES`; JOB_LOCK_IDS topology decision deferred to discuss-phase (see Hard Parts: scheduler topology)
- `frontend/src/App.tsx` MODIFIED — wrap `<TabbedDashboard>` in `<Route path=":company" element={<CompanyScopedRoute />}>`; `<Route index element={<Navigate to="/seva" replace />} />`; preserve v2.x bookmark grace redirects (`/queue`, `/agents/:slug`, `/`, `/calendar`, `/viral` all redirect to Seva targets); `/digest` and `/settings` remain non-tenanted
- `frontend/src/components/layout/CompanyScopedRoute.tsx` NEW — reads `useParams<{company: string}>()`, validates against `ACTIVE_COMPANIES`, redirects to `/seva` on invalid, publishes to `companyStore`, renders `<Outlet />`
- `frontend/src/components/layout/CompanySwitcher.tsx` NEW — segmented control (2 NavLink buttons styled as toggle); active from `useParams()`; navigate preserves current sub-path (`/{newCompany}` + current tab); placement decision (header edit vs sibling `CompanyBar.tsx`) deferred to discuss-phase
- `frontend/src/components/layout/AppHeader.tsx` MODIFIED IF Path A chosen (5-line insertion between brand + Logout); OR `frontend/src/components/layout/CompanyBar.tsx` NEW + `AppShell.tsx` MODIFIED to render sibling component IF Path B chosen
- `frontend/src/components/layout/TabNav.tsx` MODIFIED — NavLink `to` props prepend `/${company}` (reads from `useParams()`)
- `frontend/src/stores/companyStore.ts` NEW — Zustand store with `persist` middleware; `lastVisited: CompanyId`; SINGLE writer is `CompanyScopedRoute`; consumers are read-only
- `frontend/src/api/queryKeys.ts` NEW — centralized key factory: `summaries(c, limit) → ['summaries', c, limit]`; `calendar(c, start, end) → ['calendar', c, start, end]`; `weeklySweeps(c, limit) → ['weekly-sweeps', c, limit]`; CI grep gate forbids `queryKey: [` outside this module
- `frontend/src/api/{summaries,calendar,weeklySweeps}.ts` MODIFIED — `getX(company, ...)` fetches `/api/{company}/...`; `useX(company)` consumes `queryKeys` factory; on company switch CompanyScopedRoute calls `queryClient.clear()` (nuclear, simplest defence against stale render)
- `frontend/src/pages/{SummaryFeedPage,ContentCalendarPage,WeeklyViralSweeperPage}.tsx` MODIFIED — read `company` from `useParams()` and pass to hooks; render explicit empty-state component when `total=0` AND `company=juno` ("Juno News Funnel — first daily summary will appear after Phase 10 ships and the next 08:00 PT cron fires")
- `backend/app/routers/auth.py` MODIFIED — login captures `state.from` from `<ProtectedRoute>`; on success navigate to `from` (default `/seva`) preserving pathname + search + hash
- `backend/tests/test_multitenant_isolation.py` NEW — for EVERY list/detail endpoint and EVERY cron, insert both Seva and Juno rows, assert tenant-scoped responses return ONLY the requested tenant; build fails on any cross-tenant leakage
- `scheduler/tests/test_company_config.py` NEW — startup assertion that DB CHECK constraint enum matches `ACTIVE_COMPANIES`; Seva-only agents (`ontario_law`, `ontario_stats`) only run inside `_run_daily_summary_for_company('seva')`

**Success Criteria** (what must be TRUE when this phase completes):
1. Visiting `/seva/` renders the v2.1 News Funnel byte-equivalent (3-section SummaryCard with Gold News + Ontario Law + Ontario Stats from the latest Seva `daily_summaries` row); visiting `/juno/` renders empty-state copy on all 3 tabs ("Juno News Funnel — first daily summary will appear after Phase 10 ships"); switching companies via the switcher updates the URL (`/seva/calendar` → `/juno/calendar`) and clears TanStack cache so no Seva data flashes on the Juno render at any point
2. `alembic upgrade head` lands 0014 cleanly with zero NULL `company_id` rows post-deploy (`SELECT count(*) FROM daily_summaries WHERE company_id IS NULL` returns 0; same for calendar_items + weekly_sweeps); `alembic downgrade -1` reverses cleanly back to v2.1 schema; `EXPLAIN ANALYZE` on the canonical "latest summary" query uses `ix_daily_summaries_company_generated` composite index (not `Filter:`)
3. One manually-triggered `run_daily_summary()` fire produces TWO `daily_summaries` rows in the same Postgres transaction window — one with `company_id='seva'` and `status='completed'` (real content), one with `company_id='juno'` and `status='partial'` (empty feeds — graceful no-op per Phase 9 stub); `agent_runs.notes` JSON contains `company_id` for both; OPS-02 lock-ID assertion passes on scheduler boot
4. v2.x bookmarks survive the migration: visiting `/`, `/calendar`, `/viral`, `/queue`, `/agents/:slug` as an authenticated user all land on the correct `/seva/*` page (no 404, no auth bypass); bookmarking `/juno/calendar` then logging out, then logging back in, returns the operator to `/juno/calendar` (login preserves intended URL); CI grep gate blocks raw `select(DailySummary|CalendarItem|WeeklySweep)` outside `queries/scoped.py` and raw `queryKey: [` outside `api/queryKeys.ts`
5. `test_multitenant_isolation.py` passes with both Seva and Juno fixtures inserted: every list endpoint returns only the requested tenant's rows; cross-tenant `company_id` in URL path returns 404; ` AppHeader/CompanyBar` switcher visible on every authenticated page (including `/digest` and `/settings`)

**Plans:** 5 plans

Plans:
- [x] 09-01-PLAN.md — Wave 0 RED-tests-first scaffolding (12 Wave 0 test files + CI grep gate `scripts/verify-tenant-isolation.sh` per VALIDATION.md)
- [x] 09-02-PLAN.md — Wave 1 DB foundation (Alembic 0014 with `server_default='seva'` + dual-model parity + `backend/app/queries/scoped.py` helpers + `get_current_company` FastAPI dep)
- [x] 09-03-PLAN.md — Wave 2 backend routers + scheduler (3 routers under `/api/{company}` + per-company cron with `juno_daily_summary=1020` lock ID + `juno_weekly_sweeper=1021` slot reserved + `run_juno_daily_summary` stub writes `status='partial'` row)
- [x] 09-04-PLAN.md — Wave 3 frontend routing + switcher + queryKeys (`<Route path=':company'>` wrapper + bookmark grace redirects + `CompanySwitcher` segmented control inside formally freeze-lifted AppHeader + Zustand persist for `lastVisitedCompany` + centralized TanStack key factory + per-page Juno empty-state short-circuits)
- [x] 09-05-PLAN.md — Wave 4 cross-tenant integration verification + human-verify checkpoint at 1440×900 (populates `test_multitenant_isolation.py` parametrized matrix; runs full 3-layer test suite + CI grep gate; reproduces verbatim 50+ item UI-SPEC QA checklist; smoke-tests one scheduler fire produces both tenants' rows; documents AppHeader freeze-lift in PROJECT.md Key Decisions per D-02 third documentation location)

**UI hint**: yes

**Complexity:** L (heaviest phase in v3.0 — single atomic deploy spans Alembic migration, backend router restructure, scheduler per-company fan-out, frontend routing migration, AppHeader freeze treatment, TanStack cache strategy; cross-tenant leak is the #1 v3.0 bug class)
**Estimated duration:** 6-9 hours

**Dependencies:**
- v2.1 Phase 8 merged: lock-ID dict at 4 keys post-UI-06 strip; AppHeader visual baseline locked
- `alembic heads` must confirm exactly one head (`0013`) before writing `0014_add_company_id.py` `down_revision`
- Discuss-phase MUST resolve three architectural decisions BEFORE plan-phase: (a) scheduler topology, (b) AppHeader freeze treatment, (c) `companies` DB table vs hardcoded CHECK
- Migration window scheduled outside the 08:00 PT / 12:00 PT cron windows (recommend 04:00 PT, between 03:00 prune cron and 08:00 daily_summary cron); Railway worker process restart acceptable for ~30s during migration (single-operator, internal tool)

**Hard parts (cross-ref PITFALLS.md):**

| # | Pitfall | Severity | Prevention |
|---|---------|----------|-----------|
| P1 | Cross-tenant leak — a query forgets `WHERE company_id = ?` and returns Juno data to Seva user (catastrophic; v3.0 ships immediately broken) | CRITICAL | PITFALLS §1 — `scoped_*()` helpers (`backend/app/queries/scoped.py`); CI grep gate blocks raw `select(DailySummary|CalendarItem|WeeklySweep)` outside helpers; `test_multitenant_isolation.py` covers every list/detail endpoint |
| P2 | Async session ContextVar leak across pool connections (asyncpg + Neon `-pooler` reuses connections across asyncio Tasks; SET-not-SET-LOCAL persists tenant state to next request) | CRITICAL | PITFALLS §1 — NO middleware ContextVar magic; pass `company_id` as EXPLICIT parameter on every repository function; a repo function without `company_id` is impossible to call against the wrong tenant |
| P3 | Lock-ID collision when adding per-company crons — registered job vs unregistered job collision (OPS-02 assertion catches dict collisions but not "registered job uses an ID not in JOB_LOCK_IDS") — **DISCUSS-PHASE DECISION** | CRITICAL | PITFALLS §3.4 — three proposals on the table: (a) ARCHITECTURE D-02 single-cron-fanout (ZERO new IDs, reuse 1017/1018/1019); (b) STACK explicit per-company jobs (juno_daily_summary=1020, juno_weekly_sweeper=1021); (c) PITFALLS per-tenant 100-ID blocks (Juno 1100-1199 with 1117/1118/1119 reserved). Trade-off axes: failure isolation, lock-ID inventory, future N tenants. Must add second OPS-02 assertion: `set(scheduler.get_jobs_ids()) <= set(JOB_LOCK_IDS.keys())` after build_scheduler() returns |
| P4 | AppHeader freeze treatment — Phase 5 byte-freeze on `AppHeader.tsx` vs v3.0 milestone-level requirement for a company switcher in conventional header location — **DISCUSS-PHASE DECISION** | HIGH | PITFALLS §5 — two acceptable paths: (a) ARCHITECTURE D-04 Path A (lift the freeze formally, document v3.0 milestone-level rationale, surgical 5-line insertion between brand + Logout, re-baseline visual QA); (b) PITFALLS Path B (preserve freeze, add `CompanyBar.tsx` sibling component below AppHeader in its own border-b sub-bar). Trade-off: UX convention vs freeze contract integrity. PITFALLS recommends Path B for v3.0 launch (lower-risk); ARCHITECTURE recommends Path A (cleaner long-term) |
| P5 | `companies` DB table vs hardcoded CHECK constraint — **DISCUSS-PHASE DECISION** | MEDIUM | PITFALLS §3.4 + STACK + ARCHITECTURE D-05 disagree: STACK proposes Alembic 0014 creates `companies (id, display_name, created_at)` table with FK from `daily_summaries.company_id`; ARCHITECTURE D-05 keeps per-company config in Python `scheduler/companies/` package only (no DB table — operator has no runtime config UI in v3.0); PITFALLS accepts hardcoded `('seva', 'juno')` CHECK as v3.0 tech debt with FK upgrade by v3.2+. Trade-off: referential integrity day-one vs config-as-code |
| P6 | 0014 migration backfill race with daily_summary cron (cron fires DURING `ALTER ADD COLUMN` → `UPDATE backfill` → `ALTER SET NOT NULL`; new INSERT writes NULL `company_id`; migration fails on SET NOT NULL; Railway deploy aborts mid-way) | HIGH | PITFALLS §1 — expand/contract pattern (mandatory): ADD COLUMN with `DEFAULT 'seva'` so DEFAULT-fills new rows during migration window; drop DEFAULT in a v3.0.1 follow-up migration after all callers pass `company_id` explicitly. Schedule migration outside 08:00/12:00 PT cron windows (04:00 PT recommended) |
| P7 | TanStack Query keys missing `company_id` — operator switches Seva→Juno; cached Seva data renders for 200-2000ms while background refetch loads Juno data; first frame after switch is wrong tenant | HIGH | PITFALLS §4 — centralize keys in `frontend/src/api/queryKeys.ts` factory; `queryClient.clear()` on company switch (nuclear, simplest); CI grep gate blocks raw `queryKey: [` outside factory module; switcher behavior test asserts no Seva data appears in Juno render at any time |
| P8 | Existing bookmarks to `/` break — v2.x users land on 404 (or worse, a public route that bypasses auth depending on route ordering) | CRITICAL | PITFALLS §4.1 — grace redirects inside `<ProtectedRoute />`: `/` → `/seva`, `/calendar` → `/seva/calendar`, `/viral` → `/seva/viral`, `/queue` → `/seva`, `/agents/:slug` → `/seva`; test each old path from incognito session as authenticated user |
| P9 | Single cron iterating companies: one slow tenant blocks the next (Seva Sonnet 60s timeout delays Juno start; misfire cascade) | HIGH | PITFALLS §3.2 — discuss-phase scheduler topology decision (P3) determines whether sequential try/except (D-02 Option 1) is acceptable, or per-company independent jobs are required (Option 2/3). For Option 1 acceptable, document that Seva failure does not block Juno because they run sequentially with per-company try/except scoping (NOT concurrent) — operator must accept Juno waits up to 60s for Seva Sonnet timeout |
| P10 | Idempotency: cron retry re-summarizes Seva (misfire fires AFTER Seva completed but BEFORE Juno started) | HIGH | PITFALLS §3.3 — per-company idempotency pre-check before running tenant logic: `SELECT 1 FROM daily_summaries WHERE company_id=$1 AND date=today AND status='completed'` — skip with `agent_runs.status='skipped_already_completed'` if exists; extends v2.x single-tenant pattern |
| P11 | Login redirect drops company context — operator bookmarks `/juno/calendar`, logs in, lands at `/seva` (or `/`); has to manually re-navigate via switcher | HIGH | PITFALLS §4 — `<ProtectedRoute>` captures `state.from` (pathname + search + hash); `<LoginPage>` reads `location.state?.from?.pathname || '/seva'` and navigates there on success |
| P12 | Missing composite index `(company_id, generated_at DESC)` on multi-tenant tables — query plan shows `Filter: company_id =` instead of `Index Cond:` | HIGH | PITFALLS §1 — in 0014 migration: DROP single-column indexes, CREATE composite with `company_id` LEADING; document "company_id leads every multi-tenant index" rule in CONVENTIONS.md |
| P13 | Test fixtures don't reset `company_id` context between tests — tests pass individually, leak between fixtures in `pytest -n auto`; CI green doesn't prove isolation | MEDIUM | PITFALLS §1 — ALL ContextVar/tenant fixtures `@pytest.fixture(scope="function")` with explicit teardown; fixture factories take `company_id` as required param (no default); `test_multitenant_isolation.py` runs Seva + Juno fixtures in same session |
| P14 | Tab state leaks across company switches (calendar week offset, filter chip selection persist in flat Zustand store across tenant switch — meaningless state from Juno applied to Seva view) | MEDIUM | PITFALLS §4 — for v3.0 launch, simplest fix is `queryClient.clear()` on switch (already required for P7); any future tenant-scoped UI state goes in URL search params (`?week=2026-W21`), NOT global Zustand |
| P15 | Cross-tenant FK pointer — `daily_summaries.agent_run_id → agent_runs.id` doesn't enforce that `daily_summaries.company_id == agent_runs.company_id`; buggy code path silently corrupts audit trail | MEDIUM | PITFALLS §1 — application-layer assert in `_run_daily_summary_for_company()` write path: `assert agent_run.company_id == summary.company_id`; composite FK pattern deferred to v3.1+ |

**Architecture reference:** ARCHITECTURE.md — Decisions D-01 (row-level `company_id`), D-02 (scheduler topology — discuss-phase), D-03 (path-prefix routing `/:company`), D-04 (AppHeader freeze treatment — discuss-phase), D-05 (per-company config namespace); §3 "System Diagram (v3.0)"; §4 "Complete File Change Map"
**Feature reference:** FEATURES.md — "CATEGORY 1 — MULTI-TENANCY PLUMBING" (table stakes + anti-features); URL routing decision point; switcher UX decision point; STACK.md "Multi-Tenancy: Recommended Strategy" + "Frontend: Company Switcher + URL Routing" + "Scheduler Topology for Per-Company Cron"

---

### Phase 10: Juno Defence News Funnel

**Goal:** Tab 1 of `/juno/` renders a live defence-industry daily summary with three sections (Defence News + Canadian Procurement + World Events Relevant to Defence). Config-only after Phase 9 — no new infrastructure, no new schema, no new routing. Juno's content is populated by Tier-1 defence RSS feeds (Defense News × 8 sub-feeds + Breaking Defense + DefenseScoop + RUSI Commentary + RUSI Publications + SIPRI Combined, all directly HTTP-validated 2026-05-19) plus SerpAPI `site:` fallback for paywalled sources (Janes, IISS, Reuters defence, Bloomberg defence) and Canadian-procurement queries (`site:canada.ca defence`, Canadian Defence Review, Lagassé Substack, Atlantic Council); a Sonnet 4.6 system prompt designed from scratch in senior-defence-analyst voice (Janes/CSIS desk energy — anti-tactical framing, dual-use exclusion list, regional balance heuristic); a Haiku 4.5 structured-output relevance classifier gates the World Events section against 9 named inclusion categories (active conflict, alignment shifts, spending policy, sanctions/export controls, energy/critical-minerals, semiconductors, space, hypersonic/AI/autonomy, treaty events); a refusal-detector wraps the Sonnet call to gracefully degrade on Anthropic-Pentagon-precedent content-policy refusal; and a voice-calibration UAT (5-10 hand-curated defence stories) gates production cron enablement.

**Depends on:** Phase 9 merged and verified — `/seva/*` byte-equivalent to v2.1, `/juno/*` empty-state renders, one scheduler fire produces both Seva (`completed`) and Juno (`partial`) rows, `test_multitenant_isolation.py` passes, CI grep gates active, AppHeader/CompanyBar switcher functional, TanStack cache strategy verified

**Requirements:** DEF-01, DEF-02, DEF-03, DEF-04, DEF-05, DEF-06, DEF-07, DEF-08, DEF-09, DEF-10

**Inputs:**
- Phase 9 infrastructure live: `company_id` column on 3 tables, `scoped_*()` helpers, `/api/{company}` router prefix, `/:company/` frontend routing, `scheduler/companies/juno/` package skeleton with stub `feeds.py = []`, stub `serpapi.py`, stub `prompts.py`
- `scheduler/agents/daily_summary.py` per-company loop (Phase 9) with Juno path wired but returning `status='partial'` because Juno config is empty
- Tier-1 defence RSS feed inventory directly HTTP-validated 2026-05-19 in `.planning/research/STACK.md` "Defence RSS Feed Inventory" — Defense News (Industry, Pentagon, Global, Air, Land, Naval, Space, Unmanned), Breaking Defense, DefenseScoop, RUSI Commentary, RUSI Publications, SIPRI Combined (12 feeds validated; 3 deferred for Phase-0 verification: war.gov, nato.int, canada.ca)
- `anthropic>=0.86.0` SDK already installed (structured outputs `output_format` GA across Sonnet 4.5+, Haiku 4.5+, Opus 4.5+)
- `serpapi` SDK + `feedparser 6.0.x` already installed (v2.0 stack); existing $50/mo SerpAPI budget envelope tolerates ~$5-15/mo incremental for defence queries
- Existing v2.0 `daily_summary.py` patterns: status state machine (`completed`/`partial`/`failed`), SequenceMatcher 0.85 deduplication threshold, URL canonicalization, `raw_sources_jsonb` NULL guard, AsyncAnthropic timeout=60.0
- `SummaryCard.tsx` component (Phase 9 tolerates missing-or-renamed section markdown fields per DEF-08)

**Outputs:**
- Phase-0 verification of 3 deferred RSS endpoints (war.gov press-releases, nato.int news, canada.ca defence) via `curl -sI`; SerpAPI fallback documented for any that 404
- `scheduler/companies/juno/feeds.py` POPULATED — `JUNO_DEFENCE_RSS_FEEDS` list of Tier-1 + Tier-2 feeds (12 validated + verified Phase-0 additions); each entry `(slug, url, tier, classification)` where `classification ∈ {wire, analysis, opinion, newsletter}` (Phase 10 ingests `wire` + `analysis` only); per-feed `bozo`/`entries=[]` health-check with recent-history comparison + partial-status surface
- `scheduler/companies/juno/serpapi.py` POPULATED — `JUNO_SERPAPI_QUERIES` covering: (a) paywalled defence fallback (`engine=google_news q="site:janes.com defence"`, `site:iiss.org military balance`, `site:reuters.com defence OR military`, `site:bloomberg.com defence`); (b) Canadian procurement (`site:canada.ca defence`, `site:canadiandefencereview.com`, `site:atlanticcouncil.org canada defence`); (c) Lagassé Substack via Google News `site:philippelagasse.substack.com`
- `scheduler/companies/juno/prompts.py` POPULATED — `DEFENCE_NEWS_SYSTEM_PROMPT` designed from scratch (explicitly NOT cloned from `GOLD_NEWS_SYSTEM_PROMPT` per PITFALLS Technical Debt): senior defence analyst voice (Janes/CSIS desk energy); anti-tactical framing ("market/industry commentary only — never operational/targeting"); explicit dual-use exclusion list (consumer device launches, general AI/LLM releases unless defence-specific, crypto, sports/entertainment, climate without defence linkage); regional balance heuristic (US 4-5 / Canada 2 / Europe 2 / Indo-Pacific 1-2 / NATO 1 quota); contract-value extraction instruction ("cite dollar amount, program designator, vendor, contracting authority where present"); grounding rule ("Use ONLY facts present in supplied inputs"); inclusion-category tag emission for World Events section
- `scheduler/agents/juno_relevance.py` NEW — Haiku 4.5 structured-output classifier; Pydantic schema `DefenceRelevance(is_relevant: bool, category: Literal[9 named categories], confidence: float [0..1], reasoning: str max_length=200)`; only `is_relevant=True AND confidence >= 0.7` items flow to Sonnet synthesis; ~$1-2/mo at projected 30-50 candidate stories/day
- `scheduler/companies/juno/refusal_detector.py` NEW — wraps Sonnet call; inspects response for refusal patterns ("I can't help with", "I'm not able to provide", response < 100 chars, classic refusal preamble "I understand you're looking for..."); on refusal detection, retries ONCE with framing nudge ("Analyze as defence-industry market commentary, not tactical intelligence"); on second refusal falls back to `status='partial'` with refused section blanked (mirrors v2.1 partial status pattern in `daily_summary.py`)
- `scheduler/agents/daily_summary.py` MODIFIED (extending Phase 9 stub) — `_run_daily_summary_for_company('juno')` body populated: ingest RSS feeds with per-feed health-check; ingest SerpAPI queries with Canadian-procurement subset; deduplicate by canonical URL (existing v2.0 SequenceMatcher 0.85); rank by distinct-source-diversity; call Haiku relevance classifier on candidate world-events pool; call Sonnet 4.6 synthesis with refusal-detector wrapper; write `daily_summaries` row with `company_id='juno'`, `defence_news_md`, `canadian_procurement_md`, `world_events_md`, `raw_sources_jsonb = {"defence_news": [...], "canadian_procurement": [...], "world_events": [...]}`
- `backend/app/models/daily_summary.py` MODIFIED — add nullable `defence_news_md`, `canadian_procurement_md`, `world_events_md` TEXT columns via Alembic 0015 (sibling section columns; Seva uses gold_news_md/ontario_law_md/ontario_stats_md; Juno uses the defence trio); no rename of existing Seva columns
- `backend/app/schemas/daily_summary.py` MODIFIED — `SummaryCardResponse` exposes all 6 section markdown fields as optional; per-company section configuration in `companies/seva|juno/__init__.py` declares which sections render
- `frontend/src/components/summary/SummaryCard.tsx` MODIFIED — renders sections conditionally based on which markdown fields are populated AND per-company section list (no per-tenant SummaryCard fork per DEF-08); section labels driven by `companyStore.sectionLabels[company]`
- `frontend/src/pages/ContentCalendarPage.tsx` + `WeeklyViralSweeperPage.tsx` MODIFIED for Juno — render explicit empty-state copy "Coming in v3.1 — Juno Calendar/Sweeper not yet enabled" when `company === 'juno'` (per DEF-09); Seva paths unchanged
- `scheduler/companies/juno/voice_calibration_uat.md` NEW (artifact persisted in phase directory) — 5-10 hand-curated defence stories (Ukraine aid, Israeli operations, Taiwan tensions, Iran sanctions, Korea hypersonic test, Lockheed F-35 contract, GCAP milestone, Canadian P-8A delivery, NATO 2% commitment, semiconductor export control); operator runs the cron against the calibration set with `juno_daily_summary_dry_run.py`; confirms tone (Janes/CSIS desk energy), depth (cites contract value + vendor + region), signal-to-noise (no consumer tech bleed), dual-use boundary (excludes pure consumer AI/crypto/sports)
- `scheduler/agents/juno_daily_summary_dry_run.py` NEW (escape hatch) — `python -m scheduler.agents.juno_daily_summary_dry_run` runs the Juno path against the calibration corpus without writing to `daily_summaries`; prints structured output for operator review; gates production cron enablement
- `backend/tests/test_juno_relevance_classifier.py` NEW — 5-10 known-edge-case stories test corpus (Ukraine military aid, Israel-Gaza, Taiwan Strait, Iran sanctions, Korean hypersonic); monthly regression run asserts no `"sonnet_refused"` errors and no false-positive consumer-tech inclusion
- `backend/tests/test_defence_feed_health.py` NEW — asserts per-feed `bozo=1 AND entries=[]` triggers `agent_runs.errors` entry + `status='partial'` row; mocks feedparser to return empty for one feed and validates graceful degradation

**Success Criteria** (what must be TRUE when this phase completes):
1. Juno daily summary card on `/juno/` Tab 1 shows 3 sections (Defence News + Canadian Procurement + World Events Relevant to Defence) populated with real content from the latest production cron fire; each section has 3-7 bulleted items; Defence News cites contract value + vendor + program designator where present (e.g. "Lockheed wins $850M PAC-3 contract"); Canadian Procurement cites at least one DND/PSPC/Canadian Defence Review source; World Events items each carry an inclusion-category tag rendered as a small badge
2. Operator confirms voice calibration matches Janes/CSIS desk energy — Voice Calibration UAT against 5-10 hand-curated defence stories produces summaries the operator approves on tone (senior analyst, not advocate), depth (specifics over generalities), signal-to-noise (no consumer tech, no sports, no crypto), and dual-use boundary (no operational/tactical framings); UAT artifact persisted in phase directory; production cron remains DISABLED until operator signs off
3. Refusal-detector tested against ≥5 edge-case stories (Ukraine military aid, Israel-Gaza, Taiwan Strait, Iran sanctions, Korean hypersonic) with zero `"sonnet_refused"` markers in `agent_runs.errors`; one synthetic refusal-trigger test confirms the detector flips status to `partial` with the refused section blanked (NOT `failed`)
4. Per-feed RSS health-check surfaces silent-feed-death: a feed returning `bozo=1 AND entries=[]` writes an entry to `agent_runs.errors` with the URL and `bozo_exception`; `status='partial'` row renders without the dead feed's stories rather than failing the whole cron; recent-history comparison alerts via existing WhatsApp failure-alert pattern (`WHA-03`) when a feed's entry count drops to 0 after recently returning ≥5
5. `SELECT count(*) FROM daily_summaries GROUP BY company_id` after 7 days of production cron fires matches expected counts per tenant (Seva: 14 rows from 2x-daily; Juno: 14 rows from 2x-daily, both staggered ≥5 minutes apart per CONVENTIONS.md rate-limit rule); Seva renders byte-identical to pre-v3.0; `test_multitenant_isolation.py` continues to pass with real Juno content (no Seva cross-contamination)

**Plans:** 4/5 plans executed

- [x] 10-01-PLAN.md — Wave 0: Phase-0 RSS verification + 8 Wave 0 RED test files + companySectionConfig.ts production module (DEF-01..08 scaffolds)
- [x] 10-02-PLAN.md — Wave 1: Haiku 4.5 World Events classifier + populated JUNO_DEFENCE_FEEDS + JUNO_SERPAPI_QUERIES + production DEFENCE_NEWS_SYSTEM_PROMPT (DEF-01, DEF-02, DEF-03, DEF-06)
- [x] 10-03-PLAN.md — Wave 2: refusal-detector + extended run_juno_daily_summary with health-check + 3-section Sonnet synthesis (DEF-04, DEF-05, DEF-07)
- [x] 10-04-PLAN.md — Wave 3: SummaryCard.tsx per-tenant rendering + JUNO_CRON_ENABLED env-var gate + voice-calibration UAT operator-APPROVED (DEF-08, DEF-10)
- [ ] 10-05-PLAN.md — Wave 4: cron-enable + manual fire smoke + visual QA at 1440×900 (BLOCKING checkpoint) (DEF-09 + final verification)

**UI hint**: yes

**Complexity:** L (config-only by architecture, but voice calibration + refusal detector + relevance classifier carry research-flagged uncertainty per SUMMARY.md; voice iteration is operator-bottlenecked, not engineer-bottlenecked)
**Estimated duration:** 5-8 hours (excluding operator UAT cycles)

**Dependencies:**
- Phase 9 merged + verified: tenant isolation tests passing, CI grep gates active, switcher functional, Seva byte-identical
- Phase-0 RSS endpoint verification (war.gov, nato.int, canada.ca) as first task of plan-phase
- Operator availability for 1-3 voice-calibration UAT cycles (engineer iterates prompt between cycles; operator gates production cron enablement)
- `scheduler/companies/juno/` package skeleton from Phase 9 (stub files exist; Phase 10 populates them)
- Alembic head from Phase 9 at `0014` so `0015_add_juno_section_columns.py` `down_revision` chain is correct

**Hard parts (cross-ref PITFALLS.md):**

| # | Pitfall | Severity | Prevention |
|---|---------|----------|-----------|
| P1 | Anthropic content-policy refusal on conflict-zone news (Ukraine, Gaza, Iran/Israel, Korea, Taiwan) — Sonnet refuses or heavily hedges; Juno daily card renders with empty World Events section; Anthropic-Pentagon dispute precedent applies | HIGH | PITFALLS §2.1 — `DEFENCE_NEWS_SYSTEM_PROMPT` frames analysis as **analyst-style market commentary**, NEVER operational/tactical intelligence; explicit anti-pattern in prompt: "Do NOT provide tactical analysis, targeting recommendations, or operational details. Focus on industry/market/policy implications only."; `refusal_detector.py` wraps Sonnet call — on refusal retries once with framing nudge, falls back to `status='partial'` with section blanked; monthly regression test against 5-10 known-edge-case stories asserts zero refusals |
| P2 | Sonnet false positives — relevance filter drifts to consumer tech (iPhone launches, ChatGPT releases, crypto news) because "dual-use" surface is too broad; Juno card fills with iPhone news | HIGH | PITFALLS §2.2 — explicit exclusion list in `DEFENCE_NEWS_SYSTEM_PROMPT` (consumer device launches unless manufacturer announces defence contract; general AI/LLM releases unless defence-specific application; crypto; sports/entertainment; pure climate without defence linkage); two-stage filter: Haiku classifies `defence_direct | dual_use_relevant | excluded` → only first two reach Sonnet (mirrors v2.0 LAW-04 NRCan filter pattern); calibration set of 30-50 labeled stories run monthly with precision/recall reporting; precision floor 80% |
| P3 | RSS feed silent death — Janes / Defense News / Breaking Defense URLs reorganize without notice (Janes alone has shipped 3 distinct feed schemes in 24 months); `feedparser.parse()` returns empty `entries=[]` with `bozo=1` rather than raising; Juno daily card silently produces 0 defence stories | HIGH | PITFALLS §2.3 — per-feed `bozo`/`entries=[]` health-check after every fetch with recent-history comparison (entries=0 after recently returning ≥5 triggers WhatsApp alert via existing WHA-03 pattern); per-feed minimum threshold (if any single feed returns < 1 entry on a run AND previous run returned > 5, alert); diversify across publishers (no single publisher > 30% of stories); SerpAPI `site:` fallback discovery for dead feeds (operator confirms before prod config update) |
| P4 | Regional source bias — natural feed list (Defense News, Breaking Defense, Defense One) is US-centric; Canadian procurement (DND, RCAF, ISED), NATO announcements, European Defence Agency, Indo-Pacific stories under-represented; Juno card looks like "US defence news with a Canadian sticker" | MEDIUM | PITFALLS §2.4 — explicit regional quota in `DEFENCE_NEWS_SYSTEM_PROMPT`: US 4-5 feeds, Canada 2 (CDA Institute / Canadian Defence Review / canada.ca SerpAPI), Europe 2 (Janes EU coverage via SerpAPI, RUSI, EDA, Defence-blog), Indo-Pacific 1-2 (Australian Defence Magazine, Korea JoongAng Defense, Japan MoD English), NATO 1 (nato.int press releases — Phase-0 verify); rule documented in CONVENTIONS.md |
| P5 | Newsletter / opinion content mixed with hard news — Defense One Ideas, RealClearDefense commentary, Defence IQ thought-leadership include opinion pieces, contractor white papers, vendor-pitch-disguised-as-news | MEDIUM | PITFALLS §2.5 — feed-level classification tag (`wire | analysis | opinion | newsletter`) in `feeds.py` config; only `wire` + `analysis` reach daily summary as lead stories; title heuristic filters "Opinion:", "Commentary:", "Op-Ed:", "Sponsored:", "From Our Partners" prefixes; Sonnet prompt receives feed-classification tag as context to weight stories |
| P6 | Anthropic API rate limit hit ACROSS companies (Seva + Juno Sonnet calls + Haiku pre-filters saturate the API key's RPM/TPM in same minute); 429 retry storm cascades | MEDIUM | PITFALLS §3.5 — stagger company crons by ≥5 minutes (Seva 08:00 PT, Juno 08:05 PT); document in CONVENTIONS.md ("future companies MUST be staggered at 5-minute intervals"); monthly Anthropic usage dashboard review; v3.0 budget envelope $210-225/mo; if Juno alone pushes >$15/mo, trim Sonnet prompt size |
| P7 | Sonnet system prompt cloned from Seva's GOLD_NEWS_SYSTEM_PROMPT with minor tweaks — Seva is calibrated for gold bull thesis (wrong frame for defence); refusal + false-positive surface mounts | HIGH | PITFALLS Technical Debt — Juno prompt designed from scratch with defence-specific constraints (anti-tactical, regional balance, dual-use exclusion); engineer + operator iterate via Voice Calibration UAT (3 cycles typical); NEVER reuse Seva prompt scaffolding |
| P8 | Daily summary boundary across timezones — US Eastern news from prior 11 hours captured cleanly, but UK/Israel/Korea news 16-18 hours old; major Asian announcement at 9 AM Tokyo (5 PM PT yesterday) sits in feed 15 hours before summarization; US Eastern reaction story hits same feed and dedup hides the original | MEDIUM | PITFALLS §2.6 — keep same 08:00 PT / 12:00 PT cadence for Juno (operational simplicity); Sonnet grounding rule injects `published_at` into prompt context — "You may see stories that broke 18+ hours ago in Asia — treat publish_at timestamps as source of truth, not 'breaking now'"; defer 22:00 PT third cron to v3.1+ |
| P9 | Voice calibration without UAT corpus — engineer ships Juno cron to production; operator finds tone is wrong on first real fire; emergency prompt revision under production load | HIGH | DEF-10 — Voice Calibration UAT (5-10 hand-curated defence stories) runs BEFORE production cron enablement; `juno_daily_summary_dry_run.py` escape hatch lets engineer iterate prompt against calibration corpus without writing to `daily_summaries`; operator sign-off persisted in `voice_calibration_uat.md` artifact in phase directory |
| P10 | DND/PSPC RSS gap — no public RSS for Department of National Defence Canada or PSPC procurement; natural feed list misses Canadian-procurement signal | MEDIUM | DEF-05 + STACK Defence Feed Inventory — SerpAPI-heavier ingestion for Canadian section: `site:canada.ca defence`, `site:canadiandefencereview.com`, Lagassé Substack via Google News `site:philippelagasse.substack.com`, Atlantic Council Canadian defence briefs; v3.0 trade-off accepted (close gap if `forces.gc.ca` ever exposes RSS) |

**Architecture reference:** ARCHITECTURE.md §5 "Build Order Phase 2 — Juno News Funnel"; FEATURES.md "CATEGORY 2 — JUNO NEWS FUNNEL CONTENT" (Defence News feed catalog + Canadian Procurement source catalog) + "CATEGORY 3 — WORLD-EVENTS-RELEVANT-TO-DEFENCE" (relevance heuristic + 9 inclusion categories); STACK.md "Defence RSS Feed Inventory" (12 directly validated Tier-1 feeds) + "Sonnet Relevance Filter" (Anthropic structured outputs `output_config.format` pattern with Haiku 4.5 classification + Sonnet 4.6 synthesis)
**Feature reference:** FEATURES.md feature prioritization matrix (all DEF-* requirements at P1 priority); SUMMARY.md "Phase 2: Juno News Funnel" exit criteria (real summary on Tab 1 with non-empty Defence News + Canadian Procurement + World Events; Seva byte-identical; `count(*) GROUP BY company_id` matches expected fire counts; refusal-detector test corpus zero failures)

---

## Progress

| Phase | Milestone | Plans | Status | Completed |
|-------|-----------|-------|--------|-----------|
| 1. Gold News Card + Web Feed | v2.0 | 6/6 | Complete | 2026-05-06 |
| 2. Ontario Law Ingestion | v2.0 | 1/1 | Complete | 2026-05-06 |
| 3. Ontario Stats Ingestion | v2.0 | 1/1 | Complete | 2026-05-06 |
| 4. Prune Cron + Ops Hardening | v2.0 | 1/1 | Complete | 2026-05-06 |
| 5. Foundation — Tabs + DB + Backend Stubs | v2.1 | 5/5 | Complete | 2026-05-19 |
| 6. Content Calendar | v2.1 | 5/5 | Complete | 2026-05-19 |
| 7. Weekly Viral Sweeper | v2.1 | 6/6 | Complete | 2026-05-19 |
| 8. UI Polish + Dead-Code Strip | v2.1 | 4/4 | Complete | 2026-05-19 |
| 9. Multi-Tenant Foundation | v3.0 | 5/5 | Complete | 2026-05-19 |
| 10. Juno Defence News Funnel | v3.0 | 4/5 | In Progress|  |

---

## Coverage Check — v2.1 Requirements

All 41 requirements mapped to exactly one phase. No orphans.

| Category | Req | Phase |
|----------|-----|-------|
| TAB | TAB-01 | Phase 5 |
| TAB | TAB-02 | Phase 5 |
| TAB | TAB-03 | Phase 5 |
| TAB | TAB-04 | Phase 5 |
| TAB | TAB-05 | Phase 5 |
| DB | DB-01 | Phase 5 |
| DB | DB-02 | Phase 5 |
| DB | DB-03 | Phase 5 |
| DB | DB-04 | Phase 5 |
| DB | DB-05 | Phase 5 |
| CAL | CAL-01 | Phase 6 |
| CAL | CAL-02 | Phase 6 |
| CAL | CAL-03 | Phase 6 |
| CAL | CAL-04 | Phase 6 |
| CAL | CAL-05 | Phase 6 |
| CAL | CAL-06 | Phase 6 |
| CAL | CAL-07 | Phase 6 |
| CAL | CAL-08 | Phase 6 |
| CAL | CAL-09 | Phase 6 |
| CAL | CAL-10 | Phase 6 |
| SWEEP | SWEEP-01 | Phase 7 |
| SWEEP | SWEEP-02 | Phase 7 |
| SWEEP | SWEEP-03 | Phase 7 |
| SWEEP | SWEEP-04 | Phase 7 |
| SWEEP | SWEEP-05 | Phase 7 |
| SWEEP | SWEEP-06 | Phase 7 |
| SWEEP | SWEEP-07 | Phase 7 |
| SWEEP | SWEEP-08 | Phase 7 |
| SWEEP | SWEEP-09 | Phase 7 |
| SWEEP | SWEEP-10 | Phase 7 |
| SWEEP | SWEEP-11 | Phase 7 |
| SWEEP | SWEEP-12 | Phase 7 |
| SWEEP | SWEEP-13 | Phase 7 |
| SWEEP | SWEEP-14 | Phase 7 |
| UI | UI-01 | Phase 8 |
| UI | UI-02 | Phase 8 |
| UI | UI-03 | Phase 8 |
| UI | UI-04 | Phase 8 |
| UI | UI-05 | Phase 8 |
| UI | UI-06 | Phase 8 |
| UI | UI-07 | Phase 8 |

**Mapped: 41/41 — no orphans.**

---

## Coverage Check — v3.0 Requirements

All 20 requirements mapped to exactly one phase. No orphans.

| Category | Req | Phase |
|----------|-----|-------|
| TENANT | TENANT-01 | Phase 9 |
| TENANT | TENANT-02 | Phase 9 |
| TENANT | TENANT-03 | Phase 9 |
| TENANT | TENANT-04 | Phase 9 |
| TENANT | TENANT-05 | Phase 9 |
| TENANT | TENANT-06 | Phase 9 |
| TENANT | TENANT-07 | Phase 9 |
| TENANT | TENANT-08 | Phase 9 |
| TENANT | TENANT-09 | Phase 9 |
| TENANT | TENANT-10 | Phase 9 |
| DEF | DEF-01 | Phase 10 |
| DEF | DEF-02 | Phase 10 |
| DEF | DEF-03 | Phase 10 |
| DEF | DEF-04 | Phase 10 |
| DEF | DEF-05 | Phase 10 |
| DEF | DEF-06 | Phase 10 |
| DEF | DEF-07 | Phase 10 |
| DEF | DEF-08 | Phase 10 |
| DEF | DEF-09 | Phase 10 |
| DEF | DEF-10 | Phase 10 |

**Mapped: 20/20 — no orphans.**

---

## Open Risks for Execution

1. **Reddit app creation (manual gate before Phase 7):** `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USER_AGENT` must be created at reddit.com/prefs/apps and set in Railway before `reddit_ingest.py` can be tested. This is a one-time human action that blocks Phase 7 planning. Resolve before `/gsd:plan-phase 7`.

2. **Alembic head confirmation (before Phase 5):** `alembic heads` must confirm exactly one head at `0010_add_daily_summaries` before writing the `down_revision` for 0011. Any post-v2.0 quick-task migrations that landed after Phase 4 would shift this. Run `alembic heads` as the first action of `/gsd:plan-phase 5`.

3. **Phase 7 size:** With 14 requirements, Phase 7 is the heaviest execution session. If it runs long, a natural split point exists at SWEEP-11/SWEEP-12 (scheduler-done / frontend-starts). The plan for Phase 7 should call this out explicitly and offer the option to create Phase 7b as a separate execution if needed.

4. **shadcn Tabs Tailwind v4 branch compatibility:** Confirmed high-confidence but must be verified on the first `npx shadcn@latest add tabs` run in Phase 5. If the generated `tabs.tsx` uses v3 class syntax, the installation must be re-run against the confirmed v4 branch before any TabNav work proceeds.

5. **`r/gold` subscriber count:** Estimated 50K-80K (MEDIUM confidence). Does not affect the 4-subreddit recommendation but should be confirmed at reddit.com/r/gold before Phase 7 ships to ensure the sub is not quarantined or restricted.

6. **Phase 8 dead-code strip timing:** UI-06 (strip v1.0 files) is the final task of Phase 8, not the first. The dead-code strip happens only after Phases 5-7 are merged and a `grep` confirms no surviving callers.

7. **Three discuss-phase decisions BEFORE Phase 9 plan-phase (v3.0):** Phase 9 plan-phase MUST NOT begin until the operator resolves three architectural disagreements surfaced in research SUMMARY.md "Inter-Research Disagreements": (a) scheduler topology — single-cron-fanout (D-02 Option 1, zero new lock IDs) vs explicit per-company jobs (STACK, +2 IDs at 1020/1021) vs per-tenant 100-ID blocks (PITFALLS §3.4, Juno 1100-1199 with 1117/1118/1119 reserved); (b) AppHeader freeze treatment — Path A formal lift with re-baselined visual QA (ARCHITECTURE D-04, cleaner long-term) vs Path B sibling `CompanyBar.tsx` component (PITFALLS §5, lower-risk launch); (c) `companies` DB table vs hardcoded CHECK constraint — STACK proposes 0014 creates `companies` table with FK (referential integrity day-one) vs ARCHITECTURE D-05 keeps config in Python only (no DB table — operator has no runtime config UI in v3.0) vs PITFALLS accepts hardcoded `('seva', 'juno')` CHECK as v3.0 tech debt with upgrade by v3.2+. All three are operator decisions, not research gaps.

8. **Phase 9 single atomic deploy (v3.0):** The 0014 migration is irreversible in production semantics — partial multi-tenancy is worse than none. Phase 9 ships every TENANT-* requirement together: migration + scoped helpers + router restructure + frontend routing + AppHeader/CompanyBar switcher + TanStack key factory + per-company cron fan-out + isolation tests. Do NOT split TENANT-* across phases. Schedule migration outside 08:00/12:00 PT cron windows (recommend 04:00 PT, between 03:00 prune cron and 08:00 daily_summary cron).

9. **Phase 10 Phase-0 RSS verification gate:** Three deferred RSS endpoints (war.gov press-releases, nato.int news, canada.ca defence) MUST be `curl -sI` verified as the first task of Phase 10 plan-phase. STACK.md Defence Feed Inventory directly validated 12 Tier-1 feeds on 2026-05-19 but flagged these three for Phase-0 verification. SerpAPI fallback documented for any that return non-200.

10. **Phase 10 operator UAT bottleneck:** Voice calibration is operator-bottlenecked, not engineer-bottlenecked. Engineer iterates `DEFENCE_NEWS_SYSTEM_PROMPT` between cycles; operator gates production cron enablement via `voice_calibration_uat.md` sign-off. Schedule 1-3 UAT cycles (~30-60 min each) during Phase 10 execution. Production Juno cron remains DISABLED until UAT signed off.

---

## Suggested Next Action

Run `/gsd:discuss-phase 9` to resolve the three architectural decisions flagged in research SUMMARY.md (scheduler topology, AppHeader freeze treatment, companies DB table vs hardcoded CHECK) BEFORE generating the Phase 9 execution plan.

After discuss-phase resolves, run `/gsd:plan-phase 9` to generate the execution plan for Phase 9 — Multi-Tenant Foundation.

The plan for Phase 9 should sequence as follows:
1. `alembic heads` — confirm current head at `0013_calendar_title_nullable_unique_date` before writing 0014
2. Write `0014_add_company_id.py` with expand/contract DEFAULT 'seva' pattern; verify round-trip in dev
3. Build `backend/app/companies/` + `backend/app/queries/scoped.py` + `scheduler/companies/` packages with both `seva/` and `juno/` (juno is stub)
4. Refactor `backend/app/main.py` router prefixes + `backend/app/dependencies.py` + 3 router files to use `scoped_*()` helpers
5. Update 6 SQLAlchemy model files (dual-model parity) with `company_id` Column
6. Refactor `scheduler/agents/daily_summary.py` to per-company loop with juno path as no-op stub
7. Apply discuss-phase scheduler topology decision to `scheduler/worker.py` `JOB_LOCK_IDS`
8. Refactor `frontend/src/App.tsx` route tree to `<Route path=":company">` + bookmark grace redirects
9. Build `CompanyScopedRoute.tsx` + `CompanySwitcher.tsx` + apply discuss-phase Path A or B to AppHeader
10. Build `frontend/src/api/queryKeys.ts` factory + update API client modules + page components
11. Build `test_multitenant_isolation.py` covering every list/detail endpoint + every cron
12. Smoke test: deploy + verify `/seva/*` byte-equivalent + `/juno/*` empty-state + one cron fire produces both Seva (completed) and Juno (partial) rows

---

*v2.1 roadmap created: 2026-05-18*
*v3.0 roadmap extended: 2026-05-19*
*Requirements: 41 v2.1 + 20 v3.0 = 61 total, 100% mapped*
*Phases: 5-8 (v2.1) + 9-10 (v3.0), continuing project-wide counter from v2.0 Phases 1-4*
