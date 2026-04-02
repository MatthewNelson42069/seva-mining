# Phase 6: Instagram Agent - Context

**Gathered:** 2026-04-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the Instagram Agent: a scheduled APScheduler job that scrapes gold-sector Instagram posts via the Apify `instagram-scraper` actor (hashtags + watchlist account profiles), applies an engagement gate and composite scoring, drafts 2-3 comment alternatives per qualifying post with a separate compliance checker, handles scraper health monitoring with silent-failure detection, and passes all qualifying drafts to the Senior Agent.

This phase does NOT include: dashboard display changes, Settings page wiring, Instagram content for the Content Agent, or any changes to the approval dashboard. Those are Phases 8–9.

The `instagram_agent` job slot is already registered in `scheduler/worker.py` (lock ID 1002, every 4 hours) — Phase 6 replaces the placeholder with the real implementation.

</domain>

<decisions>
## Implementation Decisions

### Apify Scraper Configuration

- **Actor:** `apify/instagram-scraper` (already specified in CLAUDE.md tech stack)
- **Scraping mode:** Parallel — hashtag scraping and account profile scraping run concurrently via `asyncio.gather`. Mirrors Twitter Agent pattern for fetch_watchlist + fetch_keywords.
- **Lookback per run:** 24 hours (fetch last 24h of posts per hashtag/account). The 8-hour engagement gate (INST-03) is applied as a post-fetch filter — fetching 24h catches posts that recently crossed the engagement gate even if posted earlier.
- **Posts per hashtag:** 50 per run (configurable via `instagram_max_posts_per_hashtag` in config table, default `"50"`)
- **Posts per account:** 10 per run (configurable via `instagram_max_posts_per_account` in config table, default `"10"`)
- **Deduplication within run:** Deduplicate by `shortCode` (Apify's unique post identifier) before scoring — the same post can appear in both a hashtag scrape and a profile scrape.

### Hashtag Seed List

10 gold-sector Instagram hashtags seeded on first run:
```
#gold, #goldmining, #preciousmetals, #goldprice, #bullion,
#juniorminers, #goldstocks, #goldsilver, #goldnugget, #mininglife
```

Stored in the `keywords` table with `platform='instagram'`. Configurable — add/remove via Settings page in Phase 8.

### Instagram Watchlist Seed

Best-effort mapping of all 25 Twitter watchlist entities to their Instagram handles. The researcher must look up actual Instagram handles for each entity. Rules:
- If a clear, active Instagram account exists for the entity → seed it
- If Instagram account is inactive, private, or doesn't exist → skip it (do not seed a dead account)
- Seed with `relationship_value=5` (max priority, matching Twitter seed)
- Platform: `'instagram'`

Reference the 25 Twitter entities in `scheduler/seed_twitter_data.py` as the source list to map from.

### Engagement Gate and Scoring

**Engagement gate (INST-03):** 200+ likes AND post created within last 8 hours. Applies to ALL accounts — no lower watchlist gate (Instagram watchlist accounts do not get a reduced threshold).

**Scoring formula (INST-02):**
```
score = (likes × 1) + (comment_count × 2) + (normalized_follower_count × 1.5)
```

**Follower count normalization:** Log scale capped at 1M followers:
```python
import math
def normalize_followers(n: int) -> float:
    if n <= 0:
        return 0.0
    return min(math.log10(max(n, 1)) / math.log10(1_000_000), 1.0)
```
- 1k followers → ~0.33
- 100k followers → ~0.67
- 1M+ followers → 1.0

**Top N per run:** Top 3 qualifying posts by score (INST-04). Configurable via `instagram_top_n` in config table (default `"3"`).

### Draft Style (INST-05, INST-06, INST-07)

- **Format:** 2-3 comment alternatives per qualifying post, 1-2 sentences each
- **Angle:** Data point or insight first — lead with a specific fact, stat, or market context that adds to the conversation. Senior analyst voice, same as Twitter drafts. Every comment should make a gold-focused reader stop and think.
- **Hard rule:** No hashtags in any drafted comment, ever (INST-06). Compliance checker AND drafting prompt both enforce this.
- **Two-Claude pattern:** Sonnet for drafting, Haiku for compliance check (same as Phase 4)
- **Fail-safe compliance:** Ambiguous LLM response = block (not pass)

### Scraper Health Monitoring (INST-10, INST-11)

**Silent failure detection (INST-10):**
- After each run, store per-hashtag result counts in `AgentRun.notes` (JSONB)
- Maintain a rolling 7-run average per hashtag using the last 7 `agent_runs` records for `instagram_agent`
- If any hashtag returns < 20% of its rolling average, log a health event in `AgentRun.errors` with tag `health_warning`
- **Baseline establishment:** Health checks are skipped for the first 3 runs (no baseline yet). After run 3, the rolling average is active. Configurable via `instagram_health_baseline_runs` (default `"3"`).

**Critical failure WhatsApp alert (INST-11):**
- Trigger: 2+ consecutive runs where ALL hashtags return zero results
- Uses existing `breaking_news` WhatsApp template (same SID as Phase 5): `{{1}}` = "Instagram scraper failure", `{{2}}` = "instagram_agent", `{{3}}` = consecutive failure count, `{{4}}` = dashboard URL
- Single alert per failure episode (dedup by checking last run's failure state before sending)
- After recovery (non-zero results), reset the consecutive-failure counter

### Retry Logic (INST-09)

- On Apify API error: retry up to 2 times with exponential backoff (1s, 2s)
- Use `asyncio.sleep` between retries
- After 3 total failures for a source: log error to `AgentRun.errors`, skip that hashtag/account for this run (do not abort the entire run)
- Match pattern from Phase 2 WhatsApp retry logic (retry-once with logging)

### Expiry

- `expires_at = created_at + 12 hours` (INST-12), set when writing DraftItem
- `platform = 'instagram'` on DraftItem

### Senior Agent Integration

- Call `process_new_items(new_item_ids)` after committing DraftItems — same lazy import pattern as `TwitterAgent._run_pipeline()`
- Senior Agent handles: deduplication, queue cap, breaking news alert

### Claude's Discretion

- Exact `asyncio.gather` structure for parallel Apify calls
- Apify actor input schema field names (researcher must confirm exact field names from Apify docs — `likesCount`, `commentsCount`, `ownerFollowersCount`, `timestamp`, `shortCode`, `ownerUsername`, `caption` are expected but verify)
- Config key naming convention (follow `instagram_*` prefix pattern)
- Error handling for zero-result runs that don't trigger health event (normal quiet run vs failure)
- `AgentRun.notes` JSONB structure for storing per-hashtag result counts

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Specification
- `.planning/REQUIREMENTS.md` §Instagram Agent — INST-01 through INST-12
- `.planning/ROADMAP.md` §Phase 6 — Goal, success criteria, dependency context

### Existing Code to Mirror
- `scheduler/agents/twitter_agent.py` — Full reference implementation for agent structure: `AsyncSessionLocal`, `AgentRun` logging, error isolation, `_get_config()`, `_load_watchlist()`, `_load_keywords()`, dual-Claude pattern (Sonnet draft + Haiku compliance), `process_new_items()` integration
- `scheduler/worker.py` — `instagram_agent` job slot already registered at lock ID 1002, every 4 hours; `_make_job` pattern for wiring

### Seed Data Reference
- `scheduler/seed_twitter_data.py` — The 25 Twitter watchlist entities that the Instagram watchlist seed should map to their IG counterparts

### WhatsApp Service
- `scheduler/services/whatsapp.py` — Mirror created in Phase 5; use directly for critical failure alerts

### Stack Decisions
- `CLAUDE.md` §Technology Stack — `apify-client 2.5.0`, `ApifyClientAsync`, `asyncio.to_thread` for sync SDK calls, APScheduler 3.11.2

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scheduler/agents/twitter_agent.py` — `_get_config()`, `_load_watchlist()`, `_load_keywords()`, `_check_compliance()`, `AgentRun` logging pattern all directly reusable
- `scheduler/services/whatsapp.py` — WhatsApp send available immediately (created Phase 5)
- `scheduler/models/draft_item.py` — `platform`, `expires_at`, `engagement_snapshot` JSONB, `engagement_alert_level` all available
- `scheduler/models/watchlist.py` — `platform` field distinguishes `'twitter'` vs `'instagram'` accounts
- `scheduler/models/keyword.py` — `platform` field for `'instagram'` hashtags
- `scheduler/agents/senior_agent.py` — `process_new_items()` module-level function ready to call

### Established Patterns
- Agent structure: `class InstagramAgent` → `run()` → `_run_pipeline()` → fetch + filter + score + draft + persist
- Config: `_get_config(session, key, default)` reads from `Config` table — use for all thresholds
- AgentRun logging: create at start, set `status='completed'/'failed'`, always commit in `finally`
- Error isolation: catch all exceptions in job body, log to `AgentRun.errors`, never re-raise (EXEC-04)
- `engagement_snapshot` JSONB: store raw metrics at capture time `{likes, comments, follower_count, captured_at}`

### Integration Points
- `worker.py` `instagram_agent` placeholder → wire to `InstagramAgent().run()`
- `process_new_items()` → call after DraftItem commit
- `scheduler/services/whatsapp.py` → call for critical failure alert (INST-11)

</code_context>

<specifics>
## Specific Decisions

- Hashtag seed list: 10 tags — #gold #goldmining #preciousmetals #goldprice #bullion #juniorminers #goldstocks #goldsilver #goldnugget #mininglife
- Follower normalization: `min(log10(max(n,1)) / log10(1_000_000), 1.0)` — not tiered, not linear
- Health baseline: 7-run rolling average; first 3 runs have no health checks
- Critical failure alert: 2 consecutive all-zero runs → WhatsApp via `breaking_news` template
- Comment style: data point / insight first — not question-based, not mixed
- Lookback: fetch 24h per run, filter to 8h for engagement gate

</specifics>

<deferred>
## Deferred Ideas

- Watchlist engagement gate reduction (lower threshold for watchlist accounts, like Twitter's 50 likes): user declined to discuss — standard 200-like gate applies to all. Could be added post-launch if watchlist accounts produce too little content.
- Apify retry count configurability: retry-twice with 1s/2s backoff is fixed in code for Phase 6. Configurable retry logic deferred to Phase 9 (agent execution polish).
- Instagram Stories / Reels scraping: the `instagram-scraper` actor can scrape Reels — out of scope for Phase 6, which focuses on feed posts only.

</deferred>

---
*Phase: 06-instagram-agent*
*Context gathered: 2026-04-02*
