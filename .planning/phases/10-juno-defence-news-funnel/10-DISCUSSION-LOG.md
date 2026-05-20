# Phase 10: Juno Defence News Funnel - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-19
**Phase:** 10-juno-defence-news-funnel
**Areas discussed:** Sonnet system prompt voice + framing; World Events relevance classifier; Canadian procurement + Tier-2 feed inclusion; Refusal-detector + per-feed health-check + Phase-0 RSS verification

---

## Gray Area Selection

User selected all 4 candidate gray areas.

| Gray Area | Description | Selected |
|-----------|-------------|----------|
| Sonnet system prompt voice + framing | DEF-03 — voice baseline, anti-tactical framing strength, regional balance, voice UAT mechanics | ✓ |
| World Events relevance classifier | DEF-06 — model choice (Haiku vs Sonnet), inclusion categories, confidence threshold | ✓ |
| Canadian procurement + Tier-2 feed inclusion | DEF-05 + DEF-01 — DND/PSPC RSS gap strategy + Tier-2 scope | ✓ |
| Refusal-detector + per-feed health-check + Phase-0 RSS verification | DEF-07 + safety mechanics + endpoint validation | ✓ |

---

## Area 1: Sonnet System Prompt Voice + Framing

### Q1 — Voice baseline?

| Option | Description | Selected |
|--------|-------------|----------|
| Janes/CSIS desk energy | Authoritative, sober, sourced; bullet-driven; contract-value-and-vendor-named; neutral-on-conflict | ✓ |
| Breaking Defense / Defense News magazine energy | More journalistic, faster cadence, light prose | |
| Bloomberg defence-beat reporter energy | Markets-first lens; equity/supply-chain framing | |

**User's choice:** Janes/CSIS desk energy
**Notes:** Operator wants IISS Military Balance / CSIS analysis / Defense News editorial board tone. Most professional, least viral.

### Q2 — Anti-tactical framing strength?

| Option | Description | Selected |
|--------|-------------|----------|
| Explicit "market/industry commentary only" clause + refusal triggers list | Strongest defence against Anthropic refusal; ~50 tokens added | ✓ |
| Soft anti-tactical framing (no explicit list) | Cleaner prompt; more refusal risk on conflict-zone stories | |
| No framing — trust Sonnet's defaults | Highest refusal risk; NOT recommended | |

**User's choice:** Explicit clause + refusal triggers list
**Notes:** Anthropic-Pentagon dispute precedent makes explicit framing essential. Forbids operational/tactical/OOB/force-posture/capability-gap/troop-movement analysis. System prompt summarizes market/industry implications only.

### Q3 — Regional balance heuristic?

| Option | Description | Selected |
|--------|-------------|----------|
| Explicit regional quota (US + Canada + Europe + Indo-Pacific) | Forces geographic diversity; may strain on quiet weeks | |
| Source-driven balance (no in-prompt quota) | Cleaner prompt; data drives editorial balance | ✓ |
| Light regional preference (no quota) | Middle ground — nudge without forcing | |

**User's choice:** Source-driven balance
**Notes:** Tier-1 feeds skew US-defence by source. v3.0 output will skew US-defence by default. Fix at substrate layer (add more Canadian/European/Indo-Pacific feeds in DEF-01/02), not prompt layer.

### Q4 — Voice UAT mechanics (DEF-10)?

| Option | Description | Selected |
|--------|-------------|----------|
| 5-10 hand-curated stories → produce summary → operator approves | ~30 min operator time; cron stays DISABLED until sign-off | ✓ |
| Iterative prompt refinement loop | 3-5 iterations; higher overfitting risk | |
| Ship with v0 prompt, iterate post-cron-enable | Faster ship; risk of bad first-week output | |

**User's choice:** 5-10 hand-curated stories with operator approval gate
**Notes:** Approval persisted in `voice_calibration_uat.md`. Cron enable mechanism (env var preferred) TBD by planner.

---

## Area 2: World Events Relevance Classifier

### Q1 — Classifier model?

| Option | Description | Selected |
|--------|-------------|----------|
| Haiku 4.5 + structured outputs | Cheap (~$1-2/mo), fast, sufficient for binary-with-category | ✓ |
| Sonnet 4.6 + structured outputs | Better nuance on borderline; ~$5-8/mo additional | |
| No classifier — ship World Events feeds directly to Sonnet | Simpler pipeline; mixes concerns; higher refusal risk | |

**User's choice:** Haiku 4.5 + structured outputs
**Notes:** Returns `{is_relevant, category, confidence, reasoning}`. Sonnet 4.6 reserved for synthesis step.

### Q2 — Inclusion categories?

| Option | Description | Selected |
|--------|-------------|----------|
| All 9 categories from research | Comprehensive; grounded in CSIS/RAND/SIPRI taxonomy | ✓ |
| Trim to 6 | Drop space, hypersonic/AI/autonomy, treaty events | |
| Trim to 4 | Narrowest; highest signal-to-noise but misses dual-use tech | |

**User's choice:** All 9 categories
**Notes:** Active conflict, alignment shifts, spending policy, sanctions/export controls, energy/critical-minerals, semiconductors, space, hypersonic/AI/autonomy, treaty events. Categories are tags, not exclusive.

### Q3 — Confidence threshold?

| Option | Description | Selected |
|--------|-------------|----------|
| confidence >= 0.7 | Research-recommended default | ✓ |
| confidence >= 0.5 | More permissive; more noise + cost | |
| confidence >= 0.8 | Stricter; cleaner editorial input | |

**User's choice:** confidence >= 0.7
**Notes:** Tunable post-UAT if Phase 10 finds too noisy/too strict.

---

## Area 3: Canadian Procurement + Tier-2 Feed Inclusion

### Q1 — Canadian Procurement ingestion strategy?

| Option | Description | Selected |
|--------|-------------|----------|
| SerpAPI + editorial layer | 5-8 SerpAPI queries + Lagassé Substack + Atlantic Council + Canadian Defence Review. ~$5-15/mo overhead. Best signal-to-noise. | ✓ |
| Editorial-only (no SerpAPI queries) | Free but lacks raw procurement announcements | |
| SerpAPI-only (no editorial) | Raw signal without context layer | |

**User's choice:** SerpAPI + editorial layer
**Notes:** DND/PSPC RSS gap accepted. 5-8 SerpAPI queries + 3 editorial RSS sources. Budget audit in Phase 10 Wave 0.

### Q2 — Tier-2 feed inclusion?

| Option | Description | Selected |
|--------|-------------|----------|
| Tier-1 only for v3.0 | 12 HTTP-validated feeds; cleanest scope | ✓ |
| Tier-1 + selected Tier-2 (~16-18 feeds) | Add Defense One + Defense Industry Daily + National Defense Magazine | |
| Tier-1 + all Tier-2 (~20 feeds) | Maximum source breadth; higher dedup load | |

**User's choice:** Tier-1 only for v3.0
**Notes:** Tier-2 deferred to v3.1+ if Tier-1 signal proves insufficient after first 2-4 weeks of production.

---

## Area 4: Refusal-Detector + Health-Check + Phase-0 Verification

### Q1 — Refusal-detector mechanism?

| Option | Description | Selected |
|--------|-------------|----------|
| Substring patterns + retry-once with framing nudge | Inspect for refusal patterns, retry with nudge, fall to status='partial' | ✓ |
| Structured output + classifier on response | Doubles Sonnet cost; higher reliability | |
| No detector — ship raw Sonnet output | Lowest effort; worst UX | |

**User's choice:** Substring patterns + retry-once with framing nudge
**Notes:** Patterns: `'I cannot'`, `'as an AI'`, `'safety guidelines'`, `'unable to provide'`, `"I'm not able to"`, `'cannot assist'`, `'against my'`. On second refusal: write "Section unavailable" copy + log `refusal_detected: true` in `agent_runs.notes`.

### Q2 — Per-feed health-check threshold?

| Option | Description | Selected |
|--------|-------------|----------|
| Bozo OR empty + recent-history comparison | bozo, entries=[], or <30% of 7-day avg → flag | ✓ |
| Bozo OR empty only | Catches outright dead feeds; misses gradual degradation | |
| No per-feed health-check | NOT recommended; PITFALLS HIGH risk | |

**User's choice:** Bozo OR empty + recent-history comparison
**Notes:** 7-day avg from `agent_runs.notes.feed_entry_counts`. 3+ feed flags in one fire → `status='partial'`. WhatsApp alert (WHA-03) if entire ingestion fails.

### Q3 — Phase-0 RSS endpoint verification scope?

| Option | Description | Selected |
|--------|-------------|----------|
| Verify 3 TBD endpoints + re-validate 12 Tier-1 | ~10 min; safest path | ✓ |
| Only 3 TBD endpoints (skip Tier-1 re-validation) | ~5 min; trusts 2026-05-19 research | |
| Skip Phase-0 — trust research validation | Fastest; relies on health-check to catch failures | |

**User's choice:** Verify all 15 endpoints
**Notes:** war.gov, nato.int, canada.ca defence + re-validate 12 Tier-1. Any failure: drop from `JUNO_DEFENCE_FEEDS` OR replace with SerpAPI `site:` fallback. Outputs `phase-10-feed-verification.md` artifact.

---

## Wrap-Up

| Option | Description | Selected |
|--------|-------------|----------|
| Ready — write CONTEXT.md | All 4 areas resolved | ✓ |
| Explore one more area | Candidates: smoke-test row cleanup, SerpAPI budget allocation, populated-card visual QA | |

**User's choice:** Ready — write CONTEXT.md
**Notes:** Items left to Claude's discretion in CONTEXT.md: voice UAT corpus exact composition, cron-enable mechanism (env var recommended), Phase 9 smoke-test row cleanup, Sonnet token budget audit, inclusion-category badges in UI rendering.

---

## Claude's Discretion (captured for planner)

1. **Voice UAT corpus composition** — recommended split: 2 US procurement, 1 Canadian DND, 1 conflict-zone wire, 1 dual-use tech, 1-3 borderline cases. Persist in `voice_calibration_uat_corpus.md`.
2. **Cron-enable mechanism** — env var `JUNO_CRON_ENABLED=false` default (recommended over `companies` DB table or commented-out `add_job`).
3. **Phase 9 smoke-test row cleanup** — recommended: let them age out via 30-day prune cron (no action in Phase 10).
4. **Sonnet token budget audit** — recommended: confirm $5-10/mo Juno Sonnet addition fits existing $30-50/mo Anthropic budget; document in Phase 10 final summary.
5. **Inclusion-category badges in SummaryCard** — defer to Phase 10 UI plan; may push to v3.1+ if scope grows.

## Deferred Ideas (captured for v3.1+ phases)

- Tier-2 feed inclusion (Defense Daily, Inside Defense, etc.)
- Bloomberg defence-beat voice variant
- Regional balance quota in prompt
- Per-tenant Anthropic API key (PITFALLS §5)
- Equity / financial signals on defence primes (LMT, RTX, GD) — anti-feature
- Operational / tactical / OOB intelligence — anti-feature
- Live conflict map / OSINT geospatial — out of scope
- Inclusion-category badges in SummaryCard UI
