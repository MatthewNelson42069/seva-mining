import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Text, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from models.base import Base


class AgentRun(Base):
    """Mirror of backend/app/models/agent_run.py for the scheduler worker."""

    __tablename__ = "agent_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_name = Column(String(50), nullable=False)       # twitter_agent, instagram_agent, etc.
    started_at = Column(DateTime(timezone=True), nullable=False)
    ended_at = Column(DateTime(timezone=True))
    items_found = Column(Integer, server_default="0")
    items_queued = Column(Integer, server_default="0")
    items_filtered = Column(Integer, server_default="0")
    errors = Column(JSONB)                                # array of error strings
    status = Column(String(20))                           # running, completed, failed
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_agent_runs_agent_name", "agent_name"),
        Index("ix_agent_runs_created_at", "created_at"),
    )
