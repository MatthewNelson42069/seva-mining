---
phase: 02-fastapi-backend
plan: 03
subsystem: backend-api
tags: [fastapi, crud, watchlists, keywords, agent-runs, digests, content, auth]
dependency_graph:
  requires: ["02-01"]
  provides: ["watchlist-crud-endpoints", "keyword-crud-endpoints", "agent-runs-endpoint", "digests-endpoint", "content-today-endpoint"]
  affects: ["03-react-dashboard"]
tech_stack:
  added: []
  patterns: ["APIRouter with router-level dependencies", "model_dump(exclude_unset=True) for partial updates", "SQLite-compatible test fixtures for JSONB models"]
key_files:
  created:
    - backend/app/routers/watchlists.py
    - backend/app/routers/keywords.py
    - backend/app/routers/agent_runs.py
    - backend/app/routers/digests.py
    - backend/app/routers/content.py
    - backend/tests/test_crud_endpoints.py
  modified:
    - backend/app/main.py
decisions:
  - "Router-level auth dependency via dependencies=[Depends(get_current_user)] — cleaner than per-route decoration"
  - "SQLite-compatible test models with JSON type instead of JSONB — avoids creating all tables when testing specific endpoints"
metrics:
  duration_seconds: 551
  completed_date: "2026-03-31T19:16:02Z"
  tasks_completed: 2
  files_created: 6
  files_modified: 1
---

# Phase 2 Plan 3: Supporting CRUD Endpoints Summary

Five REST API routers providing watchlist/keyword management, agent-run logs, daily digests, and today's content bundle — all protected by JWT auth via router-level dependency injection.

## What Was Built

### Task 1: Watchlist and Keyword CRUD Routers (commit a76a425)

**backend/app/routers/watchlists.py** — Full CRUD for the Twitter/Instagram watchlist:
- `GET /watchlists` — list all, optional `?platform=` filter, ordered by `created_at desc`
- `POST /watchlists` — create entry, returns 201 with created object
- `PATCH /watchlists/{id}` — partial update using `model_dump(exclude_unset=True)`, 404 if not found
- `DELETE /watchlists/{id}` — delete, returns 204, 404 if not found

**backend/app/routers/keywords.py** — Full CRUD for keyword management:
- `GET /keywords` — list all, optional `?platform=` and `?active=` filters
- `POST /keywords` — create, returns 201
- `PATCH /keywords/{id}` — partial update, 404 if not found
- `DELETE /keywords/{id}` — delete, returns 204

### Task 2: Agent Runs, Digests, Content + Tests (commit e890492)

**backend/app/routers/agent_runs.py** (EXEC-01):
- `GET /agent-runs` — list with `?agent_name=` and `?days=7` filters, defaults to last 7 days, max 30

**backend/app/routers/digests.py**:
- `GET /digests/latest` — most recent digest by `digest_date desc`, 404 if none
- `GET /digests/{digest_date}` — exact date lookup, 404 if not found

**backend/app/routers/content.py**:
- `GET /content/today` — today's content bundle using `func.current_date()`, 404 if none

**backend/app/main.py** — Registered all 5 new routers (auth was already registered, queue router comes from plan 02-02).

**backend/tests/test_crud_endpoints.py** — 16 tests covering:
- Watchlist: list empty, create, filter by platform, partial update, delete
- Keywords: list empty, create, filter by active, partial update, delete
- Agent runs: list empty, filter by agent_name (EXEC-01)
- Digests: 404 when none exist, 404 by date
- Content: 404 when none today
- AUTH-03: all 7 endpoints return 401/403 without token

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] SQLite incompatible JSONB in Base.metadata.create_all**
- **Found during:** Task 2, first test run
- **Issue:** `Base.metadata.create_all` tried to create all tables including `draft_items` which has PostgreSQL JSONB columns. SQLite doesn't support JSONB, causing `CompileError`.
- **Fix:** Created SQLite-compatible test model definitions in the test file (`_Watchlist`, `_Keyword`, `_AgentRun`, `_DailyDigest`, `_ContentBundle`) using `sqlalchemy.dialects.sqlite.JSON` instead of JSONB. These are used only for table creation in SQLite; the actual ORM models (with JSONB) are used for query execution.
- **Files modified:** `backend/tests/test_crud_endpoints.py`
- **Commit:** e890492

## Test Results

```
16 passed, 42 warnings in 0.14s
```

All 16 tests pass. Warnings are non-critical: JWT key length (test secret) and deprecated `utcnow()` in SQLAlchemy column defaults.

## Self-Check: PASSED
