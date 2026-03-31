"""
Shared test fixtures for backend tests.
Database fixture will be completed when app/database.py exists (Plan 03).
"""
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# In-memory SQLite for unit tests that don't need PostgreSQL-specific features.
# Schema smoke tests (INFRA-01, INFRA-02, INFRA-06) connect to Neon using DATABASE_URL env var.
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def async_db_session():
    """
    Async DB session fixture using SQLite for unit tests.
    Requires app.models to be importable (available after Plan 03).
    """
    pytest.skip("Requires app.models — will be enabled in Plan 03")


@pytest.fixture
def anyio_backend():
    return "asyncio"
