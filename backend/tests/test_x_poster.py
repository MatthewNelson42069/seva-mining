"""Unit tests for backend/app/services/x_poster.py.

Phase B (quick-260424-l0d) Task 2.

All tests MOCK tweepy.asynchronous.AsyncClient — zero real network I/O.
Per CONTEXT.md D14: "All unit + integration tests mock tweepy client."
Catch-order is enforced by the 11 cases here: TooManyRequests/Unauthorized/
Forbidden/BadRequest BEFORE HTTPException BEFORE TweepyException.
"""
import re
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import tweepy

# Imported here so patches against `app.services.x_poster.tweepy.asynchronous.AsyncClient`
# can resolve the module path before the patch context fires.
from app.services import x_poster
from app.services.x_poster import PostError, post_single_tweet, post_thread


def _make_tweepy_http_exc(exc_cls, status_code: int, message: str = "boom"):
    """Build a tweepy HTTPException-subclass instance with .response.status_code + .api_messages."""
    fake_resp = MagicMock()
    fake_resp.status_code = status_code
    exc = exc_cls(fake_resp)
    exc.api_messages = [message]
    return exc


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_post_single_tweet_happy():
    """Mock create_tweet returns response.data={"id":"1234567890"} → returns "1234567890"."""
    mock_client = AsyncMock()
    fake_resp = MagicMock()
    fake_resp.data = {"id": "1234567890"}
    mock_client.create_tweet = AsyncMock(return_value=fake_resp)

    with patch.object(x_poster.tweepy.asynchronous, "AsyncClient", return_value=mock_client):
        result = await post_single_tweet("hello world")

    assert result == "1234567890"
    mock_client.create_tweet.assert_awaited_once()
    call_kwargs = mock_client.create_tweet.call_args.kwargs
    assert call_kwargs["text"] == "hello world"
    assert call_kwargs["user_auth"] is True


@pytest.mark.asyncio
async def test_post_thread_happy_3():
    """3 sequential create_tweet calls, in_reply_to_tweet_id chained correctly."""
    mock_client = AsyncMock()
    responses = []
    for tid in ("id1", "id2", "id3"):
        r = MagicMock()
        r.data = {"id": tid}
        responses.append(r)
    mock_client.create_tweet = AsyncMock(side_effect=responses)

    with patch.object(x_poster.tweepy.asynchronous, "AsyncClient", return_value=mock_client):
        ids, err = await post_thread(["t1", "t2", "t3"])

    assert err is None
    assert ids == ["id1", "id2", "id3"]
    assert mock_client.create_tweet.await_count == 3
    calls = mock_client.create_tweet.call_args_list
    # 1st call: no in_reply_to_tweet_id
    assert "in_reply_to_tweet_id" not in calls[0].kwargs
    assert calls[0].kwargs["text"] == "t1"
    # 2nd call: replies to id1
    assert calls[1].kwargs["in_reply_to_tweet_id"] == "id1"
    assert calls[1].kwargs["text"] == "t2"
    # 3rd call: replies to id2
    assert calls[2].kwargs["in_reply_to_tweet_id"] == "id2"
    assert calls[2].kwargs["text"] == "t3"


# ---------------------------------------------------------------------------
# Partial-thread + first-tweet-fail
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_post_thread_partial_failure_at_index_2():
    """3rd call raises 429 — first 2 succeeded; result is (["id1","id2"], PostError("429", ...))."""
    mock_client = AsyncMock()
    r1 = MagicMock()
    r1.data = {"id": "id1"}
    r2 = MagicMock()
    r2.data = {"id": "id2"}
    err = _make_tweepy_http_exc(tweepy.TooManyRequests, 429, "rate")
    mock_client.create_tweet = AsyncMock(side_effect=[r1, r2, err])

    with patch.object(x_poster.tweepy.asynchronous, "AsyncClient", return_value=mock_client):
        ids, post_err = await post_thread(["t1", "t2", "t3"])

    assert ids == ["id1", "id2"]
    assert isinstance(post_err, PostError)
    assert post_err.code == "429"


@pytest.mark.asyncio
async def test_post_thread_first_tweet_fails_returns_empty_ids():
    """First call raises — result is ([], PostError)."""
    mock_client = AsyncMock()
    err = _make_tweepy_http_exc(tweepy.Unauthorized, 401, "no auth")
    mock_client.create_tweet = AsyncMock(side_effect=err)

    with patch.object(x_poster.tweepy.asynchronous, "AsyncClient", return_value=mock_client):
        ids, post_err = await post_thread(["t1", "t2"])

    assert ids == []
    assert isinstance(post_err, PostError)
    assert post_err.code == "401"


# ---------------------------------------------------------------------------
# Exception-mapping (single-tweet path)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_post_single_tweet_429():
    """tweepy.TooManyRequests → PostError("429", ...)."""
    mock_client = AsyncMock()
    err = _make_tweepy_http_exc(tweepy.TooManyRequests, 429, "Too many")
    mock_client.create_tweet = AsyncMock(side_effect=err)

    with patch.object(x_poster.tweepy.asynchronous, "AsyncClient", return_value=mock_client):
        with pytest.raises(PostError) as exc_info:
            await post_single_tweet("hi")

    assert exc_info.value.code == "429"
    assert "Too many" in exc_info.value.message


@pytest.mark.asyncio
async def test_post_single_tweet_401():
    mock_client = AsyncMock()
    err = _make_tweepy_http_exc(tweepy.Unauthorized, 401, "bad token")
    mock_client.create_tweet = AsyncMock(side_effect=err)

    with patch.object(x_poster.tweepy.asynchronous, "AsyncClient", return_value=mock_client):
        with pytest.raises(PostError) as exc_info:
            await post_single_tweet("hi")

    assert exc_info.value.code == "401"


@pytest.mark.asyncio
async def test_post_single_tweet_403():
    mock_client = AsyncMock()
    err = _make_tweepy_http_exc(tweepy.Forbidden, 403, "duplicate")
    mock_client.create_tweet = AsyncMock(side_effect=err)

    with patch.object(x_poster.tweepy.asynchronous, "AsyncClient", return_value=mock_client):
        with pytest.raises(PostError) as exc_info:
            await post_single_tweet("hi")

    assert exc_info.value.code == "403"
    assert exc_info.value.message == "duplicate"


@pytest.mark.asyncio
async def test_post_single_tweet_400():
    mock_client = AsyncMock()
    err = _make_tweepy_http_exc(tweepy.BadRequest, 400, "tweet too long")
    mock_client.create_tweet = AsyncMock(side_effect=err)

    with patch.object(x_poster.tweepy.asynchronous, "AsyncClient", return_value=mock_client):
        with pytest.raises(PostError) as exc_info:
            await post_single_tweet("hi")

    assert exc_info.value.code == "400"


@pytest.mark.asyncio
async def test_post_single_tweet_5xx():
    """A generic HTTPException with response.status_code=503 → PostError("503", ...)."""
    mock_client = AsyncMock()
    fake_resp = MagicMock()
    fake_resp.status_code = 503
    # tweepy.TwitterServerError inherits from HTTPException
    err = tweepy.TwitterServerError(fake_resp)
    err.api_messages = ["Service Unavailable"]
    mock_client.create_tweet = AsyncMock(side_effect=err)

    with patch.object(x_poster.tweepy.asynchronous, "AsyncClient", return_value=mock_client):
        with pytest.raises(PostError) as exc_info:
            await post_single_tweet("hi")

    # 5xx mapping: code starts with "5"
    assert exc_info.value.code.startswith("5")


@pytest.mark.asyncio
async def test_post_single_tweet_network_error():
    """Raw tweepy.TweepyException (non-HTTP) → PostError("500", ...)."""
    mock_client = AsyncMock()
    mock_client.create_tweet = AsyncMock(side_effect=tweepy.TweepyException("boom"))

    with patch.object(x_poster.tweepy.asynchronous, "AsyncClient", return_value=mock_client):
        with pytest.raises(PostError) as exc_info:
            await post_single_tweet("hi")

    assert exc_info.value.code == "500"


# ---------------------------------------------------------------------------
# FOR UPDATE SQL-compile assertion (per RESEARCH.md option b: SQLite cannot enforce
# row locks but the SQL must explicitly contain "FOR UPDATE" for prod Postgres).
# ---------------------------------------------------------------------------

def test_for_update_sql_compiles_with_for_update_clause():
    """select(DraftItem).where(...).with_for_update() must compile to SQL containing FOR UPDATE."""
    from sqlalchemy import select
    from sqlalchemy.dialects import postgresql

    from app.models.draft_item import DraftItem

    stmt = select(DraftItem).where(DraftItem.id == uuid.uuid4()).with_for_update()
    sql = str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    assert re.search(r"FOR UPDATE", sql, re.IGNORECASE), \
        f"Expected 'FOR UPDATE' in compiled SQL, got: {sql}"
