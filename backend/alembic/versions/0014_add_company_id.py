"""Multi-tenant foundation — add company_id to 3 tenant-scoped tables.

Phase 9 (v3.0). Expand step of expand/contract pattern (PITFALLS.md HIGH-3):
- ADD COLUMN with server_default='seva' makes existing rows + concurrent
  cron writes both default to 'seva' atomically. No backfill UPDATE needed —
  Postgres applies the DEFAULT to every existing row inside the same DDL
  transaction, eliminating the backfill race entirely.
- DROP DEFAULT happens in a follow-up v3.0.1 migration once all callers
  (routers + cron agents) pass company_id explicitly.

Hand-written; NO --autogenerate (Pitfall MOD-2 — autogenerate would emit
spurious DDL against the ApprovalState enum from 0009). Mirrors the
hand-written discipline of 0010/0013.

CONCURRENTLY threshold ~100K rows; revisit at v3.x+. At v3.0's row counts
(~60 rows total across 3 tables) the inline op.create_index inside the
Alembic transaction completes in microseconds; CONCURRENTLY would force
per-statement transactions and break the atomic guarantee.

After downgrade, the company_id column is dropped — Juno rows become
indistinguishable from Seva rows. Operator must manually
``DELETE FROM <table> WHERE company_id='juno'`` BEFORE downgrade if a
clean v2.1 rollback is desired (documented in PR description + this docstring).

Revision ID: 0014
Revises: 0013
Create Date: 2026-05-19
"""
import sqlalchemy as sa

from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. ADD COLUMN with server_default='seva' AND nullable=False in one ALTER.
    #    Postgres applies the default to all existing rows during the ALTER
    #    (atomic — no separate UPDATE backfill, eliminates HIGH-3 race window).
    #    Any cron INSERT during the deploy also gets 'seva' via the same DEFAULT.
    for table in ("daily_summaries", "calendar_items", "weekly_sweeps"):
        op.add_column(
            table,
            sa.Column(
                "company_id",
                sa.String(length=20),
                nullable=False,
                server_default="seva",
            ),
        )

    # 2. CHECK constraint enumerating valid tenants (D-03 — hardcoded list).
    #    Keep in lockstep with ACTIVE_COMPANIES in backend/app/companies/__init__.py.
    #    Naming convention in app/models/base.py is `ck_%(table_name)s_%(constraint_name)s`,
    #    so passing constraint_name="company_id" yields the final name
    #    `ck_<table>_company_id`. Do NOT pre-prefix or the convention double-prefixes.
    for table in ("daily_summaries", "calendar_items", "weekly_sweeps"):
        op.create_check_constraint(
            "company_id",
            table,
            "company_id IN ('seva', 'juno')",
        )

    # 3. Composite indexes — company_id LEADS every multi-tenant index.
    #    Drop old single-column indexes that no longer match the query shape.
    #    Note on CREATE INDEX CONCURRENTLY: not used — see module docstring.

    # daily_summaries: replace ix_daily_summaries_generated_at with composite
    op.drop_index("ix_daily_summaries_generated_at", table_name="daily_summaries")
    op.create_index(
        "ix_daily_summaries_company_generated",
        "daily_summaries",
        ["company_id", sa.text("generated_at DESC")],
    )

    # calendar_items: replace uq_calendar_items_date with composite UNIQUE +
    # add a composite index leading with company_id for the calendar tab queries.
    op.drop_constraint("uq_calendar_items_date", "calendar_items", type_="unique")
    op.create_unique_constraint(
        "uq_calendar_items_company_date",
        "calendar_items",
        ["company_id", "date"],
    )
    op.create_index(
        "ix_calendar_items_company_date",
        "calendar_items",
        ["company_id", "date"],
    )

    # weekly_sweeps: replace ix_weekly_sweeps_generated_at with composite
    op.drop_index("ix_weekly_sweeps_generated_at", table_name="weekly_sweeps")
    op.create_index(
        "ix_weekly_sweeps_company_generated",
        "weekly_sweeps",
        ["company_id", sa.text("generated_at DESC")],
    )


def downgrade() -> None:
    # Reverse exact order. After downgrade, all rows lose the company_id
    # column — Juno rows become indistinguishable from Seva rows.
    op.drop_index("ix_weekly_sweeps_company_generated", table_name="weekly_sweeps")
    op.create_index(
        "ix_weekly_sweeps_generated_at",
        "weekly_sweeps",
        [sa.text("generated_at DESC")],
    )

    op.drop_index("ix_calendar_items_company_date", table_name="calendar_items")
    op.drop_constraint(
        "uq_calendar_items_company_date", "calendar_items", type_="unique"
    )
    op.create_unique_constraint(
        "uq_calendar_items_date", "calendar_items", ["date"]
    )

    op.drop_index(
        "ix_daily_summaries_company_generated", table_name="daily_summaries"
    )
    op.create_index(
        "ix_daily_summaries_generated_at", "daily_summaries", ["generated_at"]
    )

    for table in ("weekly_sweeps", "calendar_items", "daily_summaries"):
        # Naming convention auto-prefixes — pass just the constraint_name token.
        op.drop_constraint("company_id", table, type_="check")
        op.drop_column(table, "company_id")
