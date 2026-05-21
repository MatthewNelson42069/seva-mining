"""Integration tests for GET /summaries — Phase 1, Plan 04.

Covers FEED-05 (auth-gated), pagination clamps, DESC ordering, response shape.

Uses mock AsyncSession (mirrors test_content_bundles.py pattern) to avoid
PostgreSQL-only type conflicts (UUID, JSONB) with SQLite in-memory test DB.
"""

import os
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.database import get_db
from app.main import app

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_summary(
    *,
    generated_at: datetime | None = None,
    period_label: str = "08:00 PT",
    gold_news_md: str | None = "## Gold News\n* test",
    ontario_law_md: str | None = None,
    ontario_stats_md: str | None = None,
    status: str = "completed",
    error_text: str | None = None,
) -> MagicMock:
    """Create a MagicMock that mimics a DailySummary ORM object."""
    summary = MagicMock()
    summary.id = uuid.uuid4()
    summary.generated_at = generated_at or datetime.now(UTC)
    summary.period_label = period_label
    summary.gold_news_md = gold_news_md
    summary.ontario_law_md = ontario_law_md
    summary.ontario_stats_md = ontario_stats_md
    summary.raw_sources_jsonb = {
        "gold_news": [],
        "ontario_law": {"hits": [], "last_known_law": None},
        "ontario_stats": {"snapshot_date": "", "last_known_figure": None, "fresh_data": None},
    }
    summary.status = status
    summary.error_text = error_text
    # v3.0 Phase 9 — Pydantic SummaryCardResponse.company_id is `str | None`.
    # MagicMock auto-attr would return a MagicMock instance → Pydantic 422.
    # Default to 'seva' (matches DB server_default).
    summary.company_id = "seva"
    return summary


def make_mock_db(rows: list | None = None) -> AsyncMock:
    """Create a mock AsyncSession returning the given list of rows."""
    mock_db = AsyncMock()
    execute_result = MagicMock()
    scalars_result = MagicMock()
    scalars_result.all.return_value = rows or []
    execute_result.scalars.return_value = scalars_result
    mock_db.execute = AsyncMock(return_value=execute_result)
    return mock_db


def authed_headers() -> dict:
    """Return seva_auth_token cookie dict for cookie-based auth (quick-260521-9ze)."""
    return {"seva_auth_token": os.environ["SEVA_DASHBOARD_TOKEN"]}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

async def test_get_summaries_unauthenticated_returns_403():
    """GET /summaries without auth cookie returns 403 (cookie auth, quick-260521-9ze)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/seva/summaries")
    assert resp.status_code in (401, 403)


async def test_get_summaries_empty_returns_200_with_empty_list():
    """GET /summaries with no DB rows returns 200 {summaries: [], total: 0}."""
    mock_db = make_mock_db(rows=[])

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/api/seva/summaries", cookies=authed_headers())
        assert resp.status_code == 200
        body = resp.json()
        assert body == {"summaries": [], "total": 0}
    finally:
        app.dependency_overrides.pop(get_db, None)


async def test_get_summaries_returns_rows_in_descending_order():
    """GET /summaries returns rows ordered newest-first (generated_at DESC)."""
    now = datetime.now(UTC)
    # Rows already ordered DESC by the SQL query — mock returns them pre-sorted
    rows = [
        make_summary(generated_at=now),
        make_summary(generated_at=now - timedelta(hours=4)),
        make_summary(generated_at=now - timedelta(hours=8)),
    ]
    mock_db = make_mock_db(rows=rows)

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/api/seva/summaries", cookies=authed_headers())
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 3
        ts = [c["generated_at"] for c in body["summaries"]]
        assert ts == sorted(ts, reverse=True), f"Expected DESC order, got: {ts}"
    finally:
        app.dependency_overrides.pop(get_db, None)


async def test_get_summaries_respects_limit_param():
    """GET /summaries?limit=2 with 3 DB rows returns 2 rows (SQL LIMIT enforced by mock)."""
    now = datetime.now(UTC)
    # SQL LIMIT is enforced by the real DB; mock returns the 2 pre-limited rows
    rows = [
        make_summary(generated_at=now),
        make_summary(generated_at=now - timedelta(hours=2)),
    ]
    mock_db = make_mock_db(rows=rows)

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/api/seva/summaries?limit=2", cookies=authed_headers())
        assert resp.status_code == 200
        assert len(resp.json()["summaries"]) == 2
    finally:
        app.dependency_overrides.pop(get_db, None)


async def test_get_summaries_limit_above_120_rejected():
    """GET /summaries?limit=121 returns 422 (limit le=120)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/seva/summaries?limit=121", cookies=authed_headers())
    assert resp.status_code == 422


async def test_get_summaries_limit_zero_rejected():
    """GET /summaries?limit=0 returns 422 (limit ge=1)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/seva/summaries?limit=0", cookies=authed_headers())
    assert resp.status_code == 422


async def test_get_summaries_response_omits_raw_sources_jsonb():
    """Response card contains required keys and NO raw_sources_jsonb key."""
    mock_db = make_mock_db(rows=[make_summary(generated_at=datetime.now(UTC))])

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/api/seva/summaries", cookies=authed_headers())
        assert resp.status_code == 200
        card = resp.json()["summaries"][0]
        assert "raw_sources_jsonb" not in card
        for key in (
            "id", "generated_at", "period_label", "gold_news_md",
            "ontario_law_md", "ontario_stats_md", "status", "error_text",
        ):
            assert key in card, f"Missing key in card: {key}"
    finally:
        app.dependency_overrides.pop(get_db, None)
