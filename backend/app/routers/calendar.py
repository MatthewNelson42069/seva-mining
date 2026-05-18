"""Calendar router stub — v2.1 Phase 5 (DB-04).

Phase 5 deliverable: GET /calendar returns empty payload (200 OK) so the
frontend tab shell can confirm the auth-gated endpoint registration before
Phase 6 ships full CRUD. POST/PATCH/DELETE are NOT stubbed here — Phase 6
replaces this file with the full router.

Auth: router-level `Depends(get_current_user)` matches summaries.py pattern;
all routes inherit JWT gate.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user

router = APIRouter(
    prefix="/calendar",
    tags=["calendar"],
    dependencies=[Depends(get_current_user)],
)


@router.get("")
async def list_calendar_items(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Phase 5 stub — returns empty payload. Full implementation in Phase 6 (CAL-01)."""
    return {"items": [], "total": 0}
