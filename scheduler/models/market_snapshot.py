"""SQLAlchemy ORM model for market_snapshots table — quick-260420-oa1."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Column, DateTime, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID

from models.base import Base


class MarketSnapshot(Base):
    """Persisted market snapshot for audit and replay.

    Written once per content_agent cron cycle. Status CHECK constraint enforces
    the fail-open contract: ok | partial | failed.
    """

    __tablename__ = "market_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fetched_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    data = Column(JSONB, nullable=False)          # full snapshot payload (prices, yields, CPI)
    status = Column(String(16), nullable=False)   # ok | partial | failed
    error_detail = Column(JSONB, nullable=True)   # per-source error strings (nullable)

    __table_args__ = (
        CheckConstraint(
            "status IN ('ok','partial','failed')",
            name="ck_market_snapshots_status",
        ),
        Index("ix_market_snapshots_fetched_at", "fetched_at"),
    )
