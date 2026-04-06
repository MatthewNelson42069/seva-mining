# Phase 7: Content Agent - Context

**Gathered:** 2026-04-02
**Updated:** 2026-04-06
**Status:** Ready for planning (additional content types pending — see Deferred)

<domain>
## Phase Boundary

Build the Content Agent: a daily 6am APScheduler job that ingests RSS feeds + SerpAPI news, deduplicates by URL and headline similarity, scores stories, selects the single highest-scoring story above 7.0/10, conducts a multi-step deep research pass, decides on a content format, drafts the content, runs compliance checking, and delivers a `ContentBundle` to the Senior Agent — or creates a `ContentBundle` with `no_story_flag=True` when nothing qualifies.

This phase does NOT include: dashboard rendering of the ContentBundle, infographic image generation, Settings page wiring, or any frontend work. Those are Phase 8. Phase 7 produces structured data (JSONB) that Phase 8 renders.

The `content_agent` job slot is already registered in `scheduler/worker.py` (lock ID 1003, daily cron at 6am) — Phase 7 replaces the placeholder with the real implementation.

</domain>

<decisions>
## Implementation Decisions

### Voice & Persona (Claude Drafting Prompt)

**Who is speaking:** Senior gold analyst — authoritative, inside-the-room perspective. Speaks like someone who has been in the room when deals get made. Makes connections, not summaries.

**Tone:** Precise + punchy. Data-forward. Every sentence earns its place. Reads like Bloomberg terminal but human-accessible.

**Opening rule:** First line is always the most impactful data point or fact from the story. Lead with the number. Not a preamble, not context-setting — the stat that stops the scroll.

> Example: "Gold up $84 in 5 sessions. That's the fastest 3-week move since SVB."

**Differentiation requirement:** Every draft must surface ONE non-obvious insight that was not in the original article — a pattern, implication, or comparison Claude finds in the research. This is mandatory. Generic news summary = failed draft.

> Example: "This is the 4th consecutive month of central bank buying above 50 tonnes — the last time this sustained pace ran this long was 2010-2012, which preceded a 65% gold price increase over 18 months."

**What drafts are NOT:** Vague bullish cheerleading, generic summaries, financial advice, or "gold went up today" recaps. The compliance check already blocks financial advice — the voice guidelines block the rest.

---

### RSS Feeds and SerpAPI Ingest (CONT-02, CONT-03)

**RSS feeds — 8 feeds:**
- Kitco News: `https://www.kitco.com/rss/news.xml`
- Mining.com: `https://www.mining.com/feed/`
- Junior Mining Network: `https://www.juniorminingnetwork.com/feed`
- World Gold Council: `https://www.gold.org/goldhub/news/feed`
- Reuters (business/commodities): `https://feeds.reuters.com/reuters/businessNews`
- Bloomberg Markets: Bloomberg gold/commodities RSS (exact URL to verify at implementation)
- GoldSeek: `https://goldseek.com/feed/`
- Investing.com gold news: `https://www.investing.com/rss/news_25.rss`

**SerpAPI keywords (CONT-03) — 10 keywords:**
- "gold exploration", "gold price", "central bank gold", "gold ETF", "junior miners", "gold reserves" (original 6)
- "gold inflation hedge", "Fed gold", "dollar gold", "recession gold" (added macro/inflation angle)
- Uses Google News engine (`engine=google_news`). Top 5 results per keyword.
- SerpAPI budget: 10 × 5 = 50 articles per run + 2-3 corroborating searches per qualifying story. ~53 credits/day, ~1,600/month. Within budget.

**Feed failure handling:** If a feed errors (403, timeout, malformed XML), log to `AgentRun.errors` and continue with remaining feeds. One failed feed does not abort the run.

**Deduplication (CONT-04):**
- Step 1: URL dedup — exact URL match removes duplicate
- Step 2: Headline similarity — `difflib.SequenceMatcher` ratio ≥ 0.85 → same story
- **Tie-break rule:** When same story appears in multiple feeds, keep the version from the most credible source (highest credibility tier). `difflib` is stdlib — no added dep.

**Story age:** 24-hour soft cutoff via scoring. Stories ≥ 24h old score 0.2 on recency — they rarely clear 7.0/10 unless extremely credible. Let scoring handle filtering naturally.

**Noise filter:** Pure price recap stories ("gold closed at $X today, up $Y") have low relevance to gold sector analysis — they score low on the 40% relevance component naturally. No hardcoded exclusion needed; scoring handles it.

---

### Source Credibility Tiers

Tiers used in Story Scoring (30% weight):

| Source | Credibility | Reasoning |
|--------|-------------|-----------|
| `reuters.com` | 1.0 | Tier-1 financial wire |
| `bloomberg.com` | 1.0 | Tier-1 financial wire |
| `worldgoldcouncil.org` | 0.9 | Official gold industry body |
| `kitco.com` | 0.8 | Gold-specialist outlet, trusted in sector |
| `mining.com` | 0.8 | Mining-specialist outlet, trusted in sector |
| `juniorminingnetwork.com` | 0.7 | Solid niche source, junior mining focus |
| `goldseek.com` | 0.6 | Reputable commentary aggregator |
| `investing.com` | 0.6 | Mainstream financial news, broad coverage |
| SerpAPI unknown sources | 0.4 | Unverified / unknown outlets |

Config key: `content_credibility_weight` (default `"0.30"`)

---

### Story Scoring (CONT-05)

**Three components, weights sum to 1.0:**

1. **Relevance to gold/mining (40%):** Claude Haiku classifies relevance on a 0–1 scale based on topic alignment with gold sector, mining companies, prices, ETFs, central bank activity. Config key: `content_relevance_weight` (default `"0.40"`).

2. **Recency (30%):** Linear decay — article published < 3h ago = 1.0, < 6h = 0.8, < 12h = 0.6, < 24h = 0.4, ≥ 24h = 0.2. Config key: `content_recency_weight` (default `"0.30"`).

3. **Source credibility tier (30%):** See credibility tiers table above. Config key: `content_credibility_weight` (default `"0.30"`).

**Final score:** `(relevance × 0.40) + (recency × 0.30) + (credibility × 0.30)` → normalized to 0–10 scale (multiply by 10).

**Quality threshold:** 7.0/10 (config key: `content_quality_threshold`, default `"7.0"`).

---

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

---

### Format Decision Logic (CONT-09, CONT-10)

**Who decides:** Claude, after reading the full research summary.

**Signals for each format:**

| Format | Pick when... |
|--------|-------------|
| `thread` | Story has **3+ separable distinct angles** each worth a tweet — data points, implications, historical parallel, key quote, market reaction. |
| `long_form` | One powerful coherent narrative — single argument or insight that flows as a single post. Fewer distinct angles. |
| `infographic` | Story has a clear **comparison, trend, or historical pattern** that is better visualized than narrated. Triggered by: multiple data points across time, cross-entity comparisons, "this echoes X from the past" framing. |

**Default format:** Thread. When no clear format signal exists, default to thread.

**Outputs per format:**
- `"thread"` → draft BOTH: (a) tweet thread (3-5 tweets, each ≤ 280 chars) AND (b) single long-form X post (≤ 2,200 chars). Stored as `{"format": "thread", "tweets": [...], "long_form_post": "..."}`.
- `"long_form"` → single extended X post ≤ 2,200 chars. NOT a blog article. Stored as `{"format": "long_form", "post": "..."}`.
- `"infographic"` → structured JSON brief (see below).

---

### Infographic Format (CONT-12)

**What is produced:** Structured JSON data, NOT an image file. Phase 8 dashboard renders the visual.

**Two infographic modes:**
1. **Current-data infographic:** Key stats from today's story. Multiple numerical data points, production figures, price levels, percentages.
2. **Historical pattern infographic:** Today's story triggers a historical analysis — how current conditions echo a past pattern, and what that pattern predicted. Example: *"Central bank gold buying at 1,000+ tonnes/year for 4th consecutive year — mirrors 2010-2012 pace, which preceded 65% gold price gain."*

**Historical mode rules:**
- Only when the story **naturally supports** a compelling historical parallel. Not forced.
- Claude uses **training knowledge** to identify the historical parallel, then runs an **additional SerpAPI search** to verify the historical claim before including it.
- If historical search fails to verify the claim, fall back to current-data infographic mode.
- Additional SerpAPI cost: ~2 credits for the verification search.

**Infographic brief stored in `ContentBundle.draft_content`:**
```json
{
  "format": "infographic",
  "mode": "current_data" | "historical_pattern",
  "headline": "...",
  "key_stats": [
    {"stat": "Gold hits $3,200/oz", "source": "Reuters, Apr 2026", "source_url": "https://..."},
    ...
  ],
  "historical_context": {
    "pattern": "...(description of historical parallel)...",
    "then": "...(what happened historically)...",
    "now": "...(how current situation compares)...",
    "implication": "...(what the pattern suggests about now)..."
  },
  "visual_structure": "bar chart | timeline | comparison table | stat callouts | map | historical comparison | trend line",
  "caption_text": "...(full caption for posting alongside the infographic)..."
}
```
Note: `historical_context` field is `null` when `mode = "current_data"`. `visual_structure` for historical infographics typically uses `"historical comparison"` or `"trend line"`.

**Key stats (5-8):** Claude extracts most impactful numerical data points. Returns as structured list with stat text + source citation.

**Caption text:** Full caption for posting alongside the infographic. Senior analyst voice. Suitable for X or Instagram.

---

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

---

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
- Link `DraftItem` back to `ContentBundle` — store `ContentBundle.id` in `DraftItem.engagement_snapshot` as `{"content_bundle_id": "..."}` for Phase 8 to use

---

### Compliance Checking (CONT-14, CONT-15, CONT-16)

- Separate Claude Haiku compliance call on the complete content package (draft text + caption if infographic)
- Same fail-safe pattern: ambiguous response = block
- Checks: no "Seva Mining" mention, no financial advice
- If compliance fails: log to `AgentRun.errors`, set `ContentBundle.compliance_passed = False`, do NOT create DraftItem

---

### New Dependencies Required

- `feedparser>=6.0` — RSS ingestion (not yet in `scheduler/pyproject.toml`)
- `httpx>=0.27` — article fetch (check if already present; if not, add)
- `beautifulsoup4>=4.12` — article text extraction
- `serpapi>=0.1.5` — SerpAPI Python client (check if already present)

---

### Claude's Discretion

- Exact `BeautifulSoup` selector logic for main content extraction (use `article`, `main`, or `div.content` tags; strip `nav`, `header`, `footer`, `aside`)
- SerpAPI response parsing (field names: `title`, `link`, `snippet`, `source`)
- Exact Claude Haiku prompt for relevance scoring
- Exact Claude Sonnet prompt for deep research + format decision + drafting. **Must include:** voice/persona instructions (senior analyst, precise/punchy, lead with number, find the non-obvious connection), format decision criteria (3+ angles = thread; comparison/trend = infographic; single narrative = long-form; default = thread), historical parallel detection and verification logic.
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

- Voice: senior gold analyst — precise, punchy, opens with the number, finds the non-obvious connection
- Infographic = structured JSON, not image file — Phase 8 renders the visual
- Infographic modes: current-data OR historical pattern (when story naturally supports it)
- Historical infographic: Claude training knowledge + SerpAPI verification search; only when compelling parallel exists
- `visual_structure` options: `["bar chart", "timeline", "comparison table", "stat callouts", "map", "historical comparison", "trend line"]`
- Format decision by Claude after deep research (not rules-based)
- Thread = 3+ separable distinct angles; Long-form = one coherent narrative; Infographic = comparison/trend/historical
- Default format when ambiguous: Thread
- Thread format produces BOTH tweet thread AND long-form X post (≤ 2,200 chars)
- Long-form = single X post ≤ 2,200 chars (not a blog article)
- Article fetch: httpx + BeautifulSoup, fall back to RSS summary on failure
- Corroborating sources: SerpAPI Google News (re-use existing client)
- RSS feeds: 8 total — Kitco, Mining.com, JMN, WGC, Reuters, Bloomberg, GoldSeek, Investing.com
- SerpAPI: 10 keywords × top 5 results = up to 50 articles from SerpAPI per run
- Dedup: URL exact match first, then difflib headline ≥ 0.85; tie-break = most credible source
- Credibility tiers: Reuters/Bloomberg=1.0, WGC=0.9, Kitco/Mining=0.8, JMN=0.7, GoldSeek/Investing.com=0.6, unknown=0.4
- Feed failure: log + skip, run continues
- Story age: 24h soft cutoff via recency scoring (no hard filter needed)

</specifics>

<deferred>
## Deferred Ideas

- **Additional content types** — User wants to discuss additional formats beyond thread / long-form / infographic. Scheduled for a later session. Do NOT plan or implement Phase 7 until this discussion is complete, OR note it as a gap if planning proceeds without it.
- Actual image file generation (HTML→screenshot or AI image API) — deferred to post-launch or a future phase. Phase 7 produces the structured brief; rendering is Phase 8's job.
- SerpAPI `result_position` as an engagement proxy — decided against in favour of source credibility tier.
- ContentBundle–DraftItem FK in schema — no migration needed; use `engagement_snapshot` JSONB to store the link for now. Clean FK can be added in a future phase.

</deferred>

---
*Phase: 07-content-agent*
*Context gathered: 2026-04-02*
*Context updated: 2026-04-06*
