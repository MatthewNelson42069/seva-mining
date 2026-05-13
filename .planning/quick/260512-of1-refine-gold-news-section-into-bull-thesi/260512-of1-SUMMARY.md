---
quick_task: 260512-of1
subsystem: scheduler/agents/daily_summary
tags: [gold-news, prompt-engineering, bull-thesis, constants]
files_modified:
  - scheduler/agents/daily_summary.py
  - scheduler/tests/agents/test_daily_summary.py
decisions:
  - Replaced headline-grouped format (quick-260507-drw) with curated bull-thesis 4-section brief
  - GOLD_TOP_N bumped 5→12 to provide richer source material for the multi-section structure
  - SONNET_MAX_TOKENS bumped 800→1500 because the new structured output is ~2x larger
  - Analyst & Bank Predictions section uses plain ampersand (not HTML-encoded) in prompt and tests
  - Macro Economic Stats references v2.1 for live indicator future work (10Y yield, DXY, CPI, gold/silver ratio)
metrics:
  duration: ~8 minutes
  completed_date: "2026-05-12"
  tasks_completed: 2
  files_changed: 2
  tests_before: 45
  tests_after: 47
  tests_added: 3
  tests_removed: 1
  commit: 0e6072c
---

# Quick Task 260512-of1: Refine Gold News Section into Bull-Thesis Brief — Summary

**One-liner:** Rewrote GOLD_NEWS_SYSTEM_PROMPT from a "1-3 headline-grouped stories" format to a curated 4-section bull-thesis brief with GOLD_TOP_N 5→12 and SONNET_MAX_TOKENS 800→1500.

## Changes Made

### scheduler/agents/daily_summary.py — 3 edits

**Edit 1 (GOLD_TOP_N):** `GOLD_TOP_N = 5` → `GOLD_TOP_N = 12`. The `[:GOLD_TOP_N]` slice in `_build_gold_news_section` already references the constant — no function changes needed. This widens the candidate pool from 5 to 12 to give the multi-section brief richer source material.

**Edit 2 (SONNET_MAX_TOKENS):** `SONNET_MAX_TOKENS = 800` → `SONNET_MAX_TOKENS = 1500`. The new 4-section structured brief is structurally larger than the previous 1-3 headlines format and needs the wider output budget.

**Edit 3 (GOLD_NEWS_SYSTEM_PROMPT):** Complete replacement of the block comment and prompt string. The old "headline-grouped" prompt (quick-260507-drw) produced balanced market commentary; the new prompt is a curated bull-thesis brief with 4 labeled sub-sections:
- `### 🟡 Top Gold Headlines` — direct gold-sector news supporting higher prices
- `### 🌐 Top Macro Headlines (Why It Matters for Gold)` — macro stories supporting gold
- `### 🎯 Analyst & Bank Predictions` — named-analyst/bank calls with price targets (Pierre Lassonde, Peter Schiff, Goldman Sachs prioritized)
- `### 📊 Macro Economic Stats` — embedded numerical macro data (live indicators ship in v2.1)
- `### ⚠️ Bearish Risk to Watch` — optional; include ONLY when clear bearish-for-gold catalyst present

All other constants (`GOLD_SCORE_FLOOR`, `SONNET_MODEL`, `IDEMPOTENCY_WINDOW_MIN`), all functions, all imports, and all Ontario section builders are byte-identical.

### scheduler/tests/agents/test_daily_summary.py — 4 edits (A/B/C/D)

**Edit A:** Replaced `test_build_gold_news_section_top_n_is_5` with `test_build_gold_news_section_top_n_is_12`. New test uses 20 above-floor candidates and asserts `len(raw) == 12`.

**Edit B:** Replaced `test_gold_news_system_prompt_contains_headline_grouped_format` with 4 new tests:
- `test_gold_news_system_prompt_contains_bull_thesis_structure` — asserts all 6 section markers present, no legacy "Why it matters"
- `test_gold_news_system_prompt_contains_analyst_names` — asserts Pierre Lassonde, Peter Schiff, Goldman Sachs
- `test_gold_news_system_prompt_references_v2_1_macro_stats_future_work` — asserts "v2.1" present
- `test_sonnet_max_tokens_is_1500` — asserts `SONNET_MAX_TOKENS == 1500`

**Edit C:** Removed `test_gold_news_system_prompt_no_numbered_headline_prefix` — legacy "Gold headline #" prefix concern no longer applies; new prompt uses `###` markdown headings as section structure.

**Edit D:** Updated `test_build_gold_news_section_filters_by_score_floor` docstring from "selects top 5 stories" to "selects up to GOLD_TOP_N stories with score >= 6.0". Assertion message updated from `"Expected 5 stories in raw"` to `"Expected 5 stories (5 above floor in input)"`. Assertion value `== 5` remains correct (input only has 5 stories above floor, which is less than GOLD_TOP_N=12, so both old and new constant produce the same result for this floor-logic test).

## Test Counts

| Metric | Count |
|--------|-------|
| Tests before | 45 |
| Tests removed | 1 (`test_gold_news_system_prompt_no_numbered_headline_prefix`) |
| Tests added | 3 (`test_build_gold_news_section_top_n_is_12`, `test_gold_news_system_prompt_contains_bull_thesis_structure`, `test_gold_news_system_prompt_contains_analyst_names`, `test_gold_news_system_prompt_references_v2_1_macro_stats_future_work`, `test_sonnet_max_tokens_is_1500` — 4 tests added in Edit B, 1 replaced from Edit A = net +3) |
| Tests after | 47 |
| Pass status | 47/47 PASSED |

Note: Edit B replaced 1 test with 4 tests (net +3). Edit A replaced 1 test with 1 renamed test (net 0). Edit C deleted 1 test (net -1). Total: 45 - 1 + 3 = 47.

## Verification Results

```
pytest -x -q tests/agents/test_daily_summary.py  → 47 passed in 3.35s
ruff check agents/daily_summary.py tests/agents/test_daily_summary.py → All checks passed!
git diff main -- backend/ frontend/ scheduler/agents/content_agent.py scheduler/agents/ontario_law.py scheduler/agents/ontario_stats.py scheduler/worker.py | wc -c → 0
```

Smoke test output:
```
GOLD_TOP_N=12
SONNET_MAX_TOKENS=1500
GOLD_SCORE_FLOOR=6.0
SONNET_MODEL=claude-sonnet-4-6
prompt len=3934 chars
6 markers: True
```

## Commit

`0e6072c` — `feat(quick-260512-of1): bull-thesis brief — GOLD_TOP_N 5→12, SONNET_MAX_TOKENS 800→1500, new 4-section prompt`

## Deviations from Plan

None — plan executed exactly as written.

The prompt length (3,934 chars) is slightly above the plan's "2,500-3,500 char range" estimate. This is expected: the plan noted the range as an approximation. The content (4 labeled sub-sections with formatting rules, named analyst list, and rules block) naturally falls at this length.

## Known Stubs

None. The `Macro Economic Stats` sub-section is intentionally described in the prompt as using "embedded numerical macro data" from supplied stories for v2.0, with live indicators (10Y real yield, DXY, CPI, gold/silver ratio) explicitly deferred to v2.1. This is a planned, documented scope boundary — not a stub that prevents the plan's goal from being achieved.

## Self-Check: PASSED

- `scheduler/agents/daily_summary.py` exists and verified via smoke test
- `scheduler/tests/agents/test_daily_summary.py` exists and all 47 tests pass
- Commit `0e6072c` exists: confirmed by `git rev-parse --short HEAD`
- Zero bytes diff in out-of-scope paths: confirmed
