# Phase 7: Content Agent - Context

**Gathered:** 2026-04-02
**Updated:** 2026-04-07
**Status:** Ready for planning (full context — replan required before execution)

<domain>
## Phase Boundary

Build the Content Agent: a set of APScheduler jobs that ingest RSS feeds + SerpAPI news, source video clips and quotes from Twitter, score and select the best stories, conduct deep research, and produce structured `ContentBundle` records across 7 content formats for Twitter and Instagram.

**Runs:** Daily at 6am AND 12pm (same full pipeline, catches different stories). No per-run cap — surface everything that qualifies. Target: 4-6 Twitter pieces/day, 1-2 Instagram pieces/day.

**Separate Gold History job:** Bi-weekly Sunday cron, produces a Gold History thread + Instagram carousel alongside the normal news runs.

This phase does NOT include: dashboard rendering, infographic/carousel image generation, Settings page wiring, or any frontend work. Phase 7 produces structured JSON data; Phase 8 renders it.

The `content_agent` job slot is already registered in `scheduler/worker.py` (lock ID 1003, daily 6am cron) — Phase 7 replaces the placeholder. The 12pm run and Gold History Sunday job are new slots to add.

</domain>

<decisions>
## Implementation Decisions

---

### Content Types and Platform Mapping

7 content formats. Each `ContentBundle` is tagged with a `content_type` field.

| `content_type` | Dashboard Label | Twitter | Instagram | Instagram Format |
|----------------|-----------------|---------|-----------|-----------------|
| `thread` | Thread | ✓ | ✗ | — |
| `long_form` | Long-form | ✓ | ✗ | — |
| `breaking_news` | Breaking News | ✓ | ✗ | — |
| `infographic` | Infographic | ✓ | ✓ | Single post |
| `video_clip` | Video Clip | ✓ | ✓ | Single post |
| `quote` | Quote | ✓ | ✓ | Single post |
| `gold_history` | Gold History | ✓ | ✓ | Carousel |

**Priority when multiple pieces qualify in one run:** breaking_news > thread/infographic/long_form > video_clip/quote > gold_history

**Format flag rule:** Every `ContentBundle` record must have `content_type` set. Dashboard uses this as a visible tag on each content card.

---

### Voice & Persona (All Formats)

**Who is speaking:** Senior gold analyst — authoritative, inside-the-room perspective. Makes connections, not summaries.

**Tone:** Precise + punchy. Data-forward. Every sentence earns its place.

**Opening rule:** First line is always the most impactful data point or fact. Lead with the number. Not a preamble.

> Example: "Gold up $84 in 5 sessions. That's the fastest 3-week move since SVB."

**Differentiation requirement:** Every draft (except video_clip reposts) must surface ONE non-obvious insight not in the original article — a pattern, implication, or comparison.

> Example: "This is the 4th consecutive month of central bank buying above 50 tonnes — the last time this sustained pace ran this long was 2010-2012, which preceded a 65% gold price increase."

---

### Format 1: Thread (`thread`)

**Signal:** Story has 3+ separable distinct angles each worth a tweet.

**Output in `draft_content`:**
```json
{
  "format": "thread",
  "tweets": ["tweet 1 (≤280 chars)", "tweet 2", "..."],
  "long_form_post": "single X post ≤2,200 chars covering the same story"
}
```
Thread always produces BOTH the tweet thread (3-5 tweets) AND a long-form X post.

**Platform:** Twitter only.

---

### Format 2: Long-form (`long_form`)

**Signal:** One powerful coherent narrative — single argument or insight. Fewer distinct angles than a thread.

**Output in `draft_content`:**
```json
{
  "format": "long_form",
  "post": "single X post ≤2,200 chars"
}
```

**Platform:** Twitter only.

---

### Format 3: Breaking News Tweet (`breaking_news`)

**Signal:** Urgency/speed — "this just happened, pay attention." Either a major price move, a major announcement, or any story where speed is the value.

**Style:** 1-3 punchy lines. ALL CAPS for key terms. No hashtags.

> Example:
> GOLD JUST HIT $3,200.
> First close above 3,200 in 2026.
> Central banks bought 1,047 tonnes last year. Watch this.

**Optional infographic pairing:** If the story also has strong visual data, Claude may additionally draft an infographic brief. The breaking news tweet is the primary deliverable; the infographic is optional.

**Output in `draft_content`:**
```json
{
  "format": "breaking_news",
  "tweet": "1-3 line breaking news tweet",
  "infographic_brief": null
}
```
`infographic_brief` is `null` unless Claude decides the story warrants it.

**Platform:** Twitter only.

---

### Format 4: Infographic (`infographic`)

**Signal:** Story with clear comparison, trend, or historical parallel better visualized than narrated.

**Two modes:**

1. **Current-data:** Key stats from today's story — prices, tonnage, percentages, production figures.
2. **Historical pattern:** Today's story triggers a historical analysis — how current conditions echo a past pattern and what that predicted. Claude uses training knowledge + SerpAPI verification. Only when story naturally supports a compelling parallel. If historical search fails to verify, fall back to current-data mode.

**Output in `draft_content`:**
```json
{
  "format": "infographic",
  "mode": "current_data" | "historical_pattern",
  "headline": "...",
  "key_stats": [
    {"stat": "Gold hits $3,200/oz", "source": "Reuters, Apr 2026", "source_url": "https://..."}
  ],
  "historical_context": {
    "pattern": "...",
    "then": "...",
    "now": "...",
    "implication": "..."
  },
  "visual_structure": "bar chart | timeline | comparison table | stat callouts | map | historical comparison | trend line",
  "twitter_caption": "...(1-3 sentences, senior analyst voice, for posting with the infographic on X)...",
  "instagram_brief": {
    "headline": "...",
    "key_stats": [...],
    "visual_structure": "...",
    "caption": "...(Instagram caption)..."
  }
}
```
`historical_context` is `null` when `mode = "current_data"`. `instagram_brief` is always populated for infographic format.

**Platform:** Twitter + Instagram (single post).

---

### Format 5: Video Clip (`video_clip`)

**Sourcing:** Content agent performs its own Twitter/X search using the `X_API_BEARER_TOKEN` already in the environment. Searches for video posts from key accounts (Kitco, CNBC, Bloomberg, Peter Schiff, Jim Rickards, WGC, Barrick CEO, mining executives, macro investors, billionaires discussing gold, politicians discussing gold).

**Quality bar:** Source credibility — the person speaking is the primary signal. Respected figure = qualifies. Generic gold commentary from unknown accounts = does not qualify.

**Output in `draft_content`:**
```json
{
  "format": "video_clip",
  "source_account": "...",
  "tweet_url": "https://twitter.com/...",
  "twitter_caption": "1-3 sentences: who said it, what the key claim is, why it matters",
  "instagram_caption": "same content adapted for Instagram single post"
}
```

**Platform:** Twitter + Instagram (single post).

---

### Format 6: Quote/Insight (`quote`)

**Sourcing:** Two pools:
1. Extract strong quotes from articles already being ingested (RSS/SerpAPI).
2. Twitter text post search — notable posts from credible sector figures.

When both a video and a text quote are available for the same person/statement, use `video_clip` format (video takes precedence).

**Quality bar:** Same as video_clip — the person matters most.

**Style:** Pull quote in quotation marks + attribution + 1-2 lines of analyst context.

> "Gold is not in a bubble — it's in a recognition phase."
> — Jim Rickards, Apr 2026
>
> Here's why that framing matters right now: [1-2 analyst sentences]

**Output in `draft_content`:**
```json
{
  "format": "quote",
  "speaker": "Jim Rickards",
  "speaker_title": "Author, macro investor",
  "quote_text": "\"Gold is not in a bubble — it's in a recognition phase.\"",
  "source_url": "https://...",
  "twitter_post": "full formatted post for X",
  "instagram_post": "same content formatted for Instagram single post caption"
}
```

**Platform:** Twitter + Instagram (single post).

---

### Format 7: Gold History (`gold_history`)

**Schedule:** Separate APScheduler job — bi-weekly Sunday cron. Runs alongside (not replacing) the normal 6am/12pm news runs on those Sundays.

**Topic selection:** Claude picks a fresh story each run. Tracks used story topics in the DB (config key `gold_history_used_topics`, JSONB list of story slugs) to avoid repeats. Agent is prompted to think of the most compelling unused story it knows.

**Story types:** How major gold companies were built, famous mergers and acquisitions, historic exploration discoveries, notable industry characters (founders, dealmakers, promoters), crashes and frauds, gold rushes. Examples: Frank Giustra/GoldCorp, Barrick founding by Peter Munk, the Bre-X fraud, Newmont history, Nevada gold rush, Klondike.

**Sourcing:** Claude training knowledge for the story arc + SerpAPI search to verify key facts (dates, deal sizes, names) before drafting.

**Tone:** Drama-first storytelling. Lead with the most dramatic moment. The audacity, the risk, the payoff. Gold industry is full of bigger-than-life characters — lean into that.

**Twitter output:** Thread of 5-7 tweets. Hook tweet, rising action, climax, what it means for gold today.

**Instagram output:** Carousel — one key moment or fact per slide. 4-7 slides total.

**Output in `draft_content`:**
```json
{
  "format": "gold_history",
  "story_title": "How Frank Giustra Built GoldCorp in 24 Hours",
  "story_slug": "giustra-goldcorp-1994",
  "tweets": ["hook tweet", "tweet 2", "...up to 7"],
  "instagram_carousel": [
    {"slide": 1, "headline": "...", "body": "...", "visual_note": "..."},
    {"slide": 2, "headline": "...", "body": "...", "visual_note": "..."}
  ],
  "instagram_caption": "full caption for the carousel post"
}
```

**Platform:** Twitter thread + Instagram carousel.

---

### Instagram Design System

All Instagram content (infographic single posts, video clip posts, quote posts, Gold History carousels) follows the same design language.

**Aesthetic:** Minimalist, data-forward — inspired by a16z's clean editorial Instagram style. One key message per slide (carousels) or per post (singles). No clutter.

**Brand colors:**
- Background: `#F0ECE4` (warm cream)
- Primary text: `#0C1B32` (deep navy)
- Gold accent: `#D4AF37` (metallic gold — used for key numbers, highlights, borders, chart elements)

**Design principles:**
- Large, bold headline or stat as the visual anchor
- Minimal copy — if it can't be said in 15 words, it's too much for a slide
- Gold accent used sparingly (1-2 elements per slide) for maximum impact
- Clean typography — serif for headlines, sans-serif for body
- Phase 8 applies the full visual design; Phase 7's JSON brief specifies content and layout intent, not CSS

**Instagram brief fields** (included in relevant `draft_content` objects):
- `headline` — the large-text anchor (stat, quote, or chapter title)
- `body` — supporting text (max 15 words)
- `visual_note` — layout intent ("full-bleed number", "side-by-side comparison", "simple bar chart", "pull quote centered")
- `caption` — the Instagram post caption (separate from the visual)

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

**SerpAPI keywords — 10 keywords:**
- "gold exploration", "gold price", "central bank gold", "gold ETF", "junior miners", "gold reserves"
- "gold inflation hedge", "Fed gold", "dollar gold", "recession gold"
- Google News engine (`engine=google_news`). Top 5 results per keyword.

**Feed failure handling:** Log to `AgentRun.errors`, continue. One failed feed does not abort the run.

**Deduplication (CONT-04):**
- Step 1: URL exact match
- Step 2: Headline similarity — `difflib.SequenceMatcher` ratio ≥ 0.85
- **Cross-run dedup:** Before surfacing a story, check if a `ContentBundle` with the same URL or similar headline already exists from today's earlier run. Skip if already covered.
- **Tie-break:** Keep the version from the most credible source.

**Story age:** 24-hour soft cutoff via recency scoring.

**Noise filter:** Pure price recap stories score low on relevance naturally. No hardcode needed.

---

### Source Credibility Tiers

| Source | Credibility |
|--------|-------------|
| `reuters.com`, `bloomberg.com` | 1.0 |
| `worldgoldcouncil.org` | 0.9 |
| `kitco.com`, `mining.com` | 0.8 |
| `juniorminingnetwork.com` | 0.7 |
| `goldseek.com`, `investing.com` | 0.6 |
| SerpAPI unknown sources | 0.4 |

---

### Story Scoring (CONT-05)

1. **Relevance (40%):** Claude Haiku, 0–1 scale. Config: `content_relevance_weight` default `"0.40"`.
2. **Recency (30%):** <3h=1.0, <6h=0.8, <12h=0.6, <24h=0.4, ≥24h=0.2. Config: `content_recency_weight` default `"0.30"`.
3. **Source credibility (30%):** See tiers above. Config: `content_credibility_weight` default `"0.30"`.

**Final score:** `(relevance×0.40 + recency×0.30 + credibility×0.30) × 10`

**Quality threshold:** 7.0/10. Config: `content_quality_threshold` default `"7.0"`.

---

### Deep Research Approach (CONT-08)

- **Full article fetch:** `httpx` + `BeautifulSoup`. Fall back to RSS summary on failure (paywall, 403, JS-rendered). Log warning, do not discard.
- **Corroborating sources:** SerpAPI Google News, 2-3 results.
- **Historical infographic verification:** Additional SerpAPI search (~2 credits) to verify historical claims.

**`ContentBundle.deep_research` JSONB:**
```json
{
  "article_text": "...",
  "article_fetch_succeeded": true,
  "corroborating_sources": [{"title": "...", "url": "...", "source": "...", "snippet": "..."}],
  "key_data_points": ["..."]
}
```

---

### Format Decision Logic (CONT-09, CONT-10)

Claude decides format after reading the full research bundle. Decision criteria:

| Signal | → Format |
|--------|----------|
| Urgency + speed ("this just happened") | `breaking_news` |
| 3+ separable angles worth individual tweets | `thread` |
| Comparison, trend, or historical parallel with ≥4 stats | `infographic` |
| Strong video clip found from credible figure | `video_clip` |
| Strong text quote found from credible figure | `quote` |
| Single coherent narrative, no visual data | `long_form` |
| Bi-weekly Sunday (Gold History job) | `gold_history` |

**Default (ambiguous news story):** `thread`

---

### No-Story Flag (CONT-07)

When no story clears 7.0/10 and no strong quote/clip surfaced:
- `ContentBundle` with `no_story_flag=True`, best candidate score stored
- Log to `AgentRun.notes`
- Do NOT create DraftItem or call Senior Agent

---

### Senior Agent Integration (CONT-17)

After qualifying `ContentBundle` created and compliance passed:
- Create `DraftItem`:
  - `platform = "content"`
  - `source_text = story_headline`
  - `source_url = story_url`
  - `source_account = source_name`
  - `alternatives = json.dumps([draft summary])`
  - `rationale = format decision rationale`
  - `score = content_bundle.score`
  - `expires_at = None`
  - `urgency = "low"`
- Call `process_new_items([draft_item.id])` via lazy import
- Store `ContentBundle.id` in `DraftItem.engagement_snapshot` as `{"content_bundle_id": "..."}`

---

### Compliance Checking (CONT-14, CONT-15, CONT-16)

- Claude Haiku compliance call on complete content package
- Ambiguous response = block
- Checks: no "Seva Mining" mention, no financial advice
- If fail: log to `AgentRun.errors`, `compliance_passed=False`, do NOT create DraftItem

---

### APScheduler Jobs

| Job | Lock ID | Schedule | Description |
|-----|---------|----------|-------------|
| `content_agent_morning` | 1003 | Daily 6am | Full pipeline — news, quotes, clips |
| `content_agent_midday` | 1008 | Daily 12pm | Full pipeline — catches midday developments |
| `gold_history_agent` | 1009 | Bi-weekly Sunday | Gold History thread + Instagram carousel |

Config keys for schedules (all DB-driven, follow Phase 9 pattern):
- `content_agent_schedule_hour` = `"6"` (morning run, already seeded in Phase 9)
- `content_agent_midday_hour` = `"12"` (new)
- `gold_history_cron` = `"0 9 */14 * 0"` (9am every other Sunday, or similar)

---

### New Dependencies Required

- `feedparser>=6.0` — RSS ingestion
- `httpx>=0.27` — article fetch
- `beautifulsoup4>=4.12` — article text extraction
- `serpapi>=0.1.5` — SerpAPI client
- `tweepy>=4.0` or direct Twitter API v2 via `httpx` — Twitter video/quote search (check if already present)

---

### Claude's Discretion

- Exact `BeautifulSoup` selector logic for main content extraction
- Twitter API v2 search query construction for video/quote discovery
- Exact Claude Haiku prompt for relevance scoring
- Exact Claude Sonnet prompt for deep research + format decision + drafting. **Must include:** voice/persona instructions (senior analyst, precise/punchy, lead with number, find the non-obvious connection), all 7 format decision criteria, dual-platform output instructions for applicable formats, Instagram design brief instructions (a16z-inspired, Seva colors).
- `ContentBundle` model extension strategy — how to store multi-platform drafts (all in `draft_content` JSONB is recommended, with platform-specific keys)
- Config key naming for new APScheduler jobs
- `AgentRun.notes` JSONB structure

</decisions>

<canonical_refs>
## Canonical References

### Phase Specification
- `.planning/REQUIREMENTS.md` §Content Agent — CONT-01 through CONT-17
- `.planning/ROADMAP.md` §Phase 7 — Goal, success criteria, dependency context

### Existing Models
- `backend/app/models/content_bundle.py` — ContentBundle schema (verify fields support new `content_type` enum + dual-platform `draft_content`)
- `backend/app/models/draft_item.py` — DraftItem schema

### Existing Code to Mirror
- `scheduler/agents/twitter_agent.py` — `_get_config()`, AgentRun logging, two-Claude pattern, `_check_compliance()`
- `scheduler/agents/instagram_agent.py` — Same patterns, most recent
- `scheduler/worker.py` — `content_agent` placeholder at lock ID 1003; `_make_job` wiring pattern
- `scheduler/seed_instagram_data.py` — Seed script pattern
- `scheduler/seed_content_data.py` — Existing content agent seed (extend, don't replace)

### Stack Decisions
- `CLAUDE.md` §Technology Stack — `feedparser 6.0.x`, `serpapi latest`, `httpx 0.27.x`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scheduler/agents/twitter_agent.py` — `_get_config()`, AgentRun, two-Claude (Sonnet + Haiku), `_check_compliance()`
- `scheduler/agents/senior_agent.py` — `process_new_items()` ready to call
- `scheduler/models/draft_item.py` — DraftItem with all needed fields
- No `scheduler/models/content_bundle.py` yet — needs creation as mirror of backend model

### Established Patterns
- Agent structure: `class ContentAgent` → `run()` → `_run_pipeline()`
- Config: `_get_config(session, key, default)`
- AgentRun: create at start, set status, always commit in `finally`
- Error isolation: catch all, log to `AgentRun.errors`, never re-raise

### Integration Points
- `worker.py` `content_agent` placeholder → wire to `ContentAgent().run()`
- New midday + Gold History jobs → add to `build_scheduler()`
- `process_new_items()` → lazy import after DraftItem commit
- `ContentBundle` model may need `content_type` column added (migration required)

</code_context>

<specifics>
## Specific Decisions (Quick Reference)

**Voice:** Senior gold analyst. Precise + punchy. Opens with the number. Finds the non-obvious connection.

**7 formats:** thread / long_form / breaking_news / infographic / video_clip / quote / gold_history

**Platform mapping:**
- Twitter only: thread, long_form, breaking_news
- Twitter + Instagram: infographic (single), video_clip (single), quote (single), gold_history (carousel)

**Instagram design:** a16z minimalist. Colors: background #F0ECE4, text #0C1B32, gold accent #D4AF37. Content agent produces JSON briefs; Phase 8 renders.

**Runs:** 6am + 12pm daily (same pipeline). No per-run cap. Target 4-6 Twitter pieces/day, 1-2 Instagram.

**Gold History:** Separate bi-weekly Sunday APScheduler job. Claude picks story, tracks used slugs in DB. Drama-first. SerpAPI fact verification.

**Breaking news:** 1-3 lines, ALL CAPS key terms, no hashtags. Optional infographic pairing.

**Video clip:** Twitter API search, credibility-based bar, quote-tweet caption.

**Quote:** RSS extract + Twitter text search. Pull quote + attribution + 1-2 analyst lines.

**RSS feeds:** 8 (Kitco, Mining.com, JMN, WGC, Reuters, Bloomberg, GoldSeek, Investing.com)

**SerpAPI:** 10 keywords × top 5. Macro/inflation keywords added.

**Credibility tiers:** Reuters/Bloomberg=1.0, WGC=0.9, Kitco/Mining=0.8, JMN=0.7, GoldSeek/Investing=0.6, unknown=0.4

**Cross-run dedup:** Skip stories already in today's ContentBundle records.

**Format priority (when multiple qualify):** breaking_news > analysis > curation

</specifics>

<deferred>
## Deferred Ideas

- Actual image/carousel file generation (HTML→screenshot or AI image) — Phase 7 produces JSON briefs; rendering is Phase 8.
- ContentBundle–DraftItem FK in schema — use `engagement_snapshot` JSONB for now.
- SerpAPI `result_position` as engagement proxy — decided against, using source credibility tier.
- YouTube as a video clip source — deferred. Twitter/X is primary for now.
- Pre-defined Gold History story bank — decided against; Claude picks fresh with DB tracking.

</deferred>

---
*Phase: 07-content-agent*
*Context gathered: 2026-04-02*
*Context updated: 2026-04-07 — full rewrite with 7 formats, dual-platform, Instagram design system*
