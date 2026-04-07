# Phase 7: Content Agent - Research

**Researched:** 2026-04-02
**Domain:** RSS ingestion, SerpAPI news search, BeautifulSoup article extraction, Claude two-model pipeline, APScheduler job wiring, ContentBundle persistence
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Phase Boundary:**
Build the Content Agent: a daily 6am APScheduler job that ingests RSS feeds + SerpAPI news, deduplicates by URL and headline similarity, scores stories, selects the single highest-scoring story above 7.0/10, conducts a multi-step deep research pass, decides on a content format, drafts the content, runs compliance checking, and delivers a `ContentBundle` to the Senior Agent — or creates a `ContentBundle` with `no_story_flag=True` when nothing qualifies.

This phase does NOT include: dashboard rendering, infographic image generation, Settings page wiring, or frontend work. Those are Phase 8.

**Infographic Generation (CONT-12):**
- Produces structured JSON data, NOT an image file. Phase 8 renders the visual.
- `draft_content` structure: `{"format": "infographic", "headline": "...", "key_stats": [{"stat": "...", "source": "...", "source_url": "..."}, ...], "visual_structure": "bar chart", "caption_text": "..."}`
- 5-8 key stats with stat text + source citation
- Visual structure: Claude picks from `["bar chart", "timeline", "comparison table", "stat callouts", "map"]`
- Caption text: full caption, senior analyst voice, suitable for X or Instagram

**Format Decision Logic (CONT-09, CONT-10):**
- Claude decides after reading full research summary
- `"thread"` → BOTH tweet thread (3-5 tweets ≤ 280 chars each) AND long-form X post (≤ 2,200 chars): `{"format": "thread", "tweets": [...], "long_form_post": "..."}`
- `"long_form"` → single X post ≤ 2,200 chars: `{"format": "long_form", "post": "..."}`
- `"infographic"` → structured brief (see above)
- Format decision is made AFTER deep research

**Deep Research Approach (CONT-08):**
- Full article fetch: `httpx` GET + `BeautifulSoup` text extraction
- Fall back to RSS summary if fetch fails (paywall, 403, JS-rendered). Log warning to `AgentRun.errors`.
- Corroborating sources: SerpAPI Google News, 2-3 results, same client as ingest
- `deep_research` JSONB: `{"article_text": "...", "article_fetch_succeeded": true, "corroborating_sources": [...], "key_data_points": [...]}`
- Key data point extraction done in the same combined Claude Sonnet prompt

**Story Scoring (CONT-05):**
- Relevance to gold/mining: 40% (Claude Haiku, 0–1 scale). Config key: `content_relevance_weight` (default `"0.40"`)
- Recency: 30% (linear decay: <3h=1.0, <6h=0.8, <12h=0.6, <24h=0.4, ≥24h=0.2). Config key: `content_recency_weight` (default `"0.30"`)
- Source credibility tier: 30% (reuters/bloomberg=1.0, worldgoldcouncil.org=0.9, kitco/mining.com=0.8, juniorminingnetwork.com=0.7, unknown=0.4). Config key: `content_credibility_weight` (default `"0.30"`)
- Final score: `(relevance × 0.40 + recency × 0.30 + credibility × 0.30) × 10` → 0–10 scale
- Quality threshold: 7.0/10. Config key: `content_quality_threshold` (default `"7.0"`)

**No-Story Flag (CONT-07):**
- Create `ContentBundle` with `no_story_flag=True`, `story_headline="No qualifying story today"`, `score=best_candidate_score`, all other fields null
- Log best candidate headline + score to `AgentRun.notes`
- Do NOT call `process_new_items` — no DraftItem created

**RSS Feeds (CONT-02):**
- Kitco News: `https://www.kitco.com/rss/news.xml`
- Mining.com: `https://www.mining.com/feed/`
- Junior Mining Network: `https://www.juniorminingnetwork.com/feed`
- World Gold Council: `https://www.gold.org/goldhub/news/feed`

**SerpAPI Keywords (CONT-03):**
- 6 keywords: "gold exploration", "gold price", "central bank gold", "gold ETF", "junior miners", "gold reserves"
- `engine=google_news`, top 5 results per keyword
- Up to 30 articles from SerpAPI per run

**Deduplication (CONT-04):**
- Step 1: URL exact match
- Step 2: `difflib.SequenceMatcher` ratio ≥ 0.85 — keep more credible source (or earlier if same tier)
- `difflib` is Python stdlib, no additional dep

**Senior Agent Integration (CONT-17):**
- Create `DraftItem` with `platform="content"`, `source_text=story_headline`, `source_url=story_url`, `source_account=source_name`, `alternatives=json.dumps([draft summary])`, `rationale=format decision rationale`, `score=content_bundle.score`, `expires_at=None`, `urgency="low"`
- Call `process_new_items([draft_item.id])` via lazy import
- Store `ContentBundle.id` in `DraftItem.engagement_snapshot` as `{"content_bundle_id": "..."}` (no FK yet)

**Compliance Checking (CONT-14, CONT-15, CONT-16):**
- Separate Claude Haiku call on complete content package
- Checks: no "Seva Mining" mention, no financial advice
- Ambiguous response = block (fail-safe)
- If fails: log to `AgentRun.errors`, set `ContentBundle.compliance_passed=False`, do NOT create DraftItem

**New Dependencies Required:**
- `feedparser>=6.0` — not yet in `scheduler/pyproject.toml`
- `httpx>=0.27` — already in `uv.lock` (v0.28.1) as transitive dep via anthropic SDK; must be added explicitly to `pyproject.toml` as direct dep
- `beautifulsoup4>=4.12` — not yet in `scheduler/pyproject.toml`
- `serpapi>=0.1.5` — not yet in `scheduler/pyproject.toml`

**Claude's Discretion:**
- Exact BeautifulSoup selector logic for main content extraction (use `article`, `main`, or `div.content` tags; strip `nav`, `header`, `footer`, `aside`)
- SerpAPI response parsing (field names: `title`, `link`, `snippet`, `source.name`, `iso_date`)
- Exact Claude Haiku prompt for relevance scoring
- Exact Claude Sonnet prompt for deep research + format decision + drafting (single combined prompt recommended)
- Config key naming convention (follow `content_*` prefix)
- `AgentRun.notes` JSONB structure for storing run stats

### Deferred Ideas (OUT OF SCOPE)
- Actual image file generation — Phase 8's job
- SerpAPI `result_position` as engagement proxy — replaced by source credibility tier
- ContentBundle–DraftItem FK in schema — use `engagement_snapshot` JSONB for now
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CONT-01 | Agent runs daily at 6am, pulling new content from all sources since last run | APScheduler cron job already registered at lock ID 1003; replace placeholder in `worker.py` with `ContentAgent().run()` |
| CONT-02 | RSS ingestion from Kitco, Mining.com, JMN, World Gold Council | `feedparser.parse(url)` — synchronous; run in executor to avoid blocking async loop |
| CONT-03 | SerpAPI news search with 6 gold-sector keywords | `serpapi.Client(api_key=...).search({"engine": "google_news", "q": keyword, "num": 5})` |
| CONT-04 | Deduplication by URL and headline similarity (85% threshold) | URL set dedup + `difflib.SequenceMatcher(None, h1, h2).ratio() >= 0.85` |
| CONT-05 | Story scoring: relevance 40%, recency 30%, credibility 30% | Claude Haiku relevance call + linear recency decay + credibility tier dict |
| CONT-06 | Quality threshold 7.0/10 — single highest-scoring story selected | Sort by final score desc, check `score >= threshold`, take `[0]` |
| CONT-07 | No-story flag when nothing clears threshold | `ContentBundle(no_story_flag=True, story_headline="No qualifying story today", score=best)` |
| CONT-08 | Deep research: full article + 2-3 corroborating sources + key data points | `httpx.AsyncClient().get(url)` + `BeautifulSoup(html).get_text()` + SerpAPI corroboration |
| CONT-09 | Format decision: long_form / thread / infographic — decided by Claude after research | Single Claude Sonnet prompt with full research bundle; Claude picks format with rationale |
| CONT-10 | Thread format: tweet thread (3-5 ≤280 chars) AND long-form X post (≤2,200 chars) | Included in same Sonnet drafting prompt; validated by character count check |
| CONT-11 | Infographic brief: headline, 5-8 key stats, visual structure, caption | Part of Sonnet drafting prompt when format=infographic |
| CONT-12 | Infographic generation = structured JSON brief only (Phase 8 renders) | Stored in `draft_content` JSONB; no image generation |
| CONT-13 | Senior analyst voice — data-driven, cites specifics | System prompt directive; validated by compliance check |
| CONT-14 | No mention of Seva Mining in any content | Compliance check pre-screen + Claude Haiku call |
| CONT-15 | No financial advice in any content | Compliance check Claude Haiku call |
| CONT-16 | Separate Claude compliance-checker call on all content | Same fail-safe pattern as Instagram/Twitter agents |
| CONT-17 | Content packaged with sources + credibility score, sent to Senior Agent | `DraftItem` created + `process_new_items` lazy import; `engagement_snapshot` links back to `ContentBundle.id` |
</phase_requirements>

---

## Summary

Phase 7 builds the Content Agent: the system's daily-publishing pipeline. Unlike the Twitter and Instagram agents (which react to social content), this agent proactively discovers, researches, and drafts original gold-sector content from scratch. The pipeline is longer than previous agents — ingest, deduplicate, score, deep-research, draft, comply, persist — but the patterns are nearly identical to what already exists in `instagram_agent.py`.

The critical difference is complexity: the Content Agent makes multiple Claude calls (Haiku for scoring, Sonnet for combined research+format+drafting, Haiku for compliance) and produces a richer data structure (`ContentBundle`) instead of simple comment alternatives. The deep research step introduces two new I/O boundaries — `httpx` article fetch and SerpAPI corroboration — that need proper error isolation.

The new dependencies (`feedparser`, `serpapi`, `beautifulsoup4`) are all stable, battle-tested libraries with simple APIs. `httpx` is already present in the lock file as a transitive dep and just needs to be declared explicit in `pyproject.toml`. The `ContentBundle` model already exists in the backend; a scheduler mirror needs to be created.

**Primary recommendation:** Mirror the `InstagramAgent` structure exactly — module-level pure functions for testability, two-Claude pattern, lazy senior agent import, AgentRun logging with `try/except/finally`. The only genuinely new work is the multi-step deep research and the combined Sonnet prompt for format+draft.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| feedparser | 6.0.12 (PyPI current) | RSS/Atom ingestion | Python stdlib for feeds for 15+ years; handles malformed RSS, all versions, character encoding. Zero config. |
| serpapi | 1.0.2 (PyPI current) | SerpAPI Python client | Official client. `serpapi.Client(api_key=...).search({...})`. Synchronous; run in executor. |
| httpx | 0.28.1 (already in uv.lock) | Async HTTP for article fetch | Already present as anthropic SDK transitive dep; just needs explicit `pyproject.toml` entry. `AsyncClient` pairs naturally with async pipeline. |
| beautifulsoup4 | 4.14.3 (PyPI current) | HTML article text extraction | Standard for HTML parsing in Python. `bs4.BeautifulSoup(html, "html.parser")` — no lxml needed, avoids extra dep. |
| difflib | stdlib | Headline deduplication | Python stdlib `SequenceMatcher` — no dep needed. |
| anthropic | 0.86.0 (already in pyproject.toml) | Claude API (Haiku + Sonnet) | Already present. `AsyncAnthropic` client. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| lxml | 6.0.2 (PyPI current) | Faster BS4 parser | Only add if html.parser proves too slow or fails on specific feeds. Adds a C extension dep. Overkill for 4 RSS feeds + ~30 SerpAPI articles. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| feedparser | aiohttp + manual XML parsing | feedparser handles malformed RSS/Atom, character encoding, multiple versions. No reason to hand-roll. |
| beautifulsoup4 | trafilatura / newspaper3k | trafilatura is more opinionated about "main content" extraction but adds a heavy dep tree. BS4 + selector logic is sufficient for the volume here. |
| serpapi client | httpx direct to SerpAPI | serpapi client is 10 lines; direct httpx works but gains nothing. |

**Installation (new deps only — add to `scheduler/pyproject.toml`):**
```bash
cd scheduler
uv add "feedparser>=6.0" "beautifulsoup4>=4.12" "serpapi>=1.0" "httpx>=0.27"
```

Note: `httpx>=0.27` is already in `uv.lock` at 0.28.1 via the anthropic SDK. Adding it explicitly makes it a declared direct dep (correct practice) rather than relying on a transitive dep.

**Version verification (confirmed 2026-04-02 from PyPI):**
- feedparser 6.0.12 (released Sep 2025)
- serpapi 1.0.2
- beautifulsoup4 4.14.3
- httpx 0.28.1 (already installed)

---

## Architecture Patterns

### Recommended Project Structure
```
scheduler/
├── agents/
│   └── content_agent.py         # New: ContentAgent class + module-level functions
├── models/
│   └── content_bundle.py        # New: mirror of backend/app/models/content_bundle.py
├── tests/
│   └── test_content_agent.py    # New: Wave 0 stubs → implementation tests
└── seed_content_data.py         # New: seed config defaults (mirrors seed_instagram_data.py)
```

### Pattern 1: Agent Class Structure (mirrors instagram_agent.py exactly)
**What:** Class with `run()` entry point → `_run_pipeline()` → steps. Module-level pure functions for testability.
**When to use:** All agents in this codebase.
**Example:**
```python
# Source: scheduler/agents/instagram_agent.py (established pattern)
class ContentAgent:
    def __init__(self) -> None:
        settings = get_settings()
        self.anthropic = AsyncAnthropic(api_key=settings.anthropic_api_key)
        # serpapi.Client is synchronous — instantiate here, run in executor

    async def run(self) -> None:
        async with AsyncSessionLocal() as session:
            agent_run = AgentRun(
                agent_name="content_agent",
                status="running",
                started_at=datetime.now(timezone.utc),
                items_found=0,
                items_queued=0,
                items_filtered=0,
            )
            session.add(agent_run)
            await session.commit()
            try:
                await self._run_pipeline(session, agent_run)
                agent_run.status = "completed"
            except Exception as exc:
                agent_run.status = "failed"
                agent_run.errors = str(exc)
                logger.error("ContentAgent run failed: %s", exc, exc_info=True)
            finally:
                agent_run.ended_at = datetime.now(timezone.utc)
                await session.commit()
```

### Pattern 2: Two-Claude Model Split
**What:** Claude Haiku for fast/cheap classification (relevance scoring, compliance); Claude Sonnet for quality reasoning (format decision + full drafting).
**When to use:** Any pipeline needing both cost efficiency and drafting quality.
**Example:**
```python
# Source: scheduler/agents/instagram_agent.py (check_compliance uses Haiku)
# Relevance scoring — Haiku (fast, cheap, scalar output)
model="claude-haiku-3-20240307"
# Deep research + format + drafting — Sonnet (combined to save API calls)
model="claude-sonnet-4-20250514"
```

### Pattern 3: Synchronous Library in Async Pipeline
**What:** `feedparser.parse()` and `serpapi.Client().search()` are synchronous. Run them in the executor to avoid blocking the async event loop.
**When to use:** Any sync I/O inside an async function.
**Example:**
```python
# Source: established Python asyncio pattern
import asyncio

async def _fetch_rss(self, url: str) -> list[dict]:
    loop = asyncio.get_event_loop()
    feed = await loop.run_in_executor(None, feedparser.parse, url)
    return feed.entries

async def _search_serpapi(self, query: str, client) -> list[dict]:
    loop = asyncio.get_event_loop()
    def _call():
        return client.search({"engine": "google_news", "q": query, "num": 5})
    results = await loop.run_in_executor(None, _call)
    return results.get("news_results", [])
```

### Pattern 4: feedparser Entry Fields
**What:** feedparser normalizes RSS/Atom entry fields to a consistent dict-like structure.
**When to use:** Extracting story data from feed entries.
```python
# Source: feedparser docs (HIGH confidence — official library behavior)
for entry in feed.entries:
    title = entry.get("title", "")
    link = entry.get("link", "")
    published = entry.get("published_parsed")  # time.struct_time or None
    summary = entry.get("summary", "")         # RSS description / Atom summary
    # Convert published_parsed to datetime:
    # datetime(*published[:6], tzinfo=timezone.utc) if published else None
```

### Pattern 5: SerpAPI Google News Response Fields
**What:** Google News search returns `news_results` list with title, link, source.name, snippet, iso_date.
**When to use:** SerpAPI corroboration + ingest.
```python
# Source: SerpAPI Google News API docs (HIGH confidence — official docs verified)
results = client.search({"engine": "google_news", "q": "gold price", "num": 5})
for item in results.get("news_results", []):
    title = item.get("title", "")
    link = item.get("link", "")
    source_name = (item.get("source") or {}).get("name", "unknown")
    snippet = item.get("snippet", "")
    iso_date = item.get("iso_date")  # "2024-11-12T07:09:00Z" or None
```

### Pattern 6: BeautifulSoup Main Content Extraction
**What:** Prioritize semantic tags, strip boilerplate.
**When to use:** Extracting article body from full HTML.
```python
# Source: Claude's discretion (established BS4 pattern)
from bs4 import BeautifulSoup

def extract_article_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    # Strip boilerplate
    for tag in soup.find_all(["nav", "header", "footer", "aside", "script", "style"]):
        tag.decompose()
    # Try semantic main content tags in priority order
    for selector in ["article", "main", "[role='main']", "div.content", "div.article-body"]:
        node = soup.select_one(selector)
        if node:
            return node.get_text(separator=" ", strip=True)
    # Fallback: full body text
    return soup.get_text(separator=" ", strip=True)
```

### Pattern 7: ContentBundle Model Mirror
**What:** `scheduler/models/content_bundle.py` must mirror `backend/app/models/content_bundle.py`. Scheduler has no access to the backend package.
**When to use:** All new models needed by scheduler agents.
```python
# Source: backend/app/models/content_bundle.py (must mirror exactly)
# scheduler/models/content_bundle.py imports from models.base (not app.models.base)
from models.base import Base  # scheduler base, not backend base
```

### Pattern 8: Worker.py Integration
**What:** Replace placeholder in `_make_job` with `ContentAgent().run()` for `content_agent`.
**When to use:** Wiring a new agent to the scheduler.
```python
# Source: scheduler/worker.py lines 113-130 (existing pattern to mirror)
elif job_name == "content_agent":
    agent = ContentAgent()
    await with_advisory_lock(
        conn,
        JOB_LOCK_IDS[job_name],
        job_name,
        agent.run,
    )
```
Also add import: `from agents.content_agent import ContentAgent`

### Anti-Patterns to Avoid
- **Calling `feedparser.parse()` directly in async code without executor:** Blocks the event loop during DNS resolution + download.
- **Using `requests` for article fetch:** Blocks the event loop. Use `httpx.AsyncClient`.
- **Assuming feedparser `published_parsed` is always present:** Some feeds omit dates. Guard with `if entry.get("published_parsed")`.
- **Not guarding against None from SerpAPI `news_results`:** The key may be absent if the API returns an error response. Always `.get("news_results", [])`.
- **Calling `serpapi.Client` inside async code without executor:** `serpapi.Client.search()` is synchronous and will block.
- **Creating `serpapi.Client` per-call:** Instantiate once in `__init__`, reuse.
- **Assuming httpx article fetch succeeds:** Many gold news sites are paywalled (Bloomberg, Reuters). Must catch `httpx.HTTPError`, `httpx.TimeoutException`, and any non-200 status. Fall back to RSS summary.
- **Re-raising exceptions from `_run_pipeline`:** Worker uses error isolation — log to `AgentRun.errors`, never re-raise from individual steps (EXEC-04).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| RSS parsing | Custom XML parser | `feedparser` | Handles RSS 0.9/1.0/2.0, Atom, malformed feeds, encoding, date normalization |
| Headline fuzzy matching | Custom string similarity | `difflib.SequenceMatcher` (stdlib) | No dep needed; well-tested; 0.85 threshold is straightforward |
| Article body extraction | Custom regex-based HTML parser | `BeautifulSoup` | Handles malformed HTML, entity decoding, nested tag removal |
| News search | Manual SerpAPI HTTP calls | `serpapi` client | Official client with error types; 10 lines vs hand-rolled JSON parsing |
| Async HTTP | `requests` | `httpx.AsyncClient` | `requests` blocks event loop |

**Key insight:** All the genuinely complex parts of this agent (the research pipeline logic, the scoring formula, the combined Claude prompt) are unique to this system and must be written. The plumbing libraries (feedparser, httpx, bs4, serpapi) are commodity — don't invent alternatives.

---

## Runtime State Inventory

> Applies partially: new agent introduces new Config keys but no rename/migration.

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | No existing ContentBundle records; `content_bundles` table exists from Phase 1 schema | None — table is empty, no migration |
| Live service config | No `content_*` Config keys in DB yet | Seed script must insert 4 config defaults at Phase 7 deploy |
| OS-registered state | APScheduler `content_agent` job already registered in `worker.py` at lock ID 1003 with daily 6am cron | Replace placeholder in `_make_job` — no scheduler config change |
| Secrets/env vars | `serpapi_api_key` already in `Settings` and `config.py` | None — key exists, just needs to be set in Railway env if not already |
| Build artifacts | `feedparser`, `beautifulsoup4`, `serpapi` not yet in `scheduler/pyproject.toml` | `uv add` these packages; `uv.lock` will update |

**Config keys to seed in `seed_content_data.py`:**
- `content_relevance_weight` = `"0.40"`
- `content_recency_weight` = `"0.30"`
- `content_credibility_weight` = `"0.30"`
- `content_quality_threshold` = `"7.0"`

---

## Common Pitfalls

### Pitfall 1: feedparser is Synchronous
**What goes wrong:** Calling `feedparser.parse(url)` inside an `async def` blocks the event loop for the duration of the HTTP request (can be 1-5 seconds per feed; 4 feeds = up to 20 seconds of blocking).
**Why it happens:** feedparser uses `urllib` internally, which is blocking.
**How to avoid:** Always use `await loop.run_in_executor(None, feedparser.parse, url)`.
**Warning signs:** Tests pass but production agent delays other scheduler jobs.

### Pitfall 2: serpapi Client is Also Synchronous
**What goes wrong:** Same as feedparser — `client.search({...})` blocks the event loop. With 6 keyword searches, this can block for 6-30 seconds.
**Why it happens:** `serpapi.Client.search()` uses `requests` internally.
**How to avoid:** Wrap each call in `run_in_executor`. Run all 6 keyword searches concurrently using `asyncio.gather()` with executor wrappers.
**Warning signs:** Agent runs take far longer than expected.

### Pitfall 3: httpx Article Fetch Failures Are the Norm, Not the Exception
**What goes wrong:** Bloomberg, Reuters, Financial Times URLs return 403 or redirect to paywall. Treating this as an error causes the agent to drop valid stories.
**Why it happens:** Most premium news sources block scrapers. The story is still valid — the RSS headline + snippet contain enough signal.
**How to avoid:** Catch `httpx.HTTPStatusError` (non-200), `httpx.TimeoutException`, and all `httpx.HTTPError`. Log warning to `AgentRun.errors`. Set `article_fetch_succeeded=False` in `deep_research` JSONB. Continue with RSS summary.
**Warning signs:** High-credibility sources (Reuters, Bloomberg) never produce full article text.

### Pitfall 4: feedparser `published_parsed` Missing or in Local Time
**What goes wrong:** Some feeds omit publish dates; others provide them in local time without timezone info. Recency scoring breaks with `None` dates or wrong time offsets.
**Why it happens:** RSS spec makes `pubDate` optional. feedparser normalizes to UTC `time.struct_time` when possible but not always.
**How to avoid:** Guard: `if entry.get("published_parsed"): datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)`. Fall back to `datetime.now(timezone.utc)` (assumes fresh = recent, acceptable bias).
**Warning signs:** Stories with no publish date get full recency score (1.0) when using `now()` fallback — acceptable but document the choice.

### Pitfall 5: SerpAPI Quota
**What goes wrong:** 6 keywords × top 5 results = 6 searches/day × 30 days = 180 searches/month. Plus 2-3 corroboration searches per run = +60-90/month. Total: ~270/month. SerpAPI basic plan is 100 searches/month — this overruns basic by 2.7x.
**Why it happens:** SerpAPI pricing requires a paid plan above the free tier.
**How to avoid:** Per STATE.md blocker note: "SerpAPI plan selection needed before Content Agent — 100 searches/mo on basic plan may be insufficient." Flag in open questions. The plan needs to confirm they're on the Developer plan (5,000 searches/month).
**Warning signs:** `serpapi.HTTPError` with 429 status during runs.

### Pitfall 6: difflib Headline Comparison Case Sensitivity
**What goes wrong:** "Gold Hits $3,200" and "gold hits $3,200" score 0.75 similarity instead of 1.0, missing an obvious duplicate.
**Why it happens:** `SequenceMatcher` is case-sensitive by default.
**How to avoid:** Normalize to lowercase before comparison: `SequenceMatcher(None, h1.lower(), h2.lower()).ratio()`.
**Warning signs:** Obvious duplicates making it through deduplication with different capitalizations.

### Pitfall 7: ContentBundle Model Import Path in Scheduler
**What goes wrong:** Importing `from backend.app.models.content_bundle import ContentBundle` fails — the scheduler process has no access to the backend package.
**Why it happens:** Scheduler and backend are separate Python packages. STATE.md confirms: "scheduler/models/ mirrors backend/app/models/ — scheduler has no access to backend package."
**How to avoid:** Create `scheduler/models/content_bundle.py` as a mirror. Import `from models.base import Base` (scheduler base), not `from app.models.base import Base`.
**Warning signs:** `ModuleNotFoundError: No module named 'app'` at agent import time.

### Pitfall 8: Combined Sonnet Prompt Token Budget
**What goes wrong:** The combined prompt (full article text + 2-3 corroborating snippets + key data extraction + format decision + full draft) can exceed 4,000 tokens input easily for long articles. If the article fetch returns the full page HTML text, it can be enormous.
**Why it happens:** No truncation on article text before passing to Claude.
**How to avoid:** Truncate `article_text` to ~3,000 characters before including in the Claude prompt. The key data points matter more than verbatim full text.
**Warning signs:** High Claude API costs, slow Sonnet calls, occasional `max_tokens` errors.

---

## Code Examples

Verified patterns from official sources and existing codebase:

### feedparser: Parse RSS Feed (in executor)
```python
# Source: feedparser official docs + asyncio.run_in_executor pattern
import asyncio
import feedparser

async def _fetch_rss_feed(url: str) -> list[dict]:
    loop = asyncio.get_event_loop()
    feed = await loop.run_in_executor(None, feedparser.parse, url)
    stories = []
    for entry in feed.entries:
        published = None
        if entry.get("published_parsed"):
            from datetime import datetime, timezone
            published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        stories.append({
            "title": entry.get("title", ""),
            "url": entry.get("link", ""),
            "summary": entry.get("summary", ""),
            "published_at": published,
            "source_name": feed.feed.get("title", ""),
            "source_url": url,
        })
    return stories
```

### SerpAPI: Google News Search (in executor)
```python
# Source: SerpAPI Python docs + Google News API docs (verified 2026-04-02)
import serpapi
import asyncio

async def _search_news(query: str, client: serpapi.Client, num: int = 5) -> list[dict]:
    loop = asyncio.get_event_loop()
    def _call():
        return client.search({"engine": "google_news", "q": query, "num": num})
    results = await loop.run_in_executor(None, _call)
    stories = []
    for item in results.get("news_results", []):
        source = item.get("source") or {}
        stories.append({
            "title": item.get("title", ""),
            "url": item.get("link", ""),
            "snippet": item.get("snippet", ""),
            "source_name": source.get("name", "unknown"),
            "iso_date": item.get("iso_date"),
        })
    return stories
```

### httpx: Article Fetch with Fallback
```python
# Source: httpx docs + established pattern
import httpx

async def _fetch_article_text(url: str) -> tuple[str, bool]:
    """Returns (text, fetch_succeeded). Falls back to empty string on failure."""
    headers = {"User-Agent": "Mozilla/5.0 (compatible; SevaBot/1.0)"}
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            return resp.text, True
    except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.HTTPError):
        return "", False
```

### BeautifulSoup: Extract Main Content
```python
# Source: BeautifulSoup docs + Claude's discretion (CONT-08)
from bs4 import BeautifulSoup

def extract_main_content(html: str, max_chars: int = 3000) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(["nav", "header", "footer", "aside", "script", "style"]):
        tag.decompose()
    for selector in ["article", "main", "[role='main']", "div.content", "div.article-body"]:
        node = soup.select_one(selector)
        if node:
            text = node.get_text(separator=" ", strip=True)
            return text[:max_chars]
    return soup.get_text(separator=" ", strip=True)[:max_chars]
```

### Recency Score Function
```python
# Source: CONTEXT.md scoring spec (locked decision)
from datetime import datetime, timezone

def calculate_recency_score(published_at: datetime | None) -> float:
    if published_at is None:
        return 0.4  # treat as ~24h old
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)
    age_hours = (datetime.now(timezone.utc) - published_at).total_seconds() / 3600.0
    if age_hours < 3:
        return 1.0
    elif age_hours < 6:
        return 0.8
    elif age_hours < 12:
        return 0.6
    elif age_hours < 24:
        return 0.4
    else:
        return 0.2
```

### Source Credibility Tier
```python
# Source: CONTEXT.md locked decision
CREDIBILITY_TIERS = {
    "reuters.com": 1.0,
    "bloomberg.com": 1.0,
    "worldgoldcouncil.org": 0.9,
    "gold.org": 0.9,
    "kitco.com": 0.8,
    "mining.com": 0.8,
    "juniorminingnetwork.com": 0.7,
}

def get_credibility_score(source_url: str) -> float:
    for domain, score in CREDIBILITY_TIERS.items():
        if domain in source_url.lower():
            return score
    return 0.4  # unknown source
```

### Headline Deduplication
```python
# Source: CONTEXT.md decision + difflib stdlib docs
from difflib import SequenceMatcher

def deduplicate_stories(stories: list[dict]) -> list[dict]:
    # Step 1: URL dedup
    seen_urls: set[str] = set()
    url_deduped = []
    for s in stories:
        url = s.get("url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            url_deduped.append(s)
        elif not url:
            url_deduped.append(s)

    # Step 2: Headline fuzzy dedup (keep more credible, or earlier if tie)
    unique: list[dict] = []
    for story in url_deduped:
        h1 = story.get("title", "").lower()
        is_dup = False
        for i, existing in enumerate(unique):
            h2 = existing.get("title", "").lower()
            if SequenceMatcher(None, h1, h2).ratio() >= 0.85:
                # Keep more credible source
                if story.get("credibility_score", 0) > existing.get("credibility_score", 0):
                    unique[i] = story
                is_dup = True
                break
        if not is_dup:
            unique.append(story)
    return unique
```

### Senior Agent Integration
```python
# Source: scheduler/agents/instagram_agent.py lines 205-207 (established pattern)
if content_bundle_id and compliance_passed:
    from agents.senior_agent import process_new_items  # noqa: PLC0415
    await process_new_items([draft_item.id])
```

### ContentBundle: No-Story Flag
```python
# Source: CONTEXT.md locked decision
from models.content_bundle import ContentBundle

# When no story clears threshold:
bundle = ContentBundle(
    no_story_flag=True,
    story_headline="No qualifying story today",
    score=best_score,  # float score of best candidate for observability
    compliance_passed=None,
)
session.add(bundle)
agent_run.notes = json.dumps({
    "no_story": True,
    "best_candidate_headline": best_candidate_headline,
    "best_candidate_score": best_score,
})
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `newspaper3k` for article extraction | `httpx` + `BeautifulSoup` | newspaper3k unmaintained; httpx+bs4 is lighter | No change needed — CONTEXT.md locked this |
| SerpAPI `result_position` as engagement proxy | Source credibility tier | Phase 7 context decision | Removes dependency on SerpAPI-specific position signals |
| Separate Claude calls for research + format + draft | Single combined Sonnet prompt | Phase 7 context decision | Saves API calls, reduces latency |

**Deprecated/outdated:**
- `feedparser` v5.x: The v6.x release (current: 6.0.12) cleaned up the API and improved Python 3 support. Always use `>=6.0`.
- `serpapi` client `GoogleSearch` class: The old `google-search-results` package used `GoogleSearch`. The new official `serpapi` package uses `serpapi.Client`. CONTEXT.md specifies `serpapi>=0.1.5` — current is 1.0.2, use that.

---

## Open Questions

1. **SerpAPI Plan Quota**
   - What we know: 6 keywords/day ingest + 2-3 corroboration/day = ~270 searches/month. Basic plan = 100/month.
   - What's unclear: Which SerpAPI plan is currently active? STATE.md flags this as a blocker.
   - Recommendation: Confirm Developer plan ($50/mo for 5,000 searches) before Phase 7 deploy. The planner should include a Wave 0 task to verify `SERPAPI_API_KEY` plan level. If on basic, the agent will 429 after ~10 days.

2. **feedparser for World Gold Council feed**
   - What we know: `https://www.gold.org/goldhub/news/feed` is the specified URL.
   - What's unclear: Whether this feed is publicly accessible without authentication. Some WGC content requires registration.
   - Recommendation: Test the feed URL in Wave 1. If it returns empty or 403, remove it from the feed list and document in `AgentRun.errors`.

3. **Claude Model Version for Haiku**
   - What we know: `instagram_agent.py` uses `claude-haiku-3-20240307`. `twitter_agent.py` uses the same.
   - What's unclear: Whether `claude-haiku-3-5-20241022` (claude-3-5-haiku) should be used instead for better relevance scoring. The project currently standardizes on the older Haiku.
   - Recommendation: Use `claude-haiku-3-20240307` to match existing agents unless Haiku 3.5 is already used elsewhere. Consistency > marginal quality gain.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12 | Runtime | ✓ | 3.12 (pyproject.toml requires-python) | — |
| httpx | Article fetch | ✓ | 0.28.1 (in uv.lock) | — (just needs explicit pyproject.toml entry) |
| feedparser | CONT-02 | ✗ (not in pyproject.toml) | 6.0.12 available | — (must add) |
| beautifulsoup4 | CONT-08 | ✗ (not in pyproject.toml) | 4.14.3 available | — (must add) |
| serpapi | CONT-03 | ✗ (not in pyproject.toml) | 1.0.2 available | — (must add) |
| SERPAPI_API_KEY | CONT-03 | ✓ (in Settings, in config.py) | — | — (key must be set in Railway env) |
| anthropic SDK | Claude calls | ✓ | 0.86.0 (in pyproject.toml) | — |
| PostgreSQL (Neon) | ContentBundle persist | ✓ | 16 (Neon managed) | — |
| `content_bundles` table | ContentBundle model | ✓ | Phase 1 schema | — |

**Missing dependencies with no fallback:**
- `feedparser`, `beautifulsoup4`, `serpapi` — all must be added to `scheduler/pyproject.toml` before Wave 1 implementation. Use `uv add` to update `uv.lock` simultaneously.

**Missing dependencies with fallback:**
- None.

---

## Validation Architecture

> `nyquist_validation: true` in `.planning/config.json` — section required.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio 0.23.x |
| Config file | `scheduler/pyproject.toml` `[tool.pytest.ini_options]` (existing) |
| Quick run command | `cd scheduler && uv run pytest tests/test_content_agent.py -x -q` |
| Full suite command | `cd scheduler && uv run pytest tests/ -q` |

`asyncio_mode = "auto"` is already set — no `@pytest.mark.asyncio` needed on individual tests.

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CONT-02 | feedparser entries parsed to story dicts | unit | `pytest tests/test_content_agent.py::test_rss_feed_parsing -x` | ❌ Wave 0 |
| CONT-03 | SerpAPI results parsed to story dicts | unit | `pytest tests/test_content_agent.py::test_serpapi_parsing -x` | ❌ Wave 0 |
| CONT-04 | URL dedup removes exact duplicates | unit | `pytest tests/test_content_agent.py::test_url_deduplication -x` | ❌ Wave 0 |
| CONT-04 | Headline fuzzy dedup at 0.85 threshold | unit | `pytest tests/test_content_agent.py::test_headline_deduplication -x` | ❌ Wave 0 |
| CONT-05 | Recency score: <3h=1.0, ≥24h=0.2 | unit | `pytest tests/test_content_agent.py::test_recency_score -x` | ❌ Wave 0 |
| CONT-05 | Credibility tiers: reuters=1.0, unknown=0.4 | unit | `pytest tests/test_content_agent.py::test_credibility_score -x` | ❌ Wave 0 |
| CONT-05 | Final score formula: (r×0.4+rc×0.3+c×0.3)×10 | unit | `pytest tests/test_content_agent.py::test_final_score_formula -x` | ❌ Wave 0 |
| CONT-06 | Top story selection: highest score above threshold | unit | `pytest tests/test_content_agent.py::test_select_top_story -x` | ❌ Wave 0 |
| CONT-07 | No-story flag: ContentBundle created, no DraftItem | unit | `pytest tests/test_content_agent.py::test_no_story_flag -x` | ❌ Wave 0 |
| CONT-08 | Article fetch fallback on httpx failure | unit | `pytest tests/test_content_agent.py::test_article_fetch_fallback -x` | ❌ Wave 0 |
| CONT-10 | Thread draft: both tweet array and long_form_post present | unit | `pytest tests/test_content_agent.py::test_thread_draft_structure -x` | ❌ Wave 0 |
| CONT-14/15 | Compliance block on "seva mining" mention | unit | `pytest tests/test_content_agent.py::test_compliance_fail_seva_mining -x` | ❌ Wave 0 |
| CONT-16 | Compliance fail-safe: ambiguous = block | unit | `pytest tests/test_content_agent.py::test_compliance_failsafe -x` | ❌ Wave 0 |
| CONT-17 | DraftItem created with platform="content", urgency="low" | unit | `pytest tests/test_content_agent.py::test_draft_item_fields -x` | ❌ Wave 0 |
| CONT-17 | ContentBundle.id stored in DraftItem.engagement_snapshot | unit | `pytest tests/test_content_agent.py::test_content_bundle_link -x` | ❌ Wave 0 |

All tests use mocked httpx, mocked serpapi client, mocked feedparser, mocked anthropic — no real network calls.

### Sampling Rate
- **Per task commit:** `cd scheduler && uv run pytest tests/test_content_agent.py -x -q`
- **Per wave merge:** `cd scheduler && uv run pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `scheduler/tests/test_content_agent.py` — all 15 tests listed above (stubs with `pytest.skip()` before lazy import, same pattern as `test_instagram_agent.py`)
- [ ] `scheduler/models/content_bundle.py` — mirror of backend model, uses `models.base.Base`
- [ ] `scheduler/seed_content_data.py` — seeds 4 `content_*` config keys (mirrors `seed_instagram_data.py`)
- [ ] New deps: `uv add "feedparser>=6.0" "beautifulsoup4>=4.12" "serpapi>=1.0" "httpx>=0.27"` in `scheduler/`

*(Existing test infrastructure — pytest, pytest-asyncio, asyncio_mode=auto — covers all Phase 7 test needs. Only the test file, model mirror, seed script, and deps are gaps.)*

---

## Sources

### Primary (HIGH confidence)
- `scheduler/agents/instagram_agent.py` — agent structure, two-Claude pattern, compliance fail-safe, process_new_items lazy import
- `scheduler/agents/worker.py` — content_agent placeholder at lock ID 1003, `_make_job` wiring pattern
- `backend/app/models/content_bundle.py` — ContentBundle schema (all fields confirmed)
- `scheduler/models/draft_item.py` — DraftItem fields including `engagement_snapshot` JSONB
- `scheduler/config.py` — `serpapi_api_key` already present in Settings
- `scheduler/pyproject.toml` — confirmed `httpx` in `uv.lock` at 0.28.1 (transitive dep via anthropic)
- SerpAPI Google News API docs (https://serpapi.com/google-news-api) — confirmed `news_results[].title/link/source.name/snippet/iso_date`
- PyPI feedparser 6.0.12 (https://pypi.org/project/feedparser/) — confirmed current version
- PyPI serpapi 1.0.2 (https://pypi.org/project/serpapi/) — confirmed current version
- PyPI beautifulsoup4 4.14.3 (https://pypi.org/project/beautifulsoup4/) — confirmed current version

### Secondary (MEDIUM confidence)
- `.planning/phases/07-content-agent/07-CONTEXT.md` — all locked implementation decisions (source of truth for this phase)
- `scheduler/seed_instagram_data.py` — seed script pattern to mirror
- asyncio.run_in_executor pattern for sync libs in async code — standard Python docs pattern

### Tertiary (LOW confidence)
- WGC feed accessibility at `https://www.gold.org/goldhub/news/feed` — not verified; flagged in Open Questions

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all versions confirmed from PyPI registry 2026-04-02; httpx presence confirmed from uv.lock
- Architecture: HIGH — mirrors directly from existing instagram_agent.py which is complete and verified
- Pitfalls: HIGH — pitfalls 1/2/3 verified by library design; pitfall 5 (SerpAPI quota) documented in STATE.md as blocker; others verified from library docs and existing code patterns
- SerpAPI response fields: HIGH — verified from official SerpAPI Google News API docs

**Research date:** 2026-04-02
**Valid until:** 2026-05-02 (stable libraries; SerpAPI quota concern is time-sensitive if plan not confirmed)

---

## Expansion Research (2026-04-07)

**Scope:** NEW features only — Twitter/X video+quote search, bi-weekly APScheduler cron, cross-run dedup, dual-platform JSONB briefs, Gold History topic tracking, and `content_type` column strategy. The original Phase 7 (3 formats, single daily run) is already built and verified.

---

### EXP-1: Twitter/X API v2 — Video and Text Quote Search

**What already exists in the codebase:**
`scheduler/agents/twitter_agent.py` uses `tweepy.asynchronous.AsyncClient` with `search_recent_tweets()` and `get_users_tweets()`. The `ContentAgent.__init__` only instantiates `AsyncAnthropic` and `serpapi.Client` — it has no Tweepy client yet. Adding one follows the exact TwitterAgent pattern.

**Bearer token auth:**
`X_API_BEARER_TOKEN` is already in `Settings` and used by `TwitterAgent`. `ContentAgent` needs to instantiate its own `tweepy.asynchronous.AsyncClient(bearer_token=settings.x_api_bearer_token)`.

**Searching for video posts — `has:videos` operator:**
The X API v2 `search_recent_tweets` query string supports `has:videos` as a standard operator. To find video posts from a named account:

```python
# Query for video tweets from a specific account
query = "from:Kitco has:videos -is:retweet"
# Query for video tweets from multiple target accounts (combined with OR)
query = "(from:Kitco OR from:CNBC OR from:Bloomberg) has:videos -is:retweet"
```

To retrieve media type information, add `expansions="attachments.media_keys"` and `media_fields=["type", "duration_ms", "preview_image_url"]`. The media objects land in `response.includes["media"]`; each has `type` which equals `"video"` or `"animated_gif"` or `"photo"`.

**Searching for text quote posts:**
Text posts (no media) from credible figures use:

```python
query = "(from:PeterSchiff OR from:jimrickards OR from:JimRickards) gold -has:media -is:retweet"
```

The `-has:media` operator excludes images, videos, and GIFs — returning only text posts.

**Tweepy AsyncClient call pattern:**

```python
# Source: scheduler/agents/twitter_agent.py — established pattern
response = await self.tweepy_client.search_recent_tweets(
    query=query,
    max_results=10,
    tweet_fields=["created_at", "public_metrics", "author_id", "text", "attachments"],
    expansions=["author_id", "attachments.media_keys"],
    user_fields=["username", "public_metrics"],
    media_fields=["type", "duration_ms", "preview_image_url"],
)
# Media info accessible via:
media_map = {}
if response.includes and response.includes.get("media"):
    for m in response.includes["media"]:
        media_map[m.media_key] = m
# For each tweet:
for tweet in response.data:
    attachments = getattr(tweet, "attachments", None) or {}
    media_keys = attachments.get("media_keys", []) if isinstance(attachments, dict) else []
    has_video = any(
        media_map.get(k) and media_map[k].type == "video"
        for k in media_keys
    )
```

**Rate limits — Basic tier ($100/mo):**
- Monthly tweet read cap: **10,000 tweets/month** across all searches in the project (same cap already tracked by `twitter_monthly_tweet_count` in Config).
- Per-request rate limit: 15 requests per 15 minutes for `search_recent_tweets` (Basic tier).
- The existing `_check_quota()` / `_increment_quota()` pattern in `TwitterAgent` must be reused or mirrored in `ContentAgent`. The monthly cap is project-level — both agents draw from the same 10,000/month pool.

**Quota impact of expansion:**
The content agent runs 2x/day. If it makes 3-5 Twitter searches per run (video + quote pools), that is 6-10 searches × ~10 results each = 60-100 tweets/day read. Over 30 days: 1,800-3,000 tweet reads for content agent alone. Combined with the existing TwitterAgent (≤500 reads/run × 12 runs/day = 6,000/month), total approaches 9,000-10,000/month. **The quota is tight.** Content agent Twitter searches should be kept to 2-3 targeted account searches per run, not broad keyword searches.

**Account list for video/quote search:**
The CONTEXT.md specifies: Kitco, CNBC, Bloomberg, Peter Schiff, Jim Rickards, WGC, Barrick CEO, mining executives, macro investors, billionaires discussing gold, politicians discussing gold. These should be stored as a Config key (e.g., `content_video_accounts`) rather than hardcoded so they can be tuned without deployment.

**Confidence:** HIGH — Tweepy v2 async pattern verified directly from `twitter_agent.py`. `has:videos` operator verified from X API v2 docs (official developer docs confirm operator availability for Basic tier standard operators). Media field expansion pattern from official X API v2 docs.

---

### EXP-2: Bi-Weekly APScheduler CronTrigger

**What the CONTEXT.md specifies:**
`gold_history_agent` job, lock ID 1009, runs bi-weekly on Sunday at 9am. Config key `gold_history_cron` stores the expression.

**APScheduler 3.x CronTrigger fields:**
Confirmed from official docs: supports `year`, `month`, `day`, `week`, `day_of_week`, `hour`, `minute`, `second` fields. Field expressions include `*/n` for "every n steps from minimum."

**Bi-weekly pattern — `week='*/2'`:**

```python
from apscheduler.triggers.cron import CronTrigger

# Bi-weekly Sunday at 9am — fires every 2 ISO weeks on Sunday
trigger = CronTrigger(
    day_of_week="sun",
    week="*/2",
    hour=9,
    minute=0,
    timezone="UTC",
)
```

**Critical gotcha: `day_of_week` numbering in APScheduler 3.x is Monday=0, not Sunday=0.** APScheduler uses ISO weekday numbering where Monday=0 and Sunday=6. Using the string `"sun"` is the safe approach — confirmed from APScheduler source (abbreviated names `mon`-`sun` are explicitly supported).

**The `*/2` week drift problem:**
Standard Unix cron `*/2` for weeks counts from ISO week 1 of the year. This means in some years the "every other week" pattern resets at the year boundary, potentially running on consecutive Sundays across a year-end. For a Gold History feature this is acceptable — a miss or double-fire once a year at New Year is low-stakes. The alternative (CalendarIntervalTrigger) is APScheduler 4 only (alpha — CLAUDE.md explicitly bans v4).

**Recommended implementation:**

```python
# scheduler/worker.py — new job registration in build_scheduler()
gold_history_hour = int(cfg.get("gold_history_hour", "9"))

scheduler.add_job(
    _make_job("gold_history_agent", engine),
    trigger="cron",
    day_of_week="sun",
    week="*/2",
    hour=gold_history_hour,
    minute=0,
    id="gold_history_agent",
    name="Gold History Agent — bi-weekly Sunday",
    timezone="UTC",
)
```

**New `JOB_LOCK_IDS` entry:** Add `"gold_history_agent": 1009` (lock ID from CONTEXT.md). Also add `"content_agent_midday": 1008`.

**Midday job (lock ID 1008):** The 12pm run is the same pipeline as 6am — same `ContentAgent().run()` call, different cron hour:

```python
scheduler.add_job(
    _make_job("content_agent_midday", engine),
    trigger="cron",
    hour=12,
    minute=0,
    id="content_agent_midday",
    name="Content Agent (midday) — daily at 12pm",
)
```

**New config keys to seed:**
- `content_agent_midday_hour` = `"12"`
- `gold_history_hour` = `"9"`

**Confidence:** HIGH for `day_of_week="sun"` and `week="*/2"` syntax — confirmed from APScheduler 3.x official docs RST source on GitHub. MEDIUM for year-boundary behavior (documented as known limitation in APScheduler community, but acceptable for this use case).

---

### EXP-3: Cross-Run Deduplication (Today's Earlier Run)

**What exists:** `deduplicate_stories()` in `content_agent.py` deduplicates within a single run's fetched stories by URL and headline similarity. It does NOT check against already-persisted `ContentBundle` records.

**What's needed:** Before surfacing a qualifying story, check if a `ContentBundle` with the same story URL OR similar headline already exists from today (same calendar date in UTC).

**Query pattern — using existing `ContentBundle` model:**

```python
# Verify: ContentBundle model field is story_url (not source_url)
# Source: backend/app/models/content_bundle.py — confirmed fields: story_url, story_headline, created_at

from sqlalchemy import select, cast, Date, func
from datetime import date, timezone, datetime

async def _is_already_covered_today(
    self,
    session: AsyncSession,
    story_url: str,
    story_headline: str,
) -> bool:
    """Check if story was already processed in today's earlier run."""
    today_utc = datetime.now(timezone.utc).date()

    result = await session.execute(
        select(ContentBundle).where(
            func.date(ContentBundle.created_at) == today_utc,
            ContentBundle.no_story_flag.is_(False),
        )
    )
    today_bundles = result.scalars().all()

    for bundle in today_bundles:
        # URL exact match
        if bundle.story_url and bundle.story_url == story_url:
            return True
        # Headline similarity
        if bundle.story_headline:
            ratio = difflib.SequenceMatcher(
                None,
                story_headline.lower(),
                bundle.story_headline.lower(),
            ).ratio()
            if ratio >= 0.85:
                return True
    return False
```

**Where to insert it:** In `_run_pipeline`, after scoring and selecting qualifying stories but before deep research. If all qualifying stories are already covered, fall through to no-story flag with a note.

**ContentBundle model import in scheduler:** The scheduler-side mirror at `scheduler/models/content_bundle.py` needs to match `backend/app/models/content_bundle.py` exactly. Confirmed the backend model has `story_url`, `story_headline`, `created_at`, and `no_story_flag` columns.

**The `func.date()` approach:** SQLAlchemy `func.date(ContentBundle.created_at)` works with PostgreSQL's `created_at timestamptz` column. It extracts the date portion in the DB server's timezone. Since Neon is UTC, this is reliable.

**Confidence:** HIGH — query pattern is standard SQLAlchemy 2.0 async. Model fields verified from `backend/app/models/content_bundle.py` source read.

---

### EXP-4: Dual-Platform JSONB Briefs Without DB Migration

**What exists:** `ContentBundle.draft_content` is a JSONB column (no schema constraints). The current agent stores format-specific dicts like `{"format": "thread", "tweets": [...], "long_form_post": "..."}`. Compliance extractor `_extract_check_text()` only handles `thread`, `long_form`, `infographic`.

**What's needed:** 4 of the 7 formats produce both Twitter and Instagram content. The `instagram_brief` sub-object needs to be embedded in `draft_content` without a DB migration.

**Confirmed approach — extend existing JSONB keys:**
JSONB is schema-free. Adding new keys to the stored dict requires no Alembic migration. The CONTEXT.md draft_content structures already include `instagram_brief` as a nested sub-object for `infographic`, and `instagram_caption` / `instagram_post` for `video_clip` and `quote`. These are simple additions to the Sonnet prompt's response format instructions.

**Format structures (from CONTEXT.md — locked):**

| Format | Twitter key | Instagram key |
|--------|-------------|---------------|
| `infographic` | `twitter_caption`, `key_stats`, etc. | `instagram_brief: {headline, key_stats, visual_structure, caption}` |
| `video_clip` | `twitter_caption` | `instagram_caption` |
| `quote` | `twitter_post` | `instagram_post` |
| `gold_history` | `tweets` (thread) | `instagram_carousel: [{slide, headline, body, visual_note}]` + `instagram_caption` |

**What needs to change in `content_agent.py`:**
1. `_extract_check_text()` must be extended to extract text from `video_clip`, `quote`, and `gold_history` formats for compliance checking.
2. `build_draft_item()` summary logic (the `alternatives` field) must handle all 7 formats.
3. The `_research_and_draft()` Sonnet prompt must be rewritten to present all 7 format options with dual-platform output instructions.

**No migration needed.** JSONB fields accept any valid JSON — the expanded keys are stored automatically when the dict is wider than before. Existing `no_story_flag=True` bundles with null `draft_content` are unaffected.

**Confidence:** HIGH — JSONB flexibility is a PostgreSQL guarantee, not an assumption. Verified against `backend/app/models/content_bundle.py` schema which has no JSON Schema constraint on `draft_content`.

---

### EXP-5: `content_type` Column — Naming and Migration Strategy

**Critical finding — naming conflict:**
CONTEXT.md specifies a `content_type` field on `ContentBundle`. However, the **existing** `backend/app/models/content_bundle.py` model (and the `0001_initial_schema.py` Alembic migration) use `format_type` for the same purpose. The existing `content_agent.py` code already writes to `bundle.format_type = draft_content.get("format")`.

**Options:**

| Option | Effort | Risk |
|--------|--------|------|
| A: Add `content_type` as a new column via Alembic migration, write both `format_type` and `content_type` | Low migration cost | Two columns with the same data; technical debt |
| B: Rename `format_type` → `content_type` via Alembic (`op.alter_column`), update model + all code | Medium — single migration, one rename | Must update model, seed scripts, any backend API reading `format_type` |
| C: Store `content_type` inside `draft_content` JSONB (already present as `draft_content["format"]`) | Zero migration cost | Slightly less queryable; requires JSON extraction in SQL queries |

**Recommendation: Option B — rename via Alembic.** The field is not yet read by any frontend code (Phase 8 builds the dashboard). The only writer is `content_agent.py` (line: `format_type=draft_content.get("format")`). Renaming now is lower cost than living with two columns.

**Migration template:**

```python
# backend/alembic/versions/0005_rename_format_type_to_content_type.py
revision = "0005"
down_revision = "0004"

def upgrade() -> None:
    op.alter_column("content_bundles", "format_type", new_column_name="content_type")

def downgrade() -> None:
    op.alter_column("content_bundles", "content_type", new_column_name="format_type")
```

**Files to update after migration:**
- `backend/app/models/content_bundle.py` — `format_type` → `content_type`
- `scheduler/models/content_bundle.py` — same rename in mirror
- `scheduler/agents/content_agent.py` — `format_type=...` → `content_type=...` (line ~732)
- Any backend API routes that filter or return `format_type` (check `backend/app/` routers)

**Confidence:** HIGH — migration pattern confirmed from existing `0004_add_engagement_alert_columns.py`. `op.alter_column` with `new_column_name` is the standard Alembic approach.

---

### EXP-6: Gold History Topic Tracking via Config Table

**What the CONTEXT.md specifies:** Store used story slugs in the Config table under key `gold_history_used_topics` as a JSONB list. Use the existing `_get_config()` pattern.

**Config table schema (confirmed):**
The `Config` model has `key` (String) and `value` (Text). It stores all values as text strings. For the existing config keys (`content_quality_threshold = "7.0"`), simple string values are sufficient. Storing a JSONB list requires serializing to/from JSON string in the value field.

**Confirmed approach — JSON serialized in Config.value:**

```python
import json

async def _get_used_topics(self, session: AsyncSession) -> list[str]:
    """Read used Gold History story slugs from config."""
    result = await session.execute(
        select(Config).where(Config.key == "gold_history_used_topics")
    )
    row = result.scalar_one_or_none()
    if row is None:
        return []
    try:
        return json.loads(row.value)  # Config.value stores JSON-encoded list
    except (json.JSONDecodeError, TypeError):
        return []

async def _add_used_topic(self, session: AsyncSession, slug: str) -> None:
    """Append a story slug to the used topics list in config."""
    topics = await self._get_used_topics(session)
    if slug not in topics:
        topics.append(slug)
    result = await session.execute(
        select(Config).where(Config.key == "gold_history_used_topics")
    )
    row = result.scalar_one_or_none()
    if row is None:
        session.add(Config(
            key="gold_history_used_topics",
            value=json.dumps(topics),
        ))
    else:
        row.value = json.dumps(topics)
    # caller commits
```

**Config.value is Text (not JSONB).** The `Config` model stores everything as text. There is no JSONB column on Config. The CONTEXT.md phrase "JSONB list" means "a JSON-encoded list stored in the text value column." This is exactly how to implement it.

**Seed entry:** Add `gold_history_used_topics` = `"[]"` to `seed_content_data.py` so the key exists from day one and `_get_used_topics` never returns an error on first run.

**Confidence:** HIGH — Config model structure verified directly from source. `_get_config()` pattern verified from `content_agent.py` lines 552-556. JSON-in-text-column pattern is standard for simple list storage in this codebase.

---

### EXP-7: Pipeline Changes for Multi-Story Output (No Per-Run Cap)

**What changed from original spec:**
Original Phase 7: select single highest-scoring story above 7.0, produce one `ContentBundle`.
Expanded Phase 7: surface ALL qualifying stories, produce multiple `ContentBundle` records per run. Target: 4-6 Twitter pieces/day, 1-2 Instagram pieces/day.

**Impact on existing `_run_pipeline()`:**
The current `select_top_story()` function returns at most 1 story. The expansion requires replacing it with a "select all above threshold" pattern:

```python
# Replace single-story selection with multi-story:
qualifying = [s for s in scored if s["score"] >= threshold]
qualifying.sort(key=lambda s: s["score"], reverse=True)
# No cap — process all qualifying stories
```

For each qualifying story, run the full deep research + draft + compliance + persist cycle. The loop must continue on individual failures (error isolation per story, not per run). `agent_run.items_queued` becomes a count of successfully persisted bundles.

**Priority enforcement:**
CONTEXT.md specifies: `breaking_news > thread/infographic/long_form > video_clip/quote > gold_history`. Since Claude decides format per story independently, priority is post-hoc — it affects dashboard ordering (Phase 8), not which stories are processed. The content agent processes all qualifying stories; the dashboard sorts by priority. No change to the processing loop needed for priority.

**Confidence:** HIGH — the existing `select_top_story()` and `_run_pipeline()` code is directly inspected. The multi-story change is a straightforward refactor of the selection and loop logic.

---

### EXP-8: Updated `_extract_check_text` and `build_draft_item` for 7 Formats

**What needs to extend in existing code (verified from source):**

Current `_extract_check_text()` (lines ~394-408) handles only `thread`, `long_form`, `infographic`. The expansion adds `breaking_news`, `video_clip`, `quote`, `gold_history`.

**Extension:**
```python
elif fmt == "breaking_news":
    parts.append(draft_content.get("tweet", ""))
    if draft_content.get("infographic_brief"):
        parts.append(draft_content["infographic_brief"].get("caption", ""))
elif fmt == "video_clip":
    parts.append(draft_content.get("twitter_caption", ""))
    parts.append(draft_content.get("instagram_caption", ""))
elif fmt == "quote":
    parts.append(draft_content.get("twitter_post", ""))
    parts.append(draft_content.get("instagram_post", ""))
    parts.append(draft_content.get("quote_text", ""))
elif fmt == "gold_history":
    parts.extend(draft_content.get("tweets", []))
    parts.append(draft_content.get("instagram_caption", ""))
    for slide in draft_content.get("instagram_carousel", []):
        parts.append(slide.get("headline", ""))
        parts.append(slide.get("body", ""))
```

Current `build_draft_item()` (lines ~341-348) summary logic handles only `thread`, `long_form`, `infographic`. Must add cases for `breaking_news`, `video_clip`, `quote`, `gold_history`.

**Confidence:** HIGH — both functions read directly from source. Extension is mechanical.

---

### EXP-9: New Worker.py Job Registrations

**Confirmed from worker.py inspection:**

Current `JOB_LOCK_IDS`:
```python
"content_agent": 1003,
# 1008 and 1009 not yet registered
```

Current `_make_job()` has `elif job_name == "content_agent"` branch — wired to `ContentAgent().run()`.

**New entries needed:**

```python
# JOB_LOCK_IDS additions
"content_agent_midday": 1008,
"gold_history_agent": 1009,
```

**`_make_job()` additions:**

```python
elif job_name == "content_agent_midday":
    agent = ContentAgent()
    await with_advisory_lock(conn, JOB_LOCK_IDS[job_name], job_name, agent.run)
elif job_name == "gold_history_agent":
    agent = GoldHistoryAgent()
    await with_advisory_lock(conn, JOB_LOCK_IDS[job_name], job_name, agent.run)
```

`ContentAgent` can be reused for the midday run — same class, same `run()` method, different schedule. `GoldHistoryAgent` is a new class (or a method on `ContentAgent`). Per CONTEXT.md, it is a separate job with separate lock ID, so a separate class is cleaner.

**`_read_schedule_config()` additions:**
```python
defaults = {
    # ... existing keys ...
    "content_agent_midday_hour": "12",
    "gold_history_hour": "9",
}
```

**`build_scheduler()` additions:**
```python
midday_hour = int(cfg["content_agent_midday_hour"])
gold_history_hour = int(cfg["gold_history_hour"])

scheduler.add_job(
    _make_job("content_agent_midday", engine),
    trigger="cron",
    hour=midday_hour,
    minute=0,
    id="content_agent_midday",
    name=f"Content Agent (midday) — daily at {midday_hour}pm",
)
scheduler.add_job(
    _make_job("gold_history_agent", engine),
    trigger="cron",
    day_of_week="sun",
    week="*/2",
    hour=gold_history_hour,
    minute=0,
    id="gold_history_agent",
    name=f"Gold History Agent — bi-weekly Sunday at {gold_history_hour}am",
    timezone="UTC",
)
```

**Confidence:** HIGH — worker.py structure read directly. Lock IDs from CONTEXT.md.

---

### EXP: Common Pitfalls (Expansion-Specific)

**Pitfall A: Twitter quota exhaustion from content agent video search**
The content agent now runs 2×/day and searches Twitter for video + quote posts. At 2 runs × 3 searches × ~10 results = 60 reads/day, that is 1,800/month from content agent alone, added to the existing TwitterAgent's ~6,000/month. Total: ~7,800-8,000/month of the 10,000 cap. **Do not add broad keyword searches to the content agent** — restrict to targeted `from:AccountName` queries only. Monitor `twitter_monthly_tweet_count` in Config.

**Pitfall B: `week='*/2'` fires on both an even and odd ISO week at year rollover**
When ISO week 52/53 rolls to week 1, the `*/2` step may produce two consecutive Sunday firings. For Gold History this is low-stakes (worst case: an extra history post in early January). Document the behavior in a comment in `worker.py`.

**Pitfall C: Config.value is Text, not JSONB**
`_get_config()` returns the raw `Config` row. `row.value` is always a string. For `gold_history_used_topics`, callers must `json.loads(row.value)` to get the list. Forgetting this produces a string comparison instead of a list membership check — the topic is never found as "used," and the same story gets selected repeatedly.

**Pitfall D: `format_type` vs `content_type` naming mismatch**
CONTEXT.md uses `content_type` throughout. The existing model and Alembic schema use `format_type`. Until Migration 0005 is applied and the model/agent are updated, using `content_type` in new code will silently succeed (SQLAlchemy won't error — it stores to the wrong column or not at all). All writers must use the same column name. Apply the rename migration as the first task of the expansion wave.

**Pitfall E: `has:videos` operator may return animated GIFs**
The `has:videos` operator includes both native videos and animated GIFs. When checking media type in the API response, filter on `media.type == "video"` (not just presence of media). GIFs are low-value for the video_clip format — the speaker's face and voice are what makes a clip credible.

**Pitfall F: Tweepy includes dict access**
`response.includes` in Tweepy's `AsyncClient` returns a plain dict, not an object with attribute access. Use `response.includes.get("media", [])` and `response.includes.get("users", [])` — not `response.includes.media`.

---

### EXP: Sources

#### Primary (HIGH confidence)
- `scheduler/agents/content_agent.py` — confirmed `format_type` column usage, `_get_config` pattern, `_run_pipeline` single-story flow
- `backend/app/models/content_bundle.py` — confirmed column names: `format_type` (not `content_type`), `story_url`, `story_headline`, `created_at`, `no_story_flag`
- `backend/alembic/versions/0001_initial_schema.py` — confirmed `format_type` String(50) in DB schema
- `backend/alembic/versions/0004_add_engagement_alert_columns.py` — confirmed `op.alter_column` / `op.add_column` migration pattern (down_revision = "0004" is correct chain point)
- `scheduler/agents/twitter_agent.py` — confirmed Tweepy `search_recent_tweets` call signature, `response.includes` dict access pattern, bearer token auth, quota tracking
- `scheduler/worker.py` — confirmed `JOB_LOCK_IDS`, `_make_job` dispatch pattern, `_read_schedule_config` defaults dict
- X API v2 docs (via WebSearch, multiple verified sources) — `has:videos` operator, `attachments.media_keys` expansion, `media_fields=["type"]`, Basic tier 10,000 tweets/month cap

#### Secondary (MEDIUM confidence)
- APScheduler 3.x CronTrigger docs (RST source on GitHub) — `week='*/2'` and `day_of_week='sun'` field syntax confirmed; year-boundary behavior documented as known limitation
- X API v2 search operators (docs.x.com via search) — `-has:media` for text-only posts, `from:` operator

#### Tertiary (LOW confidence)
- Year-boundary firing behavior of `week='*/2'` — community-reported; not tested; acceptable risk documented

---

**Expansion research date:** 2026-04-07
**Valid until:** 2026-05-07 (Twitter quota numbers may shift if X API pricing changes)
