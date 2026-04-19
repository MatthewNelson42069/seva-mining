import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base


class Watchlist(Base):
    __tablename__ = "watchlists"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    platform = Column(String(20), nullable=False)     # twitter
    account_handle = Column(String(255), nullable=False)
    # Twitter numeric user ID, resolved lazily by agent
    platform_user_id = Column(String(50), nullable=True)
    relationship_value = Column(Integer)              # 1-5 for Twitter (SETT-01)
    follower_threshold = Column(Integer)              # for Instagram (SETT-02)
    notes = Column(Text)
    active = Column(Boolean, nullable=False, server_default="true")
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), onupdate=datetime.utcnow)
