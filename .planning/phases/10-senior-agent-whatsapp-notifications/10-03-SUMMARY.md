---
phase: 10-senior-agent-whatsapp-notifications
plan: "03"
subsystem: notifications
tags: [twilio, whatsapp, python, apscheduler, senior-agent]

# Dependency graph
requires:
  - phase: 10-01
    provides: send_whatsapp_message() free-form WhatsApp sender
provides:
  - worker.py with expiry_sweep removed (6 jobs, not 7)
  - seed_content_data.py with morning_digest_schedule_hour="15" (7am PST)
  - senior_agent.py run_morning_digest() uses send_whatsapp_message() with try/except guard
  - All send_whatsapp_template() callers in senior_agent.py and instagram_agent.py updated
affects:
  - railway-deployment (scheduler worker now logs 6 jobs at startup)
  - morning-digest-scheduling (DB value should be updated to 15 for live environment)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Inner try/except around WhatsApp send in run_morning_digest — failure is non-fatal, DailyDigest record still committed"
    - "Free-form digest message format: date + queue total + yesterday stats + top stories + dashboard URL"

key-files:
  created: []
  modified:
    - scheduler/worker.py
    - scheduler/seed_content_data.py
    - scheduler/agents/senior_agent.py
    - scheduler/agents/instagram_agent.py
    - scheduler/tests/test_worker.py
    - scheduler/tests/test_senior_agent.py
    - scheduler/tests/test_instagram_agent.py

key-decisions:
  - "Phase 10-03: expiry_sweep removed from JOB_LOCK_IDS and build_scheduler() — run_expiry_sweep() preserved in SeniorAgent class but no longer scheduled; lock ID 1004 retired"
  - "Phase 10-03: morning_digest_schedule_hour seed default changed from 8 to 15 (15:00 UTC = 7am PST); existing DB rows require manual SQL UPDATE"
  - "Phase 10-03: WhatsApp send in run_morning_digest wrapped in inner try/except — failure is non-fatal; DailyDigest record and run.status=completed proceed regardless"

patterns-established:
  - "Non-fatal WhatsApp pattern: wrap await send_whatsapp_message() in try/except, log warning, continue — do not propagate to outer exception handler"

requirements-completed:
  - WHAT-01
  - WHAT-02

# Metrics
duration: 15min
completed: 2026-04-07
---

# Phase 10 Plan 03: Senior Agent WhatsApp Notifications Summary

**expiry_sweep removed from scheduler, morning digest rewritten to use send_whatsapp_message() with non-fatal failure guard, 82 tests passing**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-04-07T23:10:00Z
- **Completed:** 2026-04-07T23:25:00Z
- **Tasks:** 2 (TDD: RED + GREEN for each task)
- **Files modified:** 7

## Accomplishments

- Removed `expiry_sweep` from `JOB_LOCK_IDS` and `build_scheduler()` in worker.py — scheduler now registers 6 jobs
- Removed `expiry_sweep_interval_minutes` from `_read_schedule_config` defaults
- Changed `morning_digest_schedule_hour` seed default from `"8"` to `"15"` (15:00 UTC = 7am PST)
- Rewrote `run_morning_digest()` to use `send_whatsapp_message()` with a free-form digest text
- Wrapped WhatsApp send in inner try/except — WhatsApp failure no longer aborts DailyDigest commit
- Removed `whatsapp_sent_at` timestamp update from outer scope (moved inside try so only set on success)
- Updated all 4 remaining `send_whatsapp_template()` callers in senior_agent.py to use free-form messages
- Fixed instagram_agent.py critical failure alert (also calling removed `send_whatsapp_template`)
- Updated all test mocks: replaced `send_whatsapp_template` patches with `send_whatsapp_message` across 3 test files

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED tests):** `1555efb` — test(10-03): add failing tests for expiry_sweep removal from worker
2. **Task 1 (GREEN impl):** `de3f4cf` — feat(10-03): remove expiry_sweep from worker, update seed to 15:00 UTC
3. **Task 2 (RED+GREEN tests):** `271c4d8` — test(10-03): add and update morning_digest WhatsApp tests
4. **Task 2 (GREEN impl):** `ba26e66` — feat(10-03): update senior_agent.py to use send_whatsapp_message()
5. **Rule 3 fix:** `6221e05` — fix(10-03): update instagram_agent.py critical failure alert

## Files Created/Modified

- `scheduler/worker.py` — expiry_sweep removed from JOB_LOCK_IDS, _read_schedule_config defaults, build_scheduler()
- `scheduler/seed_content_data.py` — morning_digest_schedule_hour changed to "15", expiry_sweep entry removed
- `scheduler/agents/senior_agent.py` — import updated, run_morning_digest() rewritten, all 4 send_whatsapp_template() calls updated
- `scheduler/agents/instagram_agent.py` — critical failure alert updated to use send_whatsapp_message()
- `scheduler/tests/test_worker.py` — existing test updated (6 jobs not 7), 3 new expiry_sweep tests added
- `scheduler/tests/test_senior_agent.py` — 2 new morning digest tests, all existing send_whatsapp_template mocks updated
- `scheduler/tests/test_instagram_agent.py` — 2 tests updated to mock send_whatsapp_message

## Decisions Made

- Phase 10-03: expiry_sweep removed from scheduler. run_expiry_sweep() preserved in SeniorAgent class for manual use if needed. Lock ID 1004 is retired.
- Phase 10-03: morning_digest_schedule_hour seed default changed from 8 to 15 (15:00 UTC = 7am PST). Note: seed is idempotent — existing DB rows NOT overwritten. Manual SQL UPDATE required for live Railway environment.
- Phase 10-03: WhatsApp send in run_morning_digest() wrapped in inner try/except (non-fatal). Digest record and run.status=completed are not affected by Twilio failures.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] instagram_agent.py still called removed send_whatsapp_template**
- **Found during:** Task 2 verification (full test suite run)
- **Issue:** `instagram_agent.py` line 243 imported and called `send_whatsapp_template("breaking_news", {...})` for critical failure alerts. This function was removed in plan 10-01.
- **Fix:** Updated to `send_whatsapp_message(f"Instagram scraper failure — ... ")` with free-form text
- **Files modified:** `scheduler/agents/instagram_agent.py`, `scheduler/tests/test_instagram_agent.py`
- **Commit:** `6221e05`

**2. [Rule 1 - Bug] Existing test_senior_agent.py tests mocked removed send_whatsapp_template**
- **Found during:** Task 2 verification
- **Issue:** 9 tests in test_senior_agent.py still patched `agents.senior_agent.send_whatsapp_template` which no longer exists — AttributeError on collection
- **Fix:** All mock patches updated to `send_whatsapp_message`; assertions updated to check message string content instead of template name/variables dict
- **Files modified:** `scheduler/tests/test_senior_agent.py`
- **Commit:** `271c4d8`

**3. [Rule 3 - Blocking] test_worker.py existing test expected 7 jobs including expiry_sweep**
- **Found during:** Task 1 GREEN verification
- **Issue:** `test_all_five_jobs_registered` asserted `expected_ids` containing `"expiry_sweep"`, failing after removal
- **Fix:** Updated expected_ids to 6 jobs without expiry_sweep
- **Files modified:** `scheduler/tests/test_worker.py`
- **Commit:** `de3f4cf`

## Known Stubs

None — all code paths are fully implemented.

## Checkpoint

This plan ends at a human-verify checkpoint. The following manual steps are required before production use:

1. Run: `python -m pytest tests/ -v` — confirm 82 tests pass
2. Confirm `grep "expiry_sweep" scheduler/worker.py` returns only comments
3. Confirm `grep "morning_digest_schedule_hour" scheduler/seed_content_data.py` shows `"15"`
4. Run SQL against Neon DB: `UPDATE config SET value = '15' WHERE key = 'morning_digest_schedule_hour';`
5. Deploy to Railway and verify scheduler startup logs show "6 jobs registered" and "digest=cron(15:00 UTC)"
6. Optional: test end-to-end WhatsApp delivery via Twilio sandbox

## Self-Check

- [x] `scheduler/worker.py` has no `expiry_sweep` in JOB_LOCK_IDS or build_scheduler() code
- [x] `scheduler/seed_content_data.py` has `morning_digest_schedule_hour = "15"` and no expiry_sweep entry
- [x] `scheduler/agents/senior_agent.py` imports `send_whatsapp_message` (not `send_whatsapp_template`)
- [x] `scheduler/agents/senior_agent.py` `run_morning_digest()` uses free-form message with try/except
- [x] Commit `1555efb` exists (RED: worker tests)
- [x] Commit `de3f4cf` exists (GREEN: worker implementation)
- [x] Commit `271c4d8` exists (tests update)
- [x] Commit `ba26e66` exists (senior_agent implementation)
- [x] Commit `6221e05` exists (instagram_agent fix)
- [x] 82 tests pass, 0 failures

## Self-Check: PASSED

---
*Phase: 10-senior-agent-whatsapp-notifications*
*Completed: 2026-04-07*
