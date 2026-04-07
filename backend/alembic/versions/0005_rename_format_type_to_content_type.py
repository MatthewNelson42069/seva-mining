"""Rename format_type to content_type on content_bundles table

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-07

Renames the format_type column to content_type on the content_bundles table.
The expanded 7-format content type system uses content_type as the canonical
field name. All models, schemas, agents, and frontend code reference content_type.
Requirements: CONT-09
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("content_bundles", "format_type", new_column_name="content_type")


def downgrade() -> None:
    op.alter_column("content_bundles", "content_type", new_column_name="format_type")
