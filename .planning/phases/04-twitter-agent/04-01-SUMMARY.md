---
phase: 04-twitter-agent
plan: 01
subsystem: scheduler
tags: [dependencies, models, migration, tests, foundation]
dependency_graph:
  requires: []
  provides:
    - scheduler/models package (DraftItem, AgentRun, Watchlist, Keyword, Config)
    - tweepy[async] + anthropic in scheduler venv
    - Alembic migration 0003 (config table + watchlists.platform_user_id)
    - test stubs for TWIT-01 through TWIT-14
  affects:
    - scheduler/agents/twitter_agent.py (Plans 02-03 implement these)
    - backend database schema (migration adds config table and column)
tech_stack:
  added:
    - tweepy 4.16.0 (with [async] extra — aiohttp, async-lru, oauthlib)
    - anthropic 0.88.0
  patterns:
    - scheduler/models/ mirrors backend/app/models/ with same table names and columns
    - Config model is new (no backend equivalent) — key-value store for quota counter
    - Watchlist model adds platform_user_id not in backend model (new column)
    - Alembic migration follows existing format: sequential string revision IDs
key_files:
  created:
    - scheduler/models/__init__.py
    - scheduler/models/base.py
    - scheduler/models/draft_item.py
    - scheduler/models/agent_run.py
    - scheduler/models/watchlist.py
    - scheduler/models/keyword.py
    - scheduler/models/config.py
    - backend/alembic/versions/0003_add_config_table_and_watchlist_platform_user_id.py
    - scheduler/tests/test_twitter_agent.py
  modified:
    - scheduler/pyproject.toml (added tweepy[async], anthropic)
    - scheduler/uv.lock (regenerated with new deps)
decisions:
  - "tweepy[async] extra required to satisfy tweepy.asynchronous import (needs aiohttp + async-lru)"
  - "Test stubs use per-function lazy imports (_get_twitter_agent) so all 20 tests are collectable even before agent module exists"
  - "Watchlist.platform_user_id placed after account_handle per plan spec — matches migration column order"
metrics:
  duration_minutes: 5
  completed_date: "2026-04-01"
  tasks_completed: 2
  tasks_total: 2
  files_created: 9
  files_modified: 2
---

# Phase 4 Plan 01: Twitter Agent Foundation Summary

**One-liner:** tweepy[async] + anthropic installed in scheduler venv; scheduler models package mirrors all backend DB tables plus new Config model; Alembic migration 0003 adds config table and watchlists.platform_user_id; 20 pytest test stubs cover every TWIT-01 through TWIT-14 requirement.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add dependencies, create scheduler models, write Alembic migration | 7281e67, e1704a4 | scheduler/pyproject.toml, scheduler/models/* (7 files), backend/alembic/versions/0003_* |
| 2 | Create comprehensive test stubs for TWIT-01 through TWIT-14 | ba32f2e | scheduler/tests/test_twitter_agent.py |

## Verification Results

All plan success criteria met:

- `uv sync` succeeded — tweepy 4.16.0 and anthropic 0.88.0 installed with transitive deps
- `from models import DraftItem, AgentRun, Watchlist, Keyword, Config` exits 0
- `import tweepy.asynchronous; import anthropic` exits 0
- `pytest --collect-only` shows 20 tests collected (>= 18 required)
- Migration file `0003_add_config_table_and_watchlist_platform_user_id.py` exists with `op.create_table("config"` and `op.add_column("watchlists"...)`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] tweepy[async] extra required for tweepy.asynchronous import**
- **Found during:** Task 1 verification
- **Issue:** Plan specified `"tweepy>=4.14"` but verification command `import tweepy.asynchronous` requires `aiohttp` and `async-lru` which are only installed via the `[async]` extra
- **Fix:** Changed dependency to `"tweepy[async]>=4.14"` — installs aiohttp 3.13.5, async-lru 2.3.0, and related packages
- **Files modified:** scheduler/pyproject.toml, scheduler/uv.lock
- **Commit:** e1704a4

**2. [Rule 3 - Blocking] Module-level importorskip prevents test collection**
- **Found during:** Task 2 verification
- **Issue:** Using `pytest.importorskip("agents.twitter_agent")` at module level caused 0 tests collected (all skipped) since the module doesn't exist yet, failing the >=18 tests criterion
- **Fix:** Replaced module-level import with `_get_twitter_agent()` helper function using `importlib.import_module` — tests are collected and will fail with ImportError until Plans 02-03 implement the agent (correct Wave 0 behavior)
- **Files modified:** scheduler/tests/test_twitter_agent.py
- **Commit:** ba32f2e

## Known Stubs

None — this plan creates test stubs and infrastructure only. No agent implementation stubs with empty data exist. The test file itself is intentionally expected to fail with ImportError until Plans 02-03 build the agent.

## Self-Check: PASSED
