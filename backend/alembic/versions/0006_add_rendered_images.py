"""Add rendered_images JSONB column to content_bundles

Revision ID: 0006
Revises: 0005
Create Date: 2026-04-16
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "content_bundles",
        sa.Column("rendered_images", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("content_bundles", "rendered_images")
