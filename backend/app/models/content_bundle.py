import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.models.base import Base


class ContentBundle(Base):
    __tablename__ = "content_bundles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    story_headline = Column(Text, nullable=False)
    story_url = Column(Text)
    source_name = Column(String(255))
    # thread, long_form, infographic, breaking_news, video_clip, quote, gold_history
    content_type = Column(String(50))
    score = Column(Numeric(5, 2))
    quality_score = Column(Numeric(5, 2))
    no_story_flag = Column(Boolean, nullable=False, server_default="false")
    deep_research = Column(JSONB)              # sources, key_data_points, corroborating_sources
    draft_content = Column(JSONB)              # format-specific draft output
    compliance_passed = Column(Boolean)
    rendered_images = Column(JSONB, nullable=True)   # array of {role, url, generated_at} — Phase 11
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_content_bundles_created_at", "created_at"),
    )
