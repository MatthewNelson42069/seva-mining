# Roadmap: Seva Mining

## Milestones

- ✅ **v1.0.1 — Approval Dashboard (deprecated by v2.0 pivot)** — Phases 1-11, shipped 2026-04-25 → archive: [`milestones/v1.0.1/ROADMAP.md`](milestones/v1.0.1/ROADMAP.md)
- ✅ **v2.0 — Daily Summary Feed** — Phases 1-4 (reset numbering), shipped 2026-05-06 → archive: [`milestones/v2.0-ROADMAP.md`](milestones/v2.0-ROADMAP.md)
- 🚧 **v2.1 — Three-Tab Content Engine + UI Polish** — Phases 5-8 (project-wide counter continues), initiated 2026-05-18

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

- [ ] **Phase 5: Foundation — Tabs + DB + Backend Stubs** — DB migrations, dual-model parity, backend router stubs, frontend tab shell with route restructure
- [ ] **Phase 6: Content Calendar** — Full CRUD over `calendar_items`: backend routes, Pydantic schemas, weekly grid UI, optimistic mutations
- [ ] **Phase 7: Weekly Viral Sweeper** — Scheduler + Reddit ingestion + virality compute + Sonnet call + sweep card UI
- [ ] **Phase 8: UI Polish + Dead-Code Strip** — Linear dark/amber-500 pass across all 3 tabs, WCAG audit, v1.0 dead-code removal

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

**Plans:** 5 plans
- [x] 06-01-PLAN.md — Requirements rephrase + Migration 0013 (title nullable + UNIQUE(date)) + Pydantic schemas (Wave 1)
- [x] 06-02-PLAN.md — Full CRUD router replace + pytest coverage including P1/P4 defenses (Wave 2, depends on 06-01)
- [x] 06-03-PLAN.md — Frontend API module + useCalendar hook + 3 optimistic mutation hooks with rollback (Wave 2, depends on 06-01)
- [ ] 06-04-PLAN.md — ISO week helpers + DayCell (textarea + auto-save 4-way branch) + WeeklyGrid (Wave 3, depends on 06-02 + 06-03)
- [ ] 06-05-PLAN.md — WeekNav + live ContentCalendarPage + human-verify checkpoint (Wave 4, depends on 06-04)

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

**Goal:** Every Sunday at 08:00 PT a cron job ingests the top Reddit posts from 4 gold/silver subreddits, computes story virality across the past 7 days of `daily_summaries`, calls Sonnet for 3 content angles, persists a `weekly_sweeps` row, and the frontend's Tab 3 renders the latest sweep card with all three sections plus an empty state for the first deploy.

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

**Plans:** TBD

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

**Plans:** TBD

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

## Progress

| Phase | Milestone | Plans | Status | Completed |
|-------|-----------|-------|--------|-----------|
| 1. Gold News Card + Web Feed | v2.0 | 6/6 | Complete | 2026-05-06 |
| 2. Ontario Law Ingestion | v2.0 | 1/1 | Complete | 2026-05-06 |
| 3. Ontario Stats Ingestion | v2.0 | 1/1 | Complete | 2026-05-06 |
| 4. Prune Cron + Ops Hardening | v2.0 | 1/1 | Complete | 2026-05-06 |
| 5. Foundation — Tabs + DB + Backend Stubs | v2.1 | 0/5 | Planned | - |
| 6. Content Calendar | v2.1 | 0/? | Not started | - |
| 7. Weekly Viral Sweeper | v2.1 | 0/? | Not started | - |
| 8. UI Polish + Dead-Code Strip | v2.1 | 0/? | Not started | - |

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

## Open Risks for Execution

1. **Reddit app creation (manual gate before Phase 7):** `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USER_AGENT` must be created at reddit.com/prefs/apps and set in Railway before `reddit_ingest.py` can be tested. This is a one-time human action that blocks Phase 7 planning. Resolve before `/gsd:plan-phase 7`.

2. **Alembic head confirmation (before Phase 5):** `alembic heads` must confirm exactly one head at `0010_add_daily_summaries` before writing the `down_revision` for 0011. Any post-v2.0 quick-task migrations that landed after Phase 4 would shift this. Run `alembic heads` as the first action of `/gsd:plan-phase 5`.

3. **Phase 7 size:** With 14 requirements, Phase 7 is the heaviest execution session. If it runs long, a natural split point exists at SWEEP-11/SWEEP-12 (scheduler-done / frontend-starts). The plan for Phase 7 should call this out explicitly and offer the option to create Phase 7b as a separate execution if needed.

4. **shadcn Tabs Tailwind v4 branch compatibility:** Confirmed high-confidence but must be verified on the first `npx shadcn@latest add tabs` run in Phase 5. If the generated `tabs.tsx` uses v3 class syntax, the installation must be re-run against the confirmed v4 branch before any TabNav work proceeds.

5. **`r/gold` subscriber count:** Estimated 50K-80K (MEDIUM confidence). Does not affect the 4-subreddit recommendation but should be confirmed at reddit.com/r/gold before Phase 7 ships to ensure the sub is not quarantined or restricted.

6. **Phase 8 dead-code strip timing:** UI-06 (strip v1.0 files) is the final task of Phase 8, not the first. The dead-code strip happens only after Phases 5-7 are merged and a `grep` confirms no surviving callers.

---

## Suggested Next Action

Run `/gsd:plan-phase 5` to generate the execution plan for Phase 5 — Foundation.

The plan for Phase 5 should sequence as follows:
1. `alembic heads` — confirm current head before writing migrations
2. Add `"weekly_sweeper": 1019` to `JOB_LOCK_IDS` in `worker.py` (before any sweeper module code)
3. Write and validate migrations 0011 + 0012 (hand-written; verify `down_revision` chain)
4. Create 4 SQLAlchemy model files with parity tests
5. Create backend router stubs + schemas + `main.py` registration
6. `npx shadcn@latest add tabs` (confirm Tailwind v4 branch)
7. Create `TabbedDashboard.tsx` + `TabNav.tsx` (URL-driven, not local state)
8. Restructure `App.tsx` routes (lock URL contract: `/`, `/calendar`, `/viral`)
9. Create stub `ContentCalendarPage.tsx` + `WeeklyViralSweeperPage.tsx` with `React.lazy()` boundaries
10. Smoke-test: visit all 3 tabs, test back/forward, confirm v2.0 routes still redirect correctly

---

*v2.1 roadmap created: 2026-05-18*
*Requirements: 41 v2.1 requirements, 100% mapped*
*Phases: 5-8 (continuing project-wide counter from v2.0 Phases 1-4)*
