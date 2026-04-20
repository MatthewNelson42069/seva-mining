"""
Tests for GET /content-bundles/{id} endpoint.

Uses mock AsyncSession to avoid PostgreSQL-only type conflicts with SQLite.
Requirements: CREV-02 (GET detail), CREV-06 (full payload)

Rerender endpoint and rendered_images surface area removed in quick-260420-mfy.
The rendered_images DB column stays (operator-locked), but it is not part of
the API response schema. The make_content_bundle helper still sets rendered_images
on the mock object for DB-layer compatibility — it is simply not asserted via API.
"""
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth import create_access_token
from app.database import get_db
from app.main import app

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_content_bundle(
    *,
    id: UUID | None = None,
    story_headline: str = "African central banks gold accumulation",
    story_url: str | None = "https://example.com/gold",
    source_name: str | None = "Reuters",
    content_type: str | None = "infographic",
    score: float | None = 8.5,
    quality_score: float | None = 7.0,
    no_story_flag: bool = False,
    deep_research: dict | None = None,
    draft_content: dict | None = None,
    compliance_passed: bool | None = True,
    rendered_images: list | None = None,
    created_at: datetime | None = None,
) -> MagicMock:
    """Create a MagicMock that mimics a ContentBundle ORM object.

    rendered_images is preserved on the mock for DB-layer compatibility,
    but is no longer surfaced in API responses (schema removed in mfy pivot).
    """
    bundle = MagicMock()
    bundle.id = id or uuid.uuid4()
    bundle.story_headline = story_headline
    bundle.story_url = story_url
    bundle.source_name = source_name
    bundle.content_type = content_type
    bundle.score = score
    bundle.quality_score = quality_score
    bundle.no_story_flag = no_story_flag
    bundle.deep_research = deep_research or {"key_data_points": ["Central banks bought 1,037t in 2023"]}  # noqa: E501
    bundle.draft_content = draft_content or {"format": "infographic", "headline": "Gold Surge"}
    bundle.compliance_passed = compliance_passed
    bundle.rendered_images = rendered_images  # DB column stays; not in API response
    bundle.created_at = created_at or datetime(2026, 4, 16, 10, 0, 0, tzinfo=UTC)
    return bundle


def make_mock_db(bundle: MagicMock | None = None) -> AsyncMock:
    """Create a mock AsyncSession returning the given bundle."""
    mock_db = AsyncMock()
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = bundle
    mock_db.execute = AsyncMock(return_value=execute_result)
    mock_db.commit = AsyncMock()
    return mock_db


def authed_headers() -> dict:
    token = create_access_token()
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Tests: GET /content-bundles/{id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_content_bundle_returns_full_bundle():
    """GET /content-bundles/{id} returns 200 with full payload for authenticated operator."""
    bundle_id = uuid.uuid4()
    bundle = make_content_bundle(
        id=bundle_id,
        rendered_images=[{
            "role": "twitter_visual",
            "url": "https://r2.example/x.png",
            "generated_at": "2026-04-16T00:00:00+00:00",
        }],
    )
    mock_db = make_mock_db(bundle)

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"/content-bundles/{bundle_id}", headers=authed_headers())

        assert resp.status_code == 200
        data = resp.json()
        assert data["story_headline"] == "African central banks gold accumulation"
        assert data["draft_content"] == {"format": "infographic", "headline": "Gold Surge"}
        # rendered_images is NOT in the API response (schema removed in mfy pivot)
        assert "rendered_images" not in data
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_get_content_bundle_requires_auth():
    """GET /content-bundles/{id} returns 401/403 without token."""
    bundle_id = uuid.uuid4()
    bundle = make_content_bundle(id=bundle_id)
    mock_db = make_mock_db(bundle)

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"/content-bundles/{bundle_id}")

        assert resp.status_code in (401, 403)
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_get_content_bundle_returns_404_for_missing():
    """GET /content-bundles/{random_uuid} returns 404 when bundle does not exist."""
    mock_db = make_mock_db(None)  # scalar_one_or_none returns None

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"/content-bundles/{uuid.uuid4()}", headers=authed_headers())

        assert resp.status_code == 404
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_get_content_bundle_rendered_images_not_in_response():
    """GET /content-bundles/{id} does not include rendered_images in response body.

    The rendered_images column stays in the DB (operator-locked), but the mfy pivot
    removed it from the API response schema.
    """
    bundle_id = uuid.uuid4()
    bundle = make_content_bundle(id=bundle_id, rendered_images=None)
    mock_db = make_mock_db(bundle)

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"/content-bundles/{bundle_id}", headers=authed_headers())

        assert resp.status_code == 200
        data = resp.json()
        assert "rendered_images" not in data
    finally:
        app.dependency_overrides.pop(get_db, None)
