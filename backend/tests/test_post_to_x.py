"""Integration tests for backend/app/routers/post_to_x.py.

Phase B (quick-260424-l0d) Task 3.

All tests MOCK both the DB session AND tweepy — zero real network I/O,
zero real Postgres rows. Per CONTEXT.md D14: "All unit + integration tests
mock tweepy client." Per RESEARCH.md option (b): the FOR UPDATE row-lock
intent is verified syntactically (SQLite in-memory parses but does not
enforce row locks).

Test cases (12 total):
1. test_simulate_happy_breaking_news      — X_POSTING_ENABLED=False, BN
2. test_simulate_happy_thread             — X_POSTING_ENABLED=False, thread
3. test_idempotency_already_posted        — second POST returns already_posted=true
4. test_not_found_404                     — random UUID → 404
5. test_missing_content_bundle_id_400     — engagement_snapshot empty → 400
6. test_content_type_out_of_scope_400     — content_type='quote' → 400
7. test_real_happy_breaking_news          — X_POSTING_ENABLED=True + mocked post_single_tweet
8. test_real_happy_thread                 — mocked post_thread returns 3 IDs
9. test_real_thread_partial_failure       — post_thread returns (2 IDs, PostError)
10. test_real_post_single_tweet_429       — post_single_tweet raises PostError → state=failed
11. test_auth_401                         — no Authorization header → 401
12. test_for_update_compiles              — _build_locked_select compiles to SQL with FOR UPDATE
"""
from __future__ import annotations

import re
import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth import create_access_token
from app.config import get_settings
from app.database import get_db
from app.main import app
from app.services import x_poster

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_draft_item(
    *,
    item_id: UUID | None = None,
    approval_state: str = "pending",
    bundle_id: UUID | None = None,
    posted_tweet_id: str | None = None,
    posted_tweet_ids: list[str] | None = None,
) -> MagicMock:
    """Build a MagicMock that mimics a DraftItem ORM row.

    The route reads .id, .approval_state, .engagement_snapshot, .posted_tweet_id,
    .posted_tweet_ids, .posted_at, .post_error and writes the same set on
    success/failure. MagicMock auto-creates attributes on assignment.
    """
    item = MagicMock()
    item.id = item_id or uuid.uuid4()
    item.approval_state = approval_state
    item.posted_tweet_id = posted_tweet_id
    item.posted_tweet_ids = posted_tweet_ids
    item.posted_at = None
    item.post_error = None
    if bundle_id is not None:
        item.engagement_snapshot = {"content_bundle_id": str(bundle_id)}
    else:
        item.engagement_snapshot = None
    return item


def _make_bundle(content_type: str, draft_content: dict | None) -> MagicMock:
    """Build a MagicMock ContentBundle with content_type + draft_content."""
    bundle = MagicMock()
    bundle.content_type = content_type
    bundle.draft_content = draft_content
    return bundle


def _make_mock_db(*, locked_item: MagicMock | None, bundle: MagicMock | None) -> AsyncMock:
    """Construct an AsyncMock session whose .begin() yields, .execute() returns the
    locked item, and .get(ContentBundle, uuid) returns the configured bundle.

    The route does:
        async with db.begin():
            result = await db.execute(<select FOR UPDATE>)
            item = result.scalar_one_or_none()
            ...
            bundle = await db.get(ContentBundle, UUID(...))

    db.begin() must be an async context manager. AsyncMock alone won't make
    `async with db.begin():` work — we need a real @asynccontextmanager.
    """
    mock_db = AsyncMock()

    @asynccontextmanager
    async def _begin():
        yield None

    mock_db.begin = _begin

    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = locked_item
    mock_db.execute = AsyncMock(return_value=execute_result)
    mock_db.get = AsyncMock(return_value=bundle)
    return mock_db


def _auth_headers() -> dict:
    return {"Authorization": f"Bearer {create_access_token()}"}


@asynccontextmanager
async def _override_db(mock_db: AsyncMock):
    """Context manager that swaps in a mocked AsyncSession via dependency_overrides."""

    async def _override():
        yield mock_db

    app.dependency_overrides[get_db] = _override
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# Simulate-mode tests (X_POSTING_ENABLED defaults to False in conftest)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_simulate_happy_breaking_news(monkeypatch):
    """Simulate mode + breaking_news → state=posted, sim- ID, no tweepy call."""
    bundle_id = uuid.uuid4()
    item = _make_draft_item(bundle_id=bundle_id)
    bundle = _make_bundle("breaking_news", {"tweet": "Gold hits $3000"})
    mock_db = _make_mock_db(locked_item=item, bundle=bundle)

    # Spy on tweepy service to confirm it is NOT called
    fake_post_single = AsyncMock()
    monkeypatch.setattr(x_poster, "post_single_tweet", fake_post_single)

    async with _override_db(mock_db):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(f"/items/{item.id}/post-to-x", headers=_auth_headers())

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["approval_state"] == "posted"
    assert body["posted_tweet_id"].startswith("sim-")
    assert body["posted_tweet_ids"] is None
    assert body["already_posted"] is False
    assert body["post_error"] is None
    assert body["posted_at"] is not None
    fake_post_single.assert_not_awaited()
    # Confirm route mutated the ORM row
    assert item.approval_state == "posted"
    assert item.posted_tweet_id.startswith("sim-")


@pytest.mark.asyncio
async def test_simulate_happy_thread(monkeypatch):
    """Simulate mode + thread → posted_tweet_ids has N sim- entries, posted_tweet_id is first."""
    bundle_id = uuid.uuid4()
    item = _make_draft_item(bundle_id=bundle_id)
    tweets = ["t1 first", "t2 second", "t3 third"]
    bundle = _make_bundle("thread", {"tweets": tweets})
    mock_db = _make_mock_db(locked_item=item, bundle=bundle)

    fake_post_thread = AsyncMock()
    monkeypatch.setattr(x_poster, "post_thread", fake_post_thread)

    async with _override_db(mock_db):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(f"/items/{item.id}/post-to-x", headers=_auth_headers())

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["approval_state"] == "posted"
    assert isinstance(body["posted_tweet_ids"], list)
    assert len(body["posted_tweet_ids"]) == 3
    for tid in body["posted_tweet_ids"]:
        assert tid.startswith("sim-")
    assert body["posted_tweet_id"] == body["posted_tweet_ids"][0]
    fake_post_thread.assert_not_awaited()


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_idempotency_already_posted(monkeypatch):
    """When approval_state is already 'posted', short-circuit returns already_posted=true."""
    bundle_id = uuid.uuid4()
    item = _make_draft_item(
        approval_state="posted",
        bundle_id=bundle_id,
        posted_tweet_id="1234567890",
    )
    # Bundle is irrelevant — short-circuit happens before bundle resolution.
    mock_db = _make_mock_db(locked_item=item, bundle=None)

    fake_post_single = AsyncMock()
    monkeypatch.setattr(x_poster, "post_single_tweet", fake_post_single)

    async with _override_db(mock_db):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(f"/items/{item.id}/post-to-x", headers=_auth_headers())

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["already_posted"] is True
    assert body["approval_state"] == "posted"
    assert body["posted_tweet_id"] == "1234567890"
    fake_post_single.assert_not_awaited()


# ---------------------------------------------------------------------------
# Error responses
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_not_found_404():
    """POST to non-existent item_id → 404."""
    random_id = uuid.uuid4()
    mock_db = _make_mock_db(locked_item=None, bundle=None)

    async with _override_db(mock_db):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(f"/items/{random_id}/post-to-x", headers=_auth_headers())

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_missing_content_bundle_id_400():
    """draft_items.engagement_snapshot empty → 400 'missing content_bundle_id'."""
    item = _make_draft_item(bundle_id=None)  # engagement_snapshot=None
    mock_db = _make_mock_db(locked_item=item, bundle=None)

    async with _override_db(mock_db):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(f"/items/{item.id}/post-to-x", headers=_auth_headers())

    assert resp.status_code == 400
    assert "content_bundle_id" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_content_type_out_of_scope_400():
    """content_type='quote' → 400 with detail naming supported types."""
    bundle_id = uuid.uuid4()
    item = _make_draft_item(bundle_id=bundle_id)
    bundle = _make_bundle("quote", {"text": "irrelevant"})
    mock_db = _make_mock_db(locked_item=item, bundle=bundle)

    async with _override_db(mock_db):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(f"/items/{item.id}/post-to-x", headers=_auth_headers())

    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert "quote" in detail
    assert "breaking_news" in detail
    assert "thread" in detail


# ---------------------------------------------------------------------------
# Real-tweepy paths (X_POSTING_ENABLED=True via monkeypatch)
# ---------------------------------------------------------------------------


def _enable_real_posting(monkeypatch):
    """Helper: flip X_POSTING_ENABLED=True for the duration of a test.

    Patches both the env var (so a fresh Settings sees it) AND clears the
    lru_cache on get_settings so the route picks up the new value.
    """
    monkeypatch.setenv("X_POSTING_ENABLED", "true")
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_real_happy_breaking_news(monkeypatch):
    """Real mode + mocked post_single_tweet → state=posted, posted_tweet_id == mock id."""
    _enable_real_posting(monkeypatch)
    bundle_id = uuid.uuid4()
    item = _make_draft_item(bundle_id=bundle_id)
    bundle = _make_bundle("breaking_news", {"tweet": "Real tweet text"})
    mock_db = _make_mock_db(locked_item=item, bundle=bundle)

    fake_post_single = AsyncMock(return_value="1234567890")
    monkeypatch.setattr(x_poster, "post_single_tweet", fake_post_single)

    async with _override_db(mock_db):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(f"/items/{item.id}/post-to-x", headers=_auth_headers())

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["approval_state"] == "posted"
    assert body["posted_tweet_id"] == "1234567890"
    assert body["posted_tweet_ids"] is None
    assert body["post_error"] is None
    fake_post_single.assert_awaited_once_with("Real tweet text")


@pytest.mark.asyncio
async def test_real_happy_thread(monkeypatch):
    """Real mode + mocked post_thread → state=posted, posted_tweet_ids matches mock."""
    _enable_real_posting(monkeypatch)
    bundle_id = uuid.uuid4()
    item = _make_draft_item(bundle_id=bundle_id)
    tweets = ["one", "two", "three"]
    bundle = _make_bundle("thread", {"tweets": tweets})
    mock_db = _make_mock_db(locked_item=item, bundle=bundle)

    fake_post_thread = AsyncMock(return_value=(["111", "222", "333"], None))
    monkeypatch.setattr(x_poster, "post_thread", fake_post_thread)

    async with _override_db(mock_db):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(f"/items/{item.id}/post-to-x", headers=_auth_headers())

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["approval_state"] == "posted"
    assert body["posted_tweet_id"] == "111"
    assert body["posted_tweet_ids"] == ["111", "222", "333"]
    fake_post_thread.assert_awaited_once_with(tweets)


@pytest.mark.asyncio
async def test_real_thread_partial_failure(monkeypatch):
    """Real mode + post_thread returns (2 IDs, PostError) → state=posted_partial + post_error."""
    _enable_real_posting(monkeypatch)
    bundle_id = uuid.uuid4()
    item = _make_draft_item(bundle_id=bundle_id)
    tweets = ["one", "two", "three"]
    bundle = _make_bundle("thread", {"tweets": tweets})
    mock_db = _make_mock_db(locked_item=item, bundle=bundle)

    err = x_poster.PostError("500", "server_error")
    fake_post_thread = AsyncMock(return_value=(["111", "222"], err))
    monkeypatch.setattr(x_poster, "post_thread", fake_post_thread)

    async with _override_db(mock_db):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(f"/items/{item.id}/post-to-x", headers=_auth_headers())

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["approval_state"] == "posted_partial"
    assert body["posted_tweet_id"] == "111"
    assert body["posted_tweet_ids"] == ["111", "222"]
    assert body["post_error"].startswith("thread posted 2/3:")
    assert "500:server_error" in body["post_error"]


@pytest.mark.asyncio
async def test_real_post_single_tweet_429(monkeypatch):
    """Real mode + post_single_tweet raises PostError(429) → state=failed, post_error='429:...'."""
    _enable_real_posting(monkeypatch)
    bundle_id = uuid.uuid4()
    item = _make_draft_item(bundle_id=bundle_id)
    bundle = _make_bundle("breaking_news", {"tweet": "Real tweet text"})
    mock_db = _make_mock_db(locked_item=item, bundle=bundle)

    fake_post_single = AsyncMock(
        side_effect=x_poster.PostError("429", "too_many_requests"),
    )
    monkeypatch.setattr(x_poster, "post_single_tweet", fake_post_single)

    async with _override_db(mock_db):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(f"/items/{item.id}/post-to-x", headers=_auth_headers())

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["approval_state"] == "failed"
    assert body["posted_tweet_id"] is None
    assert body["post_error"] == "429:too_many_requests"
    assert body["posted_at"] is not None


# ---------------------------------------------------------------------------
# Auth gate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auth_401():
    """POST without Authorization header → 401 or 403."""
    item_id = uuid.uuid4()
    mock_db = _make_mock_db(locked_item=None, bundle=None)

    async with _override_db(mock_db):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(f"/items/{item_id}/post-to-x")

    assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# SELECT FOR UPDATE compile assertion (per RESEARCH.md option b)
# ---------------------------------------------------------------------------


def test_for_update_compiles():
    """The route's _build_locked_select must compile to SQL containing 'FOR UPDATE'.

    SQLite cannot enforce row locks (Pitfall 2). This syntactic test verifies
    that the route is wired with `with_for_update()` so prod Postgres serializes
    concurrent post-to-x requests on the same draft.
    """
    from sqlalchemy.dialects import postgresql

    from app.routers.post_to_x import _build_locked_select

    stmt = _build_locked_select(uuid.uuid4())
    sql = str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    assert re.search(r"FOR UPDATE", sql, re.IGNORECASE), \
        f"Expected 'FOR UPDATE' in compiled SQL, got: {sql}"
