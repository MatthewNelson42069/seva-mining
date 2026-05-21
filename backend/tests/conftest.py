"""
Shared test fixtures for backend tests.
"""
import os
from pathlib import Path as _Path

import pytest
import pytest_asyncio

# ---------------------------------------------------------------------------
# STEP 0: Capture the real DATABASE_URL (Neon Postgres) BEFORE override.
#         The migration-test fixture (postgres_migration_session) needs the
#         real PG URL to run Postgres-specific queries (pg_catalog,
#         information_schema with PG-specific columns) against the
#         already-migrated Neon DB. v3.0 Phase 9 (TENANT-01/02 migration
#         verification tests).
# ---------------------------------------------------------------------------
_REAL_DATABASE_URL = os.environ.get("DATABASE_URL")
if not _REAL_DATABASE_URL:
    # Fall back to reading backend/.env directly (uv run alembic loads this
    # automatically, but pytest does not unless pydantic-settings dotenv is
    # invoked, which happens AFTER conftest imports here).
    _env_path = _Path(__file__).resolve().parents[1] / ".env"
    if _env_path.exists():
        for _line in _env_path.read_text().splitlines():
            if _line.startswith("DATABASE_URL="):
                _REAL_DATABASE_URL = _line.split("=", 1)[1].strip().strip('"').strip("'")
                break

# ---------------------------------------------------------------------------
# STEP 1: Set environment variables BEFORE any app imports
# ---------------------------------------------------------------------------
_TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

os.environ["DATABASE_URL"] = _TEST_DB_URL
os.environ["ANTHROPIC_API_KEY"] = "test-key"
os.environ["TWILIO_ACCOUNT_SID"] = "test-sid"
os.environ["TWILIO_AUTH_TOKEN"] = "test-token"
os.environ["TWILIO_WHATSAPP_FROM"] = "whatsapp:+14155238886"
os.environ["DIGEST_WHATSAPP_TO"] = "whatsapp:+15551234567"
os.environ["X_API_BEARER_TOKEN"] = "test-bearer"
os.environ["X_API_KEY"] = "test-key"
os.environ["X_API_SECRET"] = "test-secret"
# Phase B (quick-260424-l0d): OAuth1 user-context tokens for tweepy.
# X_POSTING_ENABLED stays UNSET → defaults to False → all tests run in simulate mode,
# never invoking the real tweepy AsyncClient (no network calls in unit tests).
os.environ["X_ACCESS_TOKEN"] = "test-access"
os.environ["X_ACCESS_TOKEN_SECRET"] = "test-access-secret"
os.environ["SERPAPI_API_KEY"] = "test-key"
os.environ["SEVA_DASHBOARD_TOKEN"] = "test-dashboard-token-for-tests-xyz"
os.environ["FRONTEND_URL"] = "http://localhost:3000"

# ---------------------------------------------------------------------------
# STEP 2: Patch create_async_engine to strip PostgreSQL-only pool kwargs
#         before app.database is first imported.
# ---------------------------------------------------------------------------
from sqlalchemy.ext.asyncio import (  # noqa: E402 (must come after env setup above)
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.ext.asyncio import (  # noqa: E402 (must come after env setup above)
    create_async_engine as _real_create_async_engine,
)

_SQLITE_INCOMPATIBLE_KWARGS = {"pool_size", "max_overflow", "pool_pre_ping", "pool_recycle"}

def _sqlite_safe_create_async_engine(url, **kwargs):
    """Wrapper that strips PostgreSQL-only pool kwargs when using SQLite."""
    url_str = str(url)
    if "sqlite" in url_str:
        for key in _SQLITE_INCOMPATIBLE_KWARGS:
            kwargs.pop(key, None)
    return _real_create_async_engine(url, **kwargs)

# Patch at module level before app.database imports it
import sqlalchemy.ext.asyncio as _sqla_async  # noqa: E402 (deliberate late import so we can monkey-patch)

_sqla_async.create_async_engine = _sqlite_safe_create_async_engine

# ---------------------------------------------------------------------------
# STEP 3: Now safely import app modules
# ---------------------------------------------------------------------------
from httpx import ASGITransport, AsyncClient  # noqa: E402 (must follow engine patch)

from app.config import get_settings  # noqa: E402 (must follow engine patch)
from app.database import get_db  # noqa: E402 (must follow engine patch)
from app.main import app  # noqa: E402 (must follow engine patch)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clear_settings_cache():
    """Clear lru_cache on get_settings before and after each test."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def async_db_session():
    """Async DB session fixture using SQLite in-memory for unit tests."""
    engine = _sqlite_safe_create_async_engine(_TEST_DB_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def postgres_migration_session():
    """Async DB session against the REAL Neon Postgres for migration tests.

    v3.0 Phase 9 — TENANT-01/02 migration verification tests issue
    Postgres-specific queries (pg_catalog.pg_constraint, information_schema
    with PG-specific column_default shape) that SQLite cannot satisfy.

    Skips at collection time if no real DATABASE_URL is available (CI without
    Neon creds). When present, connects via asyncpg + ssl=True (Neon idiom).

    Wraps every test in a ROLLBACK so pg_constraint checks see the migrated
    schema but no test data leaks between runs.
    """
    if not _REAL_DATABASE_URL or "sqlite" in _REAL_DATABASE_URL:
        pytest.skip(
            "postgres_migration_session requires DATABASE_URL pointing at a "
            "real Postgres (Neon). Found: "
            f"{_REAL_DATABASE_URL!r}"
        )

    # asyncpg does not accept sslmode=require in URL; pass ssl=True via
    # connect_args (Neon idiom — matches backend/alembic/env.py).
    url = _REAL_DATABASE_URL.replace("?sslmode=require", "").replace(
        "&sslmode=require", ""
    )
    connect_args = {"ssl": True} if "neon.tech" in url else {}

    engine = _real_create_async_engine(url, connect_args=connect_args)
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        try:
            yield session
        finally:
            await session.rollback()
    await engine.dispose()


@pytest_asyncio.fixture
async def client():
    """HTTP test client using httpx AsyncClient + ASGITransport."""
    engine = _sqlite_safe_create_async_engine(_TEST_DB_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_db, None)
    await engine.dispose()


@pytest.fixture
def auth_token():
    """Return the test dashboard token (cookie-based auth, quick-260521-9ze).

    Was: create_access_token() (JWT). Now: the literal SEVA_DASHBOARD_TOKEN
    value set in STEP 1 above. Still called `auth_token` to minimise diffs
    in existing test helpers that call this fixture.
    """
    return os.environ["SEVA_DASHBOARD_TOKEN"]


@pytest_asyncio.fixture
async def authed_client(client, auth_token):
    """HTTP test client with seva_auth_token cookie pre-set."""
    client.cookies.set("seva_auth_token", auth_token)
    yield client


@pytest.fixture
def anyio_backend():
    return "asyncio"
