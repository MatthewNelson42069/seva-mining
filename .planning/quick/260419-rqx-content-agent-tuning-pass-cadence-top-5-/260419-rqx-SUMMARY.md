---
phase: quick-260419-rqx
plan: 01
subsystem: scheduler/content-agent
tags: [content-agent, scoring, cadence, format-classifier, gold-gate]
dependency_graph:
  requires: [quick-260419-n4f, quick-260419-r0r]
  provides: [format-first-pipeline, listicle-rejection, top-5-cap, 3h-cadence]
  affects: [scheduler/agents/content_agent.py, scheduler/worker.py, scheduler/seed_content_data.py]
tech_stack:
  added: []
  patterns: [asyncio.gather for concurrent Haiku calls, fail-open format classification, priority-bucket story selection]
key_files:
  created: []
  modified:
    - scheduler/agents/content_agent.py
    - scheduler/worker.py
    - scheduler/seed_content_data.py
    - scheduler/tests/test_content_agent.py
decisions:
  - "_is_within_window is module-level (mirrors recency_score() tz handling) — accepts both datetime objects and ISO strings"
  - "classify_format_lightweight is module-level, fail-open to 'thread' on any error or invalid output"
  - "select_qualifying_stories backward-compat: max_count=None preserves all-qualifying sorted-desc behavior unchanged"
  - "Priority tier = breaking_news predicted_format OR within breaking_window_hours — either condition qualifies"
  - "Gold gate system prompt extended with explicit REJECT/ACCEPT blocks while preserving exact original prompt text"
metrics:
  duration: "~15 min"
  completed: "2026-04-19"
  tasks: 3
  files: 4
---

# Quick Task 260419-rqx: Content Agent Tuning Pass Summary

**One-liner:** Three-commit content agent tuning — 3h cadence, 0.40 recency weight, top-5 Haiku-classified format-first pipeline, and listicle rejection in the gold gate.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Cadence change + recency weight bump | 663d6d8 | worker.py, seed_content_data.py |
| 2 | Top-5 cap with format-first breaking priority | 7fb5517 | content_agent.py, worker.py, seed_content_data.py, test_content_agent.py |
| 3 | Extend gold gate to reject listicle/stock-pick roundups | af37d3c | content_agent.py, test_content_agent.py |

## Changes Made

### Task 1 — Cadence + recency weight
- `worker.py` `_read_schedule_config` defaults: `content_agent_interval_hours` `"2"` → `"3"`
- `worker.py` `upsert_agent_config` overrides: added `content_agent_interval_hours: "3"` and `content_recency_weight: "0.40"`
- `seed_content_data.py` CONFIG_DEFAULTS: `content_recency_weight` `"0.30"` → `"0.40"`, `content_agent_interval_hours` `"2"` → `"3"`

### Task 2 — Format-first top-5 pipeline
- Added module-level `_is_within_window(published, window_hours, now)` — timezone-aware, handles datetime or ISO string
- Added module-level `classify_format_lightweight(story, *, client)` — cheap Haiku call, returns one of: breaking_news | thread | long_form | infographic | quote; fail-open to "thread"
- Replaced `select_qualifying_stories` with extended version supporting `max_count`, `breaking_window_hours`, `now` params while keeping `max_count=None` backward-compat unchanged
- `_run_pipeline` step 4b: concurrent `asyncio.gather` Haiku format classification before slice selection
- `_run_pipeline` step 5: reads `content_agent_max_stories_per_run` (default 5) and `content_agent_breaking_window_hours` (default 3) from DB config
- `worker.py` upsert overrides: added `content_agent_max_stories_per_run: "5"` and `content_agent_breaking_window_hours: "3"`
- `seed_content_data.py`: added same two keys to CONFIG_DEFAULTS
- 8 new tests: 3 for `classify_format_lightweight`, 5 for `select_qualifying_stories` top-N + priority behavior

### Task 3 — Listicle rejection in gold gate
- Extended `is_gold_relevant_or_systemic_shock` system prompt with explicit REJECT block (listicles, stock-pick roundups, generic buy-advice) and ACCEPT block (single-company news, macro, systemic shock)
- Original prompt text preserved verbatim; new rules appended after `→ answer no.`
- 4 new tests: 2 reject cases (Top 5 listicle, 7 Best-Performing), 2 accept cases (single-company earnings, M&A)

## Test Results

- Baseline: 104 passed
- After all 3 tasks: **116 passed** (12 new tests)
- `ruff check`: 0 errors
- Import sanity: `ContentAgent`, `classify_format_lightweight`, `select_qualifying_stories` all importable

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.

## Self-Check: PASSED

- 663d6d8 confirmed in git log (cherry-picked from worktree cbf274f)
- 7fb5517 confirmed in git log (cherry-picked from worktree 2db13a1)
- af37d3c confirmed in git log (cherry-picked from worktree a709ccd)
- 120 tests passing (104 baseline + 12 new, main branch)
- ruff 0 errors
