import uuid
from datetime import datetime

from sqlalchemy import Column, Date, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.models.base import Base


class WeeklySweep(Base):
    __tablename__ = "weekly_sweeps"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # v3.0 Phase 9 — TENANT-01 — multi-tenant column (per 09-CONTEXT.md D-03).
    company_id = Column(String(20), nullable=False, server_default="seva")
    generated_at = Column(DateTime(timezone=True), nullable=False)
    week_start = Column(Date, nullable=False)
    week_end = Column(Date, nullable=False)
    reddit_top_md = Column(Text, nullable=True)
    story_virality_md = Column(Text, nullable=True)
    content_angles_md = Column(Text, nullable=True)
    raw_sources_jsonb = Column(JSONB, nullable=True)
    status = Column(String(20), nullable=False, server_default="completed")
    error_text = Column(Text, nullable=True)
    agent_run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("agent_runs.id", ondelete="SET NULL"),
        nullable=True,
    )

    __table_args__ = (
        # v3.0 Phase 9 — composite index matches migration 0014.
        Index(
            "ix_weekly_sweeps_company_generated",
            "company_id",
            text("generated_at DESC"),
        ),
    )
