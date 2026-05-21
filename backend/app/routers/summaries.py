"""GET /api/{company}/summaries — v3.0 daily summary feed read endpoint.

v3.0 Phase 9 (TENANT-04 / TENANT-10) — refactored to use the
multi-tenant URL prefix + `get_current_company` dependency + the
`scoped_summaries(company)` query helper. The router is mounted under
`/api/{company}` in main.py.

Auth-gated at router level (mirrors digests.py — single-user JWT contract).
Returns up to 120 rows ordered by generated_at DESC, scoped to the tenant
identified by the `:company` path parameter.

Requirements: FEED-05 (auth-gated read), TENANT-04 (multi-tenant prefix),
TENANT-10 (no cross-tenant leak).
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.companies import CompanyId
from app.database import get_db
from app.dependencies import get_current_company, get_current_session_token
from app.models.daily_summary import DailySummary
from app.queries.scoped import scoped_summaries
from app.schemas.daily_summary import SummaryCardResponse, SummaryFeedResponse

router = APIRouter(
    prefix="/summaries",  # /api/{company} prefix added by main.py include_router
    tags=["summaries"],
    dependencies=[Depends(get_current_session_token)],  # FEED-05 — router-level auth
)


@router.get("", response_model=SummaryFeedResponse)
async def list_summaries(
    limit: int = Query(60, ge=1, le=120),
    db: AsyncSession = Depends(get_db),
    company: CompanyId = Depends(get_current_company),
) -> SummaryFeedResponse:
    """Return up to `limit` summaries for `company` ordered by generated_at DESC.

    30-day retention × 2 fires/day = 60 rows max in steady state. The 120
    ceiling exists for forensic convenience without exposing an unbounded
    list. The `company` path parameter scopes every row via the
    `scoped_summaries(company)` helper.
    """
    stmt = (
        scoped_summaries(company)
        .order_by(DailySummary.generated_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()
    cards = [SummaryCardResponse.model_validate(r) for r in rows]
    return SummaryFeedResponse(summaries=cards, total=len(cards))
