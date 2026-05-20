# Phase 7: Weekly Viral Sweeper - Context

**Gathered:** 2026-05-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Every Sunday at 08:00 PT, a cron job ingests the top X posts from the past week (combined keyword + cashtag + hashtag query for gold-sector chatter), computes story virality across the past 7 days of `daily_summaries.raw_sources_jsonb.gold_news[]`, calls Sonnet for 3 content angles connecting the X signals with the cross-referenced news signals, persists a `weekly_sweeps` row, and the frontend's `/viral` tab renders the latest sweep card as a single scrolling card with three stacked sections plus an empty state when no sweep has run yet.

**Major pivot from spec:** REPLACE Reddit ingestion with X API recent search. Reddit is dropped entirely; the existing X API Basic tier subscription (already paid, already wired for the Content Agent's `video_clip` pipeline) becomes the social-signal source. This collapses Phase 7's external-dependency surface by ~1 vendor and ~3 env vars.

</domain>

<decisions>
## Implementation Decisions

### Scope
- **D-01:** **Full sweeper as specced**, including the Sonnet 3-content-angle generation. The AI here serves the operator (reads + summarizes external signals), unlike Phase 6 where it was explicitly dropped because the operator does the writing themselves.
- **D-02:** Single phase, not split. Despite 14 SWEEP-* requirements and 15 cataloged pitfalls, the scheduler + frontend land together so the manual-trigger escape hatch (`python -m agents.weekly_sweeper`) gives end-to-end verification before Sunday.

### Signal Source (PIVOT from spec)
- **D-03:** **X API recent search**, NOT Reddit. The X API Basic tier ($100/mo) is already active for the Content Agent's `video_clip` pipeline (`scheduler/agents/content/gold_media.py` uses `tweepy.asynchronous.AsyncClient.search_recent_tweets`). Reusing it avoids:
  - Standing up a Reddit script app at reddit.com/prefs/apps
  - 3 new env vars (`REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` / `REDDIT_USER_AGENT`)
  - A new package dependency (`asyncpraw>=7.8.1`) and the SQLAlchemy-style async client config
  - Reddit-specific pitfalls P1 (praw sync blocks event loop), P5 (asyncpraw timeout missing), P11 (REDDIT_CLIENT_SECRET logging)
- **D-04:** All SWEEP-* requirements referencing Reddit (SWEEP-01, SWEEP-02, SWEEP-04, SWEEP-05) need rephrasing. The planner will produce a small Wave 1 task that updates REQUIREMENTS.md alongside the asyncpraw → tweepy swap.

### X API Search Strategy
- **D-05:** **Combined query** — `("gold price" OR "gold market" OR "gold mining" OR "central bank gold" OR $GOLD OR $GLD OR $GDX OR $NEM OR $AEM OR #gold OR #goldprice OR #goldmining) -is:retweet -is:reply lang:en`. Captures keywords (analyst/journalist tweets) + cashtags (finance-engaged traders) + hashtags (retail chatter) in a single recent-search call.
- **D-06:** **Sort: relevancy, then post-fetch re-rank by engagement.** Use X's recommended `sort_order="relevancy"` on `search_recent_tweets` to let the API surface most-relevant tweets, then re-rank in Python by combined engagement score `likes + retweets*2 + replies*1.5` (mirrors the retired Twitter Agent's scoring formula in spirit, lower weights since we're sweeping not gating). No hard engagement floor — risk of empty weeks is too high on a weekly cadence.
- **D-07:** **Fetch 100, display top 10.** `max_results=100` (the API maximum for recent search) gives substrate for the engagement re-rank; display top 10 in the sweep card.
- **D-08:** **Monthly quota awareness.** The Content Agent's `video_clip` pipeline already tracks `twitter_monthly_tweet_count` / `twitter_monthly_quota_limit` config keys (default cap 10K/month). The weekly sweeper consumes ~400 tweets/month (~4% of budget) — coordinate by reading the same counter at start and aborting if within the 500-tweet safety margin (same pattern as `_search_gold_media_clips` in `gold_media.py`). On abort, write `status='partial'` with a "quota near cap" note in `agent_runs.errors`.

### Virality Compute (unchanged from spec)
- **D-09:** Compute story virality by querying `daily_summaries` for `generated_at >= now() - INTERVAL '7 days' AND status IN ('completed','partial')`, flattening `raw_sources_jsonb.gold_news[]`, canonicalizing each `link` (strip UTM/fbclid/gclid/ref params, lowercase host, sort query, no trailing slash), grouping by canonical URL, ranking by **distinct source_name count DESC**, top 5.
- **D-10:** Guard against `raw_sources_jsonb=None` on failed rows (P3): `(row.raw_sources_jsonb or {}).get("gold_news", [])`.

### Sonnet Content-Angle Generation (unchanged from spec)
- **D-11:** Model `claude-sonnet-4-6`, `AsyncAnthropic(api_key=..., timeout=60.0)`, max_tokens=1000. System prompt enforces:
  - 3 content angles, each connecting an X signal with a mainstream news signal
  - Gold bull thesis bias: "reframe bearish signals through the bull lens or discard them"
  - Grounding rule: "use ONLY facts present in supplied inputs" — defends against P14 (hallucinated facts)
  - Operator voice: senior analyst, data-driven, Bloomberg commodities-desk energy
- **D-12:** Truncate each X post body to 500 chars before injecting into user prompt (P7 — token budget defense, mirrors `content_agent.py [:500]`).
- **D-13:** **Insufficient signal fallback** — if `len(x_posts) < 3 OR len(viral_stories) < 3`, skip the Sonnet call and write "Insufficient signal this week — angles not generated" into `content_angles_md`. Defends against P15 (hallucination on sparse weeks).

### Scheduler (unchanged from spec)
- **D-14:** Cron registration via `_make_weekly_sweeper_job(engine)` factory in `scheduler/worker.py` `build_scheduler()`, mirroring `_make_daily_summary_job`. `CronTrigger(day_of_week='sun', hour=8, minute=0, timezone='America/Los_Angeles')`, `id="weekly_sweeper"`, `max_instances=1`, `misfire_grace_time=1800`.
- **D-15:** Idempotency guard — check for existing `weekly_sweeps` row with `week_start = sunday_of_this_week` AND `status IN ('running','completed')` within a 60-min window; on hit log `idempotency_skip` and exit cleanly.
- **D-16:** Status mapping (SWEEP-11) — `completed` when X + virality + Sonnet all succeed; `partial` when at least one fails but a row can still render; `failed` only when X ingestion crashes before any output. Per-section errors into `agent_runs.errors` list (post-jny pattern).
- **D-17:** **Manual escape hatch** — `python -m agents.weekly_sweeper` runs the sweeper directly from a Railway shell. Documented as a comment in the sweeper module's docstring (P13 — first Railway deploy after 08:30 PT on a Sunday would otherwise miss the entire week).

### Backend Read Route (unchanged from spec)
- **D-18:** `GET /weekly-sweeps?limit=12` returns `{sweeps: WeeklySweepCard[], total: int}` ordered by `generated_at DESC`; `limit` clamped `ge=1, le=52`. Auth-gated at router level (`dependencies=[Depends(get_current_user)]`) — Phase 5 already wired the stub router into `main.py`.

### Frontend
- **D-19:** **Stacked sections** for the sweep card — one scrolling card with three sections rendered via react-markdown in order: (1) "Top X Posts This Week", (2) "Most Cross-Referenced Stories", (3) "3 Content Angles". All visible at once, matches how `SummaryFeedPage` already renders daily summaries.
- **D-20:** History week-picker (dropdown) for browsing prior weeks. Default view is the latest sweep.
- **D-21:** **Empty state** when `total: 0` — "Sweeper has not run yet — first fire scheduled for Sunday {next_sunday} 08:00 PT." (compute `next_sunday` client-side via `date-fns`).
- **D-22:** **Status-specific banner copy** for non-`completed` cards:
  - `failed`: "Sweeper failed last run — see telemetry"
  - `partial`: "Sweeper had partial output — some sections may be empty"

### Claude's Discretion
- **Quota counter coordination mechanism:** Reading + writing the same `twitter_monthly_tweet_count` config key is the simplest path. Planner picks the exact transaction shape (SELECT FOR UPDATE vs naive read-then-write — given single-process scheduler + 1 weekly fire, naive read-then-write is fine).
- **X API rate-limit handling:** `tweepy.AsyncClient(wait_on_rate_limit=True)` already handles back-pressure (existing pattern in `gold_media.py`). Planner uses this default.
- **Sweep-card width / typography:** Reuse the same `max-w-[720px]` content width and Geist Variable typography from the daily summary feed. No bespoke design.
- **History-week-picker UX:** Dropdown with date labels like "May 11 – May 17, 2026 (completed)" / "May 4 – May 10, 2026 (partial)". Planner picks exact format.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Domain & Architecture
- `.planning/research/ARCHITECTURE.md` — "Scheduler Layer" (factory pattern, `JOB_LOCK_IDS` dict, `build_scheduler()` registration), "Backend / API Layer" (weekly_sweeps router shape — Phase 5 already wired stub), "New Frontend Files" (weeklySweeps.ts, SweeperCard.tsx, WeeklyViralSweeperPage.tsx). **NOTE:** ARCHITECTURE.md still references `asyncpraw` + Reddit; planner should ignore those sections and substitute the X-API pattern from `scheduler/agents/content/gold_media.py`.
- `.planning/research/FEATURES.md` §"REDDIT INGESTION" — IGNORE this section entirely (pivot to X API). Keep §"STORY VIRALITY COMPUTE" (unchanged) and §"SONNET CONTENT-ANGLE GENERATION" (unchanged — just rename "Reddit" → "X" in the prompt template). Keep §"SUNDAY CRON DESIGN".
- `.planning/research/PITFALLS.md` — P3 (NULL `raw_sources_jsonb`), P6 (Sonnet timeout), P7 (token budget — 500-char truncation), P8 (gold bull bias), P10 (URL canonicalization), P12 (`reconcile_stale_runs` 30-min threshold), P13 (Railway first-deploy miss), P14 (Sonnet hallucination), P15 (insufficient signal). **P1 (asyncpraw vs praw), P4 (subreddit 403), P5 (asyncpraw timeout), P11 (REDDIT_CLIENT_SECRET logging) are MOOT under the X-API pivot.**

### Reference Implementations (mirror these patterns)
- `scheduler/agents/content/gold_media.py` — **canonical X API consumer** in the existing codebase. Uses `tweepy.asynchronous.AsyncClient(bearer_token=settings.x_api_bearer_token, wait_on_rate_limit=True)` + `search_recent_tweets(query=..., max_results=10, tweet_fields=[...], expansions=[...], user_fields=[...])`. **Mirror its auth + quota-gate + result-processing shape.** Quota gate at top: read `twitter_monthly_tweet_count` and `twitter_monthly_quota_limit` from `bot_config`; abort if within 500 of cap.
- `scheduler/agents/daily_summary.py` — **canonical orchestration shape** for `weekly_sweeper.py`: idempotency check → `agent_runs` INSERT → external fetches → Sonnet → status mapping → row INSERT → telemetry in `finally`. Mirror exactly.
- `scheduler/agents/content_agent.py` — `deduplicate_stories()` helper (use within `_compute_virality`) + Anthropic call pattern with `timeout=60.0` + `[:500]` truncation pattern.
- `scheduler/worker.py` — `_make_daily_summary_job(engine)` factory pattern (mirror this for `_make_weekly_sweeper_job`); `build_scheduler()` registration block ordering (add weekly_sweeper after `daily_summary_prune`); `JOB_LOCK_IDS` dict already has `"weekly_sweeper": 1019` from Phase 5.
- `backend/app/routers/weekly_sweeps.py` — existing Phase 5 stub returning `{sweeps:[], total:0}`. Phase 7 fleshes this out with the real query.
- `frontend/src/pages/SummaryFeedPage.tsx` — react-markdown rendering reference for the sweep card's three sections.

### Phase Inputs (already in place from Phase 5)
- `backend/alembic/versions/0012_add_weekly_sweeps.py` — `weekly_sweeps` table DDL (live in Neon dev DB at head)
- `backend/app/models/weekly_sweep.py` + `scheduler/models/weekly_sweep.py` — dual-model SQLAlchemy parity
- `scheduler/worker.py` JOB_LOCK_IDS already contains `"weekly_sweeper": 1019` (Phase 5, plan 05-01)
- `frontend/src/pages/WeeklyViralSweeperPage.tsx` — current "Coming soon" stub (gets replaced)
- `frontend/src/App.tsx` — `/viral` route already nested under `TabbedDashboard` (Phase 5)
- X API env vars (`x_api_bearer_token` and friends) already in `scheduler/config.py` + `backend/app/config.py`; no new env work needed

### Requirements Rescoping (planner must update REQUIREMENTS.md)
The 14 SWEEP-* requirements were written assuming Reddit. Several need surgical edits:
- **DROP:** SWEEP-01 (asyncpraw dependency — not needed; tweepy already in stack), SWEEP-02 (Reddit env vars — not needed; X API env vars already set)
- **KEEP unchanged:** SWEEP-03 (lock 1019 — already done in Phase 5), SWEEP-06 (orchestration shape), SWEEP-07 (virality compute), SWEEP-09 (cron registration), SWEEP-10 (idempotency), SWEEP-11 (status mapping), SWEEP-12 (read route), SWEEP-14 (empty + status banner copy)
- **REPLACE:** SWEEP-04 (`reddit_ingest.py` → `x_ingest.py` with `fetch_top_x_posts(query, max_results) -> list[dict]` using `tweepy.asynchronous.AsyncClient.search_recent_tweets`), SWEEP-05 (4 subreddits → single combined X search query, `max_results=100`, post-fetch top-10 by engagement re-rank)
- **REPHRASE:** SWEEP-08 ("Reddit posts" → "X posts" in the Sonnet prompt template, insufficient-signal fallback condition `len(x_posts) < 3 OR len(viral_stories) < 3` unchanged), SWEEP-13 ("Top Reddit Posts This Week" section → "Top X Posts This Week")

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `tweepy.asynchronous.AsyncClient` — already imported and used in `scheduler/agents/content/gold_media.py`. Same pattern, different query.
- `x_api_bearer_token` config value — already in `scheduler/config.py:13`. Read via `get_settings().x_api_bearer_token`.
- `twitter_monthly_tweet_count` + `twitter_monthly_quota_limit` config keys — already coordinated by `gold_media.py`. Phase 7 reuses both.
- `AsyncAnthropic` pattern with `timeout=60.0` — `scheduler/agents/daily_summary.py` is the canonical reference; mirror exactly.
- `deduplicate_stories()` in `content_agent.py` — usable for per-row pre-dedup in virality compute (P9).
- `agent_runs` model + telemetry pattern — every existing scheduler agent writes status='running' → status='completed/partial/failed' transition; mirror.
- `react-markdown ^10.1.0` (in `package.json`) — already used by SummaryFeedPage for `gold_news_md`, `ontario_law_md`, etc. Reuse for the 3 sweep-card sections.

### Established Patterns
- All scheduler agents follow the same orchestration shape: `_validate_env()` → `idempotency_check()` → `agent_runs` INSERT → external work → status mapping → output INSERT → `finally` telemetry. Mirror exactly.
- Factory functions for APScheduler jobs use `_make_{job_name}_job(engine)` returning an inner `async def job()` that does lazy imports inside. Mirror.
- `JOB_LOCK_IDS` dict + the OPS-02 uniqueness assertion at `scheduler/worker.py:118` are the contract every new lock must respect.
- Backend routers follow `APIRouter(prefix=..., tags=..., dependencies=[Depends(get_current_user)])`. Phase 5 already wrote the stub with this shape.
- Pydantic v2 schemas live in `backend/app/schemas/`; `weekly_sweep.py` is a new file the planner creates.
- Frontend pages live in `frontend/src/pages/`; API modules in `frontend/src/api/`; component modules in `frontend/src/components/{feature}/`.

### Integration Points
- `backend/app/main.py` already includes `weekly_sweeps.router` (Phase 5 wiring) — no main.py changes needed.
- `frontend/src/App.tsx` already routes `/viral` to `WeeklyViralSweeperPage` under `TabbedDashboard` (Phase 5) — no App.tsx changes needed.
- `scheduler/worker.py` needs ONE addition: the `_make_weekly_sweeper_job(engine)` factory + a `scheduler.add_job(...)` block in `build_scheduler()`. The lock ID is already in the dict.

</code_context>

<specifics>
## Specific Ideas

User's pivot in their own words: "We dont need the reddit API, just go based off the X API."

This signals: we've already paid for X API Basic ($100/mo), it's already wired and producing value for the Content Agent's video_clip pipeline, and standing up Reddit on top of that adds vendor surface for no clear marginal benefit. The decision is pragmatic / budget-driven, not a quality preference — X and Reddit both surface gold-sector chatter; X has the additional virtue of being where finance Twitter actually lives ($GOLD cashtag traffic is meaningful).

</specifics>

<deferred>
## Deferred Ideas

Items that came up in spec but won't be built in Phase 7 (kept here so they aren't lost):

- **SWEEP-REDDIT-v22:** Reddit ingestion as a complementary signal source alongside X. Could revisit in v2.2 if the X-only signal proves too narrow or too finance-leaning. Implementation cost is non-trivial (Reddit script app, asyncpraw, 3 env vars, 4 subreddit list curation, additional P1/P4/P5/P11 pitfalls). Revisit only on operator request.
- **SWEEP-X-USERLIST-v22:** Limit the X search to a watchlist of credible gold analysts (e.g. @PeterSchiff, @LawrieWilliams, @LukeGromen, etc.) — same pattern as the retired Twitter Agent's `watchlists` table (now empty, kept as dead schema). Adds signal-to-noise but reintroduces the curation burden the operator just dropped. Revisit only if the keyword-based sweep produces too much noise.
- **SWEEP-CASHTAG-PRIMARY-v22:** Drop keywords + hashtags, query only `$GOLD OR $GLD OR $GDX OR $NEM OR $AEM`. Highest signal-to-noise for finance audience, but misses macro/policy chatter. Easy revisit — single-line query change.
- **SWEEP-DnD-PRIORITY-v22:** Manual override of "Top 10" ranking via drag-to-pin in the UI. Out of scope for v2.1.
- **SWEEP-WHATSAPP-v22:** Sunday morning WhatsApp ping with sweep card preview. Already deferred to v2.2 per ROADMAP; stays deferred.
- **SWEEP-HISTORY-COMPARE-v22:** Side-by-side compare of two weeks' content angles. Out of scope.

</deferred>

---

*Phase: 07-weekly-viral-sweeper*
*Context gathered: 2026-05-19*
