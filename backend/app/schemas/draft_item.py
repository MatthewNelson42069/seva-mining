from pydantic import BaseModel, ConfigDict
from datetime import datetime
from uuid import UUID
from typing import Optional, Any
from enum import Enum


class DraftStatusEnum(str, Enum):
    pending = "pending"
    approved = "approved"
    edited_approved = "edited_approved"
    rejected = "rejected"
    expired = "expired"


class DraftItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    platform: str
    status: DraftStatusEnum
    source_url: Optional[str] = None
    source_text: Optional[str] = None
    source_account: Optional[str] = None
    follower_count: Optional[float] = None
    score: Optional[float] = None
    quality_score: Optional[float] = None
    alternatives: list = []
    rationale: Optional[str] = None
    urgency: Optional[str] = None
    related_id: Optional[UUID] = None
    rejection_reason: Optional[str] = None
    edit_delta: Optional[str] = None
    expires_at: Optional[datetime] = None
    decided_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    engagement_snapshot: Optional[Any] = None  # Phase 11: exposes content_bundle_id to frontend


class ApproveRequest(BaseModel):
    edited_text: Optional[str] = None  # per D-05: optional inline edit on approve


class RejectRequest(BaseModel):
    category: str  # per D-12: off-topic, low-quality, bad-timing, tone-wrong, duplicate
    notes: Optional[str] = None  # per D-12: optional free-text


class QueueListResponse(BaseModel):
    items: list[DraftItemResponse]
    next_cursor: Optional[str] = None  # per D-02: base64 encoded created_at:id
