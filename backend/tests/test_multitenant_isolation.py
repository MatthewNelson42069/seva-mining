"""Cross-tenant leak detection (TENANT-10).

Phase 9 Wave 0 RED — production code lands in Wave 2 (09-03-PLAN.md).
Router prefix expected at:
    /api/{company}/summaries
    /api/{company}/calendar?start=...&end=...
    /api/{company}/weekly-sweeps

Creates rows for BOTH tenants, then asserts each tenant's API returns ONLY
its own rows. Parametrized over ('seva', 'juno') so symmetry is explicit.
Catches any router that bypasses scoped_*() helpers.

Sources:
- PITFALLS.md CRITICAL-2 ("Query without company_id filter is the #1
  multi-tenancy bug")
- 09-CONTEXT.md TENANT-10
- 09-RESEARCH.md §Code Example 10 (this file is a near-verbatim copy)

The module-level pytest.skip below is the canonical Phase-9 Wave-0 idiom:
removing this single line in Wave 2 (after the /api/{company}/* router prefix
+ get_current_company() dependency land) turns the whole module GREEN.
"""
from __future__ import annotations

import pytest

pytest.skip(
    "/api/{company}/* router prefix lands in Wave 2 (09-03-PLAN.md). "
    "Remove this line in Wave 2 Task 1 step 6 to turn tests GREEN.",
    allow_module_level=True,
)

# ---------------------------------------------------------------------------
# Unreachable until Wave 2 removes the skip line above. Lazy imports inside
# each test so the module collects cleanly even before the models carry
# company_id and the router prefix lands.
# ---------------------------------------------------------------------------

import uuid
from datetime import datetime, timezone

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.calendar_item import CalendarItem
from app.models.daily_summary import DailySummary
from app.models.weekly_sweep import WeeklySweep


@pytest_asyncio.fixture
async def both_tenant_rows(async_db_session: AsyncSession):
    """Seed one row per tenant per multi-tenant table."""
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
    for row in rows:
        async_db_session.add(row)
    await async_db_session.commit()
    return rows


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
    authed_client, both_tenant_rows, company, endpoint
):
    """Each tenant's endpoint returns ONLY its own rows.

    Schema-agnostic check: walk the JSON response for any dict that has a
    "company_id" field, assert it matches the expected tenant. Catches any
    response shape where a row from the OTHER tenant leaks through.
    """
    url = endpoint.format(company=company)
    response = await authed_client.get(url)
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
async def test_invalid_company_returns_404(authed_client, invalid_slug):
    """get_current_company validation rejects malformed/unknown slugs.

    Either the path-regex `^[a-z][a-z0-9-]{1,19}$` rejects with 422, or the
    dependency rejects with 404 — both are acceptable.
    """
    response = await authed_client.get(f"/api/{invalid_slug}/summaries")
    assert response.status_code in (404, 422), (
        f"Expected 404 or 422 for invalid slug {invalid_slug!r}, "
        f"got {response.status_code}"
    )
