from pydantic import BaseModel, ConfigDict
from datetime import datetime
from uuid import UUID
from typing import Optional


class WatchlistCreate(BaseModel):
    platform: str   # twitter or instagram
    account_handle: str
    relationship_value: Optional[int] = None  # 1-5 for Twitter
    follower_threshold: Optional[int] = None  # for Instagram
    notes: Optional[str] = None
    active: bool = True


class WatchlistUpdate(BaseModel):
    relationship_value: Optional[int] = None
    follower_threshold: Optional[int] = None
    notes: Optional[str] = None
    active: Optional[bool] = None


class WatchlistResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    platform: str
    account_handle: str
    relationship_value: Optional[int] = None
    follower_threshold: Optional[int] = None
    notes: Optional[str] = None
    active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
