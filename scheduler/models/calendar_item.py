import uuid
from datetime import datetime

from sqlalchemy import Column, Date, DateTime, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from models.base import Base


class CalendarItem(Base):
    __tablename__ = "calendar_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # v3.0 Phase 9 — TENANT-01 — multi-tenant column (per 09-CONTEXT.md D-03).
    company_id = Column(String(20), nullable=False, server_default="seva")
    date = Column(Date, nullable=False)
    title = Column(Text, nullable=True)
    notes_md = Column(Text, nullable=True)
    tag = Column(String(20), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    __table_args__ = (
        # v3.0 Phase 9 — TENANT-02 — composite UNIQUE matches migration 0014.
        Index("ix_calendar_items_company_date", "company_id", "date"),
        UniqueConstraint(
            "company_id", "date", name="uq_calendar_items_company_date"
        ),
    )
