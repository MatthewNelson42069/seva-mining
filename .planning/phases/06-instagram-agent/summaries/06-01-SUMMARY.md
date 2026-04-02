---
phase: 06-instagram-agent
plan: 01
subsystem: scheduler/tests
tags: [wave-0, test-stubs, apify, instagram]
dependency_graph:
  requires: []
  provides: [test_instagram_agent_stubs, apify_client_dep]
  affects: [06-02-PLAN, 06-03-PLAN, 06-04-PLAN, 06-05-PLAN]
tech_stack:
  added: [apify-client==2.5.0]
  patterns: [pytest.skip-before-lazy-import, wave-0-stub-pattern]
key_files:
  created:
    - scheduler/tests/test_instagram_agent.py
  modified:
    - scheduler/pyproject.toml
    - scheduler/uv.lock
decisions:
  - "Used pytest.skip() before lazy import (not ImportError) so stubs show as SKIPPED not ERROR"
  - "Matched Twitter agent stub pattern but added APIFY_API_TOKEN env var"
  - "Plain def for pure-function tests (scoring/gate/selection); async def for I/O tests"
metrics:
  duration: "~5 minutes"
  completed: "2026-04-02T22:22:29Z"
  tasks_completed: 2
  tasks_total: 2
  files_created: 1
  files_modified: 2
---

# Phase 6 Plan 01: Wave 0 Foundation — Test Stubs and apify-client Dependency

Wave 0 foundation for Phase 6: 15 test stubs covering INST-01 through INST-12 plus `apify-client==2.5.0` installed in the scheduler venv.

## What Was Done

### Task 1: Add apify-client dependency and sync venv

Added `"apify-client==2.5.0"` to `scheduler/pyproject.toml` dependencies after `twilio>=9.0`. Ran `uv sync --all-extras` to install the package and restore dev dependencies (pytest, ruff) that plain `uv sync` had temporarily excluded.

Verification: `uv run python -c "from apify_client import ApifyClientAsync; print('OK')"` prints `OK`.

**Commit:** `c9509cd` — `chore(06-01): add apify-client==2.5.0 dependency`

### Task 2: Create 15 test stubs for Instagram Agent

Created `scheduler/tests/test_instagram_agent.py` with exactly 15 test functions, all using `pytest.skip("Instagram agent not yet implemented")` as the first line of each test body — before the lazy `_get_instagram_agent()` import call. This ensures tests show as SKIPPED (not ERROR) when `agents.instagram_agent` does not yet exist.

**Stub breakdown:**

| Test | Requirement | Sync/Async |
|------|-------------|------------|
| `test_scoring_formula` | INST-02 | sync |
| `test_normalize_followers` | INST-02 | sync |
| `test_engagement_gate` | INST-03 | sync |
| `test_select_top_posts` | INST-04 | sync |
| `test_draft_for_post` | INST-05, INST-06 | async |
| `test_compliance_blocks_hashtags` | INST-06 | async |
| `test_compliance_blocks_seva` | INST-08 | async |
| `test_compliance_fail_safe` | INST-08 | async |
| `test_retry_logic` | INST-09 | async |
| `test_health_check_skip_baseline` | INST-10 | async |
| `test_health_warning_threshold` | INST-10 | async |
| `test_critical_failure_alert` | INST-11 | async |
| `test_no_duplicate_alert` | INST-11 | async |
| `test_scheduler_wiring` | INST-01 | async |
| `test_expiry_12h` | INST-12 | async |

**Commit:** `0c9828f` — `test(06-01): add 15 Wave 0 test stubs for Instagram Agent`

## Test Results

```
platform darwin -- Python 3.12.13, pytest-9.0.2
15 tests, all SKIPPED (pytest.skip before lazy import), 0 errors

Full suite: 43 passed, 15 skipped in 0.58s
```

## Files Created / Modified

| File | Action | Purpose |
|------|--------|---------|
| `scheduler/tests/test_instagram_agent.py` | Created | 15 test stubs, 366 lines |
| `scheduler/pyproject.toml` | Modified | Added `apify-client==2.5.0` to dependencies |
| `scheduler/uv.lock` | Modified | Updated lockfile with apify-client + transitive deps |

## Deviations from Plan

**1. [Rule 3 - Blocking] uv sync removed dev dependencies**

- **Found during:** Task 1 `uv sync`
- **Issue:** Plain `uv sync` (no extras flag) uninstalled pytest, pytest-asyncio, and ruff because the dev group wasn't explicitly requested.
- **Fix:** Ran `uv sync --all-extras` immediately after to restore dev dependencies before proceeding.
- **Files modified:** scheduler/uv.lock (no pyproject.toml change needed)
- **Commit:** included in `c9509cd`

**2. [Rule 1 - Bug] pytest.skip grep count was 17 not 15**

- **Found during:** Task 2 acceptance criteria check
- **Issue:** Module-level docstring and `_get_instagram_agent()` docstring both contained the literal text "pytest.skip" causing `grep -c "pytest.skip"` to return 17 instead of 15.
- **Fix:** Rewrote both docstrings to remove the literal "pytest.skip" reference, keeping description accurate without affecting grep count.
- **Files modified:** scheduler/tests/test_instagram_agent.py

## Known Stubs

This entire plan IS the stub-creation wave. All 15 tests are intentional stubs. They will be filled in by Plans 02-05. No stubs prevent this plan's goal (creating collectable skipping stubs).

## Self-Check: PASSED

- [x] `scheduler/tests/test_instagram_agent.py` exists with 15 test functions
- [x] `grep -c "def test_"` = 15
- [x] `grep -c "pytest.skip"` = 15
- [x] `grep "APIFY_API_TOKEN"` matches
- [x] pytest: 15 skipped, 0 errors
- [x] Full suite: 43 passed, 15 skipped, 0 errors
- [x] Commits c9509cd and 0c9828f exist
