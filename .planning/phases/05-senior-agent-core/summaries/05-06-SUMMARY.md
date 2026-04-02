---
phase: 05-senior-agent-core
plan: 06
subsystem: scheduler
tags: [wiring, integration, config-seed, worker, twitter-agent, senior-agent, senr-01, senr-03, senr-09]
dependency_graph:
  requires:
    - scheduler/agents/senior_agent.py (SeniorAgent with run_expiry_sweep, run_morning_digest, process_new_item, process_new_items built in Plans 02-05)
    - scheduler/worker.py (JOB_LOCK_IDS 1004/1005, _make_job pattern, main() async entry point)
    - scheduler/agents/twitter_agent.py (_process_drafts persisting DraftItems, _run_pipeline orchestrating)
    - scheduler/models/config.py (Config key-value table)
    - scheduler/database.py (AsyncSessionLocal)
  provides:
    - worker.py: expiry_sweep job wired to SeniorAgent().run_expiry_sweep() (lock 1004)
    - worker.py: morning_digest job wired to SeniorAgent().run_morning_digest() (lock 1005)
    - worker.py: calls seed_senior_config() in main() before scheduler.start()
    - senior_agent.py: seed_senior_config() with 7 default config keys
    - twitter_agent.py: _process_drafts returns new_item_ids (4-tuple); lazy import + process_new_items call after commit
  affects:
    - scheduler/worker.py
    - scheduler/agents/senior_agent.py
    - scheduler/agents/twitter_agent.py
tech_stack:
  added: []
  patterns:
    - Lazy import pattern for cross-agent calls: `from agents.senior_agent import process_new_items` inside function body, not at module level — avoids circular import
    - seed_senior_config() uses AsyncSessionLocal directly; idempotent (only inserts missing rows); called in worker main() before scheduler.start()
    - _process_drafts extended to 4-tuple return (items_queued, items_filtered, errors, new_item_ids) — new_item_ids populated after session.commit()
key_files:
  created: []
  modified:
    - scheduler/worker.py
    - scheduler/agents/senior_agent.py
    - scheduler/agents/twitter_agent.py
decisions:
  - Lazy import for process_new_items inside _run_pipeline rather than module-level to avoid circular imports if SeniorAgent ever imports sub-agent models
  - new_item_ids collected as list of DraftItem objects before commit, IDs extracted after commit (UUIDs populated by SQLAlchemy after flush)
  - seed_senior_config placed as module-level function alongside process_new_items in senior_agent.py for clean exports
  - senior_dedup_lookback_hours included in seed defaults (was in SeniorAgent but not previously in plan's explicit key list)
metrics:
  duration: ~12 minutes
  completed: 2026-04-02
  tasks_completed: 2
  tasks_total: 2
  files_created: 0
  files_modified: 3
---

# Phase 5 Plan 6: Wiring, Integration, and Config Seed Summary

**One-liner:** `worker.py` expiry_sweep and morning_digest jobs wired to `SeniorAgent` methods; `twitter_agent.py` calls `process_new_items` after DraftItem commit (lazy import); `seed_senior_config()` seeds 7 config defaults on worker startup — all 43 tests pass.

## What Was Done

### Task 1: Wire worker.py, integrate Twitter Agent, seed config defaults (27f962b)

**scheduler/worker.py — 3 changes:**

1. Added import: `from agents.senior_agent import SeniorAgent, seed_senior_config`
2. Updated `_make_job()` to handle `expiry_sweep` and `morning_digest` branches:
   - `expiry_sweep` → `SeniorAgent().run_expiry_sweep()` (advisory lock ID 1004)
   - `morning_digest` → `SeniorAgent().run_morning_digest()` (advisory lock ID 1005)
3. Added `await seed_senior_config()` in `main()` before `scheduler.start()`

**scheduler/agents/senior_agent.py — 1 addition:**

Added `async def seed_senior_config() -> None:` as a module-level function alongside `process_new_items`. Seeds 7 defaults if not present:
- `senior_queue_cap`: `"15"`
- `senior_breaking_news_threshold`: `"8.5"`
- `senior_dedup_threshold`: `"0.40"`
- `senior_dedup_lookback_hours`: `"24"`
- `senior_expiry_alert_score_threshold`: `"7.0"`
- `senior_expiry_alert_minutes_before`: `"60"`
- `dashboard_url`: `"https://app.sevamining.com"`

**scheduler/agents/twitter_agent.py — 2 changes:**

1. `_process_drafts()` now returns a 4-tuple `(items_queued, items_filtered, errors, new_item_ids)`. DraftItem objects are accumulated in `new_draft_items` list before commit; IDs are extracted after `session.commit()`.
2. `_run_pipeline()` unpacks the 4-tuple and adds Step 12: lazy import of `process_new_items` + `await process_new_items(new_item_ids)` — only fires when new items were created.

**Test results:**
```
43 passed in 0.54s
(19 senior agent + 20 twitter agent + 4 worker)
```

### Task 2: Human verification checkpoint

Human reviewed and approved on 2026-04-02. All 6 verification items confirmed:

- Full test suite: 43/43 passed, 0 failed (19 senior agent + 20 twitter agent + 4 worker)
- worker.py wiring: expiry_sweep and morning_digest branches use SeniorAgent; seed_senior_config() called in main()
- Twitter Agent integration: process_new_items called in _run_pipeline() after DraftItem commit (lazy import)
- Migration 0004 applied to Neon production: engagement_alert_level and alerted_expiry_at confirmed added
- Both DraftItem models updated: backend/app/models/draft_item.py and scheduler/models/draft_item.py both have the two new columns

## Deviations from Plan

**1. [Rule 2 - Missing Critical Functionality] Added senior_dedup_lookback_hours to seed defaults**

- **Found during:** Task 1 implementation
- **Issue:** Plan explicitly listed 6 config keys to seed. The `senior_dedup_lookback_hours` key is read by `_run_deduplication()` with a fallback of `"24"`, but it was missing from the seed list — any future query of this key would silently use the fallback rather than the seeded value, breaking operator visibility into the configured default.
- **Fix:** Added `"senior_dedup_lookback_hours": "24"` to `seed_senior_config()` defaults (7 total keys seeded).
- **Files modified:** scheduler/agents/senior_agent.py
- **Commit:** 27f962b

## Known Stubs

None — all wiring is fully implemented with real SeniorAgent methods.

## Self-Check: PASSED

Files exist:
- FOUND: /Users/matthewnelson/seva-mining/scheduler/worker.py
- FOUND: /Users/matthewnelson/seva-mining/scheduler/agents/senior_agent.py
- FOUND: /Users/matthewnelson/seva-mining/scheduler/agents/twitter_agent.py

Commits exist:
- FOUND: 27f962b (feat(05-06): wire SeniorAgent jobs, Twitter Agent integration, seed config)
