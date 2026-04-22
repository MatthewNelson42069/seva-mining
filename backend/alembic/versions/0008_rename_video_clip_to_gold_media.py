"""Rename video_clip → gold_media in content_bundles.content_type and agent_runs.agent_name.

quick-260422-mfg.

Revision ID: 0008
Revises: 0007
Create Date: 2026-04-22
"""
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE content_bundles SET content_type = 'gold_media' "
        "WHERE content_type = 'video_clip'"
    )
    op.execute(
        "UPDATE agent_runs SET agent_name = 'sub_gold_media' "
        "WHERE agent_name = 'sub_video_clip'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE agent_runs SET agent_name = 'sub_video_clip' "
        "WHERE agent_name = 'sub_gold_media'"
    )
    op.execute(
        "UPDATE content_bundles SET content_type = 'video_clip' "
        "WHERE content_type = 'gold_media'"
    )
