import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base


class Watchlist(Base):
    __tablename__ = "watchlists"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # content (historical: twitter/instagram purged)
    platform = Column(String(20), nullable=False)
    account_handle = Column(String(255), nullable=False)
    # Platform-native numeric user ID (legacy: Twitter user ID resolution); no longer populated
    platform_user_id = Column(String(50), nullable=True)
    relationship_value = Column(Integer)              # 1-5 relationship score (legacy SETT-01)
    follower_threshold = Column(Integer)              # legacy SETT-02 (Instagram purged 2026-04-19)
    notes = Column(Text)
    active = Column(Boolean, nullable=False, server_default="true")
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), onupdate=datetime.utcnow)
