---
phase: quick
plan: 260407-neq
subsystem: scheduler
tags: [content-agent, scheduler, interval, cron-removal]
dependency_graph:
  requires: []
  provides: [content-agent-interval-schedule]
  affects: [scheduler/worker.py, scheduler/seed_content_data.py]
tech_stack:
  added: []
  patterns: [interval-trigger-over-cron]
key_files:
  modified:
    - scheduler/worker.py
    - scheduler/seed_content_data.py
    - scheduler/tests/test_worker.py
decisions:
  - Content agent uses interval trigger (every 2h) matching Twitter agent pattern — no cron time management needed
metrics:
  duration: ~5 minutes
  completed: 2026-04-07
  tasks: 2
  files: 3
---

# Quick Task 260407-neq: Switch Content Agent to Interval Every 2 Hours

**One-liner:** Replaced two cron-based content agent jobs (morning + midday) with a single `trigger="interval"` job firing every 2 hours, matching the Twitter agent pattern.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Rewrite worker.py — remove midday job, add content_agent interval trigger | d84658a | scheduler/worker.py |
| 2 | Update seed_content_data.py and tests; provide DB migration SQL | 8b1e22e | scheduler/seed_content_data.py, scheduler/tests/test_worker.py |

## Changes Made

### scheduler/worker.py
- Removed `"content_agent_midday": 1008` from `JOB_LOCK_IDS`
- Removed `elif job_name == "content_agent_midday":` branch from `_make_job()`
- Replaced `content_agent_schedule_hour` and `content_agent_midday_hour` defaults with `content_agent_interval_hours: "2"` in `_read_schedule_config()`
- Changed `build_scheduler()` content agent job from `trigger="cron"` to `trigger="interval"` with `hours=content_hours`
- Removed `content_agent_midday` `add_job()` block entirely
- Updated logger.info format string and `build_scheduler()` docstring

### scheduler/seed_content_data.py
- Removed `("content_agent_schedule_hour", "14")` and `("content_agent_midday_hour", "20")` from `CONFIG_DEFAULTS`
- Added `("content_agent_interval_hours", "2")` in their place
- Added DB migration SQL block in module docstring (labeled for one-time production run)

### scheduler/tests/test_worker.py
- Updated `test_all_five_jobs_registered`: removed `content_agent_midday` from expected IDs, updated docstring to say 5 jobs
- Renamed `test_build_scheduler_has_6_jobs_no_expiry_sweep` to `test_build_scheduler_has_5_jobs_no_expiry_sweep`; updated `len == 6` to `len == 5`; added `content_agent_midday not in job_ids` assertion
- Added `content_agent_midday_hour not in source` and `content_agent_interval_hours in source` assertions to `test_read_schedule_config_defaults_no_expiry_sweep`

## DB Migration SQL (run once against production)

```sql
-- Remove old content agent cron config keys
DELETE FROM config WHERE key IN ('content_agent_schedule_hour', 'content_agent_midday_hour');

-- Insert new interval config key (skip if already seeded by updated seed script)
INSERT INTO config (key, value) VALUES ('content_agent_interval_hours', '2')
ON CONFLICT (key) DO NOTHING;
```

## Verification

All 7 tests pass:
```
tests/test_worker.py::test_advisory_lock_prevents_duplicate_run PASSED
tests/test_worker.py::test_job_exception_does_not_propagate PASSED
tests/test_worker.py::test_placeholder_job_is_async PASSED
tests/test_worker.py::test_all_five_jobs_registered PASSED
tests/test_worker.py::test_expiry_sweep_removed_from_job_lock_ids PASSED
tests/test_worker.py::test_build_scheduler_has_5_jobs_no_expiry_sweep PASSED
tests/test_worker.py::test_read_schedule_config_defaults_no_expiry_sweep PASSED
7 passed, 1 warning in 0.47s
```

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.

## Self-Check: PASSED

- scheduler/worker.py: exists, no `content_agent_midday` references, `content_agent_interval_hours` present, interval trigger used
- scheduler/seed_content_data.py: exists, `content_agent_interval_hours` present, old keys removed
- scheduler/tests/test_worker.py: exists, all 7 tests pass
- Commits d84658a and 8b1e22e verified in git log
