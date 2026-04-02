---
phase: 06-instagram-agent
plan: 02
subsystem: scheduler/agents
tags: [tdd, scoring, engagement-gate, apify, instagram, wave-1]
dependency_graph:
  requires: [06-01]
  provides: [instagram_agent_scoring, instagram_agent_skeleton]
  affects: [06-03-PLAN, 06-04-PLAN, 06-05-PLAN]
tech_stack:
  added: []
  patterns: [module-level-pure-functions, tdd-red-green, apify-async-client, log10-normalization]
key_files:
  created:
    - scheduler/agents/instagram_agent.py
  modified:
    - scheduler/tests/test_instagram_agent.py
decisions:
  - "passes_engagement_gate accepts (likes, created_at) datetime signature matching test stubs, not post_age_hours float"
  - "select_top_posts named without 'instagram_' prefix to match existing test stub calls"
  - "Module-level pure functions (not class methods) for direct testability via module object"
  - "InstagramAgent._run_pipeline() uses passes_engagement_gate internally with datetime conversion from Apify timestamp strings"
metrics:
  duration: "~10 minutes"
  completed: "2026-04-02T22:25:53Z"
  tasks_completed: 1
  tasks_total: 1
  files_created: 1
  files_modified: 1
---

# Phase 6 Plan 02: Scoring Functions and InstagramAgent Skeleton Summary

TDD implementation of Instagram scoring formula, follower normalization, engagement gate, top-N selection, and InstagramAgent class skeleton with Apify fetch pipeline. 4 test stubs converted from SKIPPED to PASSED; 11 remaining stubs stay SKIPPED.

## What Was Done

### Task 1: TDD — Scoring functions and engagement gate

**RED phase:** Removed `pytest.skip()` guards from 4 test stubs (`test_scoring_formula`, `test_normalize_followers`, `test_engagement_gate`, `test_select_top_posts`). All 4 failed with `ModuleNotFoundError: No module named 'agents.instagram_agent'`.

**Commit:** `514944f` — `test(06-02): add failing tests for scoring and engagement gate`

**GREEN phase:** Created `scheduler/agents/instagram_agent.py` (275 lines, 15 function/method definitions) with:

**Pure scoring functions (module-level):**
- `normalize_followers(n)` — `min(log10(max(n,1)) / log10(1_000_000), 1.0)`, returns 0.0 for n <= 0
- `calculate_instagram_score(likes, comment_count, follower_count)` — `likes*1 + comment_count*2 + normalize_followers(follower_count)*1.5`
- `passes_engagement_gate(likes, created_at)` — 200+ likes AND datetime within 8h (strict `< 8.0`)
- `select_top_posts(scored_posts, top_n=3)` — sort descending by "score" key, return top N

**InstagramAgent class skeleton:**
- `run()` — async entry point matching APScheduler call pattern; wraps pipeline in AgentRun logging
- `_run_pipeline()` — loads config, fetches hashtags and accounts in parallel via `asyncio.gather`, deduplicates by `shortCode`, applies engagement gate (converting Apify `timestamp` strings to datetime), scores qualifying posts, selects top N
- `_get_config()`, `_load_keywords()`, `_load_watchlist()` — mirrors twitter_agent.py patterns exactly
- `_fetch_hashtag_posts()`, `_fetch_account_posts()` — Apify directUrls input schema, 24h lookback
- `_call_apify_actor()` — calls `apify/instagram-scraper`, returns dataset items
- `_deduplicate_posts()` — deduplication by `shortCode` set

**Commit:** `530eafe` — `feat(06-02): implement scoring functions and InstagramAgent skeleton`

## Test Results

```
4 passed, 11 skipped, 0 errors
Full suite: 47 passed, 11 skipped in 0.37s
```

All 4 target tests pass:
- `test_normalize_followers` — 0 → 0.0, 1000 → ~0.5, 1M → 1.0
- `test_scoring_formula` — returns float > 0 with correct formula
- `test_engagement_gate` — 200/recent = pass; 199/recent = fail; 200/9h-old = fail
- `test_select_top_posts` — top 3 from 5, sorted descending (9.5, 8.1, 7.2)

## Deviations from Plan

**1. [Rule 1 - Bug] Function signatures match test stubs, not plan spec**

- **Found during:** RED phase — reading test stubs before writing implementation
- **Issue:** Plan's `<action>` block specifies `passes_instagram_engagement_gate(likes, post_age_hours)` but the Wave 0 test stub (Plan 01) calls `passes_engagement_gate(likes, created_at=datetime)`. Similarly, plan specifies `select_top_instagram_posts` but stub calls `select_top_posts`.
- **Fix:** Implemented functions with signatures matching the existing test stubs, which are the authoritative test spec. `passes_engagement_gate` accepts a timezone-aware datetime and computes age internally. `select_top_posts` uses the shorter name.
- **Impact:** Zero — tests pass, behavior is correct per INST-03/INST-04 requirements.
- **Files modified:** scheduler/agents/instagram_agent.py

## Known Stubs

None in the scoring/gate/selection functions — all are fully implemented.

The `_run_pipeline()` method stub note: Steps 7-9 (draft, compliance, persist) are intentionally deferred to Plan 03, and Step 10 (health monitoring) to Plan 04. These are explicitly commented in the code and are not stubs blocking Plan 02's goal.

## Self-Check: PASSED

- [x] `scheduler/agents/instagram_agent.py` exists (275 lines, > 180 min)
- [x] `grep "def normalize_followers"` matches
- [x] `grep "def calculate_instagram_score"` matches
- [x] `grep "def passes_engagement_gate"` matches
- [x] `grep "def select_top_posts"` matches
- [x] `grep "class InstagramAgent"` matches
- [x] `grep "from apify_client import ApifyClientAsync"` matches
- [x] 4 tests pass: test_scoring_formula, test_normalize_followers, test_engagement_gate, test_select_top_posts
- [x] 11 remaining stubs SKIPPED (not ERROR)
- [x] Full suite: 47 passed, 11 skipped, 0 errors
- [x] Commits 514944f (RED) and 530eafe (GREEN) exist
