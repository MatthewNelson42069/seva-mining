# Research Summary — v2.1 Three-Tab Content Engine + UI Polish

**Project:** Seva Mining — AI Social Media Agency
**Milestone:** v2.1 Three-Tab Content Engine + UI Polish
**Researched:** 2026-05-18
**Confidence:** HIGH (stack, architecture, virality compute, Sonnet prompt); MEDIUM (subreddit subscriber counts)

---

## Executive Summary

Seva Mining v2.1 adds two new tabs (Content Calendar + Weekly Viral Sweeper) and a Linear-style UI polish pass on top of the shipped v2.0 News Funnel. The only net-new dependencies are `asyncpraw>=7.8.1` (scheduler) and the shadcn Tabs primitive (frontend copy-paste) — everything else is covered by the existing stack. All architectural integration follows locked v2.0 patterns confirmed from direct codebase reads: scheduler factory, advisory lock dict, agent_runs lifecycle, idempotency guard, 60s Anthropic timeout, hand-written Alembic migrations, dual-model parity.

The Content Calendar is intentionally simple: a personal weekly planning grid with CRUD over a single `calendar_items` table — no AI drafting, no autoposting, no AI-generated content. The Weekly Viral Sweeper runs Sundays at 08:00 PT (advisory lock 1019), fetches top posts from 4 gold/silver subreddits via asyncpraw, computes story virality across the past 7 days of `daily_summaries.raw_sources_jsonb.gold_news[]` using URL canonicalization + distinct-source counting, and asks Sonnet for 3 content angles connecting Reddit signal with mainstream news. The UI polish is dark + amber-500 accents (Tailwind), preserving the existing Geist font; new tab strip uses React Router NavLink (not shadcn Tabs internal state) so deep-linking and Back/Forward work.

The critical implementation risk is the cluster of cross-cutting pitfalls flagged across all 4 research files: (1) `praw` sync blocks AsyncIOScheduler — must use `asyncpraw`; (2) `Column(Date)` not `DateTime` for `calendar_items.date` — TZ off-by-one is invisible locally but breaks on Railway UTC; (3) shadcn Tabs `value` must be wired to `useLocation()`, not local state, or tab highlight desyncs on browser nav; (4) advisory lock 1019 must enter `JOB_LOCK_IDS` dict BEFORE any other weekly_sweeper code lands so the OPS-02 assertion can catch collisions; (5) virality compute must guard against `raw_sources_jsonb=None` on failed daily_summary rows.

---

## Recommended Stack — Net-New Additions Only

| Package | Verdict | Where | Why |
|---------|---------|-------|-----|
| `asyncpraw >= 7.8.1` | **ADD** | `scheduler/pyproject.toml` | Reddit ingestion; async-native; same `praw-dev` org; uses aiohttp |
| `shadcn Tabs` | **ADD** (copy-paste) | frontend via `npx shadcn@latest add tabs` | Top tab navigation; already on Tailwind v4 branch |
| `@dnd-kit/core` | **SKIP** | — | Use date dropdown instead; DnD complexity not justified |
| Inter font swap | **SKIP** | — | Current Geist Variable stays; no design reason to change |
| Markdown editor lib | **SKIP** | — | Plain `<textarea>` + existing `react-markdown` render is sufficient |
| `difflib.SequenceMatcher` | **SKIP** | — | Python stdlib; already imported in content_agent.py |
| Any posting library | **SKIP** | — | Phase B stays dormant; no autoposting |

**3 new env vars** (Railway): `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USER_AGENT`. One-time setup at reddit.com/prefs/apps → "create app" → type "script" → free public read-only access.

Full detail: `.planning/research/STACK.md`

---

## Architecture Decisions (locked, from direct codebase reads)

### Database Layer

**Two new tables, two migrations, dual-model parity (backend + scheduler).**

**`calendar_items`** (Alembic 0011):
```sql
id           UUID PK DEFAULT gen_random_uuid()
date         DATE NOT NULL              -- NOT DateTime; TZ off-by-one risk
title        TEXT NOT NULL
notes_md     TEXT                       -- nullable markdown
tag          VARCHAR(20)                -- CHECK: thread|video|podcast|tweet|idea|other
created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
INDEX ix_calendar_items_date ON (date)
```
Note: `updated_at` is set explicitly by PATCH handler (no DB trigger).

**`weekly_sweeps`** (Alembic 0012):
```sql
id                UUID PK DEFAULT gen_random_uuid()
generated_at      TIMESTAMPTZ NOT NULL
week_start        DATE NOT NULL          -- Sunday of swept week
week_end          DATE NOT NULL          -- Saturday
reddit_top_md     TEXT
story_virality_md TEXT
content_angles_md TEXT
raw_sources_jsonb JSONB
status            VARCHAR(20) NOT NULL DEFAULT 'completed'  -- CHECK: completed|failed|partial
error_text        TEXT
agent_run_id      UUID FK agent_runs.id ON DELETE SET NULL
INDEX ix_weekly_sweeps_generated_at ON (generated_at DESC)
```

Week boundary: **Sun-Sat**. Cron fires Sunday 08:00 PT, summarizes the week just ending. `week_start = now_la.date()` (Sunday), `week_end = week_start + timedelta(days=6)`.

### Scheduler Integration

**Advisory lock:** Add `"weekly_sweeper": 1019` to `JOB_LOCK_IDS` in `worker.py` **as first task of Phase 3** — OPS-02 assertion catches dict collisions but cannot catch hardcoded IDs.

**Factory:** `_make_weekly_sweeper_job(engine)` — same shape as `_make_daily_summary_job`. Lazy-import `run_weekly_sweeper` inside the inner `async def job()`.

**Registration:**
```python
scheduler.add_job(
    _make_weekly_sweeper_job(engine),
    trigger=CronTrigger(day_of_week='sun', hour=8, minute=0,
                        timezone='America/Los_Angeles'),
    id="weekly_sweeper",
    name="Weekly Viral Sweeper — 08:00 Sunday America/Los_Angeles",
)
```

**Module split:** `scheduler/agents/reddit_ingest.py` (asyncpraw wrapper) + `scheduler/agents/weekly_sweeper.py` (orchestrator). Mirrors the `content_agent.py` ↔ `daily_summary.py` separation in v2.0.

**Idempotency:** 60-min window keyed on `week_start = this_sunday`.

**Sonnet timeout:** `AsyncAnthropic(api_key=..., timeout=60.0)` — same post-ii6 pattern as daily_summary.py.

### Backend Routes

Two new routers under existing auth gate:
- `GET /calendar?start=&end=` + `POST /calendar` + `PATCH /calendar/{id}` + `DELETE /calendar/{id}`
- `GET /weekly-sweeps?limit=12`

Pydantic schemas use `Literal[...]` for tag/status enums + `model_config = ConfigDict(from_attributes=True)`. PATCH handler MUST set `updated_at = datetime.utcnow()` explicitly (no DB trigger).

### Frontend Routes

**Restructure `App.tsx`** — wrap existing `SummaryFeedPage` (Tab 1) + new pages (Tab 2/3) under a new `<TabbedDashboard />` route:
```tsx
<Route element={<AppShell />}>
  <Route element={<TabbedDashboard />}>
    <Route index element={<SummaryFeedPage />} />
    <Route path="calendar" element={<ContentCalendarPage />} />
    <Route path="viral" element={<WeeklyViralSweeperPage />} />
  </Route>
  {/* /queue, /agents/:slug, /digest, /settings preserved */}
</Route>
```

`TabbedDashboard` renders `<TabNav />` then `<Outlet />` (analogous to `AppShell`). `AppShell` itself stays unchanged (12 lines). Tabs only appear inside the 3-tab surface — NOT on `/digest` or `/settings`.

**Tab nav implementation:** React Router `<NavLink>` styled to look like shadcn Tabs visually. Drive any shadcn Tabs `value` prop from `useLocation()` — never from local state.

Full detail: `.planning/research/ARCHITECTURE.md`

---

## Feature Priorities

### P1 — Table Stakes (must ship in v2.1)

| Feature | Complexity |
|---------|------------|
| Tab navigation (3 tabs) | S |
| Calendar CRUD (create/edit/delete) | M |
| Weekly Reddit ingestion (Sunday cron) | M |
| Story virality compute | M |
| Sonnet content-angle generation | M |
| Weekly sweep card UI | M |
| Linear-style UI pass | M |

### P2 — Differentiators (nice-to-have within v2.1 if time)

- Tag color-coding on calendar (S)
- Today highlight on calendar (S)
- Day hover "+ Add" hint (S)
- Reddit post score display (S)
- Weekly sweep history picker (M)

### P3 — Anti-Features (never ship)

- AI content drafting (v1.0 sub-agents stay retired)
- Autoposting to X/IG/anywhere (Phase B stays dormant)
- WhatsApp ping for sweeper (defer v2.2)
- Live FRED macro indicators (defer v2.2)
- Mobile-responsive UI (desktop-only constraint)
- DnD for calendar in v2.1 (defer v2.2 if user asks)
- Kitco scraping (defer v2.2)

Full detail: `.planning/research/FEATURES.md`

---

## Reddit Ingestion — Key Findings

**Recommended subreddits (4):** `gold`, `Wallstreetsilver`, `silverbugs`, `Gold_and_Silver`. Drop `Gold_Silver_Crypto` (too small) and `wallstreetbets` (signal-to-noise unacceptable at limit=10).

**API pattern:** `subreddit.top(time_filter='week', limit=10)`. Use `submission.score` (net upvotes) as the primary ranking signal. Ingest both text and link posts; skip comments in v2.1.

**Rate limits:** 100 QPM free tier; sweep makes ~5 calls/week. Zero risk.

**User agent:** `"SevaMiningSweeper/1.0 by sevabot"` (or username chosen at Reddit app creation).

---

## Story Virality Compute — Key Findings

**Source:** `daily_summaries.raw_sources_jsonb.gold_news[]` for past 7 days; ~14 rows (2/day × 7 days). Each story has `{title, link, source_name, score, published_at}`.

**Dedup strategy:** URL canonicalization, **NOT** SequenceMatcher on URLs (would conflate `kitco.com/2026/01/a.html` and `kitco.com/2026/02/a.html`). Strip UTM params, lowercase hostname, remove trailing slash, sort query. After canonicalization, group by canonical URL.

**Virality score:** Count of distinct `source_name` covering the story (NOT raw occurrence count). A story covered by Bloomberg + Northern Miner + GoldSwitzerland = virality_score=3. A story appearing in fxstreet 14 times = virality_score=1.

**Output:** Top 5 by `virality_score DESC`, with `(canonical_title, canonical_url, source_count, latest_seen_at)`.

**Defensive guard:** `(row.raw_sources_jsonb or {}).get("gold_news", [])` — failed daily_summary rows may have `raw_sources_jsonb=None`.

---

## Sonnet Content-Angle Prompt — Key Findings

**Model:** `claude-sonnet-4-6` (consistent with daily_summary.py `SONNET_MODEL`).
**Max tokens:** 1000 (3 angles × ~300 each).
**Timeout:** 60.0s (matches post-ii6 pattern).

**System prompt structure:** "Tactical content strategist for a gold-sector social media account." Each of 3 angles must connect a Reddit signal with a mainstream news signal and identify the narrative tension between them. Never mention Seva Mining. No financial advice.

Output format per angle: `**Angle N: [title]**` followed by `Reddit signal / Mainstream signal / Your angle` lines. The gap/tension framing is the key differentiator vs. a generic "summarize this week's gold news" prompt.

Full prompt + Python builder: `.planning/research/FEATURES.md` (Sonnet section).

---

## TOP 10 Pitfalls (severity-sorted, must-prevent)

1. **CRITICAL — `praw` (sync) blocks AsyncIOScheduler.** Use `asyncpraw>=7.8.1`, not `praw` + `asyncio.to_thread`. PRAW docs explicitly say "use Async PRAW if asynchronous."

2. **CRITICAL — `Column(DateTime)` on `calendar_items.date` causes UTC off-by-one.** Must use `Column(Date)` + Pydantic `datetime.date` field + `"YYYY-MM-DD"` string from frontend. Bug invisible in PT dev, breaks on Railway UTC. Add `TZ=UTC pytest` test.

3. **CRITICAL — shadcn Tabs `value` driven by local state desyncs from URL.** Wire to `useLocation()` so Back/Forward updates tab highlight.

4. **CRITICAL — Alembic `down_revision` mismatch breaks Railway deploy.** Run `alembic heads` before writing 0011/0012 to confirm parent revision.

5. **CRITICAL — Lock ID 1019 hardcoded outside `JOB_LOCK_IDS` evades OPS-02 assertion.** Add `"weekly_sweeper": 1019` to dict as **first task** of Phase 3.

6. **HIGH — `raw_sources_jsonb=None` on failed daily_summary rows.** Guard: `(row.raw_sources_jsonb or {}).get("gold_news", [])`.

7. **HIGH — TanStack Query mutations without rollback on error.** Use `onMutate` snapshot + `onError` restore pattern per TanStack v5 docs.

8. **HIGH — Reddit per-subreddit failure cascades.** Wrap each `subreddit.top()` in try/except; partial results > all-or-nothing. Use `requestor_kwargs={"timeout": 15}` on client construction.

9. **HIGH — `updated_at` silently not set on PATCH.** Router handler sets it explicitly; never put it in Pydantic `CalendarItemUpdate` schema.

10. **MEDIUM — Sonnet hallucination on weeks with sparse Reddit signal.** Inject grounding: if `reddit_posts < 3 OR viral_stories < 3`, write "insufficient signal this week" instead of calling Sonnet.

Full 32-pitfall inventory across 8 categories: `.planning/research/PITFALLS.md`

---

## Recommended Phase Build Order (4 phases)

### Phase 1 — Foundation (DB + API scaffolding + frontend shell)

**Why first:** DB migrations must precede any feature work. Route restructure must precede both calendar and sweeper UI. The stub pages confirm routing works before adding business logic.

- Alembic 0011_add_calendar_items + 0012_add_weekly_sweeps
- Dual-model parity (4 model files: scheduler + backend × 2 tables)
- Add `"weekly_sweeper": 1019` to `JOB_LOCK_IDS`
- Backend Pydantic schemas + router stubs (GET returns empty list, POST returns 501)
- `main.py` includes both routers
- `App.tsx` route restructure + `TabbedDashboard` + `TabNav` components
- Stub `ContentCalendarPage` + `WeeklyViralSweeperPage` ("Coming soon")
- Install shadcn Tabs primitive

### Phase 2 — Content Calendar (self-contained CRUD)

**Why second:** Pure CRUD; no scheduler changes, no Sonnet, no new env vars. Highest confidence of the two features. Ships value immediately.

- Full calendar router (GET/POST/PATCH/DELETE) + complete Pydantic schemas
- `WeeklyGrid.tsx` + `CalendarItemDialog.tsx` + `CalendarItem.tsx` components
- Tag color-coding (Tailwind utility map)
- Today highlight + hover "+ Add" hint
- Date dropdown reschedule (NOT drag-and-drop)
- `calendar.ts` API client + TanStack Query hooks with optimistic mutations + rollback
- `ContentCalendarPage.tsx` with live data

### Phase 3 — Weekly Viral Sweeper (scheduler + Reddit + Sonnet)

**Why third:** External dependency (Reddit API setup), scheduler changes, most complex logic (virality + Sonnet). Sequencing after Calendar means full backend is live before tackling the hardest feature.

- `asyncpraw>=7.8.1` to `scheduler/pyproject.toml`
- 3 env vars to Railway (REDDIT_CLIENT_ID / SECRET / USER_AGENT)
- `reddit_ingest.py` module (asyncpraw wrapper, per-subreddit try/except)
- `weekly_sweeper.py` orchestrator (idempotency → agent_runs → Reddit fetch → virality compute → Sonnet call → status mapping → weekly_sweeps INSERT → telemetry)
- `_make_weekly_sweeper_job(engine)` factory + `build_scheduler()` registration
- `weeklySweeps.ts` API client + hook
- `WeeklyViralSweeperPage.tsx` + `SweeperCard.tsx`

### Phase 4 — UI Polish + Cleanup

**Why last:** UI polish is iterative; can't be "done" until all surfaces exist. Dead-code strip requires confidence that nothing references deleted files.

- Linear-style dark + amber-500 accent pass across all 3 tabs
- shadcn component audit (replace any ad-hoc form elements)
- Strip v1.0 dead-code content sub-agent source files
- Visual QA pass

**Parallelism:** Phases 2 and 3 are logically independent and can run in parallel if bandwidth allows. Phase 4 strictly serial after both ship.

Full file change map (NEW / MODIFIED / UNCHANGED): `.planning/research/ARCHITECTURE.md`

---

## Open Questions / Risks for REQUIREMENTS authoring

1. **r/gold subscriber count uncertainty (MEDIUM):** Confirm at reddit.com/r/gold before Phase 3; estimate 50K-80K, but margin doesn't change the 4-subreddit recommendation.

2. **`REDDIT_USER_AGENT` exact string:** User decides at Reddit app creation. Default: `"SevaMiningSweeper/1.0 by sevabot"`.

3. **Combined vs split migration:** Two separate migrations (0011, 0012) is the safer pattern per ARCHITECTURE.md. Combined `0011_add_calendar_and_sweeps.py` only justified if same-deploy is guaranteed.

4. **Phase 2 vs 3 ordering:** Recommendation is Calendar before Sweeper. User can override if Sweeper has stronger pull.

5. **shadcn Tabs install timing:** `npx shadcn@latest add tabs` should run in Phase 1; confirm Tailwind v4 branch compat (it's the known-good branch per CLAUDE.md).

6. **DnD deferral:** Locked decision per FEATURES.md — date dropdown in v2.1, DnD as quick task in v2.2 if user wants it after using v2.1.

7. **Sweeper WhatsApp ping:** Out of scope per FEATURES.md. User adds in v2.2 if they want Sunday alerting after seeing the web feed in action.

---

## Source Files Cross-Reference

| Section | Primary source | Detail level |
|---------|----------------|--------------|
| Stack additions | STACK.md | Full PyPI/npm version verdicts + version compat matrix |
| DB schemas + scheduler + frontend routes | ARCHITECTURE.md | Full SQL DDL + Python signatures + tsx route trees |
| Reddit API patterns + subreddit viability + Sonnet prompt | FEATURES.md | Full prompt builders + asyncpraw call patterns |
| 32 pitfalls × 8 categories | PITFALLS.md | Prevention code + phase assignment per pitfall |

**Ready for REQUIREMENTS.md authoring.**
