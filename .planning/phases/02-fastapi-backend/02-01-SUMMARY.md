---
phase: 02-fastapi-backend
plan: 01
subsystem: backend-auth
tags: [auth, jwt, bcrypt, pydantic, schemas, testing]
dependency_graph:
  requires: []
  provides:
    - app/auth.py (verify_password, create_access_token, decode_token)
    - app/dependencies.py (get_current_user, bearer_scheme)
    - app/routers/auth.py (POST /auth/login)
    - app/schemas/* (all Pydantic response/request models)
  affects:
    - All subsequent plans depend on auth dependency and Pydantic schemas
tech_stack:
  added:
    - PyJWT>=2.9 (JWT encode/decode)
    - bcrypt>=4.2,<5 (password hashing)
    - aiosqlite>=0.22 (SQLite async for tests)
  patterns:
    - FastAPI HTTPBearer dependency for auth
    - Pydantic v2 ConfigDict(from_attributes=True) on ORM response models
    - lru_cache cleanup pattern for settings in tests
    - SQLite-safe engine wrapper for test isolation
key_files:
  created:
    - backend/app/auth.py
    - backend/app/dependencies.py
    - backend/app/routers/__init__.py
    - backend/app/routers/auth.py
    - backend/app/schemas/__init__.py
    - backend/app/schemas/auth.py
    - backend/app/schemas/draft_item.py
    - backend/app/schemas/content_bundle.py
    - backend/app/schemas/watchlist.py
    - backend/app/schemas/keyword.py
    - backend/app/schemas/agent_run.py
    - backend/app/schemas/daily_digest.py
    - backend/alembic/versions/0002_add_edit_delta.py
    - backend/tests/test_auth.py
  modified:
    - backend/pyproject.toml (added PyJWT, bcrypt, aiosqlite)
    - backend/uv.lock
    - backend/app/models/draft_item.py (added edit_delta column)
    - backend/app/main.py (include_router for auth)
    - backend/tests/conftest.py (full rewrite — working SQLite fixtures)
decisions:
  - "PyJWT used directly (not python-jose) — already in CLAUDE.md stack but plan specified PyJWT which is the correct standalone library"
  - "SQLite engine pool-arg patching in conftest rather than refactoring database.py — database.py module-level engine creation is production code, test isolation handled at test layer"
  - "autouse clear_settings_cache fixture ensures lru_cache does not leak between tests"
metrics:
  duration_seconds: 1321
  completed_date: "2026-03-31"
  tasks_completed: 2
  files_created: 14
  files_modified: 5
---

# Phase 2 Plan 1: Auth Foundation, Pydantic Schemas, and Test Infrastructure Summary

JWT auth with bcrypt password verify, all Pydantic response schemas, and working httpx AsyncClient test infrastructure.

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| 1 | Install deps, add edit_delta column, create auth helpers and all Pydantic schemas | e1a4179 |
| 2 | Test infrastructure and auth endpoint tests (TDD) | f8a8bdb |

## What Was Built

### Auth System (app/auth.py, app/dependencies.py, app/routers/auth.py)

- `verify_password(plain, hashed)` — bcrypt.checkpw comparison
- `create_access_token()` — HS256 JWT with sub=operator, 7-day expiry (D-08)
- `decode_token(token)` — PyJWT decode with algorithm check
- `get_current_user` FastAPI dependency — raises HTTP 401 on invalid/missing token
- `POST /auth/login` — verifies bcrypt hash, returns `{access_token, token_type: "bearer"}`

### Pydantic Schemas (app/schemas/)

All response and request models defined with Pydantic v2 patterns:
- `auth.py`: LoginRequest, TokenResponse
- `draft_item.py`: DraftItemResponse (includes edit_delta), ApproveRequest (D-05), RejectRequest (D-12), QueueListResponse (D-02 cursor pagination)
- `content_bundle.py`: ContentBundleResponse
- `watchlist.py`: WatchlistCreate, WatchlistUpdate, WatchlistResponse
- `keyword.py`: KeywordCreate, KeywordUpdate, KeywordResponse
- `agent_run.py`: AgentRunResponse
- `daily_digest.py`: DailyDigestResponse

### Database Schema (edit_delta column)

- `edit_delta = Column(Text)` added to DraftItem model (D-14)
- Alembic migration 0002_add_edit_delta.py with upgrade/downgrade

### Test Infrastructure (tests/conftest.py, tests/test_auth.py)

- Replaced `pytest.skip()` placeholder with working fixtures
- `_sqlite_safe_create_async_engine` wrapper strips PostgreSQL-only pool kwargs when using SQLite — enables module-level `database.py` engine to work with `sqlite+aiosqlite:///:memory:` in tests without modifying production code
- `client` fixture: httpx AsyncClient + ASGITransport with get_db override
- `auth_token` fixture: creates valid JWT via create_access_token()
- `authed_client` fixture: pre-authorized client
- `clear_settings_cache` autouse fixture: clears lru_cache before/after each test

### Test Results

All 9 auth tests pass:
- test_verify_password_correct
- test_verify_password_incorrect
- test_token_decode_roundtrip
- test_token_has_7day_expiry
- test_protected_endpoint_invalid_token
- test_login_success
- test_login_wrong_password
- test_health_no_auth_required
- test_protected_endpoint_no_token

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] SQLite incompatible pool kwargs in test engine creation**
- **Found during:** Task 2
- **Issue:** `database.py` creates a module-level engine with `pool_size` and `max_overflow` which SQLite rejects. This caused conftest.py import to fail.
- **Fix:** Added `_sqlite_safe_create_async_engine` wrapper in conftest.py that strips incompatible kwargs when URL contains "sqlite". Patched `sqlalchemy.ext.asyncio.create_async_engine` at conftest module level before any app imports.
- **Files modified:** `backend/tests/conftest.py`
- **Commit:** f8a8bdb (included in Task 2 commit)

**2. [Rule 1 - Bug] Test file referenced non-existent `override_settings` fixture**
- **Found during:** Task 2
- **Issue:** Initial test file referenced `override_settings` fixture which was not in the new conftest design.
- **Fix:** Removed fixture parameter from tests that didn't need it — `clear_settings_cache` autouse handles the clearing automatically.
- **Files modified:** `backend/tests/test_auth.py`
- **Commit:** f8a8bdb

## Known Stubs

None. All schemas are properly wired to ORM model fields via `from_attributes=True`.

## Self-Check: PASSED
