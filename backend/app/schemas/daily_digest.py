from pydantic import BaseModel, ConfigDict
from datetime import date, datetime
from uuid import UUID
from typing import Optional, Any


class DailyDigestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    digest_date: date
    top_stories: Optional[Any] = None
    queue_snapshot: Optional[Any] = None
    yesterday_approved: Optional[Any] = None
    yesterday_rejected: Optional[Any] = None
    yesterday_expired: Optional[Any] = None
    priority_alert: Optional[Any] = None
    whatsapp_sent_at: Optional[datetime] = None
    created_at: datetime
