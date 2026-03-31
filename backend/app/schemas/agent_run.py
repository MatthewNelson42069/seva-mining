from pydantic import BaseModel, ConfigDict
from datetime import datetime
from uuid import UUID
from typing import Optional, Any


class AgentRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    agent_name: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    items_found: Optional[int] = None
    items_queued: Optional[int] = None
    items_filtered: Optional[int] = None
    errors: Optional[Any] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
