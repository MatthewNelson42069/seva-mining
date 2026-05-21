"""Phase 15 D-09 — Cross-tenant weekly-sweeps list isolation.

Mirrors backend/tests/test_calendar_cross_tenant.py (Phase 14 D-05) for the
/api/{company}/weekly-sweeps endpoint. Self-contained: own SQLite engine,
own table-create, own get_db override. Independent of the shared `client`
fixture in conftest.py which lacks the weekly_sweeps table.

JSWEEP-06 contract: GET /api/seva/weekly-sweeps returns ONLY Seva sweeps;
GET /api/juno/weekly-sweeps returns ONLY Juno sweeps. Zero leak in either
direction.

Semantic note vs Phase 14 D-05: The weekly_sweeps router exposes only GET
(cron-written rows; no user-facing PATCH/DELETE), so the "404 on cross-tenant
UUID" assertion doesn't apply here — isolation manifests as "list returns
zero rows for the wrong tenant prefix" instead. Same defence-in-depth
semantic; different surface area.
"""
from __future__ import annotations

import os
from datetime import UTC, date, datetime

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.ext.compiler import compiles

from app.database import get_db
from app.main import app
from app.models.weekly_sweep import WeeklySweep


# SQLite has no JSONB — compile JSONB to JSON when running against SQLite so
# WeeklySweep.__table__.create() succeeds for the in-memory test DB.
# Production (Neon Postgres) is unaffected — the @compiles dispatcher only
# fires for the 'sqlite' dialect. Mirrors test_multitenant_isolation.py:84-86.
@compiles(JSONB, "sqlite")
def _compile_jsonb_as_json_on_sqlite(type_, compiler, **kw):  # noqa: D401
    return compiler.visit_JSON(JSON())


_TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


# ---------------------------------------------------------------------------
# Fixtures — self-contained engine + weekly_sweeps table create
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def cross_tenant_client_and_session():
    """HTTP client + raw session factory.

    The session factory is exposed so tests can seed weekly_sweeps rows
    directly (cron-write simulation — no public POST endpoint exists).

    Mirrors test_multitenant_isolation.py:108-124 fixture shape: a single
    SQLite engine shared between row-seeding session AND the HTTP client
    so a session-inserted row is visible to subsequent /api/{company}/
    requests routed through the same get_db override.
    """
    engine = create_async_engine(_TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        # Postgres-only types (UUID, JSONB) compile against SQLite via
        # SQLAlchemy's generic fallbacks — same pattern proven in
        # test_multitenant_isolation.py:122.
        await conn.run_sync(lambda c: WeeklySweep.__table__.create(c))

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
        ac.cookies.set("seva_auth_token", os.environ["SEVA_DASHBOARD_TOKEN"])
        yield (ac, session_factory)
    app.dependency_overrides.pop(get_db, None)
    await engine.dispose()


async def _seed_sweep(
    session_factory,
    *,
    company_id: str,
    week_offset_days: int = 0,
) -> str:
    """Insert a weekly_sweeps row directly (cron-write simulation).

    Returns the inserted row's UUID (as a string) for assertion use.
    """
    sweep = WeeklySweep(
        company_id=company_id,
        generated_at=datetime.now(UTC),
        week_start=date(2026, 6, 1) if week_offset_days == 0 else date(2026, 6, 8),
        week_end=date(2026, 6, 7) if week_offset_days == 0 else date(2026, 6, 14),
        reddit_top_md=f"### Top X Posts ({company_id})\n\n* test post",
        story_virality_md=f"### Most Cross-Referenced Stories ({company_id})\n\n* test story",
        content_angles_md=f"### Angle 1: test ({company_id})\n\nbody",
        raw_sources_jsonb={"test_seed": True, "company_id": company_id},
        status="completed",
        error_text=None,
        agent_run_id=None,
    )
    async with session_factory() as session:
        session.add(sweep)
        await session.commit()
        await session.refresh(sweep)
        return str(sweep.id)


# ---------------------------------------------------------------------------
# Cross-tenant GET-list isolation — both directions, list-level contract
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_seva_sweep_not_visible_via_juno_prefix(
    cross_tenant_client_and_session,
):
    """JSWEEP-06 — A Seva-seeded sweep MUST NOT appear via /api/juno/weekly-sweeps."""
    client, session_factory = cross_tenant_client_and_session
    seva_uuid = await _seed_sweep(session_factory, company_id="seva")

    # GET via Juno prefix — must return EMPTY list (0 rows)
    juno_resp = await client.get("/api/juno/weekly-sweeps?limit=12")
    assert juno_resp.status_code == 200, juno_resp.text
    juno_body = juno_resp.json()
    assert juno_body["total"] == 0, (
        f"Cross-tenant leak: Seva row {seva_uuid} surfaced via /api/juno/weekly-sweeps. "
        f"total={juno_body['total']}, sweeps={juno_body['sweeps']}"
    )
    assert juno_body["sweeps"] == []

    # Defence-in-depth — confirm the Seva row IS visible via Seva prefix
    seva_resp = await client.get("/api/seva/weekly-sweeps?limit=12")
    assert seva_resp.status_code == 200
    seva_body = seva_resp.json()
    assert seva_body["total"] >= 1
    assert any(s["id"] == seva_uuid for s in seva_body["sweeps"])


@pytest.mark.asyncio
async def test_juno_sweep_not_visible_via_seva_prefix(
    cross_tenant_client_and_session,
):
    """JSWEEP-06 inverse — Juno-seeded sweep MUST NOT appear via /api/seva/weekly-sweeps."""
    client, session_factory = cross_tenant_client_and_session
    juno_uuid = await _seed_sweep(session_factory, company_id="juno")

    # GET via Seva prefix — must return EMPTY list
    seva_resp = await client.get("/api/seva/weekly-sweeps?limit=12")
    assert seva_resp.status_code == 200, seva_resp.text
    seva_body = seva_resp.json()
    assert seva_body["total"] == 0, (
        f"Cross-tenant leak: Juno row {juno_uuid} surfaced via /api/seva/weekly-sweeps. "
        f"total={seva_body['total']}, sweeps={seva_body['sweeps']}"
    )
    assert seva_body["sweeps"] == []

    # Confirm Juno-prefix sees the row
    juno_resp = await client.get("/api/juno/weekly-sweeps?limit=12")
    assert juno_resp.status_code == 200
    juno_body = juno_resp.json()
    assert juno_body["total"] >= 1
    assert any(s["id"] == juno_uuid for s in juno_body["sweeps"])


@pytest.mark.asyncio
async def test_mixed_seed_each_tenant_sees_only_its_own(
    cross_tenant_client_and_session,
):
    """JSWEEP-06 — Mixed-data scenario: 1 Seva row + 1 Juno row in DB.

    /api/seva/weekly-sweeps returns 1 row (the Seva one); /api/juno/weekly-sweeps
    returns 1 row (the Juno one). Zero leak in either direction.
    """
    client, session_factory = cross_tenant_client_and_session
    seva_uuid = await _seed_sweep(session_factory, company_id="seva")
    juno_uuid = await _seed_sweep(
        session_factory, company_id="juno", week_offset_days=7
    )

    seva_resp = await client.get("/api/seva/weekly-sweeps?limit=12")
    assert seva_resp.status_code == 200
    seva_body = seva_resp.json()
    seva_ids = {s["id"] for s in seva_body["sweeps"]}
    assert seva_body["total"] == 1
    assert seva_uuid in seva_ids
    assert juno_uuid not in seva_ids, (
        f"Cross-tenant leak in mixed-seed: Juno row {juno_uuid} surfaced "
        f"via /api/seva/weekly-sweeps"
    )

    juno_resp = await client.get("/api/juno/weekly-sweeps?limit=12")
    assert juno_resp.status_code == 200
    juno_body = juno_resp.json()
    juno_ids = {s["id"] for s in juno_body["sweeps"]}
    assert juno_body["total"] == 1
    assert juno_uuid in juno_ids
    assert seva_uuid not in juno_ids, (
        f"Cross-tenant leak in mixed-seed: Seva row {seva_uuid} surfaced "
        f"via /api/juno/weekly-sweeps"
    )
