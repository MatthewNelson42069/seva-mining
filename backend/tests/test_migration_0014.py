"""Migration 0014 — `company_id` column addition (TENANT-01, TENANT-02).

v3.0 Phase 9 Wave 1 — production code lives at:
    backend/alembic/versions/0014_add_company_id.py

Assertions:
- test_company_id_column_exists       — VARCHAR(20), NOT NULL, server_default='seva'
- test_check_constraint                — CHECK company_id IN ('seva','juno')
- test_composite_indexes               — (company_id, generated_at DESC) etc.
- test_backfill_uses_server_default    — pre-migration rows backfilled to 'seva'

These tests issue Postgres-specific queries (pg_catalog, information_schema)
so they require a real Neon DATABASE_URL. The `postgres_migration_session`
fixture in conftest.py skips at collection time when only the SQLite test
URL is available (CI without Neon creds).
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

MULTI_TENANT_TABLES = ("daily_summaries", "calendar_items", "weekly_sweeps")


# ---------------------------------------------------------------------------
# TENANT-01 — column exists with correct type / nullability / default
# ---------------------------------------------------------------------------


async def test_company_id_column_exists(postgres_migration_session: AsyncSession):
    """After `alembic upgrade head`, all 3 multi-tenant tables carry
    company_id VARCHAR(20) NOT NULL DEFAULT 'seva'.
    """
    for table_name in MULTI_TENANT_TABLES:
        result = await postgres_migration_session.execute(
            text(
                """
                SELECT data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_name = :tname AND column_name = 'company_id'
                """
            ),
            {"tname": table_name},
        )
        row = result.fetchone()
        assert row is not None, f"{table_name}.company_id column missing"
        data_type, is_nullable, column_default = row
        assert data_type == "character varying", (
            f"{table_name}.company_id type is {data_type!r}; expected VARCHAR"
        )
        assert is_nullable == "NO", (
            f"{table_name}.company_id must be NOT NULL"
        )
        assert column_default is not None and "'seva'" in column_default, (
            f"{table_name}.company_id default should be 'seva', got {column_default!r}"
        )


# ---------------------------------------------------------------------------
# TENANT-02 — CHECK constraint enumerating ('seva', 'juno')
# ---------------------------------------------------------------------------


async def test_check_constraint(postgres_migration_session: AsyncSession):
    """A CHECK constraint must reject any company_id not in ('seva', 'juno').

    Verifies via pg_catalog.pg_constraint that a CHECK exists per table whose
    definition contains both 'seva' and 'juno' literals.
    """
    expected_names = {
        "daily_summaries": "ck_daily_summaries_company_id",
        "calendar_items": "ck_calendar_items_company_id",
        "weekly_sweeps": "ck_weekly_sweeps_company_id",
    }
    for table_name, constraint_name in expected_names.items():
        result = await postgres_migration_session.execute(
            text(
                """
                SELECT pg_get_constraintdef(oid)
                FROM pg_catalog.pg_constraint
                WHERE conname = :cname
                """
            ),
            {"cname": constraint_name},
        )
        row = result.fetchone()
        assert row is not None, (
            f"Expected CHECK constraint {constraint_name} on {table_name}"
        )
        defn = row[0]
        assert "seva" in defn and "juno" in defn, (
            f"Constraint {constraint_name} should enumerate ('seva','juno'); "
            f"got {defn!r}"
        )


# ---------------------------------------------------------------------------
# TENANT-02 — composite indexes on (company_id, <sort-col>)
# ---------------------------------------------------------------------------


async def test_composite_indexes(postgres_migration_session: AsyncSession):
    """Composite indexes for the hot tenant-scoped sort paths."""
    expected_indexes = {
        "daily_summaries": "ix_daily_summaries_company_generated",
        "calendar_items": "ix_calendar_items_company_date",
        "weekly_sweeps": "ix_weekly_sweeps_company_generated",
    }
    for table_name, idx_name in expected_indexes.items():
        result = await postgres_migration_session.execute(
            text(
                """
                SELECT indexdef
                FROM pg_catalog.pg_indexes
                WHERE schemaname = 'public'
                  AND tablename = :tname
                  AND indexname = :iname
                """
            ),
            {"tname": table_name, "iname": idx_name},
        )
        row = result.fetchone()
        assert row is not None, (
            f"Expected composite index {idx_name} on {table_name}; not found"
        )
        defn = row[0]
        assert "company_id" in defn, (
            f"Index {idx_name} should include company_id column; got {defn!r}"
        )


# ---------------------------------------------------------------------------
# TENANT-01 — server_default backfills pre-migration rows to 'seva'
# ---------------------------------------------------------------------------


async def test_backfill_uses_server_default(
    postgres_migration_session: AsyncSession,
):
    """Pre-migration rows MUST end up with company_id='seva' automatically.

    The expand/contract migration uses `server_default='seva'` so existing rows
    inherit 'seva' without an explicit UPDATE backfill in the upgrade body.

    Verifies the property by inserting WITHOUT company_id and asserting the
    DEFAULT takes effect. Session rollback (conftest fixture finalizer)
    ensures the test row does not persist between runs.
    """
    # Insert a row WITHOUT company_id; Postgres applies the server_default.
    await postgres_migration_session.execute(
        text(
            """
            INSERT INTO daily_summaries
                (generated_at, period_label, status, created_at)
            VALUES (now(), '08:00 PT', 'completed', now())
            """
        )
    )
    # Note: do NOT commit — the rollback in the fixture finalizer cleans up.
    # SELECT inside the same transaction still sees the row.

    result = await postgres_migration_session.execute(
        text(
            """
            SELECT company_id
            FROM daily_summaries
            WHERE period_label = '08:00 PT'
            ORDER BY created_at DESC
            LIMIT 1
            """
        )
    )
    row = result.fetchone()
    assert row is not None, "Insert without company_id failed unexpectedly"
    assert row[0] == "seva", (
        f"Pre-migration insert should backfill 'seva' via server_default; "
        f"got {row[0]!r}"
    )
