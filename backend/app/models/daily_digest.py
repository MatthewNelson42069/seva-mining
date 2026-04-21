import uuid
from datetime import datetime

from sqlalchemy import Column, Date, DateTime, Index
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.models.base import Base


class DailyDigest(Base):
    __tablename__ = "daily_digests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    digest_date = Column(Date, nullable=False, unique=True)
    top_stories = Column(JSONB)             # list of {headline, source, score}
    queue_snapshot = Column(JSONB)          # {content: N, total: N} (twitter/instagram purged)
    yesterday_approved = Column(JSONB)      # count + top items
    yesterday_rejected = Column(JSONB)      # count
    yesterday_expired = Column(JSONB)       # count
    priority_alert = Column(JSONB)          # highest-value queue item
    whatsapp_sent_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_daily_digests_digest_date", "digest_date"),
    )
