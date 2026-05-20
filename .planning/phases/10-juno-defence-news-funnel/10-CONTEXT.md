# Phase 10: Juno Defence News Funnel - Context

**Gathered:** 2026-05-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Config-only build on top of Phase 9's multi-tenant foundation. Phase 10 populates the three Juno skeletons (`scheduler/companies/juno/{feeds.py, prompts.py, serpapi.py}`) with real defence-sector content, adds a `juno_relevance.py` Sonnet/Haiku classifier for the World Events section, wires a refusal-detector wrapper around Sonnet calls, adds per-feed health-check, and runs a voice-calibration UAT against 5-10 hand-curated stories BEFORE the production Juno cron is enabled. By phase close, Tab 1 of `/juno/` renders a live 3-section daily summary (Defence News + Canadian Procurement + World Events Relevant to Defence) with operator-approved voice.

Phase 10 covers all of DEF-01 through DEF-10. No infrastructure changes — Phase 9 already shipped `company_id` columns, `/api/{company}/...` routers, `juno_daily_summary=1020` registered cron, `scheduler/queries/scoped.py` mirror, and the `<Route path=":company">` frontend wrapper.

**Carrying forward from earlier phases:**

- **Phase 9 D-01a:** Juno `daily_summary` fires at `CronTrigger(hour="8,12", minute=5, timezone="America/Los_Angeles")` (5-min stagger from Seva). Phase 10 does NOT change this; it just populates what the cron synthesizes.
- **Phase 9 (idempotency bug fix):** `run_juno_daily_summary` idempotency filter is `status.in_(['running','completed','partial'])` — Phase 10 must continue to use `'partial'` as the fallback status when refusal-detector trips or insufficient signal surfaces (matches existing pattern + keeps idempotency working).
- **Phase 9 (skeletons in place):**
  - `scheduler/companies/juno/feeds.py` — `JUNO_DEFENCE_FEEDS: list[tuple[str, str]] = []` (Phase 10 fills with (source_name, feed_url) tuples)
  - `scheduler/companies/juno/prompts.py` — `DEFENCE_NEWS_SYSTEM_PROMPT: str = "STUB ..."` (Phase 10 replaces with real prompt)
  - `scheduler/companies/juno/serpapi.py` — `JUNO_SERPAPI_QUERIES: list[str] = []` (Phase 10 fills with query strings)
- **v3.0 research SUMMARY.md (2026-05-19):** 12 Tier-1 RSS feeds HTTP-validated, 9 World Events inclusion categories, Anthropic-Pentagon dispute precedent → refusal-detector required, $5-15/mo SerpAPI overhead for Canadian procurement gap (DND/PSPC have NO RSS).
- **Phase 9 v3.0 tech debt (accepted, still applies):** Brand mark stays "Seva Mining" on `/juno/*` (v3.1+ TENANT-BRAND-v31); hardcoded CHECK `('seva','juno')` (v3.2+ TENANT-N-v32). Phase 10 does NOT change these.

</domain>

<decisions>
## Implementation Decisions

### Sonnet System Prompt Design (DEF-03)
- **D-01:** **Voice baseline = Janes / CSIS desk energy.** Authoritative, sober, sourced-with-receipts senior-defence-analyst-at-a-think-tank tone. Bullet-driven; contract-value-and-vendor-named where present; neutral-on-conflict. Examples to anchor: IISS Military Balance briefings, CSIS analysis pieces, RAND research summaries, Defense News editorial board commentary. NEVER cloned from Seva's gold-bull-bias prompt — defence sector requires a wholly different intelligence brief shape (no bull/bear framing; no analyst rating language).
- **D-02:** **Explicit anti-tactical framing clause + refusal triggers list in the system prompt.** A dedicated paragraph in `DEFENCE_NEWS_SYSTEM_PROMPT` (per DEF-03): "You produce market/industry commentary on the defence sector. You do NOT produce operational, tactical, targeting, force-posture, order-of-battle, capability-gap, or troop-movement analysis. If a source story crosses into operational territory, summarize the market/industry implications only and explicitly note the operational details were excluded." This is the strongest defence against Anthropic content-policy refusal (per Anthropic-Pentagon dispute precedent in PITFALLS). Adds ~50 tokens to the system prompt — acceptable.
- **D-03:** **Source-driven regional balance (no in-prompt quota).** System prompt does NOT request explicit US + Canada + Europe + Indo-Pacific quotas. Sonnet picks the strongest 3-7 stories from whatever the RSS + SerpAPI substrate surfaced that fire. Tier-1 feeds skew US-defence by source (Defense News, Breaking Defense, DefenseScoop are US-centric) so v3.0 output will skew US-defence by default. Operator-level fix is at the substrate layer (add Canadian + European + Indo-Pacific feeds in `JUNO_DEFENCE_FEEDS` and `JUNO_SERPAPI_QUERIES`), not the prompt layer. Cleaner prompt; data drives editorial balance.
- **D-04:** **Voice UAT mechanics (DEF-10):** 5-10 hand-curated defence stories assembled by the planner (mix: US procurement contract, Canadian DND announcement, conflict-zone wire story, dual-use tech announcement, semiconductor export-control update). Sonnet 4.6 produces a sample daily summary against the curated input. Operator reads + approves. Approval persisted in `voice_calibration_uat.md`. **Cron stays DISABLED until operator signs off.** Cron enable is a single env var or config flip; planner specifies the exact mechanism.

### World Events Relevance Classifier (DEF-06)
- **D-05:** **Haiku 4.5 + Anthropic structured outputs (`output_config.format` with Pydantic schema).** Classifier returns `{is_relevant: bool, category: Literal[...], confidence: float, reasoning: str}` per call. Cheap (~$1-2/mo at projected volume of ~50-100 world-news items/fire), fast (sub-second), sufficient for binary-with-category classification. Sonnet 4.6 retained for the actual synthesis step (after classifier filters).
- **D-06:** **All 9 inclusion categories** from research SUMMARY.md:
  1. Active conflict (Ukraine, Gaza, Taiwan Strait, Yemen, Korea, Iran)
  2. Alignment shifts (NATO accession, BRICS expansion, AUKUS-style deals)
  3. Spending policy (defence budget bills, NATO 2% commitments, SIPRI annual)
  4. Sanctions / export controls (semiconductor export bans, critical-tech denial lists)
  5. Energy / critical-minerals (lithium, cobalt, REE supply-chain stories; LNG-vs-defence-supply-chain links)
  6. Semiconductors (chip act, fabs, EUV controls, advanced-node access)
  7. Space (Starlink-defence, satellite intelligence, anti-satellite weapons, commercial launch contracts)
  8. Hypersonic / AI / autonomy (DARPA, JADC2, autonomous-systems contracts, AI-export controls)
  9. Treaty events (New START, INF, conventional-arms-control, nuclear non-proliferation)
- **D-07:** **Confidence threshold `confidence >= 0.7`** — only items at 0.7+ flow to Sonnet synthesis. Filters borderline cases; trusts Sonnet for the final editorial cut. Default is tunable post-UAT (research-recommended starting point).
- **D-08:** **World Events source feeds:** Reuters World, AP World, BBC World (if RSS available — verify in Phase-0), plus any large-source feeds the operator surfaces during Phase 10 voice UAT. Distinct from the Defence News feeds (DEF-01) — World Events ingestion is "what's happening in the world" not "what defence press is covering."

### Canadian Procurement Strategy (DEF-05)
- **D-09:** **SerpAPI-heavy + editorial layer (DND/PSPC RSS gap accepted).** Canadian Procurement section ingests via:
  - **SerpAPI `google_news` `site:` queries (5-8 queries):** `site:canada.ca defence`, `site:canadiandefencereview.com`, `site:pspc-spac.gc.ca`, `site:tpsgc-pwgsc.gc.ca`, plus topic queries (`"DND contract"`, `"RCAF procurement"`, `"Royal Canadian Navy contract"`, `"DND innovation"`). 1 query/day per source.
  - **Editorial layer (RSS where available):** Lagassé Substack (RSS confirmed), Atlantic Council Canadian-defence reports (RSS confirmed), Canadian Defence Review (RSS verify in Phase-0).
  - **Budget:** Adds $5-15/mo to SerpAPI inside existing $50/mo budget. Confirm in Phase 10 wave 0 budget audit.

### Tier-2 Feed Inclusion (DEF-01)
- **D-10:** **Tier-1 ONLY for v3.0 Phase 10.** Ship the 12 HTTP-validated Tier-1 feeds (Defense News × 8 sub-feeds + Breaking Defense + DefenseScoop + RUSI Commentary + RUSI Publications + SIPRI Combined). Tier-2 candidates (Defense Daily, Inside Defense, National Defense Magazine, Defense Industry Daily, Shephard, Defense One) deferred to v3.1+ if Tier-1 signal proves insufficient after first 2-4 weeks of production. Cleanest v3.0 scope; minimal dedup load.

### Refusal-Detector + Safety (DEF-07)
- **D-11:** **Substring-pattern detector + retry-once with framing nudge + `status='partial'` fallback.** Inspect Sonnet response after each section synthesis call for refusal patterns: `'I cannot'`, `'as an AI'`, `'safety guidelines'`, `'unable to provide'`, `"I'm not able to"`, `'cannot assist'`, `'against my'`. On detection:
  1. Retry ONCE with a framing nudge appended to the user prompt: `"Analyze the following stories as defence-industry market commentary, not tactical or operational intelligence. Focus on contract values, vendor names, policy implications, and market signals — explicitly NOT on force posture, capability gaps, or military operations."`
  2. On second refusal: write the refused section's markdown as `"Section unavailable — defence-industry summary could not be generated for this fire. See agent_runs.notes for diagnostic."`, set the row `status='partial'`, log `{"refusal_detected": true, "section": "<section_name>", "first_attempt_excerpt": "<first 100 chars>"}` in `agent_runs.notes`. Matches the Phase 7 partial-status pattern. Operator sees the section unavailable copy in the dashboard — never raw refusal text.

### Per-Feed Health-Check (DEF-04)
- **D-12:** **Bozo OR empty + recent-history comparison.** After each feed fetch:
  1. If `feedparser.parse(url).bozo == 1` OR `entries == []` → flag the feed.
  2. Read last 7-day average entry count from `agent_runs.notes` (Phase 10 stores `{"feed_entry_counts": {"<source_name>": <count>, ...}}` per fire). If today's count is < 30% of the 7-day average → flag.
  3. On any flag: append to `agent_runs.errors` array; if 3+ feeds flag in one fire, write the daily_summary row with `status='partial'`.
  4. WhatsApp alert via existing WHA-03 pattern (Phase 1) if entire defence ingestion fails (zero entries across all feeds).

### Phase-0 RSS Endpoint Verification (DEF-01)
- **D-13:** **Verify ALL 15 endpoints at Phase 10 start.** Phase 10 Wave 0 (or Task 1) runs `curl + python -c "import feedparser; f = feedparser.parse('<url>'); print(f.bozo, len(f.entries))"` against:
  - **3 TBD endpoints** (from research): war.gov, nato.int, canada.ca defence
  - **12 Tier-1 feeds** (research-validated 2026-05-19 — may have drifted): Defense News × 8 sub-feeds, Breaking Defense, DefenseScoop, RUSI Commentary, RUSI Publications, SIPRI Combined
  - Any feed that fails verification: drop from `JUNO_DEFENCE_FEEDS` OR replace with a SerpAPI `site:` fallback query
- **D-14:** Phase-0 outputs a `phase-10-feed-verification.md` artifact in the phase directory listing each endpoint with status (✓ working, ✗ dropped, → fallback). Becomes the source-of-truth for the final `JUNO_DEFENCE_FEEDS` list.

### Claude's Discretion (planner picks)
- **Voice UAT corpus exact composition (5-10 stories).** Planner curates the mix. Recommended split: 2 US procurement (Lockheed/Raytheon contract wins), 1 Canadian DND announcement, 1 conflict-zone wire (Ukraine OR Gaza OR Taiwan), 1 dual-use tech (semiconductor or AI export control), 1-3 borderline cases (where classifier confidence would be near 0.7 threshold). Persist in `voice_calibration_uat_corpus.md`.
- **Cron-enable mechanism.** Planner picks: env var `JUNO_CRON_ENABLED=false` default + flip after UAT, OR a `companies` config flag (but D-03 from Phase 9 said no companies DB table — so env var preferred), OR comment-out the `add_job(...)` call in `worker.py` until UAT (cleanest — no live cron until commit-and-deploy). Recommended: env var so production toggle doesn't require a deploy.
- **Smoke-test row cleanup from Phase 9.** Phase 9 left 2 `daily_summaries` rows (1 seva partial + 1 juno partial) in the dev DB. Phase 10 first fire will write fresh rows; the Phase 9 smoke rows are clutter, not regression. Planner picks whether to DELETE them in Phase 10 Wave 0 or let them age out via the 30-day prune cron. Recommended: let them age out.
- **Sonnet token budget per fire.** Defence News section: ~3-7 bullets × ~150 tokens each + system prompt = ~1500-2000 tokens. Canadian Procurement section: ~3-5 bullets × ~150 = ~1000-1500. World Events: ~5-7 bullets × ~150 = ~1500-2000 (after classifier filter). Total per Juno fire: ~5000-6000 tokens at $5-10/mo for 60 fires/month. Planner confirms budget in Phase 10 final summary.
- **Inclusion-category badges in UI rendering.** Research suggested World Events bullets carry inclusion-category badges (e.g. "Sanctions/Export Controls"). Planner decides whether to render these as visual badges in `SummaryCard` (yes — adds visual signal; uses semantic CSS tokens) or omit (no — keeps markdown clean). Defer to Phase 10 UI plan.

### Folded Todos
None — no pending todos matched Phase 10 scope.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Domain & Research
- `.planning/research/SUMMARY.md` — v3.0 research synthesis with 4 cross-research agreements + 5 operator decision points (3 resolved in Phase 9, 2 still apply to Phase 10: per-tenant Anthropic API key + default `/` redirect target are still v3.1+/deferred)
- `.planning/research/STACK.md` §"Defence RSS feeds" — 12 Tier-1 feeds + paywalled fallback strategy + Anthropic structured outputs
- `.planning/research/FEATURES.md` §"Juno News Funnel structural divergence" — World Events Relevant to Defence replaces Seva's Ontario Stats slot
- `.planning/research/PITFALLS.md` §2 "Defence-sector domain pitfalls" — Anthropic-Pentagon precedent, RSS feed instability, regional bias, dual-use boundary, newsletter-vs-hard-news classification, conflict-zone timezone considerations
- `.planning/research/ARCHITECTURE.md` §"Phase 2 — Juno News Funnel" — config-only after Phase 9; references the 3 skeleton files

### Requirements
- `.planning/REQUIREMENTS.md` §"Juno Defence News Funnel (DEF)" — DEF-01..10 full text; all 10 map to Phase 10

### v3.0 Prior Phase
- `.planning/phases/09-multi-tenant-foundation/09-CONTEXT.md` — D-01a confirms `CronTrigger(hour="8,12", minute=5)` for Juno
- `.planning/phases/09-multi-tenant-foundation/09-SUMMARY.md` — Decisions section documents Phase 9 D-02 freeze-lift + multi-tenant strategy
- `.planning/phases/09-multi-tenant-foundation/09-VERIFICATION.md` — Phase 9 verifier 10/10 PASS

### Backend / Scheduler Edit Targets
- `scheduler/companies/juno/feeds.py` — populate `JUNO_DEFENCE_FEEDS` list[tuple[str,str]] with 12 Tier-1 feeds (after Phase-0 verification)
- `scheduler/companies/juno/serpapi.py` — populate `JUNO_SERPAPI_QUERIES` list[str] with paywalled-fallback + Canadian-procurement queries
- `scheduler/companies/juno/prompts.py` — replace STUB `DEFENCE_NEWS_SYSTEM_PROMPT` with real Janes/CSIS-voice prompt + anti-tactical clause
- `scheduler/agents/daily_summary.py::run_juno_daily_summary` — extend the stub to actually ingest feeds + classify world events + call Sonnet (currently writes empty status='partial' row)
- `scheduler/agents/juno_relevance.py` (NEW) — Haiku 4.5 structured-output classifier for World Events
- `scheduler/agents/juno_refusal_detector.py` (NEW) OR inline helper in `daily_summary.py` — substring detector + retry wrapper
- `backend/app/schemas/daily_summary.py` (verify) — confirm response schema can carry Juno's section markdown fields (Phase 9 D-08 said `SummaryCard` tolerates missing fields; Phase 10 produces `defence_news_md`, `canadian_procurement_md`, `world_events_md` — verify these aren't required-fields in the Pydantic v2 model)

### Frontend Edit Targets
- `frontend/src/components/summary/SummaryCard.tsx` — verify tolerates Juno's section markdown field names (`defence_news_md` etc. instead of `gold_news_md`); may need a per-company section-config object passed via props or context
- `frontend/src/components/summary/SectionBlock.tsx` — verify already wired (Phase 8 MarkdownContent wrapper); should render Juno markdown identically to Seva
- (No new frontend files expected — Phase 10 is config + scheduler primarily)

### Testing
- Voice UAT corpus → `voice_calibration_uat_corpus.md` (NEW artifact in phase dir)
- Voice UAT results → `voice_calibration_uat.md` (NEW artifact, persisted at operator sign-off)
- Phase-0 feed verification → `phase-10-feed-verification.md` (NEW artifact, source-of-truth for final `JUNO_DEFENCE_FEEDS`)
- `scheduler/tests/agents/test_juno_daily_summary.py` (extend Phase 9 stub tests) — exercise real ingestion + classifier + Sonnet path (with mocked Sonnet for unit tests, integration test for live-DB smoke)
- `scheduler/tests/agents/test_juno_relevance.py` (NEW) — unit-test the Haiku classifier with golden inputs/outputs

### Historical / CLAUDE.md Context
- `CLAUDE.md` — async-only Python, SQLAlchemy 2.0 + asyncpg, Pydantic v2, single-user desktop, no autoposting, GSD workflow enforcement
- Phase 7 (v2.1) Sonnet system prompt at `scheduler/agents/weekly_sweeper.py` — pattern reference for system prompt structure (but voice + framing diverge per D-01)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`scheduler/agents/daily_summary.py::run_juno_daily_summary`** (Phase 9 stub) — already wired to the cron, writes a `status='partial'` row, has idempotency guard (60-min window, includes `'partial'` in the filter post-Phase-9-fix). Phase 10 extends this function with real synthesis logic.
- **`scheduler/queries/scoped.py`** (Phase 9) — `scoped_summaries('juno')` is the canonical query path. Phase 10 uses this for the 7-day-virality-window lookback (if Juno virality compute is needed — DEF doesn't explicitly require it, but the World Events relevance classifier might benefit from cross-fire deduplication).
- **`scheduler/companies/juno/*.py`** (Phase 9 skeletons) — three files with the correct symbol names + empty/STUB contents. Phase 10 only needs to populate, NOT restructure.
- **`AsyncAnthropic` client + `output_config.format` structured outputs** — already available via `anthropic>=0.86.0` (already in dependencies). Phase 10 uses this for the Haiku classifier.
- **`feedparser` 6.0.x** — already in scheduler deps. Phase 10 uses for RSS ingestion + `bozo`/`entries=[]` health check.
- **SerpAPI `google_news` engine** — already in use by Seva (v2.0 Ontario Law). Phase 10 reuses with `site:` queries.
- **`SummaryCard.tsx` + `SectionBlock.tsx`** — Phase 8 + Phase 9 wired to tolerate per-company section field names. Phase 10 should NOT require frontend edits (verify in Wave 0).
- **Phase 7 weekly_sweeper system prompt at `scheduler/agents/weekly_sweeper.py:386-426`** — pattern reference for system-prompt structure, NOT voice content.

### Established Patterns
- **`status='partial'` fallback** — used by Phase 7 weekly_sweeper (insufficient signal) and Phase 9 Juno stub (placeholder). Phase 10's refusal-detector reuses this status.
- **Idempotency window 60 min** (Phase 7 D-15) — applies to Juno cron too; Phase 9 fix already includes `'partial'` in the filter.
- **`agent_runs.notes` JSONB** — Phase 7 uses this for `{"refusal_detected": ..., "feed_entry_counts": ...}` diagnostic markers; Phase 10 extends with classifier-related markers.
- **Sonnet 4.6 + AsyncAnthropic + 60s timeout + 1000 max_tokens** — established by Phase 7 D-11. Phase 10 inherits.

### Integration Points
- New Haiku 4.5 classifier endpoint: same `AsyncAnthropic` client, different model + smaller token budget per call
- World Events feeds (Reuters World / AP World / BBC World) — new RSS sources, NOT defence-press, ingested by the classifier path (NOT by the Defence News path)
- SerpAPI overhead — Canadian Procurement queries add ~5-8 calls/day at ~$0.005/call = ~$0.75-$1.50/day = ~$22-45/month. Inside existing $50/mo budget but reduces headroom. Phase 10 must audit existing Seva SerpAPI usage to confirm.
- WhatsApp alert (WHA-03) — already wired for Seva failures; Phase 10 extends to fire for Juno ingestion-zero events too. Confirm the alert template can disambiguate by company.

</code_context>

<specifics>
## Specific Ideas

- **Janes/CSIS desk energy** — operator wants the dashboard to read like an IISS Military Balance brief or a Defense News editorial column, not like a wire-service summary. Sober + sourced + neutral-on-conflict.
- **5-min stagger** between Seva (`hour="8,12"`) and Juno (`hour="8,12", minute=5`) — established Phase 9 D-01a; Phase 10 honors but doesn't change.
- **Source-driven editorial balance** — operator accepts that v3.0 Juno output will skew US-defence by source (Tier-1 feeds are US-centric). Fix is at the substrate layer (add more Canadian + European + Indo-Pacific feeds in DEF-01/DEF-02), not the prompt.
- **Anti-tactical framing is the strongest defence against Anthropic refusals** — explicit paragraph + refusal-detector retry-with-nudge fallback covers ~95% of edge cases per Anthropic-Pentagon dispute analysis in research.

</specifics>

<deferred>
## Deferred Ideas

- **Tier-2 feed inclusion** (Defense Daily, Inside Defense, National Defense Magazine, Defense Industry Daily, Shephard, Defense One) — defer to v3.1+ if Tier-1 signal proves insufficient after first 2-4 weeks
- **Inclusion-category badges in SummaryCard UI** — Claude's discretion in Phase 10 UI plan; may defer to v3.1+ if Phase 10 scope grows
- **Equity / financial signals on defence primes (LMT, RTX, GD)** — explicit anti-feature per REQUIREMENTS v3.0 Out of Scope
- **Operational / tactical / OOB intelligence** — explicit anti-feature; hard prohibition per system prompt
- **Live conflict map / OSINT geospatial** — out of scope per REQUIREMENTS
- **Per-tenant Anthropic API key** — PITFALLS §5 recommendation; defer to v3.1+ unless content-policy review surfaces a real need during Phase 10 voice UAT
- **Bloomberg defence-beat voice variant** — rejected in D-01 in favor of Janes/CSIS; revisit only if Janes/CSIS voice doesn't land for the operator
- **Regional balance quota in prompt** — rejected in D-03 in favor of source-driven; revisit if Phase 10 UAT shows strong regional skew the operator wants to fix at the prompt layer

### Reviewed Todos (not folded)
None — no pending todos matched Phase 10 scope.

</deferred>

---

*Phase: 10-juno-defence-news-funnel*
*Context gathered: 2026-05-19*
