"""End-to-end tests for backend/app/routers/calendar.py — Phase 6 Plan 02.

Covers CAL-01..CAL-04 + Pitfall P1 (TZ off-by-one) + Pitfall P4 (updated_at
explicit on PATCH) + router-level auth gate.
"""
from __future__ import annotations

import os
import time

# P1 defense: force the test process timezone to UTC so any
# accidental datetime->date conversion would visibly slip.
os.environ["TZ"] = "UTC"
if hasattr(time, "tzset"):
    time.tzset()

import asyncio  # noqa: E402

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.auth import create_access_token  # noqa: E402
from app.database import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.calendar_item import CalendarItem  # noqa: E402

_TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


# ---------------------------------------------------------------------------
# Fixtures — own SQLite engine + table creation so routes have a real DB
# (mirrors backend/tests/test_crud_endpoints.py pattern)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def calendar_client():
    """HTTP client wired to a SQLite engine with calendar_items table created."""
    engine = create_async_engine(_TEST_DB_URL, echo=False)

    # Create only the calendar_items table — keep this test module self-contained.
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: CalendarItem.__table__.create(c))

    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_db, None)
    await engine.dispose()


@pytest_asyncio.fixture
async def authed_calendar_client(calendar_client):
    """calendar_client with Authorization: Bearer header pre-set."""
    token = create_access_token()
    calendar_client.headers.update({"Authorization": f"Bearer {token}"})
    yield calendar_client


# ---------------------------------------------------------------------------
# Auth gate tests (CAL-01..CAL-04 inherit router-level Depends)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_calendar_requires_auth(calendar_client):
    """Router-level Depends(get_current_user) must reject unauthenticated."""
    r = await calendar_client.get("/api/seva/calendar?start=2026-05-18&end=2026-05-24")
    assert r.status_code == 401, r.text


@pytest.mark.asyncio
async def test_post_calendar_requires_auth(calendar_client):
    r = await calendar_client.post(
        "/api/seva/calendar", json={"date": "2026-05-20", "body": "x"}
    )
    assert r.status_code == 401, r.text


# ---------------------------------------------------------------------------
# CAL-01: GET range
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_calendar_empty_range_returns_200(authed_calendar_client):
    r = await authed_calendar_client.get(
        "/api/seva/calendar?start=2026-05-18&end=2026-05-24"
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body == {"items": [], "total": 0}


@pytest.mark.asyncio
async def test_get_calendar_returns_items_in_date_asc(authed_calendar_client):
    await authed_calendar_client.post(
        "/api/seva/calendar", json={"date": "2026-06-03", "body": "c"}
    )
    await authed_calendar_client.post(
        "/api/seva/calendar", json={"date": "2026-06-01", "body": "a"}
    )
    await authed_calendar_client.post(
        "/api/seva/calendar", json={"date": "2026-06-02", "body": "b"}
    )
    r = await authed_calendar_client.get(
        "/api/seva/calendar?start=2026-06-01&end=2026-06-07"
    )
    assert r.status_code == 200
    items = r.json()["items"]
    assert [it["date"] for it in items] == ["2026-06-01", "2026-06-02", "2026-06-03"]
    assert [it["body"] for it in items] == ["a", "b", "c"]
    assert r.json()["total"] == 3


@pytest.mark.asyncio
async def test_get_calendar_excludes_dates_outside_range(authed_calendar_client):
    await authed_calendar_client.post(
        "/api/seva/calendar", json={"date": "2026-07-01", "body": "in"}
    )
    await authed_calendar_client.post(
        "/api/seva/calendar", json={"date": "2026-07-31", "body": "out"}
    )
    r = await authed_calendar_client.get(
        "/api/seva/calendar?start=2026-07-01&end=2026-07-07"
    )
    body = r.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["date"] == "2026-07-01"


# ---------------------------------------------------------------------------
# CAL-02: POST create
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_creates_item_returns_201_with_response_shape(
    authed_calendar_client,
):
    r = await authed_calendar_client.post(
        "/api/seva/calendar",
        json={"date": "2026-05-20", "body": "draft thread about gold ETFs"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["date"] == "2026-05-20"
    assert body["body"] == "draft thread about gold ETFs"
    assert "id" in body
    assert "created_at" in body
    assert "updated_at" in body
    # P1: round-trip the date — UTC server, date string stays same day
    assert body["date"] == "2026-05-20"


@pytest.mark.asyncio
async def test_post_rejects_blank_body_with_422(authed_calendar_client):
    r = await authed_calendar_client.post(
        "/api/seva/calendar", json={"date": "2026-05-20", "body": "   "}
    )
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_post_duplicate_date_returns_409(authed_calendar_client):
    """D-02 enforcement: UNIQUE(date) constraint surfaces as 409."""
    r1 = await authed_calendar_client.post(
        "/api/seva/calendar", json={"date": "2026-05-21", "body": "first"}
    )
    assert r1.status_code == 201
    r2 = await authed_calendar_client.post(
        "/api/seva/calendar", json={"date": "2026-05-21", "body": "second"}
    )
    assert r2.status_code == 409, r2.text
    assert "2026-05-21" in r2.json()["detail"]


# ---------------------------------------------------------------------------
# CAL-03: PATCH update + P4 updated_at defense
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_updates_body_and_bumps_updated_at(authed_calendar_client):
    """P4 defense: PATCH handler MUST explicitly set updated_at.

    We exercise this by reading updated_at before and after the PATCH and
    asserting strict increase. created_at MUST be unchanged.
    """
    post = await authed_calendar_client.post(
        "/api/seva/calendar", json={"date": "2026-08-01", "body": "old"}
    )
    assert post.status_code == 201
    item_id = post.json()["id"]
    original_updated = post.json()["updated_at"]
    original_created = post.json()["created_at"]

    # Sleep 50ms to guarantee a measurable timestamp delta even if the test
    # host has coarse clock resolution.
    await asyncio.sleep(0.05)

    patch = await authed_calendar_client.patch(
        f"/api/seva/calendar/{item_id}", json={"body": "new"}
    )
    assert patch.status_code == 200, patch.text
    body = patch.json()
    assert body["body"] == "new"
    assert body["created_at"] == original_created
    assert body["updated_at"] > original_updated, (
        f"updated_at not bumped: before={original_updated} "
        f"after={body['updated_at']}"
    )


@pytest.mark.asyncio
async def test_patch_rejects_unknown_id_with_404(authed_calendar_client):
    r = await authed_calendar_client.patch(
        "/api/seva/calendar/00000000-0000-0000-0000-000000000000", json={"body": "x"}
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_patch_rejects_blank_body_with_422(authed_calendar_client):
    post = await authed_calendar_client.post(
        "/api/seva/calendar", json={"date": "2026-09-01", "body": "x"}
    )
    item_id = post.json()["id"]
    r = await authed_calendar_client.patch(
        f"/api/seva/calendar/{item_id}", json={"body": "   "}
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_patch_ignores_unknown_fields(authed_calendar_client):
    """CalendarItemUpdate exposes only `body`; date/tag/updated_at are ignored."""
    post = await authed_calendar_client.post(
        "/api/seva/calendar", json={"date": "2026-09-15", "body": "x"}
    )
    item_id = post.json()["id"]
    # Try to sneak in a date change and a fake updated_at — both must be ignored.
    r = await authed_calendar_client.patch(
        f"/api/seva/calendar/{item_id}",
        json={
            "body": "y",
            "date": "1900-01-01",
            "updated_at": "1900-01-01T00:00:00",
            "tag": "thread",
        },
    )
    assert r.status_code == 200
    # The date stayed 2026-09-15 because CalendarItemUpdate has no `date` field
    assert r.json()["date"] == "2026-09-15"


# ---------------------------------------------------------------------------
# CAL-04: DELETE
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_returns_204_and_removes_row(authed_calendar_client):
    post = await authed_calendar_client.post(
        "/api/seva/calendar", json={"date": "2026-10-01", "body": "to delete"}
    )
    item_id = post.json()["id"]
    d = await authed_calendar_client.delete(f"/api/seva/calendar/{item_id}")
    assert d.status_code == 204, d.text
    # Confirm it's gone via GET range
    g = await authed_calendar_client.get(
        "/api/seva/calendar?start=2026-10-01&end=2026-10-01"
    )
    assert g.json()["total"] == 0


@pytest.mark.asyncio
async def test_delete_returns_404_on_missing(authed_calendar_client):
    r = await authed_calendar_client.delete(
        "/api/seva/calendar/00000000-0000-0000-0000-000000000000"
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# P1 round-trip defense (TZ=UTC, date string stays identical across POST/GET)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_then_get_round_trips_date_in_utc(authed_calendar_client):
    """P1 defense: the date a UTC server receives is the date it returns.

    With `os.environ['TZ'] = 'UTC'` set at module top, this asserts the
    Pydantic date_type field round-trips a YYYY-MM-DD string without any
    silent datetime conversion that would slip into the prior/next day.
    """
    r1 = await authed_calendar_client.post(
        "/api/seva/calendar", json={"date": "2026-11-15", "body": "P1 test"}
    )
    assert r1.status_code == 201
    assert r1.json()["date"] == "2026-11-15"

    r2 = await authed_calendar_client.get(
        "/api/seva/calendar?start=2026-11-15&end=2026-11-15"
    )
    assert r2.json()["items"][0]["date"] == "2026-11-15"
