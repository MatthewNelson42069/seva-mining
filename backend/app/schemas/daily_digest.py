from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DailyDigestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    digest_date: date
    top_stories: Any | None = None
    queue_snapshot: Any | None = None
    yesterday_approved: Any | None = None
    yesterday_rejected: Any | None = None
    yesterday_expired: Any | None = None
    priority_alert: Any | None = None
    whatsapp_sent_at: datetime | None = None
    created_at: datetime
