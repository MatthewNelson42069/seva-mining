"""add_edit_delta

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-31

Add edit_delta column to draft_items table to preserve original draft text
when operator edits a draft before approving (D-14).
Requirements: AUTH-01, AUTH-02, AUTH-03
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("draft_items", sa.Column("edit_delta", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("draft_items", "edit_delta")
