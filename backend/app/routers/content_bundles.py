"""
content_bundles router — GET /content-bundles/{id} only.

Requirements: CREV-02, CREV-06 (GET detail).

Rerender endpoint removed in quick-260420-mfy (infographic/quote pivoted to
text-only three-field output; operator pastes image_prompt into claude.ai).
"""
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.content_bundle import ContentBundle
from app.schemas.content_bundle import ContentBundleDetailResponse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(
    prefix="/content-bundles",
    tags=["content-bundles"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/{bundle_id}", response_model=ContentBundleDetailResponse)
async def get_content_bundle(
    bundle_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> ContentBundleDetailResponse:
    """Return full ContentBundle detail for the dashboard modal (CREV-02 / CREV-06)."""
    result = await db.execute(select(ContentBundle).where(ContentBundle.id == bundle_id))
    bundle = result.scalar_one_or_none()
    if bundle is None:
        raise HTTPException(status_code=404, detail="Content bundle not found")
    return ContentBundleDetailResponse.model_validate(bundle)
