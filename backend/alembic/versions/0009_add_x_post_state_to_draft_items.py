"""Add Phase B X post-state columns to draft_items.

quick-260424-l0d.

Adds the 5 orthogonal columns + CHECK constraint + index needed for
user-initiated per-item approve→post-to-X (Phase B). All new columns are
orthogonal to the existing `status` column (which owns the dashboard
approve/reject lifecycle); `approval_state` owns the post-to-X result.

Revision ID: 0009
Revises: 0008
Create Date: 2026-04-24
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 5 new columns on draft_items
    op.add_column(
        "draft_items",
        sa.Column(
            "approval_state",
            sa.String(length=16),
            nullable=False,
            server_default="pending",
        ),
    )
    op.add_column(
        "draft_items",
        sa.Column("posted_tweet_id", sa.Text(), nullable=True),
    )
    op.add_column(
        "draft_items",
        sa.Column("posted_tweet_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "draft_items",
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "draft_items",
        sa.Column("post_error", sa.Text(), nullable=True),
    )

    # CHECK constraint (NOT a PG enum — easier to extend per CONTEXT.md D6 Claude's Discretion)
    op.create_check_constraint(
        "ck_draft_items_approval_state",
        "draft_items",
        "approval_state IN ('pending','posted','failed','discarded','posted_partial')",
    )

    # Index on the new column for cheap filtering by post state
    op.create_index(
        "ix_draft_items_approval_state",
        "draft_items",
        ["approval_state"],
    )


def downgrade() -> None:
    # Reverse order of upgrade
    op.drop_index("ix_draft_items_approval_state", table_name="draft_items")
    op.drop_constraint("ck_draft_items_approval_state", "draft_items", type_="check")
    op.drop_column("draft_items", "post_error")
    op.drop_column("draft_items", "posted_at")
    op.drop_column("draft_items", "posted_tweet_ids")
    op.drop_column("draft_items", "posted_tweet_id")
    op.drop_column("draft_items", "approval_state")
