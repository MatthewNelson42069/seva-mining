---
phase: quick-260419-r0r
plan: 01
subsystem: scheduler/content-agent
tags: [content-agent, prompt-quality, validation, testing]
dependency_graph:
  requires: []
  provides: [long_form 400-char floor enforcement, prompt sharpening for thread/long_form]
  affects: [scheduler/agents/content_agent.py, scheduler/tests/test_content_agent.py]
tech_stack:
  added: []
  patterns: [instance counter for per-run rejection tracking, post-validation guard after LLM parse]
key_files:
  created: []
  modified:
    - scheduler/agents/content_agent.py
    - scheduler/tests/test_content_agent.py
decisions:
  - "400-char floor enforced post-validation (not prompt-only) to catch short posts despite prompt instructions"
  - "Instance attribute _skipped_short_longform (not local var) enables test inspection without caplog"
  - "Thread bullet rewritten to emphasize fact-stringing narrative; long_form bullet rewritten with article-style op-ed framing"
metrics:
  duration: "~10 min"
  completed: "2026-04-19"
  tasks: 2
  files: 2
---

# Quick Task 260419-r0r Summary

**One-liner:** Enforces 400-char hard floor on long_form posts via post-validation guard + instance counter + run-end log, and sharpens thread/long_form format-selection bullets with fact-rich narrative vs article-style analyst op-ed framing.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Prompt update + post-validation + counter + log | f30dd44 | scheduler/agents/content_agent.py |
| 2 | Tests — 400-char floor boundary conditions | 14caedc | scheduler/tests/test_content_agent.py |

## What Was Built

**Task 1 — 6 edits to content_agent.py:**

1. `__init__`: Added `self._skipped_short_longform: int = 0` instance counter
2. Thread bullet (line 1086): Rewritten to emphasize "fact-rich stories where a few data points or facts can be strung together into a narrative"
3. long_form bullet (line 1087): Rewritten with "article-style analysis" framing — short analyst op-ed with thesis, evidence, takeaway; 400-2200 char range with explicit minimum instruction
4. JSON contract for long_form (line 1120): Updated to show `400-2200 chars (minimum 400 required)`
5. Post-validation block: After `key_data_points` assignment, before infographic historical_pattern check — skips bundle + increments counter + returns None if long_form post < 400 chars
6. Run-end log in `_run_pipeline`: Added matching log line after `skipped_by_gate` log

**Task 2 — 4 new tests in test_content_agent.py:**
- `test_long_form_accepted_at_minimum`: 400 chars → returns tuple, counter stays 0
- `test_long_form_accepted_well_above_minimum`: 800 chars → returns tuple, counter stays 0
- `test_long_form_rejected_below_minimum`: 350 chars → returns None, counter = 1
- `test_long_form_boundary_399_chars`: 399 chars → returns None (strict < comparison confirmed), counter = 1

## Verification Results

| Check | Result |
|-------|--------|
| Import check | ok |
| ruff check (scheduler) | 0 errors |
| scheduler pytest | 108 passed (104 + 4 new), 0 failed |
| backend pytest | 71 passed, 5 skipped, 0 failed |
| grep "400" in content_agent.py | 5 matches (>=3 required) |
| grep "_skipped_short_longform" in content_agent.py | 4 matches (>=3 required) |
| grep "skipped_short_longform" in test file | 8 matches |
| grep "article-style analysis" | 1 match |
| grep "fact-rich" | 1 match |

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — all new code paths are fully wired and tested.

## Self-Check: PASSED

- `scheduler/agents/content_agent.py`: FOUND, modified with all 6 edits
- `scheduler/tests/test_content_agent.py`: FOUND, 4 new tests added
- Commit f30dd44: FOUND (Task 1)
- Commit 14caedc: FOUND (Task 2)
- 108 scheduler tests: PASS
- 71 backend tests: PASS
- 0 ruff errors: PASS
