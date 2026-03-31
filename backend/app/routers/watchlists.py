from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from app.database import get_db
from app.dependencies import get_current_user
from app.models.watchlist import Watchlist
from app.schemas.watchlist import WatchlistCreate, WatchlistUpdate, WatchlistResponse

router = APIRouter(
    prefix="/watchlists",
    tags=["watchlists"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=list[WatchlistResponse])
async def list_watchlists(
    platform: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List all watchlist entries, optionally filtered by platform."""
    stmt = select(Watchlist)
    if platform:
        stmt = stmt.where(Watchlist.platform == platform)
    stmt = stmt.order_by(Watchlist.created_at.desc())
    result = await db.execute(stmt)
    return [WatchlistResponse.model_validate(w) for w in result.scalars().all()]


@router.post("", response_model=WatchlistResponse, status_code=status.HTTP_201_CREATED)
async def create_watchlist(
    body: WatchlistCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new watchlist entry."""
    entry = Watchlist(**body.model_dump())
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return WatchlistResponse.model_validate(entry)


@router.patch("/{watchlist_id}", response_model=WatchlistResponse)
async def update_watchlist(
    watchlist_id: UUID,
    body: WatchlistUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Partially update a watchlist entry."""
    result = await db.execute(select(Watchlist).where(Watchlist.id == watchlist_id))
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Watchlist entry not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(entry, field, value)
    await db.commit()
    await db.refresh(entry)
    return WatchlistResponse.model_validate(entry)


@router.delete("/{watchlist_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_watchlist(
    watchlist_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a watchlist entry."""
    result = await db.execute(select(Watchlist).where(Watchlist.id == watchlist_id))
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Watchlist entry not found")
    await db.delete(entry)
    await db.commit()
