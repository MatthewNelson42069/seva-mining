"""
content_bundles router — GET /content-bundles/{id} and POST /content-bundles/{id}/rerender.

Requirements: CREV-02, CREV-06 (GET detail), CREV-09 (rerender 202).

The rerender endpoint fires render_bundle_job via asyncio.create_task in the backend's
own event loop per RESEARCH.md Pitfall 1 / Finding 3 (backend and scheduler are separate
Railway services — cross-process scheduler access is not possible, so the render function
must be importable and invokable from both contexts).

sys.path shim: both services share the same repo in Railway. The scheduler/ directory is
always a sibling of backend/. We insert it at import time so the backend can import
scheduler/agents/image_render_agent.py.
"""
import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.content_bundle import ContentBundle
from app.schemas.content_bundle import ContentBundleDetailResponse, RerenderResponse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# sys.path shim — allow backend to import scheduler package.
# Both Railway services share the same repo at /app, so scheduler/ is always
# a sibling of backend/. The shim is harmless if the path is already present.
# ---------------------------------------------------------------------------
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_SCHEDULER_PATH = os.path.join(_REPO_ROOT, "scheduler")
if _SCHEDULER_PATH not in sys.path:
    sys.path.insert(0, _SCHEDULER_PATH)


def _get_render_bundle_job():
    """
    Return the render_bundle_job coroutine function from the scheduler package.

    Uses importlib.util.spec_from_file_location to load image_render_agent.py
    DIRECTLY — bypassing scheduler/agents/__init__.py, which eagerly imports
    TwitterAgent → tweepy (not installed in the backend venv).

    Returns a no-op async stub if image_render_agent.py is missing or fails to
    load (logs the reason). Plan 07 checkpoint verifies this is wired correctly
    in the Railway deploy.
    """
    import importlib.util

    module_path = os.path.join(_SCHEDULER_PATH, "agents", "image_render_agent.py")
    if not os.path.exists(module_path):
        logger.warning(
            "image_render_agent.py not found at %s — rerender will fire a no-op stub.",
            module_path,
        )
    else:
        try:
            spec = importlib.util.spec_from_file_location(
                "seva_image_render_agent", module_path
            )
            if spec is None or spec.loader is None:
                raise ImportError(
                    "spec_from_file_location returned None for image_render_agent.py"
                )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module.render_bundle_job
        except Exception as exc:  # pragma: no cover — defensive
            logger.warning(
                "Failed to load image_render_agent via importlib (%s: %s) — "
                "rerender will fire a no-op stub.",
                type(exc).__name__,
                exc,
            )

    async def _noop_render_bundle_job(bundle_id: str) -> None:
        logger.info("No-op render_bundle_job called for bundle %s (stub)", bundle_id)

    return _noop_render_bundle_job


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


@router.post("/{bundle_id}/rerender", status_code=202, response_model=RerenderResponse)
async def rerender_content_bundle(
    bundle_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> RerenderResponse:
    """Clear existing rendered_images and enqueue a fresh render (CREV-09).

    Returns 202 immediately; the render runs async in the backend event loop via
    asyncio.create_task. Frontend polls GET /content-bundles/{id} until new URLs appear.

    Per D-15: always enqueues (idempotent). Per D-16: works on any bundle.
    """
    result = await db.execute(select(ContentBundle).where(ContentBundle.id == bundle_id))
    bundle = result.scalar_one_or_none()
    if bundle is None:
        raise HTTPException(status_code=404, detail="Content bundle not found")

    # Clear so frontend polling state re-engages (D-15/D-16)
    bundle.rendered_images = []
    await db.commit()

    # Fire-and-forget render. _get_render_bundle_job() is a module-level helper so
    # tests can monkeypatch it without needing to patch a local import.
    render_fn = _get_render_bundle_job()
    asyncio.create_task(render_fn(str(bundle_id)))

    job_id = f"rerender_{bundle_id}_{uuid4().hex[:8]}"
    return RerenderResponse(
        bundle_id=bundle_id,
        render_job_id=job_id,
        enqueued_at=datetime.now(timezone.utc).isoformat(),
    )
