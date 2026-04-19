from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.daily_digest import DailyDigest
from app.models.draft_item import DraftItem
from app.schemas.daily_digest import DailyDigestResponse

router = APIRouter(
    prefix="/digests",
    tags=["digests"],
    dependencies=[Depends(get_current_user)],
)


class NewsStory(BaseModel):
    headline: str
    source: str | None = None
    time: str | None = None
    url: str | None = None
    score: float | None = None


@router.get("/news-feed", response_model=list[NewsStory])
async def get_news_feed(
    limit: int = Query(15, ge=1, le=50),
    hours: int = Query(24, ge=1, le=168),
    db: AsyncSession = Depends(get_db),
):
    """Return the top gold news stories ingested by the content agent in the last N hours.

    Queries DraftItem records directly (platform=content) so the response always
    reflects live ingested data rather than a stale stored digest snapshot.
    Ordered by score DESC then created_at DESC.
    """
    cutoff = datetime.now(UTC) - timedelta(hours=hours)
    stmt = (
        select(DraftItem)
        .where(
            DraftItem.platform == "content",
            DraftItem.created_at >= cutoff,
        )
        .order_by(DraftItem.score.desc().nullslast(), DraftItem.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    items = result.scalars().all()

    stories: list[NewsStory] = []
    seen_headlines: set[str] = set()
    for item in items:
        # source_text is the raw news headline from RSS/SerpAPI
        headline = (item.source_text or "").split("\n")[0].strip()
        if not headline:
            continue
        # Deduplicate by normalised headline (case-insensitive first 60 chars)
        key = headline.lower()[:60]
        if key in seen_headlines:
            continue
        seen_headlines.add(key)
        stories.append(NewsStory(
            headline=headline,
            source=item.source_account,
            time=item.created_at.isoformat() if item.created_at else None,
            url=item.source_url,
            score=float(item.score) if item.score is not None else None,
        ))

    return stories


@router.get("/latest", response_model=DailyDigestResponse)
async def get_latest_digest(db: AsyncSession = Depends(get_db)):
    """Return the most recent daily digest."""
    stmt = select(DailyDigest).order_by(DailyDigest.digest_date.desc()).limit(1)
    result = await db.execute(stmt)
    digest = result.scalar_one_or_none()
    if not digest:
        raise HTTPException(status_code=404, detail="No digests found")
    return DailyDigestResponse.model_validate(digest)


@router.get("/{digest_date}", response_model=DailyDigestResponse)
async def get_digest_by_date(digest_date: date, db: AsyncSession = Depends(get_db)):
    """Return a daily digest for a specific date (YYYY-MM-DD)."""
    stmt = select(DailyDigest).where(DailyDigest.digest_date == digest_date)
    result = await db.execute(stmt)
    digest = result.scalar_one_or_none()
    if not digest:
        raise HTTPException(status_code=404, detail="Digest not found for this date")
    return DailyDigestResponse.model_validate(digest)
