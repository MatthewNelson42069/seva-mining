"""Add weekly_sweeps table — v2.1 Phase 5 (DB-02).

Phase 5, Plan 02 — Hand-written; NO --autogenerate. Follows the template
pattern of 0010_add_daily_summaries.py. Chains off 0011_add_calendar_items
(down_revision = "0011"), not 0010.

Per pitfall P_DB_FK_NULL (MEDIUM): `agent_run_id` FK uses ondelete="SET NULL"
so manual cleanup of agent_runs rows preserves the weekly_sweeps content
(mirrors daily_summaries.agent_run_id behavior).

Revision ID: 0012
Revises: 0011
Create Date: 2026-05-18
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "weekly_sweeps",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("week_end", sa.Date(), nullable=False),
        sa.Column("reddit_top_md", sa.Text(), nullable=True),
        sa.Column("story_virality_md", sa.Text(), nullable=True),
        sa.Column("content_angles_md", sa.Text(), nullable=True),
        sa.Column(
            "raw_sources_jsonb",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="completed",
        ),
        sa.Column("error_text", sa.Text(), nullable=True),
        sa.Column(
            "agent_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_check_constraint(
        "ck_weekly_sweeps_status",
        "weekly_sweeps",
        "status IN ('completed', 'failed', 'partial')",
    )
    # P-DB-02 spec: index on (generated_at DESC) — Phase 7 queries
    # ORDER BY generated_at DESC; descending index is more efficient.
    op.create_index(
        "ix_weekly_sweeps_generated_at",
        "weekly_sweeps",
        [sa.text("generated_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_weekly_sweeps_generated_at", table_name="weekly_sweeps")
    op.drop_constraint("ck_weekly_sweeps_status", "weekly_sweeps", type_="check")
    op.drop_table("weekly_sweeps")
