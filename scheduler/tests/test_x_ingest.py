"""pytest coverage for scheduler/agents/x_ingest.py (Phase 7, Plan 02).

Tests fetch_top_x_posts control-flow branches:
- happy path (top 10 engagement-ranked)
- quota near cap (returns [])
- quota at safety margin boundary (proceeds)
- X API exception (returns [])
- empty response (returns [])
- fewer than top N (returns all, still ranked)
- engagement rank order
- dict shape contract
- query + sort_order forwarded to tweepy
"""
import os
import sys
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _mk_tweet(tid, text, author_id, likes=0, retweets=0, replies=0):
    return SimpleNamespace(
        id=tid,
        text=text,
        author_id=author_id,
        created_at=datetime(2026, 5, 15, tzinfo=timezone.utc),
        public_metrics={
            "like_count": likes,
            "retweet_count": retweets,
            "reply_count": replies,
        },
    )


def _mk_user(uid, username):
    return SimpleNamespace(id=uid, username=username)


def _mk_response(tweets, users):
    return SimpleNamespace(
        data=tweets,
        includes={"users": users} if users else None,
        errors=None,
    )


@pytest.mark.asyncio
async def test_happy_path():
    """50 tweets with varying engagement → result is top 10 sorted desc; counter +50."""
    from agents import x_ingest

    async def fake_get_config(session, key, default):
        return {
            "twitter_monthly_tweet_count": "5000",
            "twitter_monthly_quota_limit": "10000",
        }.get(key, default)

    tweets = [_mk_tweet(f"t{i}", f"text{i}", f"u{i}", likes=i * 10) for i in range(50)]
    users = [_mk_user(f"u{i}", f"user{i}") for i in range(50)]
    fake_response = _mk_response(tweets, users)

    mock_client = MagicMock()
    mock_client.search_recent_tweets = AsyncMock(return_value=fake_response)

    mock_set = AsyncMock()
    with patch.object(x_ingest, "_get_config", side_effect=fake_get_config), \
         patch.object(x_ingest, "_set_config_str", new=mock_set), \
         patch("tweepy.asynchronous.AsyncClient", return_value=mock_client):
        result = await x_ingest.fetch_top_x_posts(query="gold OR $GOLD")

    assert len(result) == 10, f"expected top 10, got {len(result)}"
    # Verify descending engagement order
    scores = [r["likes"] + r["retweets"] * 2 + r["replies"] * 1.5 for r in result]
    assert scores == sorted(scores, reverse=True), "results not engagement-ranked desc"
    # Verify counter persisted to 5000 + 50
    mock_set.assert_awaited()
    call_args = mock_set.await_args
    # call_args = call(session, key, value); positional args [1]=key, [2]=value
    args = call_args.args
    assert args[1] == "twitter_monthly_tweet_count"
    assert args[2] == "5050", f"expected counter=5050, got {args[2]}"


@pytest.mark.asyncio
async def test_quota_near_cap():
    """counter=9600/10000 (delta=400 < 500) → [] and tweepy NOT called; counter unchanged."""
    from agents import x_ingest

    async def fake_get_config(session, key, default):
        return {
            "twitter_monthly_tweet_count": "9600",
            "twitter_monthly_quota_limit": "10000",
        }.get(key, default)

    mock_client = MagicMock()
    mock_client.search_recent_tweets = AsyncMock()

    mock_set = AsyncMock()
    with patch.object(x_ingest, "_get_config", side_effect=fake_get_config), \
         patch.object(x_ingest, "_set_config_str", new=mock_set), \
         patch("tweepy.asynchronous.AsyncClient", return_value=mock_client):
        result = await x_ingest.fetch_top_x_posts(query="gold")

    assert result == [], "quota near cap should return []"
    mock_client.search_recent_tweets.assert_not_called()
    mock_set.assert_not_called()


@pytest.mark.asyncio
async def test_quota_at_safety_margin():
    """counter=9500/10000 (delta=500, NOT < 500) → proceeds; tweepy IS called."""
    from agents import x_ingest

    async def fake_get_config(session, key, default):
        return {
            "twitter_monthly_tweet_count": "9500",
            "twitter_monthly_quota_limit": "10000",
        }.get(key, default)

    tweets = [_mk_tweet("t1", "x", "u1", likes=5)]
    users = [_mk_user("u1", "user1")]
    mock_client = MagicMock()
    mock_client.search_recent_tweets = AsyncMock(return_value=_mk_response(tweets, users))

    with patch.object(x_ingest, "_get_config", side_effect=fake_get_config), \
         patch.object(x_ingest, "_set_config_str", new=AsyncMock()), \
         patch("tweepy.asynchronous.AsyncClient", return_value=mock_client):
        result = await x_ingest.fetch_top_x_posts(query="gold")

    assert len(result) == 1, "boundary delta=500 should proceed"
    mock_client.search_recent_tweets.assert_called_once()


@pytest.mark.asyncio
async def test_x_api_exception():
    """tweepy raises → returns []; counter NOT incremented; warning logged."""
    from agents import x_ingest

    async def fake_get_config(session, key, default):
        return {
            "twitter_monthly_tweet_count": "0",
            "twitter_monthly_quota_limit": "10000",
        }.get(key, default)

    mock_client = MagicMock()
    mock_client.search_recent_tweets = AsyncMock(side_effect=ConnectionError("boom"))

    mock_set = AsyncMock()
    with patch.object(x_ingest, "_get_config", side_effect=fake_get_config), \
         patch.object(x_ingest, "_set_config_str", new=mock_set), \
         patch("tweepy.asynchronous.AsyncClient", return_value=mock_client):
        result = await x_ingest.fetch_top_x_posts(query="gold")

    assert result == [], "X API exception should return []"
    mock_set.assert_not_called()


@pytest.mark.asyncio
async def test_empty_response():
    """response.data=None → returns []; counter unchanged."""
    from agents import x_ingest

    async def fake_get_config(session, key, default):
        return {
            "twitter_monthly_tweet_count": "0",
            "twitter_monthly_quota_limit": "10000",
        }.get(key, default)

    mock_client = MagicMock()
    mock_client.search_recent_tweets = AsyncMock(return_value=_mk_response(None, None))

    mock_set = AsyncMock()
    with patch.object(x_ingest, "_get_config", side_effect=fake_get_config), \
         patch.object(x_ingest, "_set_config_str", new=mock_set), \
         patch("tweepy.asynchronous.AsyncClient", return_value=mock_client):
        result = await x_ingest.fetch_top_x_posts(query="gold")

    assert result == []
    mock_set.assert_not_called()


@pytest.mark.asyncio
async def test_fewer_than_top_n():
    """5 tweets → returns all 5; counter incremented by 5."""
    from agents import x_ingest

    async def fake_get_config(session, key, default):
        return {
            "twitter_monthly_tweet_count": "100",
            "twitter_monthly_quota_limit": "10000",
        }.get(key, default)

    tweets = [_mk_tweet(f"t{i}", f"x{i}", f"u{i}", likes=i) for i in range(5)]
    users = [_mk_user(f"u{i}", f"user{i}") for i in range(5)]
    mock_client = MagicMock()
    mock_client.search_recent_tweets = AsyncMock(return_value=_mk_response(tweets, users))

    mock_set = AsyncMock()
    with patch.object(x_ingest, "_get_config", side_effect=fake_get_config), \
         patch.object(x_ingest, "_set_config_str", new=mock_set), \
         patch("tweepy.asynchronous.AsyncClient", return_value=mock_client):
        result = await x_ingest.fetch_top_x_posts(query="gold")

    assert len(result) == 5
    # Sorted desc by engagement: t4 (likes=4) first, t0 last
    assert result[0]["likes"] == 4
    assert result[-1]["likes"] == 0
    # Counter incremented by 5
    mock_set.assert_awaited()
    args = mock_set.await_args.args
    assert args[2] == "105"


@pytest.mark.asyncio
async def test_engagement_rank_order():
    """3 tweets with metrics {l=10,r=0,re=0}, {l=0,r=5,re=0}, {l=0,r=0,re=10}.

    Scores: t1=10, t2=10, t3=15. Sorted: [t3=15, t1=10/t2=10].
    """
    from agents import x_ingest

    async def fake_get_config(session, key, default):
        return {
            "twitter_monthly_tweet_count": "0",
            "twitter_monthly_quota_limit": "10000",
        }.get(key, default)

    tweets = [
        _mk_tweet("t1", "likes-only", "u1", likes=10, retweets=0, replies=0),
        _mk_tweet("t2", "retweets-only", "u2", likes=0, retweets=5, replies=0),
        _mk_tweet("t3", "replies-only", "u3", likes=0, retweets=0, replies=10),
    ]
    users = [_mk_user("u1", "user1"), _mk_user("u2", "user2"), _mk_user("u3", "user3")]
    mock_client = MagicMock()
    mock_client.search_recent_tweets = AsyncMock(return_value=_mk_response(tweets, users))

    with patch.object(x_ingest, "_get_config", side_effect=fake_get_config), \
         patch.object(x_ingest, "_set_config_str", new=AsyncMock()), \
         patch("tweepy.asynchronous.AsyncClient", return_value=mock_client):
        result = await x_ingest.fetch_top_x_posts(query="gold")

    assert len(result) == 3
    # Highest score (t3: 0 + 0*2 + 10*1.5 = 15.0) first
    assert result[0]["tweet_id"] == "t3", f"expected t3 first, got {result[0]['tweet_id']}"
    # The two tied 10s (t1: 10+0+0=10, t2: 0+10+0=10) follow
    remaining_ids = {result[1]["tweet_id"], result[2]["tweet_id"]}
    assert remaining_ids == {"t1", "t2"}


@pytest.mark.asyncio
async def test_dict_shape():
    """Each returned dict has exact key set; tweet_url is well-formed."""
    from agents import x_ingest

    async def fake_get_config(session, key, default):
        return {
            "twitter_monthly_tweet_count": "0",
            "twitter_monthly_quota_limit": "10000",
        }.get(key, default)

    tweets = [_mk_tweet("t1", "hello", "u1", likes=1, retweets=2, replies=3)]
    users = [_mk_user("u1", "alice")]
    mock_client = MagicMock()
    mock_client.search_recent_tweets = AsyncMock(return_value=_mk_response(tweets, users))

    with patch.object(x_ingest, "_get_config", side_effect=fake_get_config), \
         patch.object(x_ingest, "_set_config_str", new=AsyncMock()), \
         patch("tweepy.asynchronous.AsyncClient", return_value=mock_client):
        result = await x_ingest.fetch_top_x_posts(query="gold")

    assert len(result) == 1
    expected_keys = {
        "tweet_id", "text", "author_username", "tweet_url",
        "likes", "retweets", "replies", "created_at",
    }
    actual_keys = set(result[0].keys())
    assert actual_keys == expected_keys, f"unexpected keys: {actual_keys ^ expected_keys}"
    assert result[0]["tweet_url"] == "https://twitter.com/alice/status/t1"
    assert result[0]["likes"] == 1
    assert result[0]["retweets"] == 2
    assert result[0]["replies"] == 3
    assert result[0]["author_username"] == "alice"


@pytest.mark.asyncio
async def test_query_and_sort_order_forwarded():
    """Verifies tweepy is called with query=<input>, sort_order='relevancy', max_results=100."""
    from agents import x_ingest

    async def fake_get_config(session, key, default):
        return {
            "twitter_monthly_tweet_count": "0",
            "twitter_monthly_quota_limit": "10000",
        }.get(key, default)

    mock_client = MagicMock()
    mock_client.search_recent_tweets = AsyncMock(return_value=_mk_response(None, None))

    with patch.object(x_ingest, "_get_config", side_effect=fake_get_config), \
         patch.object(x_ingest, "_set_config_str", new=AsyncMock()), \
         patch("tweepy.asynchronous.AsyncClient", return_value=mock_client):
        await x_ingest.fetch_top_x_posts(query="MY_TEST_QUERY", max_results=100)

    call_kwargs = mock_client.search_recent_tweets.await_args.kwargs
    assert call_kwargs["query"] == "MY_TEST_QUERY"
    assert call_kwargs["sort_order"] == "relevancy"
    assert call_kwargs["max_results"] == 100
