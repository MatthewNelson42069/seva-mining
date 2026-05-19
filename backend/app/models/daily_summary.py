import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.models.base import Base


class DailySummary(Base):
    __tablename__ = "daily_summaries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # v3.0 Phase 9 — TENANT-01 — multi-tenant column (per 09-CONTEXT.md D-03).
    # Postgres applies server_default='seva' on INSERTs that omit this column
    # (defence-in-depth on top of explicit company_id passed by callers).
    company_id = Column(String(20), nullable=False, server_default="seva")
    generated_at = Column(DateTime(timezone=True), nullable=False)
    period_label = Column(String(20), nullable=False)  # '08:00 PT' | '12:00 PT'
    gold_news_md = Column(Text, nullable=True)
    ontario_law_md = Column(Text, nullable=True)
    ontario_stats_md = Column(Text, nullable=True)
    raw_sources_jsonb = Column(JSONB, nullable=True)
    status = Column(String(20), nullable=False, server_default="completed")
    error_text = Column(Text, nullable=True)
    agent_run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("agent_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    __table_args__ = (
        # v3.0 Phase 9 — composite index matches migration 0014.
        Index(
            "ix_daily_summaries_company_generated",
            "company_id",
            text("generated_at DESC"),
        ),
    )
