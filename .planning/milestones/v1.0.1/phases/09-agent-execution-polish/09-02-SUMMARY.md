---
phase: 09-agent-execution-polish
plan: "02"
subsystem: infra
tags: [apscheduler, sqlalchemy, config, scheduler, worker]

# Dependency graph
requires:
  - phase: 09-agent-execution-polish
    provides: Plan 01 engagement gate config pattern in seed scripts
provides:
  - DB-driven APScheduler job intervals via 5 config keys read at worker startup
  - Schedule config defaults seeded across agent-owned seed scripts
affects: [scheduler, settings-schedule-tab]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "async_sessionmaker used for one-off DB reads outside request context (worker startup)"
    - "Schedule config keys distributed to seed scripts by agent ownership"

key-files:
  created: []
  modified:
    - scheduler/worker.py
    - scheduler/seed_twitter_data.py
    - scheduler/seed_instagram_data.py
    - scheduler/seed_content_data.py

key-decisions:
  - "expiry_sweep and morning_digest scheduler keys go in seed_content_data.py — scheduler-level concerns closest to content agent (daily cron), avoids new seed file"
  - "build_scheduler changed to async to support await _read_schedule_config(engine) at startup — no impact to APScheduler internals"
  - "_read_schedule_config wraps DB read in try/except — worker must survive DB unavailability at startup (EXEC-04 principle)"

patterns-established:
  - "Schedule config key naming: keys containing 'interval' or 'schedule' are auto-discovered by Settings > Schedule tab"

requirements-completed: [EXEC-02]

# Metrics
duration: 2min
completed: 2026-04-06
---

# Phase 9 Plan 02: DB-Driven APScheduler Intervals Summary

**APScheduler job intervals made configurable via 5 DB config keys read at worker startup, with fallback defaults and Settings > Schedule tab auto-discovery**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-04-06T00:05:28Z
- **Completed:** 2026-04-06T00:07:42Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- `build_scheduler()` is now `async` and reads 5 schedule config keys from DB before registering APScheduler jobs
- `_read_schedule_config()` helper wraps DB session in try/except — falls back to hardcoded defaults if DB unreachable, logs warning per missing key
- 5 config keys seeded across 3 existing seed scripts grouped by agent ownership: `twitter_interval_hours` in twitter seed, `instagram_interval_hours` in instagram seed, `content_agent_schedule_hour` + `expiry_sweep_interval_minutes` + `morning_digest_hour` in content seed
- All 5 key names contain "interval" or "schedule", enabling automatic display in Settings > Schedule tab

## Task Commits

Each task was committed atomically:

1. **Task 1: Make build_scheduler read intervals from DB config** - `5e1fbe2` (feat)
2. **Task 2: Seed schedule interval config keys in existing seed scripts** - `0504d31` (feat)

**Plan metadata:** `(pending — docs commit)`

## Files Created/Modified
- `scheduler/worker.py` - Added `_read_schedule_config()`, changed `build_scheduler()` to async, updated imports and call site
- `scheduler/seed_twitter_data.py` - Added `twitter_interval_hours=2` to CONFIG_DEFAULTS
- `scheduler/seed_instagram_data.py` - Added `instagram_interval_hours=4` to CONFIG_DEFAULTS
- `scheduler/seed_content_data.py` - Added `content_agent_schedule_hour=6`, `expiry_sweep_interval_minutes=30`, `morning_digest_hour=8` to CONFIG_DEFAULTS

## Decisions Made
- `expiry_sweep` and `morning_digest` config keys placed in `seed_content_data.py` — these are scheduler-level concerns with no agent-specific home; content seed is the closest match and avoids creating a new seed file
- `build_scheduler` changed from `def` to `async def` — required to `await _read_schedule_config()`; the APScheduler API is unaffected since `main()` already runs in an async context
- `_read_schedule_config` uses `async_sessionmaker` (not a raw connection) to match SQLAlchemy 2.0 patterns used elsewhere in the scheduler codebase

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Worker startup now reads all 5 schedule intervals from DB before registering jobs
- Settings > Schedule tab will auto-discover and display all 5 keys on next seed run
- Changes take effect on next worker restart (expected and documented behavior per EXEC-02)

---
*Phase: 09-agent-execution-polish*
*Completed: 2026-04-06*
