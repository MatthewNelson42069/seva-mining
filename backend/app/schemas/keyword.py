from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class KeywordCreate(BaseModel):
    term: str
    platform: str | None = None  # twitter, content, or null=all
    weight: float = 1.0
    active: bool = True


class KeywordUpdate(BaseModel):
    weight: float | None = None
    active: bool | None = None
    platform: str | None = None


class KeywordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    term: str
    platform: str | None = None
    weight: float | None = None
    active: bool
    created_at: datetime
    updated_at: datetime | None = None
