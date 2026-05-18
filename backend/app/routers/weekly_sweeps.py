"""Weekly sweeps router stub — v2.1 Phase 5 (DB-04).

Phase 5 deliverable: GET /weekly-sweeps returns empty payload (200 OK) so
the frontend tab shell can confirm the auth-gated endpoint registration
before Phase 7 ships the full read route (SWEEP-12).

Auth: router-level `Depends(get_current_user)` matches summaries.py pattern.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user

router = APIRouter(
    prefix="/weekly-sweeps",
    tags=["weekly-sweeps"],
    dependencies=[Depends(get_current_user)],
)


@router.get("")
async def list_weekly_sweeps(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Phase 5 stub — returns empty payload. Full implementation in Phase 7 (SWEEP-12)."""
    return {"sweeps": [], "total": 0}
