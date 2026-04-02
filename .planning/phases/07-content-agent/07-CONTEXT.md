# Phase 7: Content Agent - Context

**Gathered:** 2026-04-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the Content Agent: a daily 6am APScheduler job that ingests RSS feeds + SerpAPI news, deduplicates by URL and headline similarity, scores stories, selects the single highest-scoring story above 7.0/10, conducts a multi-step deep research pass, decides on a content format, drafts the content, runs compliance checking, and delivers a `ContentBundle` to the Senior Agent — or creates a `ContentBundle` with `no_story_flag=True` when nothing qualifies.

This phase does NOT include: dashboard rendering of the ContentBundle, infographic image generation, Settings page wiring, or any frontend work. Those are Phase 8. Phase 7 produces structured data (JSONB) that Phase 8 renders.

The `content_agent` job slot is already registered in `scheduler/worker.py` (lock ID 1003, daily cron at 6am) — Phase 7 replaces the placeholder with the real implementation.

</domain>

<decisions>
## Implementation Decisions

### Infographic Generation (CONT-12)

- **What is produced:** Structured JSON data, NOT an image file. Phase 8 dashboard renders the visual.
- **Infographic brief structure stored in `ContentBundle.draft_content`:**
  ```json
  {
    "format": "infographic",
    "headline": "...",
    "key_stats": [
      {"stat": "Gold hits $3,200/oz", "source": "Reuters, Apr 2026", "source_url": "https://..."},
      ...
    ],
    "visual_structure": "bar chart",
    "caption_text": "...(full caption for posting alongside the infographic)..."
  }
  ```
- **Key stats (5-8):** Claude extracts the most impactful numerical data points from the full article + corroborating sources — price levels, percentages, tonnage, dates, production figures. Returns them as a structured list with stat text + source citation.
- **Visual structure suggestion:** Claude picks from fixed set: `"bar chart"`, `"timeline"`, `"comparison table"`, `"stat callouts"`, `"map"`. Written as a string in the JSON.
- **Caption text:** Full caption for posting alongside the infographic. Senior analyst voice. Suitable for X or Instagram.

### Format Decision Logic (CONT-09, CONT-10)

- **Who decides:** Claude, after reading the full research summary. Claude picks format and provides rationale.
- **Formats and outputs:**
  - `"thread"` → draft BOTH: (a) tweet thread (3-5 tweets, each ≤ 280 chars) AND (b) single long-form X post (≤ 2,200 chars). Stored in `draft_content` as `{"format": "thread", "tweets": [...], "long_form_post": "..."}`.
  - `"long_form"` → single extended X post ≤ 2,200 chars. NOT a blog article. Stored as `{"format": "long_form", "post": "..."}`.
  - `"infographic"` → structured brief (see above).
- **Thread + long-form drafting:** Only when `format="thread"`. Not produced for other formats.
- **Format decision is made AFTER deep research** — Claude has the full story context before picking.

### Deep Research Approach (CONT-08)

- **Full article fetch:** `httpx` GET + `BeautifulSoup` text extraction (strip nav, ads, boilerplate, keep main content). Fall back to RSS summary/description if fetch fails (paywall, 403, JS-rendered). Log warning in `AgentRun.errors` on fetch failure, do not discard the story.
- **Corroborating sources:** SerpAPI Google News search using the story's headline keywords. 2-3 results. Same SerpAPI client used in CONT-03 ingest. Costs ~2-3 additional SerpAPI credits per run.
- **Deep research output stored in `ContentBundle.deep_research`:**
  ```json
  {
    "article_text": "...(full or partial)...",
    "article_fetch_succeeded": true,
    "corroborating_sources": [
      {"title": "...", "url": "...", "source": "...", "snippet": "..."},
      ...
    ],
    "key_data_points": ["Gold hit $3,200/oz according to...", ...]
  }
  ```
- **Key data point extraction:** Claude extracts from the full research bundle in the same prompt that decides format and produces the draft.

### Story Scoring (CONT-05)

**Three components, weights sum to 1.0:**

1. **Relevance to gold/mining (40%):** Claude Haiku classifies relevance on a 0–1 scale based on topic alignment with gold sector, mining companies, prices, ETFs, central bank activity. Config key: `content_relevance_weight` (default `"0.40"`).

2. **Recency (30%):** Linear decay — article published < 3h ago = 1.0, < 6h = 0.8, < 12h = 0.6, < 24h = 0.4, ≥ 24h = 0.2. Config key: `content_recency_weight` (default `"0.30"`).

3. **Source credibility tier (30%):** Replaces "engagement signal" (articles have no likes/views). Tiers:
   - `reuters.com`, `bloomberg.com` → 1.0
   - `worldgoldcouncil.org` → 0.9
   - `kitco.com`, `mining.com` → 0.8
   - `juniorminingnetwork.com` → 0.7
   - SerpAPI results from unknown sources → 0.4
   - Config key: `content_credibility_weight` (default `"0.30"`)

**Final score:** `(relevance × 0.40) + (recency × 0.30) + (credibility × 0.30)` → normalized to 0–10 scale (multiply by 10).

**Quality threshold:** 7.0/10 (config key: `content_quality_threshold`, default `"7.0"`).

### No-Story Flag (CONT-07)

When no story clears the quality threshold:
- Create a `ContentBundle` record with:
  - `no_story_flag = True`
  - `story_headline = "No qualifying story today"`
  - `score` = score of the best candidate (for observability)
  - All other fields null
- Log to `AgentRun.notes`: best candidate headline and score
- Do NOT call Senior Agent's `process_new_item` (no DraftItem created)
- Phase 8 dashboard queries `ContentBundle` for today's record to display "No story today"

### RSS Feeds and SerpAPI Ingest (CONT-02, CONT-03)

**RSS feeds (4 feeds, all free):**
- Kitco News: `https://www.kitco.com/rss/news.xml`
- Mining.com: `https://www.mining.com/feed/`
- Junior Mining Network: `https://www.juniorminingnetwork.com/feed`
- World Gold Council: `https://www.gold.org/goldhub/news/feed`

**SerpAPI keywords (CONT-03):** 6 searches per run:
- "gold exploration", "gold price", "central bank gold", "gold ETF", "junior miners", "gold reserves"
- Uses Google News engine (`engine=google_news`). Fetches top 5 results per keyword.

**Deduplication (CONT-04):**
- Step 1: URL dedup — exact URL match removes duplicate
- Step 2: Headline similarity — `difflib.SequenceMatcher` ratio ≥ 0.85 → treat as same story, keep the one from the more credible source (or earlier if same credibility)
- `difflib` is in Python stdlib — no additional dep needed

### Senior Agent Integration (CONT-17)

After a qualifying `ContentBundle` is created and compliance passes:
- Create a `DraftItem` from the `ContentBundle` with:
  - `platform = "content"`
  - `source_text = story_headline`
  - `source_url = story_url`
  - `source_account = source_name`
  - `alternatives = json.dumps([draft summary])` — the actual full draft is in `ContentBundle.draft_content`
  - `rationale = format decision rationale from Claude`
  - `score = content_bundle.score`
  - `expires_at = None` (content is evergreen)
  - `urgency = "low"` (content agent stories are never time-critical)
- Call `process_new_items([draft_item.id])` via lazy import
- Link `DraftItem` back to `ContentBundle` — note: no FK in current schema, store `ContentBundle.id` in `DraftItem.engagement_snapshot` as `{"content_bundle_id": "..."}` for Phase 8 to use

### Compliance Checking (CONT-14, CONT-15, CONT-16)

- Separate Claude Haiku compliance call on the complete content package (draft text + caption if infographic)
- Same fail-safe pattern: ambiguous response = block
- Checks: no "Seva Mining" mention, no financial advice
- If compliance fails: log to `AgentRun.errors`, set `ContentBundle.compliance_passed = False`, do NOT create DraftItem

### New Dependencies Required

- `feedparser>=6.0` — RSS ingestion (not yet in `scheduler/pyproject.toml`)
- `httpx>=0.27` — article fetch (check if already present; if not, add)
- `beautifulsoup4>=4.12` — article text extraction
- `serpapi>=0.1.5` — SerpAPI Python client (check if already present)

### Claude's Discretion

- Exact `BeautifulSoup` selector logic for main content extraction (use `article`, `main`, or `div.content` tags; strip `nav`, `header`, `footer`, `aside`)
- SerpAPI response parsing (field names: `title`, `link`, `snippet`, `source`)
- Exact Claude Haiku prompt for relevance scoring
- Exact Claude Sonnet prompt for deep research + format decision + drafting (single combined prompt recommended to save API calls)
- Config key naming convention (follow `content_*` prefix)
- `AgentRun.notes` JSONB structure for storing run stats

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Specification
- `.planning/REQUIREMENTS.md` §Content Agent — CONT-01 through CONT-17
- `.planning/ROADMAP.md` §Phase 7 — Goal, success criteria, dependency context

### Existing Models
- `backend/app/models/content_bundle.py` — ContentBundle schema (all fields: story_headline, story_url, source_name, format_type, score, quality_score, no_story_flag, deep_research JSONB, draft_content JSONB, compliance_passed)
- `backend/app/models/draft_item.py` — DraftItem schema for Senior Agent integration

### Existing Code to Mirror
- `scheduler/agents/twitter_agent.py` — Agent structure: class → run() → _run_pipeline(), AgentRun logging, error isolation, _get_config(), two-Claude pattern
- `scheduler/agents/instagram_agent.py` — Same patterns, more recent; also shows process_new_items lazy import
- `scheduler/worker.py` — `content_agent` job slot at lock ID 1003, daily 6am cron; `_make_job` wiring pattern
- `scheduler/seed_instagram_data.py` — Seed script pattern to mirror for content agent config seed

### Stack Decisions
- `CLAUDE.md` §Technology Stack — `feedparser 6.0.x`, `serpapi latest`, `httpx 0.27.x`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scheduler/agents/twitter_agent.py` — `_get_config()`, AgentRun logging, two-Claude pattern (Sonnet + Haiku), `_check_compliance()` all directly reusable
- `scheduler/agents/senior_agent.py` — `process_new_items()` module-level function ready to call
- `scheduler/services/whatsapp.py` — available for any alerts (not expected in Phase 7)
- `scheduler/models/draft_item.py` — DraftItem model with all needed fields
- No `scheduler/models/content_bundle.py` exists yet — needs to be created as mirror of backend model

### Established Patterns
- Agent structure: `class ContentAgent` → `run()` → `_run_pipeline()` → fetch + score + research + draft + persist
- Config: `_get_config(session, key, default)` reads from `Config` table
- AgentRun logging: create at start, set status, always commit in `finally`
- Error isolation: catch all exceptions, log to `AgentRun.errors`, never re-raise

### Integration Points
- `worker.py` `content_agent` placeholder → wire to `ContentAgent().run()`
- `process_new_items()` → call after DraftItem commit (lazy import, same as Instagram/Twitter agents)
- `ContentBundle` → new model mirror needed in `scheduler/models/content_bundle.py`

</code_context>

<specifics>
## Specific Decisions

- Infographic = structured JSON, not image file — Phase 8 renders the visual
- Visual structure: Claude picks from `["bar chart", "timeline", "comparison table", "stat callouts", "map"]`
- Format decision by Claude after deep research (not rules-based)
- Thread format produces BOTH tweet thread AND long-form X post (≤ 2,200 chars each tweet/post)
- Long-form = single X post ≤ 2,200 chars (not a blog article)
- Article fetch: httpx + BeautifulSoup, fall back to RSS summary on failure
- Corroborating sources: SerpAPI Google News (re-use existing client)
- Engagement signal replaced by source credibility tier: Reuters/Bloomberg=1.0, WGC=0.9, Kitco/Mining=0.8, JMN=0.7, unknown=0.4
- No-story: ContentBundle with no_story_flag=True, score of best candidate stored
- RSS feeds: Kitco, Mining.com, Junior Mining Network, World Gold Council (4 feeds)
- SerpAPI: 6 keywords × top 5 results = up to 30 articles from SerpAPI per run
- Dedup: URL exact match first, then difflib headline ≥ 0.85

</specifics>

<deferred>
## Deferred Ideas

- Actual image file generation (HTML→screenshot or AI image API) — deferred to post-launch or a future phase. Phase 7 produces the structured brief; rendering is Phase 8's job.
- SerpAPI `result_position` as an engagement proxy — decided against in favour of source credibility tier.
- ContentBundle–DraftItem FK in schema — no migration needed; use `engagement_snapshot` JSONB to store the link for now. Clean FK can be added in Phase 9 or v1.x.

</deferred>

---
*Phase: 07-content-agent*
*Context gathered: 2026-04-02*
