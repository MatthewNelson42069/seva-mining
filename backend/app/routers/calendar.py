"""Calendar router — v2.1 Phase 6 + v3.0 Phase 9 multi-tenant refactor.

Mounted under `/api/{company}` in main.py (TENANT-04). Endpoints:
  - GET    /api/{company}/calendar?start=YYYY-MM-DD&end=YYYY-MM-DD   -> CalendarRangeResponse
  - POST   /api/{company}/calendar                                    -> 201 + CalendarItemResponse
  - PATCH  /api/{company}/calendar/{item_id}                          -> 200 + CalendarItemResponse
  - DELETE /api/{company}/calendar/{item_id}                          -> 204 No Content

Auth: router-level Depends(get_current_session_token), mirroring summaries.py.
Tenant scope: per-endpoint `company: CompanyId = Depends(get_current_company)`.
Every query is routed through `scoped_calendar(company)` so the CI grep gate
(`scripts/verify-tenant-isolation.sh`) finds zero raw select-of-CalendarItem
call sites in this module. PATCH + DELETE re-look-up the row via the scoped
SELECT BEFORE mutating so an operator on `/seva/...` cannot accidentally
mutate a Juno row by guessing the UUID (defence-in-depth on top of URL prefix).

Pitfall defenses:
  - P1 (DATE vs DateTime TZ off-by-one): start/end are datetime.date parsed
    from YYYY-MM-DD strings; SQLAlchemy column is Date; round-trip is TZ-free.
  - P4 (updated_at not set on PATCH): the PATCH handler explicitly assigns
    item.updated_at = datetime.utcnow() BEFORE commit. CalendarItemUpdate
    does NOT expose updated_at.
  - D-02 single-row-per-date: enforced by UNIQUE(company_id, date) from
    migration 0014. POST raises IntegrityError -> 409 with descriptive detail.

Serialization note:
  All response-returning routes set `response_model_by_alias=False` so that
  `CalendarItemResponse.body` is emitted as `body` in JSON (its field name)
  rather than `notes_md` (its alias). The alias exists so Pydantic can
  read from the ORM column `notes_md` via `populate_by_name=True`, but the
  API contract surfaces it as `body` — the user-facing field name.
"""
import uuid
from datetime import date as date_type
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.companies import CompanyId
from app.database import get_db
from app.dependencies import get_current_company, get_current_session_token
from app.models.calendar_item import CalendarItem
from app.queries.scoped import scoped_calendar
from app.schemas.calendar import (
    CalendarItemCreate,
    CalendarItemResponse,
    CalendarItemUpdate,
    CalendarRangeResponse,
)

router = APIRouter(
    prefix="/calendar",  # /api/{company} prefix added by main.py include_router
    tags=["calendar"],
    dependencies=[Depends(get_current_session_token)],
)


@router.get("", response_model=CalendarRangeResponse, response_model_by_alias=False)
async def list_calendar_items(
    start: date_type = Query(..., description="Inclusive start date (YYYY-MM-DD)"),
    end: date_type = Query(..., description="Inclusive end date (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db),
    company: CompanyId = Depends(get_current_company),
) -> CalendarRangeResponse:
    """Return calendar items in [start, end] ordered by date ASC (CAL-01),
    scoped to `company`.
    """
    stmt = (
        scoped_calendar(company)
        .where(CalendarItem.date >= start)
        .where(CalendarItem.date <= end)
        .order_by(CalendarItem.date.asc())
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()
    items = [CalendarItemResponse.model_validate(r) for r in rows]
    return CalendarRangeResponse(items=items, total=len(items))


@router.post(
    "",
    response_model=CalendarItemResponse,
    status_code=status.HTTP_201_CREATED,
    response_model_by_alias=False,
)
async def create_calendar_item(
    payload: CalendarItemCreate,
    db: AsyncSession = Depends(get_db),
    company: CompanyId = Depends(get_current_company),
) -> CalendarItemResponse:
    """Create a new calendar item under `company` (CAL-02). Body text goes
    into notes_md. Server-side `company_id` is sourced from the URL — the
    client cannot override it.
    """
    now = datetime.utcnow()
    item = CalendarItem(
        company_id=company,
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


@router.patch(
    "/{item_id}",
    response_model=CalendarItemResponse,
    response_model_by_alias=False,
)
async def update_calendar_item(
    item_id: uuid.UUID,
    payload: CalendarItemUpdate,
    db: AsyncSession = Depends(get_db),
    company: CompanyId = Depends(get_current_company),
) -> CalendarItemResponse:
    """Update an existing calendar item body (CAL-03), tenant-scoped.

    Look up the row via `scoped_calendar(company)` so an operator on
    `/seva/...` cannot PATCH a Juno row even if they guess its UUID
    (defence-in-depth on top of the URL prefix).

    P4 defense: handler MUST set updated_at explicitly. CalendarItemUpdate
    deliberately does NOT expose updated_at.
    """
    stmt = scoped_calendar(company).where(CalendarItem.id == item_id)
    result = await db.execute(stmt)
    item = result.scalar_one_or_none()
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
    company: CompanyId = Depends(get_current_company),
) -> Response:
    """Hard-delete a calendar item (CAL-04), tenant-scoped.

    Look up the row via `scoped_calendar(company)` so cross-tenant deletes
    return 404 — same defence-in-depth as PATCH.
    """
    stmt = scoped_calendar(company).where(CalendarItem.id == item_id)
    result = await db.execute(stmt)
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Calendar item not found",
        )
    await db.delete(item)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
