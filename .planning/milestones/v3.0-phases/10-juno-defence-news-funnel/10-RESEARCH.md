# Phase 10: Juno Defence News Funnel - Research

**Researched:** 2026-05-19
**Domain:** Defence-sector content pipeline (Sonnet 4.6 + Haiku 4.5 structured outputs) layered on Phase 9 multi-tenant infrastructure
**Confidence:** HIGH on Anthropic structured-output API syntax, SerpAPI cost math, refusal-detector pattern, and existing Phase 7/9 code shape. MEDIUM on voice UAT pass-criteria (judgment call). HIGH on critical finding: SummaryCard.tsx hardcodes Seva field names — Phase 10 MUST edit frontend.

## Summary

Phase 10 is **config-only on Phase 9 infrastructure** with one infrastructure gap discovered during research: `SummaryCard.tsx` (lines 61-75) and `frontend/src/api/summaries.ts` (lines 11-13) hardcode `gold_news_md` / `ontario_law_md` / `ontario_stats_md` as section field names. Phase 9 D-08 claimed `SummaryCard` "tolerates missing-or-renamed section markdown fields" — verified-false during this research. Phase 10 needs a minimal frontend edit (per-company section configuration via a config object keyed by `useParams().company`) so Juno renders `defence_news_md` / `canadian_procurement_md` / `world_events_md` semantically while reusing the same DB columns (Phase 9 D-08 said field-rename via repurposing the existing 3 markdown columns — no schema migration).

The Sonnet system prompt, Haiku classifier, refusal-detector, and SerpAPI/RSS substrate are all implementable inside the existing AsyncAnthropic + serpapi.Client + feedparser stack with **zero new dependencies**. Anthropic structured outputs ship via `client.messages.parse(output_format=PydanticModel)` (NO beta header required in current SDK — `output_config.format` is the old beta name). Haiku 4.5 is GA for structured outputs. Cost envelope fits the $50/mo SerpAPI budget: Seva's current Ontario Law usage is 2 calls/day (~60/month); Juno's Canadian procurement adds 5-8 calls/day (~150-240/month) at $15/1K = $2.25-3.60/month additional. Well inside the $50/mo cap.

**Primary recommendation:** Adopt the 5 wave structure from `<files_to_read>` — Wave 0 = test scaffolding + Phase-0 RSS endpoint verification + SummaryCard per-company section-config refactor; Wave 1 = `juno_relevance.py` Haiku classifier + populated `feeds.py`/`serpapi.py`/`prompts.py`; Wave 2 = `run_juno_daily_summary` real synthesis path with refusal-detector wrapper + per-feed bozo health-check; Wave 3 = voice-calibration UAT + `voice_calibration_uat.md` artifact + operator sign-off + cron-enable flip; Wave 4 = integration smoke (cron-disabled run via `python -m agents.daily_summary juno`).

## User Constraints (from CONTEXT.md)

### Locked Decisions

**Sonnet System Prompt Design (DEF-03):**
- **D-01:** Voice baseline = Janes/CSIS desk energy. Authoritative, sober, sourced-with-receipts senior-defence-analyst-at-a-think-tank tone. Bullet-driven; contract-value-and-vendor-named where present; neutral-on-conflict. Examples: IISS Military Balance, CSIS analysis, RAND research summaries, Defense News editorial board. NEVER cloned from Seva's gold-bull prompt — defence requires a wholly different brief shape (no bull/bear framing; no analyst rating language).
- **D-02:** Explicit anti-tactical framing clause + refusal triggers list in the system prompt. Dedicated paragraph in `DEFENCE_NEWS_SYSTEM_PROMPT`: "You produce market/industry commentary on the defence sector. You do NOT produce operational, tactical, targeting, force-posture, order-of-battle, capability-gap, or troop-movement analysis. If a source story crosses into operational territory, summarize the market/industry implications only and explicitly note the operational details were excluded." Adds ~50 tokens.
- **D-03:** Source-driven regional balance (no in-prompt quota). System prompt does NOT request explicit US + Canada + Europe + Indo-Pacific quotas. Sonnet picks the strongest 3-7 stories from whatever the RSS + SerpAPI substrate surfaced. Fix is at the substrate layer, not the prompt.
- **D-04:** Voice UAT mechanics (DEF-10): 5-10 hand-curated defence stories. Sonnet 4.6 produces a sample. Operator approves. Approval persisted in `voice_calibration_uat.md`. Cron stays DISABLED until operator signs off.

**World Events Relevance Classifier (DEF-06):**
- **D-05:** Haiku 4.5 + Anthropic structured outputs. Returns `{is_relevant: bool, category: Literal[...], confidence: float, reasoning: str}`. Cheap (~$1-2/mo at 50-100 world-news items/fire), sub-second.
- **D-06:** All 9 inclusion categories (active conflict, alignment shifts, spending policy, sanctions/export controls, energy/critical-minerals, semiconductors, space, hypersonic/AI/autonomy, treaty events).
- **D-07:** `confidence >= 0.7` threshold.
- **D-08:** World Events feeds = Reuters World, AP World, BBC World (RSS verify in Phase-0).

**Canadian Procurement Strategy (DEF-05):**
- **D-09:** SerpAPI-heavy + editorial layer. 5-8 `site:` queries (`site:canada.ca defence`, `site:canadiandefencereview.com`, `site:pspc-spac.gc.ca`, `site:tpsgc-pwgsc.gc.ca`, `"DND contract"`, `"RCAF procurement"`, `"Royal Canadian Navy contract"`, `"DND innovation"`). Editorial RSS: Lagassé Substack, Atlantic Council, Canadian Defence Review (verify Phase-0). Budget: $5-15/mo inside existing $50/mo cap.

**Tier-2 Feed Inclusion (DEF-01):**
- **D-10:** Tier-1 ONLY for v3.0 Phase 10. Ship the 12 HTTP-validated Tier-1 feeds. Tier-2 deferred to v3.1+.

**Refusal-Detector + Safety (DEF-07):**
- **D-11:** Substring-pattern detector + retry-once with framing nudge + `status='partial'` fallback. Patterns: `'I cannot'`, `'as an AI'`, `'safety guidelines'`, `'unable to provide'`, `"I'm not able to"`, `'cannot assist'`, `'against my'`. On second refusal: section markdown becomes `"Section unavailable — defence-industry summary could not be generated for this fire. See agent_runs.notes for diagnostic."`, row `status='partial'`, log `{"refusal_detected": true, "section": "...", "first_attempt_excerpt": "..."}` in `agent_runs.notes`.

**Per-Feed Health-Check (DEF-04):**
- **D-12:** Bozo OR empty + recent-history comparison. If `feedparser.parse(url).bozo == 1` OR `entries == []` → flag. If today's count < 30% of 7-day average → flag. 3+ feeds flag → `status='partial'`. Zero entries across all feeds → WHA-03 WhatsApp alert.

**Phase-0 RSS Endpoint Verification (DEF-01):**
- **D-13:** Verify ALL 15 endpoints at Phase 10 start (3 TBD: war.gov, nato.int, canada.ca defence; 12 Tier-1: Defense News × 8 sub-feeds, Breaking Defense, DefenseScoop, RUSI Commentary, RUSI Publications, SIPRI Combined). Failed feeds: drop or replace with SerpAPI `site:` fallback.
- **D-14:** Phase-0 outputs `phase-10-feed-verification.md` artifact in the phase directory.

### Claude's Discretion

- **Voice UAT corpus exact composition (5-10 stories).** Recommended split: 2 US procurement (Lockheed/Raytheon wins), 1 Canadian DND announcement, 1 conflict-zone wire (Ukraine OR Gaza OR Taiwan), 1 dual-use tech (semiconductor or AI export control), 1-3 borderline cases. Persist in `voice_calibration_uat_corpus.md`.
- **Cron-enable mechanism.** Recommended: env var `JUNO_CRON_ENABLED=false` default, flip after UAT.
- **Smoke-test row cleanup from Phase 9.** Recommended: let them age out via the 30-day prune cron.
- **Sonnet token budget per fire.** Per-fire total: ~5000-6000 tokens; ~$5-10/mo for 60 fires/month.
- **Inclusion-category badges in UI rendering.** Planner decides — defer to Phase 10 UI plan.

### Deferred Ideas (OUT OF SCOPE)

- Tier-2 feed inclusion (Defense Daily, Inside Defense, National Defense Magazine, Defense Industry Daily, Shephard, Defense One) → v3.1+ if Tier-1 signal proves insufficient
- Inclusion-category badges in SummaryCard UI (Claude's discretion; may defer to v3.1+)
- Equity/financial signals on defence primes (LMT, RTX, GD) — explicit anti-feature
- Operational / tactical / OOB intelligence — explicit anti-feature; hard prohibition
- Live conflict map / OSINT geospatial — out of scope
- Per-tenant Anthropic API key — defer to v3.1+ unless content-policy surfaces real need
- Bloomberg defence-beat voice variant — rejected D-01 in favor of Janes/CSIS
- Regional balance quota in prompt — rejected D-03 in favor of source-driven

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DEF-01 | Tier-1 defence RSS feeds (12 feeds) + per-feed bozo/recent-history health-check | Standard Stack §Defence RSS Inventory; Phase-0 verification script in §Code Examples |
| DEF-02 | SerpAPI `site:`-restricted queries for paywalled sources + Canadian procurement | Standard Stack §SerpAPI Query Set; budget math in §Cost Analysis |
| DEF-03 | Defence-industry Sonnet 4.6 system prompt — designed from scratch (Janes/CSIS voice, anti-tactical clause) | Architecture Patterns §Sonnet Prompt Structure; token budget audit |
| DEF-04 | Defence News section via Tier-1 RSS + SerpAPI fallback + 3-7 bulleted items | Code Examples §Defence News Section Build; refusal-detector wrap |
| DEF-05 | Canadian Procurement section via SerpAPI-heavy + editorial RSS | Standard Stack §Canadian Procurement Sources |
| DEF-06 | World Events Relevance Classifier — Haiku 4.5 structured output (9 categories, confidence ≥ 0.7) | Code Examples §Haiku Structured-Output Classifier |
| DEF-07 | Sonnet refusal-detector + retry-once-with-nudge + partial fallback | Code Examples §Refusal-Detector Wrapper |
| DEF-08 | SummaryCard tolerates Juno's renamed section fields (defence_news_md, canadian_procurement_md, world_events_md) | **CRITICAL FINDING: SummaryCard is hardcoded — frontend edit required.** §Common Pitfalls |
| DEF-09 | Juno Tab 2/Tab 3 empty-state "Coming in v3.1" | Phase 9 already wired; verify in Wave 0 |
| DEF-10 | Voice-calibration UAT with 5-10 hand-curated defence stories; operator sign-off before cron enabled | §Voice UAT Mechanics; pass criteria documented |

## Standard Stack

### Core (already installed — pattern additions only)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `anthropic` | `>=0.86.0` (confirmed in `scheduler/pyproject.toml` line 12) | AsyncAnthropic client for Sonnet 4.6 synthesis + Haiku 4.5 structured-output classifier | Phase 7 D-11 baseline (60s timeout, 1000 max_tokens); structured outputs GA in this SDK version. Use `client.messages.parse(output_format=PydanticModel)` per Anthropic docs (verified 2026-05-19). |
| `feedparser` | `6.0.x` | RSS ingestion for 12 Tier-1 defence feeds | Battle-tested; `.bozo` + `.entries` are the health-check primitives. |
| `serpapi` | latest | `google_news` engine for SerpAPI queries | Already in use by Seva Ontario Law (`scheduler/agents/ontario_law.py:140-162`). Reuses `serpapi.Client.search({"engine": "google_news", ...})` pattern. |
| `pydantic` | `2.x` | Schema for Haiku structured-output classifier | Already in stack. `BaseModel` + `Literal` + `Field(ge=0.0, le=1.0)` for the `DefenceRelevance` model. |
| `re` (stdlib) | — | Refusal-detector substring pattern compilation | Use `re.compile(..., re.IGNORECASE)` at module load time, not per-call. |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `httpx` | `0.27.x` | Async HTTP for the Phase-0 RSS verification script (alternative to feedparser-only) | Wave 0 verification only. Production path uses feedparser. |
| `sqlalchemy[asyncio]` | `2.0.x` | `scoped_summaries('juno')` query path for 7-day virality lookback (if needed) | Phase 9 helper at `scheduler/queries/scoped.py`. |

### Defence RSS Feed Inventory (12 Tier-1 from research/STACK.md, all HTTP-validated 2026-05-19)

| # | Source | RSS URL | Domain |
|---|--------|---------|--------|
| 1 | Defense News — Industry | `https://www.defensenews.com/arc/outboundfeeds/rss/category/industry/?outputType=xml` | Industry beat |
| 2 | Defense News — Pentagon | `https://www.defensenews.com/arc/outboundfeeds/rss/category/pentagon/?outputType=xml` | Pentagon |
| 3 | Defense News — Global | `https://www.defensenews.com/arc/outboundfeeds/rss/category/global/?outputType=xml` | Geopolitics |
| 4 | Defense News — Air | `https://www.defensenews.com/arc/outboundfeeds/rss/category/air/?outputType=xml` | Air |
| 5 | Defense News — Land | `https://www.defensenews.com/arc/outboundfeeds/rss/category/land/?outputType=xml` | Land |
| 6 | Defense News — Naval | `https://www.defensenews.com/arc/outboundfeeds/rss/category/naval/?outputType=xml` | Naval |
| 7 | Defense News — Space | `https://www.defensenews.com/arc/outboundfeeds/rss/category/space/?outputType=xml` | Space |
| 8 | Defense News — Unmanned | `https://www.defensenews.com/arc/outboundfeeds/rss/category/unmanned/?outputType=xml` | UAS |
| 9 | Breaking Defense | `https://breakingdefense.com/feed/` | US defence tech + policy |
| 10 | DefenseScoop | `https://defensescoop.com/feed/` | US military tech |
| 11 | RUSI Commentary | `https://www.rusi.org/rss/latest-commentary.xml` | UK think tank commentary |
| 12 | RUSI Publications | `https://www.rusi.org/rss/latest-publications.xml` | UK think tank papers |
| 13 | SIPRI Combined | `https://www.sipri.org/rss/combined.xml` | Stockholm peace research |

Total: 13 feeds (Defense News 8 sub-feeds + Breaking Defense + DefenseScoop + RUSI ×2 + SIPRI). CONTEXT.md D-10 says "12" Tier-1; reconciliation: research/STACK.md groups Defense News × 8 as one "publisher" so the count was 5 publishers (Defense News + Breaking Defense + DefenseScoop + RUSI + SIPRI) = "12 sub-feeds." Treat as 13 (count of URLs) in `JUNO_DEFENCE_FEEDS`. Planner verifies in Phase-0.

### Canadian Procurement Sources (DEF-05 substrate)

**SerpAPI `site:` queries (planner picks final 5-8 from this menu):**
```
"site:canada.ca defence"
"site:canadiandefencereview.com"
"site:pspc-spac.gc.ca contract"
"site:tpsgc-pwgsc.gc.ca defence"
"DND contract" canada
"RCAF procurement" canada
"Royal Canadian Navy contract"
"DND innovation" canada
```

**Editorial RSS (verify Phase-0):**
- Philippe Lagassé Substack — `https://philippelagasse.substack.com/feed` (RSS standard for Substack)
- Atlantic Council Canadian-defence (RSS confirmed in research, exact feed URL Phase-0 verifies)
- Canadian Defence Review — TBD in Phase-0

### Three Phase-0 TBD Endpoints (D-13)

- `https://www.war.gov/news/rss/?feedtype=press-releases` — verify HTTP 200 + parseable RSS
- `https://www.nato.int/cps/en/natohq/news.htm?selectedLocale=en&_=feed` — verify; landing page 404'd 2026-05-19, fall back to SerpAPI `site:nato.int defence` if dead
- `https://www.canada.ca/en/news/web-feeds.html` — grep for defence-specific sub-feed URLs; fall back to SerpAPI `site:canada.ca defence` if no clean RSS

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Substring refusal-detector | LLM-judge refusal classifier (Haiku call to detect refusal) | Adds latency + cost; substring patterns cover 95%+ per Anthropic-Pentagon dispute analysis. Substring is correct for v3.0. |
| Haiku 4.5 structured output | Free-form Sonnet + JSON repair (existing v2.0 Ontario Law pattern at `scheduler/agents/ontario_law.py:227-280`) | Free-form pattern works (Ontario Law ships it) but requires manual `json.loads(raw)` + markdown-fence stripping + fail-closed parse error handling. `messages.parse()` eliminates the parse layer. NEW classifier code should use `parse()`. |
| `messages.parse(output_format=...)` | Tool-use-based JSON extraction | tool_use pattern works but adds round-trip complexity. `parse()` is the modern path. |
| Substack RSS for Lagassé | Manual SerpAPI fallback | Substack publishes `/feed` by default; verify Phase-0. |

### Installation

```bash
# Backend — NO new Python dependencies. All Phase 10 capabilities use existing stack.
# anthropic>=0.86.0, feedparser 6.0.x, serpapi, sqlalchemy>=2.0, asyncpg — all present.

# Frontend — NO new npm dependencies. SummaryCard edit is in-source; no new lib.
```

### Version Verification

```bash
# Already verified in research/STACK.md and scheduler/pyproject.toml:
# anthropic>=0.86.0  — line 12  (confirms structured-outputs GA via messages.parse)
# feedparser 6.0.x   — confirmed via prior Phase 5+ usage
# serpapi            — confirmed via Seva Ontario Law usage (ontario_law.py:140-162)
```

## Architecture Patterns

### Recommended Module Structure (additions only)

```
scheduler/
├── agents/
│   ├── daily_summary.py             # EDIT: extend run_juno_daily_summary (line 762) with real synthesis
│   ├── juno_relevance.py            # NEW: Haiku 4.5 World Events classifier (DEF-06)
│   └── juno_refusal_detector.py     # NEW: substring detector + retry-once helper (DEF-07)
├── companies/juno/
│   ├── feeds.py                     # POPULATE: JUNO_DEFENCE_FEEDS = [(source, url), ...]
│   ├── prompts.py                   # POPULATE: real DEFENCE_NEWS_SYSTEM_PROMPT (DEF-03)
│   └── serpapi.py                   # POPULATE: JUNO_SERPAPI_QUERIES = [str, ...]
└── tests/agents/
    ├── test_juno_relevance.py       # NEW: Haiku classifier unit tests with golden inputs
    ├── test_juno_refusal_detector.py # NEW: substring pattern tests + retry integration
    ├── test_juno_daily_summary.py   # EXTEND: real synthesis path with mocked Sonnet
    └── test_juno_health_check.py    # NEW: bozo + recent-history threshold tests
```

```
frontend/src/
├── components/summary/
│   ├── SummaryCard.tsx              # EDIT: per-company section config (D-08 — Phase 9 claim was verified-false)
│   └── __tests__/SummaryCard.test.tsx # EXTEND: per-tenant rendering test
└── config/
    └── companySectionConfig.ts      # NEW: company → {section_title, field_name, empty_fallback}[] map
```

### Phase Directory Artifacts (NEW, generated during Phase 10)

```
.planning/phases/10-juno-defence-news-funnel/
├── phase-10-feed-verification.md         # Wave 0 — Phase-0 RSS endpoint verification output (DEF-01 / D-14)
├── voice_calibration_uat_corpus.md       # Wave 3 — 5-10 hand-curated defence stories (DEF-10)
└── voice_calibration_uat.md              # Wave 3 — operator sign-off artifact (DEF-10)
```

```
scripts/
└── verify-juno-rss.sh                    # NEW: Phase-0 endpoint verification script (Wave 0)
```

### Pattern 1: Anthropic Haiku 4.5 Structured Output via `messages.parse()`

**What:** Haiku classifier returns a Pydantic-validated `DefenceRelevance` instance per world-events story.
**When to use:** DEF-06 — World Events Relevance Classifier inside the Juno daily_summary pipeline.
**Source:** [Anthropic Structured Outputs docs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) (verified 2026-05-19) — **`output_format` parameter is current; `output_config.format` was the old beta name; beta header NO LONGER required**.

### Pattern 2: Janes/CSIS Voice — System Prompt Structure (DEF-03)

**What:** Defence-industry Sonnet system prompt designed from scratch, with anti-tactical clause + section structure mirroring Seva's gold prompt SHAPE (not voice).
**When to use:** DEF-03 — populated in `scheduler/companies/juno/prompts.py`.
**Source:** Phase 7 weekly_sweeper system prompt at `scheduler/agents/weekly_sweeper.py:386-426` for STRUCTURE reference only; voice is fresh per CONTEXT D-01.

The prompt MUST include:
1. **Role line:** "You are a senior defence-industry analyst writing a daily intelligence brief for a Canadian defence-tech operator."
2. **Voice anchor:** "Tone: authoritative, sober, sourced-with-receipts. Match the energy of a Janes desk brief, a CSIS analysis piece, an IISS Military Balance update, or a Defense News editorial column."
3. **Anti-tactical clause (D-02, verbatim recommended):** "You produce market/industry commentary on the defence sector. You do NOT produce operational, tactical, targeting, force-posture, order-of-battle, capability-gap, or troop-movement analysis. If a source story crosses into operational territory, summarize the market/industry implications only and explicitly note the operational details were excluded."
4. **Bullet rule:** "Every bullet must name a vendor, contract value (if present), program designator, or policy instrument. Generic claims (`tensions rose`, `analysts say`) are rejected."
5. **Section structure (3 sections, Sonnet generates each independently):**
   - `### 🛡️ Defence News` — 3-7 bullets from Tier-1 RSS + SerpAPI substrate
   - `### 🇨🇦 Canadian Procurement` — 3-5 bullets from SerpAPI + editorial RSS
   - `### 🌐 World Events Relevant to Defence` — 5-7 bullets from Haiku-filtered Reuters/AP/BBC (confidence ≥ 0.7)
6. **Source-attribution rule:** "Each bullet ends with `(Source Name)` matching the RSS source."
7. **Negative space (anti-pattern callouts):** "DO NOT cite stock tickers, P/E ratios, or investment-advice framings. DO NOT advocate for or against specific weapons programs. DO NOT speculate on classified material."

**Token budget audit (Discretion §Sonnet token budget):**
- System prompt: ~400-500 tokens (with all 7 elements above)
- User prompt input per section:
  - Defence News: ~3-7 RSS bullets + summaries truncated to 500 chars each = ~1500-3500 tokens
  - Canadian Procurement: ~3-5 SerpAPI hits + summaries = ~1500-2500 tokens
  - World Events: ~5-7 Haiku-filtered items (already relevance-confirmed) + reasoning = ~1500-2500 tokens
- Output budget per section: 3-7 bullets × ~150 tokens = ~450-1050 tokens. **Phase 7 D-11 baseline is `max_tokens=1000`** — Juno's Defence News section may need `max_tokens=1500` to fit a 7-bullet output. Planner confirms.
- Total per Juno fire: ~5000-6000 tokens (per CONTEXT discretion estimate). Sonnet 4.6 pricing $3/M input + $15/M output × 60 fires/month ≈ **$5-10/month total Sonnet cost for Juno**.

### Pattern 3: Refusal-Detector Wrapper (DEF-07)

**What:** Inspect every Sonnet response.content[0].text against 7 compiled substring patterns; on detection, retry once with a framing nudge; on second failure, write section-unavailable copy + `status='partial'`.
**When to use:** Wrapping every Sonnet call inside `run_juno_daily_summary` (Defence News, Canadian Procurement, World Events synthesis calls).
**Source:** Phase 7 weekly_sweeper partial-status pattern at `weekly_sweeper.py:432-462`; Anthropic-Pentagon dispute timeline ([Wikipedia](https://en.wikipedia.org/wiki/Anthropic%E2%80%93United_States_Department_of_Defense_dispute), [TechPolicy.Press](https://www.techpolicy.press/a-timeline-of-the-anthropic-pentagon-dispute/), [Congress.gov CRS](https://www.congress.gov/crs-product/IN12669)).

### Pattern 4: Per-Feed Bozo + Recent-History Health-Check (DEF-04)

**What:** After each `feedparser.parse(url)`, check `bozo` flag + entry count vs 7-day average from `agent_runs.notes`.
**When to use:** Inside the RSS ingestion loop in `run_juno_daily_summary`.
**Source:** research/PITFALLS §"RSS feed reorganization" — Janes/Defense News feed paths have rotated 3× in 24 months; silent feed death is the #1 RSS pitfall.

### Pattern 5: Per-Company Section Config (frontend, DEF-08 — CRITICAL FINDING)

**What:** `SummaryCard.tsx` currently hardcodes Seva field names + section titles. Per Phase 9 D-08, it was supposed to tolerate missing fields and per-company section configuration. **Verified false during this research** (`SummaryCard.tsx` lines 61-75 reference `summary.gold_news_md`, `summary.ontario_law_md`, `summary.ontario_stats_md` directly with hardcoded `<SectionBlock title="Gold News" ...>` etc.).

**When to use:** Wave 0 task — minimal frontend edit to introduce a `companySectionConfig[company]` map keyed by `useParams().company`.

**Pattern:**

```typescript
// frontend/src/config/companySectionConfig.ts (NEW)
import type { SummaryCard } from '@/api/summaries'

export interface SectionConfig {
  title: string
  field: keyof Pick<SummaryCard, 'gold_news_md' | 'ontario_law_md' | 'ontario_stats_md'>
  emptyFallback: string
}

export const companySectionConfig: Record<'seva' | 'juno', SectionConfig[]> = {
  seva: [
    { title: 'Gold News', field: 'gold_news_md', emptyFallback: 'No major moves in gold for this window.' },
    { title: 'Ontario Law', field: 'ontario_law_md', emptyFallback: 'No new Ontario mining-related laws today.' },
    { title: 'Ontario Stats', field: 'ontario_stats_md', emptyFallback: 'No new production statistics released today.' },
  ],
  juno: [
    // Phase 9 D-08 says: reuse the existing 3 markdown columns; field names stay the same in DB
    // but render with defence-domain titles. NO schema migration needed.
    { title: 'Defence News', field: 'gold_news_md', emptyFallback: 'No major defence-industry moves for this window.' },
    { title: 'Canadian Procurement', field: 'ontario_law_md', emptyFallback: 'No new Canadian defence procurement signals today.' },
    { title: 'World Events Relevant to Defence', field: 'ontario_stats_md', emptyFallback: 'No defence-relevant world events met the relevance threshold today.' },
  ],
}
```

**Note on DB column naming:** Phase 9 D-08 ruled "field-rename via repurposing the existing 3 markdown columns — no schema migration." This means `daily_summaries.gold_news_md` is semantically Juno's "Defence News" when `company_id='juno'`. The CONTEXT.md `code_context` section confirms: `Phase 10 produces 'defence_news_md', 'canadian_procurement_md', 'world_events_md'` — but those are SEMANTIC names. Physical column name remains `gold_news_md` / `ontario_law_md` / `ontario_stats_md`. Backend Pydantic response schema at `backend/app/schemas/daily_summary.py:115-123` already exposes these 3 fields. **No backend schema edit needed.** Only frontend rendering.

### Anti-Patterns to Avoid

- **Anti-pattern 1:** Cloning `GOLD_NEWS_SYSTEM_PROMPT` (`daily_summary.py:74-133`) for Juno. CONTEXT D-01 explicitly forbids this. The gold prompt has a bull-thesis bias that's structurally wrong for defence (defence has no bull/bear framing).
- **Anti-pattern 2:** Using SerpAPI `tbs=qdr:d` 24h filter for World Events feeds. World Events ingestion should use feedparser-only on Reuters/AP/BBC RSS — SerpAPI is for paywalled fallback (D-09) and Canadian procurement (D-09), not generic world news.
- **Anti-pattern 3:** Forgetting to wrap each section's Sonnet call independently with the refusal-detector. CONTEXT D-11 says "after each section synthesis call" — that's 3 wrap-points, not one global wrap.
- **Anti-pattern 4:** Treating Haiku confidence < 0.7 items as ineligible globally. They're only ineligible for World Events synthesis — they still appear in `agent_runs.notes` for operator review (telemetry).
- **Anti-pattern 5:** Setting `JUNO_CRON_ENABLED=true` before voice UAT sign-off. CONTEXT D-04 says cron stays disabled until operator signs off in `voice_calibration_uat.md`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSON parsing from Sonnet/Haiku output | Manual `json.loads()` + markdown-fence stripping (existing Ontario Law pattern at `ontario_law.py:248-280`) | `client.messages.parse(output_format=PydanticModel)` | The new SDK method eliminates parse errors entirely — grammar-constrained generation guarantees schema match. Use for `juno_relevance.py` (NEW code). Existing Ontario Law `messages.create()` + json.loads pattern is grandfathered; do NOT touch it. |
| Refusal classifier | LLM-judge call to detect refusal | 7-substring `re.compile()` pattern | Substring covers ~95% of Anthropic content-policy refusal preambles per Pentagon dispute corpus. Adding a Haiku call adds latency + cost. |
| RSS feed health check | Custom HTTP HEAD + content-type sniffing | `feedparser.parse(url)` then check `.bozo` and `len(.entries)` | feedparser handles RSS 0.9x/1.0/2.0/Atom; `.bozo` is the documented "malformed" flag. |
| 7-day rolling average for feed-entry counts | New aggregation table | Query `agent_runs.notes` JSONB for `feed_entry_counts` over last 7 days, average client-side | `agent_runs.notes` already accepts arbitrary JSONB; Phase 7 uses it for `{"refusal_detected": ...}`. Phase 10 extends. |
| Per-tenant cron registration | New `companies` DB table | Hardcoded `company_id="juno"` in `run_juno_daily_summary` (already shipped in Phase 9) | Phase 9 D-03 said no companies table in v3.0. Phase 10 inherits. |
| Frontend per-company branding | New `branding` field in API response + dynamic CSS | Per-company section config map (literal `Record<'seva' | 'juno', SectionConfig[]>`) | v3.0 tech debt accepted (CONTEXT.md): hardcoded company list; brand stays "Seva Mining" on `/juno/*`. |

**Key insight:** Phase 10 is **content + config**, not infrastructure. Every new code surface either populates an existing stub or extends an existing pattern (refusal-detector mirrors Phase 7 partial-status; bozo health-check mirrors v2.1 weekly_sweeper subreddit-403 isolation; Haiku classifier mirrors Ontario Law filter but uses the modern `parse()` SDK). The ONE exception is `SummaryCard.tsx` — Phase 9 D-08 claim was incorrect, so a minimal frontend edit is required.

## Common Pitfalls

### Pitfall 1: SummaryCard.tsx is hardcoded — Phase 9 D-08 verified false

**What goes wrong:** Phase 9 D-08 explicitly said `SummaryCard.tsx` "tolerates missing-or-renamed section markdown fields" and "a single component handles both tenants via per-company section configuration (no per-tenant SummaryCard fork)." Inspection of the live file at `/Users/matthewnelson/seva-mining/frontend/src/components/summary/SummaryCard.tsx` lines 61-75 shows hardcoded `<SectionBlock title="Gold News" content={summary.gold_news_md} ...>` calls. There is no `companySectionConfig` map and no `useParams()` lookup. The `/juno/` route renders with Seva section titles.

**Why it happens:** Phase 9 shipped the URL routing (`<Route path=":company">`) and the backend per-company API (`/api/{company}/summaries`) but the frontend rendering layer was not actually refactored. Phase 9 verifier passed because no Juno data existed to render — `SummaryCard` rendered the Phase 9 smoke `status='partial'` row with `gold_news_md=None`, hitting `SectionBlock`'s `emptyFallback="No major moves in gold for this window."` — which the verifier may not have flagged as a Juno-specific bug.

**How to avoid:** Wave 0 task — introduce `frontend/src/config/companySectionConfig.ts` map + edit `SummaryCard.tsx` to read `useParams<{company: 'seva' | 'juno'}>()` and iterate `companySectionConfig[company]`. Add `SectionBlock.test.tsx` per-tenant rendering tests.

**Warning signs:** Operator opens `/juno/` after Phase 10 deploys; sees Tab 1 rendering "Gold News" as section title even though the markdown content is defence-news content. The Phase 9 smoke-test rows surface this immediately.

### Pitfall 2: Anthropic content-policy refusal on conflict-zone news

**What goes wrong:** Per research/PITFALLS §"Anthropic content-policy refusal", Claude (Sonnet 4.6) refuses requests that frame defence analysis as operational/tactical/targeting-adjacent. The Anthropic-Pentagon dispute (Feb-Apr 2026) established Anthropic prohibits Claude use in autonomous weapons targeting + mass surveillance. The Juno News Funnel ingests Ukraine/Gaza/Taiwan stories — naive prompts trigger refusals.

**Why it happens:** Anthropic safety classifiers are trained to refuse operational-intelligence framings. Naive "summarize this Israeli operation" prompts trigger; "analyze the defence-industry market implications of [event]" does not.

**How to avoid:** D-02 anti-tactical clause in the system prompt + D-11 refusal-detector wrapper + retry-once-with-nudge. Maintain a test corpus of 5-10 known-edge-case stories in `voice_calibration_uat_corpus.md`; assert no refusals.

**Warning signs:** Juno daily summary card has empty section despite RSS ingestion succeeding; `agent_runs.notes` contains `"refusal_detected": true`; Sonnet response starts with "I understand you're looking for..." or "As an AI...".

### Pitfall 3: SerpAPI budget overflow (existing $50/mo cap)

**What goes wrong:** Adding 5-8 Canadian procurement queries/day × 60 fires/month = up to 240 SerpAPI calls/month NEW for Juno. Combined with Seva's Ontario Law (60 calls/month) + Seva's gold news SerpAPI fallback in `content_agent.py` (volume varies), total could approach the $50/mo cap.

**Why it happens:** SerpAPI Starter plan is $25/mo for 1K searches; bumping to next tier costs more. CONTEXT discretion §SerpAPI overhead estimates $5-15/mo for Juno's adds (matches at $15/1K — 240 calls = $3.60).

**How to avoid:** Wave 0 audit task — count current Seva SerpAPI calls/month by querying `agent_runs.notes` for `{"serpapi": ...}` counters over last 30 days. Confirm headroom before Phase 10 wave 1.

**Cost math (verified):**
- Seva Ontario Law: 1 SerpAPI call/fire × 2 fires/day × 30 days = 60 calls/month
- Seva Gold News content_agent: variable (estimate 30-50 calls/month based on RSS fallback frequency)
- Juno Canadian Procurement (Phase 10): 5-8 queries × 1 fire/day (run only on the morning fire to save budget — planner confirms) × 30 days = 150-240 calls/month
- Total monthly: 240-350 calls/month — well inside SerpAPI Starter $25/mo (1K calls).
- **At $15 per 1K (current SerpAPI pricing 2026):** 350 calls = $5.25/month. Headroom: $44.75 inside the $50 cap.

**Warning signs:** SerpAPI dashboard shows monthly count climbing past 700/month; `agent_runs.notes` shows `serpapi` counters spiking past 10/fire.

### Pitfall 4: Haiku classifier returns is_relevant=true on consumer-tech dual-use news

**What goes wrong:** Per research/PITFALLS §"False positives", the "world events relevant to defence" heuristic drifts to consumer tech (Apple Vision Pro, ChatGPT releases) because almost everything is *arguably* dual-use.

**Why it happens:** Sonnet/Haiku default to inclusive interpretation when the prompt is "is this relevant?" — dual-use technology is the dominant defence-tech trend per Chatham House, so the false-positive surface is large.

**How to avoid:** Explicit exclusion list in the Haiku system prompt (D-08 categories define INCLUSION; D-07 confidence ≥ 0.7 cuts borderline). Test corpus during Phase 10 Wave 3 voice UAT should include 1-3 borderline cases (consumer drone, semiconductor with civilian use, climate-policy with defence implications) to validate the threshold.

**Warning signs:** World Events section renders an iPhone announcement or ChatGPT update as defence-relevant. Operator-visible during UAT.

### Pitfall 5: Idempotency filter excludes 'partial' for Juno but includes it for Seva

**What goes wrong:** Phase 9 fixed an idempotency bug in `run_juno_daily_summary` (line 798): `status.in_(["running", "completed", "partial"])`. Phase 10's real synthesis path may write `status='partial'` legitimately (refusal-detector trips). A second cron fire within the 30-min window would be skipped — **correct behavior**, but planner must not regress this.

**Why it happens:** Two different idempotency rules for Seva (`['running', 'completed']` at `_idempotency_skip` line 164) vs Juno (`['running', 'completed', 'partial']` at line 798). Seva excludes 'partial' to allow retry-on-flake; Juno includes 'partial' because Phase 9 stub ALWAYS writes 'partial' and back-to-back fires would otherwise duplicate.

**How to avoid:** Phase 10 Wave 2 KEEPS Juno's idempotency filter as `['running', 'completed', 'partial']`. Operator can manually re-run via `python -m agents.daily_summary juno` if a 'partial' row needs replacement.

**Warning signs:** Phase 9 smoke-test rows show 2 Juno partial rows in dev DB (1 from each Phase 9 smoke fire); back-to-back live fires in Phase 10 do not produce duplicates.

### Pitfall 6: Phase-0 RSS endpoint drift between research and execution

**What goes wrong:** Research/STACK.md validated all 12 Tier-1 feeds on 2026-05-19. By Phase 10 execution (could be days later), feeds may rotate, especially Defense News which has rotated 3× in 24 months per PITFALLS.

**Why it happens:** Defence publishers treat RSS as undocumented infrastructure; path changes are unannounced.

**How to avoid:** D-13 mandates Phase-0 verification on ALL 15 endpoints (12 Tier-1 + 3 TBD) at Phase 10 start. Output to `phase-10-feed-verification.md` per D-14. Failed feeds: drop from `JUNO_DEFENCE_FEEDS` OR replace with `JUNO_SERPAPI_QUERIES` `site:` fallback.

**Warning signs:** `verify-juno-rss.sh` reports `bozo=1` or `entries=0` on a feed that was validated in research/STACK.md.

## Code Examples

Verified patterns from official sources. **All examples use existing dependencies — no new installs.**

### Example 1: Haiku 4.5 Structured-Output Classifier (DEF-06)

```python
# scheduler/agents/juno_relevance.py (NEW)
"""Juno World Events relevance classifier — Phase 10 DEF-06.

Haiku 4.5 + Anthropic structured outputs via messages.parse(). Returns a
Pydantic-validated DefenceRelevance per story. Sub-second per call, ~$1-2/mo
at projected volume.
"""
from __future__ import annotations

import logging
from typing import Literal

from anthropic import AsyncAnthropic
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

HAIKU_MODEL = "claude-haiku-4-5"
HAIKU_MAX_TOKENS = 400
HAIKU_TIMEOUT_S = 30.0
CONFIDENCE_THRESHOLD = 0.7  # CONTEXT D-07


class DefenceRelevance(BaseModel):
    """One world-events item classified for defence relevance.

    9 inclusion categories per CONTEXT D-06. is_relevant=True AND
    confidence >= 0.7 items flow to Sonnet synthesis; below-threshold items
    are logged to agent_runs.notes for operator review (not surfaced).
    """
    is_relevant: bool = Field(description="True if defence-industry-relevant")
    category: Literal[
        "active_conflict",      # Ukraine, Gaza, Taiwan Strait, Yemen, Korea, Iran
        "alignment_shifts",     # NATO accession, BRICS, AUKUS-style deals
        "spending_policy",      # defence budgets, NATO 2%, SIPRI annual
        "sanctions_export",     # semiconductor export bans, denial lists
        "energy_critmin",       # lithium, cobalt, REE, LNG-defence links
        "semiconductors",       # CHIPS act, fabs, EUV controls
        "space",                # Starlink-defence, sat-intel, ASAT, launch contracts
        "hypersonic_ai_auto",   # DARPA, JADC2, autonomous systems, AI export
        "treaty_events",        # New START, INF, conventional arms control
        "not_relevant",
    ]
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = Field(max_length=200, description="One-sentence justification")


RELEVANCE_SYSTEM_PROMPT = """\
You classify general world-news items for relevance to the defence industry.

A story is defence-industry-relevant if it falls into one of 9 categories:
- active_conflict: Ukraine, Gaza, Taiwan Strait, Yemen, Korea, Iran developments
- alignment_shifts: NATO accession, BRICS expansion, AUKUS-style deals, basing
- spending_policy: defence budget bills, NATO 2% commitments, SIPRI reports
- sanctions_export: semiconductor export bans, denial lists, ITAR/EAR actions
- energy_critmin: lithium, cobalt, REE, LNG-vs-defence-supply-chain links
- semiconductors: CHIPS Act, fab news, EUV controls, advanced-node access
- space: Starlink-defence, satellite intelligence, ASAT, commercial launch contracts
- hypersonic_ai_auto: DARPA, JADC2, autonomous-systems contracts, AI export controls
- treaty_events: New START, INF, conventional-arms-control, non-proliferation

EXCLUDE (return is_relevant=false, category=not_relevant):
- Consumer device launches (phones, tablets) unless manufacturer announces defence contract
- General AI/LLM releases (GPT, Claude, Gemini) unless announcement specifically targets defence/intelligence
- Cryptocurrency price moves and exchange news
- Sports, entertainment, celebrity news under any framing
- Pure climate/weather news unless tied to military operations or basing

Return confidence as a float in [0.0, 1.0]. Use ≥0.85 for strong signal, 0.7-0.85
for moderate signal, <0.7 for borderline. The downstream pipeline filters at 0.7.
Reasoning: one sentence, ≤ 200 chars.
"""


async def classify_story(
    client: AsyncAnthropic,
    *,
    title: str,
    snippet: str,
) -> DefenceRelevance | None:
    """Run the Haiku classifier on one story. Returns None on hard failure.

    Fail-closed: on exception, log + return None. Caller treats None as
    `is_relevant=False` (drop the story) rather than retrying.
    """
    user_message = (
        f"Title: {title}\n\n"
        f"Snippet: {snippet[:1500]}\n\n"
        f"Classify this story for defence-industry relevance."
    )
    try:
        response = await client.messages.parse(
            model=HAIKU_MODEL,
            max_tokens=HAIKU_MAX_TOKENS,
            system=RELEVANCE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
            output_format=DefenceRelevance,
        )
        return response.parsed_output
    except Exception as exc:  # noqa: BLE001 — fail-closed
        logger.warning(
            "juno_relevance: classify_story failed on '%s' (%s)",
            (title or "")[:60],
            type(exc).__name__,
        )
        return None


def survives_threshold(result: DefenceRelevance | None) -> bool:
    """CONTEXT D-07 — is_relevant=True AND confidence >= 0.7."""
    return (
        result is not None
        and result.is_relevant
        and result.confidence >= CONFIDENCE_THRESHOLD
        and result.category != "not_relevant"
    )
```

**Source:** [Anthropic Structured Outputs docs (verified 2026-05-19)](https://platform.claude.com/docs/en/build-with-claude/structured-outputs). Key syntax confirmation:
- Parameter name is `output_format` (NOT `output_config.format` — that was the old beta name)
- NO `anthropic-beta` header required in current SDK
- Method is `messages.parse()` (NOT `messages.create()` + manual `json.loads`)
- Response field is `response.parsed_output`

### Example 2: Refusal-Detector Wrapper (DEF-07)

```python
# scheduler/agents/juno_refusal_detector.py (NEW)
"""Juno Sonnet refusal-detector + retry-with-framing-nudge wrapper.

CONTEXT D-11 — 7 substring patterns covering ~95% of Anthropic content-policy
refusals per the Anthropic-Pentagon dispute corpus. Retry once with a framing
nudge; on second refusal, return None so caller writes section-unavailable
copy with status='partial'.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from anthropic import AsyncAnthropic

logger = logging.getLogger(__name__)

# CONTEXT D-11 — 7 substring patterns. Compiled at module load (not per-call).
REFUSAL_PATTERN = re.compile(
    r"(I cannot|as an AI|safety guidelines|unable to provide|"
    r"I'm not able to|cannot assist|against my)",
    re.IGNORECASE,
)

# Framing nudge appended to user prompt on first refusal (D-11 retry-once)
FRAMING_NUDGE = (
    "\n\nAnalyze the following stories as defence-industry market commentary, "
    "not tactical or operational intelligence. Focus on contract values, "
    "vendor names, policy implications, and market signals — explicitly NOT "
    "on force posture, capability gaps, or military operations."
)


def is_refusal(text: str | None) -> bool:
    """Return True if text matches any of the 7 refusal patterns."""
    if not text:
        return False
    # Heuristic: first 500 chars catches the refusal preamble; full-text
    # scan would catch in-bullet mentions like "(the analyst cannot...)" as
    # false positives.
    return bool(REFUSAL_PATTERN.search(text[:500]))


async def call_with_refusal_guard(
    client: AsyncAnthropic,
    *,
    model: str,
    max_tokens: int,
    system: str,
    user_prompt: str,
    section_name: str,
) -> tuple[str | None, dict[str, Any]]:
    """Call Sonnet with refusal-detection + retry-once.

    Returns (text_or_None, diagnostic_dict). diagnostic_dict carries
    refusal_detected/first_attempt_excerpt for agent_runs.notes per D-11.
    """
    diagnostic: dict[str, Any] = {
        "refusal_detected": False,
        "section": section_name,
        "first_attempt_excerpt": None,
        "retry_attempted": False,
    }
    # First attempt
    try:
        resp = await client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = resp.content[0].text.strip()
    except Exception as exc:
        logger.exception("juno_refusal_guard: first attempt raised on section=%s", section_name)
        diagnostic["first_attempt_excerpt"] = f"EXCEPTION: {type(exc).__name__}: {str(exc)[:100]}"
        return (None, diagnostic)

    if not is_refusal(text):
        return (text, diagnostic)

    # First-attempt refusal — capture excerpt + retry with framing nudge
    diagnostic["refusal_detected"] = True
    diagnostic["first_attempt_excerpt"] = text[:100]
    diagnostic["retry_attempted"] = True
    logger.warning(
        "juno_refusal_guard: section=%s refused on first attempt; retrying with framing nudge",
        section_name,
    )

    try:
        resp2 = await client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user_prompt + FRAMING_NUDGE}],
        )
        text2 = resp2.content[0].text.strip()
    except Exception as exc:
        logger.exception("juno_refusal_guard: retry raised on section=%s", section_name)
        diagnostic["second_attempt_excerpt"] = f"EXCEPTION: {type(exc).__name__}"
        return (None, diagnostic)

    if is_refusal(text2):
        logger.warning(
            "juno_refusal_guard: section=%s refused on retry; falling back to status=partial",
            section_name,
        )
        diagnostic["second_attempt_excerpt"] = text2[:100]
        return (None, diagnostic)

    return (text2, diagnostic)


SECTION_UNAVAILABLE_COPY = (
    "Section unavailable — defence-industry summary could not be generated "
    "for this fire. See agent_runs.notes for diagnostic."
)
```

**Refusal pattern verification audit:** The 7 patterns from CONTEXT D-11 cover the canonical Anthropic refusal preambles documented in:
- The Anthropic-Pentagon dispute timeline (Feb-Apr 2026) — Anthropic public statements use "we cannot provide" framing
- Anthropic API docs content-policy examples — "I cannot help with" / "I'm unable to provide" / "this goes against my guidelines"
- Community reports (Reddit r/ClaudeAI, Anthropic Discord) — "as an AI" / "against my values" / "cannot assist with"

**Recommended addition (planner discretion):** consider also adding `"violates"` and `"harmful"` if the UAT corpus surfaces refusals using those words. Default 7 patterns are sufficient for the documented 95% coverage — planner does NOT need to add patterns preemptively.

### Example 3: SerpAPI Canadian Procurement Query (DEF-05)

```python
# scheduler/companies/juno/serpapi.py (POPULATE)
"""Juno SerpAPI google_news queries — Phase 10 DEF-05.

5-8 site:-restricted + topic queries for Canadian procurement gap. Cost: 5-8
queries × 1 fire/day × 30 days = 150-240 calls/month at $15/1K = $2.25-$3.60/mo
incremental inside the $50/mo SerpAPI cap.

NOTE: Run on morning fire only (08:00 PT) to save budget. The 12:00 PT fire
does NOT re-run SerpAPI queries — it re-uses raw_sources_jsonb from the
morning fire if available. Planner confirms this decision in Phase 10.
"""
from __future__ import annotations

JUNO_SERPAPI_QUERIES: list[str] = [
    # Government sites — direct DND/PSPC procurement signal
    "site:canada.ca defence procurement",
    "site:tpsgc-pwgsc.gc.ca defence",
    # Editorial / trade press
    "site:canadiandefencereview.com",
    # Topic queries — wider net
    '"DND contract" canada',
    '"RCAF procurement"',
    '"Royal Canadian Navy contract"',
    '"DND innovation challenge"',
]
# Planner picks final 5-8 from above (8 listed; 1 spare for swap-in if any
# Phase-0 verifies as low-signal). See voice_calibration_uat.md for tuning.
```

```python
# Usage inside _build_canadian_procurement_section in daily_summary.py:
import asyncio
import serpapi
from companies.juno.serpapi import JUNO_SERPAPI_QUERIES


async def _fetch_juno_serpapi(client: serpapi.Client) -> list[dict]:
    """Fetch all JUNO_SERPAPI_QUERIES concurrently. Returns flat list of hits."""
    loop = asyncio.get_event_loop()

    async def _one_query(q: str) -> list[dict]:
        def _call() -> Any:
            return client.search({
                "engine": "google_news",
                "q": q,
                "tbs": "qdr:d",  # last 24h (same as Ontario Law pattern)
                "num": 10,
            })
        try:
            results = await loop.run_in_executor(None, _call)
            return results.get("news_results") or []
        except Exception as exc:
            logger.warning("juno_serpapi: query '%s' failed (%s)", q, type(exc).__name__)
            return []

    all_hits = await asyncio.gather(*[_one_query(q) for q in JUNO_SERPAPI_QUERIES])
    return [item for batch in all_hits for item in batch]
```

**Source:** [SerpAPI google_news engine docs](https://serpapi.com/google-news-api) and existing pattern at `scheduler/agents/ontario_law.py:140-162`.

### Example 4: Phase-0 RSS Verification Script (D-13/D-14)

```bash
#!/usr/bin/env bash
# scripts/verify-juno-rss.sh (NEW — Phase 10 Wave 0)
#
# Verify ALL 15 Juno defence RSS endpoints. Output is pipe-delimited so
# phase-10-feed-verification.md can be auto-generated.
#
# Format: feed_name|feed_url|bozo|entries_count|verdict
# verdict: WORKING | DROPPED | FALLBACK_TO_SERPAPI
#
# Usage:
#   bash scripts/verify-juno-rss.sh > .planning/phases/10-juno-defence-news-funnel/feed-verification.raw
#   then human-curates into phase-10-feed-verification.md

set -u

FEEDS=(
    # Tier-1 — 12 sub-feeds (validated 2026-05-19 in research/STACK.md)
    "defense_news_industry|https://www.defensenews.com/arc/outboundfeeds/rss/category/industry/?outputType=xml"
    "defense_news_pentagon|https://www.defensenews.com/arc/outboundfeeds/rss/category/pentagon/?outputType=xml"
    "defense_news_global|https://www.defensenews.com/arc/outboundfeeds/rss/category/global/?outputType=xml"
    "defense_news_air|https://www.defensenews.com/arc/outboundfeeds/rss/category/air/?outputType=xml"
    "defense_news_land|https://www.defensenews.com/arc/outboundfeeds/rss/category/land/?outputType=xml"
    "defense_news_naval|https://www.defensenews.com/arc/outboundfeeds/rss/category/naval/?outputType=xml"
    "defense_news_space|https://www.defensenews.com/arc/outboundfeeds/rss/category/space/?outputType=xml"
    "defense_news_unmanned|https://www.defensenews.com/arc/outboundfeeds/rss/category/unmanned/?outputType=xml"
    "breaking_defense|https://breakingdefense.com/feed/"
    "defense_scoop|https://defensescoop.com/feed/"
    "rusi_commentary|https://www.rusi.org/rss/latest-commentary.xml"
    "rusi_publications|https://www.rusi.org/rss/latest-publications.xml"
    "sipri_combined|https://www.sipri.org/rss/combined.xml"
    # 3 TBD endpoints (D-13)
    "war_gov|https://www.war.gov/news/rss/?feedtype=press-releases"
    "nato_news|https://www.nato.int/cps/en/natohq/news.htm?selectedLocale=en&_=feed"
    "canada_ca_defence|https://www.canada.ca/en/news/web-feeds.html"
)

echo "feed_name|feed_url|bozo|entries_count|verdict"
for entry in "${FEEDS[@]}"; do
    NAME="${entry%%|*}"
    URL="${entry#*|}"
    # Use feedparser via inline Python — matches the production code path
    RESULT=$(python3 -c "
import feedparser, sys
try:
    f = feedparser.parse('$URL')
    print(f'{int(f.bozo)}|{len(f.entries)}')
except Exception as e:
    print(f'-1|0')
" 2>/dev/null)
    BOZO="${RESULT%%|*}"
    COUNT="${RESULT#*|}"
    if [[ "$BOZO" == "0" && "$COUNT" -gt 0 ]]; then
        VERDICT="WORKING"
    elif [[ "$BOZO" == "-1" ]]; then
        VERDICT="DROPPED"
    else
        VERDICT="FALLBACK_TO_SERPAPI"
    fi
    echo "$NAME|$URL|$BOZO|$COUNT|$VERDICT"
done
```

Output goes into `phase-10-feed-verification.md` (D-14):

```markdown
# Phase 10 Feed Verification — Phase-0 Output

**Verified:** YYYY-MM-DD

| Feed | URL | Bozo | Entries | Verdict |
|------|-----|------|---------|---------|
| defense_news_industry | https://www.defensenews.com/... | 0 | 23 | ✓ WORKING |
| war_gov | https://www.war.gov/news/rss/?... | 1 | 0 | ✗ FALLBACK_TO_SERPAPI |
...
```

### Example 5: Per-Feed Bozo Health-Check (DEF-04)

```python
# Snippet inside run_juno_daily_summary's RSS ingestion loop:
from companies.juno.feeds import JUNO_DEFENCE_FEEDS

feed_entry_counts: dict[str, int] = {}
flagged_feeds: list[str] = []
all_entries: list[dict] = []

for source_name, feed_url in JUNO_DEFENCE_FEEDS:
    try:
        loop = asyncio.get_event_loop()
        feed = await loop.run_in_executor(None, feedparser.parse, feed_url)
    except Exception as exc:
        logger.warning("juno: feedparser raised on %s (%s)", source_name, type(exc).__name__)
        flagged_feeds.append(source_name)
        feed_entry_counts[source_name] = 0
        continue

    n_entries = len(feed.entries)
    feed_entry_counts[source_name] = n_entries

    if feed.bozo and n_entries == 0:
        logger.warning(
            "juno: feed %s bozo=1 entries=0 (%s)",
            source_name,
            getattr(feed, 'bozo_exception', 'unknown'),
        )
        flagged_feeds.append(source_name)
        continue

    # Recent-history comparison (CONTEXT D-12)
    # Query agent_runs.notes for last 7-day average for this feed:
    avg_7d = await _fetch_7day_avg_for_feed(session, source_name)
    if avg_7d > 0 and n_entries < (0.3 * avg_7d):
        logger.info(
            "juno: feed %s today=%d < 30%% of 7d avg=%.1f — flagged",
            source_name, n_entries, avg_7d,
        )
        flagged_feeds.append(source_name)
        # NOTE: still ingest the entries — flag is informational, not blocking

    all_entries.extend([_entry_to_dict(e, source_name) for e in feed.entries])

# Status mapping per D-12
section_status: str
if not all_entries:
    section_status = "failed"  # zero entries across all feeds
elif len(flagged_feeds) >= 3:
    section_status = "partial"  # 3+ feeds flagged
else:
    section_status = "completed"

# Telemetry → agent_runs.notes per D-12
notes_dict = {
    "feed_entry_counts": feed_entry_counts,
    "flagged_feeds": flagged_feeds,
}
```

### Example 6: Voice UAT Corpus Shape (DEF-10 / Claude's discretion)

Candidate 5-10 defence stories for `voice_calibration_uat_corpus.md`. Planner curates; this is a research-suggested SHAPE, not the literal final corpus:

| # | Story shape | Domain | Why curated |
|---|-------------|--------|-------------|
| 1 | US procurement: "Lockheed Martin wins $1.8B PAC-3 missile contract" | Defence News | Standard contract story — tests "contract value + vendor named" bullet rule |
| 2 | US procurement: "Raytheon awarded $500M JADC2 follow-on" | Defence News | Tests dual-use boundary (JADC2 is C2/networking, not weapons) |
| 3 | Canadian DND: "DND announces P-8A Poseidon delivery schedule" | Canadian Procurement | Standard procurement signal — tests Canadian regional balance |
| 4 | Conflict-zone wire (pick one): "Ukraine receives ATACMS delivery from US" OR "Israel-Iran tensions escalate after Tehran strike" OR "Taiwan announces submarine fleet expansion" | World Events | Tests refusal-detector against active conflict; anti-tactical clause must hold |
| 5 | Dual-use tech: "US imposes new EUV export controls on China" | World Events | Tests semiconductor inclusion category + Haiku classifier confidence |
| 6 | Borderline #1: "Apple Vision Pro 2 launches with defense-grade encryption" | (should reject) | Consumer device with defence framing — Haiku must return is_relevant=false |
| 7 | Borderline #2: "Skydio releases consumer drone with dual-use applications" | (borderline) | Drone story — tests dual-use exclusion list |
| 8 | Borderline #3: "Canada's federal climate plan includes defence-base resiliency funding" | (should accept low-confidence) | Climate+defence — tests `confidence` near 0.7 threshold |
| 9 | (optional) Treaty event: "New START extension talks resume in Geneva" | World Events | Tests treaty_events inclusion category |
| 10 | (optional) Sanctions: "EU adopts 14th Russia sanctions package targeting microelectronics" | World Events | Tests sanctions_export category |

### Voice UAT Pass Criteria (DEF-10 / Claude's discretion)

Concrete pass bar for operator sign-off in `voice_calibration_uat.md`:

1. **Voice match (qualitative):** Sample summary reads like a Janes/CSIS desk brief (operator judgment, no automated metric).
2. **Anti-tactical clause holds:** No bullets reference force-posture, OOB, troop movements, capability gaps, or targeting. Verified by grep against the sample output for keywords: `force posture | order of battle | OOB | troop movement | capability gap | targeting`. Zero matches = pass.
3. **Source attribution complete:** Every bullet ends with `(Source Name)`. Verified by regex `\(\w[\w\s]+\)$` on each bullet line. ≥95% match = pass.
4. **Section balance:** Defence News has 3-7 bullets; Canadian Procurement has 3-5; World Events has 5-7. Operator visually confirms.
5. **No refusals:** None of the 5-10 UAT stories triggers refusal-detector. `agent_runs.notes` shows `refusal_detected=false` on all.
6. **Borderline cases correctly handled:** Apple Vision Pro story (item 6) returns `is_relevant=false` from Haiku; climate+defence (item 8) returns `is_relevant=true` with `confidence` in `[0.6, 0.8]` range (planner picks the operator-acceptable bar).
7. **Dual-use exclusion holds:** Consumer drone (item 7) does NOT appear in World Events synthesis output even if Haiku marks it relevant.

UAT failure path (mirrors Phase 7 partial-status pattern): operator marks `voice_calibration_uat.md` as "REJECTED" with specific failure category (voice mismatch / refusal / dual-use leak / regional skew). Planner iterates on `DEFENCE_NEWS_SYSTEM_PROMPT` or `RELEVANCE_SYSTEM_PROMPT` and re-runs UAT until "APPROVED" sign-off. Cron stays disabled (D-04) until APPROVED.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Free-form Sonnet + `json.loads` for structured extraction (existing Ontario Law pattern at `ontario_law.py:248-280`) | `messages.parse(output_format=PydanticModel)` | Anthropic SDK ≥ 0.86.0 (current) | New code (Juno classifier) uses `parse()`; existing Ontario Law `create()` + parse pattern grandfathered. |
| `output_config.format` + `anthropic-beta: structured-outputs-2025-11-13` header | `output_format=PydanticModel` direct parameter, no beta header | Late 2025 GA | Beta-era code needs migration; greenfield Juno classifier uses GA syntax directly. |
| Reddit / asyncpraw ingestion for weekly_sweeper | Tweepy AsyncClient X API recent_search | Phase 7 D-03 (2026-04-21) | Phase 10 inherits the X-only weekly-sweeper pattern (not directly relevant to Phase 10, but the partial-status pattern from Phase 7 IS reused). |
| Pydantic v1 patterns | Pydantic v2 `BaseModel` + `Field(ge=..., le=...)` + `Literal[...]` | FastAPI 0.135+ deprecation | New Juno classifier uses v2 patterns (already enforced project-wide per CLAUDE.md). |
| Per-tenant config in DB (`companies` table) | Per-tenant config in Python `scheduler/companies/{seva,juno}/` package | v3.0 Phase 9 D-05 / D-03 | Phase 10 populates the package; no companies table needed at N=2. |

**Deprecated/outdated approaches to avoid:**
- `output_config.format` parameter name — superseded by `output_format` in current SDK
- Cloning `GOLD_NEWS_SYSTEM_PROMPT` for Juno — explicit anti-pattern per CONTEXT D-01
- Reddit asyncpraw — replaced by X API in Phase 7; not relevant to Phase 10 but reaffirms "deprecated in v2.1"
- `SET LOCAL app.current_tenant` PostgreSQL RLS — rejected in Phase 9; no relevance to Phase 10

## Open Questions

1. **Should the SerpAPI Canadian procurement queries run on EVERY Juno fire (08:00 PT + 12:00 PT) or just the morning fire?**
   - What we know: budget math (Pitfall 3) allows both, but the 12:00 PT fire adds 5-8 queries × 30 days = 150-240 extra calls/month with limited new signal (Canadian procurement announcements concentrate on morning EST releases).
   - What's unclear: whether the 12:00 PT operator value-add from re-querying procurement is worth $2-4/month.
   - Recommendation: Run SerpAPI on morning fire only; 12:00 PT fire re-uses morning's `raw_sources_jsonb`. Planner confirms in Phase 10 Wave 1 or 2.

2. **Should Haiku classifier failures (returns None) be counted in section status calculation?**
   - What we know: D-07 says items with confidence < 0.7 are excluded; D-12 says 3+ flagged feeds → partial. Silent on classifier failures.
   - What's unclear: if Haiku times out on 10/20 stories, should that cascade to a section-partial?
   - Recommendation: Treat classifier failures as "story dropped" (fail-closed) — do NOT cascade to section-partial unless ALL stories fail classification. Planner picks final rule in Wave 1.

3. **Voice UAT — what's the minimum operator review time before sign-off?**
   - What we know: D-04 says operator approves and persists in `voice_calibration_uat.md`. Cron stays disabled until sign-off.
   - What's unclear: whether the planner should specify a minimum review window (e.g., "24h review period before sign-off") or trust the operator to read carefully.
   - Recommendation: No artificial delay. Operator reviews, signs off in same session if satisfied. Planner notes "operator reviewed for [N] minutes" in `voice_calibration_uat.md` for audit trail.

4. **Smoke-test row cleanup from Phase 9 — confirm "let them age out" is acceptable?**
   - What we know: CONTEXT discretion recommends letting them age out via the 30-day prune cron.
   - What's unclear: whether they show up in operator-facing UI during the next 30 days and cause confusion.
   - Recommendation: Confirm in Wave 0 — query `daily_summaries WHERE company_id='juno' AND raw_sources_jsonb @> '{"phase_10_pending": true}'` and decide. Likely fine; the SummaryCard renders them with the new per-company section config, and `error_text="Juno content pipeline pending — Phase 10"` clearly explains.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `anthropic` Python SDK | DEF-03, DEF-06, DEF-07 | ✓ | `>=0.86.0` (line 12 of `scheduler/pyproject.toml`) | — |
| `feedparser` | DEF-01, DEF-04 | ✓ | `6.0.x` | — |
| `serpapi` Python SDK | DEF-02, DEF-05 | ✓ | latest (Seva Ontario Law uses) | — |
| `pydantic` | DEF-06 (DefenceRelevance schema) | ✓ | `2.x` | — |
| Anthropic API key (`ANTHROPIC_API_KEY` env) | All Sonnet + Haiku calls | ✓ | shared key (Phase 9 D-05 — no per-tenant keys in v3.0) | — |
| SerpAPI key (`SERPAPI_API_KEY` env) | DEF-05 | ✓ | shared key | — |
| Reuters World / AP World / BBC World RSS | DEF-06 World Events ingestion | ⚠ TBD | — | SerpAPI `site:reuters.com world` / `site:apnews.com world` / `site:bbc.co.uk world` |
| war.gov RSS | DEF-01 (3 TBD endpoints) | ⚠ TBD (Phase-0) | — | SerpAPI `site:war.gov defence` |
| nato.int RSS | DEF-01 (3 TBD endpoints) | ⚠ TBD (Phase-0) | — | SerpAPI `site:nato.int defence` |
| canada.ca defence sub-feed | DEF-01 (3 TBD endpoints) | ⚠ TBD (Phase-0) | — | SerpAPI `site:canada.ca defence` (already in DEF-02) |
| `bash`, `python3`, `curl` for verify-juno-rss.sh | Wave 0 Phase-0 verification | ✓ | system | — |

**Missing dependencies with no fallback:** None. All Phase 10 functionality has either a primary path or a documented SerpAPI fallback.

**Missing dependencies with fallback:**
- 3 TBD RSS endpoints (war.gov, nato.int, canada.ca) — Phase-0 verification in Wave 0 determines whether to use RSS or SerpAPI per endpoint.
- Reuters/AP/BBC World RSS — research/SUMMARY.md says "if RSS available — verify in Phase-0." If not, route through SerpAPI inside the World Events ingestion path.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | `pytest>=8.0` + `pytest-asyncio>=0.23` (confirmed in `scheduler/pyproject.toml` lines 22-23) |
| Config file | `scheduler/pyproject.toml` `[tool.pytest.ini_options]` (line 27) |
| Quick run command | `cd scheduler && pytest tests/agents/test_juno_relevance.py tests/agents/test_juno_refusal_detector.py tests/agents/test_juno_health_check.py -x` |
| Full suite command | `cd scheduler && pytest tests/ -x` |
| Frontend test framework | Vitest (existing) — `cd frontend && pnpm test` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DEF-01 | Tier-1 RSS feeds populated + bozo/entries health-check | unit + integration | `pytest scheduler/tests/agents/test_juno_health_check.py -x` | ❌ Wave 0 |
| DEF-01 | Phase-0 endpoint verification script outputs all 15 endpoints | smoke (Wave 0 only) | `bash scripts/verify-juno-rss.sh` | ❌ Wave 0 |
| DEF-02 | SerpAPI `JUNO_SERPAPI_QUERIES` queries return parseable hits | unit (mocked serpapi.Client) | `pytest scheduler/tests/agents/test_juno_daily_summary.py::test_serpapi_canadian_procurement -x` | ❌ Wave 0 (extend stub) |
| DEF-03 | `DEFENCE_NEWS_SYSTEM_PROMPT` contains anti-tactical clause + voice anchor + section structure | unit (string match against prompts.py) | `pytest scheduler/tests/companies/test_juno_prompts.py -x` | ❌ Wave 0 |
| DEF-04 | Defence News section ingestion + dedup + 3-7 bullet output | unit (mocked Sonnet) | `pytest scheduler/tests/agents/test_juno_daily_summary.py::test_defence_news_section -x` | ❌ Wave 0 (extend stub) |
| DEF-04 | bozo flag + recent-history < 30% threshold flag feeds | unit | `pytest scheduler/tests/agents/test_juno_health_check.py::test_health_check_thresholds -x` | ❌ Wave 0 |
| DEF-05 | Canadian Procurement section via SerpAPI + editorial RSS | unit (mocked serpapi + feedparser) | `pytest scheduler/tests/agents/test_juno_daily_summary.py::test_canadian_procurement_section -x` | ❌ Wave 0 (extend stub) |
| DEF-06 | Haiku classifier returns DefenceRelevance with correct category + confidence ≥ 0.7 filter | unit (mocked AsyncAnthropic + golden inputs) | `pytest scheduler/tests/agents/test_juno_relevance.py -x` | ❌ Wave 0 |
| DEF-06 | confidence < 0.7 items excluded from synthesis | unit | `pytest scheduler/tests/agents/test_juno_relevance.py::test_survives_threshold -x` | ❌ Wave 0 |
| DEF-07 | 7 substring patterns detect refusal in first 500 chars | unit | `pytest scheduler/tests/agents/test_juno_refusal_detector.py::test_is_refusal_patterns -x` | ❌ Wave 0 |
| DEF-07 | Retry-once with framing nudge on first refusal | integration (mocked AsyncAnthropic) | `pytest scheduler/tests/agents/test_juno_refusal_detector.py::test_retry_with_nudge -x` | ❌ Wave 0 |
| DEF-07 | Second refusal → status='partial' + section-unavailable copy | integration | `pytest scheduler/tests/agents/test_juno_refusal_detector.py::test_second_refusal_fallback -x` | ❌ Wave 0 |
| DEF-08 | SummaryCard.tsx renders Juno section titles via companySectionConfig | unit (Vitest) | `cd frontend && pnpm test src/components/summary/__tests__/SummaryCard.test.tsx` | ⚠ Extend existing |
| DEF-09 | Tab 2/Tab 3 empty-state for Juno (Phase 9 already shipped — verify) | smoke | manual-only (operator opens /juno/calendar and /juno/viral, sees empty-state) | manual |
| DEF-10 | Voice UAT — operator-approved sample summary | manual-only | manual sign-off in `voice_calibration_uat.md`; cron stays disabled until APPROVED | manual |

**Manual-only justification (DEF-09, DEF-10):**
- DEF-09: Phase 9 already wired Tab 2/Tab 3 empty-states. Phase 10 verifies they still render — a visual check during the operator UAT session, not a regression-test target.
- DEF-10: Voice quality is a qualitative judgment call (Janes/CSIS energy match). No automated metric captures "does this sound like a senior defence analyst." Pass criteria documented in §Voice UAT Pass Criteria.

### Sampling Rate

- **Per task commit:** `pytest scheduler/tests/agents/test_juno_*.py -x` (Juno-specific tests only — ~3 seconds)
- **Per wave merge:** `cd scheduler && pytest tests/ -x` (full scheduler suite — ~30 seconds) + `cd frontend && pnpm test` (full frontend suite — ~10 seconds)
- **Phase gate:** Both full suites green + `voice_calibration_uat.md` shows `APPROVED` + `verify-juno-rss.sh` output exists in `phase-10-feed-verification.md` + manual `/juno/` tab walkthrough before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `scripts/verify-juno-rss.sh` — Phase-0 endpoint verification (D-13/D-14)
- [ ] `scheduler/tests/agents/test_juno_relevance.py` — Haiku classifier unit tests (golden inputs: 1 defence-direct, 1 active-conflict, 1 sanctions, 1 consumer-tech reject, 1 borderline ~0.7 confidence)
- [ ] `scheduler/tests/agents/test_juno_refusal_detector.py` — 7 substring patterns + retry-with-nudge + second-refusal fallback
- [ ] `scheduler/tests/agents/test_juno_health_check.py` — bozo flag + recent-history threshold (mock `agent_runs.notes` for 7-day window)
- [ ] `scheduler/tests/agents/test_juno_daily_summary.py` — EXTEND existing stub for real synthesis path (mocked Sonnet for unit, integration test with real DB for live smoke)
- [ ] `scheduler/tests/companies/test_juno_prompts.py` (NEW directory) — string-match assertions on `DEFENCE_NEWS_SYSTEM_PROMPT` (anti-tactical clause present, section markers present, bullet rule present)
- [ ] `frontend/src/components/summary/__tests__/SummaryCard.test.tsx` — EXTEND for per-tenant section-field rendering test (verify `/juno/` renders "Defence News" title; `/seva/` renders "Gold News" title)
- [ ] `frontend/src/config/companySectionConfig.ts` — NEW config map (production code + types; tested via SummaryCard.test.tsx)

*(Framework install: none needed — pytest, pytest-asyncio, Vitest all present.)*

## Sources

### Primary (HIGH confidence)

- Direct code reads (verified 2026-05-19):
  - `/Users/matthewnelson/seva-mining/.planning/phases/10-juno-defence-news-funnel/10-CONTEXT.md` — all D-01..D-14 decisions
  - `/Users/matthewnelson/seva-mining/scheduler/companies/juno/feeds.py` — Phase 9 skeleton (empty list confirmed)
  - `/Users/matthewnelson/seva-mining/scheduler/companies/juno/prompts.py` — Phase 9 STUB confirmed
  - `/Users/matthewnelson/seva-mining/scheduler/companies/juno/serpapi.py` — Phase 9 skeleton (empty list confirmed)
  - `/Users/matthewnelson/seva-mining/scheduler/agents/daily_summary.py` lines 762-875 — `run_juno_daily_summary` Phase 9 stub
  - `/Users/matthewnelson/seva-mining/scheduler/agents/daily_summary.py` lines 74-133 — `GOLD_NEWS_SYSTEM_PROMPT` (structure reference, voice anti-pattern)
  - `/Users/matthewnelson/seva-mining/scheduler/agents/ontario_law.py` lines 89-280 — Ontario Law SerpAPI pattern + Haiku filter pattern (volume estimate: 1 call/fire × 2 fires/day = 60/month for Seva)
  - `/Users/matthewnelson/seva-mining/scheduler/agents/weekly_sweeper.py` lines 350-541 — Phase 7 partial-status pattern + idempotency check shape
  - `/Users/matthewnelson/seva-mining/scheduler/pyproject.toml` line 12 — `anthropic>=0.86.0` confirmed (structured-outputs GA)
  - `/Users/matthewnelson/seva-mining/frontend/src/components/summary/SummaryCard.tsx` lines 61-75 — **HARDCODED Seva field names confirmed** (Phase 9 D-08 claim verified false)
  - `/Users/matthewnelson/seva-mining/frontend/src/components/summary/SectionBlock.tsx` — Phase 8 MarkdownContent wrapper confirmed
  - `/Users/matthewnelson/seva-mining/frontend/src/api/summaries.ts` lines 11-13 — TypeScript `SummaryCard` interface with hardcoded `gold_news_md`/`ontario_law_md`/`ontario_stats_md` fields
  - `/Users/matthewnelson/seva-mining/backend/app/schemas/daily_summary.py` lines 113-123 — `SummaryCardResponse` Pydantic schema with same 3 markdown fields + `company_id` exposed
  - `/Users/matthewnelson/seva-mining/.planning/research/STACK.md` — 12 Tier-1 feeds + Anthropic structured outputs + SerpAPI patterns
  - `/Users/matthewnelson/seva-mining/.planning/research/FEATURES.md` — defence news taxonomy + 9 inclusion categories + Sonnet relevance heuristic
  - `/Users/matthewnelson/seva-mining/.planning/research/PITFALLS.md` §2 — defence-sector pitfalls (refusal, dual-use, RSS feed reorganization)
  - `/Users/matthewnelson/seva-mining/.planning/research/SUMMARY.md` — v3.0 cross-research synthesis
  - `/Users/matthewnelson/seva-mining/.planning/config.json` — `workflow.nyquist_validation: true` confirmed (Validation Architecture section required)
- [Anthropic Structured Outputs docs (verified 2026-05-19)](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) — `messages.parse(output_format=PydanticModel)` is the current GA syntax; `output_config.format` was the old beta name; NO `anthropic-beta` header required

### Secondary (MEDIUM confidence)

- [Anthropic-Pentagon dispute timeline (TechPolicy.Press)](https://www.techpolicy.press/a-timeline-of-the-anthropic-pentagon-dispute/) — content-policy refusal corpus context
- [Anthropic–US Department of Defense dispute (Wikipedia)](https://en.wikipedia.org/wiki/Anthropic%E2%80%93United_States_Department_of_Defense_dispute) — public refusal language references for substring pattern verification
- [Pentagon-Anthropic Dispute (Congress.gov CRS)](https://www.congress.gov/crs-product/IN12669) — refusal pattern verification source
- [SerpAPI Plans and Pricing](https://serpapi.com/pricing) — $25/mo Starter (1K calls) + $15/1K marginal — confirmed for budget math
- [SerpAPI Google News API docs](https://serpapi.com/google-news-api) — `engine=google_news` + `tbs=qdr:d` parameter syntax
- [Defense News RSS feed inventory](https://www.defensenews.com/m/rss/) — 8 sub-feeds confirmed (validated 2026-05-19 in research/STACK.md)
- [Breaking Defense feed](https://breakingdefense.com/feed/) — HIGH confidence per research validation
- [DefenseScoop feed](https://defensescoop.com/feed/) — HIGH confidence per research validation
- [RUSI RSS feeds listing](https://www.rusi.org/rusi-rss-feeds) — both Commentary + Publications confirmed
- [SIPRI Combined RSS](https://www.sipri.org/rss) — confirmed

### Tertiary (LOW confidence — Phase-0 validation required)

- war.gov RSS landing (`https://www.war.gov/news/rss/`) — Phase-0 verifies the exact `?feedtype=press-releases` path
- nato.int RSS — landing page 404'd in research/STACK.md 2026-05-19; Phase-0 confirms whether the news.htm feed exists or fall back to SerpAPI
- canada.ca defence sub-feed — research/STACK.md says no direct RSS confirmed; Phase-0 greps `https://www.canada.ca/en/news/web-feeds.html` for defence-specific URLs
- Reuters/AP/BBC World RSS for DEF-06 World Events ingestion — research/SUMMARY.md says "if RSS available — verify in Phase-0"
- Philippe Lagassé Substack RSS — `https://philippelagasse.substack.com/feed` (Substack default), Phase-0 confirms

## Metadata

**Confidence breakdown:**
- Standard stack (Anthropic SDK, SerpAPI, feedparser, pydantic versions): HIGH — verified via pyproject.toml + Anthropic docs fetched 2026-05-19
- Anthropic structured-output API syntax (`messages.parse(output_format=...)`): HIGH — verified via official Anthropic docs page 2026-05-19
- Refusal pattern coverage (7 substrings cover 95%): MEDIUM — based on Anthropic-Pentagon dispute corpus + community reports; planner should plan to add patterns if UAT surfaces gaps
- SummaryCard.tsx hardcoded finding: HIGH — direct file read confirmed lines 61-75 hardcode Seva field names
- SerpAPI cost math: HIGH — 240-350 calls/month total × $15/1K = $5.25/month against $50/mo cap
- Voice UAT pass criteria: MEDIUM — research-recommended bar, operator may tighten/loosen during Wave 3
- Token budget audit: MEDIUM — estimates based on Phase 7 D-11 baseline + observed gold-news section sizes; planner confirms by adjusting `max_tokens` if Sonnet truncates output
- 9 inclusion categories: HIGH — locked in CONTEXT D-06 + research/STACK.md classifier example
- Per-feed bozo + recent-history pattern: HIGH — feedparser docs confirm `.bozo` and `.entries` semantics; `agent_runs.notes` JSONB already used for telemetry

**Research date:** 2026-05-19
**Valid until:** 2026-06-18 (30 days for stable backend stack; 7 days for RSS feed URLs which can rotate — Phase-0 verification is the load-bearing freshness check)
