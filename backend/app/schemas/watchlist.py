from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class WatchlistCreate(BaseModel):
    platform: str   # twitter or instagram
    account_handle: str
    relationship_value: int | None = None  # 1-5 for Twitter
    follower_threshold: int | None = None  # for Instagram
    notes: str | None = None
    active: bool = True


class WatchlistUpdate(BaseModel):
    relationship_value: int | None = None
    follower_threshold: int | None = None
    notes: str | None = None
    active: bool | None = None


class WatchlistResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    platform: str
    account_handle: str
    platform_user_id: str | None = None
    relationship_value: int | None = None
    follower_threshold: int | None = None
    notes: str | None = None
    active: bool
    created_at: datetime
    updated_at: datetime | None = None
