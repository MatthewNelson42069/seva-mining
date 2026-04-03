"""
CRUD endpoint tests for watchlists, keywords, agent-runs, digests, and content.
Requirements: EXEC-01 (agent-runs filter), AUTH-03 (all endpoints require auth)
"""
import pytest
import pytest_asyncio
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, Numeric, Date
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON
from sqlalchemy.orm import DeclarativeBase

from app.main import app
from app.database import get_db
from app.auth import create_access_token

# Use a separate in-memory SQLite for these tests (tables created fresh each time)
_TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


def _make_engine():
    return create_async_engine(_TEST_DB_URL, echo=False)


# SQLite-compatible versions of the models (JSONB -> JSON, no PostgreSQL-specific types)
class _TestBase(DeclarativeBase):
    pass


import uuid as _uuid
from sqlalchemy import Column as Col


def _uuid_default():
    return str(_uuid.uuid4())


class _Watchlist(_TestBase):
    __tablename__ = "watchlists"
    id = Col(String(36), primary_key=True, default=_uuid_default)
    platform = Col(String(20), nullable=False)
    account_handle = Col(String(255), nullable=False)
    platform_user_id = Col(String(50))
    relationship_value = Col(Integer)
    follower_threshold = Col(Integer)
    notes = Col(Text)
    active = Col(Boolean, nullable=False, default=True)
    created_at = Col(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Col(DateTime(timezone=True))


class _Keyword(_TestBase):
    __tablename__ = "keywords"
    id = Col(String(36), primary_key=True, default=_uuid_default)
    term = Col(String(255), nullable=False)
    platform = Col(String(20))
    weight = Col(Numeric(4, 2), default=1.0)
    active = Col(Boolean, nullable=False, default=True)
    created_at = Col(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Col(DateTime(timezone=True))


class _AgentRun(_TestBase):
    __tablename__ = "agent_runs"
    id = Col(String(36), primary_key=True, default=_uuid_default)
    agent_name = Col(String(50), nullable=False)
    started_at = Col(DateTime(timezone=True), nullable=False)
    ended_at = Col(DateTime(timezone=True))
    items_found = Col(Integer, default=0)
    items_queued = Col(Integer, default=0)
    items_filtered = Col(Integer, default=0)
    errors = Col(SQLiteJSON)
    status = Col(String(20))
    notes = Col(Text)
    created_at = Col(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class _DailyDigest(_TestBase):
    __tablename__ = "daily_digests"
    id = Col(String(36), primary_key=True, default=_uuid_default)
    digest_date = Col(Date, nullable=False, unique=True)
    top_stories = Col(SQLiteJSON)
    queue_snapshot = Col(SQLiteJSON)
    yesterday_approved = Col(SQLiteJSON)
    yesterday_rejected = Col(SQLiteJSON)
    yesterday_expired = Col(SQLiteJSON)
    priority_alert = Col(SQLiteJSON)
    whatsapp_sent_at = Col(DateTime(timezone=True))
    created_at = Col(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class _ContentBundle(_TestBase):
    __tablename__ = "content_bundles"
    id = Col(String(36), primary_key=True, default=_uuid_default)
    story_headline = Col(Text, nullable=False)
    story_url = Col(Text)
    source_name = Col(String(255))
    format_type = Col(String(50))
    score = Col(Numeric(5, 2))
    quality_score = Col(Numeric(5, 2))
    no_story_flag = Col(Boolean, nullable=False, default=False)
    deep_research = Col(SQLiteJSON)
    draft_content = Col(SQLiteJSON)
    compliance_passed = Col(Boolean)
    created_at = Col(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class _Config(_TestBase):
    __tablename__ = "config"
    key = Col(String(100), primary_key=True)
    value = Col(Text, nullable=False)
    updated_at = Col(DateTime(timezone=True))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def db_client():
    """
    HTTP test client with its own SQLite in-memory DB.
    Tables are created from ORM models before yielding.
    """
    engine = _make_engine()

    # Create SQLite-compatible tables for this test module
    async with engine.begin() as conn:
        await conn.run_sync(_TestBase.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_db, None)
    await engine.dispose()


@pytest_asyncio.fixture
async def authed_db_client(db_client):
    """db_client with Authorization: Bearer header pre-set."""
    token = create_access_token()
    db_client.headers.update({"Authorization": f"Bearer {token}"})
    yield db_client


# ---------------------------------------------------------------------------
# Watchlist tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_watchlists_empty(authed_db_client):
    """GET /watchlists returns empty list when no entries exist."""
    response = await authed_db_client.get("/watchlists")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_create_watchlist(authed_db_client):
    """POST /watchlists with valid body returns 201 and created entry."""
    payload = {
        "platform": "twitter",
        "account_handle": "@goldanalyst",
        "relationship_value": 4,
        "active": True,
    }
    response = await authed_db_client.post("/watchlists", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["platform"] == "twitter"
    assert data["account_handle"] == "@goldanalyst"
    assert data["relationship_value"] == 4
    assert "id" in data


@pytest.mark.asyncio
async def test_list_watchlists_with_platform_filter(authed_db_client):
    """GET /watchlists?platform=twitter filters by platform."""
    # Create two entries
    await authed_db_client.post("/watchlists", json={"platform": "twitter", "account_handle": "@tw1"})
    await authed_db_client.post("/watchlists", json={"platform": "instagram", "account_handle": "@ig1"})

    response = await authed_db_client.get("/watchlists?platform=twitter")
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1
    assert items[0]["platform"] == "twitter"


@pytest.mark.asyncio
async def test_update_watchlist(authed_db_client):
    """PATCH /watchlists/{id} partially updates the entry."""
    create_resp = await authed_db_client.post(
        "/watchlists", json={"platform": "twitter", "account_handle": "@update_me"}
    )
    watchlist_id = create_resp.json()["id"]

    patch_resp = await authed_db_client.patch(
        f"/watchlists/{watchlist_id}", json={"active": False, "notes": "Paused"}
    )
    assert patch_resp.status_code == 200
    data = patch_resp.json()
    assert data["active"] is False
    assert data["notes"] == "Paused"
    assert data["account_handle"] == "@update_me"  # unchanged field preserved


@pytest.mark.asyncio
async def test_delete_watchlist(authed_db_client):
    """DELETE /watchlists/{id} returns 204 and entry is gone."""
    create_resp = await authed_db_client.post(
        "/watchlists", json={"platform": "instagram", "account_handle": "@delete_me"}
    )
    watchlist_id = create_resp.json()["id"]

    del_resp = await authed_db_client.delete(f"/watchlists/{watchlist_id}")
    assert del_resp.status_code == 204

    # Confirm gone
    list_resp = await authed_db_client.get("/watchlists")
    ids = [w["id"] for w in list_resp.json()]
    assert watchlist_id not in ids


# ---------------------------------------------------------------------------
# Keyword tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_keywords_empty(authed_db_client):
    """GET /keywords returns empty list when no keywords exist."""
    response = await authed_db_client.get("/keywords")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_create_keyword(authed_db_client):
    """POST /keywords with valid body returns 201 and created entry."""
    payload = {"term": "gold mining", "platform": "twitter", "weight": 1.5, "active": True}
    response = await authed_db_client.post("/keywords", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["term"] == "gold mining"
    assert data["platform"] == "twitter"
    assert "id" in data


@pytest.mark.asyncio
async def test_list_keywords_with_active_filter(authed_db_client):
    """GET /keywords?active=true returns only active keywords."""
    await authed_db_client.post("/keywords", json={"term": "active_kw", "active": True})
    await authed_db_client.post("/keywords", json={"term": "inactive_kw", "active": False})

    response = await authed_db_client.get("/keywords?active=true")
    assert response.status_code == 200
    items = response.json()
    assert all(k["active"] for k in items)
    assert any(k["term"] == "active_kw" for k in items)


@pytest.mark.asyncio
async def test_update_keyword(authed_db_client):
    """PATCH /keywords/{id} partially updates the keyword."""
    create_resp = await authed_db_client.post("/keywords", json={"term": "patch_me"})
    keyword_id = create_resp.json()["id"]

    patch_resp = await authed_db_client.patch(
        f"/keywords/{keyword_id}", json={"weight": 2.5, "active": False}
    )
    assert patch_resp.status_code == 200
    data = patch_resp.json()
    assert data["active"] is False
    assert data["term"] == "patch_me"  # unchanged field preserved


@pytest.mark.asyncio
async def test_delete_keyword(authed_db_client):
    """DELETE /keywords/{id} returns 204 and keyword is gone."""
    create_resp = await authed_db_client.post("/keywords", json={"term": "delete_me"})
    keyword_id = create_resp.json()["id"]

    del_resp = await authed_db_client.delete(f"/keywords/{keyword_id}")
    assert del_resp.status_code == 204

    list_resp = await authed_db_client.get("/keywords")
    ids = [k["id"] for k in list_resp.json()]
    assert keyword_id not in ids


# ---------------------------------------------------------------------------
# Agent run tests (EXEC-01)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_agent_runs_empty(authed_db_client):
    """GET /agent-runs returns empty list when no runs exist."""
    response = await authed_db_client.get("/agent-runs")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_agent_runs_filter_by_name(authed_db_client):
    """
    GET /agent-runs?agent_name=twitter_agent returns only runs for that agent.
    EXEC-01: agent-runs endpoint filterable by agent_name.
    """
    # Directly insert agent run records via the override session
    override_fn = app.dependency_overrides.get(get_db)
    async for db in override_fn():
        now = datetime.now(timezone.utc)
        run_twitter = _AgentRun(
            agent_name="twitter_agent",
            started_at=now,
            status="completed",
            items_found=5,
            items_queued=3,
            items_filtered=2,
        )
        run_insta = _AgentRun(
            agent_name="instagram_agent",
            started_at=now,
            status="completed",
            items_found=2,
            items_queued=1,
            items_filtered=1,
        )
        db.add(run_twitter)
        db.add(run_insta)
        await db.commit()
        break

    response = await authed_db_client.get("/agent-runs?agent_name=twitter_agent&days=1")
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1
    assert items[0]["agent_name"] == "twitter_agent"


# ---------------------------------------------------------------------------
# Digest tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_latest_digest_404(authed_db_client):
    """GET /digests/latest returns 404 when no digests exist."""
    response = await authed_db_client.get("/digests/latest")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_digest_by_date_404(authed_db_client):
    """GET /digests/{date} returns 404 when digest not found for that date."""
    response = await authed_db_client.get("/digests/2025-01-01")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Content tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_today_content_404(authed_db_client):
    """GET /content/today returns 404 when no content bundle exists for today."""
    response = await authed_db_client.get("/content/today")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# AUTH-03: all CRUD endpoints require auth token
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_all_crud_require_auth(db_client):
    """
    All CRUD endpoints return 403 (HTTPBearer) or 401 without auth token.
    AUTH-03: all endpoints protected by get_current_user.
    """
    endpoints = [
        ("GET", "/watchlists"),
        ("POST", "/watchlists"),
        ("GET", "/keywords"),
        ("POST", "/keywords"),
        ("GET", "/agent-runs"),
        ("GET", "/digests/latest"),
        ("GET", "/content/today"),
    ]
    for method, path in endpoints:
        if method == "GET":
            response = await db_client.get(path)
        else:
            response = await db_client.post(path, json={})
        assert response.status_code in (401, 403), (
            f"{method} {path} should require auth, got {response.status_code}"
        )


# ---------------------------------------------------------------------------
# Config tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_config_empty(authed_db_client):
    """GET /config returns empty list when no config entries exist."""
    response = await authed_db_client.get("/config")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_patch_config_create(authed_db_client):
    """PATCH /config/{key} creates a new config entry when key does not exist."""
    response = await authed_db_client.patch(
        "/config/content_quality_threshold",
        json={"value": "7.5"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["key"] == "content_quality_threshold"
    assert data["value"] == "7.5"

    # Verify it appears in list
    list_resp = await authed_db_client.get("/config")
    assert len(list_resp.json()) == 1


@pytest.mark.asyncio
async def test_patch_config_update(authed_db_client):
    """PATCH /config/{key} updates existing config entry."""
    # Create first
    await authed_db_client.patch(
        "/config/content_quality_threshold",
        json={"value": "7.0"},
    )
    # Update
    response = await authed_db_client.patch(
        "/config/content_quality_threshold",
        json={"value": "8.0"},
    )
    assert response.status_code == 200
    assert response.json()["value"] == "8.0"

    # Verify only one entry
    list_resp = await authed_db_client.get("/config")
    assert len(list_resp.json()) == 1
    assert list_resp.json()[0]["value"] == "8.0"
