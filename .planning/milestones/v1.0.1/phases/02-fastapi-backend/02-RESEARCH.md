# Phase 02: FastAPI Backend - Research

**Researched:** 2026-03-31
**Domain:** FastAPI REST API, JWT authentication, SQLAlchemy async, Twilio WhatsApp templates
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**API Endpoint Design**
- D-01: Response shape — Claude's discretion per endpoint (envelope vs direct payload)
- D-02: Cursor-based pagination for the approval queue using `created_at` cursor. Queue is capped at 15 but pagination supports filtering by platform/status
- D-03: Error format — Claude's discretion (pick what's cleanest for the React frontend)
- D-04: URL versioning — Claude's discretion
- D-05: Inline edit + approve in one API call — `PATCH /items/{id}/approve` accepts optional `edited_text` in body. Single call, not two-step edit-then-approve
- D-06: Bulk operations for watchlists/keywords — Claude's discretion

**Authentication**
- D-07: Simple password login — single bcrypt hash stored in `DASHBOARD_PASSWORD` env var, compared on login, returns JWT
- D-08: JWT expiry: 7 days
- D-09: Token expiry behavior — Claude's discretion (silent redirect to login or refresh token — pick the simpler approach for single-user)
- D-10: JWT secret stored in `JWT_SECRET` env var (already in config.py)

**Draft State Machine**
- D-11: Valid transitions: `pending → approved`, `pending → edited_approved` (with edit_delta preserved), `pending → rejected` (reason required), `pending → expired` (auto, by expiry processor). No other transitions allowed — API returns error on invalid transition
- D-12: Rejection reasons: category tag (off-topic, low-quality, bad-timing, tone-wrong, duplicate) + optional free-text notes. Both stored in `rejection_reason` field as structured JSON
- D-13: Expired items visible in an 'Expired' tab — soft state, not deleted, queryable via `GET /queue?status=expired`
- D-14: Edit history preserved — when `edited_approved`, store the original draft text in `edit_delta` field so the learning loop can compare original vs edited

**WhatsApp Notifications**
- D-15: Three WhatsApp trigger types: (1) daily morning digest at 8am, (2) breaking news alert when content scores 9.0+, (3) high-urgency draft about to expire
- D-16: Twilio failure handling — Claude's discretion (log + retry once, or log only)
- D-17: Use pre-registered Meta-approved templates: `seva_morning_digest` (HX930c2171b211acdea4d5fa0a12d6c0e0), `seva_breaking_news` (HXc5bcef9a42a18e9071acd1d6fb0fac39), `seva_expiry_alert` (HX45fd40f45d91e2ea54abd2298dd8bc41)

### Claude's Discretion
- Response envelope vs direct payload (D-01)
- Error format (D-03)
- URL versioning (D-04)
- Bulk operations (D-06)
- Token expiry handling (D-09)
- Twilio failure strategy (D-16)

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| AUTH-01 | Operator can log in with a password on the dashboard | POST /auth/login with bcrypt comparison against DASHBOARD_PASSWORD env var; returns JWT |
| AUTH-02 | Session persists across browser refresh (JWT token) | 7-day JWT stored in localStorage; HTTPBearer dependency validates on every protected route |
| AUTH-03 | Unauthenticated requests to dashboard and API are rejected | FastAPI HTTPBearer dependency injected into all non-auth routers; 401 on missing/invalid token |
| EXEC-01 | Every agent run logged: agent name, start/end time, items found, items queued, items filtered, errors | GET /agent-runs endpoint reads from agent_runs table; AgentRun model already complete in Phase 1 |
</phase_requirements>

---

## Summary

Phase 2 adds all the REST API endpoints to the FastAPI skeleton built in Phase 1. The core deliverables are: (1) a login endpoint that bcrypt-compares the dashboard password and returns a 7-day JWT, (2) a JWT validation dependency that protects every subsequent route, (3) the full approval queue CRUD with state-machine enforcement, and (4) a Twilio WhatsApp notification service that sends pre-approved template messages.

All six database models are already deployed. Phase 2 writes no migrations — it is pure API layer work on top of an existing schema. The existing `AsyncSessionLocal` dependency in `database.py` is used directly for all DB access. The `config.py` Settings class already holds `jwt_secret` and `dashboard_password`, so no new environment variable work is required.

**Key finding:** `passlib` is unmaintained (last release 2020) and breaks with `bcrypt >= 5.0.0`. The correct approach for this project is to use `bcrypt` directly (or `PyJWT` for the JWT side) rather than relying on the `passlib` CryptContext wrapper. FastAPI's own full-stack template already switched to direct `bcrypt` in 2025. `PyJWT` is preferred over `python-jose` for JWT operations: it is actively maintained, has minimal dependencies, and is now the library FastAPI's own docs use.

**Primary recommendation:** Use `bcrypt` directly for password hashing and `PyJWT` for JWT encoding/decoding. Structure routes under `backend/app/routers/` with one file per concern. Use `app.dependency_overrides[get_db]` + `httpx.AsyncClient(transport=ASGITransport(app=app))` for all tests.

---

## Standard Stack

### Core (already in pyproject.toml)
| Library | Installed Version | Purpose | Why Standard |
|---------|-------------------|---------|--------------|
| FastAPI | 0.135.2 | HTTP framework | Already installed; async-first, auto OpenAPI |
| SQLAlchemy | 2.0.x | Async ORM | Already installed; `AsyncSession` + `asyncpg` |
| Twilio | 9.10.4 | WhatsApp notifications | Already installed; `content_sid` API for templates |

### New Dependencies Required
| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| PyJWT | 2.9.x | JWT encode/decode | Actively maintained; FastAPI docs now use it; minimal deps |
| bcrypt | 4.2.x | Password hashing | Direct usage, no passlib wrapper needed; `bcrypt.checkpw()` API is simple |
| aiosqlite | 0.22.x | Async SQLite for tests | Lets test suite use in-memory SQLite via `sqlite+aiosqlite:///` DSN; no Neon needed |

**Why not python-jose:** Last meaningful maintenance was 2021; FastAPI community migrated away; python-jose 3.5.0 is healthy but the FastAPI full-stack template uses PyJWT. For this project's simple HS256 signing need, PyJWT is sufficient and lower risk.

**Why not passlib:** Unmaintained since 2020. `bcrypt 5.x` breaks `passlib`'s assumptions. FastAPI's own full-stack template replaced passlib with direct `bcrypt` in PR #1539 (2025). Direct bcrypt API is three lines of code.

**Version verification:**
```bash
# Run before finalising pyproject.toml additions
uv add "PyJWT>=2.9" "bcrypt>=4.2,<5" "aiosqlite>=0.22"
```
Note: pin `bcrypt < 5` to avoid the 72-byte password length restriction change in bcrypt 5.0.0 and the Rust-compiled wheel requirement. bcrypt 4.2.x is stable and Python-wheel distributed.

### Installation
```bash
cd backend
uv add "PyJWT>=2.9" "bcrypt>=4.2,<5" "aiosqlite>=0.22"
uv add --dev "pytest-asyncio>=0.23" "httpx>=0.27"
```

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| PyJWT | python-jose[cryptography] | python-jose has JWE support we don't need; PyJWT is lighter, actively maintained |
| bcrypt direct | passlib[bcrypt] | passlib is unmaintained and breaks with bcrypt 5.x |
| aiosqlite (tests) | pytest-anyio + real Neon DB | Real DB tests are slower, require env var, fail offline |

---

## Architecture Patterns

### Recommended Project Structure
```
backend/app/
├── main.py              # FastAPI app — includes all routers
├── config.py            # Settings (already exists, no changes)
├── database.py          # AsyncSession dep (already exists, no changes)
├── auth.py              # JWT encode/decode + bcrypt helpers
├── dependencies.py      # get_current_user dependency (reused by all protected routers)
├── routers/
│   ├── __init__.py
│   ├── auth.py          # POST /auth/login
│   ├── queue.py         # GET/PATCH /queue, /items/{id}/*
│   ├── content.py       # GET /content/today
│   ├── digests.py       # GET /digests/latest, /digests/{date}
│   ├── watchlists.py    # CRUD /watchlists
│   ├── keywords.py      # CRUD+PATCH /keywords
│   └── agent_runs.py    # GET /agent-runs
├── schemas/
│   ├── __init__.py
│   ├── auth.py          # LoginRequest, TokenResponse
│   ├── draft_item.py    # DraftItemResponse, ApproveRequest, RejectRequest
│   ├── content_bundle.py
│   ├── watchlist.py
│   ├── keyword.py
│   ├── agent_run.py
│   └── daily_digest.py
├── services/
│   └── whatsapp.py      # Twilio send_template() wrapper
└── models/              # Already complete from Phase 1 — no changes
```

### Pattern 1: JWT Auth Dependency
**What:** A single `get_current_user` function uses `Depends(HTTPBearer())` and decodes the token with PyJWT. Raises 401 on any failure. Injected as a router-level dependency so auth applies to the entire router without per-endpoint decoration.

**When to use:** Every router except `routers/auth.py`.

```python
# backend/app/auth.py
import jwt
import bcrypt
from datetime import datetime, timedelta, timezone
from app.config import get_settings

settings = get_settings()
ALGORITHM = "HS256"
TOKEN_EXPIRE_DAYS = 7


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token() -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=TOKEN_EXPIRE_DAYS)
    return jwt.encode({"sub": "operator", "exp": expire}, settings.jwt_secret, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    # Raises jwt.PyJWTError on invalid/expired token
    return jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
```

```python
# backend/app/dependencies.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.auth import decode_token
import jwt

bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> str:
    try:
        payload = decode_token(credentials.credentials)
        return payload["sub"]
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
```

```python
# backend/app/routers/queue.py  (example of router-level auth)
from fastapi import APIRouter, Depends
from app.dependencies import get_current_user

router = APIRouter(
    prefix="/queue",
    tags=["queue"],
    dependencies=[Depends(get_current_user)],  # ALL endpoints in this router require auth
)
```

### Pattern 2: Login Endpoint
**What:** POST /auth/login — accepts JSON body with `password`, compares bcrypt against `DASHBOARD_PASSWORD` env var, returns `{"access_token": "...", "token_type": "bearer"}`.

**Note:** `dashboard_password` in `config.py` must be stored as a bcrypt hash (e.g., `$2b$12$...`). The hash must be generated once at setup: `python -c "import bcrypt; print(bcrypt.hashpw(b'yourpass', bcrypt.gensalt()).decode())"`. The plain-text password is never stored.

```python
# backend/app/routers/auth.py
from fastapi import APIRouter, HTTPException, status
from app.schemas.auth import LoginRequest, TokenResponse
from app.auth import verify_password, create_access_token
from app.config import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest):
    settings = get_settings()
    if not verify_password(body.password, settings.dashboard_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect password")
    token = create_access_token()
    return TokenResponse(access_token=token, token_type="bearer")
```

### Pattern 3: State Machine Enforcement
**What:** `PATCH /items/{id}/approve`, `PATCH /items/{id}/reject`, and `PATCH /items/{id}/edit` each validate the current status before writing. Return 409 Conflict on invalid transition.

**Valid transitions (D-11):**
- `pending → approved`
- `pending → edited_approved` (requires `edited_text` in body; original text saved to `edit_delta`)
- `pending → rejected` (requires rejection reason JSON)
- `pending → expired` (scheduler only, not API-triggered)

```python
# Inside queue router
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.draft_item import DraftItem, DraftStatus

VALID_TRANSITIONS = {
    DraftStatus.pending: {DraftStatus.approved, DraftStatus.edited_approved, DraftStatus.rejected},
}

async def enforce_transition(item: DraftItem, target: DraftStatus) -> None:
    allowed = VALID_TRANSITIONS.get(item.status, set())
    if target not in allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot transition from '{item.status}' to '{target}'",
        )
```

### Pattern 4: Twilio WhatsApp Template Send
**What:** Wrap `client.messages.create()` with `content_sid` parameter. The template SIDs from D-17 are module-level constants in `services/whatsapp.py`. No `body` or `media_url` — use only `content_sid` + `content_variables`.

```python
# backend/app/services/whatsapp.py
from twilio.rest import Client
from app.config import get_settings

TEMPLATE_SIDS = {
    "morning_digest": "HX930c2171b211acdea4d5fa0a12d6c0e0",
    "breaking_news":  "HXc5bcef9a42a18e9071acd1d6fb0fac39",
    "expiry_alert":   "HX45fd40f45d91e2ea54abd2298dd8bc41",
}


async def send_whatsapp_template(template: str, variables: dict) -> str:
    """Send a pre-approved WhatsApp template. Returns Twilio message SID."""
    settings = get_settings()
    client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
    import json
    msg = client.messages.create(
        from_=settings.twilio_whatsapp_from,
        to=settings.digest_whatsapp_to,
        content_sid=TEMPLATE_SIDS[template],
        content_variables=json.dumps(variables),
    )
    return msg.sid
```

**Note:** Twilio's Python SDK is synchronous. Call it via `asyncio.to_thread()` in async routes/services to avoid blocking the event loop.

```python
import asyncio
msg_sid = await asyncio.to_thread(send_whatsapp_template_sync, template, variables)
```

### Pattern 5: Testing with Dependency Overrides
**What:** Override `get_db` with an in-memory SQLite session. Use `httpx.AsyncClient` with `ASGITransport`.

```python
# tests/conftest.py  (updated for Phase 2)
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.main import app
from app.database import get_db
from app.models.base import Base

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def async_db_session():
    engine = create_async_engine(TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def client(async_db_session):
    async def override_get_db():
        yield async_db_session
    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
```

**Known SQLite limitation:** SQLite does not support the `ENUM` PostgreSQL type used in `DraftItem.status`. The test engine must use `render_as_batch=True` in Alembic context, or the test models must be created with `String` fallback. A simpler approach: mark ENUM column as `String` in a test-only model, OR skip SQLite for state-machine tests and mock the DB layer instead.

**Recommended approach:** For auth tests (pure logic, no DB state needed), use SQLite. For state-machine enforcement tests, mock the SQLAlchemy session with `unittest.mock.AsyncMock` and test the transition logic as a unit function, not through the HTTP layer.

### Anti-Patterns to Avoid
- **Calling `bcrypt.hashpw()` on every request:** Hash once at setup time. The hash is in the env var; call `checkpw()` only on login.
- **Storing JWT in a DB table for invalidation:** Single-user 7-day token — stateless is sufficient. No token blacklist needed.
- **Putting `get_current_user` on the route function level with `Depends()`:** Use `router = APIRouter(dependencies=[Depends(get_current_user)])` at the router level to protect all routes at once without per-endpoint boilerplate.
- **Using `client.messages.create()` directly in an async def route:** Twilio SDK is sync — wrapping in `asyncio.to_thread()` is required.
- **Returning SQLAlchemy model objects directly from routes:** Always serialize through Pydantic schema with `model_validate(orm_obj)` and `from_attributes=True`.
- **Calling `session.commit()` inside a test fixture:** The test session fixture should not commit; changes accumulate in the transaction and roll back when the fixture closes.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Password hashing | Custom SHA-256 scheme | `bcrypt.hashpw()` / `bcrypt.checkpw()` | Salting, timing-safe comparison, cost factor — all built in |
| JWT creation/validation | Manual base64+HMAC | `PyJWT` | Handles exp validation, algorithm selection, error types |
| HTTP security scheme parsing | Manual `Authorization: Bearer` header parsing | `fastapi.security.HTTPBearer` | Returns `HTTPAuthorizationCredentials` cleanly; auto-documents in OpenAPI |
| WhatsApp template registry | Database table of template SIDs | Module-level constants in `services/whatsapp.py` | Template SIDs are stable strings known at build time — no runtime lookup needed |
| Async test HTTP client | `requests` + sync TestClient | `httpx.AsyncClient` + `ASGITransport` | Preserves async lifecycle; required for async route testing |

**Key insight:** This phase's "custom" work is almost entirely composition — wiring together FastAPI's dependency injection, PyJWT, bcrypt, and Twilio. The only genuinely custom logic is the state machine transition map, which is 8 lines of Python.

---

## Common Pitfalls

### Pitfall 1: bcrypt Hash Format in Env Var
**What goes wrong:** `bcrypt.checkpw()` expects the hash as `bytes`, but `pydantic-settings` reads env vars as `str`. Calling `bcrypt.checkpw(password.encode(), settings.dashboard_password)` fails with a TypeError.
**Why it happens:** bcrypt's Python API accepts `bytes` only; `str` is not accepted in bcrypt 4.x.
**How to avoid:** Call `settings.dashboard_password.encode()` when passing to `checkpw`: `bcrypt.checkpw(password.encode(), settings.dashboard_password.encode())`.
**Warning signs:** `TypeError: Unicode-objects must be encoded before hashing` or `ValueError: Invalid salt`.

### Pitfall 2: DraftStatus ENUM Type in SQLite Tests
**What goes wrong:** SQLAlchemy's `ENUM("pending", ...)` with `create_type=False` requires PostgreSQL to create the enum type. SQLite does not support `CREATE TYPE`. Running `Base.metadata.create_all()` against SQLite raises `CompileError`.
**Why it happens:** Phase 1 used `create_type=False` because Alembic manages the PostgreSQL ENUM. SQLite has no ENUM type at all.
**How to avoid:** For in-memory test DB, either (a) only test auth routes (no DraftItem needed) or (b) patch the DraftStatus column to `String` in the test session. The simplest is option (a): auth tests use SQLite, state-machine tests use mocked sessions.
**Warning signs:** `sqlalchemy.exc.CompileError: (in table 'draft_items', column 'status'): Can't generate DDL for NullType`.

### Pitfall 3: Router Registration Order in main.py
**What goes wrong:** If `routers/auth.py` is registered with a prefix that conflicts with protected routers, FastAPI may route auth requests through the auth dependency, causing 401 on the login endpoint itself.
**Why it happens:** Router-level `dependencies=[Depends(get_current_user)]` applies to all routes in that router, but if the auth router is accidentally given the same dependency, login returns 401.
**How to avoid:** Only non-auth routers get the auth dependency. `routers/auth.py` has no dependencies at router level.

### Pitfall 4: Twilio sync call blocking event loop
**What goes wrong:** `client.messages.create(...)` blocks the event loop for the duration of the HTTPS call (typically 200-800ms). Under load, this stalls all concurrent requests.
**Why it happens:** Twilio's Python SDK is synchronous — there is no `async` version.
**How to avoid:** Wrap in `await asyncio.to_thread(lambda: client.messages.create(...))`. This offloads the call to a threadpool executor without blocking.

### Pitfall 5: edit_delta Field Not in Current DraftItem Schema
**What goes wrong:** D-14 requires storing the original draft text in `edit_delta` when a draft is `edited_approved`. But `DraftItem` model in Phase 1 has no `edit_delta` column.
**Why it happens:** Phase 1 schema was built for the initial design. The `edit_delta` field was added to requirements in Phase 2 discussion (D-14).
**How to avoid:** Phase 2 MUST add an Alembic migration to add `edit_delta TEXT` column to `draft_items`. The CONTEXT.md says "Phase 2 likely needs none — schema is complete" but D-14 contradicts this for `edit_delta`. Verify by reading the current migration file before writing code.
**Warning signs:** `sqlalchemy.exc.ProgrammingError: column "edit_delta" of relation "draft_items" does not exist`.

### Pitfall 6: cursor-based pagination with UUID primary keys
**What goes wrong:** D-02 specifies cursor-based pagination using `created_at`. But `created_at` values can collide (two items created within the same millisecond), causing items to be skipped.
**Why it happens:** Timestamp cursors are not strictly unique.
**How to avoid:** Use a composite cursor: `(created_at, id)`. The query is `WHERE (created_at, id) < (cursor_ts, cursor_id) ORDER BY created_at DESC, id DESC`. Return both values as the cursor token (base64-encode as `created_at_iso:id`).

---

## Code Examples

Verified patterns from official/confirmed sources:

### PyJWT encode/decode (official PyJWT docs)
```python
# Source: https://pyjwt.readthedocs.io/en/stable/
import jwt
from datetime import datetime, timedelta, timezone

secret = "your-secret"
payload = {"sub": "operator", "exp": datetime.now(timezone.utc) + timedelta(days=7)}
token = jwt.encode(payload, secret, algorithm="HS256")  # returns str in PyJWT 2.x
decoded = jwt.decode(token, secret, algorithms=["HS256"])  # raises jwt.ExpiredSignatureError if expired
```

### bcrypt direct usage (official bcrypt PyPI docs, bcrypt 4.x)
```python
# Source: https://pypi.org/project/bcrypt/
import bcrypt

# Generate hash (run once at setup, store result in DASHBOARD_PASSWORD env var)
hashed = bcrypt.hashpw(b"mypassword", bcrypt.gensalt()).decode()

# Verify on login (hashed is str from env var, encode both sides)
is_valid = bcrypt.checkpw(b"mypassword", hashed.encode())
```

### Twilio content_sid template send (Twilio docs 2025)
```python
# Source: https://www.twilio.com/docs/content/send-templates-created-with-the-content-template-builder
import json
from twilio.rest import Client

client = Client(account_sid, auth_token)
message = client.messages.create(
    from_="whatsapp:+14155238886",
    to="whatsapp:+1XXXXXXXXXX",
    content_sid="HX930c2171b211acdea4d5fa0a12d6c0e0",
    content_variables=json.dumps({"1": "value_for_variable_1"}),
)
# message.sid is the Twilio message SID for logging
```

### FastAPI router-level auth dependency (FastAPI docs)
```python
# Source: https://fastapi.tiangolo.com/reference/apirouter/
from fastapi import APIRouter, Depends
from app.dependencies import get_current_user

router = APIRouter(
    prefix="/queue",
    tags=["queue"],
    dependencies=[Depends(get_current_user)],
)
# No need to add Depends(get_current_user) to each individual endpoint
```

### httpx AsyncClient test pattern (FastAPI docs)
```python
# Source: https://fastapi.tiangolo.com/advanced/async-tests/
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.anyio
async def test_login_success():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/auth/login", json={"password": "test"})
    assert response.status_code == 200
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| passlib + bcrypt | bcrypt direct | 2024-2025 (passlib abandoned) | Fewer deps, no compatibility issues |
| python-jose | PyJWT | 2024 (FastAPI docs updated) | Actively maintained, simpler API |
| `TestClient` (sync) | `httpx.AsyncClient` + `ASGITransport` | FastAPI 0.107+ | Full async lifecycle in tests |
| `body` in Twilio messages.create | `content_sid` + `content_variables` | 2023 (WhatsApp template enforcement) | Required for outbound-initiated messages outside 24h window |
| `OAuth2PasswordBearer` + user DB | `HTTPBearer` + env var hash | N/A — design choice | Appropriate for single-user internal tool |

**Deprecated/outdated:**
- `passlib.context.CryptContext`: Breaks with bcrypt 5.x. Use `bcrypt.hashpw()` / `bcrypt.checkpw()` directly.
- `python-jose`: Last meaningful release 2021. Use `PyJWT` for HS256 token signing.
- Twilio `body=` parameter for WhatsApp templates: Superseded by `content_sid=`. Templates submitted outside the 24-hour session window require `content_sid`.

---

## Open Questions

1. **edit_delta column missing from DraftItem model**
   - What we know: D-14 requires `edit_delta TEXT` to store original draft text when `edited_approved` transition occurs.
   - What's unclear: Phase 1 alembic migration `0001_initial_schema.py` needs inspection to confirm `edit_delta` is absent.
   - Recommendation: Read `backend/alembic/versions/0001_initial_schema.py` in the PLAN step. If absent, Wave 0 of Phase 2 must add an Alembic migration `0002_add_edit_delta.py` before any endpoint code is written.

2. **content_variables format for the three Seva templates**
   - What we know: The template SIDs are known (D-17). The variable placeholders `{1}`, `{2}`, etc. depend on how each template was submitted to Meta.
   - What's unclear: The exact variable keys for each template are not documented in CONTEXT.md.
   - Recommendation: The `services/whatsapp.py` implementation should document the expected variable dict for each template in a docstring. In Wave 0, verify template variable format with a test send or by reading the template content from the Twilio console.

3. **dashboard_password bcrypt hash setup**
   - What we know: `config.py` stores `dashboard_password` as a string from env var.
   - What's unclear: Is the current value in `.env` a plain-text password or already a bcrypt hash? The CONTEXT.md says "stored as bcrypt hash in Phase 2" — meaning Phase 1 likely left it as plain text.
   - Recommendation: Wave 0 task should include a script or CLI command to generate the bcrypt hash and update `.env`. Document the one-time setup command.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| uv | Dependency management | Yes | 0.11.2 | — |
| Python 3.12 | Runtime (via uv) | Yes (uv manages it) | 3.12.13 | — |
| Twilio SDK | WhatsApp service | Yes (installed) | 9.10.4 | — |
| FastAPI | HTTP framework | Yes (installed) | 0.135.2 | — |
| PyJWT | JWT auth | No — needs `uv add` | — | — |
| bcrypt | Password hashing | No — needs `uv add` | — | — |
| aiosqlite | Test SQLite driver | No — needs `uv add` | — | — |
| Neon PostgreSQL | Live DB | Yes (Phase 1 deployed) | PG 16 | SQLite for unit tests |

**Missing dependencies with no fallback:**
- `PyJWT` — blocks all auth implementation
- `bcrypt` — blocks all auth implementation

**Missing dependencies with fallback:**
- `aiosqlite` — blocks in-memory test DB; fallback is mocked sessions (acceptable for state-machine tests)

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.x + pytest-asyncio 1.3.x |
| Config file | `backend/pyproject.toml` [tool.pytest.ini_options] |
| Quick run command | `uv run pytest tests/test_auth.py tests/test_queue.py -x` |
| Full suite command | `uv run pytest tests/ -x` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| AUTH-01 | POST /auth/login returns 200 + token with correct password | unit | `uv run pytest tests/test_auth.py::test_login_success -x` | Wave 0 |
| AUTH-01 | POST /auth/login returns 401 with wrong password | unit | `uv run pytest tests/test_auth.py::test_login_wrong_password -x` | Wave 0 |
| AUTH-02 | Token decoded correctly; same token works across multiple requests | unit | `uv run pytest tests/test_auth.py::test_token_reuse -x` | Wave 0 |
| AUTH-03 | GET /queue without Authorization header returns 401 | unit | `uv run pytest tests/test_auth.py::test_unauthenticated_rejected -x` | Wave 0 |
| AUTH-03 | GET /queue with invalid token returns 401 | unit | `uv run pytest tests/test_auth.py::test_invalid_token_rejected -x` | Wave 0 |
| EXEC-01 | GET /agent-runs returns list with correct fields | unit | `uv run pytest tests/test_agent_runs.py::test_list_agent_runs -x` | Wave 0 |
| D-11 | PATCH /items/{id}/approve from pending returns 200 | unit | `uv run pytest tests/test_queue.py::test_approve_transition -x` | Wave 0 |
| D-11 | PATCH /items/{id}/approve from approved returns 409 | unit | `uv run pytest tests/test_queue.py::test_invalid_transition -x` | Wave 0 |
| D-12 | PATCH /items/{id}/reject without reason returns 422 | unit | `uv run pytest tests/test_queue.py::test_reject_requires_reason -x` | Wave 0 |
| D-14 | PATCH /items/{id}/approve with edited_text saves edit_delta | unit | `uv run pytest tests/test_queue.py::test_edit_delta_preserved -x` | Wave 0 |
| D-17 | send_whatsapp_template called with correct content_sid | unit (mock) | `uv run pytest tests/test_whatsapp.py::test_template_sid_correct -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_auth.py -x`
- **Per wave merge:** `uv run pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_auth.py` — covers AUTH-01, AUTH-02, AUTH-03
- [ ] `tests/test_queue.py` — covers D-11, D-12, D-14, EXEC-01
- [ ] `tests/test_agent_runs.py` — covers EXEC-01
- [ ] `tests/test_whatsapp.py` — covers D-17 (mocked Twilio client)
- [ ] `tests/conftest.py` — update the existing stub to activate `async_db_session` fixture (remove the `pytest.skip()` placeholder)
- [ ] Install: `uv add "PyJWT>=2.9" "bcrypt>=4.2,<5" "aiosqlite>=0.22"` — if absent, all tests fail to import

---

## Project Constraints (from CLAUDE.md)

| Constraint | Directive |
|------------|-----------|
| Stack | FastAPI (Python) backend — no switching framework |
| Auth | Simple password login, single user — no OAuth, no multi-user |
| JWT | Use `jwt_secret` env var from config.py — already wired |
| Password | Single bcrypt hash in `DASHBOARD_PASSWORD` env var |
| Async | All handlers must be `async def`; no `requests` library; use `httpx` for any outbound HTTP |
| ORM | SQLAlchemy 2.0 only — `create_async_engine`, `AsyncSession`, `async_sessionmaker` |
| Pydantic | v2 patterns only: `model_config = ConfigDict(from_attributes=True)` — no v1 patterns |
| No auto-posting | Never implement any endpoint that posts to Twitter or Instagram |
| Scheduler | APScheduler 3.11.2 — v4 alpha is forbidden |
| Package manager | `uv` — use `uv add` not `pip install` |
| Linter | `ruff` — configured in pyproject.toml |
| Testing | `pytest` + `pytest-asyncio` with `asyncio_mode = "auto"` in pyproject.toml |

---

## Sources

### Primary (HIGH confidence)
- FastAPI official docs — APIRouter, dependencies, async tests: https://fastapi.tiangolo.com/
- PyJWT PyPI (version 2.9.x, actively maintained): https://pypi.org/project/PyJWT/
- bcrypt PyPI (version 4.2.x stable Python wheels): https://pypi.org/project/bcrypt/
- Twilio docs — content_sid template send pattern: https://www.twilio.com/docs/content/send-templates-created-with-the-content-template-builder
- FastAPI full-stack template PR #1539 — passlib replaced by direct bcrypt: https://github.com/fastapi/full-stack-fastapi-template/pull/1539
- aiosqlite PyPI (version 0.22.1, Dec 2025): https://pypi.org/project/aiosqlite/

### Secondary (MEDIUM confidence)
- passlib maintenance status (Snyk + GitHub discussion): https://snyk.io/advisor/python/passlib + https://github.com/fastapi/fastapi/discussions/11773
- python-jose community migration to PyJWT: https://github.com/fastapi/fastapi/discussions/9587
- FastAPI async testing with ASGITransport: https://fastapi.tiangolo.com/advanced/async-tests/

### Tertiary (LOW confidence — verify at implementation time)
- Twilio WhatsApp content_variables key format for pre-registered templates: must be confirmed from Twilio console at implementation time

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — FastAPI/SQLAlchemy already installed and verified; PyJWT and bcrypt versions confirmed from PyPI
- Authentication pattern: HIGH — verified against FastAPI docs and the full-stack template migration
- State machine: HIGH — pure Python logic, no external dependencies
- Twilio template send: HIGH — verified against Twilio official docs 2025
- Test infrastructure: HIGH — pytest-asyncio asyncio_mode=auto already configured in pyproject.toml

**Research date:** 2026-03-31
**Valid until:** 2026-04-30 (stable ecosystem; bcrypt/PyJWT don't move fast)
