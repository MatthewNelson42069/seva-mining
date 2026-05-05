# Feature Research — v2.0 Daily Summary Feed

**Domain:** Scheduled daily news summary feed (single-operator, gold sector, Ontario mining focus)
**Researched:** 2026-05-05
**Confidence:** HIGH (core summary mechanics, StatCan sources), MEDIUM (Ontario law sources — feed structure unconfirmed), LOW (OLA bill tracker RSS — no RSS feed confirmed to exist)

> **Scope note:** This file supersedes the v1.0 approval-dashboard FEATURES.md for the v2.0 milestone.
> Existing features already built (fetch_stories, Sonnet scoring, APScheduler, FastAPI auth, Twilio WhatsApp,
> Neon Postgres) are not re-researched here. Focus is entirely on new v2.0 surface area.

---

## How Daily Summary Products Work in Production

### Patterns Stolen from Morning Brew / Axios / Stratechery

**Morning Brew pattern (steal this):**
- Fixed section structure every issue — reader knows where to look for "markets" vs "tech" vs "the kicker"
- Each section: 1-sentence headline, 2-4 bullets, source attribution at bullet level (not section level)
- "TLDR" is implicit — bullet 1 IS the TLDR; bullets 2-4 are supporting detail

**Axios Smart Brevity pattern (steal this):**
- "What's new" + "Why it matters" as the first two micro-sections of every story
- Paragraphs are 1-2 sentences max; white space is a feature not waste
- Section headers are anchor links — reader can jump to Gold / Laws / Stats without scrolling
- "Be Smart" closer: one synthesis sentence at the end of each section that the reader can quote

**Stratechery pattern (steal selectively):**
- Cross-issue continuity: "As I noted on Tuesday…" references are normal, expected, valued
- "Building on this morning's update: gold has now broken $X" is a native pattern for that audience
- Daily subscribers tolerate and enjoy callbacks; it signals the author is tracking a narrative arc

**Recommended synthesis for v2.0:**
Each summary card should follow this structure per section:

```
## Section Title (e.g., "Gold News")
**Headline:** [One-sentence lead]
- [Bullet 1 — the TLDR fact]
- [Bullet 2 — supporting context]
- [Bullet 3 — so-what or implication]  ← optional, omit on slow news days
*(Source, HH:MM ET)*
```

For the 12:00 PT card, Sonnet should receive the 08:00 card's gold news section in its context
window and be instructed to note continuity where prices have moved materially. This is more
reliable than a stylistic tone instruction alone — it grounds the cross-reference in actual data.

---

## Feature Landscape

### Table Stakes (Must Ship in v2.0)

| Feature | Why Expected | Complexity | Dependencies |
|---------|--------------|------------|--------------|
| `daily_summary` cron at 08:00 PT + 12:00 PT | Core product premise; without it nothing exists | MEDIUM | APScheduler CronTrigger (existing), `daily_summaries` table (new) |
| Three-section card: Gold News / Ontario Laws / Ontario Stats | Defined product contract; operator expects all three | MEDIUM | New ingestion modules for laws + stats sections |
| Gold News section via existing `fetch_stories()` | fetch_stories is already scored and deduped — reuse it | LOW | `fetch_stories()` (existing) |
| Ontario Laws ingestion + Sonnet filter | Core product requirement; no machine-readable feed — needs custom approach | HIGH | Ontario Newsroom RSS + Sonnet relevance gate (new) |
| Ontario Stats section with empty-state design | StatCan publishes monthly; most days have no new data | MEDIUM | StatCan "The Daily" RSS (new); empty-state copy template |
| Web feed at `/` — vertical scroll, latest 30 days | Replace retired approval dashboard; primary reading surface | MEDIUM | `GET /summaries` endpoint (new), React feed page (new) |
| WhatsApp delivery on each successful summary fire | Operator reads on phone; WhatsApp is the existing delivery channel | LOW | Twilio (existing), summary content formatted for WhatsApp |
| WhatsApp failure alert when cron errors | Silent failures are invisible; operator must know | LOW | Twilio (existing), APScheduler error hook (new) |
| 30-day auto-prune cron | Prevents unbounded DB growth; operator expectation from project spec | LOW | Neon Postgres, daily prune job (new) |
| "No major moves since 08:00" template for 12:00 card | Slow news day at noon is normal; card must still fire | LOW | Sonnet prompt variant, prior summary in context |
| Dedup within summary (same story from Kitco + Reuters = one bullet) | fetch_stories SequenceMatcher 0.85 threshold already handles URL+headline dedup | LOW | `deduplicate_stories()` (existing) — confirmed sufficient |
| Source attribution per bullet — inline "(Kitco, 06:34 ET)" | Operator needs to verify claims; inline citation is the newsletter standard | LOW | Stored in story dict as `source_name` + `published` (existing) |

### Differentiators (Nice-to-Have — Ship if Scope Allows)

| Feature | Value Proposition | Complexity | Dependencies |
|---------|-------------------|------------|--------------|
| Cross-summary continuity reference (noon → morning) | "Gold has now broken $2,500 since this morning's update" — turns two separate cards into a narrative arc | MEDIUM | Pass 08:00 card's gold section into 12:00 Sonnet context; requires `daily_summaries` table with content stored as JSONB |
| Section anchor links in web feed | Reader can jump to "Ontario Laws" without scrolling past gold news | LOW | CSS `id` anchors on section headers; no backend change |
| "Last updated" pointer in empty-state sections | Empty stats section shows "No new data. Last release: Apr 20, 2026 (Feb 2026 data)" | LOW | Query `daily_summaries` for last non-empty stats section; render link |
| Click-through to source URL per bullet | Operator can read full article from the feed | LOW | Store `story.link` in summary JSONB; render as hyperlink in feed |
| WhatsApp formatting: section emoji prefixes | Gold section gets a gold-colored emoji prefix; Laws gets ⚖; Stats gets 📊 | LOW | Twilio WhatsApp message template only |
| Statcan release detection: auto-note when new data drops | "New StatCan data released today (Feb 2026 production figures):" surfaces prominently | MEDIUM | Poll StatCan "The Daily" RSS for table 16-10-0019-01 release notices |

### Anti-Features (Never Ship)

| Feature | Why Requested | Why Problematic |
|---------|---------------|-----------------|
| User comments / reactions on feed cards | Feels like a "complete" feed product | Single-user product — comments are talking to yourself. Adds DB schema complexity for zero value. |
| Sharing / social export of summary cards | "Share today's summary with followers" | Defeats the personal intelligence tool positioning. Adds auth/public-access complexity. Out of scope per locked decisions. |
| Multi-user / multi-operator access | "What if I want to share with a colleague?" | Multi-tenancy is explicitly out of scope until second client exists. Password auth is single-user by design. |
| Custom keyword configuration for summary sections | "I want to add 'platinum' to the gold section" | Operator locked decisions say no custom keywords. Keywords are hard-coded per section; SerpAPI queries are fixed. |
| Push notifications beyond WhatsApp (email, SMS, Slack) | "Redundant delivery channels" | Twilio WhatsApp is sufficient for single-user. Adding channels adds cost and maintenance without value. |
| Archival beyond 30 days | "I want to read summaries from 6 months ago" | 30-day retention is a locked decision. Unlimited retention compounds storage cost with no demonstrated need. |
| "Mark as read" / read-state tracking | Feels like a proper feed app | Single-user vertical scroll; chronological order is self-evidencing. State tracking adds complexity for no functional improvement. |
| Auto-posting summary content to social media | Scope creep from original product pivot | Core value is operator intelligence, not content broadcasting. Explicitly out of scope. |

---

## Source Viability Assessment

### Section 1: Gold News

**Primary source: existing `fetch_stories()`**
The pipeline (RSS: Kitco/Mining.com/JMN/WGC/BNN/Bloomberg/Goldseek + SerpAPI 17 keywords) already
covers gold news comprehensively. `deduplicate_stories()` handles the Kitco-Reuters same-story problem
via URL dedup + SequenceMatcher 0.85 headline similarity. The composite score
(relevance×0.4 + recency×0.3 + credibility×0.3)×10 is already calibrated.

**Recommended approach for summary generation:**
Pass top 5-7 stories (score ≥ 6.0) to a Sonnet summary call. Do NOT re-score for the summary —
reuse scores already computed by fetch_stories. Group bullets by theme if possible (price moves /
institutional demand / macro backdrop), but do not over-engineer the grouping.

**Dedup verdict:** SUFFICIENT — existing `deduplicate_stories()` covers URL + headline similarity.
The 0.85 ratio threshold correctly collapses "Gold hits $3,200" (Kitco) and "Gold price reaches $3,200
record" (Reuters) into one entry, keeping the higher-credibility source. No new dedup work needed.

---

### Section 2: Ontario Mining-Favourable Laws

This is the hardest section. No clean machine-readable feed delivers "Ontario just passed a
mining-favourable law." Every candidate source requires a Sonnet filter.

**Source A: Ontario Newsroom RSS — `https://news.ontario.ca/en/release/feed`**
Verdict: **VIABLE (with mandatory Sonnet filter)**

Confidence: MEDIUM (URL confirmed in project spec; feed structure inferred from standard Ontario govt pattern; content verified by external search results showing active 2025 mining legislation)

- The feed covers all Ontario government press releases — energy, mining, health, transit, everything
- Mining-relevant signal rate: approximately 1-2 items/week when legislation is active; 0-1 items/week in quiet periods
- High noise: ministerial speeches, unrelated announcements dominate
- Requires Sonnet filter to separate "minister gives speech about supporting mining" from "Ontario passes Bill X amending Mining Act"
- The Bill 5 / "Protect Ontario by Unleashing our Economy Act, 2025" example shows actual mining legislation does appear here — it received Royal Assent June 5, 2025

**Source B: Ontario Environmental Registry (ERO) — `https://ero.ontario.ca/`**
Verdict: **MARGINAL**

Confidence: MEDIUM (ERO confirmed active; RSS availability unconfirmed)

- ERO publishes proposed regulatory changes before they become law — mining notices do appear here
- Useful for "proposed amendments to the Mining Act" coverage, but lags behind actual Royal Assent
- No confirmed RSS feed URL; scraping ERO search results is an option but fragile
- Make viable by: adding `ero.ontario.ca` to a SerpAPI keyword search for "Ontario Mining Act" rather than relying on direct RSS

**Source C: Ontario Legislative Assembly bills tracker — `https://www.ola.org/en/legislative-business/bills/current`**
Verdict: **MARGINAL**

Confidence: LOW (no RSS feed confirmed; web interface only)

- Definitive source for bill status (first reading / second reading / committee / Royal Assent)
- No confirmed RSS feed; OLA website is HTML-only for bill listing
- Make viable by: SerpAPI query `"Ontario bill" "Mining Act" OR "mining" site:ola.org` — low yield but catches bill-passage events
- Alternatively: scrape the current bills page weekly, not daily

**Source D: CanLII — `https://www.canlii.org/rss`**
Verdict: **MARGINAL**

Confidence: MEDIUM (CanLII RSS confirmed to exist; mining act consolidation confirmed updated to Jan 1, 2026)

- CanLII publishes updated legislation consolidations; the Ontario Mining Act is tracked here
- RSO 1990, c M.14 last amendment: 2025, c. 17, Sched. 1 (confirmed)
- CanLII RSS covers new legislation and regulation releases across all Canadian jurisdictions
- Noise level is high — covers all legislation, not just mining
- Filter approach: subscribe to CanLII Ontario RSS, Sonnet-filter for Mining Act / Ontario mineral-related content

**Source E: Natural Resources Canada News RSS — `https://natural-resources.canada.ca/corporate/rss-feeds`**
Verdict: **VIABLE (supplementary)**

Confidence: MEDIUM (NRCan RSS confirmed to exist; mining/minerals subset available)

- NRCan publishes federal mining-related announcements, budget impacts, critical minerals policy
- Covers federal (not Ontario-specific) regulatory changes — still relevant for "mining-favourable laws" at federal level
- Cadence: 2-4 items/week across all NRCan topics; mining-specific subset is lower
- Add to ingestion alongside Ontario Newsroom; Sonnet filter handles both feeds with same prompt

**Source F: Mining Association of Canada (MAC) news — `https://mining.ca/resources/`**
Verdict: **VIABLE (supplementary)**

Confidence: MEDIUM (MAC website confirmed active; RSS availability not confirmed)

- MAC publishes policy commentary, budget reactions, regulatory analysis — exactly the "mining-favourable" framing
- Less noisy than government feeds because MAC already filters for mining relevance
- No confirmed RSS feed; use SerpAPI query `"Mining Association of Canada" legislation policy 2026`

**Source G: Ontario Mining Association (OMA) — `https://www.oma.on.ca/news/`**
Verdict: **VIABLE (supplementary)**

Confidence: MEDIUM (OMA website confirmed active with regular news posts; RSS availability unconfirmed)

- OMA releases Ontario-specific mining industry news, regulatory commentary, annual State of Ontario Mining report
- Published State of Mining Sector March 2025 — the type of stats-heavy content that belongs in Section 3
- Use SerpAPI keyword `"Ontario Mining Association" site:oma.on.ca` or add OMA news feed if RSS is available at `oma.on.ca/modules/news/en`

**Recommended Ontario Laws ingestion stack:**
1. Ontario Newsroom RSS (`news.ontario.ca/en/release/feed`) — PRIMARY
2. NRCan news RSS (`natural-resources.canada.ca/corporate/rss-feeds`) — SECONDARY
3. SerpAPI keyword query: `"Ontario" "mining" ("bill" OR "act" OR "regulation" OR "policy") Canada` — TERTIARY
4. Sonnet filter on ALL results (see prompt recommendation below)

**Realistic frequency:** 1-3 genuinely new mining-favourable law items per week when the legislature is sitting; near-zero during summer recess (June–August) and winter break. Section will be empty 3-4 days out of 5 on average. Empty-state design is mandatory, not an edge case.

---

### Section 3: Ontario Gold Mining Statistics

**Source A: StatCan Table 16-10-0019-01 (Monthly Mineral Production, metallic minerals)**
Verdict: **VIABLE — but monthly, ~2-month lag**

Confidence: HIGH (table confirmed active; release cadence confirmed from search results)

URL: `https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1610001901`
API: `https://www150.statcan.gc.ca/t1/wds/rest/` (StatCan WDS JSON API, confirmed)

Release pattern (confirmed from actual release dates):
- April 2025 data → released June 20, 2025
- September 2025 data → released November 20, 2025
- February 2026 data → released April 20, 2026
- Pattern: data for month M releases approximately the 19th–21st of month M+2

Practical implication: Ontario gold production figures for January 2026 will not be available until
approximately March 20, 2026. The summary will have genuine new StatCan data roughly once per month
on the 19th-21st. All other days → empty state for this sub-source.

StatCan WDS API access pattern:
```
GET https://www150.statcan.gc.ca/t1/wds/rest/getSeriesInfoFromVector/{vectorId}
GET https://www150.statcan.gc.ca/t1/wds/rest/getDataFromVectorsAndLatestNPeriods/{vectorId}/1
```
No API key required. JSON response. Vector IDs for Ontario gold production need to be resolved
once at setup by querying table 16-10-0019-01 metadata for Ontario + Gold rows.

**Source B: StatCan "The Daily" RSS for mineral production releases**
Verdict: **VIABLE — the best trigger mechanism**

Confidence: HIGH (The Daily confirmed to publish mineral production release notices; RSS feeds confirmed at statcan.gc.ca)

"The Daily" (`https://www150.statcan.gc.ca/n1/dai-quo/index-eng.htm`) publishes a release notice
the same day StatCan publishes new mineral production data. Subscribe to The Daily RSS and Sonnet-filter
for "mineral production" releases — this is the trigger event for Section 3 having real content.

**Source C: Natural Resources Canada — Annual Statistics of Mineral Production**
Verdict: **VIABLE (annual, supplementary)**

Confidence: HIGH (NRCan confirmed to publish annual mineral production; URL confirmed active)

URL: `https://mmsd.nrcan-rncan.gc.ca/prod-prod/ann-ann-eng.aspx`

Annual data for 2024 was released February 25, 2026. Useful once per year for the annual summary
bulletin. Not a daily source.

**Source D: Ontario Geological Survey (OGS) — Mineral Exploration Activity Reports**
Verdict: **MARGINAL**

Confidence: MEDIUM (OGS confirmed active; activity reports confirmed; cadence unclear)

URL: `https://www.geologyontario.mndm.gov.on.ca/mines/ogs/rgp/mer_listing_e.html`

- OGS publishes monthly and year-to-date mineral exploration activity reports
- These are exploration activity counts (new claims staked, drill holes reported) — useful context but not production figures
- No confirmed RSS feed; HTML-only listing
- Make viable by: SerpAPI query `"Ontario Geological Survey" gold production OR exploration statistics`

**Source E: OMA State of Ontario Mining report (annual)**
Verdict: **VIABLE (annual, high-value when it drops)**

Confidence: MEDIUM (2025 report confirmed published March 2025; annual cadence confirmed)

The OMA State of Ontario Mining Sector report publishes in Q1 each year and contains:
- Ontario GDP contribution from mining
- Employment figures (~22,000 direct jobs, $150k avg salary)
- Capital expenditures ($5.2B in 2023)
- Mineral export values ($64B in 2023)

This is exactly the type of stats that belong in Section 3 when the report drops. When it does, Section 3
should feature it prominently even though it is technically not "new today" data.

**Recommended Ontario Stats ingestion stack:**
1. StatCan "The Daily" RSS — monitor for mineral production release notices (monthly event, ~19th-21st)
2. StatCan WDS API call on confirmed release day to pull Ontario gold production figures
3. SerpAPI query `"Ontario gold" production statistics site:statcan.gc.ca OR site:nrcan.gc.ca OR site:oma.on.ca`
4. Section fires with real data approximately once/month; empty state all other days

---

## Sonnet Filter Prompts (Recommended)

### Ontario Laws Relevance Filter

Minimize false positives (minister speeches, unrelated bills) while catching genuine law/policy changes.

```
You are a regulatory filter for an Ontario gold mining industry intelligence feed.

Evaluate this Ontario government news item and respond with a JSON object only.

Rules:
- KEEP if: The item announces passage, Royal Assent, or coming-into-force of a law, bill, regulation, or
  Order in Council that DIRECTLY affects mining operations, mineral exploration, mine permitting, land
  access, environmental assessment for mines, or mineral rights in Ontario.
- KEEP if: A federal or Ontario government policy change (budget measure, critical minerals strategy,
  Indigenous consultation framework change) materially affects the economics or regulatory burden
  of gold mining in Ontario.
- REJECT if: A minister gives a speech, attends an event, or "supports" mining without announcing
  a concrete regulatory change.
- REJECT if: The item is about a specific company's mine (company-specific news, not sector-wide).
- REJECT if: The regulatory change is unrelated to mining (e.g., healthcare, transit, housing).
- REJECT if: The item is about environmental opposition to a mining project without a regulatory change.

Respond ONLY with:
{"keep": true|false, "reason": "one sentence", "law_name": "Bill X / Act name or null", "favour_or_neutral": "favourable|neutral|unfavourable|unclear"}

Title: {title}
Summary: {summary}
```

Key discrimination logic: "minister announces support for mining" → REJECT; "Ontario passes Bill 5 amending Mining Act" → KEEP. The `law_name` field forces the model to name the actual legislation, which is a strong signal for false-positive detection — if it cannot name a law, the item is probably a speech.

### Ontario Stats Relevance Filter (simpler — less noise in this feed)

```
You are a statistics filter for an Ontario gold mining feed.

Evaluate this item and respond with JSON only.

KEEP if: The item contains new statistical data about Ontario gold/mineral production, exploration
activity, investment figures, employment numbers, or jurisdictional rankings published by StatCan,
NRCan, Ontario Geological Survey, or Ontario Mining Association.
REJECT if: The item is opinion, forecast, or commentary without new data.
REJECT if: The data is about a specific company only (not sector-wide).

{"keep": true|false, "data_type": "production|exploration|employment|investment|ranking|other|null", "source_org": "StatCan|NRCan|OGS|OMA|other|null"}
```

---

## Empty-State Copy (Recommended Defaults)

### Gold News — slow day (12:00 summary, nothing material since 08:00)

> **No major moves since the 08:00 summary.** Gold is holding near {last_price}. Next scheduled update: 08:00 PT tomorrow.

Note: pass `last_price` from a spot price API call (Kitco or metals-api.com) at summary generation time — a static "no news" message without current price is less useful than one grounding the user.

### Ontario Laws — no new items today

> **No new Ontario mining-related laws or regulatory changes today.** Last update: {date of last non-empty laws section} — {law_name with link if stored}.

Do NOT say "check back later" — it feels like a broken app. The pointer to the last real item is more useful than a blank state.

### Ontario Stats — between monthly StatCan releases

> **No new production statistics released today.** StatCan's next Monthly Mineral Production Survey release is expected around {next_release_estimate}. Last data: {month/year of last StatCan release} — Ontario gold production: {last_known_figure} oz.

Storing `last_known_figure` in the DB as part of the summary JSONB means the agent can always fill this in without re-querying StatCan. Update it each time a real StatCan release is processed.

---

## Deduplication Strategy (Confirmed Sufficient)

`fetch_stories()` runs `deduplicate_stories()` before scoring. Two-step process:
1. URL exact match — first occurrence wins
2. SequenceMatcher headline similarity ≥ 0.85 — higher-credibility source wins on tie

For v2.0 summary generation, the gold news bullets are generated from the top-N already-deduped stories.
No additional dedup layer is needed. The existing approach correctly handles the Kitco/Reuters case.

**One gap:** Cross-session dedup (same story appearing in both 08:00 and 12:00 summaries). The 30-min
cache refreshes between summary fires. A story published at 07:30 will appear in both the 08:00 and
potentially the 12:00 summary if it is still the top-scoring item.

**Recommendation:** In the Sonnet 12:00 prompt, pass the 08:00 summary's bullet list and instruct
Sonnet to omit any story already covered there unless there is material new development. This is the
same mechanism as the cross-summary continuity differentiator — solving both problems with one prompt
addition.

---

## Feature Dependencies

```
[daily_summary cron fires at 08:00 PT]
    └──requires──> [APScheduler CronTrigger America/Los_Angeles (existing)]
    └──requires──> [daily_summaries table (new)]
    └──requires──> [Gold News ingestion: fetch_stories() (existing)]
    └──requires──> [Ontario Laws ingestion module (new)]
    └──requires──> [Ontario Stats ingestion module (new)]
    └──requires──> [Sonnet summary generation call (new)]
    └──triggers──> [WhatsApp delivery on success (Twilio existing)]
    └──triggers──> [WhatsApp failure alert on cron error (new hook)]

[daily_summary cron fires at 12:00 PT]
    └──requires──> [Same as 08:00 above]
    └──enhances-with──> [08:00 summary JSONB from daily_summaries (differentiator)]

[Web feed at /]
    └──requires──> [GET /summaries API endpoint (new)]
    └──requires──> [daily_summaries table with content JSONB (new)]
    └──requires──> [React feed page replacing /queue (new)]

[30-day prune cron]
    └──requires──> [daily_summaries table (new)]
    └──independent-of──> [summary generation — runs on separate schedule]

[Ontario Laws section — real content]
    └──requires──> [Ontario Newsroom RSS ingestion (new)]
    └──requires──> [NRCan news RSS ingestion (new)]
    └──requires──> [Sonnet laws relevance filter (new)]

[Ontario Stats section — real content]
    └──requires──> [StatCan "The Daily" RSS monitor (new)]
    └──requires──> [StatCan WDS API call on release day (new)]

[Empty-state copy for Laws + Stats]
    └──requires──> [daily_summaries table queryable for last non-empty section (new)]

[Cross-summary continuity — differentiator]
    └──requires──> [08:00 daily_summaries row committed before 12:00 cron fires]
    └──requires──> [JSONB structure storing section content separately (new schema decision)]

[Source attribution per bullet]
    └──requires──> [story.source_name + story.published stored in summary JSONB alongside each bullet (new schema field)]
    └──independent-of──> [dedup — attribution happens after dedup, not before]
```

### Dependency Notes

- **Ontario Laws ingestion is the only net-new pipeline complexity** — all other sections reuse existing
  infrastructure (fetch_stories for Gold, StatCan API for Stats which is a simple HTTP call).
- **30-day prune is independent** — does not need to coordinate with summary generation; safe to ship
  in a separate phase and run from day one.
- **Cross-summary continuity requires JSONB schema design** — the `daily_summaries` table must store
  gold news bullets as a structured field, not just a rendered string, for the 12:00 Sonnet call to
  reference them. This is a schema decision to lock early.
- **WhatsApp failure alert requires APScheduler error hook** — APScheduler v3 supports `add_listener`
  with `EVENT_JOB_ERROR`; this is a small addition to the scheduler worker, not a new service.

---

## MVP Definition for v2.0

### Must Ship

- [ ] `daily_summaries` table with `id`, `fired_at`, `summary_type` (08:00/12:00), `content` (JSONB), `whatsapp_sent` bool
- [ ] `daily_summary` APScheduler job: 08:00 PT + 12:00 PT CronTrigger
- [ ] Gold News section: pass top-5 stories from fetch_stories() to Sonnet; return headline + 3 bullets + source attribution
- [ ] Ontario Laws ingestion: Ontario Newsroom RSS + NRCan RSS + SerpAPI query; Sonnet relevance filter
- [ ] Ontario Stats ingestion: StatCan "The Daily" RSS monitor; StatCan WDS API call on release day
- [ ] Empty-state copy for all three sections (strings, not magic — just correct copy in the prompt)
- [ ] "No major moves since 08:00" template for 12:00 gold section on slow days
- [ ] `GET /summaries` — returns latest 30 days of summary cards, paginated
- [ ] React feed page at `/` — vertical scroll, one card per summary, three sections rendered
- [ ] WhatsApp delivery: send formatted summary on successful fire
- [ ] WhatsApp failure alert: send alert on APScheduler `EVENT_JOB_ERROR` for daily_summary job
- [ ] 30-day prune cron: delete `daily_summaries` rows where `fired_at < now() - interval '30 days'`

### Ship After Core is Validated

- [ ] Cross-summary continuity: pass 08:00 gold bullets into 12:00 Sonnet context
- [ ] Section anchor links in web feed (`#gold-news`, `#ontario-laws`, `#ontario-stats`)
- [ ] "Last updated" pointer in empty-state sections (query for last non-empty section row)
- [ ] Click-through source URLs per bullet in web feed

### Never Ship (v2.0 and beyond)

- [ ] User comments, sharing, public access to feed
- [ ] Multi-user / multi-operator support
- [ ] Custom keyword configuration per section
- [ ] Notification channels beyond WhatsApp
- [ ] Archival beyond 30 days
- [ ] Auto-posting summaries to social media

---

## Phase Sequencing Recommendation

**Phase 1 (foundation):** `daily_summaries` table + `daily_summary` cron stub + Gold News section + WhatsApp delivery + failure alert + 30-day prune. The cron fires, produces a Gold News card, delivers to WhatsApp. Ontario sections are placeholders ("Coming soon").

**Phase 2 (complete the card):** Ontario Laws ingestion + Sonnet filter + Ontario Stats ingestion + empty-state copy for all sections. Now the full three-section card works.

**Phase 3 (web feed):** `GET /summaries` endpoint + React feed page replacing /queue. Now the operator has a reading surface beyond WhatsApp.

**Phase 4 (polish):** Cross-summary continuity, anchor links, click-through URLs, "last updated" pointers.

**Rationale:** Phase 1 delivers the highest-value piece (gold news on WhatsApp) immediately. Phase 2 completes the card. Phase 3 adds the web surface. Phase 4 adds differentiators. The dependency chain is linear — each phase is independently shippable.

---

## Sources

- [StatCan Table 16-10-0019-01 — Monthly Mineral Production, metallic minerals](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1610001901)
- [StatCan WDS API documentation](https://www.statcan.gc.ca/en/developers/wds/user-guide)
- [StatCan "The Daily" — Monthly Mineral Production, February 2026 (released Apr 20, 2026)](https://www150.statcan.gc.ca/n1/daily-quotidien/260420/dq260420c-eng.htm)
- [StatCan Annual Mineral Production Survey 2024 (released Feb 25, 2026)](https://www150.statcan.gc.ca/n1/daily-quotidien/260225/dq260225f-eng.htm)
- [NRCan Annual Statistics of Mineral Production](https://mmsd.nrcan-rncan.gc.ca/prod-prod/ann-ann-eng.aspx)
- [NRCan RSS Feeds](https://natural-resources.canada.ca/corporate/rss-feeds)
- [Ontario Newsroom](https://news.ontario.ca/releases/en)
- [Ontario Legislative Assembly — Current Bills](https://www.ola.org/en/legislative-business/bills/current)
- [CanLII RSS Feeds](https://www.canlii.org/rss)
- [CanLII — Ontario Mining Act RSO 1990 c M.14 (latest amendment: 2025, c. 17, Sched. 1)](https://www.canlii.org/en/on/laws/stat/rso-1990-c-m14/latest/rso-1990-c-m14.html)
- [Ontario Mining Association News](https://www.oma.on.ca/news/)
- [OMA State of Ontario Mining Sector Report 2025](https://www.oma.on.ca/media/jy3f0tgd/oma-economic-published-march-2025-final.pdf)
- [Mining Association of Canada Resources](https://mining.ca/resources/)
- [Ontario ERO — Mining Act Notice](https://ero.ontario.ca/notice/025-0409)
- [Bill 5 analysis — DLA Piper](https://www.dlapiper.com/en-us/insights/publications/2025/06/what-foreign-mining-investors-should-know-about-ontario-bill-5)
- [Axios Smart Brevity format description](https://help.axios.com/hc/en-us/articles/36222626161435-What-is-the-Axios-Smart-Brevity-style)
- [OGS Mineral Exploration Activity Reports](https://www.geologyontario.mndm.gov.on.ca/mines/ogs/rgp/mer_listing_e.html)
- [NRCan Mining Data, Statistics and Analysis](https://natural-resources.canada.ca/minerals-mining/mining-data-statistics-analysis)

---

*Feature research for: v2.0 Daily Summary Feed — Seva Mining*
*Researched: 2026-05-05*
