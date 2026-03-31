from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from app.database import get_db
from app.dependencies import get_current_user
from app.models.keyword import Keyword
from app.schemas.keyword import KeywordCreate, KeywordUpdate, KeywordResponse

router = APIRouter(
    prefix="/keywords",
    tags=["keywords"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=list[KeywordResponse])
async def list_keywords(
    platform: str | None = Query(None),
    active: bool | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List all keywords, optionally filtered by platform and/or active status."""
    stmt = select(Keyword)
    if platform:
        stmt = stmt.where(Keyword.platform == platform)
    if active is not None:
        stmt = stmt.where(Keyword.active == active)
    stmt = stmt.order_by(Keyword.created_at.desc())
    result = await db.execute(stmt)
    return [KeywordResponse.model_validate(k) for k in result.scalars().all()]


@router.post("", response_model=KeywordResponse, status_code=status.HTTP_201_CREATED)
async def create_keyword(
    body: KeywordCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new keyword."""
    entry = Keyword(**body.model_dump())
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return KeywordResponse.model_validate(entry)


@router.patch("/{keyword_id}", response_model=KeywordResponse)
async def update_keyword(
    keyword_id: UUID,
    body: KeywordUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Partially update a keyword."""
    result = await db.execute(select(Keyword).where(Keyword.id == keyword_id))
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Keyword not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(entry, field, value)
    await db.commit()
    await db.refresh(entry)
    return KeywordResponse.model_validate(entry)


@router.delete("/{keyword_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_keyword(
    keyword_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a keyword."""
    result = await db.execute(select(Keyword).where(Keyword.id == keyword_id))
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Keyword not found")
    await db.delete(entry)
    await db.commit()
