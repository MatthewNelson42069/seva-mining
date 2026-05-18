"""Add calendar_items table — v2.1 Phase 5 (DB-01).

Phase 5, Plan 02 — Hand-written; NO --autogenerate. Follows the template
pattern of 0010_add_daily_summaries.py (op.create_table + op.create_check_constraint
+ op.create_index, with downgrade in exact reverse order).

Per pitfall P2 (CRITICAL — TZ off-by-one): `date` column is sa.Date() (DAY only),
NOT sa.DateTime(). Postgres stores a calendar day with no timezone, preventing
UTC off-by-one bugs when a PT user creates an item near midnight local time
while the Railway server runs in UTC.

Revision ID: 0011
Revises: 0010
Create Date: 2026-05-18
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "calendar_items",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("notes_md", sa.Text(), nullable=True),
        sa.Column("tag", sa.String(length=20), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_check_constraint(
        "ck_calendar_items_tag",
        "calendar_items",
        "tag IN ('thread', 'video', 'podcast', 'tweet', 'idea', 'other')",
    )
    op.create_index(
        "ix_calendar_items_date",
        "calendar_items",
        ["date"],
    )


def downgrade() -> None:
    op.drop_index("ix_calendar_items_date", table_name="calendar_items")
    op.drop_constraint("ck_calendar_items_tag", "calendar_items", type_="check")
    op.drop_table("calendar_items")
