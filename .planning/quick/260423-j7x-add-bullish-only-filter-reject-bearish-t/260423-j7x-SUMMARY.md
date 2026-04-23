---
phase: quick-260423-j7x
plan: 01
subsystem: content-agent
tags: [content-agent, gold-gate, bearish-filter, haiku, sonnet, gold-media, scheduler]

# Dependency graph
requires:
  - phase: quick-260423-hq7
    provides: "max_count break-after-N semantics — pipeline selects best stories; this plan narrows WHAT is allowed into that pipeline"
  - phase: quick-260422-of3
    provides: "sub_infographics redesign — pipeline correctly operational; this plan is policy-only on top of it"
provides:
  - "Gold gate (is_gold_relevant_or_systemic_shock) rejects bearish-toward-gold stories with reject_reason='bearish_toward_gold'"
  - "content_bearish_filter_enabled config flag (default true) for surgical toggle of bearish-only branch"
  - "gold_media Sonnet drafter quality bar extended with criterion #4 (Bullish or neutral stance)"
  - "Gate 1 prompt internally consistent — KEEP-source preamble scoped to is_gold_relevant=false, not a blanket no-rejection guarantee"
  - "Flat/mixed framing explicitly classified as sentiment=neutral (KEPT) in Gate 1 prompt"
  - "Gate 3 (gold_history) confirmed already safe — no changes needed"
affects: [content-agent, content-init, sub-agents, seed-data]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Gold gate bearish filter: Haiku emits sentiment field; gate rejects when sentiment=bearish and flag on"
    - "Config flag naming: content_bearish_filter_enabled mirrors existing content_gold_gate_enabled pattern"
    - "Prompt consistency: KEEP-source preamble scoped to specific reject_reason axis (is_gold_relevant) to avoid contradicting a separate axis (sentiment)"

key-files:
  created: []
  modified:
    - scheduler/agents/content_agent.py
    - scheduler/agents/content/__init__.py
    - scheduler/seed_content_data.py
    - scheduler/agents/content/gold_media.py
    - scheduler/tests/test_content_agent.py
    - scheduler/tests/test_gold_media.py

key-decisions:
  - "Policy-only approach: bearish filtering implemented at the gate layer (content_agent.py) — no pipeline changes (260422-of3, 260423-hq7 already correct)"
  - "nnh precedence preserved: not_gold → specific_miner → bearish → keep ordering; miner rejection wins before sentiment is evaluated"
  - "Fail-open preserved: malformed JSON and API errors return keep=True with sentiment=None — same behavior as before but new key present"
  - "KEEP-source preamble scoped to is_gold_relevant=false axis only: eliminates Haiku seeing two contradictory rules for Morgan Stanley bearish forecasts"
  - "Flat/mixed framing explicitly neutral: prevents false-positive bearish rejections on everyday 'gold holds steady ahead of Fed decision' wire stories"
  - "Gate 3 (gold_history) confirmed safe by planner pre-read: drama-first historian + curated whitelist already precludes bearish framing — zero changes"
  - "Gate 2 (gold_media): criterion #4 added to user_prompt quality bar only — Sonnet's existing reject JSON path handles self-rejections, no new code logic"

patterns-established:
  - "Bearish filter flag: content_bearish_filter_enabled='false' bypasses ONLY bearish branch; content_gold_gate_enabled='false' still bypasses entire gate"
  - "Return shape widening: adding sentiment key to all return paths (keep/reject) for shape-consistency — callers reading only keep/reject_reason unaffected"

requirements-completed: [J7X-01, J7X-02, J7X-03, J7X-04, J7X-05, J7X-06, J7X-07, J7X-08, J7X-09, J7X-10]

# Metrics
duration: 25min
completed: 2026-04-23
---

# Quick Task 260423-j7x Summary

**Added bullish-only content policy across the 3 drafting gates — gold gate now rejects bearish-toward-gold stories with a new content_bearish_filter_enabled flag; gold_media Sonnet drafter adds Bullish-or-neutral criterion #4; gold_history confirmed already safe. Gate 1 prompt also scope-clarifies the existing KEEP-source preamble (is_gold_relevant vs sentiment) and explicitly classifies flat/mixed framing as neutral.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-04-23T00:00:00Z
- **Completed:** 2026-04-23
- **Tasks:** 3 (TDD: RED / GREEN / GREEN)
- **Files modified:** 6

## Accomplishments

- Gate 1 (Haiku gold gate): extended to emit `sentiment` field and reject `sentiment="bearish"` stories with `reject_reason="bearish_toward_gold"`, gated by `content_bearish_filter_enabled` flag
- Gate 1 prompt made internally consistent: KEEP-source preamble scoped to `is_gold_relevant=false` axis; flat/mixed framing explicitly classified as neutral
- Gate 2 (Sonnet gold_media drafter): criterion #4 "Bullish or neutral stance" added to quality bar — Sonnet self-rejects bearish analyst clips via existing reject JSON path
- Gate 3 (gold_history): confirmed already safe by planner read-through — drama-first historian voice + curated whitelist already precludes bearish framing; zero changes
- 10 new tests (8 gold-gate + 2 gold_media); suite grew 121 → 131 passing
- Zero diff in 5 downstream sub-agent callers and gold_history.py

## What Changed (per-file delta)

### scheduler/agents/content_agent.py
- `is_gold_relevant_or_systemic_shock` docstring: documents new bearish_toward_gold category, sentiment return key, content_bearish_filter_enabled flag
- `_KEEP` sentinel: extended with `"sentiment": None`
- New flag read after existing gold_gate_enabled early-return block (`bearish_enabled_str`, `bearish_filter_on`)
- System prompt: KEEP-source preamble amended — "Their presence does NOT trigger is_gold_relevant=false rejection — but the forecast's direction still determines sentiment (a bearish forecast from Goldman/Morgan Stanley yields sentiment=bearish and is rejected by the bearish filter)."
- System prompt: new REJECT — bearish_toward_gold block with 3 categories, direction-matters clarification, and explicit flat/mixed neutral-framing sentence
- JSON output contract updated: `"sentiment": "bullish"|"neutral"|"bearish"` field added
- Parse block: `sentiment_raw` extracted, validated to (`bullish`|`neutral`|`bearish`|`None`), defensive unknown→None
- Reject returns: `not_gold_relevant` and `primary_subject_is_specific_miner` returns extended with `"sentiment": sentiment`
- New bearish rejection block after specific_miner check, before final keep: `if bearish_filter_on and sentiment == "bearish":`
- Final keep return: `{"keep": True, "reject_reason": None, "company": None, "sentiment": sentiment}` (sentiment propagates)

### scheduler/agents/content/__init__.py
- `gate_config` dict: added `"content_bearish_filter_enabled": "true"` alongside existing `content_gold_gate_enabled` and `content_gold_gate_model`

### scheduler/seed_content_data.py
- `CONFIG_DEFAULTS`: added `("content_bearish_filter_enabled", "true")` after `content_gold_gate_enabled` line

### scheduler/agents/content/gold_media.py
- `_draft_gold_media_caption` user_prompt quality bar: criterion #4 added between criterion 3 and the reject-path line. Header: "Bullish or neutral stance"

### scheduler/tests/test_content_agent.py
- 8 new `@pytest.mark.asyncio` tests: `test_gold_gate_rejects_price_bearish_forecast`, `test_gold_gate_rejects_anti_gold_narrative`, `test_gold_gate_rejects_factual_price_decline`, `test_gold_gate_keeps_bullish_central_bank_buying`, `test_gold_gate_keeps_bullish_price_forecast`, `test_gold_gate_keeps_neutral_record_high`, `test_gold_gate_fail_open_on_parse_error`, `test_gold_gate_flag_disabled`
- `GATE_CONFIG` shared fixture defined at module level

### scheduler/tests/test_gold_media.py
- 2 new tests: `test_draft_rejects_bearish_analyst_clip` (caplog assertion + verbatim inline comment), `test_draft_accepts_bullish_analyst_clip`

## Task Commits

1. **Task 1: Write failing tests for all three gates (RED)** - `1a6bea1` (test)
2. **Task 2: Implement bearish gate + config flag + gate_config propagation + KEEP-source preamble** - `0e758be` (feat)
3. **Task 3: Add criterion #4 to gold_media Sonnet drafter quality bar (GREEN) + full validation** - `b9b8dad` (feat)

## Test Results

| State | Count | Notes |
|-------|-------|-------|
| Baseline (pre-task) | 121/121 | post-hq7 baseline |
| After Task 1 (RED) | 7 failures + 121 pass | 8 gate tests fail; 2 gold_media tests pass (mocked Sonnet) |
| After Task 2 (GREEN) | 131/131 | all gate tests pass, full suite green |
| After Task 3 (GREEN) | 131/131 | no regression; gold_media criterion #4 confirmed via grep |

## Preservation Checks

| Check | Result |
|-------|--------|
| breaking_news.py | Zero diff (git diff HEAD~3) |
| threads.py | Zero diff |
| long_form.py | Zero diff |
| quotes.py | Zero diff |
| infographics.py | Zero diff |
| gold_history.py | Zero diff (Gate 3 confirmed safe) |
| compliance layer (review/check_compliance) | Zero diff — no function signatures touched |
| nnh specific-miner rejection | Preserved — test passes; precedence ordering unchanged |
| Fail-open on JSON parse error | Preserved — `_KEEP` now carries `sentiment=None`, behavior identical |
| Fail-open on API error | Preserved — `return _KEEP` path in except block unchanged |

## Validation Gates (All Green)

- `pytest scheduler/ -q` → 131 passed, 0 failed
- `ruff check scheduler/` → All checks passed!
- `grep -c "bearish_toward_gold" scheduler/agents/content_agent.py` → 3
- `grep -cE "Bullish or neutral" scheduler/agents/content/gold_media.py` → 1
- `grep -n "content_bearish_filter_enabled"` → matches in content_agent.py (L393, L403), content/__init__.py (L219), seed_content_data.py (L50)
- `grep -n "is_gold_relevant=false rejection"` → 1 match (L428) — verbatim preamble amendment present
- `grep -n "gold holds steady"` → 1 match (L456) — verbatim flat/mixed neutral-framing sentence present
- `grep -n "caplog assertion verifies the reject-log code path"` → 1 match (L153) — test #9 inline comment present verbatim

## Decisions Honored

1. **Config-flag pattern mirrors content_gold_gate_enabled**: `content_bearish_filter_enabled` follows identical "false"/"0"/"no" parsing; hardcoded "true" in gate_config mirrors existing approach
2. **nnh precedence preserved**: reject ordering is not_gold → specific_miner → bearish → keep; B2Gold story still rejects as `primary_subject_is_specific_miner`, not `bearish_toward_gold`
3. **Zero-diff in callers**: 5 downstream sub-agents + gold_history have zero diff across all 3 commits of this plan
4. **Prompt internal consistency**: KEEP-source preamble scoped to `is_gold_relevant=false` axis only — Goldman/MS as SOURCE citation still doesn't trigger `is_gold_relevant=false`; but forecast direction independently evaluated as `sentiment`
5. **Flat/mixed framing explicitly neutral**: "gold holds steady", "gold flat", "gold mixed" → sentiment=neutral → KEPT; eliminates silent gap that could cause false-positive bearish rejections on everyday wire copy
6. **Gate 3 no-change**: gold_history confirmed safe by planner pre-read; drama-first historian + whitelist already precludes bearish framing; no prompt guard needed

## Next Observable Step

Monday's 12:00 PT `sub_infographics` cron — confirm no bearish stories reach the approval queue. Any Morgan-Stanley-style forecast cut should appear in scheduler/worker logs with `reject_reason="bearish_toward_gold"` at INFO level. The `sub_infographics` story that triggered this task ("Morgan Stanley cuts gold price forecast by almost 10%", score 8.5) will now be silenced at Gate 1 and never reach any drafter.

## Self-Check: PASSED

All modified files verified present. All 3 commits (1a6bea1, 0e758be, b9b8dad) confirmed in git history.
