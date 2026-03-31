---
phase: 01-infrastructure-and-foundation
plan: "04"
subsystem: database-migrations
tags: [alembic, migrations, postgresql, neon, schema, asyncpg]
dependency_graph:
  requires: [01-03]
  provides: [database-schema, alembic-migration]
  affects: [all-backend-plans]
tech_stack:
  added: [alembic-1.14]
  patterns: [async-alembic-env, op-execute-enum, explicit-migration-no-create-all]
key_files:
  created:
    - backend/alembic.ini
    - backend/alembic/env.py
    - backend/alembic/script.py.mako
    - backend/alembic/README
    - backend/alembic/versions/0001_initial_schema.py
  modified:
    - backend/tests/test_schema.py
    - backend/pyproject.toml
    - backend/uv.lock
decisions:
  - "asyncpg SSL: strip sslmode=require from URL, use ssl=True via connect_args — asyncpg rejects sslmode= as URL param"
  - "pytest fixture scope=function for async engine — module scope causes Future-attached-to-different-loop with asyncio AUTO mode"
metrics:
  duration: "5 minutes"
  completed_date: "2026-03-31"
  tasks_completed: 3
  files_changed: 8
---

# Phase 01 Plan 04: Alembic Initialization and Initial Schema Migration Summary

Alembic initialized with async template, initial migration creates all 6 tables with explicit draftstatus enum creation, applied to Neon — alembic current shows 0001 (head), all 4 test_schema.py tests pass.

## What Was Built

- **Alembic async configuration** (`alembic/env.py`): Imports all 6 models via `import app.models` before setting `target_metadata = Base.metadata`. Reads `DATABASE_URL` from environment (strips `sslmode=require`, passes `ssl=True` via connect_args for asyncpg compatibility). Uses `async_engine_from_config` with `NullPool` for migrations.
- **alembic.ini**: Standard async template with `file_template` set for chronological file naming.
- **Initial migration** (`0001_initial_schema.py`): Creates `draftstatus` PostgreSQL enum via `op.execute()` before the `draft_items` table (Pitfall 1 — enum must exist before table). Creates all 6 tables with JSONB columns. 4 indexes on `draft_items` (status, platform, created_at, expires_at). 3 additional indexes (content_bundles, agent_runs, daily_digests created_at). Downgrade drops tables in reverse dependency order then drops enum.
- **Migration applied to Neon**: `alembic upgrade head` ran successfully — `alembic current` = `0001 (head)`.
- **test_schema.py enabled**: 4 tests implemented — all 4 PASS when DATABASE_URL is set.

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1: Alembic init + env.py | 97b219f | Initialize Alembic with async template and configure env.py |
| Task 2: Initial migration | 8e79ec1 | Write initial schema migration with all 6 tables and draftstatus enum |
| Task 3: Apply migration + tests | f68b879 | Apply migration to Neon and enable test_schema.py tests |

## Verification Results

```
alembic current: 0001 (head)

pytest tests/test_schema.py -v:
  tests/test_schema.py::test_all_tables_exist PASSED
  tests/test_schema.py::test_indexes_exist PASSED
  tests/test_schema.py::test_migration_current PASSED
  tests/test_schema.py::test_draft_status_enum_exists PASSED
  4 passed in 8.91s

Full suite (with DATABASE_URL):
  9 passed, 2 skipped (health endpoint tests require live server)
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] asyncpg rejects sslmode= as URL query parameter**
- **Found during:** Task 3 (first migration attempt)
- **Issue:** `asyncpg` does not accept `sslmode=require` as a URL query param. Throws `TypeError: connect() got an unexpected keyword argument 'sslmode'`.
- **Fix:** Strip `?sslmode=require` from DATABASE_URL in both `env.py` and `test_schema.py`, then pass `connect_args={"ssl": True}` when connecting to Neon (detected by `neon.tech` in hostname).
- **Files modified:** `backend/alembic/env.py`, `backend/tests/test_schema.py`
- **Commit:** f68b879

**2. [Rule 1 - Bug] Module-scoped async engine fixture causes event loop cross-contamination**
- **Found during:** Task 3 (test run)
- **Issue:** `@pytest.fixture(scope="module")` engine fixture shared across tests causes `RuntimeError: Task got Future attached to a different loop` with `asyncio_mode=auto`.
- **Fix:** Changed engine fixture to function scope (no scope argument = default `function`) so each test gets its own engine in its own event loop.
- **Files modified:** `backend/tests/test_schema.py`
- **Commit:** f68b879

## Schema Summary

All 6 tables created in Neon PostgreSQL:

| Table | Key Columns | Indexes |
|-------|-------------|---------|
| draft_items | id (UUID PK), platform, status (draftstatus enum), alternatives (JSONB), engagement_snapshot (JSONB) | status, platform, created_at, expires_at |
| content_bundles | id (UUID PK), story_headline, deep_research (JSONB), draft_content (JSONB) | created_at |
| agent_runs | id (UUID PK), agent_name, errors (JSONB) | agent_name, created_at |
| daily_digests | id (UUID PK), digest_date (unique), top_stories (JSONB), queue_snapshot (JSONB) | digest_date |
| watchlists | id (UUID PK), platform, account_handle | — |
| keywords | id (UUID PK), term, weight | — |

## Known Stubs

None — all tables created with full production schema. No placeholder data or stub implementations.

## Self-Check: PASSED
