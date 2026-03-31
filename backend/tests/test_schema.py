"""
Tests for PostgreSQL schema correctness.
Covers: INFRA-01 (all 6 tables), INFRA-02 (indexes), INFRA-06 (Alembic at head)
Requires DATABASE_URL env var pointing to Neon (skipped otherwise).
"""
import os
import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL not set — requires Neon connection"
)

_raw_url = os.getenv("DATABASE_URL", "")
DATABASE_URL = _raw_url.replace("?sslmode=require", "").replace("&sslmode=require", "")

EXPECTED_TABLES = {
    "draft_items",
    "content_bundles",
    "agent_runs",
    "daily_digests",
    "watchlists",
    "keywords",
}

EXPECTED_INDEXES = {
    "ix_draft_items_status",
    "ix_draft_items_platform",
    "ix_draft_items_created_at",
    "ix_draft_items_expires_at",
}


@pytest.fixture
def engine():
    # ssl=True required for Neon — asyncpg does not accept sslmode= in URL
    # Use function scope (not module) to avoid event loop cross-contamination between tests
    connect_args = {"ssl": True} if "neon.tech" in DATABASE_URL else {}
    return create_async_engine(DATABASE_URL, connect_args=connect_args)


@pytest.mark.asyncio
async def test_all_tables_exist(engine):
    """All 6 tables must exist in the public schema."""
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname = 'public'"
            )
        )
        tables = {row[0] for row in result}
    assert EXPECTED_TABLES.issubset(tables), (
        f"Missing tables: {EXPECTED_TABLES - tables}"
    )


@pytest.mark.asyncio
async def test_indexes_exist(engine):
    """Required indexes must exist on draft_items."""
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT indexname FROM pg_indexes "
                "WHERE tablename = 'draft_items'"
            )
        )
        indexes = {row[0] for row in result}
    assert EXPECTED_INDEXES.issubset(indexes), (
        f"Missing indexes: {EXPECTED_INDEXES - indexes}"
    )


@pytest.mark.asyncio
async def test_migration_current(engine):
    """alembic_version table must exist and contain '0001' (head)."""
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT version_num FROM alembic_version")
        )
        version = result.scalar()
    assert version == "0001", f"Expected '0001', got '{version}'"


@pytest.mark.asyncio
async def test_draft_status_enum_exists(engine):
    """PostgreSQL type 'draftstatus' must exist with all 5 values."""
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT enumlabel FROM pg_enum "
                "JOIN pg_type ON pg_enum.enumtypid = pg_type.oid "
                "WHERE pg_type.typname = 'draftstatus' "
                "ORDER BY enumsortorder"
            )
        )
        values = [row[0] for row in result]
    expected = ["pending", "approved", "edited_approved", "rejected", "expired"]
    assert values == expected, f"DraftStatus values: {values}"
