"""Phase 14 D-05 — Cross-tenant calendar CRUD isolation.

Mirrors the test_calendar_router.py fixture pattern (own SQLite engine
+ CalendarItem.__table__.create + get_db override) so this module is
self-contained. The existing test_multitenant_isolation.py covers ONE
direction (Seva-prefix PATCH on Juno UUID -> 404); Phase 14 adds the
INVERSE direction + DELETE coverage in a descriptively-named file.

JCAL-05 contract: cross-tenant CRUD attempts return 404 (NOT 403).
Tenant existence isolation: the row appears NOT TO EXIST from the
wrong tenant's prefix, not FORBIDDEN. This validates the row-level
defence-in-depth in `backend/app/routers/calendar.py` (PATCH lines
140-147 + DELETE lines 166-173) where `scoped_calendar(company)` is
used to re-look-up the row before mutating; a UUID belonging to a
different tenant returns no row from the scoped SELECT, surfacing as
the not-found 404 branch.
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.auth import create_access_token
from app.database import get_db
from app.main import app
from app.models.calendar_item import CalendarItem

_TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


# ---------------------------------------------------------------------------
# Fixtures — self-contained engine + calendar_items table create
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def cross_tenant_client():
    """HTTP client with calendar_items table created on a shared SQLite engine.

    A single engine is shared by all requests within a test so a POST under
    /api/seva/ and a follow-up PATCH under /api/juno/ both see the same
    row (cross-tenant attack vector).
    """
    engine = create_async_engine(_TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: CalendarItem.__table__.create(c))

    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.pop(get_db, None)
    await engine.dispose()


@pytest_asyncio.fixture
async def authed_cross_tenant_client(cross_tenant_client):
    """cross_tenant_client with Authorization: Bearer header pre-set."""
    token = create_access_token()
    cross_tenant_client.headers.update({"Authorization": f"Bearer {token}"})
    yield cross_tenant_client


# ---------------------------------------------------------------------------
# PATCH cross-tenant — both directions, 404 contract
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_seva_uuid_via_juno_prefix_returns_404(
    authed_cross_tenant_client,
):
    """JCAL-05 — Seva-owned row, PATCH attempt via /api/juno/ returns 404."""
    # Seed a Seva row.
    create = await authed_cross_tenant_client.post(
        "/api/seva/calendar",
        json={"date": "2026-06-01", "body": "seva content"},
    )
    assert create.status_code == 201, create.text
    seva_uuid = create.json()["id"]

    # Cross-tenant PATCH via the Juno prefix.
    attack = await authed_cross_tenant_client.patch(
        f"/api/juno/calendar/{seva_uuid}",
        json={"body": "juno tried to steal"},
    )
    assert attack.status_code == 404, (
        f"Expected 404 (tenant existence isolation per JCAL-05); "
        f"got {attack.status_code}: {attack.text}"
    )

    # Confirm the Seva row was NOT mutated.
    readback = await authed_cross_tenant_client.get(
        "/api/seva/calendar?start=2026-06-01&end=2026-06-01"
    )
    assert readback.status_code == 200
    items = readback.json()["items"]
    assert len(items) == 1
    assert items[0]["body"] == "seva content", (
        f"Cross-tenant PATCH leaked: body is {items[0]['body']!r}"
    )


@pytest.mark.asyncio
async def test_patch_juno_uuid_via_seva_prefix_returns_404(
    authed_cross_tenant_client,
):
    """JCAL-05 — Juno-owned row, PATCH attempt via /api/seva/ returns 404
    (inverse direction — gap from existing test_multitenant_isolation.py:401)."""
    # Seed a Juno row.
    create = await authed_cross_tenant_client.post(
        "/api/juno/calendar",
        json={"date": "2026-06-02", "body": "juno content"},
    )
    assert create.status_code == 201, create.text
    juno_uuid = create.json()["id"]

    # Cross-tenant PATCH via the Seva prefix.
    attack = await authed_cross_tenant_client.patch(
        f"/api/seva/calendar/{juno_uuid}",
        json={"body": "seva tried to steal"},
    )
    assert attack.status_code == 404, (
        f"Expected 404 (tenant existence isolation per JCAL-05); "
        f"got {attack.status_code}: {attack.text}"
    )

    # Confirm the Juno row was NOT mutated.
    readback = await authed_cross_tenant_client.get(
        "/api/juno/calendar?start=2026-06-02&end=2026-06-02"
    )
    assert readback.status_code == 200
    items = readback.json()["items"]
    assert len(items) == 1
    assert items[0]["body"] == "juno content", (
        f"Cross-tenant PATCH leaked: body is {items[0]['body']!r}"
    )


# ---------------------------------------------------------------------------
# DELETE cross-tenant — both directions, 404 contract
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_seva_uuid_via_juno_prefix_returns_404(
    authed_cross_tenant_client,
):
    """JCAL-05 — Seva-owned row, DELETE attempt via /api/juno/ returns 404
    and leaves the row intact."""
    create = await authed_cross_tenant_client.post(
        "/api/seva/calendar",
        json={"date": "2026-06-03", "body": "seva delete-target"},
    )
    assert create.status_code == 201, create.text
    seva_uuid = create.json()["id"]

    attack = await authed_cross_tenant_client.delete(
        f"/api/juno/calendar/{seva_uuid}"
    )
    assert attack.status_code == 404, (
        f"Expected 404 (tenant existence isolation per JCAL-05); "
        f"got {attack.status_code}: {attack.text}"
    )

    # Row still present under Seva.
    readback = await authed_cross_tenant_client.get(
        "/api/seva/calendar?start=2026-06-03&end=2026-06-03"
    )
    assert readback.status_code == 200
    items = readback.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == seva_uuid


@pytest.mark.asyncio
async def test_delete_juno_uuid_via_seva_prefix_returns_404(
    authed_cross_tenant_client,
):
    """JCAL-05 — Juno-owned row, DELETE attempt via /api/seva/ returns 404
    and leaves the row intact."""
    create = await authed_cross_tenant_client.post(
        "/api/juno/calendar",
        json={"date": "2026-06-04", "body": "juno delete-target"},
    )
    assert create.status_code == 201, create.text
    juno_uuid = create.json()["id"]

    attack = await authed_cross_tenant_client.delete(
        f"/api/seva/calendar/{juno_uuid}"
    )
    assert attack.status_code == 404, (
        f"Expected 404 (tenant existence isolation per JCAL-05); "
        f"got {attack.status_code}: {attack.text}"
    )

    # Row still present under Juno.
    readback = await authed_cross_tenant_client.get(
        "/api/juno/calendar?start=2026-06-04&end=2026-06-04"
    )
    assert readback.status_code == 200
    items = readback.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == juno_uuid
