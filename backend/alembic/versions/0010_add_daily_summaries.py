"""Add daily_summaries table for v2.0 daily summary feed.

Phase 1, Plan 01 — Hand-written migration; NO --autogenerate (Pitfall MOD-2:
autogenerate risks emitting spurious DDL against the ApprovalState enum from
migration 0009). Only op.create_table + op.create_check_constraint + op.create_index.

Revision ID: 0010
Revises: 0009
Create Date: 2026-05-05
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "daily_summaries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_label", sa.String(length=20), nullable=False),
        sa.Column("gold_news_md", sa.Text(), nullable=True),
        sa.Column("ontario_law_md", sa.Text(), nullable=True),
        sa.Column("ontario_stats_md", sa.Text(), nullable=True),
        sa.Column("raw_sources_jsonb", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="completed"),
        sa.Column("error_text", sa.Text(), nullable=True),
        sa.Column("agent_run_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.text("now()")),
    )
    op.create_check_constraint(
        "ck_daily_summaries_status",
        "daily_summaries",
        "status IN ('completed', 'failed', 'partial')",
    )
    op.create_index(
        "ix_daily_summaries_generated_at",
        "daily_summaries",
        ["generated_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_daily_summaries_generated_at", table_name="daily_summaries")
    op.drop_constraint("ck_daily_summaries_status", "daily_summaries", type_="check")
    op.drop_table("daily_summaries")
