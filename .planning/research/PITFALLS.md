# Pitfalls Research — v3.0 Multi-Tenant Pivot + Defence-Sector Ingestion

**Domain:** Adding multi-tenancy (Seva + Juno) + defence-sector RSS ingestion + world-events-relevant-to-defence Sonnet filter to an already-shipped single-tenant FastAPI + SQLAlchemy 2.0 async + Postgres + APScheduler + React 19 stack
**Researched:** 2026-05-19
**Confidence:** HIGH (most pitfalls grounded in the v2.1 codebase audit + verified against PostgreSQL RLS CVEs, asyncpraw/asyncpg connection-pool semantics, Anthropic content-policy precedent, and Janes/Defense News feed reorganization history)

> **Scope discipline:** This file ONLY covers pitfalls SPECIFIC to the v3.0 migration. Generic engineering pitfalls (sync libs in async, timeouts, secret logging, JSONB None guards, etc.) are already documented in `.planning/milestones/v2.1-research/PITFALLS.md` and are NOT repeated here. Where a v3.0 pitfall extends a v2.1 baseline pitfall, the inheritance is noted explicitly.

---

## 1. Multi-Tenancy Data Isolation

### CRITICAL — Async session ContextVar leak across requests in connection pool

**What goes wrong:**
The natural pattern for tenant scoping in FastAPI is to set the active tenant via `ContextVar[str]` in middleware and have all repository queries automatically inject `WHERE company_id = current_tenant_var.get()`. With SQLAlchemy 2.0 async sessions backed by `asyncpg` and Neon's PgBouncer transaction-mode pooler, the failure mode is:

1. Request A (`company=juno`) sets `current_tenant_var.set("juno")` in middleware
2. Request A's async session checks out a connection from the pool, runs a Sonnet call (60s), releases the connection
3. Request B (`company=seva`) — handled by a different `asyncio.Task` — checks out the SAME connection while Request A is still awaiting Sonnet
4. If the tenant filter is applied via `SET LOCAL app.current_tenant = 'juno'` instead of a parameterized WHERE clause, Request B inherits Juno's setting because `SET` (not `SET LOCAL`) persists across the connection. Request B's `SELECT * FROM daily_summaries` returns Juno rows even though the user is on Seva.

This is the classic PostgreSQL RLS connection-pool leak documented in CVE-2024-10976 (RLS policies below subqueries disregarding user ID changes) and the broader "SET vs SET LOCAL" guidance for poolers.

**Why it happens:**
`ContextVar` is `asyncio.Task`-local, NOT connection-local. When the pool hands the same connection to a different task, the connection retains its session state. PgBouncer transaction mode resets state at transaction boundaries — but if the tenant is set OUTSIDE a transaction (e.g., in middleware before the first query), the state survives.

**How to avoid:**
- **Pattern A (RECOMMENDED for v3.0):** Pass `company_id` as an EXPLICIT parameter on every repository function. No middleware-injected ContextVar magic. A repo function with no `company_id` parameter is impossible to call against the wrong tenant. Code review rule: every query against a multi-tenant table MUST have `.filter(Model.company_id == company_id)` visible in the call site.
- **Pattern B (if ContextVar is unavoidable):** Use `SET LOCAL` inside an explicit transaction in every request, and use `pool_pre_ping=True` + `pool_recycle=300` (already configured per `STACK.md`). Add a `before_cursor_execute` SQLAlchemy event listener that asserts `current_tenant_var.get()` is set before any query runs against a multi-tenant table — fails loud, never silent.
- **Defense in depth:** Add a Postgres `RAISE EXCEPTION` trigger on `daily_summaries` that fails any INSERT with `company_id IS NULL`. Cron writes that forget the tenant will crash loudly instead of silently writing orphan rows.

**Warning signs:**
- Tests pass individually but fail when run in parallel (`pytest -n auto`)
- Operator switches from Seva to Juno and sees Seva rows briefly before refresh
- `agent_runs` rows show `company_id=seva` but the linked `daily_summary` is `company_id=juno`

**Phase to address:** Foundation phase — establish the repository-pattern + explicit `company_id` parameter rule BEFORE any cron, route, or feature touches a multi-tenant table.

---

### CRITICAL — Query without `company_id` filter is the #1 multi-tenancy bug

**What goes wrong:**
A single `SELECT * FROM daily_summaries ORDER BY date DESC LIMIT 1` in a route handler — written when the project was single-tenant in v2.x and never updated for v3.0 — returns Juno's daily summary to a Seva-authenticated user (or vice versa). The route looks correct, the test passes (single-tenant fixture), and the bug only surfaces when Juno data exists in production.

The v2.x codebase has ~20+ raw `select(DailySummary)` call sites across `backend/app/routers/`, `scheduler/agents/`, and tests. Every one of them must be audited.

**Why it happens:**
Single-tenant codebases have no concept of "the missing filter." Developers writing routes don't naturally think "wait, which tenant?" because the codebase never asked them to before. A `git grep` for `select(DailySummary)` finds the call sites but doesn't prove which ones have the filter.

**How to avoid:**
- **Audit-and-enforce:** Use an Alembic migration to RENAME `daily_summaries` to `_daily_summaries_legacy` temporarily, then create `daily_summaries` as a view that REQUIRES `company_id` via RLS. Any unfiltered query raises at runtime during the migration test phase. (This is a temporary scaffold; the view is dropped before merge.)
- **Lint rule:** Add a ruff custom rule or a CI grep check: `grep -rn 'select(DailySummary)' backend/ scheduler/ | grep -v 'company_id'` must return zero matches. Same for `select(AgentRun)`, `select(CalendarItem)`, `select(WeeklySweep)`.
- **Repository pattern:** Wrap every multi-tenant table in a `*Repository` class whose constructor takes `company_id` and stores it. ALL queries go through repository methods. The raw `select()` calls are forbidden outside repositories.
- **Test:** Add a "cross-tenant leak" test that inserts Juno data + Seva data, authenticates as Seva user, calls every list/detail endpoint, asserts NO Juno IDs appear in responses.

**Warning signs:**
- A single user-visible Juno headline appears on the Seva dashboard (catastrophic; v3.0 ships immediately broken)
- Test passes with single-tenant fixture, fails when Juno fixture added
- `daily_summaries` query plan in pg_stat_statements shows queries without `company_id` in the WHERE clause

**Phase to address:** Foundation phase — repository + audit + lint rule must be in place BEFORE Juno ingestion writes the first row.

---

### HIGH — Backfill race: cron writes during the `company_id` migration

**What goes wrong:**
The migration plan is:
1. ALTER TABLE `daily_summaries` ADD COLUMN `company_id VARCHAR(20) NULL`
2. UPDATE `daily_summaries` SET `company_id = 'seva'` (backfill existing rows)
3. ALTER TABLE `daily_summaries` ALTER COLUMN `company_id` SET NOT NULL
4. CREATE INDEX `ix_daily_summaries_company_id`

If the 08:00 PT or 12:00 PT `daily_summary` cron fires DURING step 2 (after ADD COLUMN, before backfill completes), the cron's INSERT will write a row with `company_id = NULL`. Step 3 (ALTER COLUMN ... SET NOT NULL) then fails because at least one row has NULL, and the migration aborts mid-way. The Railway deploy fails. The dashboard is down.

Even if step 3 doesn't fail (cron didn't fire in the window), the new row from the cron has `company_id = NULL` and is orphaned — invisible to both Seva queries (`WHERE company_id='seva'`) and Juno queries.

**Why it happens:**
The two daily cron times are well-known to the developer, but the migration window is short (~5-30 seconds at v2.1's row count). It's tempting to "just deploy during off-hours" and skip coordination. Murphy says the cron fires anyway, especially during DST transitions or Railway redeploy delays.

**How to avoid:**
- **Expand/contract pattern (mandatory):** Ship the migration as TWO Railway deploys:
  1. **Expand deploy:** ALTER TABLE ADD COLUMN `company_id` with a `DEFAULT 'seva'`. Existing rows backfill automatically via the DEFAULT. New cron writes (which don't yet pass `company_id` explicitly) also get `'seva'` automatically. The column is NOT NULL but has a DEFAULT — no race window.
  2. **Code-update deploy:** Update agent code to pass `company_id` explicitly. Drop the DEFAULT in a follow-up migration once all callers are explicit.
- **Alternative — pause the cron:** In the same migration file, set `seva_news_cron.pause_at_startup = True` via a feature flag for ONE deploy, run the migration, then resume. APScheduler's `pause_job(job_id)` is the API. But this adds operational complexity (mistakes = missed digests) — DEFAULT is safer.
- **Test in CI:** Spin up a Postgres + scheduler container, fire the cron, run the migration concurrently, assert no NULL rows result.

**Warning signs:**
- Migration log shows `WARNING: ALTER TABLE ... SET NOT NULL: column "company_id" contains null values`
- Daily summary card disappears from the Seva dashboard the morning after the v3.0 deploy
- `SELECT count(*) FROM daily_summaries WHERE company_id IS NULL` > 0 in production

**Phase to address:** Foundation phase — migration design. The expand/contract pattern must be in the roadmap as TWO phases (not "do the migration").

---

### HIGH — Missing composite index on `(company_id, date)` — query slowdown at low scale

**What goes wrong:**
Without `tenant_id` as the LEADING column of every index on a multi-tenant table, RLS-style queries (or even explicit `WHERE company_id = $1 AND date < $2`) become two orders of magnitude slower. At v3.0's scale (2 companies × ~14 rows/week × 52 weeks ≈ 1,500 rows/year per company), this is invisible. But the existing v2.x indexes are:
- `ix_daily_summaries_date` (on `date` only)
- `ix_daily_summaries_status` (on `status` only)

A query `WHERE company_id='juno' AND status='completed' ORDER BY date DESC LIMIT 1` will use the `status` index, fetch every Seva + Juno completed row, then filter — at 3K rows this is microseconds, but the query plan teaches the wrong habit and the bug is hidden until N companies grows.

**Why it happens:**
The existing indexes were designed for single-tenant. Adding `company_id` as a new column doesn't auto-rebuild indexes with it as the lead.

**How to avoid:**
In the same migration that adds `company_id`, also:
- DROP INDEX `ix_daily_summaries_date`
- CREATE INDEX `ix_daily_summaries_company_date ON daily_summaries (company_id, date DESC)`
- CREATE INDEX `ix_daily_summaries_company_status ON daily_summaries (company_id, status)`

Same for `agent_runs`, `calendar_items`, `weekly_sweeps`. Document the "company_id leads every multi-tenant index" rule in CONVENTIONS.md.

**Warning signs:**
- `EXPLAIN ANALYZE` on a recent-summary query shows `Filter: company_id = 'juno'` instead of `Index Cond: company_id = 'juno' AND date < ...`
- Frontend dashboard load time grows >100ms after Juno data is added

**Phase to address:** Foundation phase — index design alongside `company_id` migration.

---

### MEDIUM — Foreign-key cross-tenant pointer (agent_runs row pointing at the wrong company's summary)

**What goes wrong:**
`agent_runs.id` is referenced by `daily_summaries.agent_run_id` and `weekly_sweeps.agent_run_id` as nullable FK. After v3.0, every `agent_runs` row also has a `company_id`. The FK constraint does NOT enforce that `daily_summaries.company_id == agent_runs.company_id` — Postgres only checks that the FK target exists. A buggy code path that fetches an `agent_run` from Seva but writes a `daily_summary` under Juno's `company_id` produces a row whose FK points across tenants. This silently corrupts the "which agent run produced this summary" audit trail.

**Why it happens:**
Postgres FKs don't natively support multi-column equality constraints across tables without writing a CHECK constraint with a subquery (which is non-standard and slow).

**How to avoid:**
- **Composite FK pattern:** Add `(company_id, id)` as a composite PRIMARY KEY (or UNIQUE) on `agent_runs`, and use a composite FK `(company_id, agent_run_id) REFERENCES agent_runs(company_id, id)` on `daily_summaries`. Postgres now enforces tenant consistency automatically.
- **Trigger guard (lighter):** Add a Postgres trigger `BEFORE INSERT OR UPDATE ON daily_summaries` that raises if `NEW.company_id != (SELECT company_id FROM agent_runs WHERE id = NEW.agent_run_id)`.
- **Application-layer assert (minimum):** In the daily summary write path, assert `agent_run.company_id == summary.company_id` before commit. This catches the bug in dev but not in raw SQL.

For v3.0's scale (2 companies, low row volume), the application-layer assert is acceptable. Document the composite-FK upgrade as a v3.1+ task if N companies grows.

**Phase to address:** Foundation phase — application-layer assert. Composite FK deferred to v3.1+.

---

### MEDIUM — Test fixtures don't reset `company_id` context between tests

**What goes wrong:**
The existing 156 backend + 264 scheduler + 141 frontend tests use single-tenant fixtures (no `company_id`). When v3.0 adds `company_id`, the easy path is to set a default `company_id='seva'` in `conftest.py`. The trap: if a test fixture uses a module-scoped or session-scoped `current_tenant_var.set("seva")`, and a different test in the same session sets it to `"juno"`, the leak between tests is invisible — both tests pass because the data they query is in the right shape, but the LAST test to run determines the final state of the ContextVar at session teardown. CI green doesn't prove isolation.

**Why it happens:**
pytest fixtures default to function scope. ContextVar leaks between fixture scopes are an obscure failure mode.

**How to avoid:**
- All ContextVar/tenant fixtures MUST be `@pytest.fixture(scope="function")` with an explicit teardown that resets the var via `current_tenant_var.set(None)` or `current_tenant_var.reset(token)`.
- Add a dedicated `test_multitenant_isolation.py` that runs Seva and Juno fixtures in the same session and asserts no cross-contamination. Run it with `pytest -p no:cacheprovider --forked` to force process isolation as a sanity check.
- Update fixture factories to take `company_id` as a required parameter — no default. Forces test authors to be explicit about which tenant they're testing.

**Phase to address:** Foundation phase — establish multi-tenant test scaffolding before any tenant-aware feature is added.

---

## 2. Defence-Sector Domain Pitfalls

### HIGH — Anthropic content-policy refusal on conflict-zone news summarization

**What goes wrong:**
Claude (Sonnet 4.6) has documented content-policy guardrails around military/defence applications. The Anthropic-Pentagon dispute (2025-2026) established that Anthropic prohibits Claude's use in:
- Autonomous weapons targeting without human oversight
- Mass surveillance
- (Broadly) content that could be construed as operational intelligence for active conflicts

The Juno News Funnel ingests "world events relevant to defence" — by design, this includes Ukraine, Gaza, Iran/Israel, Korean peninsula, Taiwan Strait stories. A Sonnet prompt asking "summarize this story about the Israel-Gaza conflict and explain its relevance to defence manufacturers" may trigger a refusal or a heavily-hedged response, especially if the prompt frames the analysis from a "defence opportunity" angle. The cron silently produces a "failed" or "partial" daily summary with an unhelpful refusal message in the body. The operator's dashboard shows a blank Juno card.

**Why it happens:**
Anthropic's safety classifiers are trained to refuse operational-intelligence-style framings. The `daily_summary_system_prompt` for Seva (gold sector, no conflict content) does not trigger this. The Juno prompt, if cloned naively, will.

**How to avoid:**
- **Framing discipline:** The Juno system prompt MUST frame the analysis as **analyst-style market commentary**, not operational intelligence. Use language like "explain how this news affects the defence industry's market outlook" — NOT "summarize the tactical implications" or "identify targeting opportunities."
- **Explicit anti-pattern:** Add to the system prompt: "Do NOT provide tactical analysis, targeting recommendations, or operational details. Focus on industry/market/policy implications only."
- **Defensive handling:** Wrap the Sonnet call in a refusal-detector — if the response contains phrases like "I can't help with" or "I'm not able to provide" or is < 100 chars, mark the section as `partial` with `errors: ["sonnet_refused"]` and skip that story. Same pattern as the existing v2.1 partial-summary handling.
- **Test:** Maintain a test set of 5-10 known-edge-case stories (Ukraine military aid, Israeli operations, Taiwan tensions). Run them through the Juno prompt monthly and assert no refusals. If a refusal happens, the prompt needs revision.

**Warning signs:**
- Juno daily summary card has empty "world events" section despite RSS ingestion succeeding
- `agent_runs.errors` for `juno_daily_summary` contains `"sonnet_refused"` or similar marker
- Sonnet response body starts with "I understand you're looking for..." (classic refusal preamble)

**Phase to address:** News Funnel phase (Juno) — system prompt design is the FIRST deliverable.

---

### HIGH — False positives from "world events relevant to defence" — Sonnet drifts to consumer tech

**What goes wrong:**
The "world events relevant to defence" heuristic is intentionally broad — it must catch quantum computing breakthroughs, semiconductor export controls, drone supply chains, AI policy. But broad heuristics drift to consumer tech (Apple Vision Pro updates, ChatGPT releases, crypto news) without tight constraints. The Juno daily card fills with iPhone news because "consumer chips relate to defence chips."

This is the classic v2.0 Seva "GOLD_NEWS_SYSTEM_PROMPT excludes stories that don't advance the bull thesis" rule applied to defence — but the failure mode is opposite. Seva's filter is a one-directional exclusion (bull only). Defence is a two-axis filter: (defence industry AND/OR world events with defence relevance) — the false-positive surface is much larger.

**Why it happens:**
Sonnet defaults to inclusive interpretation when the prompt is "is this relevant to defence?" — almost everything is *arguably* dual-use. Dual-use technology (computer chips, comms, GPS) is explicitly cited by Chatham House and NSTXL as the dominant defence-tech trend. The boundary between "consumer tech with defence implications" and "consumer tech" is blurry.

**How to avoid:**
- **Explicit exclusion list in the system prompt:**
  ```
  EXCLUDE the following even if technically dual-use:
  - Consumer device launches (phones, tablets, headsets, wearables) unless the manufacturer announces a defence contract or military partnership
  - General AI/LLM releases (GPT, Claude, Gemini updates) unless the announcement specifically targets defence/intelligence applications
  - Cryptocurrency price moves and exchange news
  - Sports, entertainment, celebrity news under any framing
  - Pure climate/weather news unless tied to military operations or basing
  ```
- **Two-stage filter:** Stage 1 (Haiku, cheap) classifies each story as `defence_direct | dual_use_relevant | excluded`. Stage 2 (Sonnet) only summarizes `defence_direct` + `dual_use_relevant`. This mirrors the v2.0 LAW-04 Haiku filter pattern for Ontario law.
- **Calibration set:** Maintain a labeled set of 30-50 stories from the past 30 days, hand-classified by the operator. Run the filter against the set monthly and report precision/recall. If precision drops below 80%, tune the prompt.

**Phase to address:** News Funnel phase (Juno) — system prompt + Haiku pre-filter design.

---

### HIGH — RSS feed reorganization: Janes / Defense News / Breaking Defense URLs are not stable

**What goes wrong:**
Major defence sites have a documented history of reorganizing feed paths. Janes alone has shipped at least three distinct feed-path schemes in the past 24 months (`/feeds/all`, `/osint-insights/defence-news/feed`, the current `/osint-insights/defence-news/rss`). Defense News (defensenews.com/m/rss/) splits by section (Naval, Pentagon, Congress, Space, Training & Sim, Unmanned, Global) — each section is a distinct feed URL. A hardcoded list of 5-10 feed URLs in `defence_feeds.py` will rot within 6-12 months. When a feed 404s, `feedparser.parse(url)` does NOT raise — it returns an empty `entries` list with a `bozo=1` flag. The Juno cron silently produces a daily card with 0 defence-industry stories.

**Why it happens:**
RSS is a legacy protocol; publishers treat their feeds as undocumented infrastructure. Path changes are unannounced. `feedparser` is forgiving by design — it parses partial/broken feeds rather than erroring loudly.

**How to avoid:**
- **Health-check every feed on every run:** After `feedparser.parse(url)`, check `feed.bozo` and `len(feed.entries)`. If `bozo=1` AND `entries=[]`, mark the feed as failed-this-run. Log the URL + `feed.bozo_exception` to `agent_runs.errors`. Same pattern as the v2.1 weekly_sweeper subreddit-403 isolation.
- **Per-feed minimum threshold:** If ANY single feed returns < 1 entry on a run AND the previous run from the same feed returned > 5 entries, alert via the existing WhatsApp failure-alert pattern (`WHA-03`). This catches "feed silently went dark" within one cron cycle.
- **Feed-URL discovery fallback:** When a feed 404s/empties, attempt a SerpAPI query `site:janes.com defence news` to discover the new feed URL programmatically. Log the discovery for operator review (don't auto-update prod config — operator confirms).
- **Diversify across publishers:** Don't rely on any one publisher for >30% of stories. The Juno feed list should include at minimum: Janes, Defense News, Breaking Defense, Defense One, War.gov (DoD official), RealClearDefense, plus one Canadian source (RCAF news / CDA Institute) and one European source (Janes already covers EU, but adding Defence-blog or Defence IQ provides redundancy).

**Warning signs:**
- Juno daily card consistently has < 3 defence-industry stories despite RSS feeds appearing healthy
- `agent_runs.errors` for `juno_daily_summary` contains repeated entries for the same feed URL
- `bozo=1` warnings appear in scheduler logs

**Phase to address:** News Funnel phase (Juno) — feed-health-check + diversification.

---

### MEDIUM — Regional source bias: US-defence-press-only misses Canadian, European, Asian context

**What goes wrong:**
Juno Industries is a Canadian defence-tech company. The natural feed list (Defense News, Breaking Defense, Defense One) is US-centric. Canadian procurement news (DND, RCAF, ISED), NATO announcements from Brussels, European Defence Agency news, and Indo-Pacific (Korea, Japan, Australia defence) stories are under-represented. The Juno daily card will look like "US defence news with a Canadian sticker on it" — missing the operator's actual market context.

**Why it happens:**
US defence press dominates RSS aggregator rankings (FeedSpot's top-60 list is ~70% US sources). The path of least resistance is to add the top-ranked US feeds and call it done.

**How to avoid:**
Explicit regional quota in the feed list:
- 4-5 US feeds (Defense News, Breaking Defense, Defense One, DefenseScoop, War.gov)
- 2 Canadian feeds (RCAF news, CDA Institute, or Canadian Defence Review)
- 2 European feeds (Janes EU coverage, EDA news, Defence-blog Europe, or RUSI)
- 1-2 Indo-Pacific feeds (Australian Defence Magazine, Korea JoongAng Defense, Japan Ministry of Defense English feed)
- 1 NATO feed (NATO.int press releases)

Same diversification logic as `STAT-04` (Ontario stats prefer NRCan + StatCan over US sources). Document the regional quota in CONVENTIONS.md so feed-list edits maintain balance.

**Phase to address:** News Funnel phase (Juno) — feed list design.

---

### MEDIUM — Newsletter / opinion content mixed with hard news

**What goes wrong:**
Feeds like Defense One's "Ideas" stream, RealClearDefense's commentary section, and Defence IQ's "thought leadership" articles include opinion pieces, contractor white papers, and product-marketing-disguised-as-news. Treating these as equivalent to hard news (Janes wire reports, Defense News breaking-news section) pollutes the summary with vendor-pitch content.

**Why it happens:**
RSS feeds don't distinguish between news and opinion at the protocol level. Both have the same `<item>` structure.

**How to avoid:**
- **Feed-level classification:** Tag each feed in the config as `wire | analysis | opinion | newsletter`. Only include `wire` and `analysis` in the daily summary; mark `opinion` and `newsletter` as supporting context (not lead stories).
- **Title heuristic:** Stories with `"Opinion:"`, `"Commentary:"`, `"Op-Ed:"`, `"Analysis:"`, `"Sponsored:"`, or `"From Our Partners"` prefixes are filtered. Add the heuristic to the existing v2.1 dedup/filter pipeline.
- **Sonnet hint:** Pass the feed-classification tag to Sonnet in the prompt context so it can weight the story appropriately.

**Phase to address:** News Funnel phase (Juno) — feed metadata + filter integration.

---

### MEDIUM — Defence news cycle spans US Eastern / UK / Israel / Korea timezones — "daily summary" boundary ambiguity

**What goes wrong:**
The v2.x daily_summary runs at 08:00 PT and 12:00 PT, capturing news published in the prior 12-24 hours. For Seva (Ontario/North American gold sector), this is well-aligned with the news cycle. For Juno (global defence), a 08:00 PT cron captures:
- US Eastern news from the prior 11 hours (5 PM EST yesterday → 11 AM EST today)
- UK news from the prior 16 hours (4 PM GMT yesterday → 4 PM GMT today — but UK morning news is 3 AM PT, captured next run)
- Israel news from the prior 18 hours
- Korea/Japan from the prior 16 hours (most of the workday already done)

A major Asian defence announcement at 9 AM Tokyo time (5 PM PT yesterday) sits in the feed for 15 hours before being summarized — and by then a US Eastern reaction story may already be in the same feed, leading to "story already covered" dedup hiding the original announcement.

**Why it happens:**
"Daily summary" assumes a coherent regional news day. Defence is global with no coherent boundary.

**How to avoid:**
- **Decision (recommended):** Keep the same 08:00 / 12:00 PT cadence for Juno (operational simplicity, single-operator schedule). Document the timezone caveat in the prompt: "You may see stories that broke 18+ hours ago in Asia — treat publish_at timestamps as the source of truth, not 'breaking now.'"
- **Alternative:** Add a 22:00 PT (midnight Eastern / 6 AM UK / 8 AM Israel) cron specifically for Juno. Doubles the Sonnet cost but captures the European morning news cycle. Defer to v3.1+ unless the operator finds the 12-hour gap painful.
- **Sonnet grounding rule:** Always inject `published_at` into the prompt context (already done for Seva per MOD-5). Force the model to reference timestamps rather than imply recency.

**Phase to address:** News Funnel phase (Juno) — cron schedule decision documented in PROJECT.md.

---

## 3. Scheduler Fan-Out

### CRITICAL — Lock ID collision when adding per-company crons (OPS-02 extension)

**What goes wrong:**
The current `JOB_LOCK_IDS` allocates:
- 1005, 1010-1016 (dead-code reserved)
- 1017: daily_summary (Seva)
- 1018: daily_summary_prune
- 1019: weekly_sweeper (Seva)

v3.0 introduces `juno_daily_summary` at minimum. Naive allocation: 1020. But what about `juno_daily_summary_prune`? `juno_weekly_sweeper` (deferred to v3.1)? If the developer adds `juno_daily_summary: 1020` and later (v3.1) adds `juno_weekly_sweeper: 1020` by accident — copy/paste error from another company's allocation — the OPS-02 assertion catches it at module import time. Good. But if the developer adds `juno_daily_summary: 1019` (typo — `1019` is `weekly_sweeper`), the OPS-02 assertion ALSO catches it. Less good is the failure mode where someone adds the job in `build_scheduler()` without registering it in `JOB_LOCK_IDS` at all — the assertion doesn't fire and two jobs use the same advisory lock silently.

**Why it happens:**
The OPS-02 pattern catches DICT collisions but not "registered job vs unregistered job" collisions. Per-company fan-out doubles the number of lock IDs that have to stay coherent, increasing typo surface.

**How to avoid:**
- **Tenant-scoped lock IDs:** Allocate a 100-ID block per tenant. Seva: 1000-1099. Juno: 1100-1199. New companies: 1200-1299, etc. Assign:
  - 1017: seva_daily_summary (existing — DO NOT renumber; preserves all v2.x advisory locks)
  - 1018: seva_daily_summary_prune (existing)
  - 1019: seva_weekly_sweeper (existing)
  - 1117: juno_daily_summary (new)
  - 1118: juno_daily_summary_prune (new — even if pruning isn't implemented yet, reserve the slot)
  - 1119: juno_weekly_sweeper (reserved for v3.1)
- **Naming convention enforced at import:** Add a second OPS-02 assertion that every job name in `build_scheduler()` is also in `JOB_LOCK_IDS`. Use `set(scheduler.get_jobs_ids()) <= set(JOB_LOCK_IDS.keys())` after `build_scheduler()` returns.
- **Document in CONVENTIONS.md:** "Lock IDs are allocated in 100-ID blocks per tenant. Tenant block assignments are append-only — never renumber existing locks."

**Phase to address:** Foundation phase — lock ID block allocation BEFORE any Juno cron is registered.

---

### HIGH — Single cron iterating companies: one slow tenant blocks the next

**What goes wrong:**
The "one cron, iterates all companies" pattern is appealing for code simplicity:
```python
async def daily_summary_all_companies():
    for company in ['seva', 'juno']:
        await run_daily_summary(company)
```
But: if Seva's Sonnet call hangs at the 60s timeout, Juno doesn't start until 60s later. Worse, if Seva's call fails inside the agent (not at the timeout layer) and the existing partial-summary logic does retries, Juno may not run at all in the misfire grace window. Juno's daily card is missing.

**Why it happens:**
Sequential `for` loop over tenants. Natural pattern but couples failure domains.

**How to avoid:**
- **One cron per company (RECOMMENDED):** Register `seva_daily_summary` and `juno_daily_summary` as INDEPENDENT APScheduler jobs with independent advisory locks. They run concurrently (each acquires its own lock). Seva failure does not affect Juno. Adding a third company is a new job registration — no fan-out logic to update.
- **If fan-out is unavoidable (e.g., 10+ companies):** Use `asyncio.gather()` with `return_exceptions=True` to run all tenants concurrently:
  ```python
  results = await asyncio.gather(
      *[run_daily_summary(c) for c in companies],
      return_exceptions=True
  )
  for company, result in zip(companies, results):
      if isinstance(result, Exception):
          logger.error("daily_summary failed for %s: %s", company, result)
  ```
- **Test:** Mock Seva's Sonnet call to hang for 90s; assert Juno's call completes within 30s anyway (concurrent, not sequential).

**Phase to address:** Foundation phase — scheduler topology decision (one job per company) documented before code.

---

### HIGH — Idempotency: Juno cron retry re-summarizes Seva

**What goes wrong:**
APScheduler's `misfire_grace_time=1800` (30 minutes) means a job that misses its scheduled time by < 30 min still fires once the worker recovers. If `daily_summary_all_companies()` (single fan-out cron) misfires AFTER Seva completed but BEFORE Juno started — e.g., Railway redeploy at 08:05 PT, worker boots at 08:20 PT, misfire grace fires the job at 08:20 — the implementation must check "is today's Seva summary already done?" before re-running it. Without an idempotency check, the misfire retry re-summarizes Seva (wasted Sonnet $), overwrites the existing row (data loss if the second run produces a degraded summary), and inflates `agent_runs` with duplicate entries.

The v2.x daily_summary uses advisory locks AND a "today already completed?" pre-check (`exists(SELECT 1 FROM daily_summaries WHERE date = today AND status = 'completed')`). The same pre-check must be applied per-company.

**Why it happens:**
Advisory locks prevent concurrent execution but not duplicate execution across the misfire grace window.

**How to avoid:**
- **Per-company idempotency check:** Before running the tenant-specific cron logic, query `SELECT 1 FROM daily_summaries WHERE company_id = $1 AND date = today AND status = 'completed'`. If exists, skip with a `agent_runs.status='skipped_already_completed'` log entry.
- **Mirror the v2.x pattern exactly:** The v2.0 `run_daily_summary` already has this check for the single-tenant case — extend it to scope by `company_id`.
- **Per-company cron jobs (recommended above) make this trivial:** each job has its own idempotency scope, no cross-tenant coordination needed.

**Phase to address:** Foundation phase — extend existing idempotency check to be company-scoped.

---

### MEDIUM — Anthropic API rate limit hit ACROSS companies, not per-company

**What goes wrong:**
Anthropic's API rate limits (requests per minute, tokens per minute) apply to the API key, not to the workload. When Seva's daily summary runs at 08:00 PT and Juno's runs at 08:01 PT (one cron per company, slightly staggered start), the two Sonnet calls plus the Haiku pre-filters can saturate the rate limit for ~30 seconds. The second call gets a `429 Too Many Requests` and the existing v2.x retry logic kicks in — but the existing retry is sized for a single tenant. With 2 tenants concurrent, the retry storm can cascade.

**Why it happens:**
Single-tenant Seva never saturated the rate limit. Multi-tenant doubles concurrency without raising the budget envelope.

**How to avoid:**
- **Stagger company crons by 5+ minutes:** Seva at 08:00 PT, Juno at 08:05 PT. Different `CronTrigger(hour=8, minute=0)` vs `CronTrigger(hour=8, minute=5)`. APScheduler trivially supports this.
- **Document the stagger as intentional in CONVENTIONS.md:** Future companies (v3.2+) MUST be staggered at 5-minute intervals to avoid rate-limit collisions.
- **Monitor Anthropic usage dashboard monthly:** Total monthly tokens. v3.0 budget envelope is $210-225/mo total. If Juno alone is pushing >$15/mo, the prompt needs trimming.

**Phase to address:** News Funnel phase (Juno) — cron schedule offset.

---

## 4. Frontend Routing Migration

### CRITICAL — Existing bookmarks to `/` break without default-tenant redirect

**What goes wrong:**
v2.x users bookmark `/` (the News Funnel feed). v3.0 changes URL structure to `/seva/`, `/juno/`. If the root route `/` is removed without a redirect to `/seva/`, every existing bookmark + browser history entry produces a 404 (or worse, a public route that bypasses auth depending on route ordering).

**Why it happens:**
URL restructure is treated as a "new path" deploy, not a "migrate old paths" deploy. The grace redirects from v2.0 (`/queue` → `/`) exist for exactly this reason — but the developer who built v3.0 may not see them as a pattern to extend.

**How to avoid:**
Add to `App.tsx`:
```tsx
<Route path="/" element={<Navigate to="/seva" replace />} />
<Route path="/calendar" element={<Navigate to="/seva/calendar" replace />} />
<Route path="/viral" element={<Navigate to="/seva/viral" replace />} />
{/* v2.0 redirects still apply */}
<Route path="/queue" element={<Navigate to="/seva" replace />} />
<Route path="/agents/:slug" element={<Navigate to="/seva" replace />} />
```
- All redirects must be INSIDE `<ProtectedRoute />` (mirror v2.1 pitfall #2 lesson).
- The default-tenant target (`/seva`) is the "owner's home" tenant — assume the operator always has Seva access. Document the convention: "If a user has access to multiple tenants but no explicit URL, redirect to the alphabetically first or the operator-designated default."
- Test: visit each old path as authenticated user, assert it lands on the correct v3.0 path AND renders the correct page.

**Phase to address:** Foundation phase — routing layout.

---

### HIGH — TanStack Query keys missing `company_id` — cross-tenant stale data

**What goes wrong:**
Existing query keys look like `['daily-summary-feed']`, `['calendar-items']`, `['weekly-sweep']`. If these are NOT updated to include `company_id`, the moment the operator clicks the company switcher (Seva → Juno), TanStack Query returns the CACHED Seva data for `['daily-summary-feed']` while triggering a background refetch for Juno. For the first 200-2000 ms (until refetch lands), the Juno dashboard renders Seva's stories. The operator sees the stale data, refreshes, and only then sees Juno content.

This is documented in TanStack Query's caching guide: query key hierarchy must include the tenant identifier or cache leaks between tenants on key collision.

**Why it happens:**
The single-tenant codebase uses scalar keys. Adding `company_id` to every key requires editing every `useQuery` / `useMutation` / `queryClient.invalidateQueries` call site. Easy to miss one.

**How to avoid:**
- **Key factory pattern:** Centralize query keys in `frontend/src/queryKeys.ts`:
  ```typescript
  export const queryKeys = {
    dailySummaryFeed: (companyId: string) => ['daily-summary-feed', companyId] as const,
    calendarItems: (companyId: string) => ['calendar-items', companyId] as const,
    weeklySweep: (companyId: string) => ['weekly-sweep', companyId] as const,
  }
  ```
  No raw key arrays in component code. The factory ENFORCES that `companyId` is passed at every call site.
- **Switcher invalidation:** When the user switches companies, call `queryClient.clear()` (nuclear) OR `queryClient.removeQueries({ queryKey: ['daily-summary-feed'] })` (surgical, prefix match). The former is simplest and avoids the stale-render window entirely.
- **Test:** Mock the API to return Seva data for `companyId='seva'` and Juno data for `companyId='juno'`. Render the dashboard, switch tenants, assert no Seva data appears in the Juno render at any time.

**Phase to address:** Foundation phase — query key factory + switcher behavior. BEFORE the company switcher UI is built.

---

### HIGH — Login redirect drops company context

**What goes wrong:**
The v2.x login flow: operator visits `/`, sees the login screen (auth gate), submits password, lands at `/`. Now: operator visits `/juno/calendar`, sees login, submits password, lands at `/seva` (or `/`) because the login form doesn't preserve the original target URL. The operator has to re-navigate to Juno. Bookmark links to Juno tabs become a two-step "log in, then click switcher" flow.

**Why it happens:**
React Router's `<Navigate to="/" />` after auth success is naive. The original location isn't captured.

**How to avoid:**
Capture and restore the intended URL:
```tsx
function ProtectedRoute({ children }) {
  const location = useLocation()
  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }
  return children
}

function LoginPage() {
  const location = useLocation()
  const from = location.state?.from?.pathname || '/seva'
  // ... after successful login:
  navigate(from, { replace: true })
}
```
- The `from` location includes pathname AND search params AND hash — preserve all three.
- The default fallback is `/seva` (the operator's primary tenant), not `/`.

**Phase to address:** Foundation phase — auth flow update.

---

### MEDIUM — Tab state leaks across company switches

**What goes wrong:**
Within a tenant (e.g., Juno), the operator selects Tab 2 (Calendar). They switch to Seva. Seva's dashboard renders with Tab 1 (News Funnel) per URL-driven tab state — which is correct (URLs are independent per tenant). BUT: if any tab-specific UI state lives in Zustand (e.g., "calendar week offset", "filter chip selection"), it persists across the switch. The operator sees Seva's News Funnel with Juno's calendar week-offset value applied — meaningless but confusing.

**Why it happens:**
Zustand stores are global by default. State that should be tenant-scoped lives in a flat store.

**How to avoid:**
- **Tenant-scoped Zustand slices:** Refactor the store to `state[companyId].calendarWeekOffset` instead of `state.calendarWeekOffset`. Selectors take `companyId` as an argument.
- **OR — clear UI state on switch:** When the company switcher fires `setCompany(newCompany)`, also reset all tab-local UI state via `useStore.setState({ calendarWeekOffset: 0, filterChips: [], ... })`. Simpler but loses navigation context within a tenant.
- **OR — push state into URL search params:** Calendar week offset becomes `?week=2026-W21`. Eliminates the cross-tenant leak by removing the global state entirely. Best long-term solution; defer if it's a wide refactor.

For v3.0, the "clear on switch" approach is acceptable. Document the search-params upgrade as v3.1+.

**Phase to address:** Foundation phase — switcher behavior.

---

## 5. AppHeader Freeze Constraint Conflict

### HIGH — `AppHeader.tsx` is byte-frozen per Phase 5; v3.0 requires a switcher inside it

**What goes wrong:**
v2.1 Phase 5 declared `AppHeader.tsx` byte-frozen as the visual QA baseline (UI-07 sign-off). The v3.0 PROJECT.md explicitly notes "a surgical addition" — but a company switcher is not surgical. It changes the header's layout, adds a Radix Popover or DropdownMenu primitive, adds state binding, and shifts the brand mark. Treating this as "small edit" produces a header that no longer matches the Phase 5 baseline. Subsequent visual QA can't compare against the baseline; regressions in the existing brand/logout layout slip through.

**Why it happens:**
The freeze constraint was a deliberate boundary to lock the v2.1 visual QA. v3.0's planning treated the constraint as a soft guideline ("surgical addition") rather than a hard contract ("frozen file"). Re-opening a frozen file silently invalidates the baseline.

**How to avoid:**
Two acceptable paths:

**Path A — Formally lift the freeze, document the new baseline:**
1. Add a v3.0 Phase 0 task: "Lift AppHeader freeze. Document why (multi-tenant switcher required). Re-run visual QA after switcher addition. Establish v3.0 visual QA baseline."
2. Edit `AppHeader.tsx` with the switcher.
3. Update CONVENTIONS.md or wherever the freeze was declared to point at the new baseline.
4. Visual QA at 1440×900 across Seva and Juno tenants.

**Path B — Add a sibling component, leave AppHeader byte-identical:**
1. Create `frontend/src/components/CompanyBar.tsx` — a NEW component that renders the switcher BELOW the AppHeader, in its own bar (`border-b border-zinc-800` matching the v2.1 sub-nav pattern from the tab nav).
2. `AppShell.tsx` renders `<AppHeader />` followed by `<CompanyBar />` followed by the tab nav and main content.
3. AppHeader stays byte-frozen. CompanyBar is a separate component, freeze-able on its own.

**Recommendation:** Path B for v3.0 launch. It preserves the v2.1 baseline, keeps the freeze contract intact, and adds a clear architectural place for the switcher. Path A is a heavier change with more visual QA debt — defer it.

**Warning signs:**
- A PR titled "small AppHeader update for switcher" shows diff > 30 lines in AppHeader.tsx
- Visual QA at 1440×900 shows AppHeader looks different from v2.1 baseline screenshots
- The freeze comment in AppHeader.tsx is removed without an accompanying CONVENTIONS.md update

**Phase to address:** Foundation phase — switcher placement decision. Decide Path A vs Path B before any header-touching work begins.

---

## 6. Test Infrastructure

### HIGH — Existing 156 + 264 + 141 tests assume single tenant; adding `company_id` to fixtures has wide blast radius

**What goes wrong:**
The existing tests assume:
- Backend: `db_session` fixture inserts data without `company_id`
- Scheduler: `mock_daily_summary` fixture builds rows without `company_id`
- Frontend: API response mocks don't include `company_id`

When v3.0 adds `company_id` as NOT NULL, every fixture file (~30-50 files across backend + scheduler + frontend) needs an update. The trap: a developer updates the fixture file but the test still passes because the fixture defaults `company_id='seva'`. The test doesn't actually verify multi-tenant behavior — it just continues to test single-tenant correctness with a meaningless `company_id` field. CI green doesn't prove tenant isolation.

A subtler failure: a fixture that creates BOTH Seva and Juno data, but the test code under test only filters by date (forgot the `company_id` filter). The test passes against the fixture because dates happen not to collide. In production, the same query returns rows from both tenants.

**Why it happens:**
"Update fixtures to add `company_id`" is interpreted as a mechanical refactor. Adding the column doesn't change what's tested.

**How to avoid:**
- **Per-fixture audit:** For every fixture that creates DB rows, decide explicitly: "is this a single-tenant test or a multi-tenant test?"
  - Single-tenant tests: explicitly `company_id='seva'`, document why
  - Multi-tenant tests: insert BOTH Seva and Juno rows, assert queries return only the requested tenant
- **New required test class — `test_multitenant_isolation.py`:** For every list/detail endpoint and every cron, add a test that creates BOTH tenants' data and asserts the system returns only the queried tenant. This is THE most important test class added in v3.0.
- **Mark mechanical fixture updates:** Add a `# TODO: v3.0 multi-tenant verification` comment to every fixture file updated mechanically. Track the count via grep. Once a fixture's multi-tenant story is verified, the TODO comes out.
- **CI grep gate:** A CI check that counts `# TODO: v3.0 multi-tenant verification` comments. The count must monotonically decrease across PRs. Final count of zero = full audit complete.

**Phase to address:** Foundation phase (initial fixture migration) AND every feature phase (per-endpoint isolation tests).

---

### MEDIUM — Frontend MSW mocks lack `company_id` routing

**What goes wrong:**
The frontend tests use MSW (Mock Service Worker) to mock API responses. If the mocks don't differentiate by `company_id` in the URL (e.g., `/api/summary-feed` vs `/api/seva/summary-feed`), the component under test can't be exercised with multi-tenant scenarios. The test "checks that the summary feed renders" — but it doesn't check that switching tenants causes a re-fetch with the new tenant in the URL.

**Why it happens:**
MSW handlers in v2.x match by path only. Multi-tenant requires matching by path-prefix or query parameter.

**How to avoid:**
- Update all MSW handlers to match `/api/:companyId/...` pattern (URL-parameterized).
- Each test sets up handlers for the tenants it cares about (Seva-only, Juno-only, or both for isolation tests).
- A canonical "switcher behavior" test: render the app with both tenants mocked, click switcher, assert the API call URL changed to include the new tenant.

**Phase to address:** Foundation phase — MSW handler refactor alongside frontend routing changes.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Use `juno_daily_summaries` as a separate table instead of `company_id` column | Zero migration risk on existing v2.x rows; query simplicity | N tables grow linearly with companies; cross-tenant analytics impossible; duplicate index/migration overhead | Acceptable ONLY if v3.0 is the last multi-tenant company (Juno proves the pattern, then we go back to single-tenant). Never for true multi-tenant. |
| Ship `company_id` as nullable, defer NOT NULL | Avoids backfill race in step 3 | NULL rows accumulate; queries must defensively filter `company_id IS NOT NULL`; tenant isolation becomes opt-in instead of enforced | Acceptable during the expand/contract migration window only. Must close to NOT NULL within ONE deploy cycle. |
| Single cron iterating companies (`for company in [...]`) | One cron registration, one lock ID | One slow tenant blocks others; failure domains coupled; per-company misfire-grace impossible | Acceptable if you have ≤2 tenants AND the per-tenant runtime is < 30s AND you commit to refactoring before tenant #3. |
| Hardcoded company list in code (`COMPANIES = ['seva', 'juno']`) | No DB schema for companies table | Adding company #3 requires a code deploy; no per-company config (display name, brand color, etc.); operator can't self-serve | Acceptable for v3.0 (proving the pattern with 2 companies); MUST become a `companies` table by v3.2+ when N grows. |
| `company_id` as VARCHAR, not FK to a `companies` table | Simpler migration; no companies table to seed | Typos in code (`'jjuno'`) write valid-looking data that's orphaned; no referential integrity | Acceptable for v3.0 only with a CHECK constraint enforcing `company_id IN ('seva', 'juno')`. Drop the CHECK + add the FK when the `companies` table lands. |
| Reuse the Seva Sonnet system prompt with minor tweaks for Juno | Fast path to a working Juno daily card | The Seva prompt is calibrated for the gold bull thesis — the wrong frame for defence. Sonnet refusals + false positives will mount. | Never. The Juno prompt must be designed from scratch with the defence-specific constraints (anti-tactical, regional balance, dual-use exclusion list). |
| Skip the cross-tenant isolation tests for v3.0 launch | Faster delivery | The most likely v3.0 production bug (data leak between tenants) goes uncaught. Recovery requires emergency hotfix + customer apology. | Never. These tests are the MVP of v3.0. |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| PostgreSQL connection pool (Neon `-pooler` endpoint) | `SET app.current_tenant = 'juno'` (no LOCAL) — persists across the pool connection lifecycle, leaks to next request | `SET LOCAL app.current_tenant = 'juno'` inside an explicit BEGIN/COMMIT block, OR pass `company_id` as a query parameter (no session state at all) |
| asyncpg + SQLAlchemy 2.0 async session | Assuming `AsyncSession` is tenant-bound; reusing it across requests via ContextVar | `AsyncSession` is per-request via FastAPI `Depends`. Tenant identity comes from the JWT, not from session state. Use explicit `company_id` parameters. |
| RSS feeds (`feedparser`) | Treating empty `entries=[]` as "no news today" | Check `feed.bozo`, `feed.bozo_exception`, and compare entry count to recent history. Alert on sudden drops. |
| Anthropic Sonnet (defence content) | Cloning the Seva system prompt verbatim for Juno | Design the Juno prompt from scratch with anti-tactical framing, explicit dual-use exclusion list, and refusal-detection wrapper |
| TanStack Query | Updating one `useQuery` to include `company_id` but missing the matching `invalidateQueries` call site | Centralize keys in `queryKeys.ts`. All invalidations go through the same factory. Find/replace becomes safe. |
| React Router | Restructuring routes without preserving v2.x bookmark URLs | Add `<Navigate to="/seva" replace />` for every removed/changed v2.x path. Test from a fresh incognito session with the old bookmark. |
| APScheduler advisory locks | Adding a new job to `build_scheduler()` without registering its lock ID in `JOB_LOCK_IDS` | Add an assertion after `build_scheduler()` returns: every registered job ID must appear in `JOB_LOCK_IDS`. Fail-fast at worker boot. |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Missing composite index `(company_id, date)` | Query plan shows `Filter:` instead of `Index Cond:` for `company_id`; latency grows linearly with row count | Add composite index in the `company_id` migration; convention: `company_id` leads every multi-tenant index | Invisible at v3.0's row count (<5K total). Becomes painful at ~50K rows or when N companies grows. |
| RSS feed fan-out: parsing 15 feeds sequentially | Juno cron runtime grows from ~25s (Seva baseline) to 90+ seconds; misfire grace window exceeded | Parse feeds concurrently with `asyncio.gather()` (each `feedparser.parse` wrapped in `asyncio.to_thread`); cap concurrency at 5 | Breaks when total feeds × per-feed latency > 30 min misfire window. At 15 feeds × 5s avg = 75s sequential, still under the cap, but a single slow feed (timeout = 30s) can push over. |
| Per-company Sonnet calls saturating rate limit | `429 Too Many Requests` in `agent_runs.errors`; retries cascade | Stagger company crons by ≥5 minutes; monitor Anthropic usage dashboard monthly | Breaks at ~3 companies if all run in the same minute, OR if Sonnet prompt sizes balloon to push tokens-per-minute over the tier limit |
| Two-stage Haiku + Sonnet filter (per pitfall §2 above) | Costs $$ per story even after rejection | Hard-limit total stories evaluated per cron to <50; only stories that pass Haiku reach Sonnet | Breaks when feed list grows to >10 feeds with >20 stories each = 200+ story candidates per cron. Haiku at $0.001/story = $0.20/cron = $6/mo just for filtering. |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Authorization check at route level filters by `current_user.id` but not `current_user.has_access_to(company_id)` | A logged-in Seva operator can manually craft URLs to Juno endpoints and access Juno data | Add a `require_company_access(company_id)` dependency to every multi-tenant route. The dep raises 403 if the user can't access the requested company. For v3.0 single-operator, this means "the operator has access to both Seva and Juno" — but the check must EXIST so v3.2+ multi-operator can extend it. |
| Audit log doesn't capture `company_id` | Forensic analysis after a data leak can't determine WHICH tenant's data was accessed | Add `company_id` to every `agent_runs` row and every route-access log line. The existing `agent_runs.errors` JSONB pattern can hold this. |
| Backup/restore doesn't preserve tenant isolation | Restoring a backup overlays both tenants' data; if one tenant has a corruption, restoring partial backup risks the other tenant | Neon's PITR (point-in-time recovery) is database-level, not tenant-level. Document that any restore operation requires manual verification of BOTH tenants' state post-restore. |
| Defence-sector ingestion pulls export-controlled content | Some defence news (technical specs, weapon parameters) may be ITAR/EAR controlled; aggregating/republishing could create compliance exposure | Source from PUBLIC press releases and analyst coverage ONLY. Never scrape behind-paywall defence-industry-insider content. Document the source-allowlist policy. |
| Sonnet prompt logs (Anthropic-side) contain Seva proprietary intel mixed with Juno defence-relevant snippets | If Anthropic ever logs prompts for safety review, cross-tenant content is mixed in a single review record | Use a different Anthropic API key per tenant — `ANTHROPIC_API_KEY_SEVA` and `ANTHROPIC_API_KEY_JUNO`. Anthropic's safety logging is per-key; tenant boundaries are preserved upstream. |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Company switcher hidden in a menu | Operator forgets they're on the wrong tenant; mistakes Seva news for Juno news | Prominent persistent switcher in the header bar (or sub-bar). Display the active company name in 14-16px text next to the brand mark. |
| No visual differentiation between Seva and Juno dashboards | Operator can't tell at a glance which tenant they're on — especially at 7 AM checking on phone | Even if v3.0 keeps the same amber/zinc palette (per PROJECT.md), add a single-word company name in the header at body text size. Defer per-tenant accent color to v3.1. |
| Switching companies clears unsaved calendar edits without warning | Operator types into a calendar cell, switches tenants, comes back, work is gone | Use `beforeunload`-style warning on dirty form state, OR persist dirty state to localStorage per tenant. The v2.1 calendar's auto-save-on-blur mostly mitigates this — verify the auto-save fires BEFORE the company switch animation. |
| "All companies" overview view that bypasses tenant scoping | Operator clicks "see everything" expecting an aggregated view; gets a query that violates tenant isolation contract | Explicitly do NOT build an "all companies" view in v3.0. Cross-tenant analytics is in the deferred-to-v3.1+ list. If the operator asks for it, build it carefully as a separate `/admin/all-tenants/` route with hardcoded admin-only access. |
| Empty Juno dashboard on day 1 looks "broken" | Operator deploys v3.0, switches to Juno, sees blank state, thinks the migration broke things | Implement an explicit empty-state component: "Juno News Funnel — your first daily summary will appear after the 08:00 PT cron tomorrow. To trigger one now, run `python -m scheduler.agents.juno_daily_summary`." Mirror the v2.1 Phase 7 weekly sweep empty-state pattern. |

---

## "Looks Done But Isn't" Checklist

- [ ] **`company_id` column added:** Often missing — composite index `(company_id, date)` and `(company_id, status)` — verify `EXPLAIN ANALYZE` on the canonical "latest summary" query uses the composite index
- [ ] **Repository pattern enforced:** Often missing — CI grep check that `select(DailySummary)` outside `repositories/` directory returns zero matches
- [ ] **Cross-tenant isolation tests:** Often missing — `test_multitenant_isolation.py` covering every list/detail endpoint and every cron — verify both Seva and Juno fixtures are inserted in the same test
- [ ] **Default-tenant redirects:** Often missing — `/` → `/seva`, `/calendar` → `/seva/calendar`, `/viral` → `/seva/viral` — verify each as authenticated user from incognito session
- [ ] **TanStack Query keys factory:** Often missing — `frontend/src/queryKeys.ts` exists and ALL queries use it — grep for `useQuery({queryKey: [` outside the factory returns zero matches
- [ ] **Query cache cleared on switcher fire:** Often missing — `queryClient.clear()` or surgical `removeQueries` on company switch — verify by switching tenants rapidly and observing no stale data flash
- [ ] **JWT contains `company_id` access list:** Often missing — the operator's JWT lists which companies they can access — verify by crafting a request for Juno data with a Seva-only JWT and asserting 403
- [ ] **AppHeader freeze contract resolved:** Often missing — either Path A documentation in CONVENTIONS.md OR Path B sibling component verified — verify diff to `AppHeader.tsx` matches the chosen path
- [ ] **Lock ID block allocated per tenant:** Often missing — Seva 1000-1099, Juno 1100-1199 — verify by grep `JOB_LOCK_IDS` and confirm tenant-prefixed names map to the right block
- [ ] **Juno empty-state component:** Often missing — verify by deploying with no Juno data and confirming the dashboard explains what to expect
- [ ] **RSS feed health-check:** Often missing — verify the cron logs `bozo=1` warnings per-feed and surfaces them in `agent_runs.errors`
- [ ] **Sonnet refusal detector:** Often missing — verify by crafting a test prompt that triggers a refusal and confirming the agent marks the section as `partial` not `completed`
- [ ] **Regional feed quota documented:** Often missing — verify CONVENTIONS.md or the feed config file lists the regional balance and the rationale
- [ ] **Anthropic API key per tenant:** Often missing — verify `settings.anthropic_api_key_seva` and `settings.anthropic_api_key_juno` exist as separate env vars

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Cross-tenant data leak in production (Juno data appears on Seva dashboard) | HIGH | 1) Immediate rollback to v2.x. 2) Audit affected query/route. 3) Manually inspect what data leaked and to whom. 4) Add `company_id` filter + isolation test. 5) Re-deploy. 6) Post-incident: review every multi-tenant query in the codebase. |
| `company_id` migration fails mid-deploy (NULL rows from cron race) | MEDIUM | 1) Pause the affected cron via Railway dashboard. 2) Manually UPDATE `daily_summaries SET company_id='seva' WHERE company_id IS NULL`. 3) Re-run migration step 3 (ALTER COLUMN SET NOT NULL). 4) Resume cron. 5) Post-incident: ship the expand/contract migration pattern for any future tenant additions. |
| Sonnet refuses to summarize a defence story; daily card empty | LOW | 1) Operator runs the manual escape hatch `python -m scheduler.agents.juno_daily_summary` after editing the prompt. 2) If the refusal is persistent, the prompt needs revision — adjust the framing language. 3) Long-term: add the failing story to the calibration set so future prompt revisions are validated against it. |
| RSS feed silently goes dark; Juno card has 0 defence-industry stories | LOW | 1) Health-check alert (per pitfall §2.3) fires automatically — operator gets WhatsApp notification. 2) Operator runs SerpAPI discovery for the publisher to find the new feed URL. 3) Update the feed config + redeploy. 4) Backfill missed days via the manual cron escape hatch if needed. |
| AppHeader baseline invalidated by switcher addition (Path B not followed) | MEDIUM | 1) Re-run visual QA at 1440×900 with v2.1 baseline screenshots side-by-side. 2) Document the new baseline in CONVENTIONS.md (Path A retroactively). 3) If the diff is unacceptable, refactor to Path B (sibling component). |
| Lock ID collision between two crons (e.g., 1019 used by both seva_weekly_sweeper and juno_daily_summary) | HIGH | 1) OPS-02 assertion at module import time prevents production deploy — caught at CI/staging. 2) If somehow reached production: one job will silently skip every fire. Symptom: missing daily card. Fix: reassign lock ID per the block allocation rule, redeploy. |
| TanStack Query cache cross-contaminates on switcher fire | LOW | 1) Operator refreshes the page — cache is cleared by browser unload. 2) Hot-fix: add `queryClient.clear()` to the switcher action. 3) Add the missing key-factory entries. |

---

## Pitfall-to-Phase Mapping

| Pitfall | Severity | Prevention Phase | Verification |
|---------|----------|------------------|--------------|
| Async session ContextVar leak across requests | CRITICAL | Foundation | Parallel test run with multi-tenant fixtures; no leaks |
| Query without `company_id` filter | CRITICAL | Foundation | CI grep check for raw `select(MultiTenantModel)` outside repos returns zero |
| Backfill race during `company_id` migration | HIGH | Foundation (migration design) | CI test: cron + migration concurrent, no NULL rows |
| Missing composite index `(company_id, date)` | HIGH | Foundation (migration) | `EXPLAIN ANALYZE` confirms composite-index use |
| Cross-tenant FK pointer | MEDIUM | Foundation (model) | Application-layer assert in tests |
| Test fixtures don't reset tenant context | MEDIUM | Foundation (test scaffolding) | `pytest -n auto` passes consistently |
| Sonnet content-policy refusal on conflict-zone news | HIGH | News Funnel (Juno) | Test set of edge-case stories; no refusals |
| Sonnet false positives — consumer tech in defence card | HIGH | News Funnel (Juno) | Calibration set; precision ≥80% |
| RSS feed reorganization / silent feed death | HIGH | News Funnel (Juno) | Per-feed health-check + alert |
| Regional source bias (US-only) | MEDIUM | News Funnel (Juno) | Feed list audit per CONVENTIONS.md quota |
| Newsletter / opinion mixed with hard news | MEDIUM | News Funnel (Juno) | Feed classification tag + Sonnet hint |
| Daily summary boundary across timezones | MEDIUM | News Funnel (Juno) | Prompt timezone disclaimer; published_at injection |
| Lock ID collision (OPS-02 extension) | CRITICAL | Foundation (scheduler topology) | OPS-02 assertion at module import; per-tenant block allocation |
| Single cron iterating companies blocks tenants | HIGH | Foundation (scheduler topology) | Mock-slow-tenant test; concurrent execution proven |
| Idempotency: cron retry re-summarizes other tenant | HIGH | Foundation (scheduler) | Per-tenant idempotency pre-check |
| Anthropic rate limit across tenants | MEDIUM | News Funnel (Juno cron schedule) | Stagger ≥5 min; usage dashboard monitoring |
| Existing bookmarks to `/` break | CRITICAL | Foundation (routing) | Each old path navigates to expected new path |
| TanStack Query keys missing `company_id` | HIGH | Foundation (frontend state) | Key factory enforced; switcher behavior test |
| Login redirect drops company context | HIGH | Foundation (auth flow) | Bookmark to `/juno/calendar` after login lands correctly |
| Tab state leaks across company switches | MEDIUM | Foundation (frontend state) | Switch tenants; UI state resets |
| AppHeader freeze constraint conflict | HIGH | Foundation (decision before any header work) | Path A or Path B documented in CONVENTIONS.md |
| Existing tests assume single tenant | HIGH | Foundation (test scaffolding) + every feature phase | TODO comment count → zero; isolation tests cover all endpoints |
| MSW mocks lack `company_id` routing | MEDIUM | Foundation (frontend tests) | Switcher behavior test mocks both tenants |

---

## Sources

- v2.1 PITFALLS baseline (read directly): `.planning/milestones/v2.1-research/PITFALLS.md`
- v3.0 PROJECT.md current-milestone section (read directly)
- CLAUDE.md (v2.x stack, architecture, deployment patterns; read directly)
- PostgreSQL RLS / multi-tenant SaaS leak patterns: [Multi-Tenant Leakage: When Row-Level Security Fails in SaaS — InstaTunnel/Medium](https://medium.com/@instatunnel/multi-tenant-leakage-when-row-level-security-fails-in-saas-da25f40c788c)
- PostgreSQL RLS implementation guide (2026): [PostgreSQL Row-Level Security for Multi-Tenant SaaS — techbuddies.io](https://www.techbuddies.io/2026/01/01/how-to-implement-postgresql-row-level-security-for-multi-tenant-saas/)
- AWS RLS multi-tenant data isolation: [Multi-tenant data isolation with PostgreSQL Row Level Security — AWS](https://aws.amazon.com/blogs/database/multi-tenant-data-isolation-with-postgresql-row-level-security/)
- Crunchy Data RLS for tenants in Postgres (composite indexes + SET LOCAL guidance): [Row Level Security for Tenants in Postgres — Crunchy Data](https://www.crunchydata.com/blog/row-level-security-for-tenants-in-postgres)
- FastAPI multi-tenancy with SQLAlchemy + Postgres RLS pattern (ContextVar discipline): [Python FastAPI Postgres SqlAlchemy RLS Multitenancy — adityamattos.com](https://adityamattos.com/multi-tenancy-in-python-fastapi-and-sqlalchemy-using-postgres-row-level-security)
- FastAPI multi-tenancy discussion (community patterns + pitfalls): [FastAPI Multi Tenancy Discussion #6056](https://github.com/fastapi/fastapi/discussions/6056)
- Anthropic-Pentagon dispute (content-policy guardrails on defence applications): [Anthropic–U.S. Department of Defense dispute — Wikipedia](https://en.wikipedia.org/wiki/Anthropic%E2%80%93United_States_Department_of_Defense_dispute)
- Anthropic-Pentagon timeline: [A Timeline of the Anthropic-Pentagon Dispute — TechPolicy.Press](https://www.techpolicy.press/a-timeline-of-the-anthropic-pentagon-dispute/)
- Defence dual-use tech surge (Chatham House): [How a surge in defence and dual-use technology investment could reconfigure the global AI race — Chatham House](https://www.chathamhouse.org/2026/04/how-surge-defence-and-dual-use-technology-investment-could-reconfigure-global-ai-race/02)
- Janes defence news current feed location: [Janes — Latest defence and security news](https://www.janes.com/osint-insights/defence-news)
- Defense News RSS feed inventory (multiple sections): [Defense News RSS Feeds](https://www.defensenews.com/m/rss/)
- Top defense RSS feeds aggregator (publisher discovery): [Top 60 Defense RSS Feeds — FeedSpot](https://rss.feedspot.com/defense_rss_feeds/)
- TanStack Query QueryClient docs (cache scoping by key): [QueryClient — TanStack Query](https://tanstack.com/query/latest/docs/reference/QueryClient)
- TanStack Query invalidation (cache leak prevention): [Query Invalidation — TanStack Query](https://tanstack.com/query/v5/docs/framework/react/guides/query-invalidation)
- Alembic safe migration patterns (expand/contract for column add): [How we make database schema migrations safe and robust — Defacto](https://www.getdefacto.com/article/database-schema-migrations)
- Alembic migration handling data in race conditions: [Handling Data in Alembic Migrations When Schema Changes Aren't Enough — hevalhazalkurt](https://hevalhazalkurt.com/blog/handling-data-in-alembic-migrations-when-schema-changes-arent-enough/)

---

*Pitfalls research for: v3.0 Multi-Tenant Pivot + Defence-Sector Ingestion*
*Researched: 2026-05-19*
*Note: This file ONLY documents v3.0-specific pitfalls. Generic engineering pitfalls (async/sync, timeouts, JSONB None guards, secret logging) inherit from `v2.1-research/PITFALLS.md` and are NOT repeated.*
