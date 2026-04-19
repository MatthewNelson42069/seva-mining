"""initial_schema

Revision ID: 0001
Revises:
Create Date: 2026-03-30

Full schema for Seva Mining AI Social Media Agency.
Creates all 6 tables with JSONB columns, draftstatus enum, and indexes.
Requirements: INFRA-01, INFRA-02, INFRA-06
Decisions: D-03, D-06, D-07, D-08
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # === STEP 1: Create PostgreSQL enum type BEFORE any table that uses it ===
    # (D-06, Pitfall 1 — must use op.execute, not ENUM(create_type=True))
    op.execute(
        "CREATE TYPE draftstatus AS ENUM "
        "('pending', 'approved', 'edited_approved', 'rejected', 'expired')"
    )

    # === STEP 2: Create draft_items table ===
    op.create_table(
        "draft_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("platform", sa.String(20), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending", "approved", "edited_approved", "rejected", "expired",
                name="draftstatus",
                create_type=False,   # already created above
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("source_text", sa.Text(), nullable=True),
        sa.Column("source_account", sa.String(255), nullable=True),
        sa.Column("follower_count", sa.Numeric(12, 0), nullable=True),
        sa.Column("score", sa.Numeric(5, 2), nullable=True),
        sa.Column("quality_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("alternatives", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("urgency", sa.String(20), nullable=True),
        sa.Column("related_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("event_mode", sa.String(20), nullable=True),
        sa.Column("engagement_snapshot", postgresql.JSONB(), nullable=True),
        sa.ForeignKeyConstraint(
            ["related_id"], ["draft_items.id"],
            name="fk_draft_items_related_id_draft_items",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_draft_items"),
    )
    # Indexes on draft_items (D-08, INFRA-02)
    op.create_index("ix_draft_items_status", "draft_items", ["status"])
    op.create_index("ix_draft_items_platform", "draft_items", ["platform"])
    op.create_index("ix_draft_items_created_at", "draft_items", ["created_at"])
    op.create_index("ix_draft_items_expires_at", "draft_items", ["expires_at"])

    # === STEP 3: Create content_bundles table ===
    op.create_table(
        "content_bundles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("story_headline", sa.Text(), nullable=False),
        sa.Column("story_url", sa.Text(), nullable=True),
        sa.Column("source_name", sa.String(255), nullable=True),
        sa.Column("format_type", sa.String(50), nullable=True),
        sa.Column("score", sa.Numeric(5, 2), nullable=True),
        sa.Column("quality_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("no_story_flag", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deep_research", postgresql.JSONB(), nullable=True),
        sa.Column("draft_content", postgresql.JSONB(), nullable=True),
        sa.Column("compliance_passed", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_content_bundles"),
    )
    op.create_index("ix_content_bundles_created_at", "content_bundles", ["created_at"])

    # === STEP 4: Create agent_runs table ===
    op.create_table(
        "agent_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_name", sa.String(50), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("items_found", sa.Integer(), server_default="0"),
        sa.Column("items_queued", sa.Integer(), server_default="0"),
        sa.Column("items_filtered", sa.Integer(), server_default="0"),
        sa.Column("errors", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.String(20), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_agent_runs"),
    )
    op.create_index("ix_agent_runs_agent_name", "agent_runs", ["agent_name"])
    op.create_index("ix_agent_runs_created_at", "agent_runs", ["created_at"])

    # === STEP 5: Create daily_digests table ===
    op.create_table(
        "daily_digests",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("digest_date", sa.Date(), nullable=False),
        sa.Column("top_stories", postgresql.JSONB(), nullable=True),
        sa.Column("queue_snapshot", postgresql.JSONB(), nullable=True),
        sa.Column("yesterday_approved", postgresql.JSONB(), nullable=True),
        sa.Column("yesterday_rejected", postgresql.JSONB(), nullable=True),
        sa.Column("yesterday_expired", postgresql.JSONB(), nullable=True),
        sa.Column("priority_alert", postgresql.JSONB(), nullable=True),
        sa.Column("whatsapp_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_daily_digests"),
        sa.UniqueConstraint("digest_date", name="uq_daily_digests_digest_date"),
    )
    op.create_index("ix_daily_digests_digest_date", "daily_digests", ["digest_date"])

    # === STEP 6: Create watchlists table ===
    op.create_table(
        "watchlists",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("platform", sa.String(20), nullable=False),
        sa.Column("account_handle", sa.String(255), nullable=False),
        sa.Column("relationship_value", sa.Integer(), nullable=True),
        sa.Column("follower_threshold", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_watchlists"),
    )

    # === STEP 7: Create keywords table ===
    op.create_table(
        "keywords",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("term", sa.String(255), nullable=False),
        sa.Column("platform", sa.String(20), nullable=True),
        sa.Column("weight", sa.Numeric(4, 2), server_default="1.0"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_keywords"),
    )


def downgrade() -> None:
    # Drop in reverse order of creation (dependencies first)
    op.drop_table("keywords")
    op.drop_table("watchlists")
    op.drop_table("daily_digests")
    op.drop_table("agent_runs")
    op.drop_table("content_bundles")
    op.drop_table("draft_items")
    op.execute("DROP TYPE draftstatus")
