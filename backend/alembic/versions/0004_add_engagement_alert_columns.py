"""Add engagement_alert_level and alerted_expiry_at columns to draft_items

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-02

engagement_alert_level tracks whether a WhatsApp engagement alert has been sent for
a draft item and at which threshold level (null = none sent, 'watchlist' = early signal
sent, 'viral' = viral alert sent). alerted_expiry_at records when an expiry alert was
dispatched to prevent duplicate sends for the same item.
Requirements: SENR-05, SENR-09, WHAT-02, WHAT-03
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # engagement_alert_level: null = no alert, 'watchlist' = first alert sent, 'viral' = viral alert sent
    op.add_column("draft_items", sa.Column("engagement_alert_level", sa.String(20), nullable=True))
    # alerted_expiry_at: timestamp when expiry alert was dispatched (dedup for WHAT-03)
    op.add_column("draft_items", sa.Column("alerted_expiry_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("draft_items", "alerted_expiry_at")
    op.drop_column("draft_items", "engagement_alert_level")
