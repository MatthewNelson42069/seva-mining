"""Make calendar_items.title nullable and add UNIQUE(date) — v2.1 Phase 6 (CAL schema reconciliation).

Phase 6, Plan 01. Reconciles the locked Phase 5 schema with the simplified
single-text-blob-per-day model from 06-CONTEXT.md decisions D-02 (single row
per date) and D-06 (Option A: migration). After this migration:
  - title is nullable (the user's text body lives in notes_md; title is
    unused under the new contract and may be left NULL forever)
  - calendar_items has UNIQUE(date) so the app contract "one row per date"
    is enforced at the DB level (defense-in-depth against double-POST)

Revision ID: 0013
Revises: 0012
Create Date: 2026-05-18
"""
import sqlalchemy as sa

from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "calendar_items",
        "title",
        existing_type=sa.Text(),
        nullable=True,
    )
    op.create_unique_constraint(
        "uq_calendar_items_date",
        "calendar_items",
        ["date"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_calendar_items_date",
        "calendar_items",
        type_="unique",
    )
    op.alter_column(
        "calendar_items",
        "title",
        existing_type=sa.Text(),
        nullable=False,
    )
