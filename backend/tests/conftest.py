"""
Shared test fixtures for backend tests.
"""
import os

import bcrypt
import pytest
import pytest_asyncio

# ---------------------------------------------------------------------------
# STEP 1: Set environment variables BEFORE any app imports
# ---------------------------------------------------------------------------
_TEST_JWT_SECRET = "test-jwt-secret-for-tests"
_TEST_PASSWORD = "testpassword"
_TEST_PASSWORD_HASH = bcrypt.hashpw(_TEST_PASSWORD.encode(), bcrypt.gensalt()).decode()
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
os.environ["APIFY_API_TOKEN"] = "test-token"
os.environ["SERPAPI_API_KEY"] = "test-key"
os.environ["JWT_SECRET"] = _TEST_JWT_SECRET
os.environ["DASHBOARD_PASSWORD"] = _TEST_PASSWORD_HASH
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

from app.auth import create_access_token  # noqa: E402 (must follow engine patch)
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
    """Create a valid JWT token for testing (uses JWT_SECRET from env)."""
    return create_access_token()


@pytest_asyncio.fixture
async def authed_client(client, auth_token):
    """HTTP test client with Authorization: Bearer header pre-set."""
    client.headers.update({"Authorization": f"Bearer {auth_token}"})
    yield client


@pytest.fixture
def anyio_backend():
    return "asyncio"
