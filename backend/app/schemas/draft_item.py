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


class ApprovalState(StrEnum):
    """Phase B (quick-260424-l0d): X post-state machine — orthogonal to DraftStatus.

    Stored in `draft_items.approval_state` (CHECK-constrained VARCHAR(16)).
    See CONTEXT.md D5 for the full state machine.
    """

    pending = "pending"
    posted = "posted"
    failed = "failed"
    discarded = "discarded"
    posted_partial = "posted_partial"


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
    # Phase B (quick-260424-l0d): X post-state surfaced to dashboard
    approval_state: ApprovalState | None = None
    posted_tweet_id: str | None = None
    posted_tweet_ids: list[str] | None = None
    posted_at: datetime | None = None
    post_error: str | None = None


class ApproveRequest(BaseModel):
    edited_text: str | None = None  # per D-05: optional inline edit on approve


class RejectRequest(BaseModel):
    category: str  # per D-12: off-topic, low-quality, bad-timing, tone-wrong, duplicate
    notes: str | None = None  # per D-12: optional free-text


class QueueListResponse(BaseModel):
    items: list[DraftItemResponse]
    next_cursor: str | None = None  # per D-02: base64 encoded created_at:id


class PostToXResponse(BaseModel):
    """Phase B (quick-260424-l0d): response from POST /items/{id}/post-to-x.

    Mirrors the post-state columns on draft_items, plus an `already_posted` flag
    that signals a no-op idempotent re-call. Full byte-for-byte fidelity per D13:
    posted_tweet_id is the canonical link target (first tweet for threads).
    """

    model_config = ConfigDict(from_attributes=True)

    approval_state: ApprovalState
    posted_tweet_id: str | None = None
    posted_tweet_ids: list[str] | None = None
    posted_at: datetime | None = None
    post_error: str | None = None
    already_posted: bool = False
