# Phase 4: Twitter Agent - Research

**Researched:** 2026-04-01
**Domain:** X API v2, Tweepy AsyncClient, AsyncAnthropic, APScheduler job wiring, PostgreSQL quota storage
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **Watchlist Accounts:** 25 accounts seeded at `relationship_value = 5` (full list in CONTEXT.md). Exact handles verified at seed time.
- **Engagement Gates:**
  - Watchlist accounts: 50+ likes AND 5,000+ views (both conditions required)
  - Non-watchlist keyword/cashtag/hashtag search: 500+ likes AND 40,000+ views (both conditions required)
  - This replaces the original TWIT-04 spec ("500+ likes OR watchlist 50+ likes"). The new rule adds a view gate and makes both conditions AND not OR.
- **Topic Filter for Watchlist Accounts:** Two-step filter: (1) keyword presence check (gold-related terms list), (2) Claude topic classification fallback for borderline cases only.
- **Draft Format:** Each qualifying post generates one reply draft AND one retweet-with-comment draft, each with 2-3 alternatives, in senior analyst voice with rationale.
- **Compliance Checker:** Separate Claude call per alternative (not the drafting prompt). Blocks Seva Mining mentions and financial advice. Drop failing alternative, keep passing ones. If ALL alternatives fail for a draft type, skip post and log it.
- **Quota Counter:** Monthly tweet read counter in DB. Hard-stop at configurable safety margin before 10,000/month cap. Resets first of each calendar month (not billing cycle). Dashboard display wired in Phase 8.
- **Agent Location:** `scheduler/agents/twitter_agent.py` — new module, called by APScheduler job.
- **APScheduler Wiring:** Placeholder `twitter_agent` job already in `scheduler/worker.py`. Replace `lambda: placeholder_job("twitter_agent")` with `await twitter_agent.run()`.
- **Database Writes:** Use existing `DraftItem` model. Set `platform = 'twitter'`, `expires_at = now() + 6h`.
- **Run Logging:** Use existing `AgentRun` model.
- **LLM Calls:** `AsyncAnthropic` — consistent with all other LLM patterns in codebase.
- **Tweepy Version:** Tweepy 4.x `Client` (v2 not legacy). Basic tier is polling only — use `search_recent_tweets`, not streaming.

### Claude's Discretion

- Exact keyword seed list curation (add/remove terms within gold sector domain)
- Tweepy v2 API call structure: `search_recent_tweets` vs streaming (Basic tier is polling only — use `search_recent_tweets`)
- Topic classification prompt wording for the Claude fallback filter
- Quota counter storage: new `config` DB table vs `agent_runs` metadata vs environment variable
- Drafting prompt structure and system prompt wording (within senior analyst voice constraint)
- Error retry logic for X API rate limit responses (429)
- Exact compliance checker prompt wording
- Whether to batch API calls or process accounts individually for efficiency within X Basic API rate limits

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TWIT-01 | Agent monitors X via Basic API using configurable cashtags, hashtags, and keywords every 2 hours | Tweepy AsyncClient `search_recent_tweets`; APScheduler job wiring |
| TWIT-02 | Agent scores posts on engagement (40%), account authority (30%), and topic relevance (30%) | Scoring formula pattern; public_metrics access confirmed |
| TWIT-03 | Engagement formula: likes x1 + retweets x2 + replies x1.5 | `public_metrics` fields: like_count, retweet_count, reply_count |
| TWIT-04 | Minimum engagement gate (updated): watchlist 50+ likes AND 5k+ views; non-watchlist 500+ likes AND 40k+ views | `public_metrics.impression_count` confirmed available for non-owned tweets on Basic tier |
| TWIT-05 | Recency decay: full score under 1h, 50% at 4h, expired at 6h | `created_at` tweet field; datetime math pattern |
| TWIT-06 | Top 3-5 qualifying posts per run passed to drafting | Sort by composite score after decay; slice top N |
| TWIT-07 | Drafts both a reply comment AND a retweet-with-comment for each qualifying post | Two separate Claude calls per post (or one structured prompt) |
| TWIT-08 | Produces 2-3 alternative drafts per response type | Prompt instructs Claude to return JSON array of alternatives |
| TWIT-09 | Each draft evaluated against quality rubric (relevance, originality, tone match, no company mention, no financial advice) | Compliance checker Claude call pattern |
| TWIT-10 | Separate Claude compliance-checker call validates no Seva Mining mention and no financial advice | Separate Claude call, not the drafting prompt |
| TWIT-11 | Monthly X API quota counter tracks tweet reads against 10,000/month cap | Counter stored in DB (config table recommended); incremented per tweet read |
| TWIT-12 | Hard-stop logic prevents API calls when quota approaches limit | Check counter at agent run start; configurable safety margin |
| TWIT-13 | Dashboard displays current quota usage and alerts when quota is low | Counter readable from DB; frontend wired in Phase 8 |
| TWIT-14 | All drafts sent to Senior Agent with rationale explaining why this post matters and what angle the draft takes | `DraftItem.rationale` field already present; write as part of draft output |
</phase_requirements>

---

## Summary

Phase 4 adds the Twitter Agent: a pure Python module in `scheduler/agents/twitter_agent.py` that is invoked by the already-wired APScheduler placeholder job every 2 hours. The agent fetches qualifying gold-sector tweets via Tweepy's `AsyncClient.search_recent_tweets` (for keyword/cashtag/hashtag searches) and `get_users_tweets` (for watchlist account monitoring), applies engagement + authority + relevance scoring with recency decay, then passes the top 3-5 qualifying posts through two separate Claude call chains — one for drafting (reply + retweet-with-comment, 2-3 alternatives each) and one for compliance checking each alternative individually. Approved alternatives are written as `DraftItem` records to the Neon database. Monthly quota consumption is tracked in a new `config` table (one row per setting) and checked at run start with a hard-stop guard.

The critical pre-research finding is that `impression_count` is included in `public_metrics` and IS accessible for non-owned tweets on the Basic tier via `search_recent_tweets` — the view gate (5,000+ for watchlist, 40,000+ for non-watchlist) is therefore implementable without elevated API access. The second key finding: `tweepy.asynchronous.AsyncClient` exists in Tweepy 4.10+ and supports `await` natively, making it a clean fit for the scheduler's async event loop without `asyncio.to_thread` wrapping.

The main risk is the 10,000 tweet/month Basic tier quota. At 12 runs/day x 30 days = 360 runs/month, the agent must fetch conservatively: approximately 27 tweets per run maximum before hitting the quota ceiling. With the configured safety margin, the hard-stop threshold should be set at ~8,500 tweets consumed (leaving 1,500 buffer). The agent design must count every tweet returned by the API (not just those that pass the engagement gate) toward the quota counter.

**Primary recommendation:** Use `tweepy.asynchronous.AsyncClient` for all X API calls, store quota in a new `config` DB table (key-value pairs), and structure the agent as a single class with clearly separated pipeline stages: fetch, filter, score, draft, compliance-check, persist.

---

## Standard Stack

### Core (this phase adds to scheduler)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| tweepy | 4.14.x | X API v2 client | Locked in CLAUDE.md. `AsyncClient` subclass supports async/await natively from v4.10+. |
| anthropic | 0.86.0 | Claude API SDK | Already used in project. `AsyncAnthropic` for drafting and compliance calls. |

Both packages must be added to `scheduler/pyproject.toml` dependencies. They are not currently in the scheduler's `uv.lock`.

**Version verification:**
```bash
# Confirm current tweepy version
pip index versions tweepy 2>/dev/null | head -1
# Confirmed in docs: tweepy 4.14.0 is latest stable as of research date
# anthropic 0.86.0 already confirmed in CLAUDE.md
```

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| sqlalchemy asyncio | 2.0.x | Async DB writes | Already in scheduler. Use `AsyncSessionLocal` from `scheduler/database.py`. |
| pydantic-settings | 2.x | Settings access | Already in scheduler. `get_settings()` from `scheduler/config.py`. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| tweepy AsyncClient | httpx direct to X API | Only if Tweepy is missing an endpoint. For Basic read-only polling, Tweepy covers all needed endpoints. |
| AsyncAnthropic calls | Sync Anthropic + asyncio.to_thread | Sync+thread wrapping is the existing Twilio pattern in the codebase, but AsyncAnthropic is cleaner and is explicitly the project standard. |

**Installation (add to scheduler/pyproject.toml dependencies):**
```
tweepy>=4.14
anthropic>=0.86.0
```
Then run: `uv sync` from the `scheduler/` directory.

---

## Architecture Patterns

### Recommended Project Structure

```
scheduler/
├── agents/
│   ├── __init__.py         # Already exists (empty placeholder)
│   └── twitter_agent.py    # NEW: TwitterAgent class (this phase)
├── worker.py               # MODIFY: wire TwitterAgent.run() into _make_job("twitter_agent")
├── config.py               # READ-ONLY: already loads X_API_BEARER_TOKEN etc.
├── database.py             # READ-ONLY: AsyncSessionLocal already configured
└── pyproject.toml          # MODIFY: add tweepy + anthropic deps
```

No new directories needed. No migrations needed (config table added via Alembic in Wave 0 or Wave 1).

### Pattern 1: TwitterAgent Class Structure

**What:** A single class `TwitterAgent` with a `run()` async method. Each pipeline stage is a private async method. The class receives settings and DB session factory at init.

**When to use:** Any agent in this codebase — matches the scheduler isolation pattern where each agent is self-contained.

```python
# scheduler/agents/twitter_agent.py
from anthropic import AsyncAnthropic
import tweepy.asynchronous
from sqlalchemy.ext.asyncio import AsyncSession
from database import AsyncSessionLocal
from config import get_settings


class TwitterAgent:
    def __init__(self):
        settings = get_settings()
        self.tweepy_client = tweepy.asynchronous.AsyncClient(
            bearer_token=settings.x_api_bearer_token,
            wait_on_rate_limit=False,  # We handle 429 manually with hard-stop logic
        )
        self.anthropic = AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def run(self) -> None:
        """Entry point called by APScheduler job."""
        async with AsyncSessionLocal() as session:
            # 1. Check quota — hard-stop if over safety margin
            # 2. Load watchlist + keywords from DB
            # 3. Fetch watchlist account tweets
            # 4. Fetch keyword/cashtag/hashtag search results
            # 5. Increment quota counter for every tweet read
            # 6. Filter by engagement gates + topic filter
            # 7. Score (engagement 40% + authority 30% + relevance 30%) with recency decay
            # 8. Take top 3-5 qualifying posts
            # 9. For each: draft (reply + RT-with-comment) via Claude
            # 10. Compliance-check each alternative via separate Claude call
            # 11. Persist passing DraftItem records
            # 12. Update AgentRun log
            ...
```

### Pattern 2: APScheduler Wiring — Replace Placeholder

The `worker.py` `_make_job("twitter_agent", engine)` function currently passes `lambda: placeholder_job("twitter_agent")` to `with_advisory_lock`. Replace this with the actual agent:

```python
# scheduler/worker.py — in _make_job, change the twitter_agent branch:
from agents.twitter_agent import TwitterAgent

def _make_job(job_name: str, engine):
    async def job():
        async with engine.connect() as conn:
            if job_name == "twitter_agent":
                agent = TwitterAgent()
                await with_advisory_lock(conn, JOB_LOCK_IDS[job_name], job_name, agent.run)
            else:
                await with_advisory_lock(conn, JOB_LOCK_IDS[job_name], job_name,
                                         lambda: placeholder_job(job_name))
    return job
```

Alternatively — and more cleanly — make `_make_job` generic and pass the coroutine function as a parameter from `build_scheduler`. Either approach works. The advisory lock wrapper already handles failures without re-raising (EXEC-04).

### Pattern 3: Quota Storage — Config Table

Use a dedicated `config` table (key-value store) for the monthly quota counter. This is cleaner than stuffing it into `agent_runs` metadata because the counter persists across runs and needs to be read at run start and displayed in the dashboard.

Schema for the new `config` table (Alembic migration needed):
```sql
CREATE TABLE config (
    key VARCHAR(100) PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Keys used by Twitter Agent:
- `twitter_monthly_tweet_count` — integer string, reset to "0" on first run of each calendar month
- `twitter_monthly_reset_date` — ISO date string, e.g. "2026-04-01", marks which month the counter belongs to
- `twitter_quota_safety_margin` — integer string, default "1500" (hard-stop at 10000 - 1500 = 8500)

Read at agent run start. If `reset_date` month != current month, reset counter to 0 and update `reset_date` in the same DB transaction.

### Pattern 4: Tweepy AsyncClient Search

```python
# Keyword/cashtag/hashtag search — single query string
query = "(gold OR $GLD OR $GC OR #goldmining) -is:retweet lang:en"

response = await self.tweepy_client.search_recent_tweets(
    query=query,
    max_results=100,  # Max per page — reduces API calls
    tweet_fields=["created_at", "public_metrics", "author_id", "text"],
    expansions=["author_id"],
    user_fields=["username", "public_metrics", "verified"],
    # start_time = now - 2h to only fetch new tweets since last run
)
# Every tweet in response.data counts against the monthly quota
```

```python
# Watchlist account timeline fetch
response = await self.tweepy_client.get_users_tweets(
    id=user_id,  # Resolved Twitter user ID (not handle)
    max_results=10,  # Recent tweets only
    tweet_fields=["created_at", "public_metrics", "text"],
    start_time=two_hours_ago,
)
```

Note: `get_users_tweets` requires the numeric Twitter user ID, not the handle. IDs for watchlist accounts must be resolved once (during seeding or at first run) and stored in the `watchlists` table. The `watchlists` table does not currently have a `platform_user_id` column — a migration is needed to add it, OR the agent can resolve IDs at runtime by calling `get_user(username=handle)` once per handle and caching.

### Pattern 5: Recency Decay

```python
from datetime import datetime, timezone

def apply_recency_decay(score: float, created_at: datetime) -> float:
    age_hours = (datetime.now(timezone.utc) - created_at).total_seconds() / 3600
    if age_hours < 1.0:
        return score          # Full score under 1h
    elif age_hours < 4.0:
        # Linear interpolation: 100% at 1h → 50% at 4h
        fraction = 1.0 - 0.5 * (age_hours - 1.0) / 3.0
        return score * fraction
    elif age_hours < 6.0:
        return score * 0.5    # 50% from 4h–6h (or treat as expired — CONTEXT.md says expired at 6h)
    else:
        return 0.0            # Expired at 6h — do not queue
```

CONTEXT.md specifies: "full score under 1 hour, 50% at 4 hours, item marked expired at 6 hours." Tweets with age >= 6h should be excluded before drafting (do not write `DraftItem` records for them). Set `expires_at = created_at + 6h` on any DraftItem written.

### Pattern 6: Compliance Checker

```python
async def _check_compliance(self, draft_text: str) -> bool:
    """Returns True if draft passes compliance (no Seva Mining mention, no financial advice)."""
    message = await self.anthropic.messages.create(
        model="claude-3-haiku-20240307",  # Cheapest model — compliance check is simple
        max_tokens=10,
        messages=[{
            "role": "user",
            "content": (
                f"Does the following text mention 'Seva Mining' (or any variant) "
                f"OR contain financial advice (buy/sell/invest recommendations)? "
                f"Answer only YES or NO.\n\nText: {draft_text}"
            )
        }]
    )
    answer = message.content[0].text.strip().upper()
    return answer == "NO"  # True = passes compliance
```

Use `claude-3-haiku-20240307` for compliance checks (cheap, fast). Use `claude-3-5-sonnet-20241022` or equivalent for the substantive drafting call.

### Anti-Patterns to Avoid

- **Using the legacy `tweepy.API` class:** This is v1.1 only. Always use `tweepy.Client` or `tweepy.asynchronous.AsyncClient`. CLAUDE.md explicitly calls this out.
- **Streaming from Basic tier:** Basic tier does not support the filtered stream endpoint. Polling only via `search_recent_tweets`.
- **Counting only filtered tweets toward quota:** The quota increments for every tweet the API returns, not just those that pass the engagement gate. Count at the API response level.
- **Resolving Twitter handles to IDs inside the hot path on every run:** Resolve watchlist handles to numeric IDs once and store them. Making `get_user()` calls per handle per run wastes quota.
- **Running compliance check inside the drafting prompt:** CONTEXT.md explicitly requires a separate Claude call. Do not merge them.
- **Blocking event loop with sync Tweepy Client:** Use `tweepy.asynchronous.AsyncClient`, not `tweepy.Client` wrapped in `asyncio.to_thread`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| X API v2 authentication + request signing | Custom HTTP client with Bearer token headers | tweepy.asynchronous.AsyncClient | Handles OAuth, rate limit headers, response parsing, pagination |
| Tweet search query building | String concatenation | X API v2 query syntax (documented) | Operators like `-is:retweet`, `lang:en`, `has:media` have specific syntax |
| Rate limit 429 handling | Custom exponential backoff from scratch | `wait_on_rate_limit=True` on AsyncClient OR inspect `x-rate-limit-reset` header | Tweepy's built-in rate limit handling covers the 15-min window resets |
| LLM response parsing | Custom JSON extractor | Structured prompts returning valid JSON + `json.loads()` | Claude reliably returns valid JSON when instructed explicitly |
| Async DB session management | Reinventing session lifecycle | `AsyncSessionLocal()` from `scheduler/database.py` | Already configured with Neon-optimized pool settings |

**Key insight:** The X API v2 query syntax is the most underestimated complexity here. Building a correct compound query string (combining cashtags, hashtags, keywords, `-is:retweet`, `lang:en`, with OR/AND operators within the 512-character limit) requires knowing the documented operator set, not just string joining.

---

## Common Pitfalls

### Pitfall 1: Quota Counter Race Condition at Month Boundary

**What goes wrong:** Agent runs at 23:58 on March 31 and 00:02 on April 1. Both runs read the same `twitter_monthly_reset_date` ("2026-03-01"), neither detects the new month, and the counter is not reset.

**Why it happens:** Non-atomic read-then-write of counter + reset date.

**How to avoid:** In a single DB transaction: read `reset_date`, compare to current month, if different reset counter to 0 and update `reset_date`, then proceed. Use `SELECT FOR UPDATE` or rely on SQLAlchemy's transaction isolation.

**Warning signs:** Dashboard shows quota > 10,000 after a month boundary.

---

### Pitfall 2: impression_count Returns None for Some Tweets

**What goes wrong:** `tweet.public_metrics.get("impression_count")` returns `None` for some tweets even though it was requested. Engagement gate crashes with `TypeError: '>' not supported between instances of 'NoneType' and 'int'`.

**Why it happens:** Not all tweets include impression_count in public_metrics, particularly older tweets or tweets from certain account types. Despite it being documented as available on Basic tier, the API does not guarantee it for every result.

**How to avoid:** Always use `.get("impression_count", 0)` with a default of 0. A tweet with None impression_count effectively fails the view gate (0 < 5000 or 40000), which is the correct conservative behavior.

**Warning signs:** Agent crashes or silently skips posts after `search_recent_tweets` response.

---

### Pitfall 3: Watchlist Handle-to-ID Resolution Quota Cost

**What goes wrong:** Agent calls `get_user(username=handle)` for each of 25 watchlist accounts at every run (every 2 hours). Each call is an API request but does NOT count toward the 10,000 tweet/month quota. However, if handle-to-ID is done inside `get_users_tweets` response processing, it creates unnecessary sequential async calls.

**Why it happens:** Watchlist table stores handles (`@KitcoNews`) not numeric IDs. `get_users_tweets` requires numeric ID.

**How to avoid:** Store the resolved numeric Twitter user ID in the `watchlists` table. Add a `platform_user_id` column via Alembic migration. Resolve IDs once (seed script or on first `None` encounter). The agent checks: if `watchlist.platform_user_id is None`, call `get_user()`, store result, proceed.

**Warning signs:** Agent makes 25 extra API calls per run even when IDs are already known.

---

### Pitfall 4: All Alternatives Fail Compliance — Silent Queue Miss

**What goes wrong:** All 2-3 alternatives for a post type fail compliance checking. The post is correctly skipped but `items_queued` count is never incremented. Dashboard appears empty even though the agent "ran successfully."

**Why it happens:** Compliance checker is strict; Claude compliance call incorrectly flags non-violating drafts, or the drafting prompt generates advice-adjacent language.

**How to avoid:** Log compliance failures to `AgentRun.errors` with detail (which alternative, which rule). Review the errors log after first few production runs to calibrate the compliance prompt. Track `items_filtered` separately from `items_queued` so the run log distinguishes "filtered by engagement gate" from "filtered by compliance."

**Warning signs:** Run logs show `items_found > 0` but `items_queued = 0` consistently.

---

### Pitfall 5: X API Query Length Limit (512 chars)

**What goes wrong:** Concatenating all cashtags + hashtags + keywords into a single OR query exceeds 512 characters, causing a 400 error from the X API.

**Why it happens:** The seed list has 7 cashtags + 7 hashtags + 9 keyword phrases = 23 terms. Naively OR-joined this easily exceeds 512 chars.

**How to avoid:** Split search into multiple queries if needed (counts as separate API calls but stays within the character limit). Alternatively, prioritize the most signal-rich terms. Build the query string programmatically and assert `len(query) <= 512` before calling the API.

**Warning signs:** HTTP 400 response from `search_recent_tweets` with "query" in the error message.

---

### Pitfall 6: tweepy AsyncClient is NOT the same module path as Client

**What goes wrong:** Developer imports `from tweepy import Client` and tries to use `await client.search_recent_tweets()`, which fails because `Client` is synchronous.

**Why it happens:** `tweepy.Client` is the synchronous class. `tweepy.asynchronous.AsyncClient` is the async class. They have the same method signatures but different import paths.

**How to avoid:** Always import `import tweepy.asynchronous` and use `tweepy.asynchronous.AsyncClient(bearer_token=...)`. Never import `from tweepy import Client` in async agent code.

**Warning signs:** `RuntimeWarning: coroutine 'search_recent_tweets' was never awaited` — the method isn't async on the wrong client class.

---

## Code Examples

Verified patterns from official sources and codebase:

### AsyncClient Initialization (confirmed: docs.tweepy.org/en/stable/asyncclient.html)

```python
import tweepy.asynchronous

client = tweepy.asynchronous.AsyncClient(
    bearer_token="YOUR_BEARER_TOKEN",
    wait_on_rate_limit=False,  # We manage hard-stop ourselves
)
```

### search_recent_tweets with public_metrics (confirmed: devcommunity.x.com/t/getting-public-metrics)

```python
response = await client.search_recent_tweets(
    query="(gold OR $GLD OR $GC OR #goldmining OR #gold OR bullion) -is:retweet lang:en",
    max_results=100,
    tweet_fields=["created_at", "public_metrics", "author_id", "text"],
    expansions=["author_id"],
    user_fields=["username", "public_metrics"],
    start_time=two_hours_ago,  # ISO 8601 datetime — only fetch new tweets
)

if response.data:
    for tweet in response.data:
        metrics = tweet.public_metrics or {}
        likes = metrics.get("like_count", 0)
        retweets = metrics.get("retweet_count", 0)
        replies = metrics.get("reply_count", 0)
        views = metrics.get("impression_count", 0)
```

### AgentRun logging pattern (from existing backend pattern, adapted for scheduler)

```python
from models.agent_run import AgentRun
from datetime import datetime, timezone

async def run(self):
    run = AgentRun(
        agent_name="twitter_agent",
        started_at=datetime.now(timezone.utc),
        status="running",
        errors=[],
    )
    async with AsyncSessionLocal() as session:
        session.add(run)
        await session.commit()
        try:
            # ... agent work ...
            run.status = "completed"
        except Exception as e:
            run.status = "failed"
            run.errors = run.errors + [str(e)]
        finally:
            run.ended_at = datetime.now(timezone.utc)
            await session.merge(run)
            await session.commit()
```

### DraftItem write pattern (from existing model)

```python
from models.draft_item import DraftItem
from datetime import datetime, timezone, timedelta

item = DraftItem(
    platform="twitter",
    status="pending",
    source_url=f"https://x.com/i/web/status/{tweet.id}",
    source_text=tweet.text,
    source_account=author_handle,
    score=composite_score,
    alternatives=[
        {"type": "reply", "text": alt1, "rationale": "..."},
        {"type": "reply", "text": alt2, "rationale": "..."},
        {"type": "retweet_with_comment", "text": alt3, "rationale": "..."},
        {"type": "retweet_with_comment", "text": alt4, "rationale": "..."},
    ],
    rationale="[Why this post matters — written by drafting Claude call]",
    urgency="high",  # or "medium" based on score + recency
    expires_at=datetime.now(timezone.utc) + timedelta(hours=6),
    engagement_snapshot={
        "likes": likes,
        "retweets": retweets,
        "replies": replies,
        "views": views,
        "captured_at": datetime.now(timezone.utc).isoformat(),
    },
)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| tweepy.API (v1.1) | tweepy.Client / AsyncClient (v2) | Tweepy 4.0 (2021) | v1.1 endpoints are mostly shut down; must use v2 Client |
| Sync tweepy.Client | tweepy.asynchronous.AsyncClient | Tweepy 4.10 (2023) | Native async without thread wrapping |
| Streaming for real-time | Polling `search_recent_tweets` | X API pricing change (2023) | Basic tier has no streaming access |
| `impression_count` in non_public_metrics only | `impression_count` now in `public_metrics` | ~2022 | View counts available for non-owned tweets on Basic+ |

**Deprecated/outdated:**
- `tweepy.API`: v1.1 legacy class. Not used in this project.
- `search_recent_tweets` full archive: Basic tier only has 7-day lookback. Full archive (`search_all_tweets`) requires Pro/Enterprise.

---

## Open Questions

1. **Watchlist `platform_user_id` column**
   - What we know: `get_users_tweets` requires a numeric Twitter user ID; the `watchlists` table stores handles only.
   - What's unclear: Should the migration for this column be in Wave 0 of Phase 4, or should the agent resolve IDs at runtime and cache them differently?
   - Recommendation: Add `platform_user_id VARCHAR(50)` column to `watchlists` via a new Alembic migration in Wave 0. The seed data for watchlist accounts can include IDs if looked up at seed time, or the agent can lazy-populate on first use.

2. **Quota counter: `config` table vs `agent_runs` metadata**
   - What we know: CONTEXT.md defers this to Claude's discretion.
   - What's unclear: Using `agent_runs` JSONB `notes` field would avoid a migration but creates a complex query to sum tweets read across all runs in the current month.
   - Recommendation: New `config` table (key-value, single migration). Simpler to read in the agent and display in the dashboard. One row: `key='twitter_monthly_tweet_count'`, `value='1234'`. The migration is small.

3. **`start_time` parameter and deduplication**
   - What we know: `search_recent_tweets` accepts a `start_time` parameter to limit results to tweets created after a given time. This prevents fetching the same tweets across 2-hour runs.
   - What's unclear: If the agent passes `start_time = now - 2h`, it will only see tweets from the last 2-hour window. Edge case: if a tweet was posted 2.1 hours ago and missed the prior run (e.g., agent was down), it will not be fetched.
   - Recommendation: Use `start_time = last_run_completed_at` (read from the most recent successful `AgentRun` record) rather than a fixed 2-hour offset. Fall back to `now - 2h` if no prior run exists.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| tweepy | X API calls | Not installed in scheduler | — | Must add to `scheduler/pyproject.toml` |
| anthropic | Drafting + compliance calls | Not installed in scheduler | — | Must add to `scheduler/pyproject.toml` |
| Python 3.12 | Runtime | Available | 3.12 | — |
| PostgreSQL (Neon) | DB reads/writes | Available (Phase 1 complete) | 16 (managed) | — |
| X API Basic credentials | API calls | Available (in .env) | — | — |
| Anthropic API key | LLM calls | Available (in .env) | — | — |

**Missing dependencies with no fallback:**
- `tweepy` — must be added to `scheduler/pyproject.toml` before any agent code runs
- `anthropic` — must be added to `scheduler/pyproject.toml` before any agent code runs

**Alembic migrations needed:**
- New `config` table (for quota counter storage)
- New `platform_user_id` column on `watchlists` table (for watchlist account ID caching)

These are blocking prerequisites for Wave 1 implementation. Plan them as Wave 0 tasks.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio 0.23, asyncio_mode=auto |
| Config file | `scheduler/pyproject.toml` [tool.pytest.ini_options] — already configured |
| Quick run command | `cd scheduler && uv run pytest tests/ -x -q` |
| Full suite command | `cd scheduler && uv run pytest tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TWIT-01 | APScheduler job calls TwitterAgent.run() | unit | `pytest tests/test_twitter_agent.py::test_scheduler_wiring -x` | Wave 0 |
| TWIT-02 | Score formula weights (40/30/30) produce correct composite | unit | `pytest tests/test_twitter_agent.py::test_scoring_formula -x` | Wave 0 |
| TWIT-03 | Engagement formula: likes x1 + retweets x2 + replies x1.5 | unit | `pytest tests/test_twitter_agent.py::test_engagement_formula -x` | Wave 0 |
| TWIT-04 | Engagement gate: watchlist 50L+5kV; non-watchlist 500L+40kV | unit | `pytest tests/test_twitter_agent.py::test_engagement_gate -x` | Wave 0 |
| TWIT-05 | Recency decay: full <1h, 50% at 4h, 0 at 6h | unit | `pytest tests/test_twitter_agent.py::test_recency_decay -x` | Wave 0 |
| TWIT-06 | Top N=3-5 posts selected from scored candidates | unit | `pytest tests/test_twitter_agent.py::test_top_n_selection -x` | Wave 0 |
| TWIT-07 | Each qualifying post produces reply + RT-with-comment drafts | unit (mock Claude) | `pytest tests/test_twitter_agent.py::test_draft_types -x` | Wave 0 |
| TWIT-08 | 2-3 alternatives produced per draft type | unit (mock Claude) | `pytest tests/test_twitter_agent.py::test_alternative_count -x` | Wave 0 |
| TWIT-09 | Quality rubric applied (compliance checker called per alternative) | unit (mock Claude) | `pytest tests/test_twitter_agent.py::test_compliance_called_per_alternative -x` | Wave 0 |
| TWIT-10 | Compliance checker is a SEPARATE Claude call from drafting | unit (mock Claude) | `pytest tests/test_twitter_agent.py::test_compliance_separate_call -x` | Wave 0 |
| TWIT-11 | Monthly quota counter increments per tweet read | unit (mock DB) | `pytest tests/test_twitter_agent.py::test_quota_counter_increments -x` | Wave 0 |
| TWIT-12 | Hard-stop prevents API calls when quota >= safety margin | unit | `pytest tests/test_twitter_agent.py::test_quota_hard_stop -x` | Wave 0 |
| TWIT-13 | Quota counter readable from DB for dashboard | unit | `pytest tests/test_twitter_agent.py::test_quota_readable -x` | Wave 0 |
| TWIT-14 | DraftItem.rationale is populated on every queued item | unit (mock Claude) | `pytest tests/test_twitter_agent.py::test_rationale_populated -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `cd scheduler && uv run pytest tests/test_twitter_agent.py -x -q`
- **Per wave merge:** `cd scheduler && uv run pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `scheduler/tests/test_twitter_agent.py` — covers TWIT-01 through TWIT-14 (all unit tests, mock tweepy + mock anthropic + mock DB)
- [ ] Alembic migration for `config` table — needed before quota counter tests can hit real DB
- [ ] Alembic migration for `watchlists.platform_user_id` column
- [ ] `tweepy` added to `scheduler/pyproject.toml` — must be present for imports to work in tests
- [ ] `anthropic` added to `scheduler/pyproject.toml` — must be present for imports to work in tests

---

## Project Constraints (from CLAUDE.md)

| Directive | Impact on Phase 4 |
|-----------|-------------------|
| Use `tweepy 4.x Client` (v2, not legacy API class) | Use `tweepy.asynchronous.AsyncClient` only |
| Avoid `requests` library in async code | Use httpx or async clients only (not relevant to Tweepy path, but Claude calls go through `anthropic` SDK which uses httpx internally) |
| APScheduler 3.11.2 — no v4 | Already deployed in scheduler; do not upgrade |
| Avoid APScheduler inside Gunicorn multi-worker | Already separated as Railway service 2; no change needed |
| `AsyncAnthropic` for all LLM calls | Drafting and compliance checker both use `AsyncAnthropic` |
| Never auto-post | Agent writes `DraftItem` records only; no posting logic ever |
| SQLAlchemy 2.0 `async_sessionmaker` + `AsyncSession` | `AsyncSessionLocal` from `scheduler/database.py` |
| No Pydantic v1 patterns | Any new schemas in agent use Pydantic v2 `model_config = ConfigDict(...)` |
| Budget: Anthropic ~$30-50/mo | Each run: ~3-5 qualifying posts x 2 draft types x 3 alternatives = 15-30 Claude calls per run + 30-60 compliance calls. At 12 runs/day x 30 days = 360 runs: up to 10,800 small Claude calls/month. Use Haiku for compliance, Sonnet for drafting. Monitor cost. |
| X API Basic tier: 10,000 tweets/month | Hard-stop logic is a phase requirement; see quota counter design |
| `ruff` linter + formatter | Agent code formatted with ruff before commit |
| `uv` package manager | `uv sync` to update lockfile after adding tweepy + anthropic to pyproject.toml |

---

## Sources

### Primary (HIGH confidence)

- [Tweepy 4.14.0 AsyncClient docs](https://docs.tweepy.org/en/stable/asyncclient.html) — AsyncClient class, method signatures, async usage
- [Tweepy 4.14.0 Client docs](https://docs.tweepy.org/en/stable/client.html) — search_recent_tweets parameters, tweet_fields, expansions
- [X API Rate Limits official docs](https://docs.x.com/x-api/fundamentals/rate-limits) — per-endpoint rate limits confirmed
- `scheduler/worker.py` — APScheduler wiring pattern, advisory lock, placeholder job structure
- `scheduler/database.py` — AsyncSessionLocal pattern for agents
- `scheduler/config.py` — Settings class with X API credentials already present
- `backend/app/models/draft_item.py` — DraftItem schema: all fields confirmed present
- `backend/app/models/agent_run.py` — AgentRun schema confirmed
- `backend/app/models/watchlist.py` — Watchlist schema: no `platform_user_id` column currently

### Secondary (MEDIUM confidence)

- [X Developer Community — impression_count in public_metrics](https://devcommunity.x.com/t/will-impressions-be-available-in-public-metrics/182004) — confirmed public_metrics.impression_count available for non-owned tweets via search/recent
- [X Developer Community — public_metrics fields](https://devcommunity.x.com/t/twitter-public-metrics/185823) — confirmed like_count, retweet_count, reply_count, impression_count
- [Twitter/X API Pricing 2025](https://twitterapi.io/blog/twitter-api-pricing-2025) — Basic tier 10,000 tweets/month confirmed across multiple sources

### Tertiary (LOW confidence)

- Community reports that `impression_count` may return `None` for some tweets even when requested — cannot confirm from official docs alone; treat as risk, handle defensively with `.get("impression_count", 0)`.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — Tweepy AsyncClient confirmed in official docs; anthropic SDK version confirmed in CLAUDE.md
- Architecture: HIGH — APScheduler wiring pattern verified against actual `scheduler/worker.py`; DraftItem model fields verified against actual model file
- Pitfalls: MEDIUM — impression_count availability confirmed via official docs + community; 429 handling and quota math are inferred from documented limits
- Test architecture: HIGH — existing test pattern (pytest-asyncio, asyncio_mode=auto, mock-based unit tests) verified in `scheduler/tests/test_worker.py`

**Research date:** 2026-04-01
**Valid until:** 2026-05-01 (X API pricing/tier changes have been frequent; verify quota before implementation)
