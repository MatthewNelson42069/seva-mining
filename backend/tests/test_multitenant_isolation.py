"""Cross-tenant leak detection (TENANT-10).

v3.0 Phase 9 Wave 4 (09-05-PLAN.md Task 1) — fully populated parametrized
cross-tenant isolation tests. Each tenant's endpoint MUST return ONLY its own
rows; create/patch handlers MUST inject server-side ``company_id`` (path
parameter) and refuse cross-tenant mutations.

Router prefix:
    /api/{company}/summaries
    /api/{company}/calendar?start=...&end=...
    /api/{company}/weekly-sweeps

Coverage matrix (RESEARCH §Code Example 10 + 09-VALIDATION TENANT-10):
  * 6 tuples — ``{company} × {summaries, calendar, weekly-sweeps}`` —
    each asserts:
      (1) GET returns 200
      (2) response body row list contains ONLY rows where
          ``row.company_id == company`` (walks the JSON tree so the
          assertion is response-shape-agnostic)
      (3) returned row count for that table equals the seeded count
          (1 row per tenant per table — see ``both_tenant_rows``).
  * ``test_invalid_company_returns_404`` — regex-matching but unknown slug
    → 404 (dep body rejects).
  * ``test_invalid_company_uppercase_returns_422`` — FastAPI Path regex
    rejects uppercase BEFORE the dep body runs → 422.
  * ``test_unprefixed_legacy_url_returns_404`` — ``GET /summaries`` no
    longer mounts post-Wave-2 (no accidental dual-registration).
  * ``test_create_calendar_item_persists_company_id`` — POST persists the
    URL-derived company, never trusting any client-supplied value.
  * ``test_patch_calendar_item_cannot_cross_tenant`` — PATCH on a Juno row
    via the Seva prefix returns 404 (scoped_calendar('seva') WHERE id=uuid
    returns no rows; defence-in-depth on top of URL prefix).

Fixture wiring (Wave 2 deviation — Rule 2 critical-functionality fix):
The shared ``tenant_test_client`` fixture creates ONE in-memory SQLite engine,
creates the 3 tenant-scoped tables on it, overrides FastAPI's ``get_db`` to
yield sessions from THAT engine, and exposes both the HTTP client AND a
session factory so the test can seed rows + hit endpoints against the same
database. The conftest's stock ``async_db_session`` + ``authed_client`` pair
use SEPARATE engines (per-fixture) and would never see each other's data
under SQLite ``:memory:`` semantics — that's why Wave 0 deferred this test.

PITFALL guard (PITFALLS.md MEDIUM-6 — test fixtures don't reset company_id
context between tests): every test acquires fresh seed rows via the
function-scoped ``both_tenant_rows`` fixture. No module-level state, no
ContextVar pollution between tests.

Sources:
- PITFALLS.md CRITICAL-2 ("Query without company_id filter is the #1
  multi-tenancy bug")
- 09-CONTEXT.md TENANT-10
- 09-RESEARCH.md §Code Example 10
- 09-VALIDATION.md §Per-Task Verification Map TENANT-10
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

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


# ---------------------------------------------------------------------------
# Endpoint-table coordinate mapping
# ---------------------------------------------------------------------------
# Each endpoint URL maps to (response_top_level_key, expected_row_count) so
# the parametrized assertion can crawl the response and verify both the
# company_id contract AND the row-count contract from a single matrix.
ENDPOINT_CONTRACT: dict[str, tuple[str, int]] = {
    "/api/{company}/summaries": ("summaries", 1),
    "/api/{company}/calendar?start=2026-01-01&end=2026-12-31": ("items", 1),
    "/api/{company}/weekly-sweeps": ("weekly_sweeps", 1),
}


# ---------------------------------------------------------------------------
# Engine + session-factory fixtures (shared between row-seeding and HTTP)
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def tenant_test_engine():
    """Single SQLite engine shared between row-seeding session AND HTTP client.

    Creates the 3 tenant-scoped tables (daily_summaries, calendar_items,
    weekly_sweeps). Postgres-only types (UUID, JSONB) compile against SQLite
    via SQLAlchemy's generic fallbacks for in-memory test execution.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        # Only create the 3 tenant-scoped tables — keep this module
        # self-contained.
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


# ---------------------------------------------------------------------------
# Seed-rows fixture — 1 row per tenant per multi-tenant table
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def both_tenant_rows(tenant_session_factory):
    """Seed one row per tenant per multi-tenant table via the shared engine.

    Total seed count: 6 rows (Seva + Juno × 3 tables). Each parametrized
    test combination verifies the slice of these 6 rows visible from its
    own tenant prefix.
    """
    now = datetime.now(UTC)
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


# ---------------------------------------------------------------------------
# Helper — walk JSON for cross-tenant leaks (response-shape-agnostic)
# ---------------------------------------------------------------------------

def _assert_no_other_tenant_rows(payload, expected_company: str) -> int:
    """Walk a JSON payload; assert every dict with a ``company_id`` field
    has ``company_id == expected_company``. Returns the count of dicts that
    DID carry the expected company_id (i.e. the row count returned by the
    API for this tenant).
    """
    other = "juno" if expected_company == "seva" else "seva"
    count = 0

    def walk(node):
        nonlocal count
        if isinstance(node, dict):
            row_company = node.get("company_id")
            if row_company == other:
                pytest.fail(
                    f"Cross-tenant leak: {expected_company} endpoint "
                    f"returned a {other} row: {node}"
                )
            if row_company == expected_company:
                count += 1
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(payload)
    return count


# ---------------------------------------------------------------------------
# Parametrized cross-tenant isolation matrix (6 combinations)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("company", ["seva", "juno"])
@pytest.mark.parametrize(
    "endpoint",
    list(ENDPOINT_CONTRACT.keys()),
)
async def test_tenant_isolation(
    tenant_authed_client, both_tenant_rows, company, endpoint
):
    """Each tenant's endpoint returns ONLY its own rows + the expected
    row count per the seed fixture (1 row per tenant per table).
    """
    url = endpoint.format(company=company)
    response = await tenant_authed_client.get(url)
    assert response.status_code == 200, (
        f"GET {url} returned {response.status_code}: {response.text}"
    )
    payload = response.json()

    # (1) + (2): no leakage, returns matching company_id rows only.
    seen_count = _assert_no_other_tenant_rows(payload, company)

    # (3): row count from the API matches the seeded fixture count
    #     (1 row per tenant per table — see ``both_tenant_rows``).
    _, expected_rows = ENDPOINT_CONTRACT[endpoint]
    assert seen_count == expected_rows, (
        f"Expected {expected_rows} {company} row(s) from {url}; "
        f"got {seen_count} (payload={payload})"
    )


# ---------------------------------------------------------------------------
# Invalid-slug handling — split into 404 (regex-matching unknown) and
# 422 (regex-rejected) cases per plan spec.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "unknown_slug",
    ["bogus", "nonsense", "seva-old"],
)
async def test_invalid_company_returns_404(tenant_authed_client, unknown_slug):
    """An ACTIVE-COMPANIES-miss slug (still matching the path regex)
    returns 404 with ``{"detail": "Unknown company: <slug>"}``.
    """
    response = await tenant_authed_client.get(f"/api/{unknown_slug}/summaries")
    assert response.status_code == 404, (
        f"Expected 404 for unknown slug {unknown_slug!r}, "
        f"got {response.status_code}: {response.text}"
    )
    body = response.json()
    assert body.get("detail") == f"Unknown company: {unknown_slug}", (
        f"Expected detail 'Unknown company: {unknown_slug}', got {body!r}"
    )


@pytest.mark.parametrize(
    "regex_invalid_slug",
    ["SEVA", "Seva", "seva!", "x" * 30, "1seva"],
)
async def test_invalid_company_uppercase_returns_422(
    tenant_authed_client, regex_invalid_slug
):
    """FastAPI Path(..., pattern=...) rejects regex misses with 422 BEFORE
    the ``get_current_company`` body runs (so 422 not 404 for these).
    """
    response = await tenant_authed_client.get(
        f"/api/{regex_invalid_slug}/summaries"
    )
    assert response.status_code == 422, (
        f"Expected 422 for regex-invalid slug {regex_invalid_slug!r}, "
        f"got {response.status_code}: {response.text}"
    )


# ---------------------------------------------------------------------------
# Legacy URL behaviour — confirm no accidental dual-registration
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "legacy_path",
    [
        "/summaries",
        "/calendar?start=2026-01-01&end=2026-12-31",
        "/weekly-sweeps",
    ],
)
async def test_unprefixed_legacy_url_returns_404(tenant_authed_client, legacy_path):
    """Post Wave 2, the v2.x unprefixed routes do NOT exist on the backend.

    The frontend handles ``/summaries`` etc. via grace-redirect ``<Navigate>``
    elements; the backend MUST NOT serve them (would indicate dual-router
    registration — a multi-tenancy escape hatch).
    """
    response = await tenant_authed_client.get(legacy_path)
    assert response.status_code == 404, (
        f"Legacy URL {legacy_path!r} should 404 (no backend mount), "
        f"got {response.status_code}: {response.text[:200]}"
    )


# ---------------------------------------------------------------------------
# Mutation handlers — company_id sourced from URL only; cross-tenant 404.
# ---------------------------------------------------------------------------

async def test_create_calendar_item_persists_company_id(
    tenant_authed_client, tenant_session_factory
):
    """POST /api/seva/calendar persists ``company_id='seva'`` from the URL.

    The client cannot override it — there is no ``company_id`` field on
    ``CalendarItemCreate``. Verify by re-reading the row from the DB.
    """
    response = await tenant_authed_client.post(
        "/api/seva/calendar",
        json={"date": "2026-01-01", "body": "hello"},
    )
    assert response.status_code == 201, (
        f"POST /api/seva/calendar returned {response.status_code}: "
        f"{response.text}"
    )
    body = response.json()
    new_id = uuid.UUID(body["id"])
    # Response also surfaces company_id for debug visibility (TENANT-04).
    assert body.get("company_id") == "seva", (
        f"Response company_id mismatch: {body!r}"
    )

    # Defence-in-depth: re-read from DB and confirm the row carries
    # company_id='seva' regardless of what the client sent.
    async with tenant_session_factory() as session:
        row = await session.get(CalendarItem, new_id)
        assert row is not None, "Created row not found in DB"
        assert row.company_id == "seva", (
            f"DB row has company_id={row.company_id!r}, expected 'seva'"
        )


async def test_patch_calendar_item_cannot_cross_tenant(
    tenant_authed_client, tenant_session_factory
):
    """PATCH /api/seva/calendar/{juno_uuid} returns 404.

    ``scoped_calendar('seva')`` filters WHERE company_id='seva'; the Juno
    row is not visible to that scoped select, so the handler hits the
    not-found branch BEFORE attempting any write. Confirms defence-in-depth
    on top of the URL prefix.
    """
    # Seed a Juno calendar_item with a known UUID directly.
    now = datetime.now(UTC)
    juno_uuid = uuid.uuid4()
    async with tenant_session_factory() as session:
        session.add(
            CalendarItem(
                id=juno_uuid,
                company_id="juno",
                date=now.date(),
                notes_md="Juno-only — Seva must not see this",
                created_at=now,
                updated_at=now,
            )
        )
        await session.commit()

    response = await tenant_authed_client.patch(
        f"/api/seva/calendar/{juno_uuid}",
        json={"body": "Seva tried to hijack this row"},
    )
    assert response.status_code == 404, (
        f"Expected 404 for cross-tenant PATCH; got {response.status_code}: "
        f"{response.text}"
    )

    # Confirm the underlying row was NOT mutated.
    async with tenant_session_factory() as session:
        row = await session.get(CalendarItem, juno_uuid)
        assert row is not None, "Juno seed row vanished — fixture bug"
        assert row.company_id == "juno", "Juno row company_id was mutated"
        assert row.notes_md == "Juno-only — Seva must not see this", (
            "Juno row notes_md was mutated by cross-tenant PATCH"
        )
