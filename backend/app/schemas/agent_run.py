from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AgentRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    agent_name: str
    started_at: datetime
    ended_at: datetime | None = None
    items_found: int | None = None
    items_queued: int | None = None
    items_filtered: int | None = None
    errors: Any | None = None
    status: str | None = None
    notes: str | None = None
    created_at: datetime
