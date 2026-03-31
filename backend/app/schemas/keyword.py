from pydantic import BaseModel, ConfigDict
from datetime import datetime
from uuid import UUID
from typing import Optional


class KeywordCreate(BaseModel):
    term: str
    platform: Optional[str] = None  # twitter, instagram, content, or null=all
    weight: float = 1.0
    active: bool = True


class KeywordUpdate(BaseModel):
    weight: Optional[float] = None
    active: Optional[bool] = None
    platform: Optional[str] = None


class KeywordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    term: str
    platform: Optional[str] = None
    weight: Optional[float] = None
    active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
