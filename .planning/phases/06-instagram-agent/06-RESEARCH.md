# Phase 6: Instagram Agent - Research

**Researched:** 2026-04-02
**Domain:** Apify Instagram scraping, async Python agent pattern, health monitoring, WhatsApp alerting
**Confidence:** HIGH (architecture mirrors fully-implemented Twitter Agent; Apify field names verified via official tutorials)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **Actor:** `apify/instagram-scraper`
- **Scraping mode:** Parallel — hashtag scraping and account profile scraping run concurrently via `asyncio.gather`
- **Lookback per run:** 24 hours (fetch), filter to 8h for engagement gate
- **Posts per hashtag:** 50 per run (`instagram_max_posts_per_hashtag`, default `"50"`)
- **Posts per account:** 10 per run (`instagram_max_posts_per_account`, default `"10"`)
- **Deduplication:** by `shortCode` before scoring
- **Hashtag seed:** #gold #goldmining #preciousmetals #goldprice #bullion #juniorminers #goldstocks #goldsilver #goldnugget #mininglife (10 tags, `platform='instagram'`)
- **Watchlist:** Best-effort mapping of 25 Twitter entities to Instagram handles, `relationship_value=5`, `platform='instagram'`
- **Engagement gate:** 200+ likes AND post within last 8 hours — applies to ALL accounts (no lower watchlist threshold)
- **Scoring:** `likes×1 + comment_count×2 + normalize_followers(n)×1.5` where `normalize = min(log10(max(n,1)) / log10(1_000_000), 1.0)`
- **Top N:** 3 posts per run (`instagram_top_n`, default `"3"`)
- **Comment format:** 2-3 alternatives per post, 1-2 sentences, no hashtags, data point/insight first, senior analyst voice
- **Two-Claude:** Sonnet drafting + Haiku compliance
- **Fail-safe compliance:** Ambiguous response = block
- **Health baseline:** 7-run rolling average, skip first 3 runs, <20% of average = health warning stored in `AgentRun.errors` with tag `health_warning`
- **Critical alert:** 2+ consecutive all-zero runs → WhatsApp via `breaking_news` template — `{{1}}` = "Instagram scraper failure", `{{2}}` = "instagram_agent", `{{3}}` = consecutive failure count, `{{4}}` = dashboard URL
- **Retry:** Up to 2 retries (1s, 2s backoff) per source; skip source after 3 failures
- **Expiry:** `expires_at = created_at + 12 hours`, `platform = 'instagram'`
- **Senior Agent integration:** call `process_new_items(new_item_ids)` after DraftItem commit (lazy import pattern)
- **worker.py:** `instagram_agent` job slot already registered at lock ID 1002, every 4 hours — replace placeholder with `InstagramAgent().run()`

### Claude's Discretion

- Exact `asyncio.gather` structure for parallel Apify calls
- Apify actor input schema field names (verify: `likesCount`, `commentsCount`, `ownerFollowersCount`, `timestamp`, `shortCode`, `ownerUsername`, `caption`)
- Config key naming convention (follow `instagram_*` prefix pattern)
- Error handling for zero-result runs that don't trigger health event (normal quiet run vs failure)
- `AgentRun.notes` JSONB structure for storing per-hashtag result counts

### Deferred Ideas (OUT OF SCOPE)

- Watchlist engagement gate reduction (lower threshold for watchlist accounts)
- Apify retry count configurability
- Instagram Stories / Reels scraping
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| INST-01 | Agent monitors Instagram via Apify scraper using configurable hashtags and account watchlist every 4 hours | worker.py placeholder at lock ID 1002 already wired; `InstagramAgent().run()` replaces `placeholder_job` |
| INST-02 | Agent scores posts: likes×1 + comment_count×2 + normalized follower count×1.5 | Scoring formula verified in CONTEXT.md; mirror `calculate_engagement_score` pattern from twitter_agent |
| INST-03 | Minimum engagement gate: 200+ likes from last 8 hours | Post-fetch filter on `timestamp`; `likesCount` field confirmed from Apify output |
| INST-04 | Top 3 posts per run passed to drafting | `instagram_top_n` config key (default `"3"`); mirror `select_top_posts` pattern |
| INST-05 | Agent drafts 2-3 alternative comments per qualifying post (1-2 sentences each) | Sonnet prompt; JSON output with `"comment_alternatives"` array |
| INST-06 | No hashtags in any drafted comment, ever | Enforced in both system prompt AND compliance check |
| INST-07 | Each draft evaluated against quality rubric before queuing | Rationale field + quality rubric in Sonnet system prompt |
| INST-08 | Separate Claude compliance-checker call on every draft | Haiku `_check_compliance()` mirror from twitter_agent; `_check_instagram_compliance()` |
| INST-09 | Retry logic for Apify scraping failures with exponential backoff | `asyncio.sleep(1)` then `asyncio.sleep(2)`; skip source after 3 failures |
| INST-10 | Scraper health monitoring: detect silent failures by comparing against baseline | Rolling 7-run average per hashtag stored as JSON in `AgentRun.notes`; skip first 3 runs |
| INST-11 | Scraper failure alerts in logs and WhatsApp if critical | 2 consecutive all-zero runs → `send_whatsapp_template("breaking_news", {...})`; use existing `scheduler/services/whatsapp.py` |
| INST-12 | Items expire after 12 hours | `expires_at = datetime.now(timezone.utc) + timedelta(hours=12)` on DraftItem |
</phase_requirements>

---

## Summary

Phase 6 builds `scheduler/agents/instagram_agent.py` — a near-direct structural mirror of `twitter_agent.py`, with Apify replacing Tweepy and a simplified scoring formula (no recency decay, no composite 40/30/30 weighting). The most significant departures from Twitter Agent are: (1) parallel fetching via `asyncio.gather` for hashtags and accounts simultaneously, (2) health monitoring with rolling baseline logic stored in `AgentRun.notes`, and (3) critical failure WhatsApp alerting.

The phase also requires `scheduler/seed_instagram_data.py` (mirrors `seed_twitter_data.py`) to populate 10 hashtags, up to ~16 watchlist handles, and config defaults. A `_make_job` branch for `instagram_agent` must be added to `worker.py`.

The key dependency gap identified in research: **`apify-client` is not installed in the scheduler venv and is absent from `scheduler/pyproject.toml`**. Wave 0 must add it before any implementation can be tested.

**Primary recommendation:** Mirror `twitter_agent.py` structure exactly, substituting Apify calls for Tweepy calls. The health monitoring logic is the only novel component — implement it as a standalone `_check_scraper_health()` method that reads prior `AgentRun` records to compute rolling averages.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| apify-client | 2.5.0 | Calls `apify/instagram-scraper` actor via `ApifyClientAsync` | Specified in CLAUDE.md; handles auth, rate limits, run lifecycle |
| anthropic | 0.86.0 | Sonnet drafting + Haiku compliance | Already installed in venv; AsyncAnthropic for async use |
| sqlalchemy[asyncio] | 2.0.x | DB sessions, AgentRun logging, DraftItem persistence | Already installed; `AsyncSessionLocal` pattern from twitter_agent |
| asyncpg | 0.30.x | Async PostgreSQL driver | Already installed |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| asyncio (stdlib) | — | `asyncio.gather` for parallel Apify calls, `asyncio.sleep` for retry backoff | Built-in |
| math (stdlib) | — | `math.log10` for follower count normalization | Built-in |

### Missing Dependency (BLOCKING — Wave 0 task)
`apify-client 2.5.0` is not in `scheduler/pyproject.toml` and not installed in `.venv`. Must be added before any implementation:

```bash
# Add to scheduler/pyproject.toml dependencies
"apify-client==2.5.0",

# Then install
cd scheduler && uv sync
```

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `apify-client` (managed) | Direct HTTP to Apify REST API | More code, more error surface; client handles run lifecycle, dataset pagination automatically |
| `ApifyClientAsync.actor().call()` | `actor().start()` + poll | `.call()` waits for run completion and returns `defaultDatasetId` directly — simpler for scheduled batch use |

---

## Architecture Patterns

### Recommended Project Structure
```
scheduler/
├── agents/
│   ├── twitter_agent.py       # Reference implementation — fully complete
│   ├── senior_agent.py        # Integration target for process_new_items()
│   └── instagram_agent.py     # NEW: this phase
├── tests/
│   ├── test_twitter_agent.py  # Reference test pattern
│   ├── test_senior_agent.py   # Reference test pattern
│   └── test_instagram_agent.py  # NEW: Wave 0 stub → Wave 1-3 implementation
├── seed_twitter_data.py        # Reference implementation
└── seed_instagram_data.py      # NEW: this phase
```

### Pattern 1: Apify Actor Async Call
**What:** Call `apify/instagram-scraper` actor via `ApifyClientAsync`, wait for completion, iterate dataset items.

**When to use:** Every fetch call (both hashtag and account profile modes).

```python
# Source: docs.apify.com/api/client/python/docs/examples/passing-input-to-actor
# Source: blog.apify.com/scrape-instagram-python/
import asyncio
from apify_client import ApifyClientAsync
from config import get_settings

async def _call_actor(self, run_input: dict) -> list[dict]:
    """Call apify/instagram-scraper and return all dataset items."""
    settings = get_settings()
    client = ApifyClientAsync(token=settings.apify_api_token)
    actor_client = client.actor("apify/instagram-scraper")

    # call() waits for run completion; returns run dict with defaultDatasetId
    run_result = await actor_client.call(run_input=run_input)
    if run_result is None:
        return []

    # Retrieve dataset items — sync iterate_items via asyncio.to_thread
    # (see Pattern 2: asyncio.to_thread for sync SDK methods)
    dataset_id = run_result.get("defaultDatasetId")
    if not dataset_id:
        return []

    dataset_client = client.dataset(dataset_id)
    # list_items() is the async method; iterate_items() is sync-only
    items_result = await dataset_client.list_items()
    return items_result.items if items_result else []
```

**IMPORTANT — sync vs async methods:**
- `ApifyClientAsync.actor().call()` — async, awaitable
- `ApifyClientAsync.dataset().list_items()` — async, awaitable (returns `ListPage` with `.items` attribute)
- `ApifyClient.dataset().iterate_items()` — sync iterator only (sync client). Do NOT use with `ApifyClientAsync`.

### Pattern 2: Parallel Fetch with asyncio.gather
**What:** Run hashtag scrape and account profile scrape concurrently.

**When to use:** `_run_pipeline()` fetch step — mirrors how Twitter Agent called `_fetch_watchlist_tweets` and `_fetch_keyword_tweets` sequentially, but parallelized here per CONTEXT.md decision.

```python
# asyncio.gather runs both coroutines concurrently
hashtag_posts, account_posts = await asyncio.gather(
    self._fetch_hashtag_posts(session, hashtags, max_per_hashtag),
    self._fetch_account_posts(session, watchlist, max_per_account),
)
all_posts = hashtag_posts + account_posts
```

Each `_fetch_hashtag_posts` call runs one Apify actor invocation per hashtag (50 results each). The `asyncio.gather` at the top level runs hashtag batch and account batch concurrently. Within each batch, Apify calls may be sequential or parallel — sequential is safer to avoid Apify rate limits.

### Pattern 3: Apify Input Schema for apify/instagram-scraper
**What:** Exact input field names for the actor.

**Confidence:** MEDIUM — confirmed from Apify docs and tutorials; actor-specific schema must be verified against live actor at plan/implement time.

```python
# Hashtag scrape input — use directUrls with hashtag explore URL
hashtag_input = {
    "directUrls": [f"https://www.instagram.com/explore/tags/{tag.lstrip('#')}/"],
    "resultsType": "posts",
    "resultsLimit": max_posts_per_hashtag,  # default 50
    "onlyPostsNewerThan": lookback_date.strftime("%Y-%m-%d"),  # 24h lookback
}

# Account profile scrape input
account_input = {
    "directUrls": [f"https://www.instagram.com/{handle}/"],
    "resultsType": "posts",
    "resultsLimit": max_posts_per_account,  # default 10
    "onlyPostsNewerThan": lookback_date.strftime("%Y-%m-%d"),
}
```

**Alternative input method for hashtags** (if `directUrls` with explore/tags doesn't work):
Some actors use `hashtags: ["gold"]` (without `#`) as a separate field. If the `directUrls` approach returns zero results on first run, switch to the `hashtags` array format.

### Pattern 4: Apify Output Field Names
**What:** JSON field names in the dataset items returned by `apify/instagram-scraper`.

**Confidence:** HIGH for core fields (confirmed by multiple sources: use-apify.com tutorial, blog.apify.com/scrape-instagram-python).

| Field | Type | Notes |
|-------|------|-------|
| `shortCode` | str | Unique post identifier — use for dedup |
| `timestamp` | str | ISO 8601 datetime string, e.g. `"2026-03-15T14:22:11.000Z"` |
| `likesCount` | int | Like count at scrape time |
| `commentsCount` | int | Comment count at scrape time |
| `ownerUsername` | str | Author's Instagram handle |
| `caption` | str | Full post caption text |
| `url` | str | Full Instagram post URL |
| `ownerFullName` | str | Display name of post owner |

**Confidence LOW — requires verification at implementation time:**
| Field | Type | Notes |
|-------|------|-------|
| `ownerFollowersCount` | int | Owner's follower count. Name uncertain — may be `followersCount`, `ownerFollowers`, or absent; check live dataset item. If absent, default to 0 (normalization formula handles 0 gracefully). |

**Defensive accessor pattern for uncertain fields:**
```python
follower_count = item.get("ownerFollowersCount") or item.get("followersCount") or 0
```

### Pattern 5: Health Monitoring with Rolling Average
**What:** Per-hashtag result counts stored in `AgentRun.notes` as JSON; rolling 7-run average computed from prior AgentRun records.

**When to use:** End of each run, after all Apify fetches complete.

```python
# Store per-hashtag counts in AgentRun.notes
import json

hashtag_counts = {
    "goldmining": 48,
    "gold": 50,
    "preciousmetals": 12,
    # ...
}
agent_run.notes = json.dumps({
    "hashtag_counts": hashtag_counts,
    "total_posts_fetched": sum(hashtag_counts.values()),
})

# Health check: compute rolling average from last 7 completed runs
async def _check_scraper_health(
    self,
    session: AsyncSession,
    current_counts: dict[str, int],
    run_number: int,  # total completed instagram_agent runs (from DB count)
    baseline_threshold: int,  # from config, default 3
) -> list[str]:
    """Return list of health warning strings for hashtags below 20% of rolling average."""
    warnings = []

    if run_number <= baseline_threshold:
        return warnings  # no baseline yet

    # Query last 7 completed instagram_agent runs
    prior_runs = await session.execute(
        select(AgentRun)
        .where(
            AgentRun.agent_name == "instagram_agent",
            AgentRun.status == "completed",
            AgentRun.notes.isnot(None),
        )
        .order_by(AgentRun.created_at.desc())
        .limit(7)
    )
    prior_run_list = list(prior_runs.scalars().all())

    if not prior_run_list:
        return warnings

    # Compute per-hashtag rolling averages
    hashtag_history: dict[str, list[int]] = {}
    for run in prior_run_list:
        try:
            notes = json.loads(run.notes)
            counts = notes.get("hashtag_counts", {})
            for tag, count in counts.items():
                hashtag_history.setdefault(tag, []).append(count)
        except (json.JSONDecodeError, AttributeError):
            continue

    for tag, current_count in current_counts.items():
        history = hashtag_history.get(tag, [])
        if not history:
            continue
        avg = sum(history) / len(history)
        if avg > 0 and current_count < avg * 0.20:
            warnings.append(
                f"health_warning: hashtag #{tag} returned {current_count} posts "
                f"(avg={avg:.1f}, threshold=20%)"
            )

    return warnings
```

### Pattern 6: Critical Failure WhatsApp Alert
**What:** Send `breaking_news` WhatsApp alert when 2+ consecutive all-zero runs.

**When to use:** After computing current run health, before finalizing `AgentRun.status`.

```python
# Check if last run was also all-zero
async def _check_critical_failure(
    self,
    session: AsyncSession,
    current_total: int,
) -> int:
    """Return consecutive zero-run count (including current run). 0 if current has results."""
    if current_total > 0:
        return 0

    # Count consecutive all-zero completed runs from most recent
    prior_runs = await session.execute(
        select(AgentRun)
        .where(
            AgentRun.agent_name == "instagram_agent",
            AgentRun.status == "completed",
            AgentRun.notes.isnot(None),
        )
        .order_by(AgentRun.created_at.desc())
        .limit(6)  # max we'd ever need to check
    )
    consecutive = 1  # current run is zero
    for run in prior_runs.scalars():
        try:
            notes = json.loads(run.notes or "{}")
            total = notes.get("total_posts_fetched", -1)
            if total == 0:
                consecutive += 1
            else:
                break
        except (json.JSONDecodeError, AttributeError):
            break

    return consecutive


# Trigger alert at exactly 2 consecutive (dedup: don't re-alert for 3rd, 4th, etc.)
if consecutive_zeros == 2:
    from services.whatsapp import send_whatsapp_template
    await send_whatsapp_template(
        "breaking_news",
        {
            "1": "Instagram scraper failure",
            "2": "instagram_agent",
            "3": str(consecutive_zeros),
            "4": settings.frontend_url,
        },
    )
```

### Pattern 7: Scoring Formula
**What:** Instagram-specific composite score (simpler than Twitter — no recency decay, no 40/30/30 weighting).

```python
import math

def normalize_followers(n: int) -> float:
    """Log-scale normalization capped at 1M followers. INST-02."""
    if n <= 0:
        return 0.0
    return min(math.log10(max(n, 1)) / math.log10(1_000_000), 1.0)

def calculate_instagram_score(
    likes: int,
    comment_count: int,
    follower_count: int,
) -> float:
    """INST-02: likes*1 + comments*2 + normalize_followers(n)*1.5"""
    return float(
        likes * 1
        + comment_count * 2
        + normalize_followers(follower_count) * 1.5
    )
```

**Note:** No recency decay in Instagram scoring. The 8-hour filter is a hard gate, not a decay curve.

### Pattern 8: DraftItem Structure for Instagram
**What:** Instagram comment DraftItem uses `alternatives` JSONB array with a single `"comment"` type.

```python
from datetime import datetime, timezone, timedelta

draft_item = DraftItem(
    platform="instagram",
    status="pending",
    source_url=f"https://www.instagram.com/p/{post['shortCode']}/",
    source_text=post.get("caption", ""),
    source_account=post.get("ownerUsername", ""),
    follower_count=post.get("ownerFollowersCount") or 0,
    score=instagram_score,
    alternatives=[
        {"type": "comment", "text": alt_text}
        for alt_text in passing_alternatives
    ],
    rationale=rationale,
    urgency="high" if instagram_score > 300 else "medium",
    expires_at=datetime.now(timezone.utc) + timedelta(hours=12),
    engagement_snapshot={
        "likes": post.get("likesCount", 0),
        "comments": post.get("commentsCount", 0),
        "follower_count": post.get("ownerFollowersCount") or 0,
        "captured_at": datetime.now(timezone.utc).isoformat(),
    },
)
```

### Pattern 9: Retry Logic per Source
**What:** Mirror Phase 2 WhatsApp retry pattern — retry up to 2 times with exponential backoff, skip source after 3 failures.

```python
async def _fetch_with_retry(self, run_input: dict, source_name: str) -> list[dict]:
    """Fetch from Apify with retry. Returns [] after 3 failures."""
    backoff = [1, 2]  # seconds between retries
    for attempt in range(3):
        try:
            return await self._call_actor(run_input)
        except Exception as exc:
            if attempt < 2:
                logger.warning(
                    "Apify fetch failed for %s (attempt %d/3): %s. Retrying in %ds.",
                    source_name, attempt + 1, exc, backoff[attempt],
                )
                await asyncio.sleep(backoff[attempt])
            else:
                logger.error(
                    "Apify fetch failed for %s after 3 attempts: %s. Skipping.",
                    source_name, exc,
                )
    return []
```

### Anti-Patterns to Avoid
- **Using `iterate_items()` with async client:** `iterate_items()` is a synchronous generator on the sync `ApifyClient`. Use `await dataset_client.list_items()` instead, which is the async equivalent.
- **Using `asyncio.to_thread` for `ApifyClientAsync` calls:** `ApifyClientAsync` is already async-native. Do NOT wrap in `asyncio.to_thread` (contrast with Twilio, which IS sync-only and requires `asyncio.to_thread`).
- **Calling `actor.call()` with `run_input={}` when no hashtags loaded:** Guard with early return if hashtags/watchlist lists are empty.
- **Treating zero results as always-suspicious:** Zero results in runs 1-3 or for low-traffic hashtags on a quiet day is normal. Health checks only trigger after 3+ runs with an established baseline AND the count is <20% of rolling average.
- **Importing `InstagramAgent` at module level in `worker.py`:** Follow Twitter Agent pattern — instantiate inside the `_make_job` closure, not at module import time.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Instagram scraping | Custom Playwright/aiohttp scraper | `apify/instagram-scraper` via `apify-client` | Instagram anti-bot aggressively blocks; Apify manages proxies, fingerprinting, session rotation |
| Dataset pagination | Manual offset/limit loops | `await dataset_client.list_items()` | Handles pagination automatically; returns all items from the run's dataset |
| Actor run lifecycle | Poll `run.status` in a loop | `actor_client.call()` | `.call()` blocks until actor completes and returns result dict |
| Follower normalization | Linear scale or percentile buckets | `log10(n) / log10(1_000_000)` formula | Already specified; log scale correctly handles 3-order-of-magnitude follower range |

**Key insight:** Apify's managed actor handles all Instagram anti-scraping complexity. The agent code only needs to pass input, wait for completion, and parse the flat JSON items from the dataset.

---

## Instagram Watchlist Seed (25 Twitter → Instagram Mapping)

Research finding — Instagram handles for the 25 Twitter watchlist entities. Confidence levels reflect verification depth.

| Twitter Handle | Instagram Handle | Confidence | Notes |
|----------------|-----------------|------------|-------|
| KitcoNews | `kitconews` | HIGH | Confirmed active: 27K followers, 3K+ posts |
| WGCouncil | `worldgoldcouncil` | HIGH | Confirmed: instagram.com/worldgoldcouncil |
| BullionVault | `bullionvault_official` | HIGH | Confirmed: @bullionvault_official |
| Reuters | SKIP | MEDIUM | Reuters Instagram exists but is general news (@reuters), not gold-focused; low signal value |
| BloombergMkts | SKIP | MEDIUM | No dedicated gold/markets Bloomberg IG found; general @bloomberg exists but not worth seeding |
| PeterSchiff | `peterschiff` | HIGH | Confirmed active posts about gold at $3,000 |
| JimRickards | `jimmrick1` | MEDIUM | Found @jimmrick1; active. Note: verify it's the author, not a parody |
| GoldSeekCom | SKIP | MEDIUM | No Instagram presence found for GoldSeek.com; primarily web/Twitter presence |
| RealVision | `realvisiontv` | HIGH | Confirmed: @realvisiontv, 75K followers, finance/gold content |
| TaviCosta | `tavicostamacro` | HIGH | Confirmed: @tavicostamacro, 35K followers, active macro/gold content |
| Mike_maloney | `mikemaloneygold` | HIGH | Confirmed: @mikemaloneygold |
| MacleodFinance | SKIP | MEDIUM | Alasdair Macleod has no confirmed active Instagram; primarily Substack/Twitter presence |
| DanielaCambone | `danicambone` | HIGH | Confirmed: @danicambone active public account |
| RonStoeferle | SKIP | LOW | No Instagram handle found for Ron Stoeferle; primarily Twitter/LinkedIn |
| Frank_Giustra | SKIP | LOW | No confirmed public Instagram handle found; has frankgiustra.com but no IG link confirmed |
| Newmont | `newmontmining` | HIGH | Confirmed: @newmontmining corporate account |
| Barrick | `barrickgold` | HIGH | Confirmed: @barrickgold (note: company rebranded to Barrick Mining; may also have @barrick_mining) |
| AgnicoEagle | `agnicoeagle` | HIGH | Confirmed: @agnicoeagle, 7K followers |
| KinrossGold | `kinrossgoldcorp` | HIGH | Confirmed: @kinrossgoldcorp, Toronto |
| FrancoNevada | SKIP | LOW | No confirmed Franco-Nevada Instagram found; royalty companies rarely active on IG |
| WheatonPrecious | SKIP | LOW | No confirmed Wheaton Precious Metals Instagram found |
| SPDR_ETFs | SKIP | MEDIUM | SPDR ETFs focuses on institutional investors; no confirmed active gold-sector Instagram |
| VanEck | SKIP | LOW | No confirmed VanEck Instagram handle found; ETF company, minimal IG presence |
| GoldTelegraph_ | `goldtelegraph` | HIGH | Confirmed: @goldtelegraph, 9.8K followers, active gold commentary |
| WSBGold | `wsbgold` | HIGH | Confirmed: instagram.com/wsbgold |

**Seed summary:** 14 accounts to seed, 11 to skip.

Seeded accounts (14): kitconews, worldgoldcouncil, bullionvault_official, peterschiff, jimmrick1, realvisiontv, tavicostamacro, mikemaloneygold, danicambone, newmontmining, barrickgold, agnicoeagle, kinrossgoldcorp, goldtelegraph, wsbgold

Wait — recounting: kitconews, worldgoldcouncil, bullionvault_official, peterschiff, jimmrick1, realvisiontv, tavicostamacro, mikemaloneygold, danicambone, newmontmining, barrickgold, agnicoeagle, kinrossgoldcorp, goldtelegraph, wsbgold = **15 accounts**.

**LOW-confidence handles that require spot-check at implementation time:** `jimmrick1` (verify it's the author James Rickards, not a parody account).

---

## Common Pitfalls

### Pitfall 1: `list_items()` vs `iterate_items()` on Async Client
**What goes wrong:** Developer calls `iterate_items()` on `ApifyClientAsync`'s dataset client, getting a synchronous generator that blocks the event loop or raises a coroutine error.
**Why it happens:** The sync `ApifyClient` has `iterate_items()` (sync generator). The async `ApifyClientAsync` has `list_items()` (returns a `ListPage` object with `.items` attribute).
**How to avoid:** Always use `await dataset_client.list_items()` with `ApifyClientAsync`. Never call `iterate_items()` in async context.
**Warning signs:** `TypeError: object is not an async iterable` or silent empty results.

### Pitfall 2: `apify-client` Not Installed
**What goes wrong:** `ImportError: No module named 'apify_client'` at agent import time, crashing the worker process startup.
**Why it happens:** `apify-client` is confirmed absent from `scheduler/pyproject.toml` and the `.venv`. It was in CLAUDE.md's tech stack recommendation but never added to the scheduler's dependencies.
**How to avoid:** Wave 0 must add `"apify-client==2.5.0"` to `pyproject.toml` and run `uv sync`.
**Warning signs:** Worker fails to start with ImportError at scheduler startup.

### Pitfall 3: Timestamp Parsing from Apify
**What goes wrong:** `timestamp` field comes as ISO string `"2026-04-01T08:30:00.000Z"`. Direct comparison with `datetime.now(timezone.utc)` fails because the string has a `Z` suffix that Python's `fromisoformat` doesn't handle before Python 3.11.
**Why it happens:** Python 3.11+ added `Z` support to `fromisoformat`, but defensive code should still handle it.
**How to avoid:** Use `.replace("Z", "+00:00")` before `fromisoformat()`, mirroring Twitter Agent's timestamp parsing pattern.
**Warning signs:** `ValueError: Invalid isoformat string` in post-fetch processing.

### Pitfall 4: Zero Results vs. Silent Failure
**What goes wrong:** An Apify actor call returns HTTP 200, run completes successfully, but dataset has zero items. This is indistinguishable from a genuine quiet day vs. a scraper failure.
**Why it happens:** Instagram anti-bot blocks the actor's session; actor "succeeds" but finds nothing.
**How to avoid:** This is exactly what INST-10 addresses. The health monitoring baseline (7-run rolling average, <20% threshold) is the detection mechanism. Log `health_warning` in errors for any hashtag below threshold; don't abort the run.
**Warning signs:** Consistently zero results across all hashtags simultaneously.

### Pitfall 5: Missing `ownerFollowersCount` in Dataset
**What goes wrong:** Scoring formula uses `ownerFollowersCount` but Apify dataset may return `followersCount` or omit it entirely for some posts.
**Why it happens:** The official Apify docs don't confirm this field name with certainty; the actor may return it differently or not at all.
**How to avoid:** Use defensive accessor: `item.get("ownerFollowersCount") or item.get("followersCount") or 0`. The `normalize_followers(0)` returns `0.0`, so the scoring formula degrades gracefully (no crash, just missing the 1.5 follower term).
**Warning signs:** All posts have a follower-count contribution of 0.0 after several runs.

### Pitfall 6: Parallel Gather with Apify Raises Uncaught Exception
**What goes wrong:** `asyncio.gather(fetch_hashtags(), fetch_accounts())` — if one coroutine raises, the other is cancelled by default.
**Why it happens:** `asyncio.gather` propagates the first exception immediately by default.
**How to avoid:** Use `asyncio.gather(..., return_exceptions=True)` and handle exception results. Alternatively, wrap each `_fetch_*` coroutine in its own try/except before passing to gather.
**Warning signs:** Entire scrape silently returns only one source's results when the other fails.

### Pitfall 7: worker.py Not Updated
**What goes wrong:** `instagram_agent` continues running `placeholder_job` after Phase 6 because `_make_job` was never updated with the `instagram_agent` branch.
**Why it happens:** Easy to forget the worker.py edit; the scheduler logs show the job running but no DraftItems appear.
**How to avoid:** Update `_make_job` in `worker.py` to add `elif job_name == "instagram_agent": agent = InstagramAgent(); ...` — mirror the `twitter_agent` branch exactly.
**Warning signs:** `placeholder_job` log lines for `instagram_agent` after deployment.

---

## Code Examples

### InstagramAgent class skeleton (mirroring TwitterAgent)
```python
# Source: scheduler/agents/twitter_agent.py (direct structural mirror)
from __future__ import annotations

import asyncio
import json
import logging
import math
from datetime import datetime, timezone, timedelta
from typing import Optional

from apify_client import ApifyClientAsync
from anthropic import AsyncAnthropic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from database import AsyncSessionLocal
from models.agent_run import AgentRun
from models.config import Config
from models.draft_item import DraftItem
from models.keyword import Keyword
from models.watchlist import Watchlist

logger = logging.getLogger(__name__)


def normalize_followers(n: int) -> float:
    if n <= 0:
        return 0.0
    return min(math.log10(max(n, 1)) / math.log10(1_000_000), 1.0)


def calculate_instagram_score(likes: int, comment_count: int, follower_count: int) -> float:
    return float(likes * 1 + comment_count * 2 + normalize_followers(follower_count) * 1.5)


def passes_instagram_gate(likes: int, post_age_hours: float) -> bool:
    return likes >= 200 and post_age_hours <= 8.0


class InstagramAgent:
    def __init__(self) -> None:
        settings = get_settings()
        self.apify_token = settings.apify_api_token
        self.anthropic = AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def run(self) -> None:
        async with AsyncSessionLocal() as session:
            agent_run = AgentRun(
                agent_name="instagram_agent",
                started_at=datetime.now(timezone.utc),
                status="running",
                errors=[],
            )
            session.add(agent_run)
            await session.commit()
            try:
                await self._run_pipeline(session, agent_run)
            except Exception as exc:
                logger.error("InstagramAgent.run() unhandled: %s", exc, exc_info=True)
                agent_run.status = "failed"
                agent_run.errors = (agent_run.errors or []) + [str(exc)]
                agent_run.ended_at = datetime.now(timezone.utc)
                await session.commit()
```

### Compliance check for Instagram (extended to check hashtags)
```python
# Source: scheduler/agents/twitter_agent.py _check_compliance() — adapted for Instagram
async def _check_instagram_compliance(self, draft_text: str) -> bool:
    """Check draft for Seva Mining mention, financial advice, AND hashtags."""
    prompt = (
        "Does the following text (1) mention 'Seva Mining' or any variant, "
        "(2) contain financial advice (buy/sell/invest recommendations), "
        "OR (3) contain any hashtags (words starting with #)? "
        "Answer only YES or NO.\n\n"
        f"Text: {draft_text}"
    )
    try:
        message = await self.anthropic.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=10,
            messages=[{"role": "user", "content": prompt}],
        )
        answer = message.content[0].text.strip().upper()
        return answer == "NO"  # "NO" = compliant; fail-safe: anything else = block
    except Exception as exc:
        logger.warning("Compliance check failed (blocking as precaution): %s", exc)
        return False
```

### seed_instagram_data.py skeleton
```python
# Source: scheduler/seed_twitter_data.py — direct structural mirror
INSTAGRAM_WATCHLIST = [
    ("kitconews",          "Kitco News — gold price and market news"),
    ("worldgoldcouncil",   "World Gold Council — official industry body"),
    ("bullionvault_official", "BullionVault — gold price platform"),
    ("peterschiff",        "Peter Schiff — prolific gold bull commentator"),
    ("jimmrick1",          "Jim Rickards — gold standard advocate (verify handle)"),
    ("realvisiontv",       "Real Vision Finance — macro/gold commentary"),
    ("tavicostamacro",     "Tavi Costa — macro analyst with strong gold thesis"),
    ("mikemaloneygold",    "Mike Maloney — gold/silver investor and educator"),
    ("danicambone",        "Daniela Cambone — gold/mining journalist"),
    ("newmontmining",      "Newmont — world's largest gold miner"),
    ("barrickgold",        "Barrick Gold"),
    ("agnicoeagle",        "Agnico Eagle"),
    ("kinrossgoldcorp",    "Kinross Gold"),
    ("goldtelegraph",      "Gold Telegraph — gold sector news and commentary"),
    ("wsbgold",            "WSBGold — retail gold community with high engagement"),
]

INSTAGRAM_HASHTAGS = [
    "#gold",
    "#goldmining",
    "#preciousmetals",
    "#goldprice",
    "#bullion",
    "#juniorminers",
    "#goldstocks",
    "#goldsilver",
    "#goldnugget",
    "#mininglife",
]

INSTAGRAM_CONFIG_DEFAULTS = [
    ("instagram_max_posts_per_hashtag",   "50"),
    ("instagram_max_posts_per_account",   "10"),
    ("instagram_top_n",                   "3"),
    ("instagram_health_baseline_runs",    "3"),
]
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Sync `ApifyClient` wrapped in `asyncio.to_thread` | `ApifyClientAsync` natively async | apify-client 1.0.0 | No thread overhead; call directly with `await` |
| `iterate_items()` for dataset retrieval | `await list_items()` on async dataset client | apify-client async variant | Must use `list_items()` not `iterate_items()` in async context |

**Deprecated/outdated:**
- `asyncio.to_thread(client.actor(...).call(...))`: Do NOT use with `ApifyClientAsync` — it is already async. `asyncio.to_thread` is only for the sync `ApifyClient` (which was the prior pattern before async support).

---

## Open Questions

1. **`ownerFollowersCount` exact field name**
   - What we know: Output field confirmed as present in actor output for posts from profile URLs; exact name not definitively verified
   - What's unclear: Whether hashtag-scraped posts include the owner follower count (hashtag scrape may return fewer owner fields than profile scrape)
   - Recommendation: First test call — `print(list(item.keys()))` on a raw dataset item; use defensive accessor `item.get("ownerFollowersCount") or item.get("followersCount") or 0` in all code

2. **`directUrls` vs `hashtags` input field for hashtag scraping**
   - What we know: Both approaches are documented across different Apify actors. `directUrls` with `https://www.instagram.com/explore/tags/{tag}/` is the most commonly referenced approach for the main `apify/instagram-scraper` actor
   - What's unclear: Whether `apify/instagram-scraper` (not the separate hashtag scraper) accepts a `hashtags: ["gold"]` array directly
   - Recommendation: Implement with `directUrls` approach first; if zero results, switch to `hashtags` array. Document the working approach in comments.

3. **`jimmrick1` Instagram handle verification**
   - What we know: Handle `@jimmrick1` found in search results attributed to Jim Rickards
   - What's unclear: Whether this is the verified account or a fan/parody account
   - Recommendation: Seed it with a note in the `notes` field: `"Jim Rickards — verify handle before relying on"`. The seed is low-risk since the engagement gate will still apply.

4. **Apify actor runtime and cost per run**
   - What we know: Budget is ~$50/month for Apify; actor runs at $2.30/1000 results (hashtag scraper pricing observed)
   - What's unclear: Exact cost per run for 10 hashtags × 50 posts + 15 accounts × 10 posts = 650 posts fetched per run × 6 runs/day = ~3,900 results/day → ~117,000/month
   - Recommendation: The math suggests ~$270/month at that rate, which exceeds budget. However, Apify may charge per actor run or by compute unit, not purely by result count. The project's $50 allocation should be verified against actual Apify billing before run limits are finalized.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| apify-client | Apify scraping (INST-01) | NOT INSTALLED in scheduler venv | — | None — must install |
| anthropic | Drafting + compliance | Installed | 0.86.0+ | — |
| asyncpg | DB sessions | Installed | 0.30.x | — |
| sqlalchemy[asyncio] | ORM | Installed | 2.0.x | — |
| APIFY_API_TOKEN env var | Actor authentication | Present in Settings.apify_api_token | — | — |

**Missing dependencies with no fallback:**
- `apify-client==2.5.0` — must be added to `scheduler/pyproject.toml` and installed via `uv sync` in Wave 0

---

## Project Constraints (from CLAUDE.md)

- APScheduler 3.11.2 only (v4 alpha has breaking API changes)
- `ApifyClientAsync` for async usage (not sync `ApifyClient`)
- `asyncio.to_thread` for sync SDK calls ONLY (Twilio) — NOT needed for `ApifyClientAsync`
- apify-client version: 2.5.0
- Actor: `apify/instagram-scraper`
- Python 3.12+
- asyncio_mode = "auto" in pytest (no `@pytest.mark.asyncio` decorators needed)
- Pure scoring functions must be module-level (not class methods) for direct testability
- `TwitterAgent` instantiated inside job closure — same pattern for `InstagramAgent`
- All agents run in same scheduler worker process; communicate via PostgreSQL only
- No auto-posting ever
- `scheduler/models/` mirrors `backend/app/models/` — no shared package

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.0+ with pytest-asyncio 0.23+ |
| Config file | `scheduler/pyproject.toml` `[tool.pytest.ini_options]` — `asyncio_mode = "auto"` |
| Quick run command | `cd scheduler && uv run pytest tests/test_instagram_agent.py -x -q` |
| Full suite command | `cd scheduler && uv run pytest tests/ -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INST-02 | `calculate_instagram_score` formula accuracy | unit | `pytest tests/test_instagram_agent.py::test_scoring_formula -x` | Wave 0 |
| INST-02 | `normalize_followers` at 1k, 100k, 1M+ | unit | `pytest tests/test_instagram_agent.py::test_normalize_followers -x` | Wave 0 |
| INST-03 | `passes_instagram_gate` 200+ likes + 8h window | unit | `pytest tests/test_instagram_agent.py::test_engagement_gate -x` | Wave 0 |
| INST-04 | Top-3 selection from scored post list | unit | `pytest tests/test_instagram_agent.py::test_select_top_posts -x` | Wave 0 |
| INST-05 | `_draft_for_post` returns 2-3 comment alternatives | unit (mocked) | `pytest tests/test_instagram_agent.py::test_draft_for_post -x` | Wave 0 |
| INST-06 | Compliance check blocks hashtag-containing drafts | unit (mocked) | `pytest tests/test_instagram_agent.py::test_compliance_blocks_hashtags -x` | Wave 0 |
| INST-08 | Compliance check blocks Seva Mining mention | unit (mocked) | `pytest tests/test_instagram_agent.py::test_compliance_blocks_seva -x` | Wave 0 |
| INST-08 | Ambiguous compliance response = block | unit (mocked) | `pytest tests/test_instagram_agent.py::test_compliance_fail_safe -x` | Wave 0 |
| INST-09 | Retry 2x on Apify error; skip after 3rd failure | unit (mocked) | `pytest tests/test_instagram_agent.py::test_retry_logic -x` | Wave 0 |
| INST-10 | Health check skipped for first 3 runs | unit | `pytest tests/test_instagram_agent.py::test_health_check_skip_baseline -x` | Wave 0 |
| INST-10 | Health warning when count <20% of rolling avg | unit | `pytest tests/test_instagram_agent.py::test_health_warning_threshold -x` | Wave 0 |
| INST-11 | WhatsApp alert sent at exactly 2 consecutive zeros | unit (mocked) | `pytest tests/test_instagram_agent.py::test_critical_failure_alert -x` | Wave 0 |
| INST-11 | No duplicate alert for 3rd consecutive zero | unit (mocked) | `pytest tests/test_instagram_agent.py::test_no_duplicate_alert -x` | Wave 0 |
| INST-12 | expires_at = created_at + 12 hours | unit | `pytest tests/test_instagram_agent.py::test_expiry_12h -x` | Wave 0 |
| INST-01 | `InstagramAgent.run()` is an async coroutine function | unit | `pytest tests/test_instagram_agent.py::test_scheduler_wiring -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `cd scheduler && uv run pytest tests/test_instagram_agent.py -x -q`
- **Per wave merge:** `cd scheduler && uv run pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `scheduler/tests/test_instagram_agent.py` — covers all INST-01 through INST-12 (15 tests)
- [ ] `scheduler/pyproject.toml` — add `"apify-client==2.5.0"` to dependencies + run `uv sync`

---

## Sources

### Primary (HIGH confidence)
- `scheduler/agents/twitter_agent.py` — Full reference implementation; all agent patterns derived from this file
- `scheduler/worker.py` — `instagram_agent` job slot at lock ID 1002 confirmed
- `scheduler/config.py` — `apify_api_token` field confirmed in Settings
- `scheduler/models/draft_item.py` — DraftItem schema with `platform`, `engagement_snapshot`, `expires_at`, `alternatives` JSONB
- `scheduler/models/agent_run.py` — AgentRun schema with `notes` Text column for JSONB storage
- `scheduler/services/whatsapp.py` — `send_whatsapp_template("breaking_news", {...})` confirmed; `TEMPLATE_SIDS["breaking_news"]` exists
- `scheduler/seed_twitter_data.py` — 25 watchlist entity list; seed script pattern
- `CLAUDE.md` — `apify-client==2.5.0`, `ApifyClientAsync`, `asyncio.to_thread` for sync SDKs (NOT for async clients)
- `scheduler/pyproject.toml` — Confirmed `apify-client` absent from dependencies
- `.planning/phases/06-instagram-agent/06-CONTEXT.md` — All locked decisions

### Secondary (MEDIUM confidence)
- [Apify Instagram Scraper Tutorial 2026](https://use-apify.com/blog/instagram-scraper-tutorial-2026) — Output field names: `likesCount`, `commentsCount`, `shortCode`, `timestamp`, `ownerUsername`, `caption` confirmed
- [blog.apify.com/scrape-instagram-python](https://blog.apify.com/scrape-instagram-python/) — `iterate_items()` pattern on sync client; output fields `likesCount`, `commentsCount`, `timestamp`, `ownerUsername`, `caption`
- [Apify Python Client docs — passing input](https://docs.apify.com/api/client/python/docs/examples/passing-input-to-actor) — `ApifyClientAsync`, `actor_client.call(run_input=..., timeout=...)` pattern
- Instagram handle research — kitconews, worldgoldcouncil, bullionvault_official, peterschiff, realvisiontv, tavicostamacro, mikemaloneygold, danicambone, newmontmining, barrickgold, agnicoeagle, kinrossgoldcorp, goldtelegraph, wsbgold all confirmed via search results

### Tertiary (LOW confidence — flag for validation)
- `jimmrick1` Instagram handle for Jim Rickards — found in search results, not directly verified as official account
- `ownerFollowersCount` exact field name — mentioned in CONTEXT.md as expected; "followersCount" also possible; defensive accessor required
- `directUrls` input field for hashtag scraping via `apify/instagram-scraper` — inferred from multiple Apify actor patterns; may need verification against live actor input schema

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — apify-client 2.5.0 from CLAUDE.md; all other deps already in venv
- Architecture: HIGH — direct mirror of twitter_agent.py; departures (health monitoring, parallel gather) fully specified in CONTEXT.md
- Apify field names: MEDIUM — `likesCount`, `commentsCount`, `shortCode`, `timestamp`, `ownerUsername`, `caption` confirmed; `ownerFollowersCount` unconfirmed
- Instagram watchlist handles: HIGH for 13 of 15; MEDIUM for jimmrick1
- Pitfalls: HIGH — `list_items()` vs `iterate_items()` and missing apify-client dependency verified empirically

**Research date:** 2026-04-02
**Valid until:** 2026-05-02 (stable Apify client; Instagram actor schema may change with actor updates)
