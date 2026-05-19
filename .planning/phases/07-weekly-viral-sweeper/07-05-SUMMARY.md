---
phase: 07-weekly-viral-sweeper
plan: 05
subsystem: infra
tags: [apscheduler, crontrigger, weekly_sweeper, advisory_lock, scheduler, pytest]

# Dependency graph
requires:
  - phase: 05-foundation-tabs-db-backend-stubs
    provides: JOB_LOCK_IDS["weekly_sweeper"]=1019 reservation in scheduler/worker.py
  - phase: 07-weekly-viral-sweeper
    provides: run_weekly_sweeper orchestrator (Plan 07-04) — lazy-imported by the factory
provides:
  - _make_weekly_sweeper_job(engine) factory mirroring _make_daily_summary_job
  - scheduler.add_job registration in build_scheduler() with CronTrigger(day_of_week='sun', hour=8, minute=0, timezone='America/Los_Angeles')
  - id="weekly_sweeper" job consuming lock 1019, max_instances=1 + misfire_grace_time=1800 inherited from job_defaults
  - 4 new pytest smoke tests + 3 pre-existing assertion bumps (9->10 keys, 2->3 jobs)
affects: [07-06-PLAN, post-Phase-7 production deploy on Railway, weekly Sunday 08:00 PT cron fire]

# Tech tracking
tech-stack:
  added: []  # no new libraries — pure scheduler wiring
  patterns:
    - "Factory + lazy-import pattern: _make_{job}_job(engine) returns inner async def job() that lazy-imports the agent runtime to keep worker.py boot cheap"
    - "Cron registration block ordering: weekly jobs added after daily jobs but before CONTENT_CRON_AGENTS loop (preserves the existing dead-code-loop invariant)"

key-files:
  created: []
  modified:
    - scheduler/worker.py
    - scheduler/tests/test_worker.py

key-decisions:
  - "Reused existing factory pattern verbatim — _make_weekly_sweeper_job is a copy of _make_daily_summary_job with two string swaps (lock name, agent import). No new abstraction introduced."
  - "Did not override max_instances or misfire_grace_time at the per-job level — both are correctly inherited from AsyncIOScheduler(job_defaults={coalesce: True, max_instances: 1, misfire_grace_time: 1800}) at the scheduler level. The plan's must_have 'max_instances=1, misfire_grace_time=1800' is satisfied by the inherited defaults."
  - "Bumped pre-existing job-count assertions (test_retired_crons_absent_from_job_lock_ids 9->10 keys, test_scheduler_registers_2_jobs->3 jobs, test_build_scheduler_omits_v1_sub_agent_crons 2->3) as Rule 3 deviation — these were failing before plan 07-05 due to the Phase 5 dict reservation, but are now correctly aligned with the post-Plan-07-05 state."

patterns-established:
  - "Test acceptance for cron registration: assert via CronTrigger.fields stringified field names — robust to APScheduler internal representation (e.g., day_of_week as 'sun' OR '6'). Pattern reused from test_morning_digest_cron_fires_in_pacific_time."
  - "Worker-suite invariant: any new job registered in build_scheduler() must bump test_retired_crons_absent_from_job_lock_ids (key count + set), test_scheduler_registers_{N}_jobs (count + sorted list), and test_build_scheduler_omits_v1_sub_agent_crons (count + 'must be registered' assertion). Failure to do so produces 3 cascading test failures that look pre-existing but are scope-blocking."

requirements-completed: [SWEEP-03, SWEEP-09]

# Metrics
duration: 4min
completed: 2026-05-19
---

# Phase 7 Plan 05: weekly_sweeper Scheduler Registration Summary

**APScheduler weekly_sweeper job registered: factory `_make_weekly_sweeper_job(engine)` mirrors `_make_daily_summary_job`, fires Sundays 08:00 PT via `CronTrigger(day_of_week='sun', hour=8, minute=0, timezone='America/Los_Angeles')` under advisory lock 1019; 4 new pytest smoke tests + 3 pre-existing job-count assertions updated to reflect 10 lock IDs / 3 registered jobs.**

## Performance

- **Duration:** 4 min
- **Started:** 2026-05-19T05:21:55Z
- **Completed:** 2026-05-19T05:25:08Z
- **Tasks:** 2 (both `type="auto"`, one with `tdd="true"`)
- **Files modified:** 2 (`scheduler/worker.py`, `scheduler/tests/test_worker.py`)

## Accomplishments

- **Scheduler wiring complete.** `weekly_sweeper` job is registered in `build_scheduler()`. On the next Railway deploy of the scheduler service, `python -m agents.weekly_sweeper` ceases to be the only invocation path — the cron will fire automatically every Sunday at 08:00 PT under advisory lock 1019 (reserved in Phase 5 Plan 05-01).
- **Factory mirrors canonical pattern.** `_make_weekly_sweeper_job(engine)` is a verbatim copy of `_make_daily_summary_job` with two string swaps (lock key + agent import). Lazy import of `run_weekly_sweeper` inside the inner `job()` function preserves worker.py boot cost — weekly_sweeper's transitive imports (anthropic, sqlalchemy, weekly_sweeper helpers) don't load until the Sunday job actually fires.
- **OPS-02 uniqueness assertion still passes.** All 10 lock IDs in `JOB_LOCK_IDS` remain distinct; module imports cleanly.
- **Test coverage: 5 targeted tests + 40 full-suite tests + 63 cross-plan tests, all green.** The new smoke tests assert the cron config field-by-field (`day_of_week` in `('sun','6')`, `hour=='8'`, `minute=='0'`, `timezone=='America/Los_Angeles'`).

## Task Commits

Each task was committed atomically:

1. **Task 1: Add `_make_weekly_sweeper_job` factory + scheduler.add_job in build_scheduler()** — `d1b030a` (feat)
2. **Task 2: pytest smoke tests + assertion-count bumps** — `c937020` (test)

_Note: Task 2 was marked `tdd="true"` in the plan. RED step was skipped intentionally — Task 1 had already wired the implementation, so the tests landed against the live factory. This is consistent with the plan's `<action>` block ("APPEND tests to scheduler/tests/test_worker.py") which describes assertions against existing code, not a true RED-GREEN cycle._

## Files Created/Modified

- `scheduler/worker.py` — Added `_make_weekly_sweeper_job(engine)` factory after `_make_daily_summary_prune_job`; added `scheduler.add_job(...)` registration block inside `build_scheduler()` after the `daily_summary_prune` block; updated module-level + `build_scheduler` docstrings from "8 jobs" to "9 jobs" and added the `weekly_sweeper` bullet. (48 insertions, 2 deletions)
- `scheduler/tests/test_worker.py` — Appended 4 new tests (`test_weekly_sweeper_in_job_lock_ids`, `test_job_lock_ids_unique`, `test_make_weekly_sweeper_job_returns_callable`, `test_build_scheduler_registers_weekly_sweeper`); updated 3 pre-existing assertions to reflect the new post-Plan-07-05 state (9->10 keys, 2->3 jobs in two places, plus rename `test_scheduler_registers_2_jobs_after_v1_deregistration` -> `test_scheduler_registers_3_jobs_after_v1_deregistration`). (89 insertions, 11 deletions)

## Decisions Made

- **No new factory abstraction.** Considered extracting a generic `_make_locked_job(engine, lock_key, import_path)` helper to dedupe `_make_daily_summary_job` + `_make_daily_summary_prune_job` + `_make_weekly_sweeper_job`. Rejected: 3 instances of a 12-line factory is not enough to justify an indirection layer, and the lazy-import pattern is more readable when written out per-factory.
- **Inherited job defaults, no per-job overrides.** Plan's must_have specifies `max_instances=1, misfire_grace_time=1800`. These are inherited from `AsyncIOScheduler(job_defaults={...})` at scheduler-level (worker.py:370-377). Per-job overrides would be redundant and create a divergence point if the scheduler-level defaults are tuned later.
- **Test pattern: assert via `trigger.fields` stringified field names.** Matches the existing `test_morning_digest_cron_fires_in_pacific_time` precedent and is robust to APScheduler version churn (day_of_week stringifies as `'sun'` in newer versions, `'6'` in older — the assertion accepts both).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Updated 3 pre-existing test assertions to reflect post-Plan-07-05 state**

- **Found during:** Task 2 (running full test_worker.py suite after appending new tests)
- **Issue:** Three pre-existing tests had hardcoded job-count / key-count assertions that became wrong once weekly_sweeper was registered:
  - `test_retired_crons_absent_from_job_lock_ids` asserted `len(JOB_LOCK_IDS) == 9` — this was already failing before Plan 07-05 began (Phase 5 added `weekly_sweeper: 1019` to the dict but didn't update the assertion). Discovery via `git stash` confirmed pre-existing.
  - `test_scheduler_registers_2_jobs_after_v1_deregistration` (and its body assertion `assert len(jobs) == 2`) — was correct before this plan, broke when we added a 3rd job to `build_scheduler()`.
  - `test_build_scheduler_omits_v1_sub_agent_crons` (assertion `assert len(job_ids) == 2`) — same as above.
- **Fix:** Updated each assertion to reflect the new state (10 lock IDs including `weekly_sweeper`; 3 registered jobs including `weekly_sweeper`). Renamed `test_scheduler_registers_2_jobs_after_v1_deregistration` -> `test_scheduler_registers_3_jobs_after_v1_deregistration` and added `weekly_sweeper` to the expected sorted list. Added `assert "weekly_sweeper" in job_ids` and `"weekly_sweeper"` to the dict-set comparison in the two affected tests. All test docstrings updated to mention Phase 7 Plan 05.
- **Files modified:** `scheduler/tests/test_worker.py`
- **Verification:** Full `pytest tests/test_worker.py` runs 40 tests, all pass. Cross-plan suite (`tests/test_worker.py tests/test_weekly_sweeper.py tests/test_x_ingest.py`) runs 63 tests, all pass.
- **Committed in:** `c937020` (Task 2 commit, alongside the 4 new tests)

---

**Total deviations:** 1 auto-fixed (1 blocking — pre-existing test assertions made stale by the new registration)
**Impact on plan:** Zero scope creep. The deviation IS the plan's effect — registering a new job in `build_scheduler()` necessarily bumps every assertion that counts jobs. Per the plan's acceptance criteria ("Full test_worker.py suite still passes: ... exits 0 (no regression)"), updating these assertions was a hard prerequisite for verification.

## Issues Encountered

None. The plan was executed exactly as written; the 3 assertion bumps were the only deviation and they fall cleanly under Rule 3 (blocking issue, directly caused by the current task's purpose).

## User Setup Required

None. No external service configuration required — the X API bearer token, ANTHROPIC_API_KEY, and DATABASE_URL are already set in the scheduler's Railway env from Phases 1-4. The Sunday 08:00 PT cron fires automatically on the next scheduler deploy.

## Next Phase Readiness

- **Plan 07-06 (frontend wiring) ready to execute.** This plan completes the scheduler half of Phase 7; the orchestrator + cron + persistence layer are all live. The remaining work is the React frontend that reads from `GET /weekly-sweeps` (live since Plan 07-03) and renders the sweep card per D-19/D-20/D-21/D-22.
- **First production fire:** Whichever Sunday 08:00 PT comes after the next Railway deploy of the scheduler service. If the deploy lands after 08:30 PT on a Sunday, the operator can use the manual escape hatch `python -m agents.weekly_sweeper` from a Railway shell (P13, documented in `scheduler/agents/weekly_sweeper.py` module docstring).
- **No blockers.** All Plan 07-05 acceptance criteria satisfied; OPS-02 still holds; cross-plan test suite green.

## Self-Check

**Created files:**
- N/A (no files created — only modifications)

**Modified files:**
- FOUND: `/Users/matthewnelson/seva-mining/scheduler/worker.py`
- FOUND: `/Users/matthewnelson/seva-mining/scheduler/tests/test_worker.py`

**Commits:**
- FOUND: `d1b030a` (Task 1 — feat: register weekly_sweeper cron)
- FOUND: `c937020` (Task 2 — test: 4 new tests + assertion bumps)

## Self-Check: PASSED

---
*Phase: 07-weekly-viral-sweeper*
*Completed: 2026-05-19*
