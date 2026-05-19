import uuid
from datetime import datetime

from sqlalchemy import Column, Date, DateTime, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base


class CalendarItem(Base):
    __tablename__ = "calendar_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    date = Column(Date, nullable=False)
    title = Column(Text, nullable=True)
    notes_md = Column(Text, nullable=True)
    tag = Column(String(20), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_calendar_items_date", "date"),
        UniqueConstraint("date", name="uq_calendar_items_date"),
    )
