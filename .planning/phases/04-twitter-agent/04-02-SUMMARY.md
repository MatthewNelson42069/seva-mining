---
phase: 04-twitter-agent
plan: 02
subsystem: scheduler/twitter-agent
tags: [twitter, scoring, fetch-pipeline, quota, tdd, tweepy, anthropic]
dependency_graph:
  requires: [04-01]
  provides: [TwitterAgent-fetch-filter-score-pipeline]
  affects: [scheduler/worker.py, scheduler/tests/test_twitter_agent.py]
tech_stack:
  added: [tweepy[async]>=4.14, anthropic>=0.86.0, aiohttp (tweepy async dep)]
  patterns: [pure-function-scoring, async-db-session, quota-counter-config-table, tdd-red-green]
key_files:
  created:
    - scheduler/agents/twitter_agent.py
    - scheduler/models/__init__.py
    - scheduler/models/base.py
    - scheduler/models/config.py
    - scheduler/models/watchlist.py
    - scheduler/models/keyword.py
    - scheduler/models/agent_run.py
    - scheduler/models/draft_item.py
    - scheduler/tests/test_twitter_agent.py
    - backend/alembic/versions/0003_add_config_table_and_watchlist_platform_user_id.py
  modified:
    - scheduler/pyproject.toml
    - scheduler/uv.lock
decisions:
  - "Pure scoring functions are module-level (not class methods) for direct testability — TwitterAgent methods delegate to them"
  - "tweepy[async] extra installs aiohttp + async_lru needed for AsyncClient"
  - "_check_quota / _set_config / _get_config separated for clean unit testability"
  - "scheduler/models/ mirrors backend/app/models/ at same table schema — scheduler has no access to backend package"
  - "Watchlist.platform_user_id lazily resolved per-run and cached in DB to avoid per-run get_user() calls"
  - "topic filter uses two-step: keyword list first (fast), Claude haiku fallback only for watchlist tweets"
metrics:
  duration_seconds: 426
  completed_date: 2026-04-01
  tasks_completed: 2
  files_created: 12
  tests_passed: 27
---

# Phase 04 Plan 02: Twitter Agent Fetch-Filter-Score Pipeline Summary

**One-liner:** Tweepy AsyncClient fetch pipeline with engagement gate, composite scoring (engagement 40% + authority 30% + relevance 30%), recency decay (full <1h, 50% at 4h, 0 at >=6h), top-N selection, and monthly quota hard-stop against the 10k/month X API cap.

## What Was Built

`scheduler/agents/twitter_agent.py` — the data ingestion half of the Twitter Agent. Contains:

**Exported pure functions (testable without DB/API):**
- `calculate_engagement_score(likes, retweets, replies)` — TWIT-03 formula
- `calculate_composite_score(engagement_norm, authority_norm, relevance_norm)` — TWIT-02 weights
- `apply_recency_decay(score, age_hours)` — TWIT-05 decay curve
- `passes_engagement_gate(likes, views, is_watchlist)` — TWIT-04 AND-gated thresholds
- `select_top_posts(scored_posts, max_count=5)` — TWIT-06 top-N selection

**TwitterAgent class methods:**
- `_check_quota` / `_increment_quota` — monthly counter in config table, hard-stop at 10000-margin (TWIT-11, TWIT-12)
- `_load_watchlist` / `_load_keywords` — DB data loading
- `_fetch_watchlist_tweets` — get_users_tweets() per watchlist account, lazy platform_user_id resolution
- `_fetch_keyword_tweets` — search_recent_tweets() with OR-combined queries, 512-char limit splitting
- `_apply_topic_filter` — keyword match + Claude haiku fallback for watchlist
- `_score_tweet` — authority scoring, composite + recency decay
- `run()` — full pipeline with AgentRun logging and try/except error isolation (EXEC-04)

**Scheduler models package** (`scheduler/models/`): Config, Watchlist (+ platform_user_id), Keyword, AgentRun, DraftItem mirror copies from backend/app/models/.

**Alembic migration 0003**: Creates `config` table (key-value quota store) and adds `watchlists.platform_user_id` column.

## Test Results

27 tests pass across two test groups:

| Group | Tests | Status |
|-------|-------|--------|
| scoring / engagement / recency / gate / top_n | 22 | PASS |
| quota / wiring | 5 | PASS |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Plan 01 prerequisites were not executed**
- **Found during:** Start of Plan 02 execution
- **Issue:** `scheduler/models/`, `scheduler/tests/test_twitter_agent.py`, and tweepy/anthropic dependencies were all missing. Plan 02 depends on Plan 01 (`depends_on: ["04-01"]`) which had not been run.
- **Fix:** Created all Plan 01 artifacts inline: scheduler/models/ package (5 files), test file, Alembic migration, tweepy[async] + anthropic added to pyproject.toml, uv sync run.
- **Files modified:** scheduler/models/ (all files), scheduler/tests/test_twitter_agent.py, scheduler/pyproject.toml, scheduler/uv.lock, backend/alembic/versions/0003_...py
- **Commit:** 2d43532

**2. [Rule 1 - Bug] tweepy[async] extra required instead of tweepy>=4.14**
- **Found during:** Task 1 dependency verification
- **Issue:** `tweepy.asynchronous` requires aiohttp + async_lru which are not installed with base tweepy package. Import fails with "tweepy.asynchronous requires aiohttp, async_lru, and oauthlib to be installed".
- **Fix:** Changed `"tweepy>=4.14"` to `"tweepy[async]>=4.14"` in pyproject.toml.
- **Commit:** 2d43532

**3. [Rule 1 - Bug] test_quota_month_reset mock under-provisioned**
- **Found during:** Task 2 quota test run
- **Issue:** Month-reset path in `_check_quota` calls `_set_config` twice, each of which calls `_get_config` — the test mock's `scalar_one_or_none.side_effect` list ran out (StopIteration).
- **Fix:** Extended mock side_effect list to include 5 entries covering initial reads + reset path reads.
- **Commit:** 2d43532

## Known Stubs

- `run()` pipeline step 10 (drafting) is a `# TODO` comment — Plan 03 wires DraftItem persistence, Claude drafting, and compliance checking.
- TWIT-07 / TWIT-08 / TWIT-09 / TWIT-10 tests in test_twitter_agent.py are `pass` stubs — validated in Plan 03.

## Self-Check: PASSED
