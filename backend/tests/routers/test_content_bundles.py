"""
Tests for GET /content-bundles/{id} and POST /content-bundles/{id}/rerender endpoints.

Uses mock AsyncSession to avoid PostgreSQL-only type conflicts with SQLite.
Requirements: CREV-02 (GET detail), CREV-06 (full payload), CREV-09 (rerender 202)
"""
import asyncio
import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.database import get_db
from app.auth import create_access_token


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
    """Create a MagicMock that mimics a ContentBundle ORM object."""
    bundle = MagicMock()
    bundle.id = id or uuid.uuid4()
    bundle.story_headline = story_headline
    bundle.story_url = story_url
    bundle.source_name = source_name
    bundle.content_type = content_type
    bundle.score = score
    bundle.quality_score = quality_score
    bundle.no_story_flag = no_story_flag
    bundle.deep_research = deep_research or {"key_data_points": ["Central banks bought 1,037t in 2023"]}
    bundle.draft_content = draft_content or {"format": "infographic", "headline": "Gold Surge"}
    bundle.compliance_passed = compliance_passed
    bundle.rendered_images = rendered_images
    bundle.created_at = created_at or datetime(2026, 4, 16, 10, 0, 0, tzinfo=timezone.utc)
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
# Task 1 Tests: GET /content-bundles/{id}
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
        assert "rendered_images" in data
        assert len(data["rendered_images"]) == 1
        assert data["rendered_images"][0]["role"] == "twitter_visual"
        assert data["rendered_images"][0]["url"] == "https://r2.example/x.png"
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
async def test_get_content_bundle_rendered_images_null_returns_null():
    """GET /content-bundles/{id} with rendered_images=None returns null for the field."""
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
        assert "rendered_images" in data
        assert data["rendered_images"] is None
    finally:
        app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# Task 2 Tests: POST /content-bundles/{id}/rerender
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rerender_returns_202():
    """POST /content-bundles/{id}/rerender returns 202 with {bundle_id, render_job_id, enqueued_at}."""
    bundle_id = uuid.uuid4()
    bundle = make_content_bundle(id=bundle_id)
    mock_db = make_mock_db(bundle)

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        with patch("app.routers.content_bundles._get_render_bundle_job") as mock_get_job:
            mock_job = AsyncMock()
            mock_get_job.return_value = mock_job
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.post(f"/content-bundles/{bundle_id}/rerender", headers=authed_headers())

        assert resp.status_code == 202
        data = resp.json()
        assert data["bundle_id"] == str(bundle_id)
        assert "render_job_id" in data
        assert "enqueued_at" in data
        assert data["render_job_id"].startswith("rerender_")
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_rerender_clears_existing_images():
    """POST /content-bundles/{id}/rerender clears bundle.rendered_images to [] before enqueueing."""
    bundle_id = uuid.uuid4()
    bundle = make_content_bundle(
        id=bundle_id,
        rendered_images=[{
            "role": "twitter_visual",
            "url": "https://r2.example/old.png",
            "generated_at": "2026-04-16T00:00:00+00:00",
        }],
    )
    mock_db = make_mock_db(bundle)

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        with patch("app.routers.content_bundles._get_render_bundle_job") as mock_get_job:
            mock_job = AsyncMock()
            mock_get_job.return_value = mock_job
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.post(f"/content-bundles/{bundle_id}/rerender", headers=authed_headers())

        assert resp.status_code == 202
        # Verify rendered_images was cleared to [] before commit
        assert bundle.rendered_images == []
        mock_db.commit.assert_awaited_once()
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_rerender_404_on_missing_bundle():
    """POST /content-bundles/{random_uuid}/rerender returns 404."""
    mock_db = make_mock_db(None)

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(f"/content-bundles/{uuid.uuid4()}/rerender", headers=authed_headers())

        assert resp.status_code == 404
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_rerender_requires_auth():
    """POST /content-bundles/{id}/rerender returns 401/403 without token."""
    bundle_id = uuid.uuid4()
    mock_db = make_mock_db(make_content_bundle(id=bundle_id))

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(f"/content-bundles/{bundle_id}/rerender")

        assert resp.status_code in (401, 403)
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_rerender_enqueues_render_bundle_job():
    """POST /content-bundles/{id}/rerender fires render_bundle_job via asyncio.create_task."""
    bundle_id = uuid.uuid4()
    bundle = make_content_bundle(id=bundle_id)
    mock_db = make_mock_db(bundle)

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        with patch("app.routers.content_bundles._get_render_bundle_job") as mock_get_job:
            mock_job = AsyncMock()
            mock_get_job.return_value = mock_job

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.post(f"/content-bundles/{bundle_id}/rerender", headers=authed_headers())

            # Let the event loop tick so create_task runs the coroutine
            await asyncio.sleep(0.05)

        assert resp.status_code == 202
        mock_get_job.assert_called_once()
        mock_job.assert_awaited_once_with(str(bundle_id))
    finally:
        app.dependency_overrides.pop(get_db, None)
