import base64
import json
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.draft_item import DraftItem, DraftStatus
from app.schemas.draft_item import (
    ApproveRequest,
    DraftItemResponse,
    QueueListResponse,
    RejectRequest,
)

router = APIRouter(
    tags=["queue"],
    dependencies=[Depends(get_current_user)],
)

# D-11: Valid state transitions — only pending can be actioned
VALID_TRANSITIONS = {
    DraftStatus.pending: {
        DraftStatus.approved,
        DraftStatus.edited_approved,
        DraftStatus.rejected,
    },
}


def _decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    """Decode base64 cursor into (created_at, id) tuple."""
    decoded = base64.b64decode(cursor).decode()
    ts_str, id_str = decoded.rsplit(":", 1)
    return datetime.fromisoformat(ts_str), UUID(id_str)


def _encode_cursor(created_at: datetime, item_id: UUID) -> str:
    """Encode (created_at, id) into base64 cursor string."""
    raw = f"{created_at.isoformat()}:{item_id}"
    return base64.b64encode(raw.encode()).decode()


@router.get("/queue", response_model=QueueListResponse)
async def list_queue(
    platform: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    cursor: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List draft items with cursor-based pagination. Filterable by platform and status."""
    stmt = select(DraftItem)
    conditions = []

    if platform:
        conditions.append(DraftItem.platform == platform)
    if status_filter:
        conditions.append(DraftItem.status == status_filter)
    if cursor:
        cursor_ts, cursor_id = _decode_cursor(cursor)
        conditions.append(
            (DraftItem.created_at < cursor_ts)
            | (
                (DraftItem.created_at == cursor_ts)
                & (DraftItem.id < cursor_id)
            )
        )

    if conditions:
        stmt = stmt.where(and_(*conditions))

    stmt = stmt.order_by(DraftItem.created_at.desc(), DraftItem.id.desc())
    stmt = stmt.limit(limit + 1)

    result = await db.execute(stmt)
    items = list(result.scalars().all())

    next_cursor = None
    if len(items) > limit:
        items = items[:limit]
        last = items[-1]
        next_cursor = _encode_cursor(last.created_at, last.id)

    return QueueListResponse(
        items=[DraftItemResponse.model_validate(i) for i in items],
        next_cursor=next_cursor,
    )


async def _get_item_or_404(item_id: UUID, db: AsyncSession) -> DraftItem:
    """Fetch a DraftItem by ID or raise 404."""
    result = await db.execute(select(DraftItem).where(DraftItem.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    return item


async def _enforce_transition(item: DraftItem, target: DraftStatus) -> None:
    """Enforce state machine: raise 409 if transition from item.status to target is invalid."""
    allowed = VALID_TRANSITIONS.get(DraftStatus(item.status), set())
    if target not in allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot transition from '{item.status}' to '{target.value}'",
        )


@router.patch("/items/{item_id}/approve", response_model=DraftItemResponse)
async def approve_item(
    item_id: UUID,
    body: ApproveRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Approve a pending draft item.

    If body.edited_text is provided, transitions to edited_approved and stores
    the original first alternative in edit_delta (D-05, D-14).
    Otherwise transitions to approved.
    """
    item = await _get_item_or_404(item_id, db)

    if body and body.edited_text:
        # D-05 + D-14: inline edit + approve — store original first alternative
        await _enforce_transition(item, DraftStatus.edited_approved)
        original = item.alternatives[0] if item.alternatives else ""
        item.edit_delta = original if isinstance(original, str) else json.dumps(original)
        item.status = DraftStatus.edited_approved
    else:
        await _enforce_transition(item, DraftStatus.approved)
        item.status = DraftStatus.approved

    item.decided_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(item)
    return DraftItemResponse.model_validate(item)


@router.patch("/items/{item_id}/reject", response_model=DraftItemResponse)
async def reject_item(
    item_id: UUID,
    body: RejectRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Reject a pending draft item with mandatory structured reason (D-12).

    body.category is required; body.notes is optional free text.
    """
    item = await _get_item_or_404(item_id, db)
    await _enforce_transition(item, DraftStatus.rejected)

    item.status = DraftStatus.rejected
    item.rejection_reason = json.dumps({"category": body.category, "notes": body.notes})
    item.decided_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(item)
    return DraftItemResponse.model_validate(item)
