"""Add market_snapshots table for real-time data snapshot caching (quick-260420-oa1)

Revision ID: 0007
Revises: 0006
Create Date: 2026-04-21
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "market_snapshots",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("data", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("error_detail", postgresql.JSONB(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_market_snapshots"),
        sa.CheckConstraint(
            "status IN ('ok','partial','failed')",
            name="ck_market_snapshots_status",
        ),
    )
    op.create_index(
        "ix_market_snapshots_fetched_at",
        "market_snapshots",
        ["fetched_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_market_snapshots_fetched_at", table_name="market_snapshots")
    op.drop_table("market_snapshots")
