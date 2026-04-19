from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DraftStatusEnum(StrEnum):
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
    source_url: str | None = None
    source_text: str | None = None
    source_account: str | None = None
    follower_count: float | None = None
    score: float | None = None
    quality_score: float | None = None
    alternatives: list = []
    rationale: str | None = None
    urgency: str | None = None
    related_id: UUID | None = None
    rejection_reason: str | None = None
    edit_delta: str | None = None
    expires_at: datetime | None = None
    decided_at: datetime | None = None
    created_at: datetime
    updated_at: datetime | None = None
    engagement_snapshot: Any | None = None  # Phase 11: exposes content_bundle_id to frontend


class ApproveRequest(BaseModel):
    edited_text: str | None = None  # per D-05: optional inline edit on approve


class RejectRequest(BaseModel):
    category: str  # per D-12: off-topic, low-quality, bad-timing, tone-wrong, duplicate
    notes: str | None = None  # per D-12: optional free-text


class QueueListResponse(BaseModel):
    items: list[DraftItemResponse]
    next_cursor: str | None = None  # per D-02: base64 encoded created_at:id
