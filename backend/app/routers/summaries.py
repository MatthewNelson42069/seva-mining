"""GET /summaries — v2.0 daily summary feed read endpoint.

Phase 1, Plan 04. Auth-gated at router level (mirrors digests.py — single-user
JWT contract). Returns up to 120 rows ordered by generated_at DESC.

Requirement: FEED-05 (auth-gated read).
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.daily_summary import DailySummary
from app.schemas.daily_summary import SummaryCardResponse, SummaryFeedResponse

router = APIRouter(
    prefix="/summaries",
    tags=["summaries"],
    dependencies=[Depends(get_current_user)],  # FEED-05 — router-level auth
)


@router.get("", response_model=SummaryFeedResponse)
async def list_summaries(
    limit: int = Query(60, ge=1, le=120),
    db: AsyncSession = Depends(get_db),
) -> SummaryFeedResponse:
    """Return up to `limit` summaries ordered by generated_at DESC.

    30-day retention × 2 fires/day = 60 rows max in steady state. The 120
    ceiling exists for forensic convenience without exposing an unbounded
    list.
    """
    stmt = (
        select(DailySummary)
        .order_by(DailySummary.generated_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()
    cards = [SummaryCardResponse.model_validate(r) for r in rows]
    return SummaryFeedResponse(summaries=cards, total=len(cards))
