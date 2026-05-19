"""X API recent-search consumer for the Weekly Viral Sweeper (Phase 7, Plan 02).

Mirrors scheduler/agents/content/gold_media.py::_search_gold_media_clips —
same auth pattern, same quota gate, same tweepy AsyncClient construction.
Difference: parameterizes on the query (vs hardcoded GOLD_MEDIA_ACCOUNTS),
fetches max_results=100 (vs 10), sorts by relevancy at the API level then
re-ranks by engagement in Python to surface the top 10 viral posts.

Public surface:
    fetch_top_x_posts(query, max_results=100) -> list[dict]

Each returned dict has keys:
    tweet_id, text, author_username, tweet_url, likes, retweets, replies, created_at

Quota coordination (P-NEW defense):
    Reads twitter_monthly_tweet_count + twitter_monthly_quota_limit from
    the Config table (bot_config row set). Aborts (returns []) if within
    500 of cap. Increments counter by actual fetched-tweet count at the
    end. Same coordination protocol as gold_media.py — single-process
    scheduler, naive read-then-write is sufficient (no SELECT FOR UPDATE
    needed).

Engagement re-rank formula (locked from 07-CONTEXT.md D-06):
    score = likes + retweets*2 + replies*1.5
"""
from __future__ import annotations

import logging

import tweepy.asynchronous
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from database import AsyncSessionLocal
from models.config import Config

logger = logging.getLogger(__name__)

AGENT_NAME = "weekly_sweeper"
TOP_N = 10
QUOTA_SAFETY_MARGIN = 500  # abort if (limit - count) < this value


async def _get_config(session: AsyncSession, key: str, default: str) -> str:
    """Read a config value from the Config table by key. Returns default if not found."""
    result = await session.execute(select(Config).where(Config.key == key))
    row = result.scalar_one_or_none()
    return row.value if row else default


async def _set_config_str(session: AsyncSession, key: str, value: str) -> None:
    """Upsert a config key with a string value."""
    result = await session.execute(select(Config).where(Config.key == key))
    row = result.scalar_one_or_none()
    if row is None:
        session.add(Config(key=key, value=value))
    else:
        row.value = value


def _engagement_score(metrics: dict) -> float:
    """Engagement re-rank formula — locked per 07-CONTEXT.md D-06.

    score = likes + retweets*2 + replies*1.5

    Defensive: treats missing keys as 0.
    """
    likes = metrics.get("like_count", 0) or 0
    retweets = metrics.get("retweet_count", 0) or 0
    replies = metrics.get("reply_count", 0) or 0
    return float(likes) + float(retweets) * 2.0 + float(replies) * 1.5


async def fetch_top_x_posts(query: str, max_results: int = 100) -> list[dict]:
    """Fetch top-10 engagement-ranked tweets for the given X recent-search query.

    Args:
        query: X recent-search query string (combined keyword + cashtag + hashtag).
        max_results: tweepy max_results param (X API ceiling is 100 for recent search).

    Returns:
        List of up to 10 dicts (engagement-ranked desc), each with keys:
        tweet_id, text, author_username, tweet_url, likes, retweets, replies, created_at.
        Returns [] on quota near cap, X API failure, or no results.

    Side effects:
        - Reads Config keys: twitter_monthly_tweet_count, twitter_monthly_quota_limit
        - Increments twitter_monthly_tweet_count by the actual fetched-tweet count
          (NOT by max_results — X may return fewer than requested)
    """
    settings = get_settings()

    async with AsyncSessionLocal() as session:
        current_count_str = await _get_config(session, "twitter_monthly_tweet_count", "0")
        quota_limit_str = await _get_config(session, "twitter_monthly_quota_limit", "10000")
        current_count = int(current_count_str)
        quota_limit = int(quota_limit_str)

        if quota_limit - current_count < QUOTA_SAFETY_MARGIN:
            logger.info(
                "%s: X API quota near cap (%d/%d, margin=%d) — skipping X ingest",
                AGENT_NAME, current_count, quota_limit, QUOTA_SAFETY_MARGIN,
            )
            return []

        tweepy_client = tweepy.asynchronous.AsyncClient(
            bearer_token=settings.x_api_bearer_token,
            wait_on_rate_limit=True,
        )

        try:
            response = await tweepy_client.search_recent_tweets(
                query=query,
                max_results=max_results,
                sort_order="relevancy",
                tweet_fields=["created_at", "public_metrics", "author_id", "text"],
                expansions=["author_id"],
                user_fields=["username"],
            )
        except Exception as exc:
            logger.warning(
                "%s: X API search_recent_tweets failed: %s", AGENT_NAME, exc,
            )
            return []

        if not response.data:
            logger.info("%s: X API returned no tweets for query", AGENT_NAME)
            return []

        users_data = (response.includes or {}).get("users") or []
        user_map = {str(u.id): u for u in users_data}

        results: list[dict] = []
        for tweet in response.data:
            user = user_map.get(str(tweet.author_id))
            username = user.username if user else "unknown"
            tweet_url = f"https://twitter.com/{username}/status/{tweet.id}"
            metrics = tweet.public_metrics or {}

            results.append({
                "tweet_id": str(tweet.id),
                "text": tweet.text,
                "author_username": username,
                "tweet_url": tweet_url,
                "likes": int(metrics.get("like_count", 0) or 0),
                "retweets": int(metrics.get("retweet_count", 0) or 0),
                "replies": int(metrics.get("reply_count", 0) or 0),
                "created_at": tweet.created_at,
            })

        total_returned = len(response.data)
        new_count = current_count + total_returned
        await _set_config_str(session, "twitter_monthly_tweet_count", str(new_count))
        await session.commit()

        results.sort(
            key=lambda r: _engagement_score({
                "like_count": r["likes"],
                "retweet_count": r["retweets"],
                "reply_count": r["replies"],
            }),
            reverse=True,
        )
        top = results[:TOP_N]

        logger.info(
            "%s: X API returned %d tweets, ranked, returning top %d",
            AGENT_NAME, total_returned, len(top),
        )
        return top
