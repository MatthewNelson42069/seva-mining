"""Calendar router — v2.1 Phase 6 full CRUD.

Replaces the Phase 5 stub. Implements:
  - GET    /calendar?start=YYYY-MM-DD&end=YYYY-MM-DD    -> CalendarRangeResponse
  - POST   /calendar                                     -> 201 + CalendarItemResponse
  - PATCH  /calendar/{item_id}                           -> 200 + CalendarItemResponse
  - DELETE /calendar/{item_id}                           -> 204 No Content

Auth: router-level Depends(get_current_user), mirroring summaries.py.

Pitfall defenses:
  - P1 (DATE vs DateTime TZ off-by-one): start/end are datetime.date parsed
    from YYYY-MM-DD strings; SQLAlchemy column is Date; round-trip is TZ-free.
  - P4 (updated_at not set on PATCH): the PATCH handler explicitly assigns
    item.updated_at = datetime.utcnow() BEFORE commit. CalendarItemUpdate
    does NOT expose updated_at.
  - D-02 single-row-per-date: enforced by UNIQUE(date) from migration 0013.
    POST raises IntegrityError -> 409 with descriptive detail.
"""
import uuid
from datetime import date as date_type
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.calendar_item import CalendarItem
from app.schemas.calendar import (
    CalendarItemCreate,
    CalendarItemResponse,
    CalendarItemUpdate,
    CalendarRangeResponse,
)

router = APIRouter(
    prefix="/calendar",
    tags=["calendar"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=CalendarRangeResponse)
async def list_calendar_items(
    start: date_type = Query(..., description="Inclusive start date (YYYY-MM-DD)"),
    end: date_type = Query(..., description="Inclusive end date (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db),
) -> CalendarRangeResponse:
    """Return calendar items in [start, end] ordered by date ASC (CAL-01)."""
    stmt = (
        select(CalendarItem)
        .where(CalendarItem.date >= start)
        .where(CalendarItem.date <= end)
        .order_by(CalendarItem.date.asc())
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()
    items = [CalendarItemResponse.model_validate(r) for r in rows]
    return CalendarRangeResponse(items=items, total=len(items))


@router.post("", response_model=CalendarItemResponse, status_code=status.HTTP_201_CREATED)
async def create_calendar_item(
    payload: CalendarItemCreate,
    db: AsyncSession = Depends(get_db),
) -> CalendarItemResponse:
    """Create a new calendar item (CAL-02). Body text goes into notes_md."""
    now = datetime.utcnow()
    item = CalendarItem(
        date=payload.date,
        title=None,
        notes_md=payload.body,
        tag=None,
        created_at=now,
        updated_at=now,
    )
    db.add(item)
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A calendar item already exists for date {payload.date.isoformat()}",
        ) from e
    await db.refresh(item)
    return CalendarItemResponse.model_validate(item)


@router.patch("/{item_id}", response_model=CalendarItemResponse)
async def update_calendar_item(
    item_id: uuid.UUID,
    payload: CalendarItemUpdate,
    db: AsyncSession = Depends(get_db),
) -> CalendarItemResponse:
    """Update an existing calendar item body (CAL-03).

    P4 defense: handler MUST set updated_at explicitly. CalendarItemUpdate
    deliberately does NOT expose updated_at.
    """
    item = await db.get(CalendarItem, item_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Calendar item not found",
        )
    item.notes_md = payload.body
    item.updated_at = datetime.utcnow()  # P4: explicit, NOT via DB trigger
    await db.commit()
    await db.refresh(item)
    return CalendarItemResponse.model_validate(item)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_calendar_item(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Hard-delete a calendar item (CAL-04). 204 on success, 404 on miss."""
    item = await db.get(CalendarItem, item_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Calendar item not found",
        )
    await db.delete(item)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
