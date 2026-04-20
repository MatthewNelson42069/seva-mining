"""
Image render service for Phase 11 — Content Preview and Rendered Images.

This module provides `render_bundle_job`, a shared async function that can be
imported and called by:
  - The scheduler worker (post-bundle-commit via APScheduler DateTrigger)
  - The backend rerender endpoint (via asyncio.create_task)

Silent-fail contract (D-18): render_bundle_job NEVER raises. All exceptions are
caught and logged. The operator sees no error — image slots simply remain empty.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import aioboto3
import google.genai as genai
from google.genai import types as genai_types
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from config import get_settings
from database import engine
from models.content_bundle import ContentBundle

logger = logging.getLogger(__name__)

# D-05: Brand palette is locked — these exact hex codes MUST appear in every prompt.
BRAND_PALETTE = (
    "Brand palette (MUST use exactly): "
    "#F0ECE4 warm cream background, "
    "#0C1B32 deep navy text, "
    "#D4AF37 gold accents."
)

# D-04 (updated): infographic format is now handled by chart renderer (not Gemini).
# See _render_infographic_charts() for the infographic code path.
# quote: handled by Gemini Imagen — 2 roles (twitter_visual + instagram_slide_1).
ROLES_BY_FORMAT: dict[str, list[tuple[str, str]]] = {
    # infographic: NOT in this dict — handled by _render_infographic_charts() via ChartRendererClient
    "quote": [
        ("twitter_visual", "16:9"),
        ("instagram_slide_1", "1:1"),
    ],
}


async def render_bundle_job(bundle_id: str) -> None:
    """Background job: generate images for a content bundle and persist URLs to rendered_images.

    Callable from APScheduler (scheduler worker) or asyncio.create_task (backend rerender endpoint).

    D-18 silent-fail contract: this function NEVER raises. All exceptions are logged at ERROR
    level but do not propagate. The operator sees no modal error or WhatsApp alert.

    Args:
        bundle_id: String UUID of the ContentBundle to render.
    """
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        try:
            await _render_and_persist(session, UUID(bundle_id))
        except Exception as exc:
            # Outer guard — should not normally be reached but ensures silence on unexpected errors.
            logger.error(
                "render: unexpected failure for bundle %s: %s",
                bundle_id,
                exc,
                exc_info=True,
            )


async def _render_and_persist(session: AsyncSession, bundle_id: UUID) -> None:
    """Core render pipeline: load bundle → compliance check → generate → upload → persist."""
    result = await session.execute(
        select(ContentBundle).where(ContentBundle.id == bundle_id)
    )
    bundle = result.scalar_one_or_none()

    if bundle is None:
        logger.warning("render: bundle %s not found — skipping", bundle_id)
        return

    if not bundle.compliance_passed:
        logger.info(
            "render: bundle %s skipped (compliance_passed=%s) — D-11",
            bundle_id,
            bundle.compliance_passed,
        )
        return

    # Infographic format: handled by chart renderer (Recharts SSR → resvg-js → PNG)
    # Quote format: continues below to Gemini Imagen path
    format_type = (bundle.content_type or "").lower()
    if format_type == "infographic":
        await _render_infographic_charts(session, bundle)
        return

    roles = ROLES_BY_FORMAT.get(format_type)
    if not roles:
        logger.info(
            "render: bundle %s format=%r has no render roles — skipping",
            bundle_id,
            bundle.content_type,
        )
        return

    client = genai.Client()  # reads GEMINI_API_KEY from environment
    rendered: list[dict[str, Any]] = []

    for role, aspect_ratio in roles:
        prompt = _build_prompt(role, bundle.draft_content or {}, bundle.story_headline or "")
        image_bytes = await _generate_with_retry(client, prompt, aspect_ratio, role, str(bundle_id))
        if image_bytes is None:
            # Per-role permanent failure — skip this role, continue others (D-18 partial-success path)
            continue

        timestamp = int(datetime.now(timezone.utc).timestamp())
        object_key = f"content-bundles/{bundle_id}/{role}-{timestamp}.png"

        try:
            url = await _upload_to_r2(image_bytes, object_key)
        except Exception as exc:
            logger.error(
                "render: R2 upload failed for bundle %s role %s: %s",
                bundle_id,
                role,
                exc,
                exc_info=True,
            )
            continue

        rendered.append(
            {
                "role": role,
                "url": url,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    # Always write SOMETHING — empty list tells frontend "render finished, no images landed".
    # This allows the age-based polling ceiling (D-14) to work correctly.
    bundle.rendered_images = rendered
    await session.commit()
    logger.info(
        "render: bundle %s produced %d/%d images",
        bundle_id,
        len(rendered),
        len(roles),
    )


async def _render_infographic_charts(session: AsyncSession, bundle) -> None:
    """Render infographic charts via ChartRendererClient (Recharts SSR → resvg-js → PNG).

    Reads charts from bundle.draft_content['charts'], validates via BundleCharts schema,
    calls the chart renderer, uploads PNGs to R2, and writes rendered_images to the bundle.

    D-18 silent-fail contract: all exceptions are caught and logged, never raised.
    Partial success: charts that return None are skipped; remaining PNGs are uploaded.
    """
    from agents.chart_renderer_client import get_chart_renderer_client  # noqa: PLC0415
    from models.chart_spec import BundleCharts  # noqa: PLC0415
    from pydantic import ValidationError  # noqa: PLC0415

    bundle_id = bundle.id
    draft = bundle.draft_content or {}
    charts_raw = draft.get("charts")

    if not charts_raw:
        logger.warning(
            "render: infographic bundle %s has no 'charts' key in draft_content — skipping render",
            bundle_id,
        )
        bundle.rendered_images = []
        await session.commit()
        return

    # Validate via BundleCharts schema
    try:
        payload = BundleCharts.model_validate({
            "charts": charts_raw,
            "twitter_caption": draft.get("twitter_caption", ""),
        })
    except (ValidationError, Exception) as exc:
        logger.error(
            "render: infographic bundle %s BundleCharts validation failed: %s — skipping render",
            bundle_id,
            exc,
        )
        bundle.rendered_images = []
        await session.commit()
        return

    # Call chart renderer
    try:
        png_list = await get_chart_renderer_client().render_charts(payload)
    except Exception as exc:
        logger.error(
            "render: chart renderer failed for bundle %s: %s",
            bundle_id,
            exc,
            exc_info=True,
        )
        bundle.rendered_images = []
        await session.commit()
        return

    # Upload non-None PNGs to R2
    roles_for_charts = ["twitter_visual", "twitter_visual_2"]
    rendered = []

    for i, png_bytes in enumerate(png_list):
        if png_bytes is None:
            logger.warning(
                "render: bundle %s chart index %d returned None (render failed) — skipping",
                bundle_id,
                i,
            )
            continue

        role = roles_for_charts[i] if i < len(roles_for_charts) else f"twitter_visual_{i + 1}"
        timestamp = int(datetime.now(timezone.utc).timestamp())
        object_key = f"content-bundles/{bundle_id}/{role}-{timestamp}.png"

        try:
            url = await _upload_to_r2(png_bytes, object_key)
        except Exception as exc:
            logger.error(
                "render: R2 upload failed for bundle %s role %s: %s",
                bundle_id,
                role,
                exc,
                exc_info=True,
            )
            continue

        rendered.append({
            "role": role,
            "url": url,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        })

    bundle.rendered_images = rendered
    await session.commit()
    logger.info(
        "render: infographic bundle %s produced %d/%d chart images",
        bundle_id,
        len(rendered),
        len(png_list),
    )


async def _generate_with_retry(
    client: Any,
    prompt: str,
    aspect_ratio: str,
    role: str,
    bundle_id: str,
) -> bytes | None:
    """Call Imagen 4 with per-role exponential backoff retry.

    D-18 retry semantics: 3 total attempts with ~2s and ~8s delays.
    Returns bytes on success, None if all 3 attempts fail (caller skips the role).
    """
    for attempt in range(3):
        try:
            response = await client.aio.models.generate_images(
                model="imagen-4.0-generate-001",
                prompt=prompt,
                config=genai_types.GenerateImagesConfig(
                    number_of_images=1,
                    aspect_ratio=aspect_ratio,
                    output_mime_type="image/png",
                ),
            )
            return response.generated_images[0].image.image_bytes
        except Exception as exc:
            if attempt < 2:
                # Delays: attempt 0 → 2s, attempt 1 → 8s (per D-18 "~2s/~8s" guidance)
                delay = 2 if attempt == 0 else 8
                logger.warning(
                    "render: bundle %s role %s attempt %d failed: %s — retrying in %ds",
                    bundle_id,
                    role,
                    attempt + 1,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    "render: bundle %s role %s permanently failed after 3 attempts: %s",
                    bundle_id,
                    role,
                    exc,
                    exc_info=True,
                )
    return None


async def _upload_to_r2(image_bytes: bytes, object_key: str) -> str:
    """Upload PNG bytes to Cloudflare R2 and return the public URL.

    R2 uses bucket-level public access (Cloudflare dashboard setting).
    No per-object access parameter is passed to put_object — R2 does not support them.
    """
    settings = get_settings()
    session = aioboto3.Session()
    async with session.client(
        "s3",
        endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        region_name="auto",
    ) as s3:
        await s3.put_object(
            Bucket=settings.r2_bucket,
            Key=object_key,
            Body=image_bytes,
            ContentType="image/png",
        )
    base_url = (settings.r2_public_base_url or "").rstrip("/")
    return f"{base_url}/{object_key}"


def _build_prompt(role: str, draft_content: dict, story_headline: str) -> str:
    """Build the Imagen 4 prompt for a given role.

    Called only for the `quote` format (see ROLES_BY_FORMAT). Infographic bundles
    go through _render_infographic_charts() / ChartRendererClient and never reach
    this function.

    D-05: BRAND_PALETTE (which contains all three hex codes verbatim) MUST appear in every prompt.
    Prompt wording is implementer discretion; brand palette is locked.
    Falls back gracefully on missing keys — never raises.
    """
    format_type = (draft_content.get("format") or "").lower()

    # --- Quote roles ---
    if role == "twitter_visual" and format_type == "quote":
        attributed_to = draft_content.get("attributed_to") or ""
        twitter_post = draft_content.get("twitter_post") or story_headline
        attribution_clause = f" — {attributed_to}" if attributed_to else ""

        return (
            f"Design a horizontal 16:9 quote pull-card for social media. "
            f"Quote text: \"{twitter_post}\"{attribution_clause}. "
            f"{BRAND_PALETTE} "
            f"Layout: large quote text centered on #F0ECE4 cream background, "
            f"attribution in smaller #0C1B32 navy text below, #D4AF37 gold quotation marks. "
            f"Professional financial media aesthetic. No watermarks. High resolution."
        )

    if role == "instagram_slide_1" and format_type == "quote":
        instagram_post = draft_content.get("instagram_post") or draft_content.get("twitter_post") or story_headline
        attributed_to = draft_content.get("attributed_to") or ""
        attribution_clause = f" — {attributed_to}" if attributed_to else ""

        return (
            f"Design a square 1:1 Instagram quote card. "
            f"Quote: \"{instagram_post}\"{attribution_clause}. "
            f"{BRAND_PALETTE} "
            f"Layout: centered quote text on #F0ECE4 cream, #0C1B32 navy typography, "
            f"#D4AF37 gold decorative border. "
            f"Professional financial media aesthetic. No watermarks. High resolution."
        )

    # --- Fallback for any unrecognized role/format combination ---
    return (
        f"Design a professional social media image for a gold sector post. "
        f"Content: \"{story_headline}\". "
        f"{BRAND_PALETTE} "
        f"Clean layout with #F0ECE4 cream background, #0C1B32 navy text, #D4AF37 gold accents. "
        f"No watermarks. High resolution."
    )
