"""Cross-tenant leak detection (TENANT-10).

v3.0 Phase 9 Wave 2 — production code landed in 09-03-PLAN.md. Tests verify
that each tenant's endpoint returns ONLY its own rows. Catches any router
that bypasses `scoped_*()` helpers.

Router prefix:
    /api/{company}/summaries
    /api/{company}/calendar?start=...&end=...
    /api/{company}/weekly-sweeps

Fixture wiring (Wave 2 deviation — Rule 2 critical-functionality fix):
The shared `tenant_test_client` fixture creates ONE in-memory SQLite engine,
creates the 3 tenant-scoped tables on it, overrides FastAPI's `get_db` to
yield sessions from THAT engine, and exposes both the HTTP client AND a
session factory so the test can seed rows + hit endpoints against the same
database. The conftest's stock `async_db_session` + `authed_client` pair
use SEPARATE engines (per-fixture) and would never see each other's data
under SQLite `:memory:` semantics — that's why Wave 0 deferred this test.

Sources:
- PITFALLS.md CRITICAL-2 ("Query without company_id filter is the #1
  multi-tenancy bug")
- 09-CONTEXT.md TENANT-10
- 09-RESEARCH.md §Code Example 10
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

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

from app.auth import create_access_token
from app.database import get_db
from app.main import app
from app.models.calendar_item import CalendarItem
from app.models.daily_summary import DailySummary
from app.models.weekly_sweep import WeeklySweep


# SQLite has no JSONB — compile JSONB to JSON when running against SQLite so
# the model.__table__.create() call below succeeds for the in-memory test DB.
# Production (Neon Postgres) is unaffected — the @compiles dispatcher only
# fires for the 'sqlite' dialect.
@compiles(JSONB, "sqlite")
def _compile_jsonb_as_json_on_sqlite(type_, compiler, **kw):  # noqa: D401
    return compiler.visit_JSON(JSON())

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def tenant_test_engine():
    """Single SQLite engine shared between row-seeding session AND HTTP client.

    Creates the 3 tenant-scoped tables (daily_summaries, calendar_items,
    weekly_sweeps). Postgres-only types (UUID, JSONB) compile against SQLite
    via SQLAlchemy's generic fallbacks for in-memory test execution.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        # Only create the 3 tenant-scoped tables — keep this module self-contained.
        await conn.run_sync(lambda c: DailySummary.__table__.create(c))
        await conn.run_sync(lambda c: CalendarItem.__table__.create(c))
        await conn.run_sync(lambda c: WeeklySweep.__table__.create(c))
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def tenant_session_factory(tenant_test_engine):
    """Async session factory bound to the shared engine."""
    return async_sessionmaker(
        tenant_test_engine, class_=AsyncSession, expire_on_commit=False
    )


@pytest_asyncio.fixture
async def both_tenant_rows(tenant_session_factory):
    """Seed one row per tenant per multi-tenant table via the shared engine."""
    now = datetime.now(timezone.utc)
    rows = [
        DailySummary(
            id=uuid.uuid4(),
            company_id="seva",
            generated_at=now,
            period_label="08:00 PT",
            gold_news_md="Seva gold news",
            raw_sources_jsonb={"company": "seva"},
            status="completed",
            created_at=now,
        ),
        DailySummary(
            id=uuid.uuid4(),
            company_id="juno",
            generated_at=now,
            period_label="08:05 PT",
            gold_news_md=None,
            raw_sources_jsonb={"company": "juno"},
            status="partial",
            created_at=now,
        ),
        CalendarItem(
            id=uuid.uuid4(),
            company_id="seva",
            date=now.date(),
            notes_md="Seva calendar item",
            created_at=now,
            updated_at=now,
        ),
        CalendarItem(
            id=uuid.uuid4(),
            company_id="juno",
            date=now.date(),
            notes_md="Juno calendar item",
            created_at=now,
            updated_at=now,
        ),
        WeeklySweep(
            id=uuid.uuid4(),
            company_id="seva",
            generated_at=now,
            week_start=now.date(),
            week_end=now.date(),
            status="completed",
        ),
        WeeklySweep(
            id=uuid.uuid4(),
            company_id="juno",
            generated_at=now,
            week_start=now.date(),
            week_end=now.date(),
            status="partial",
        ),
    ]
    async with tenant_session_factory() as session:
        for row in rows:
            session.add(row)
        await session.commit()
    return rows


@pytest_asyncio.fixture
async def tenant_authed_client(tenant_session_factory):
    """HTTP client wired to the SHARED engine via get_db override + Authorization header."""
    async def override_get_db():
        async with tenant_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    token = create_access_token()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        ac.headers.update({"Authorization": f"Bearer {token}"})
        yield ac
    app.dependency_overrides.pop(get_db, None)


@pytest.mark.parametrize("company", ["seva", "juno"])
@pytest.mark.parametrize(
    "endpoint",
    [
        "/api/{company}/summaries",
        "/api/{company}/calendar?start=2026-01-01&end=2026-12-31",
        "/api/{company}/weekly-sweeps",
    ],
)
async def test_tenant_isolation(
    tenant_authed_client, both_tenant_rows, company, endpoint
):
    """Each tenant's endpoint returns ONLY its own rows.

    Schema-agnostic check: walk the JSON response for any dict that has a
    "company_id" field, assert it matches the expected tenant. Catches any
    response shape where a row from the OTHER tenant leaks through.
    """
    url = endpoint.format(company=company)
    response = await tenant_authed_client.get(url)
    assert response.status_code == 200, (
        f"GET {url} returned {response.status_code}: {response.text}"
    )
    payload = response.json()

    other = "juno" if company == "seva" else "seva"

    def walk(node):
        if isinstance(node, dict):
            if node.get("company_id") == other:
                pytest.fail(
                    f"Cross-tenant leak: {company} endpoint returned a "
                    f"{other} row: {node}"
                )
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(payload)


@pytest.mark.parametrize(
    "invalid_slug",
    ["nonsense", "SEVA", "seva!", "x" * 30],
)
async def test_invalid_company_returns_404(tenant_authed_client, invalid_slug):
    """get_current_company validation rejects malformed/unknown slugs.

    Either the path-regex `^[a-z][a-z0-9-]{1,19}$` rejects with 422, or the
    dependency rejects with 404 — both are acceptable.
    """
    response = await tenant_authed_client.get(f"/api/{invalid_slug}/summaries")
    assert response.status_code in (404, 422), (
        f"Expected 404 or 422 for invalid slug {invalid_slug!r}, "
        f"got {response.status_code}"
    )
