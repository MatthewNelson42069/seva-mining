# Phase 15: Juno Weekly Viral Sweeper (Tab 3) — Research

**Researched:** 2026-05-20
**Domain:** Defence-sector X ingestion + Sonnet 4.6 synthesis + APScheduler env-gated cron
**Confidence:** HIGH on tweepy/X-API mechanics, mixed (HIGH/MEDIUM) on handle verification, MEDIUM on Sonnet prompting best-practices for defence synthesis

## Summary

Phase 15 ports the v2.1 Phase 7 Seva sweeper shape to Juno: Sunday 08:00 PT cron at lock 1021, single combined X query via `tweepy.AsyncClient.search_recent_tweets`, virality compute over the past 7 days of Juno's `daily_summaries` rows, Sonnet 4.6 synthesis of exactly 3 content angles in Janes/CSIS voice with verbatim anti-tactical clause from Phase 10, refusal-detector wrap reused verbatim. Code shape is well-precedented — Seva's `weekly_sweeper.py` is the load-bearing reference and Phase 10's `daily_summary.py::run_juno_daily_summary` is the per-tenant shape.

Research surfaced **four corrections to the CONTEXT.md D-02 starter handle set** (DefenseNews missing underscore, CDA handle wrong, canadaforces missing letters, JanesIntel case-variant). Three of nine starter handles **will return 0 hits as currently spelled**. Research also surfaced **one factual correction to the operator/quota assumption in CONTEXT.md** — the Basic tier query length limit is 512 characters (NOT 1024); 1024 is the Academic Research tier.

Critically, research surfaced **one substrate-shape contradiction with D-03**: Juno's `daily_summaries.raw_sources_jsonb` does NOT store story arrays under `defence_news` / `canadian_procurement` / `world_events` keys. It stores **diagnostic counts only** (`defence_diagnostic`, `world_events_diagnostic`, `procurement_diagnostic` — none of which carry the actual URL/title rows). D-03's substrate assumption "Sweeper reads `(row.raw_sources_jsonb or {}).get('defence_news', []) + .get('canadian_procurement', []) + .get('world_events', [])`" **will return three empty lists**. This is the single biggest planner-blocker the research found and must be resolved before plan-phase can produce a working virality compute.

**Primary recommendation:** Plan-phase MUST (1) fix the 4 broken X handles before any smoke fire; (2) treat 512 as the hard query length cap; (3) make a substrate decision on virality compute — either extend Phase 10's `run_juno_daily_summary` to persist story arrays under the expected keys (preferred), OR pivot Juno virality compute to query the daily_summaries `gold_news_md` / `ontario_law_md` / `ontario_stats_md` columns as text-only substrate (less rigorous), OR scope virality compute to v3.2 and ship Phase 15 with a partial-status-driven fallback for the first weeks. Recommended path documented in §3.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01 Single combined X query per Sunday cron.** One `tweepy.AsyncClient.search_recent_tweets` call, top-10 engagement-ranked posts returned, quota-friendly (~4 queries/month).

**D-02 Starter handle/tag set** (subject to verification — research surfaces 4 corrections; see §1):
- Think-tanks (3): `@RUSI_org`, `@CSIS`, `@IISS_org`
- Defence press (4): `@DefenseNews`, `@BreakingDefense`, `@DefenseScoop`, `@JanesIntel`
- Canadian-specific (2): `@CDA_CDAI`, `@canadaforces`
- Hashtags (2): `#defence`, `#NATO`
- EXCLUDED (anti-feature): defence-prime cashtags ($LMT, $RTX, $LDOS, $BAESY, $GD, etc.)
- Storage: constant `JUNO_SWEEPER_X_QUERY` in new file `scheduler/companies/juno/x_queries.py`

**D-03 Virality compute substrate.** Union of `(row.raw_sources_jsonb or {}).get('defence_news', []) + .get('canadian_procurement', []) + .get('world_events', [])`, dedupe by canonical URL, equal weight. Status mapping inherits Seva pattern verbatim (`completed` / `partial` / `failed`).

**D-04 New `JUNO_SWEEPER_SYSTEM_PROMPT`** in `scheduler/companies/juno/prompts.py` alongside existing `DEFENCE_NEWS_SYSTEM_PROMPT`. Components: Janes/CSIS voice anchor (verbatim Phase 10), anti-tactical clause (verbatim Phase 10 — grep-checkable string equality), "3 content angles" task framing (mirrors Seva sweeper's structure with defence-sector audience), refusal-prone framing avoidance. Anthropic client: `get_anthropic_client('juno', timeout=JUNO_SONNET_TIMEOUT)` per Phase 12 D-09 — hardcoded `'juno'` literal.

**D-05 Reuse Phase 10 refusal-detector verbatim.** Import `call_with_refusal_guard` from `scheduler/agents/juno_refusal_detector.py`. Retry-once with framing-nudge prepended; second-attempt refusal OR malformed JSON → `status='partial'`. No new refusal-detector code.

**D-06 New file `scheduler/agents/juno_weekly_sweeper.py`** (parallels Phase 10's `daily_summary.py::run_juno_daily_summary` shape, but isolated in its own file to keep `weekly_sweeper.py` byte-identical per D-10). Shared helper extraction default: prefer importing from `weekly_sweeper.py`; only fall back to duplication if it breaks D-10.

**D-07 Mirror Phase 10 rollout exactly.** Four-step: deploy disabled → manual smoke fire → voice UAT → flip `JUNO_SWEEPER_CRON_ENABLED=true`.

**D-08 Delete the Juno short-circuit at `frontend/src/pages/WeeklyViralSweeperPage.tsx:48-56`** verbatim (mirrors Phase 14 D-01 pattern).

**D-09 Frontend cross-tenant isolation test.** New `frontend/src/pages/__tests__/WeeklyViralSweeperPage.test.tsx` (mirror Phase 14 D-04). Backend isolation test new `backend/tests/test_weekly_sweeps_cross_tenant.py` — 404 (NOT 403) per JCAL-05 precedent.

**D-10 Zero Seva-side changes.** Phase 15 modifies ZERO Seva files. `weekly_sweeper.py`, `x_ingest.py`, all v2.1/v3.0/v3.1 Seva-facing components untouched. After Phase 15 lands, full Seva regression suite passes byte-identically (frontend ≥178, backend ≥188, scheduler ≥323).

### Claude's Discretion

- Exact X handle list — operator may tune at v1.0; treat starter set as tunable (per D-02 tunability path note)
- File naming/location: `scheduler/companies/juno/x_queries.py` is the recommended path; alternative naming acceptable
- Shared helper extraction strategy (D-06): planner picks (a) export-from-weekly_sweeper, (b) duplicate, or (c) refactor-to-shared-helpers
- CLI hook for manual smoke fire — planner adds if missing
- Voice UAT criteria refinement — operator may add criteria before fire

### Deferred Ideas (OUT OF SCOPE)

- Per-section sweeper sub-cards (3 sub-cards instead of 1)
- Multi-query parallel sweep (N=3-5 X queries)
- Tier-2 defence X reporters beyond starter set (mid-execution tunable, not phase blocker)
- Defence-prime cashtags ($LMT, $RTX, $LDOS, $BAESY, $GD — explicit anti-feature, permanent)
- LinkedIn / IG ingestion
- Auto-posting of sweeper angles (hard prohibition per CLAUDE.md)
- Sweeper system-prompt iteration (v3.2)
- Mobile-responsive UI
</user_constraints>

## Project Constraints (from CLAUDE.md)

CLAUDE.md directives that bind Phase 15:

- **Autoposting prohibition.** Sweeper output is operator-reviewed only; the 3 content angles are surfaced in Tab 3 for the operator to copy + manually post. No scheduled or agent-driven posting from Phase 15 deliverables.
- **Budget envelope.** Anthropic ~$30-50/mo total; Juno sweeper Sonnet call adds ~4 fires/month × ~$0.05/fire = ~$0.20/mo. Inside budget.
- **X API Basic tier $100/mo.** Sweeper read-only via `tweepy.AsyncClient.search_recent_tweets`. Combined Seva+Juno usage ~800 tweets/month, ~8% of cap.
- **APScheduler 3.11.2** — stable production target. Single-process worker. Lock IDs unique per OPS-02 assertion.
- **Anthropic SDK 0.86.0** — `AsyncAnthropic` async client (via `get_anthropic_client('juno', ...)` resolver). Hardcoded literal `'juno'` per Phase 12 D-07.
- **tweepy 4.x AsyncClient** for X API v2. Read-only Basic tier. Wait-on-rate-limit pattern already in place in `x_ingest.py`.
- **Sonnet 4.6** model name: `claude-sonnet-4-6` (matches Seva sweeper at `weekly_sweeper.py:64`; confirmed via Anthropic Models docs).
- **No raw `Anthropic(api_key=...)` constructor calls outside `anthropic_client.py`.** Grep gate per Phase 12 KEY-03.
- **No raw `select(WeeklySweep)` queries outside `queries/scoped.py`.** Per Phase 9 TENANT-03 grep gate (`scripts/verify-tenant-isolation.sh`).
- **No `if (company === 'juno') {...}` branches in `frontend/src/components/`.** Per BRAND-05 grep gate. The D-08 short-circuit removal will eliminate the existing Juno branch in `WeeklyViralSweeperPage.tsx`.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| JSWEEP-01 | Operator can enable Juno sweeper cron via `JUNO_SWEEPER_CRON_ENABLED=true` env var; default false. | Phase 10's `JUNO_CRON_ENABLED` pattern is the verbatim precedent (`worker.py:458`). Implementation mirrors that block exactly. Note: Phase 10 reads via `os.getenv()`, NOT via Settings — Phase 15 may follow the same pattern (CONTEXT.md spec to add to Settings is optional, see §6 Open Items). |
| JSWEEP-02 | Sunday 08:00 PT cron fires at lock 1021; runs `tweepy.AsyncClient.search_recent_tweets` with Juno-specific defence-sector query; computes virality over past 7 days of Juno's `daily_summaries.raw_sources_jsonb` Defence News + Canadian Procurement + World Events sub-arrays. | X handle verification in §1 (4 corrections needed). X query validation in §3 (single combined query within 512-char limit). **Virality substrate-shape contradiction in §3 — D-03's substrate read returns empty lists against current Phase 10 schema.** |
| JSWEEP-03 | Cron persists a `weekly_sweeps` row with `company_id='juno'`, status ∈ `(completed, partial, failed)`. Idempotency-filter includes `'partial'` (Phase 9 critical-fix pattern preserved). | Direct port of Phase 10 idempotency pattern at `daily_summary.py:1188-1205`. Status mapping inherits Seva sweeper logic at `weekly_sweeper.py:447-460`. |
| JSWEEP-04 | Sonnet 4.6 produces exactly 3 content angles per sweep; each angle respects Juno's voice constraints (Janes/CSIS desk energy, anti-tactical clause). Refusal-detector pattern reused — retry-with-framing-nudge, status=partial on second-attempt failure. | New `JUNO_SWEEPER_SYSTEM_PROMPT` (§4 prompting best practices). Anti-tactical clause string-equality contract with existing `DEFENCE_NEWS_SYSTEM_PROMPT` at `prompts.py:21-22` (4-sentence clause). Refusal-detector reused via `call_with_refusal_guard()` from `juno_refusal_detector.py`. |
| JSWEEP-05 | User opens `/juno/sweeper` and sees latest sweep card identically formatted to Seva's. Empty-state copy: "Juno's first viral sweep runs Sunday 08:00 PT. Check back then." | D-08 short-circuit removal (`WeeklyViralSweeperPage.tsx:48-56`) lets the existing Seva render path serve both tenants. Phase 14 D-01 is the verbatim pattern. |
| JSWEEP-06 | User can browse historical Juno sweeps via week-picker. Cross-tenant isolation: zero leak in either direction. | TanStack Query key isolation via `queryKeys.weeklySweeps(companyId, ...)` factory (already in Phase 9). Frontend D-04 test pattern + backend 404 test pattern (Phase 14 D-05 precedent). |
</phase_requirements>

## 1. X Handle Verification (D-02 Starter Set)

Each starter handle was verified against current X profile pages via WebSearch. **Four handles need correction before any cron fire** — they would return zero hits as currently spelled in CONTEXT.md.

| Handle (CONTEXT.md) | Verdict | Correct Form | Note |
|---------------------|---------|--------------|------|
| `@RUSI_org` | **ACTIVE** | `RUSI_org` | UK's leading defence/security think tank. Active in 2026 (Latin American Security Conference 2026). HIGH confidence. |
| `@CSIS` | **ACTIVE** | `CSIS` | Self-described "top national security think tank in the world." Content published as recently as May 20, 2026. HIGH confidence. Also has sub-accounts `@CSIS_ISP` (International Security Program) and `@CSIS_Tech` (Strategic Technologies) — leave for tunability path. |
| `@IISS_org` | **ACTIVE** | `IISS_org` | International Institute for Strategic Studies. London-based. HIGH confidence. |
| `@DefenseNews` | **WRONG SPELLING** | `defense_news` | Defense News' actual handle is `@defense_news` (snake_case with underscore). `@DefenseNews` does NOT match the official account. HIGH confidence — verified at twitter.com/defense_news. **Fix required.** |
| `@BreakingDefense` | **ACTIVE** | `BreakingDefense` | Verified at x.com/breakingdefense. 30K posts. Active in 2026. HIGH confidence. |
| `@DefenseScoop` | **ACTIVE** | `DefenseScoop` | Leading Pentagon-tech outlet. Verified active at x.com/DefenseScoop. HIGH confidence. |
| `@JanesIntel` | **CASE-VARIANT** | `JanesINTEL` | Janes' actual handle is `@JanesINTEL` (all-caps INTEL). X `from:` operator is case-insensitive per X API docs, so this LIKELY works — but the display name in the docs is `JanesINTEL`. MEDIUM confidence on whether case matters at the API layer; either spelling will plausibly resolve, but use the official form for clarity. Also exists: `@Jdefenseweekly` (Janes Defence Weekly) — separate account, lower frequency. |
| `@CDA_CDAI` | **WRONG HANDLE** | `CDAInstitute` | The CDA Institute (research/education arm of Conference of Defence Associations) is `@CDAInstitute`, NOT `@CDA_CDAI`. The handle `@CDA_CDAI` does not match any active account. HIGH confidence. **Fix required.** A separate, less-active `@ConfDefAssc` exists for the parent CDA but is much lower-signal. |
| `@canadaforces` | **WRONG SPELLING** | `CanadianForces` | Official Canadian Armed Forces handle is `@CanadianForces` (with "ian"). `@canadaforces` does not exist. HIGH confidence — verified at x.com/CanadianForces. **Fix required.** |

### Required handle corrections (must land before smoke fire)

```python
# OLD (CONTEXT.md D-02 — three handles broken)
JUNO_SWEEPER_X_QUERY = (
    "(from:RUSI_org OR from:CSIS OR from:IISS_org OR "
    "from:DefenseNews OR from:BreakingDefense OR from:DefenseScoop OR "
    "from:JanesIntel OR from:CDA_CDAI OR from:canadaforces OR "
    "#defence OR #NATO) -is:retweet lang:en"
)

# CORRECTED (research-verified handles)
JUNO_SWEEPER_X_QUERY = (
    "(from:RUSI_org OR from:CSIS OR from:IISS_org OR "
    "from:defense_news OR from:BreakingDefense OR from:DefenseScoop OR "
    "from:JanesINTEL OR from:CDAInstitute OR from:CanadianForces OR "
    "#defence OR #NATO) -is:retweet lang:en"
)
```

**Length check on corrected query: 207 chars** — well inside the Basic-tier 512-char limit (§3).

## 2. Tier-2 / Higher-Signal Canadian Candidates

The CONTEXT.md D-02 starter has only 2 Canadian-specific handles (`@CDA_CDAI` [broken] + `@canadaforces` [broken]). After correcting to `@CDAInstitute` + `@CanadianForces`, the Canadian footprint is still thin. Research surfaced **4 high-quality Tier-2 Canadian candidates** the operator should consider adding (or holding for the tunability path):

| Candidate | Type | Signal Quality | Notes |
|-----------|------|----------------|-------|
| `@DavePerryCGAI` | Analyst/think-tank-leader | HIGH | Dr. David Perry, President of Canadian Global Affairs Institute (CGAI). Co-director of Triple Helix MINDs Collaborate Network. PhD on defence budgeting/procurement at Carleton. **Probably the single highest-signal Canadian defence analyst on X.** Active. |
| `@Murray_Brewster` | Defence reporter | HIGH | CBC News senior defence writer, Ottawa. 15 months covering Afghan war for CP. 12 RTNDA awards + Ross Munro Award for defence writing. The dominant Canadian defence-beat voice. Active. |
| `@CadsiCanada` | Industry association | MEDIUM-HIGH | Canadian Association of Defence and Security Industries — represents 700+ Canadian defence/security/emerging-tech companies generating $16B/yr in revenue. Strong on procurement/contract signals. Active. |
| `@NationalDefence` | Government department | MEDIUM | Official Department of National Defence (DND) account. Government-line-output style; high authoritative signal but lower frequency and signal-to-noise ratio than analyst/journalist accounts. Active. |

**Recommendation for plan-phase / operator:**

- **Highest-ROI adds:** `@DavePerryCGAI` + `@Murray_Brewster` — both individual analysts/journalists, daily posting, defence-procurement-flavored content directly aligned with Juno's brief.
- **Question for operator:** add these to v1.0 D-02 set, or hold for tunability-path iteration after first 2-4 weeks of production sweep data shows whether the 9-handle starter is signal-thin?
- **Capacity note:** Each added `from:` operator adds ~25 chars. Adding all 4 = +101 chars; new total ≈ 308 chars — still inside 512-char limit. No length blocker either way.

**Out-of-scope candidates surfaced for documentation** (do NOT add — see anti-features):

- `@LockheedMartin`, `@RTXcorp`, `@GeneralDynamics` — defence-prime corporate accounts. Their posts skew toward equity/financial signals on primes which is the explicit anti-feature per CONTEXT.md and PROJECT.md.
- Branch-specific Canadian accounts: `@CanadianArmy`, `@RCAF_ARC`, `@CJOC_COIC` — official operational accounts; risk of surfacing tactical/operational content that triggers the anti-tactical clause + refusal-detector. Higher-volume noise without offsetting signal lift. Hold.
- Philippe Lagassé's Substack is a high-signal Canadian defence source — but he's not particularly active on X. The Lagassé Substack is already a Phase 10 daily-summary feed (RSS-side); no need to add him to the X query.

## 3. X Query Syntax + Quota Validation (JSWEEP-02)

### Operator validity on Basic tier

All operators used in the proposed CONTEXT.md combined query are **Core operators** available on the Basic/Self-serve tier per X API docs:

| Operator | Type | Basic-tier? | Used in Juno query? |
|----------|------|-------------|---------------------|
| `from:USERNAME` | Core (standalone) | YES | YES (9 instances) |
| `OR` (Boolean) | Core | YES | YES (10 instances) |
| `#hashtag` | Core | YES | YES (2 instances: `#defence`, `#NATO`) |
| `-is:retweet` | Core (negation of is:retweet) | YES | YES (1 instance) |
| `lang:en` | Core | YES | YES (1 instance) |
| `(...)` Boolean grouping | Core syntax (parentheses for grouping) | YES | YES (one outer group) |

**Source:** X Developer Platform Build-a-Query docs + Tweepy 4.14.0 AsyncClient docs. The community-reference page at GetXAPI explicitly confirms `is:retweet` works on Basic-tier search/recent. HIGH confidence.

### Query length limit (CORRECTION TO CONTEXT.md)

**CONTEXT.md says: 1024 chars. ACTUAL Basic tier limit: 512 chars.**

| Project tier | Query length limit |
|-------------|--------------------|
| **Standard Project, Basic access level** (Seva's current tier — $100/mo) | **512 characters** |
| Academic Research, Basic access level | 1024 characters |
| Enterprise | 4096 characters |

The 1024-char number in CONTEXT.md appears to be a conflation of these tiers. The **operative limit for this project is 512 chars**.

**Source:** X Developer Build-a-Query docs (verified via WebFetch), corroborated by Tweepy 4.14.0 AsyncClient docs, and multiple community references (dev.to, Medium tutorials). HIGH confidence.

### Length budget for the corrected Juno query

- Corrected query as documented in §1: **207 characters** (60% headroom on 512).
- Adding all 4 Tier-2 Canadian candidates from §2: **~308 characters** (40% headroom).
- Adding 4 Tier-2 + 3 additional branch/defence handles for hypothetical v1.2: **~410 characters** (still under). 

Plenty of room. The 512-char limit is not a blocker for the starter set or for reasonable expansion.

### Operator-count guidance (separate from char limit)

Community tutorials (Tweepy docs, dev.to "How to search for Tweets about various Topics") flag a **soft guidance of ≤10 keywords/operators per query** to avoid "query too complex" errors from the API. The current corrected Juno query has **9 `from:` clauses + 2 hashtag clauses + 1 `-is:retweet` + 1 `lang:en` = ~13 distinct operands**, joined by 10 `OR` operators. This is right at or marginally above the soft guidance line.

Practical implications:
- The 9-handle Boolean-OR pattern matches Seva's `weekly_sweeper.py:74-79` Seva-side query (which combines ~12 keywords + 5 cashtags + 3 hashtags + 2 filters), so this pattern is **already running successfully in production** for Seva. The operator-count guideline is a soft floor, not a hard ceiling.
- If the API returns "query too complex" on the first smoke fire, fallback is to drop hashtags or split into 2 sequential queries (out of scope per D-01; would require a CONTEXT amendment).
- MEDIUM confidence that the current 13-operand query works. Validate at smoke fire.

### Boolean grouping with parentheses

X API v2 explicitly supports Boolean grouping: `(A OR B OR C)`. Example from docs: `(cats OR dogs) (video OR pic)`. The Juno query's outer parentheses group is valid syntax.

**Anti-pattern flagged in docs:** Do NOT negate a parenthesized group (`-(A OR B)` is ill-defined). The current Juno query negates `is:retweet` as a standalone operator, not a group — safe.

### `from:` case sensitivity

X handles are case-insensitive at the API layer for the `from:` operator. `from:JanesINTEL` and `from:janesintel` resolve identically. Use the official form (`JanesINTEL`) for code-readability. HIGH confidence.

### Quota math (Basic tier $100/mo, ~10K tweets/month cap)

CONTEXT.md is correct on quota math:

| Source | Monthly tweets |
|--------|----------------|
| Seva sweeper (existing) | ~400 (4 calls × 100 tweets) |
| Juno sweeper (Phase 15) | ~400 (4 calls × 100 tweets) |
| Content-agent `video_clip` X-API calls (existing) | Already accounted for in current usage |
| **Combined headroom** | ~8-10% of cap |

The `scheduler/agents/x_ingest.py:43` quota safety margin (500 tweets) further protects against cap overrun. No quota changes needed for Phase 15.

### CRITICAL — virality compute substrate contradicts D-03

This is the single biggest planner-blocker the research found.

**D-03 says:** Sweeper reads `(row.raw_sources_jsonb or {}).get('defence_news', []) + .get('canadian_procurement', []) + .get('world_events', [])`, dedupes by URL, uses as virality substrate.

**Actual `raw_sources_jsonb` shape from `run_juno_daily_summary` at `daily_summary.py:1336-1358`:**

```python
notes_dict: dict = {
    # base_payload from juno_hc.build_notes_payload(...) — feed health counts only
    **base_payload,
    "defence_feed_entry_counts": dict(defence_counts),     # dict[source_name -> int]
    "defence_diagnostic": defence_diag,                    # {refusal_detected, first_attempt_excerpt, ...}
    "procurement_diagnostic": procurement_diag,            # {skipped_reason, serpapi_hit_count, refusal_detected, ...}
    "world_events_diagnostic": world_diag,                 # {world_events_total_seen, world_events_survived, world_events_categories, ...}
    "serpapi_query_count": serpapi_count,
    "is_morning_fire": is_morning_fire,
    "overall_status": overall_status,
    "haiku_validation_errors": [...],
}
```

**None of `defence_news`, `canadian_procurement`, `world_events` are top-level keys** with story-array values. The actual raw stories (title/link/source_name) are LOADED in `_run_juno_health_check` (line 925-932), CONSUMED by `_build_juno_defence_news_section`, then **discarded**. Only counts and diagnostics survive to `raw_sources_jsonb`.

**Impact on D-03:** With the current Phase 10 schema, `(row.raw_sources_jsonb or {}).get('defence_news', [])` returns `[]` for every existing Juno row. Virality compute over the past 7 days would always produce 0 cross-referenced stories → every Juno sweep would trip the insufficient-signal path → `status='partial'` on every fire indefinitely.

**Three planner options to resolve:**

1. **(Recommended) Extend Phase 10's `run_juno_daily_summary` to persist story arrays.** Add `defence_news: [...], canadian_procurement: [...], world_events: [...]` top-level keys to `notes_dict` with the actual `{title, link, source_name, published}` dicts from each section's input. ~30 LOC across `_build_juno_defence_news_section`, `_build_juno_canadian_procurement_section`, `_build_juno_world_events_section` (return entries alongside markdown), plus `notes_dict` assembly in `run_juno_daily_summary`. **Does NOT violate D-10** (D-10 protects Seva; this touches Juno code only). The DB column is JSONB — no schema migration needed. Cleanest path.

2. **Pivot virality compute to text-only substrate.** Parse `gold_news_md` / `ontario_law_md` / `ontario_stats_md` (the markdown columns) with a regex to extract `[link](url)` patterns. Less rigorous; risks attribution noise; Sonnet-generated markdown may not always include URLs.

3. **Scope virality compute to v3.2.** Ship Phase 15 with virality compute returning `[]` (no cross-reference) — `status='partial'` on every early fire with diagnostic note "virality substrate empty, see v3.2." Sonnet still gets X posts as input; just no cross-reference signal. Loses the "connect X signal with news-week signal" task contract — defeats Phase 15's value prop. Not recommended.

**Recommendation:** Option (1). It's a ~30-LOC Phase 10 amendment that lands inside Phase 15 (no Phase 10 reopen). It also has independent value beyond the sweeper — future analytics features may want to query raw entries by source/date. Plan-phase MUST present this option to the operator for explicit go/no-go before producing tasks.

## 4. Sonnet "3 Content Angles" Prompting Best Practices

### What Anthropic-published guidance says (HIGH confidence)

Anthropic's prompt-engineering docs at `platform.claude.com/docs/en/build-with-claude/prompt-engineering` consistently recommend:

1. **System prompt for persistent format constraints.** Per the Anthropic best-practices guide: "Place format instructions in your system prompt when you need them to apply consistently across every response in a session" — use a template like: `Output format: Respond in [format], Limit response to [X items], Do not include [preamble]`. The "exactly 3 angles" constraint belongs in `JUNO_SWEEPER_SYSTEM_PROMPT`, not the user prompt.

2. **XML tags for structured output.** Anthropic models are "particularly adept at understanding structured information provided through XML tags" — Claude has been specifically trained to recognize and utilize XML structure. For Phase 15: wrap each angle in `<angle index="1">...</angle>` tags, or use the existing Seva-sweeper Markdown `### Angle N:` header pattern (already proven in production for Seva).

3. **Explicit count constraint + grounding rule pair.** Seva's `weekly_sweeper.py:204-226` already follows this pattern with high success: "Output MUST be markdown in this exact structure" + "Grounding rule: Use ONLY facts ... present in the supplied inputs. ... If you cannot ground an angle in the supplied inputs, do not generate it — return fewer than 3 angles rather than hallucinate." This is the load-bearing prior-art template.

4. **Negative-space framing.** Anthropic recommends "DO NOT" lists for behaviors that must NOT appear. Phase 10's `DEFENCE_NEWS_SYSTEM_PROMPT` ends with such a negative-space list (`prompts.py:37-41`). Phase 15's sweeper prompt should repeat or extend it (defence-prime cashtag exclusion, force-posture/OOB/troop-movement exclusion).

### What Anthropic-published guidance says about defence content (MEDIUM confidence, mixed)

The **Anthropic-Pentagon dispute (Feb-Apr 2026)** has direct downstream relevance:

- Anthropic refused DoD demands to remove contractual restrictions on "fully autonomous weapons" + "domestic surveillance." DoD designated Anthropic a "supply chain risk" and barred US defense contractors from using Claude.
- Practical implication for Phase 15: Claude's content-policy guardrails for defence content are **tightening**, not loosening, in 2026. The refusal-detector (Phase 10's `juno_refusal_detector.py`) is more load-bearing now than at Phase 10 design time.
- However: Anthropic explicitly continues to allow market/industry commentary on defence sector — Sonnet 4.6 is the model serving Claude Gov via Palantir for classified work. The boundary is operational/tactical/targeting content, NOT defence-trade-press analytical content. **This boundary maps exactly to the existing Phase 10 anti-tactical clause** — which is why D-04 mandates verbatim reuse.

### Concrete prompt-structure recommendation for `JUNO_SWEEPER_SYSTEM_PROMPT`

Mirror Seva sweeper structure (`weekly_sweeper.py:204-226`), but with the following defence-specific substitutions and additions:

1. **Voice anchor** (replace Seva's "Bloomberg commodities-desk energy"): Use Phase 10's verbatim voice line — "senior defence-industry analyst writing for a Canadian defence-tech operator. Tone: authoritative, sober, sourced-with-receipts. Match the energy of a Janes desk brief, a CSIS analysis piece, an IISS Military Balance update, or a Defense News editorial column."

2. **Anti-tactical clause** (verbatim from `DEFENCE_NEWS_SYSTEM_PROMPT` at `prompts.py:21-22`) — this is the string-equality contract per D-04. Plan-phase MUST grep-check.

3. **Task framing for "exactly 3 angles"** (mirror Seva's structure):
   - "Output MUST be markdown in this exact structure (no preamble, no postamble): `### Angle 1: ... ### Angle 2: ... ### Angle 3: ...`"
   - "Each angle MUST connect an X (Twitter) signal from the defence-sector conversation with a mainstream defence-news signal from the past week."
   - "Grounding rule: Use ONLY facts ... present in the supplied inputs."
   - "If you cannot ground an angle in the supplied inputs, do not generate it — return fewer than 3 angles rather than hallucinate." (matches Seva's anti-hallucination line at `weekly_sweeper.py:208`)

4. **Bull-thesis bias INVERSION:** Seva's prompt enforces gold-bull-thesis bias. Phase 15 has NO equivalent — defence sector is neutral on conflict per D-04. Replace with: "Take no analyst position on whether conflicts escalate or de-escalate. Neutral-on-conflict per Janes/CSIS desk convention." This is the load-bearing differentiator from Seva's prompt.

5. **Negative-space (DO NOT) list:**
   - No defence-prime cashtags ($LMT, $RTX, $GD, etc.) — anti-feature
   - No force posture, order of battle (OOB), capability-gap, troop-movement, or targeting analysis (anti-tactical)
   - No buy/sell framing on defence equities
   - No advocacy for or against specific weapons programs
   - No speculation on classified material or operational intent

6. **Refusal-prone-framing avoidance** (D-04 specific): explicitly tell the model that the task is "defence-industry market commentary, not tactical or operational intelligence." This duplicates the framing-nudge that `juno_refusal_detector.FRAMING_NUDGE` prepends on retry — having it in the system prompt up-front reduces the refusal rate on first attempt.

### Plan-phase verification gate

Plan-phase MUST grep-check that `JUNO_SWEEPER_SYSTEM_PROMPT` contains the EXACT bytes of the anti-tactical clause from `DEFENCE_NEWS_SYSTEM_PROMPT`:

```bash
# Anti-tactical clause bytes (verbatim from prompts.py:21-22, ~250 chars):
"FORBID — anti-tactical framing clause:
You produce market/industry commentary on the defence sector. You do NOT produce operational, tactical, targeting, force posture, order of battle (OOB), capability gap, or troop movement analysis. If a source story crosses into operational territory, summarize the market/industry implications only and explicitly note the operational details were excluded."
```

A test in `scheduler/tests/companies/juno/test_prompts.py` (new file or extend existing) should assert `ANTI_TACTICAL_CLAUSE in JUNO_SWEEPER_SYSTEM_PROMPT and ANTI_TACTICAL_CLAUSE in DEFENCE_NEWS_SYSTEM_PROMPT` to lock the string-equality contract.

## 5. Validation Architecture (Nyquist Dimension 8)

Phase 15 `workflow.nyquist_validation` is enabled per `.planning/config.json`. The following test matrix shape MUST be present at phase exit.

### Test Framework
| Property | Value |
|----------|-------|
| Backend framework | pytest + pytest-asyncio (existing — used by `backend/tests/` + `scheduler/tests/`) |
| Frontend framework | Vitest + React Testing Library (existing — used by `frontend/src/pages/__tests__/`) |
| Config files | `scheduler/tests/conftest.py`, `backend/tests/conftest.py`, `frontend/vitest.config.ts` — all exist |
| Quick run command (scheduler) | `cd scheduler && pytest tests/agents/test_juno_weekly_sweeper.py -x` |
| Quick run command (backend) | `cd backend && pytest tests/test_weekly_sweeps_cross_tenant.py -x` |
| Quick run command (frontend) | `cd frontend && npm test -- WeeklyViralSweeperPage.test.tsx` |
| Full suite | `cd scheduler && pytest && cd ../backend && pytest && cd ../frontend && npm test` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| JSWEEP-01 | When `JUNO_SWEEPER_CRON_ENABLED` unset/false, `build_scheduler()` registers no `juno_weekly_sweeper` job. When `=true`, exactly one is registered at lock 1021 with Sunday 08:00 PT trigger. | unit (worker scheduler) | `pytest scheduler/tests/test_worker.py::test_juno_sweeper_cron_disabled_by_default` + `test_juno_sweeper_cron_enabled_registers_job` | ❌ Wave 0 — extend existing `test_worker.py` (which already tests `JUNO_CRON_ENABLED` pattern at line 128+) |
| JSWEEP-02 | `JUNO_SWEEPER_X_QUERY` is a non-empty string ≤512 chars containing `from:` operators + `-is:retweet lang:en`. `run_juno_weekly_sweeper()` happy path: X ingest → virality compute (3-sub-array union, deduped by canonical URL) → Sonnet call. | unit | `pytest scheduler/tests/agents/test_juno_weekly_sweeper.py::test_query_constant_valid` + `test_run_happy_path` + `test_virality_compute_three_sub_array_union` + `test_virality_compute_dedupes_by_canonical_url` | ❌ Wave 0 |
| JSWEEP-03 | Idempotency filter includes `'partial'`: when a recent Juno sweep with `status='partial'` exists, second invocation skips without writing duplicate row. `weekly_sweeps` row written with `company_id='juno'` only. | unit | `pytest scheduler/tests/agents/test_juno_weekly_sweeper.py::test_idempotency_skip_when_partial_exists` + `test_idempotency_skip_when_completed_exists` + `test_idempotency_skip_when_running_exists` + `test_persisted_row_has_company_id_juno` | ❌ Wave 0 |
| JSWEEP-04 | Sonnet call uses `get_anthropic_client('juno', ...)` hardcoded literal. `JUNO_SWEEPER_SYSTEM_PROMPT` contains verbatim anti-tactical clause. Refusal-detector: first refusal → retry-with-nudge; second refusal → `status='partial'`. | unit + property | `pytest scheduler/tests/agents/test_juno_weekly_sweeper.py::test_anthropic_client_called_with_juno_literal` + `test_refusal_first_attempt_retries` + `test_refusal_second_attempt_sets_partial` + `pytest scheduler/tests/companies/juno/test_prompts.py::test_anti_tactical_clause_in_sweeper_prompt` | ❌ Wave 0 (both files new) |
| JSWEEP-05 | After D-08 short-circuit removal, `<WeeklyViralSweeperPage />` at `/juno/sweeper` route renders the same component path as `/seva/sweeper`. Empty-state copy renders when no sweeps. | unit (React) | `npm test -- WeeklyViralSweeperPage.test.tsx -- --testNamePattern "renders for juno"` | ❌ Wave 0 |
| JSWEEP-06 | Cross-tenant isolation: TanStack Query keys differ between `/juno/sweeper` and `/seva/sweeper`; cache for one company does not bleed into other. Backend: GET `/api/juno/weekly-sweeps/{seva_uuid}` returns 404, NOT 403. | integration + RTL | Backend: `pytest backend/tests/test_weekly_sweeps_cross_tenant.py -x` (all tests). Frontend: `npm test -- WeeklyViralSweeperPage.test.tsx -- --testNamePattern "tenant isolation"` | ❌ Wave 0 (both files new) |

### Sampling Rate
- **Per task commit:** quick run command for the specific file changed (scheduler / backend / frontend)
- **Per wave merge:** full suite (`scheduler/ && backend/ && frontend/` all green)
- **Phase gate:** Full suite green + `scripts/verify-tenant-isolation.sh` exit 0 + `scripts/verify-anthropic-resolver.sh` exit 0 before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `scheduler/tests/agents/test_juno_weekly_sweeper.py` — covers JSWEEP-02, -03, -04 (~12 test functions per ROADMAP §Success Criteria)
- [ ] `scheduler/tests/companies/juno/test_prompts.py` — anti-tactical clause string-equality grep test (covers JSWEEP-04 contract)
- [ ] `backend/tests/test_weekly_sweeps_cross_tenant.py` — covers JSWEEP-06 backend isolation (mirror Phase 14's `test_calendar_cross_tenant.py`)
- [ ] `frontend/src/pages/__tests__/WeeklyViralSweeperPage.test.tsx` — covers JSWEEP-05 + JSWEEP-06 frontend isolation (mirror Phase 14's `ContentCalendarPage.test.tsx`)
- [ ] `scheduler/tests/test_worker.py` — EXTEND existing file with `JUNO_SWEEPER_CRON_ENABLED` env-gate tests alongside existing `JUNO_CRON_ENABLED` tests
- [ ] No framework install needed — pytest, pytest-asyncio, vitest, RTL all already present

## 6. Open Items for Planner

The following items are NOT resolvable by research and require planner judgment or operator input:

1. **CRITICAL — D-03 virality substrate decision.** As documented in §3, the CONTEXT.md D-03 substrate read returns empty lists against the current Phase 10 `raw_sources_jsonb` schema. Plan-phase MUST present three options to the operator (extend Phase 10 to persist story arrays [recommended], pivot to markdown-text-parsing substrate, or defer virality compute to v3.2) and obtain go/no-go before generating tasks. If option (1) chosen, plan-phase MUST add a wave that amends `daily_summary.py::_build_juno_*_section` functions to return entries alongside markdown, and amends `run_juno_daily_summary` to write them under top-level keys.

2. **D-02 handle corrections — operator sign-off.** Research confirms 4 of 9 starter handles need correction (§1). Plan-phase MUST surface this to operator in the discussion-log; recommended path is to update the JUNO_SWEEPER_X_QUERY constant with the corrected forms before first smoke fire. No CONTEXT amendment needed if treated as "research-verified D-02 starter," but operator should acknowledge.

3. **D-02 Tier-2 Canadian additions — operator decision.** Research recommends adding `@DavePerryCGAI` + `@Murray_Brewster` to v1.0 (§2). Plan-phase MUST ask operator whether to include in v1.0 D-02 or hold for tunability path. No CONTEXT amendment needed if held; if included, document as part of plan.

4. **`JUNO_SWEEPER_CRON_ENABLED` Settings field — pattern decision.** CONTEXT.md D-spec says add `juno_sweeper_cron_enabled: bool = False` to `scheduler/config.py` Settings. However, the analogous Phase 10 `JUNO_CRON_ENABLED` is **NOT** in Settings — it's read via `os.getenv()` directly in `worker.py:458`. Planner picks: (a) follow CONTEXT spec literally (add to Settings + use `settings.juno_sweeper_cron_enabled`), or (b) mirror Phase 10 verbatim (`os.getenv("JUNO_SWEEPER_CRON_ENABLED", "false").lower() == "true"` in worker.py). Recommend (b) — exact Phase 10 mirror — for minimal change footprint and pattern consistency. Both produce identical behavior.

5. **Anti-tactical clause string-equality test location.** Plan-phase decides whether `scheduler/tests/companies/juno/test_prompts.py` is a new file or extension to an existing one (`scheduler/tests/companies/` may not yet exist as a directory). Check before generating.

6. **Shared helper extraction from `weekly_sweeper.py`.** Per D-06, planner picks among (a) export-from-Seva-sweeper, (b) duplicate in Juno file, (c) refactor into `sweeper_helpers.py`. Candidates for extraction from `weekly_sweeper.py`: `canonical_url()` (line 90), `_engagement_score()` (in `x_ingest.py:62` — already module-public), `_sunday_of_this_week()` (line 314), `_build_x_posts_md()` (line 229). Recommend (a) export-from-Seva because D-10 byte-identical contract is about behavior preservation, not name-mangling; adding `from agents.weekly_sweeper import canonical_url, _sunday_of_this_week` to Juno module does NOT regress Seva tests.

7. **CLI hook for manual smoke fire.** Per D-07 step 2, operator needs `python -m scheduler.cli run_juno_weekly_sweeper` or analogous. Check whether `scheduler/cli.py` exists; if not, plan-phase adds a thin shim. Alternative: a `__main__` block at the bottom of `juno_weekly_sweeper.py` (mirrors Seva sweeper's `weekly_sweeper.py:545-550`) — this is the minimal-LOC path and aligns with the existing Seva pattern.

8. **Voice UAT artifact path.** ROADMAP references `.planning/phases/15-juno-weekly-viral-sweeper/voice_calibration_uat.md` (mirroring Phase 10). Plan-phase adds this as a deliverable; criteria refined per CONTEXT specifics §Voice UAT criteria.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | scheduler runtime | ✓ | 3.12+ per CLAUDE.md | — |
| FastAPI | backend router | ✓ | 0.135.1 | — |
| APScheduler | cron registration | ✓ | 3.11.2 | — |
| anthropic SDK | Sonnet 4.6 call | ✓ | 0.86.0 (CLAUDE.md), via `get_anthropic_client('juno', ...)` resolver | shared key per Phase 12 D-02 if per-tenant unset |
| tweepy | X API search/recent | ✓ | 4.x | — |
| SQLAlchemy | DB ops | ✓ | 2.0.x async | — |
| pydantic-settings | config | ✓ | 2.x | — |
| pytest + pytest-asyncio | scheduler+backend tests | ✓ | existing | — |
| Vitest + RTL | frontend tests | ✓ | existing | — |
| `claude-sonnet-4-6` model | synthesis | ✓ | Released 2026-02-17 per Anthropic announcement, currently active and not deprecated | — |
| `claude-haiku-4-5` model | NOT USED by sweeper (Phase 10 only) | n/a | — | n/a |
| X API Bearer Token (Basic tier, $100/mo) | search_recent_tweets | ✓ | settings.x_api_bearer_token already required | — |
| `JUNO_ANTHROPIC_API_KEY` | per-tenant cost attribution | ✓ if set in Railway env | optional (Phase 12 D-02 fallback) | shared ANTHROPIC_API_KEY |
| Phase 10 modules (`juno_refusal_detector.py`, `companies/juno/prompts.py`) | reuse | ✓ | shipped 2026-05-19 | — |
| Phase 12 `anthropic_client.py` resolver | per-tenant Sonnet billing | ✓ | shipped pre-15 | — |
| Phase 9 `weekly_sweeps` Alembic 0014 + scoped helpers | multi-tenant DB | ✓ | shipped pre-15 | — |
| Phase 9 `JOB_LOCK_IDS['juno_weekly_sweeper'] = 1021` | advisory lock | ✓ | already in `worker.py:108` | — |

**Missing dependencies with no fallback:** None. All required dependencies present from prior phases.

**Missing dependencies with fallback:** `JUNO_ANTHROPIC_API_KEY` — falls back to shared key per Phase 12 D-02. Operator sets this in Railway env separately from Phase 15 deploy.

## Standard Stack (versions verified)

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| tweepy | 4.x (4.14.0 stable) | X API v2 AsyncClient | Already in production via `x_ingest.py` for Seva sweeper. Industry standard for X API v2 in Python. |
| anthropic | 0.86.0 (per CLAUDE.md) | AsyncAnthropic client for Sonnet 4.6 | Already in production via Phase 10. `claude-sonnet-4-6` model verified active. |
| APScheduler | 3.11.2 | Sunday 08:00 PT CronTrigger | Already in production. v4 is alpha — avoid. |
| SQLAlchemy | 2.0.x (asyncpg driver) | `weekly_sweeps` INSERT, `daily_summaries` query | Phase 9 + Phase 10 precedent. Use `scoped_*` helpers. |
| pytest + pytest-asyncio | latest | scheduler + backend tests | Existing config; no install needed. |
| Vitest + React Testing Library | latest | frontend cross-tenant test | Existing; mirror Phase 14 D-04 pattern. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pydantic-settings | 2.x | env var loading (optional — see Open Item 4) | If planner picks Settings-field path for `JUNO_SWEEPER_CRON_ENABLED` |
| date-fns (frontend) | 3.x | Sunday computation for empty-state copy | Existing — already used by `WeeklyViralSweeperPage.tsx` |
| TanStack Query | 5.x | `queryKeys.weeklySweeps(companyId, ...)` per-tenant key isolation | Existing — JCAL precedent |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `os.getenv("JUNO_SWEEPER_CRON_ENABLED")` | `Settings.juno_sweeper_cron_enabled` | Settings adds typed validation but breaks Phase 10 pattern parity. Open Item 4. |
| Single-file Juno sweeper | Shared `sweeper_helpers.py` extraction | Helpers extraction is cleaner long-term but D-06 default is single-file. |

**Installation:** Nothing new. All dependencies present.

**Version verification:**
```bash
# Verified active models from Anthropic
# claude-sonnet-4-6 — released 2026-02-17, currently active, not deprecated
# Source: anthropic.com/news/claude-sonnet-4-6 (Feb 17 2026)

# Verified tweepy 4.14.0 supports AsyncClient.search_recent_tweets with:
#   - query parameter (string, max 512 chars Standard/Basic tier)
#   - max_results (max 100 for recent search)
#   - tweet_fields, expansions, user_fields
# Source: docs.tweepy.org/en/stable/asyncclient.html
```

## Architecture Patterns

### Recommended Project Structure (Phase 15 additions)

```
scheduler/
├── agents/
│   └── juno_weekly_sweeper.py     # NEW — run_juno_weekly_sweeper() orchestrator
├── companies/juno/
│   ├── prompts.py                  # MODIFIED — append JUNO_SWEEPER_SYSTEM_PROMPT
│   └── x_queries.py                # NEW — JUNO_SWEEPER_X_QUERY constant
├── worker.py                       # MODIFIED — env-gated cron registration at lock 1021
└── tests/
    ├── agents/
    │   └── test_juno_weekly_sweeper.py    # NEW — unit tests
    └── companies/juno/
        └── test_prompts.py                # NEW — anti-tactical string-equality test

backend/tests/
└── test_weekly_sweeps_cross_tenant.py     # NEW — 404 contract

frontend/src/pages/
├── WeeklyViralSweeperPage.tsx              # MODIFIED — delete short-circuit at 48-56
└── __tests__/
    └── WeeklyViralSweeperPage.test.tsx     # NEW — RTL + TanStack key isolation
```

### Pattern 1: Per-tenant Sweeper Orchestrator (mirrors Phase 10 daily_summary)

**What:** `run_juno_weekly_sweeper()` mirrors `run_juno_daily_summary()` shape exactly: idempotency check via `scoped_weekly_sweeps('juno')` → `agent_runs` INSERT (status='running') → X ingest → virality compute → Sonnet call via refusal-detector wrap → `weekly_sweeps` INSERT with `company_id='juno'` → finally telemetry.

**When to use:** Every per-tenant scheduled agent in this project follows this shape. Do not deviate.

**Example:** See `scheduler/agents/daily_summary.py:1147-1404` (the canonical reference). The Seva sweeper at `weekly_sweeper.py:349-538` is the shape for the sweeper-specific bits (X ingest + virality + Sonnet angle generation).

### Pattern 2: Env-gated Cron Registration (mirrors Phase 10)

**What:** `if os.getenv("JUNO_SWEEPER_CRON_ENABLED", "false").lower() == "true":` wraps `scheduler.add_job(...)`. Both ENABLED and DISABLED paths log at INFO level at boot. No deploy required to flip.

**Example:** `scheduler/worker.py:458-480` is the verbatim pattern. Copy that block, swap env var name + lock ID + trigger + job factory.

### Pattern 3: Verbatim Anti-Tactical Clause (string-equality contract)

**What:** Phase 15's `JUNO_SWEEPER_SYSTEM_PROMPT` contains the exact bytes of `DEFENCE_NEWS_SYSTEM_PROMPT`'s anti-tactical clause (line 21-22 of `prompts.py`). Grep-checkable. A test asserts the substring is present in both prompts.

**When to use:** Any new Juno Sonnet call site. Defence content-policy compliance depends on this being a verbatim string-equality contract, not a paraphrase.

### Anti-Patterns to Avoid

- **Hand-rolled Anthropic client.** Use `get_anthropic_client('juno', timeout=...)` per Phase 12. Grep gate (`scripts/verify-anthropic-resolver.sh`) fails CI if you call `Anthropic(api_key=...)` directly outside `anthropic_client.py`.
- **Variable `company_id` in resolver call.** Per Phase 12 D-07, use hardcoded literal `'juno'` at the call site. NOT `get_anthropic_client(company_id, ...)`. Inline comment cites Phase 12 Hard Part P8.
- **Raw `select(WeeklySweep)` queries.** Use `scoped_weekly_sweeps('juno')` per Phase 9 TENANT-03. Grep gate (`scripts/verify-tenant-isolation.sh`) fails CI.
- **Idempotency filter omitting `'partial'`.** Phase 9 critical bugfix. Filter MUST be `status.in_(['running', 'completed', 'partial'])`. Test exists to enforce.
- **`if (company === 'juno')` branches in frontend components.** Per BRAND-05. The D-08 short-circuit removal eliminates the existing instance; do not introduce a new one.
- **Modifying Seva files.** D-10 zero-regression. Importing from Seva's `weekly_sweeper.py` is fine (read-only); editing it is not.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Anthropic client per-tenant resolution | `Anthropic(api_key=settings.juno_anthropic_api_key or settings.anthropic_api_key)` | `get_anthropic_client('juno', timeout=JUNO_SONNET_TIMEOUT)` | Phase 12 resolver handles fallback + STRICT mode + logging. Grep gate enforces. |
| Sonnet refusal detection + retry | new regex matcher + retry-loop | `call_with_refusal_guard(client, model=..., system=..., user_prompt=..., section_name='sweeper')` | Phase 10 module (`juno_refusal_detector.py`) is the single source of truth. 7 substring patterns + framing-nudge already production-tested. |
| Advisory lock wrapper | new `try/finally` with `pg_advisory_lock()` | `with_advisory_lock(conn, JOB_LOCK_IDS["juno_weekly_sweeper"], ...)` | Existing helper at `worker.py`. Lock 1021 already reserved. |
| Multi-tenant SELECT | raw `select(WeeklySweep).where(WeeklySweep.company_id == 'juno')` | `scoped_weekly_sweeps('juno')` | Phase 9 TENANT-03 grep gate enforces. Identical SQL, mandatory routing. |
| URL canonicalization for virality | new urlparse logic | `canonical_url(url)` from `agents.weekly_sweeper` (export-from-Seva pattern) | Seva sweeper at `weekly_sweeper.py:90-116` already handles UTM/fbclid/gclid/ref/source/_ga + path normalization + query sort. Battle-tested. |
| X engagement re-rank | new score formula | `_engagement_score(metrics)` from `agents.x_ingest` (already module-public) | `x_ingest.py:62` is the canonical formula: `likes + retweets*2 + replies*1.5`. Locked per Seva Phase 7 D-06. |
| Empty-state Sunday-date computation | new date math | `nextSundayLabel(now)` from `frontend/src/pages/WeeklyViralSweeperPage.tsx:21-28` | Already exists in the Seva render path; reused once D-08 short-circuit removed. |
| TanStack Query key factory | inline key array | `queryKeys.weeklySweeps(companyId, ...)` | Phase 9 D-08 factory; ensures cache isolation between `/seva/sweeper` and `/juno/sweeper`. |
| Per-tenant 404 contract | new error response | Standard Phase 14 D-05 pattern via `Depends(get_current_company)` | Backend returns 404 (NOT 403) for tenant-existence isolation. JCAL-05 precedent. |

**Key insight:** Phase 15 has roughly zero new infrastructure to build. Every load-bearing abstraction already exists from Phases 7, 9, 10, 12, or 14. The Phase 15 task surface is **constant-and-prompt addition** + **cron wiring** + **short-circuit deletion** + **cross-tenant tests**. The total ~500-700 LOC estimate in CONTEXT.md is consistent with this — most of it is the new `juno_weekly_sweeper.py` orchestrator, which is itself ~80% Seva-sweeper-shaped boilerplate.

## Runtime State Inventory (refactor/rebrand audit)

> This is a **net-add** phase (new module, new constants, new tests) — not a rename/refactor. Most categories are not applicable. Audit completed for completeness:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — Phase 15 creates a new code path; no existing strings are being renamed. `weekly_sweeps` rows for Juno will start landing post first cron fire; no migration needed since Alembic 0014 already provides `company_id='juno'` support. | None |
| Live service config | One — Railway env var `JUNO_SWEEPER_CRON_ENABLED` to be set to `true` AFTER voice UAT. This is operator action, not a phase-execution task. | Document in voice-UAT runbook + ROADMAP success-criteria §3 |
| OS-registered state | None — APScheduler registers in-process at boot; no Windows Task Scheduler / launchd / systemd entries. The advisory lock (1021) is DB-side, already reserved in `JOB_LOCK_IDS`. | None |
| Secrets/env vars | `JUNO_SWEEPER_CRON_ENABLED` is a boolean toggle (not a secret). `JUNO_ANTHROPIC_API_KEY` for billing attribution is already set up per Phase 12; no Phase 15-side action. | None — Phase 12 work |
| Build artifacts | None — no compiled artifacts, no published packages. Railway redeploy picks up new code automatically. | None |

**Nothing found in OS-registered state, secrets, or build artifacts** — verified by review of cron-registration code path (`worker.py`) and absence of any OS-level service registration in the project.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Pre-Phase-9 hardcoded `company_id='seva'` | `scoped_*('juno')` helpers + `Depends(get_current_company)` | Phase 9 (2026-04-xx) | Required pattern for Phase 15 multi-tenant writes |
| Pre-Phase-10 shared `DEFENCE_NEWS_SYSTEM_PROMPT` | Per-domain prompts in `companies/juno/prompts.py` | Phase 10 (2026-05-19) | Phase 15 appends sibling `JUNO_SWEEPER_SYSTEM_PROMPT` to same file |
| Pre-Phase-12 `Anthropic(api_key=...)` direct construction | `get_anthropic_client('juno', timeout=...)` resolver | Phase 12 | Mandatory pattern; grep gate enforces |
| X API v2 1024-char limit assumption (Academic Research tier) | 512-char limit (Standard Basic tier — our actual tier) | n/a (CONTEXT.md error) | Plan-phase MUST cap query at 512 chars |

**Deprecated/outdated:**
- The `@DefenseNews`, `@CDA_CDAI`, `@canadaforces` handles in D-02 — replaced by the corrected handles in §1.
- The "1024 chars" query length claim in CONTEXT.md — replaced by 512 chars (Basic tier).

## Open Questions

1. **D-03 substrate contradiction — how to fix the empty-list problem?**
   - What we know: Phase 10's `raw_sources_jsonb` stores diagnostics, not story arrays. D-03's substrate read returns `[]` for every existing Juno row.
   - What's unclear: Operator preference among the three options (extend Phase 10 / pivot to markdown-parse / defer to v3.2).
   - Recommendation: Plan-phase formally raises this as Decision-1-of-Plan-Phase; default recommendation is "extend Phase 10 to persist story arrays alongside diagnostics" — small footprint, no D-10 violation (Juno-only), unlocks future analytics features.

2. **Should `JUNO_SWEEPER_CRON_ENABLED` flow through Settings or `os.getenv()`?**
   - What we know: Phase 10's analog (`JUNO_CRON_ENABLED`) uses `os.getenv()` direct; CONTEXT.md specifies adding to Settings. Both work.
   - What's unclear: Whether CONTEXT.md is intentional pattern-improvement or transcription drift from Phase 10's actual implementation.
   - Recommendation: Plan-phase picks (b) `os.getenv()` for pattern parity with Phase 10. Minimal footprint. If operator prefers (a) Settings, change is ~5 LOC delta.

3. **First-Sunday-after-deploy empty-virality behavior.**
   - What we know: Per CONTEXT.md `<code_context>` §"Integration Points", the sweeper cron may fire before sufficient daily_summary rows exist to compute meaningful virality. Behavior in that case: `status='partial'` with diagnostic note.
   - What's unclear: Does operator want a manual-fire-first protocol (D-07 step 2) BEFORE flipping the env gate, to avoid an early `'partial'` row landing in production? Yes per D-07; just flagged for tasks awareness.

## Sources

### Primary (HIGH confidence)
- `scheduler/agents/weekly_sweeper.py` — Seva sweeper reference (canonical orchestrator shape, system prompt structure, anti-hallucination + insufficient-signal patterns)
- `scheduler/agents/daily_summary.py:1147-1404` — Phase 10 `run_juno_daily_summary` (per-tenant orchestrator shape, idempotency, status mapping)
- `scheduler/agents/x_ingest.py` — `fetch_top_x_posts` signature + tweepy AsyncClient construction + quota guards
- `scheduler/agents/juno_refusal_detector.py` — refusal-detector + framing-nudge module to reuse verbatim
- `scheduler/companies/juno/prompts.py` — `DEFENCE_NEWS_SYSTEM_PROMPT` (source of verbatim anti-tactical clause for sweeper prompt)
- `scheduler/worker.py:458-480` — `JUNO_CRON_ENABLED` env-gate pattern (verbatim precedent for `JUNO_SWEEPER_CRON_ENABLED`)
- `scheduler/worker.py:108` — `JOB_LOCK_IDS['juno_weekly_sweeper'] = 1021` (already reserved)
- `scheduler/anthropic_client.py` (Phase 12) — `get_anthropic_client('juno', timeout=...)` resolver
- `.planning/phases/14-juno-content-calendar/14-CONTEXT.md` — Phase 14 D-04/D-05 cross-tenant test patterns (mirror)
- `.planning/REQUIREMENTS.md` — JSWEEP-01..06 atomic acceptance criteria
- Anthropic prompt-engineering docs — [Claude Prompting Best Practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices), [XML Tags](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/use-xml-tags)
- [Anthropic announcement of Claude Sonnet 4.6](https://www.anthropic.com/news/claude-sonnet-4-6) — model release date + status (active, not deprecated)
- [Anthropic Models overview](https://platform.claude.com/docs/en/about-claude/models/overview) — `claude-sonnet-4-6` ID confirmed

### Secondary (MEDIUM confidence — verified across multiple sources)
- [X Developer Platform — Build a Query](https://docs.x.com/x-api/posts/search/integrate/build-a-query) — 512-char query limit on Standard/Basic + Core vs Advanced operator distinction
- [Tweepy 4.14.0 AsyncClient docs](https://docs.tweepy.org/en/stable/asyncclient.html) — search_recent_tweets signature + parameter constraints
- [DEV Community — How to search for Tweets about various Topics using Twitter API v2](https://dev.to/suhemparack/how-to-search-for-tweets-about-various-topics-using-the-twitter-api-v2-3p86) — Boolean OR + from: + hashtag combined query examples
- [Twitter Search API: Operators & Code Reference 2026 (GetXAPI)](https://www.getxapi.com/blogs/twitter-advanced-search-operators) — operator availability by tier
- [X Twitter Search Operators: Complete Field Guide 2026 (Jesus Iniesta)](https://jesusiniesta.es/tools/twitter/advanced-search-guide) — Boolean grouping with parentheses
- X handle profile verification (each handle verified by visiting current X profile page via WebSearch results):
  - [RUSI (@RUSI_org)](https://twitter.com/RUSI_org)
  - [CSIS (@CSIS)](https://x.com/CSIS)
  - [IISS News (@IISS_org)](https://x.com/iiss_org)
  - [Defense News (@defense_news)](https://twitter.com/defense_news) — **correction: NOT @DefenseNews**
  - [Breaking Defense (@BreakingDefense)](https://x.com/breakingdefense)
  - [DefenseScoop (@DefenseScoop)](https://x.com/DefenseScoop)
  - [Janes (@JanesINTEL)](https://twitter.com/JanesINTEL) — case-variant
  - [CDA Institute (@CDAInstitute)](https://x.com/cdainstitute) — **correction: NOT @CDA_CDAI**
  - [Canadian Armed Forces (@CanadianForces)](https://twitter.com/canadianforces) — **correction: NOT @canadaforces**
  - [Dave Perry (@DavePerryCGAI)](https://twitter.com/daveperrycgai) — Tier-2 candidate
  - [Murray Brewster (@Murray_Brewster)](https://x.com/murray_brewster) — Tier-2 candidate
  - [CADSI (@CadsiCanada)](https://x.com/cadsicanada) — Tier-2 candidate
  - [National Defence (@NationalDefence)](https://x.com/NationalDefence) — Tier-2 candidate
- [CNBC: Anthropic-Pentagon dispute](https://www.cnbc.com/2026/03/04/pentagon-blacklist-anthropic-defense-tech-claude.html) — content-policy boundary context

### Tertiary (LOW confidence — single source, flagged for validation)
- Claim: X API `from:USERNAME` operator is case-insensitive — based on dev-community thread + Tweepy code reading; NOT explicitly documented in X official docs. Mitigation: use the official handle form (e.g., `JanesINTEL`) for code-readability regardless.
- Claim: "Limit your searches to ≤10 keywords/operators" soft guidance — sourced from community tutorials (medium.com + dev.to), not from X official docs. Mitigation: smoke fire validates; current 13-operand Juno query is within 30% of Seva's existing production query and that's working.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already in production via prior phases; versions verified via CLAUDE.md + Anthropic + Tweepy + X docs.
- Architecture patterns: HIGH — Phase 10 + Phase 7 Seva sweeper + Phase 12 + Phase 14 all provide load-bearing precedent; no new patterns invented.
- X handle verification: HIGH on the 4 corrections (each verified via direct X-profile URL); MEDIUM on Tier-2 candidate quality (signal-quality is judgment-laden).
- tweepy query syntax: HIGH on operator validity + Boolean grouping (cross-verified X docs + Tweepy docs + community tutorials).
- X API quota limits: HIGH on 512-char Basic-tier limit (explicit in X Build-a-Query doc + Tweepy doc + multiple community references). CONTEXT.md's 1024 is a tier-mismatch error.
- Sonnet prompting best practices: MEDIUM — Anthropic-published guidance exists but is not defence-sector-specific; recommendation builds on Phase 10 + Seva sweeper precedent + general Anthropic best practices.
- Substrate-shape contradiction (§3 critical finding): HIGH on the contradiction itself (verified by reading Phase 10 source); MEDIUM on which of the three resolution paths the operator prefers.
- Validation architecture: HIGH — Phase 14 patterns are direct precedent; test framework already present.

**Research date:** 2026-05-20
**Valid until:** ~2026-06-20 (Anthropic / X API / library versions may drift; X handle activity may change [accounts can rebrand, go dormant, or be suspended]).

---

*Phase: 15-juno-weekly-viral-sweeper*
*Research completed: 2026-05-20*
