import uuid
from datetime import datetime
from sqlalchemy import Column, String, Numeric, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from models.base import Base


class Keyword(Base):
    __tablename__ = "keywords"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    term = Column(String(255), nullable=False)
    platform = Column(String(20))                     # twitter, instagram, content, or null=all
    weight = Column(Numeric(4, 2), server_default="1.0")
    active = Column(Boolean, nullable=False, server_default="true")
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), onupdate=datetime.utcnow)
