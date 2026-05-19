"""Weekly sweeps router — v2.1 Phase 7 (SWEEP-12).

Replaces the Phase 5 stub (`/weekly-sweeps` returning {sweeps:[], total:0})
with the full read route: GET /weekly-sweeps?limit=12 returns the latest
weekly sweep cards ordered by generated_at DESC.

Auth: router-level `Depends(get_current_user)` matches summaries.py pattern.
Query param: limit clamped ge=1 le=52 (FastAPI auto-422 on out-of-range).
Default limit: 12 (~3 months of weekly sweeps — matches D-18 from 07-CONTEXT.md).
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.weekly_sweep import WeeklySweep
from app.schemas.weekly_sweep import WeeklySweepCard, WeeklySweepFeedResponse

router = APIRouter(
    prefix="/weekly-sweeps",
    tags=["weekly-sweeps"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=WeeklySweepFeedResponse)
async def list_weekly_sweeps(
    limit: int = Query(default=12, ge=1, le=52),
    db: AsyncSession = Depends(get_db),
) -> WeeklySweepFeedResponse:
    """Return the latest `limit` weekly sweeps ordered by generated_at DESC.

    SWEEP-12: limit clamped ge=1 le=52. Default 12. Auth-gated at router level.
    Returns total = COUNT(*) of all weekly_sweeps rows (NOT the returned count),
    so the frontend can show "showing 10 of 47" pagination labels later if needed.
    """
    # Most-recent-first row fetch
    stmt = (
        select(WeeklySweep)
        .order_by(WeeklySweep.generated_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()

    # Total count (not limit-bounded — matches summaries.py pattern for pagination)
    count_stmt = select(func.count()).select_from(WeeklySweep)
    count_result = await db.execute(count_stmt)
    total = count_result.scalar_one()

    cards = [WeeklySweepCard.model_validate(row, from_attributes=True) for row in rows]
    return WeeklySweepFeedResponse(sweeps=cards, total=total)
