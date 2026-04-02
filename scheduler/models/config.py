from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime
from models.base import Base


class Config(Base):
    """Key-value store for agent settings and quota counters.

    Used by TwitterAgent to track monthly tweet read quota (TWIT-11, TWIT-12).
    Keys used: twitter_monthly_tweet_count, twitter_monthly_reset_date,
               twitter_quota_safety_margin
    """
    __tablename__ = "config"

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
