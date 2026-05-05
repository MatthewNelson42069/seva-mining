---
phase: 09-agent-execution-polish
plan: "01"
subsystem: scheduler/agents
tags: [engagement-gate, db-config, exec-02, twitter-agent, instagram-agent]
dependency_graph:
  requires: []
  provides: [DB-driven engagement gate thresholds for Twitter and Instagram]
  affects: [scheduler/agents/twitter_agent.py, scheduler/agents/instagram_agent.py, scheduler/seed_twitter_data.py, scheduler/seed_instagram_data.py]
tech_stack:
  added: []
  patterns: [_get_config DB read pattern, threshold keyword-arg pattern]
key_files:
  created: []
  modified:
    - scheduler/agents/twitter_agent.py
    - scheduler/agents/instagram_agent.py
    - scheduler/seed_twitter_data.py
    - scheduler/seed_instagram_data.py
decisions:
  - "Twitter _get_config returns Optional[Config] (not string), so threshold reads use `int(_cfg.value) if _cfg else default` pattern — consistent with existing quota reads"
  - "Instagram _get_config returns string with default, so threshold reads use `int(await self._get_config(..., '200'))` pattern — consistent with existing config reads in instagram pipeline"
  - "Default parameter values in passes_engagement_gate match previous hardcoded values exactly — existing tests require no changes"
metrics:
  duration: "~8 minutes"
  completed: "2026-04-06T20:46:40Z"
  tasks_completed: 2
  files_modified: 4
---

# Phase 9 Plan 01: DB-Driven Engagement Gate Thresholds Summary

## One-liner

Moved all engagement gate thresholds (6 total: 4 Twitter, 2 Instagram) from hardcoded constants to DB config keys read at the start of each agent run, enabling live tuning from Settings > Scoring without a deploy.

## What Was Built

### Task 1: passes_engagement_gate parameter upgrades + _run_pipeline DB reads

**Twitter Agent (`scheduler/agents/twitter_agent.py`):**
- `passes_engagement_gate` signature extended with four keyword-only threshold params: `min_likes_general=500`, `min_views_general=40000`, `min_likes_watchlist=50`, `min_views_watchlist=5000`
- Function body updated to use parameter names instead of literals in both the watchlist and non-watchlist branches
- `_run_pipeline` reads all four threshold keys from DB immediately after the quota check using the existing `_get_config(session, key)` pattern (returns `Optional[Config]`)
- `logger.info` line logs the resolved thresholds on each run
- `passes_engagement_gate` call in Step 7 updated to pass all four thresholds via keyword args

**Instagram Agent (`scheduler/agents/instagram_agent.py`):**
- `passes_engagement_gate` signature extended with two keyword-only threshold params: `min_likes=200`, `max_post_age_hours=8.0`
- Function body updated to use `min_likes` and `max_post_age_hours` instead of literals
- `_run_pipeline` reads both threshold keys from DB in Step 1b using the existing `_get_config(session, key, default)` string-return pattern
- `logger.info` line logs the resolved thresholds on each run
- `passes_engagement_gate` call in Step 5 updated to pass both thresholds via keyword args

### Task 2: Seed script updates

**Twitter seed (`scheduler/seed_twitter_data.py`):**
- `CONFIG_DEFAULTS` extended with 4 new entries: `twitter_min_likes_general` ("500"), `twitter_min_views_general` ("40000"), `twitter_min_likes_watchlist` ("50"), `twitter_min_views_watchlist` ("5000")

**Instagram seed (`scheduler/seed_instagram_data.py`):**
- `CONFIG_DEFAULTS` extended with 2 new entries: `instagram_min_likes` ("200"), `instagram_max_post_age_hours` ("8")

## Commits

| Task | Commit | Message |
|------|--------|---------|
| 1 | bba9263 | feat(09-01): DB-driven engagement gate thresholds in Twitter and Instagram agents |
| 2 | ed702bd | feat(09-01): seed defaults for engagement gate config keys |

## Verification Results

- `grep -c "min_likes_general|..."` in twitter_agent.py: 25 matches (function sig, docstring, DB reads, call site)
- `grep -c "instagram_min_likes|instagram_max_post_age_hours"` in instagram_agent.py: 2 matches (DB reads)
- `grep -c "twitter_min_likes_general"` in seed_twitter_data.py: 1
- `grep -c "instagram_min_likes"` in seed_instagram_data.py: 1

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — all 6 threshold keys are fully wired from DB config through to the gate check logic.

## Self-Check: PASSED

Files exist:
- FOUND: scheduler/agents/twitter_agent.py
- FOUND: scheduler/agents/instagram_agent.py
- FOUND: scheduler/seed_twitter_data.py
- FOUND: scheduler/seed_instagram_data.py

Commits exist:
- FOUND: bba9263
- FOUND: ed702bd
