"""
Tests for PostgreSQL schema correctness.
Covers: INFRA-01 (all 6 tables), INFRA-02 (indexes), INFRA-06 (Alembic at head)
These tests connect to the real Neon database via DATABASE_URL env var.
Skip if DATABASE_URL is not set (local dev without DB access).
"""
import os
import pytest


pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL not set — requires Neon connection"
)


@pytest.mark.asyncio
async def test_all_tables_exist():
    """
    All 6 tables must exist: draft_items, content_bundles, agent_runs,
    daily_digests, watchlists, keywords
    """
    pytest.skip("Requires Alembic migration applied — will be enabled in Plan 04")


@pytest.mark.asyncio
async def test_indexes_exist():
    """
    Indexes must exist on: draft_items.status, draft_items.platform,
    draft_items.created_at, draft_items.expires_at
    """
    pytest.skip("Requires Alembic migration applied — will be enabled in Plan 04")


@pytest.mark.asyncio
async def test_migration_current():
    """
    alembic current must equal alembic head (no pending migrations).
    """
    pytest.skip("Requires Alembic migration applied — will be enabled in Plan 04")


@pytest.mark.asyncio
async def test_draft_status_enum_exists():
    """
    PostgreSQL type 'draftstatus' must exist with values:
    pending, approved, edited_approved, rejected, expired
    """
    pytest.skip("Requires Alembic migration applied — will be enabled in Plan 04")
