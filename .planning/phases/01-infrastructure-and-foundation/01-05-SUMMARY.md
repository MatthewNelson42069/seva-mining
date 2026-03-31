---
phase: 01-infrastructure-and-foundation
plan: 05
subsystem: backend-api
tags: [fastapi, railway, docker, health-check, deployment]
dependency_graph:
  requires: [01-04]
  provides: [fastapi-app-skeleton, health-endpoint, dockerfile, railway-config]
  affects: [all-phase-2-api-endpoints]
tech_stack:
  added: []
  patterns: [fastapi-lifespan, testclient-module-fixture, railway-toml-health-check]
key_files:
  created:
    - backend/app/main.py
    - backend/Dockerfile
    - backend/railway.toml
    - backend/.dockerignore
  modified:
    - backend/tests/test_health.py
    - backend/tests/test_schema.py
decisions:
  - "FastAPI lifespan used for engine.dispose() on shutdown — cleaner than on_event deprecated pattern"
  - "TestClient fixture scoped to module for efficiency; env vars set at module level before import"
  - "test_schema.py skip condition updated to check for real neon.tech URL (not just non-empty) to prevent fake URL leak from test_health.py"
metrics:
  duration_minutes: 2
  completed_date: "2026-03-31"
  tasks_completed: 2
  files_created: 4
  files_modified: 2
---

# Phase 1 Plan 5: FastAPI App Skeleton and Railway Deployment Config Summary

**One-liner:** FastAPI app with /health endpoint, lifespan engine disposal, Railway Dockerfile with alembic-before-uvicorn, and railway.toml health check config.

## What Was Built

- `backend/app/main.py`: FastAPI app with asynccontextmanager lifespan (disposes engine pool on shutdown), `/health` endpoint returning `{"status": "ok"}`
- `backend/Dockerfile`: python:3.12-slim, uv for deps, runs `alembic upgrade head` before `uvicorn` with `--workers 1` (Neon free tier connection limit)
- `backend/railway.toml`: `healthcheckPath = "/health"`, `numReplicas = 1`, `restartPolicyType = "ON_FAILURE"`, `dockerfilePath = "backend/Dockerfile"`
- `backend/.dockerignore`: excludes `.env`, `__pycache__`, tests, `.venv` for lean Docker image
- `backend/tests/test_health.py`: 2 tests enabled (un-skipped) — both GREEN

## Verification

- `uv run pytest tests/test_health.py -v` → 2 PASSED
- `uv run pytest tests/ -v` → 7 passed, 4 skipped, 0 failed, 0 errors

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] test_schema.py skip logic broken when run alongside test_health.py**
- **Found during:** Post-task 2 overall verification
- **Issue:** `test_health.py` sets `DATABASE_URL=postgresql+asyncpg://fake-pooler.neon.tech/testdb` via `os.environ.setdefault()` at module level. When the full test suite runs, `test_schema.py`'s `pytestmark` skip condition evaluated to `True` (URL non-empty), then failed with `socket.gaierror` trying to connect to fake host.
- **Fix:** Updated `test_schema.py` skip condition to check `"neon.tech" in DATABASE_URL and "fake" not in DATABASE_URL` — correctly skips on fake URLs while running on real Neon connections.
- **Files modified:** `backend/tests/test_schema.py`
- **Commit:** e72223d

## Commits

| Hash | Message |
|------|---------|
| ceca3da | feat(01-05): FastAPI app with /health endpoint and GREEN test_health.py |
| acafc6d | feat(01-05): backend Dockerfile, railway.toml, and .dockerignore |
| e72223d | fix(01-05): test_schema.py skip logic robust against fake DATABASE_URL |

## Known Stubs

None — `/health` endpoint returns real data (`{"status": "ok"}`). No stubs present.

## Self-Check: PASSED

- FOUND: backend/app/main.py
- FOUND: backend/Dockerfile
- FOUND: backend/railway.toml
- FOUND: backend/.dockerignore
- FOUND commit ceca3da: feat(01-05): FastAPI app with /health endpoint
- FOUND commit acafc6d: feat(01-05): backend Dockerfile, railway.toml, and .dockerignore
- FOUND commit e72223d: fix(01-05): test_schema.py skip logic robust against fake DATABASE_URL
