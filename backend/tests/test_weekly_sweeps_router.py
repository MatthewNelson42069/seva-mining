"""Integration tests for GET /weekly-sweeps — Phase 7, Plan 03 (SWEEP-12).

Covers:
- Empty DB returns {sweeps: [], total: 0} (preserves Phase 5 stub contract)
- Populated DB returns rows in generated_at DESC order
- limit clamp (ge=1, le=52) — out-of-range returns 422
- limit smaller than total — sweeps len matches limit, total reflects full count
- Auth gate at router level — missing JWT returns 401
- Status serialization — non-completed status round-trips through the response

Mirrors backend/tests/routers/test_summaries.py exactly — uses mock AsyncSession
to avoid PostgreSQL-only type conflicts (UUID, JSONB) with the SQLite in-memory
test DB. See module docstring of test_summaries.py for the rationale.

Path note: flat at backend/tests/test_weekly_sweeps_router.py per plan 07-03
acceptance criterion (flat-file pattern locked alongside test_calendar_router.py).
"""

import uuid
from datetime import UTC, date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth import create_access_token
from app.database import get_db
from app.main import app

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers (mirrors test_summaries.py shape)
# ---------------------------------------------------------------------------


def make_sweep(
    *,
    generated_at: datetime | None = None,
    week_start: date | None = None,
    week_end: date | None = None,
    reddit_top_md: str | None = "# Top X Posts\n* test",
    story_virality_md: str | None = "# Virality",
    content_angles_md: str | None = "# Angles",
    status: str = "completed",
    error_text: str | None = None,
) -> MagicMock:
    """Create a MagicMock that mimics a WeeklySweep ORM row."""
    sweep = MagicMock()
    sweep.id = uuid.uuid4()
    sweep.generated_at = generated_at or datetime.now(UTC)
    sweep.week_start = week_start or date(2026, 5, 11)
    sweep.week_end = week_end or date(2026, 5, 17)
    sweep.reddit_top_md = reddit_top_md
    sweep.story_virality_md = story_virality_md
    sweep.content_angles_md = content_angles_md
    sweep.status = status
    sweep.error_text = error_text
    sweep.agent_run_id = None
    return sweep


def make_mock_db(rows: list | None = None, total: int | None = None) -> AsyncMock:
    """Create a mock AsyncSession that:
    1. Returns the given list of rows on the first .execute() call (the SELECT)
    2. Returns the COUNT scalar on the second .execute() call (func.count())

    If `total` is None, defaults to len(rows) so simple cases stay simple.
    """
    rows = rows or []
    if total is None:
        total = len(rows)

    mock_db = AsyncMock()

    # First call: SELECT WeeklySweep — returns rows via .scalars().all()
    select_result = MagicMock()
    scalars_result = MagicMock()
    scalars_result.all.return_value = rows
    select_result.scalars.return_value = scalars_result

    # Second call: SELECT count() — returns total via .scalar_one()
    count_result = MagicMock()
    count_result.scalar_one.return_value = total

    # side_effect returns these in order across the two await db.execute(...) calls
    mock_db.execute = AsyncMock(side_effect=[select_result, count_result])
    return mock_db


def authed_headers() -> dict:
    token = create_access_token()
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_auth_required():
    """GET /weekly-sweeps without Authorization header returns 401."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/weekly-sweeps")
    assert resp.status_code == 401


async def test_list_empty():
    """Empty DB returns 200 with {"sweeps": [], "total": 0} — preserves Phase 5 stub contract."""
    mock_db = make_mock_db(rows=[], total=0)

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/weekly-sweeps", headers=authed_headers())
        assert resp.status_code == 200
        body = resp.json()
        assert body == {"sweeps": [], "total": 0}
    finally:
        app.dependency_overrides.pop(get_db, None)


async def test_list_populated_desc_order():
    """Three rows are returned newest-first; total reflects full row count."""
    now = datetime.now(UTC)
    # Mock returns rows pre-sorted (real SQL ORDER BY DESC enforced by Postgres)
    rows = [
        make_sweep(generated_at=now),
        make_sweep(generated_at=now - timedelta(days=7)),
        make_sweep(generated_at=now - timedelta(days=14)),
    ]
    mock_db = make_mock_db(rows=rows, total=3)

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/weekly-sweeps", headers=authed_headers())
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["sweeps"]) == 3
        assert body["total"] == 3
        # DESC order check
        gen_ats = [s["generated_at"] for s in body["sweeps"]]
        assert gen_ats == sorted(gen_ats, reverse=True), f"not DESC order: {gen_ats}"
    finally:
        app.dependency_overrides.pop(get_db, None)


async def test_limit_clamp_zero():
    """limit=0 returns 422 (ge=1 clamp via FastAPI Query validation)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/weekly-sweeps?limit=0", headers=authed_headers())
    assert resp.status_code == 422


async def test_limit_clamp_too_high():
    """limit=53 returns 422 (le=52 clamp per SWEEP-12)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/weekly-sweeps?limit=53", headers=authed_headers())
    assert resp.status_code == 422


async def test_limit_smaller_than_total():
    """limit=5 against 15 rows: sweeps len 5, total=15 (total reflects full DB count)."""
    now = datetime.now(UTC)
    # SQL LIMIT is enforced by the real DB; mock returns the pre-limited 5 rows.
    # Total scalar comes from a separate SELECT count() — set to 15 here.
    rows = [make_sweep(generated_at=now - timedelta(days=7 * i)) for i in range(5)]
    mock_db = make_mock_db(rows=rows, total=15)

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/weekly-sweeps?limit=5", headers=authed_headers())
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["sweeps"]) == 5
        assert body["total"] == 15
    finally:
        app.dependency_overrides.pop(get_db, None)


async def test_status_serialization():
    """A row with status='partial' round-trips through the response JSON."""
    mock_db = make_mock_db(
        rows=[make_sweep(generated_at=datetime.now(UTC), status="partial")],
        total=1,
    )

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/weekly-sweeps", headers=authed_headers())
        assert resp.status_code == 200
        body = resp.json()
        assert body["sweeps"][0]["status"] == "partial"
    finally:
        app.dependency_overrides.pop(get_db, None)


async def test_response_card_shape():
    """Card includes all WeeklySweepCard fields and omits raw_sources_jsonb."""
    mock_db = make_mock_db(
        rows=[make_sweep(generated_at=datetime.now(UTC))],
        total=1,
    )

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/weekly-sweeps", headers=authed_headers())
        assert resp.status_code == 200
        card = resp.json()["sweeps"][0]
        # raw_sources_jsonb is internal telemetry and MUST NOT leak (matches SummaryCardResponse)
        assert "raw_sources_jsonb" not in card
        for key in (
            "id",
            "generated_at",
            "week_start",
            "week_end",
            "reddit_top_md",
            "story_virality_md",
            "content_angles_md",
            "status",
            "error_text",
            "agent_run_id",
        ):
            assert key in card, f"Missing key in card: {key}"
    finally:
        app.dependency_overrides.pop(get_db, None)
