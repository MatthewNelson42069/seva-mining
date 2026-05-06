import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from models.base import Base


class DailySummary(Base):
    __tablename__ = "daily_summaries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
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
        Index("ix_daily_summaries_generated_at", "generated_at"),
    )
