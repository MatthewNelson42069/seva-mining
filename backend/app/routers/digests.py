from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date
from app.database import get_db
from app.dependencies import get_current_user
from app.models.daily_digest import DailyDigest
from app.schemas.daily_digest import DailyDigestResponse

router = APIRouter(
    prefix="/digests",
    tags=["digests"],
    dependencies=[Depends(get_current_user)],
)


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
