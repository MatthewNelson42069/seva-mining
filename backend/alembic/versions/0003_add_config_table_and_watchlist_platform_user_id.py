"""Add config table and watchlists.platform_user_id column

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-01

Config table provides a key-value store for agent settings and quota counters.
platform_user_id on watchlists caches the Twitter numeric user ID, resolved lazily
by the Twitter agent to avoid repeated username-to-ID lookup API calls (TWIT-11).
Requirements: TWIT-01, TWIT-11, TWIT-12, TWIT-13
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Config table — key-value store for agent settings and quota counters
    op.create_table(
        "config",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Add platform_user_id to watchlists for Twitter numeric user ID caching
    op.add_column("watchlists", sa.Column("platform_user_id", sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column("watchlists", "platform_user_id")
    op.drop_table("config")
