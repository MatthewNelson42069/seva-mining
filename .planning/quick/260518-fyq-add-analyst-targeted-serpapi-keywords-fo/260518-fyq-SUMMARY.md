# Quick Task 260518-fyq — Sharpen analyst-content surfacing (3 changes) — SUMMARY

**Shipped:** 2026-05-18
**Branch:** `main` (orchestrator-inline, 2-file edits + tests, single atomic commit)

## Why

User strategic feedback after seeing 4 days of cards (May 15–18) plus pointing at a Bloomberg article (*"Goldman says central banks to step up gold buying, aiding prices"*, May 18) that the system should have caught:

> *"why wouldn't we pull stuff like this?"*

Diagnosed via live DB inspection of the last 6 fires:
- All 6 fires completed cleanly ✓ (ii6 timeout bump working)
- Candidate pool healthy: 84-85 RSS + 77-82 SerpAPI = ~165/fire
- Bullet quality is GOOD — bull-thesis connection is being made
- BUT: zero named-analyst calls visible in the past 4 days of cards
- BUT: heavy M&A coverage (Equinox/Orla) saturated 05-17 fires
- BUT: Goldman article published May 18 didn't appear in the 05-18 15:00 PT card

Three diagnosed gaps:
1. **No analyst-targeted SerpAPI keywords** — current 17 keywords are topic-generic ("gold price", "central bank gold"); none specifically target analyst names or "bank+gold+target" phrases
2. **Sonnet bucketing discretion** — even when an analyst story IS in top-12, Sonnet could bucket it under Top Gold Headlines instead of Analyst & Bank Predictions
3. **TOP_N=12 too tight on heavy news days** — when one big M&A story dominates the pool, lower-but-higher-leverage analyst stories get edged out

## Fix

Three surgical edits across two files.

### #1 — Add 8 analyst-targeted SerpAPI keywords

`scheduler/agents/content_agent.py:SERPAPI_KEYWORDS` (17 → 25):

```diff
+    # quick-260518-fyq — analyst & bank named-target keywords...
+    "Goldman Sachs gold",
+    "JPMorgan gold forecast",
+    "Bank of America gold",
+    "UBS gold target",
+    "Pierre Lassonde",
+    "Peter Schiff gold",
+    "Egon von Greyerz",
+    "World Gold Council central bank",
```

Math: 8 new keywords × 2 fires/day = +480 SerpAPI calls/month. Total now ~1,500/month (was 1,020). User's plan capacity TBD but well within typical Developer-tier ($75/mo for 5,000 searches) and well below their $50/mo cost reality.

### #2 — Bump `GOLD_TOP_N` 12 → 20

`scheduler/agents/daily_summary.py:55`:

```diff
- GOLD_TOP_N = 12        # quick-260512-of1 — bumped from 5 for bull-thesis brief
+ GOLD_TOP_N = 20        # quick-260518-fyq — bumped 12→20; analyst content was getting edged out on heavy M&A days
```

Math: ~67% more prompt input tokens per fire. Cost: ~+$0.30/fire = ~+$18/month. Within budget. Anthropic SDK handles 20 candidates × ~3 KB each = ~60 KB easily.

### #3 — Mandatory tier-1 analyst/bank promotion rule in the Sonnet prompt

`scheduler/agents/daily_summary.py:GOLD_NEWS_SYSTEM_PROMPT` — new rule inserted after the existing Bullet rule:

```
**Tier-1 analyst/bank promotion rule (MANDATORY):** If any supplied story
names one of these analysts or institutions AND makes a specific gold
price target, allocation recommendation, or named catalyst narrative —
that story MUST go into the **Analyst & Bank Predictions** section. Do
NOT bucket it under Top Gold Headlines or Top Macro Headlines, even if
it would also fit there. This is the highest-leverage content type for
the reader and must be surfaced consistently.

Tier-1 list (any of these triggers the promotion rule):
- People: Pierre Lassonde, Peter Schiff, Egon von Greyerz, Matthew
  Piepenburg, Frank Giustra, John Hathaway, Rick Rule, Mike Maloney,
  Jeffrey Gundlach (when on gold)
- Banks: Goldman Sachs, JPMorgan, Bank of America, UBS, Morgan Stanley,
  Citigroup, Deutsche Bank (when issuing a gold target or thesis)
- Authorities: World Gold Council (WGC), IMF (when on gold), BIS (when
  on gold)

Example: a Bloomberg story headlined "Goldman says central banks to
step up gold buying, aiding prices" is a Goldman-named call with a
catalyst (central-bank demand) and an outcome (aiding prices) — it
goes to the **Analyst & Bank Predictions** section as a single entry
like "**Goldman Sachs — central-bank gold buying to step up, aiding
prices** / [2-3 bullets unpacking the mechanism]". It does NOT go
under Top Macro Headlines.
```

The rule includes the actual Bloomberg article you flagged as a worked example. Sonnet's bucketing decisions on that specific story type are now non-discretionary.

## Tests

3 changes across 2 test files:

**`scheduler/tests/test_content_agent.py`:**
- UPDATED `test_serpapi_keywords_constant_preserved` (count assertion 17 → 25)
- UPDATED `test_serpapi_keywords_total_count_and_unique` (count assertion 17 → 25)
- NEW `test_serpapi_keywords_analyst_targeting_quick_260518_fyq` — asserts all 8 new analyst/bank keywords are present

**`scheduler/tests/agents/test_daily_summary.py`:**
- RENAMED `test_build_gold_news_section_top_n_is_12` → `_is_20` (asserts 30 candidates → 20 selected, was 20 → 12)
- NEW `test_gold_news_system_prompt_contains_tier1_promotion_rule` — asserts the new MANDATORY rule, the Tier-1 list, and the Goldman worked example are all in the prompt

Net: scheduler tests 322 → **324** (+2 new).

## Validation

- `cd scheduler && uv run pytest -x` → **324 passed, 1 skipped, 7.01s**
- `cd scheduler && uv run ruff check .` → clean
- Preservation diff outside `content_agent.py` + `daily_summary.py` + their tests: 0 bytes ✓

## Operational impact

**Next 08:00 PT fire (~16 hrs from now):**

- SerpAPI keyword sweep now includes 8 analyst-named queries — Bloomberg/Kitco/MarketWatch articles surfaced when Goldman/JPMorgan/etc. publish a gold target should reach the candidate pool reliably.
- Candidate pool top-N: 20 (was 12) — heavy M&A days no longer edge out analyst stories.
- Sonnet's bucketing: when a tier-1 analyst-named story appears, the prompt forces it into Analyst & Bank Predictions — no more accidental dilution into Top Gold Headlines.

**Expected outcome:**

The Analyst & Bank Predictions section, which has been empty across the past 4 days of cards, should start populating regularly when analyst calls or central-bank actions are in the news. The Bloomberg "Goldman → central banks → gold buying" story type that the user flagged is exactly what this is designed to catch.

**Cost:**
- SerpAPI: +480 calls/month (8 keywords × 60 fires) = ~+10% utilization
- Anthropic: +67% prompt input chars (GOLD_TOP_N 12→20) = +$0.30/fire = +~$18/month
- Total monthly impact: well within the $205-225/month budget

## Out of scope (preserved)

- Ontario Law / Ontario Stats sections — unchanged
- Score floor (6.0), credibility tiers, recency curve, fetch_stories pipeline — unchanged
- Frontend, backend, worker.py — 0-byte diff
- v1.0 dead code — preserved

## Strategic context — the broader content quality picture

This task is the immediate-leverage fix. The remaining gaps from the strategic discussion (Kitco scraping, FRED macro stats, X/Twitter ingestion for gold-analyst accounts) are v2.1 milestone work. The fyq triple-change is the cheapest, highest-leverage improvement available without deeper sourcing work.

**Pipeline state after fyq:**
- ✅ Bull-thesis framing (of1)
- ✅ Bullet-rule (every fact ties back to gold) (oxr)
- ✅ Reliable cron + 60s Sonnet timeout (ii6)
- ✅ Per-section error diagnostics in agent_runs.errors (jny)
- ✅ Analyst-targeted ingestion + mandatory bucketing + bigger candidate pool (fyq)
- 🚧 Live FRED macro stats integration (v2.1)
- 🚧 Kitco scraping for analyst-content factory (v2.1)
- 🚧 Optional X/Twitter ingestion for gold-analyst accounts (v2.1)

## Workflow

`/gsd:quick` default mode — orchestrator-inline. 3 surgical edits across 2 source files, 3 test updates/additions, single atomic commit.
