from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.content_bundle import ContentBundle
from app.schemas.content_bundle import ContentBundleResponse

router = APIRouter(
    prefix="/content",
    tags=["content"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/today", response_model=ContentBundleResponse)
async def get_today_content(db: AsyncSession = Depends(get_db)):
    """Returns today's content bundle (most recent created_at for today)."""
    stmt = (
        select(ContentBundle)
        .where(func.date(ContentBundle.created_at) == func.current_date())
        .order_by(ContentBundle.created_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    bundle = result.scalar_one_or_none()
    if not bundle:
        raise HTTPException(status_code=404, detail="No content bundle for today")
    return ContentBundleResponse.model_validate(bundle)
