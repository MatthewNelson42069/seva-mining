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
