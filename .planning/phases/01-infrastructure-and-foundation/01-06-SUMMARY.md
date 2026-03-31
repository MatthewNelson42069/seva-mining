---
phase: 01-infrastructure-and-foundation
plan: 06
subsystem: scheduler
tags: [apscheduler, advisory-lock, postgresql, railway, worker, async]
dependency_graph:
  requires: [01-04]
  provides: [scheduler-worker-skeleton]
  affects: [phases-4-7-agent-wiring]
tech_stack:
  added: [apscheduler==3.11.2]
  patterns: [postgresql-advisory-lock, asyncio-scheduler, placeholder-jobs]
key_files:
  created:
    - scheduler/worker.py
    - scheduler/Dockerfile
    - scheduler/railway.toml
    - scheduler/.dockerignore
    - scheduler/agents/__init__.py
  modified:
    - scheduler/tests/test_worker.py
decisions:
  - "APScheduler 3.11.2 AsyncIOScheduler — v4 alpha has breaking API changes (D-12)"
  - "PostgreSQL advisory locks as defense-in-depth against duplicate job execution (D-13)"
  - "numReplicas=1 in railway.toml is primary prevention; advisory lock is secondary (D-13)"
  - "5 placeholder async jobs — real agent logic wired in Phases 4-7 (D-14)"
  - "JOB_LOCK_IDS as stable integer constants — never reuse across jobs"
metrics:
  duration_minutes: 3
  completed_date: "2026-03-31"
  tasks_completed: 2
  files_created: 5
  files_modified: 1
---

# Phase 1 Plan 06: APScheduler Worker Skeleton Summary

APScheduler 3.11.2 AsyncIOScheduler worker with PostgreSQL advisory locks (pg_try_advisory_lock/pg_advisory_unlock), 5 async placeholder jobs, EXEC-04 error isolation, and Railway single-replica deployment config.

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| 1 | Create scheduler/worker.py with advisory lock and enable test_worker.py (TDD) | ba5f2d1 |
| 2 | Write scheduler Dockerfile and railway.toml | 9345453 |

## What Was Built

### scheduler/worker.py

- `JOB_LOCK_IDS`: stable integer lock constants (1001-1005) — never reused across jobs
- `with_advisory_lock()`: acquires pg_try_advisory_lock, skips job if lock held, catches all exceptions without re-raising (EXEC-04), releases lock in finally block
- `placeholder_job()`: async coroutine satisfying EXEC-03 (all agent functions are async)
- `_make_job()`: factory that wraps placeholder_job with advisory lock per APScheduler callback
- `build_scheduler()`: configures AsyncIOScheduler with 5 jobs matching D-14 schedule
- `main()`: entry point — creates engine (pool_size=2), starts scheduler, blocks on Event

### Job Schedule (D-14)

| Job | Trigger | Schedule |
|-----|---------|----------|
| content_agent | cron | Daily at 6:00 AM |
| twitter_agent | interval | Every 2 hours |
| instagram_agent | interval | Every 4 hours |
| expiry_sweep | interval | Every 30 minutes |
| morning_digest | cron | Daily at 8:00 AM |

### scheduler/Dockerfile

- Base: python:3.12-slim
- Installs uv, syncs production deps (no dev), copies source files
- CMD: `uv run python worker.py`
- No EXPOSE — worker has no HTTP port

### scheduler/railway.toml

- `numReplicas = 1` with CRITICAL comment — primary prevention against duplicate schedulers
- `restartPolicyType = "ON_FAILURE"`, `restartPolicyMaxRetries = 5`
- No healthcheckPath — Railway monitors via process status

### scheduler/agents/__init__.py

Empty placeholder directory — Phase 4-7 will add actual agent modules here.

## Tests

test_worker.py: 4 PASSED, 0 FAILED

| Test | Coverage |
|------|----------|
| test_advisory_lock_prevents_duplicate_run | INFRA-05: lock held → job_fn not called |
| test_job_exception_does_not_propagate | EXEC-04: exception caught, lock released, no re-raise |
| test_placeholder_job_is_async | EXEC-03: coroutine function |
| test_all_five_jobs_registered | INFRA-05: all 5 job IDs registered |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test shutdown guard for non-running scheduler**
- **Found during:** Task 1 TDD GREEN phase
- **Issue:** `test_all_five_jobs_registered` called `scheduler.shutdown()` on a scheduler that was built but never started, raising `SchedulerNotRunningError`
- **Fix:** Added `if scheduler.running:` guard before shutdown call in test
- **Files modified:** scheduler/tests/test_worker.py
- **Commit:** ba5f2d1

## Known Stubs

- `scheduler/worker.py`: All 5 job functions call `placeholder_job()` — these are intentional stubs. Real agent logic (Twitter, Instagram, Content, Senior agents) will be wired in Phases 4-7 per D-14.

## Self-Check: PASSED
