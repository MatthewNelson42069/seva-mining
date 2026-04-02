---
phase: 05-senior-agent-core
plan: 01
subsystem: scheduler
tags: [foundation, wave-0, twilio, models, migration, tests]
dependency_graph:
  requires:
    - backend/alembic/versions/0003_add_config_table_and_watchlist_platform_user_id.py
    - backend/app/models/daily_digest.py
    - backend/app/services/whatsapp.py
    - scheduler/models/base.py
    - scheduler/config.py
  provides:
    - scheduler/models/daily_digest.py
    - scheduler/services/whatsapp.py
    - scheduler/services/__init__.py
    - backend/alembic/versions/0004_add_engagement_alert_columns.py
    - engagement_alert_level + alerted_expiry_at columns on both DraftItem models
    - 19 collectable pytest stubs for all Senior Agent behaviors
  affects:
    - scheduler/models/draft_item.py
    - backend/app/models/draft_item.py
    - scheduler/pyproject.toml
    - scheduler/uv.lock
tech_stack:
  added:
    - twilio>=9.0 (scheduler dependency)
  patterns:
    - Scheduler-local mirror pattern: same class, different import path (models.base vs app.models.base)
    - Wave 0 test stub pattern: pytest.skip() before lazy import so tests show 'skipped' not 'error'
    - Alembic migration pattern: synchronous upgrade/downgrade, revision chain 0003 -> 0004
key_files:
  created:
    - scheduler/models/daily_digest.py
    - scheduler/services/__init__.py
    - scheduler/services/whatsapp.py
    - backend/alembic/versions/0004_add_engagement_alert_columns.py
    - scheduler/tests/test_senior_agent.py
  modified:
    - scheduler/pyproject.toml (twilio>=9.0 added)
    - scheduler/uv.lock (twilio 9.10.4 resolved)
    - backend/app/models/draft_item.py (engagement_alert_level + alerted_expiry_at)
    - scheduler/models/draft_item.py (engagement_alert_level + alerted_expiry_at)
decisions:
  - pytest.skip() placed before lazy import in Wave 0 stubs — this ensures all 19 tests show as 'skipped' when running with -x rather than failing on ModuleNotFoundError
  - alerted_expiry_at added as a second column in migration 0004 alongside engagement_alert_level, matching the CONTEXT.md recommendation for expiry alert deduplication
metrics:
  duration: ~8 minutes
  completed: 2026-04-02
  tasks_completed: 2
  tasks_total: 2
  files_created: 5
  files_modified: 4
---

# Phase 5 Plan 1: Wave 0 Foundation Summary

**One-liner:** Twilio dep + DailyDigest/WhatsApp scheduler mirrors + Alembic migration 0004 + 19 pytest stubs for all Senior Agent behaviors.

## What Was Done

Wave 0 foundation for the Senior Agent Core phase. This plan establishes all prerequisites so that Waves 1-3 can implement pure business logic against stable types, a test harness, and a database schema.

### Task 1: Foundation files (d7873a6)

**scheduler/pyproject.toml** — Added `"twilio>=9.0"` to the dependencies list. Ran `uv lock` to resolve twilio 9.10.4 (which pulled in aiohttp-retry and pyjwt as transitive deps).

**scheduler/models/daily_digest.py** — Created as a direct mirror of `backend/app/models/daily_digest.py`. The only change is the import path: `from models.base import Base` instead of `from app.models.base import Base`. Columns are identical: id (UUID PK), digest_date (Date, unique), top_stories/queue_snapshot/yesterday_approved/yesterday_rejected/yesterday_expired/priority_alert (all JSONB), whatsapp_sent_at/created_at (DateTime with timezone). Same `ix_daily_digests_digest_date` index.

**scheduler/services/__init__.py** — Created as a single-line comment file.

**scheduler/services/whatsapp.py** — Created as a verbatim mirror of `backend/app/services/whatsapp.py` with one change: `from config import get_settings` instead of `from app.config import get_settings`. All 3 template SIDs preserved exactly. Same `_send_sync` synchronous helper, same `send_whatsapp_template` async function with retry-once behavior on `TwilioRestException`, same logging.

**backend/alembic/versions/0004_add_engagement_alert_columns.py** — Created Alembic migration following the 0003 pattern. `revision = "0004"`, `down_revision = "0003"`. Synchronous `upgrade()` adds two columns to `draft_items`: `engagement_alert_level VARCHAR(20) NULLABLE` (tracks alert state: null/watchlist/viral) and `alerted_expiry_at TIMESTAMPTZ NULLABLE` (expiry alert dedup timestamp). `downgrade()` drops both in reverse order.

**backend/app/models/draft_item.py** and **scheduler/models/draft_item.py** — Added both new columns after `engagement_snapshot`:
- `engagement_alert_level = Column(String(20), nullable=True)` — null/watchlist/viral
- `alerted_expiry_at = Column(DateTime(timezone=True), nullable=True)` — expiry alert dedup

### Task 2: Test stubs (d977797)

**scheduler/tests/test_senior_agent.py** — Created with 19 test stubs covering all Senior Agent behaviors. Each stub:
- Has a descriptive docstring stating the requirement it covers
- Calls `pytest.skip("Wave 0 stub — implementation in Wave N")` as the first line
- Has the lazy `from agents.senior_agent import ...` import AFTER the skip (so tests show as 'skipped' not 'error' in Wave 0)

Test coverage by wave:
- Wave 1 (Plans 02-03): 8 tests — SENR-02 deduplication (4) + SENR-04 queue cap (4)
- Wave 2 (Plan 04): 9 tests — SENR-05/09 expiry sweep (1) + WHAT-02 breaking news/engagement alerts (6) + WHAT-03 expiry alert (2)
- Wave 3 (Plans 05-06): 2 tests — SENR-06/07 morning digest assembly (1) + WHAT-01/05 WhatsApp send (1)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test stub import order to ensure skipped (not errored) status**
- **Found during:** Task 2 validation run with `-x` flag
- **Issue:** Plan's example code placed `from agents.senior_agent import X` before `pytest.skip()`. Since `agents.senior_agent` doesn't exist in Wave 0, every test raised `ModuleNotFoundError` before reaching the skip — making `-x` stop on the first test with FAILED instead of showing 19 skipped.
- **Fix:** Moved `pytest.skip()` to the first line of each test body, placed the lazy import after it with `# noqa: F401`. The import is still inside the function body (satisfying the lazy-import requirement) but is unreachable in Wave 0. When Wave 1 implements the module, the import will be reachable after removing the skip.
- **Files modified:** `scheduler/tests/test_senior_agent.py`
- **Commit:** d977797

## Test Results

```
cd /Users/matthewnelson/seva-mining/scheduler && uv run pytest tests/test_senior_agent.py -x -q
sssssssssssssssssss
19 skipped in 0.01s
```

```
cd /Users/matthewnelson/seva-mining/scheduler && uv run pytest tests/test_senior_agent.py --collect-only -q
...
19 tests collected in 0.00s
```

## Known Stubs

None — this is a foundation plan. The 19 test stubs are intentional Wave 0 placeholders to be implemented in Waves 1-3.

## Commits

| Hash | Message |
|------|---------|
| d7873a6 | feat(05-01): Wave 0 foundation — twilio dep, models, WhatsApp mirror, migration 0004 |
| d977797 | test(05-01): add 19 Wave 0 test stubs for Senior Agent — all collectable and skipped |
