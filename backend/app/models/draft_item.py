import enum
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Numeric, Text, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB, ENUM
from app.models.base import Base


class DraftStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    edited_approved = "edited_approved"
    rejected = "rejected"
    expired = "expired"


# create_type=False because migration creates the type explicitly with CREATE TYPE (D-06, Pitfall 1)
draft_status_enum = ENUM(
    "pending", "approved", "edited_approved", "rejected", "expired",
    name="draftstatus",
    create_type=False,
)


class DraftItem(Base):
    __tablename__ = "draft_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    platform = Column(String(20), nullable=False)          # twitter, instagram, content
    status = Column(draft_status_enum, nullable=False, server_default="pending")
    source_url = Column(Text)
    source_text = Column(Text)
    source_account = Column(String(255))
    follower_count = Column(Numeric(12, 0))
    score = Column(Numeric(5, 2))
    quality_score = Column(Numeric(5, 2))
    alternatives = Column(JSONB, nullable=False, server_default="[]")  # D-07 JSONB array
    rationale = Column(Text)
    urgency = Column(String(20))
    related_id = Column(UUID(as_uuid=True), ForeignKey("draft_items.id"), nullable=True)
    rejection_reason = Column(Text)
    expires_at = Column(DateTime(timezone=True))
    decided_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), onupdate=datetime.utcnow)

    # Event mode fields (full schema from day one per D-03)
    event_mode = Column(String(20))
    engagement_snapshot = Column(JSONB)

    __table_args__ = (
        Index("ix_draft_items_status", "status"),       # D-08
        Index("ix_draft_items_platform", "platform"),   # D-08
        Index("ix_draft_items_created_at", "created_at"),  # D-08
        Index("ix_draft_items_expires_at", "expires_at"),  # D-08
    )
