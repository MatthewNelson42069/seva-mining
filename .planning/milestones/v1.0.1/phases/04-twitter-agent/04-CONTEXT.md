# Phase 4: Twitter Agent - Context

**Gathered:** 2026-04-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the Twitter Agent: a scheduled worker that runs every 2 hours, fetches qualifying gold-sector posts via X API v2, applies engagement + authority + relevance scoring with recency decay, drafts both a reply AND a retweet-with-comment (2-3 alternatives each) for each qualifying post, runs a separate compliance checker call on every draft, tracks monthly quota consumption with hard-stop logic, and delivers approved drafts to the dashboard queue.

This phase does NOT include: Senior Agent queue management, deduplication across platforms, WhatsApp notifications, or Instagram/Content agents. Those are Phases 5–7.

</domain>

<decisions>
## Implementation Decisions

### Watchlist Accounts (Seed Data)

All 25 accounts seeded with `relationship_value = 5` (maximum priority) and `platform = 'twitter'`. Exact handles to verify against live X profiles at seed time.

**Media / News (5 accounts):**
- `@KitcoNews` — Kitco News, the definitive gold price and market news outlet
- `@WGCouncil` — World Gold Council, official industry body (demand data, ETF flows, central bank reserves)
- `@BullionVault` — BullionVault, gold price platform with regular market commentary
- `@Reuters` — Reuters (when covering gold/commodities)
- `@BloombergMkts` — Bloomberg Markets (when covering gold/commodities)

**Analysts & Commentators (10 accounts):**
- `@PeterSchiff` — Peter Schiff, CEO Euro Pacific Capital. Prolific gold bull, posts multiple times daily
- `@JimRickards` — Jim Rickards, author, gold standard advocate, macro analysis
- `@GoldSeekCom` — GoldSeek, gold news aggregator covering juniors and majors
- `@RealVision` — Real Vision Finance, macro/gold commentary from institutional voices
- `@TaviCosta` — Tavi Costa, macro analyst with strong gold thesis
- `@Mike_maloney` — Mike Maloney, gold/silver investor and educator
- `@MacleodFinance` — Alasdair Macleod, gold and monetary theory analysis
- `@DanielaCambone` — Daniela Cambone, gold/mining journalist (formerly Kitco)
- `@RonStoeferle` — Ronald Stoeferle, In Gold We Trust report author
- `@Frank_Giustra` — Frank Giustra, mining financier and gold sector veteran

**Mining Majors (6 accounts):**
- `@Newmont` — Newmont, world's largest gold miner
- `@Barrick` — Barrick Gold
- `@AgnicoEagle` — Agnico Eagle
- `@KinrossGold` — Kinross Gold
- `@FrancoNevada` — Franco-Nevada (streaming/royalty)
- `@WheatonPrecious` — Wheaton Precious Metals (streaming/royalty)

**ETFs / Funds (2 accounts):**
- `@SPDR_ETFs` — SPDR (GLD, the benchmark gold ETF)
- `@VanEck` — VanEck (GDX/GDXJ gold miner ETFs)

**Gold Media / Community (2 accounts):**
- `@GoldTelegraph_` — Gold Telegraph, gold sector news and commentary
- `@WSBGold` — WSBGold, retail gold community with high engagement

### Engagement Gates (Updated — replaces TWIT-04)

Two separate thresholds:

**Watchlist accounts:** 50+ likes **AND** 5,000+ views (both conditions required). Reflects trusted-voice status — doesn't need to go viral to be worth engaging with.

**Non-watchlist accounts (keyword/cashtag/hashtag search):** 500+ likes **AND** 40,000+ views (both conditions required). Strictly qualified posts only from unknown accounts.

Note: This replaces the original TWIT-04 spec of "500+ likes OR watchlist account 50+ likes." The new rule adds a view count gate and makes both conditions required (AND not OR).

### Topic Filter for Watchlist Accounts

Watchlist accounts are monitored specifically, but their tweets must be gold-related to be processed. Two-step filter:

1. **Keyword presence check (free, fast):** Tweet must contain at least one gold-related term — including but not limited to: `gold`, `$GLD`, `$GC`, `bullion`, `precious metals`, `#goldmining`, `#gold`, `central bank`, `gold reserve`, `gold price`, `Au`, `troy ounce`, `junior miners`, `mining stock`. If found → proceed to scoring.
2. **Claude topic classification fallback (for borderline cases):** If a watchlist tweet doesn't hit a keyword but the context might be gold-related (e.g. discussing Fed policy without mentioning gold explicitly), a brief Claude call confirms: "Is this tweet substantively about gold, precious metals, or gold mining? Yes/No." Applied sparingly — only when keyword check is inconclusive.

Non-watchlist keyword-search results are inherently gold-related by search construction and do not need this filter.

### Trending Non-Watchlist Tweets

Highly trending gold tweets from non-watchlist accounts surface via the standard keyword/cashtag/hashtag search path. Threshold: 500+ likes **AND** 40,000+ views — same gate as all non-watchlist posts. No special "trending" path needed — the combined engagement gate naturally surfaces viral content.

### Draft Format and Compliance

Per TWIT-07/08/09/10 (no changes):
- Each qualifying post generates: one reply draft AND one retweet-with-comment draft
- Each draft type produces 2-3 alternatives
- Drafts written in senior analyst voice — data-driven, measured, cites specifics
- **Separate compliance checker Claude call** (not the drafting prompt): validates no Seva Mining mention and no financial advice in every individual alternative
- Compliance failure behavior: drop only that alternative, log the failure in `agent_runs.errors`, keep remaining alternatives. If ALL alternatives for a draft type fail compliance, skip that post entirely and log it.

### Quota Counter

Per TWIT-11/12 (no changes):
- Monthly tweet read counter stored in the database (config/settings table or `agent_runs` metadata)
- Hard-stop at configurable safety margin before 10,000/month cap
- Counter resets on the first of each calendar month (not API billing cycle)
- Dashboard displays current consumption (wired in Phase 8 Settings page)

### Keyword / Cashtag / Hashtag Seed List

Claude's discretion — seed with a comprehensive initial list covering:
- Cashtags: `$GLD`, `$GC`, `$GOLD`, `$GDX`, `$GDXJ`, `$NEM`, `$GOLD` (Barrick ticker)
- Hashtags: `#gold`, `#goldmining`, `#preciousmetals`, `#goldprice`, `#bullion`, `#juniorminers`, `#mining`
- Keywords: `"gold price"`, `"central bank gold"`, `"gold reserves"`, `"gold ETF"`, `"gold exploration"`, `"junior miners"`, `"gold standard"`, `"gold rally"`, `"gold outlook"`
All stored in the `keywords` table with `platform = 'twitter'` and `active = true`. User can adjust via Settings.

### Codebase Integration Points

- **Agent location:** `backend/app/agents/twitter_agent.py` — new module, called by APScheduler job
- **APScheduler registration:** Placeholder job already exists in the scheduler worker skeleton (Phase 1). Wire to the actual `TwitterAgent.run()` function.
- **Database writes:** Use existing `DraftItem` model (all fields already present). Set `platform = 'twitter'`, `expires_at = now() + 6h`.
- **Run logging:** Use existing `AgentRun` model — create run record at start, update `items_found`, `items_queued`, `items_filtered`, `errors` on completion.
- **Watchlist reads:** Use existing `Watchlist` model with `platform = 'twitter'` filter.
- **Keyword reads:** Use existing `Keyword` model with `platform = 'twitter'` or `platform = null` (all-platform keywords).
- **LLM calls:** `AsyncAnthropic` — consistent with all other LLM patterns in the codebase.

### Claude's Discretion

- Exact keyword seed list curation (add/remove terms within the gold sector domain)
- Tweepy v2 API call structure: whether to use `search_recent_tweets` vs streaming (Basic tier is polling only — use `search_recent_tweets`)
- Topic classification prompt wording for the Claude fallback filter
- Quota counter storage: new `config` DB table vs `agent_runs` metadata vs environment variable
- Drafting prompt structure and system prompt wording (within senior analyst voice constraint)
- Error retry logic for X API rate limit responses (429)
- Exact compliance checker prompt wording
- Whether to batch API calls or process accounts individually for efficiency within X Basic API rate limits

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Specification
- `.planning/REQUIREMENTS.md` §Twitter Agent — TWIT-01 through TWIT-14 (full requirement list)
- `.planning/ROADMAP.md` §Phase 4 — Success criteria and dependency context

### Existing Models (all fields already deployed to Neon)
- `backend/app/models/draft_item.py` — DraftItem schema (platform, score, quality_score, alternatives JSONB, rationale, urgency, related_id, expires_at, engagement_snapshot, event_mode)
- `backend/app/models/watchlist.py` — Watchlist schema (platform, account_handle, relationship_value 1-5, notes, active)
- `backend/app/models/keyword.py` — Keyword schema (term, platform, weight, active)
- `backend/app/models/agent_run.py` — AgentRun schema (agent_name, started_at, ended_at, items_found, items_queued, items_filtered, errors JSONB, status)

### Stack Decisions
- `CLAUDE.md` §Technology Stack — Tweepy 4.x Client (v2 not legacy), AsyncAnthropic, APScheduler 3.11.2 AsyncIOScheduler
- `CLAUDE.md` §What NOT to Use — avoid requests library, avoid APScheduler 4.x, avoid auto-posting

### Project Non-Negotiables
- `backend/.env` — X API credentials: `X_API_BEARER_TOKEN`, `X_API_KEY`, `X_API_SECRET`
- `.planning/PROJECT.md` §Context — "Seva Mining is never mentioned in any drafted reply, comment, or retweet. Not once, not subtly, not ever." and "No financial advice" — enforced by compliance checker

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `DraftItem` model: fully ready, all Twitter Agent fields present including `engagement_snapshot` (JSONB) for storing raw likes/retweets/replies at capture time, `event_mode` for future v1.x event mode, `expires_at` for the 6h expiry
- `AgentRun` model: fully ready for run logging
- `Watchlist` model: has `relationship_value` (1-5) column ready for priority scoring
- `Keyword` model: `weight` column available for keyword relevance scoring
- `app/database.py`: async session factory already configured — agent just needs to import and use it
- `app/config.py`: pydantic-settings already loads `X_API_BEARER_TOKEN`, `X_API_KEY`, `X_API_SECRET` from environment

### Established Patterns
- All DB operations: `async with AsyncSession` with `async_sessionmaker` — match this pattern in agent
- All LLM calls: `AsyncAnthropic` client — use same pattern
- Error handling: wrap agent body in try/except, log to `AgentRun.errors` JSONB array, set `status = 'failed'` but don't raise (scheduler must keep running)

### Integration Points
- APScheduler worker skeleton: placeholder Twitter job registered — replace with `await twitter_agent.run()`
- Senior Agent (Phase 5): Twitter Agent delivers `DraftItem` records to the DB. Senior Agent reads them from DB — no direct inter-agent calls needed. Clean separation.

</code_context>

<specifics>
## Specific Ideas

- User explicitly wants: "if there is highly trending tweets about gold that are not from these accounts, those should be mentioned as well" — covered by the standard keyword search path with 500+ likes + 40k views gate
- User explicitly wants: "The tweets from any of these accounts have to be about gold" — covered by the two-step topic filter (keyword presence + Claude fallback)
- All watchlist accounts seeded at `relationship_value = 5` — user wants maximum priority for all of them, will adjust via Settings if needed

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---
*Phase: 04-twitter-agent*
*Context gathered: 2026-04-01*
