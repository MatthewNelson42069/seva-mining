"""
Instagram Agent — fetch, filter, score, draft, and compliance pipeline.

Monitors Instagram every 4 hours for qualifying gold-sector posts via
the Apify instagram-scraper actor (hashtag feeds + watchlist account profiles).
Applies engagement gate, composite scoring, selects top 3 posts, drafts
comment alternatives via Claude, runs compliance check, and persists passing
drafts as DraftItem records.

Requirements: INST-01 through INST-12
"""
from __future__ import annotations

import asyncio
import json
import logging
import math
from datetime import datetime, timezone, timedelta
from typing import Optional

from anthropic import AsyncAnthropic
from apify_client import ApifyClientAsync
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from database import AsyncSessionLocal
from models.agent_run import AgentRun
from models.config import Config
from models.draft_item import DraftItem
from models.keyword import Keyword
from models.watchlist import Watchlist

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pure scoring functions — module-level for direct testability (INST-02)
# ---------------------------------------------------------------------------

def normalize_followers(n: int) -> float:
    """INST-02: Log-scale normalization capped at 1M followers.

    1k followers  -> log10(1000)/log10(1_000_000) = 3/6 = 0.5
    100k followers -> log10(100000)/log10(1_000_000) = 5/6 ~= 0.8333
    1M+ followers  -> 1.0 (capped)
    0 followers    -> 0.0
    """
    if n <= 0:
        return 0.0
    return min(math.log10(max(n, 1)) / math.log10(1_000_000), 1.0)


def calculate_instagram_score(likes: int, comment_count: int, follower_count: int) -> float:
    """INST-02: likes*1 + comments*2 + normalize_followers(n)*1.5"""
    return float(likes * 1 + comment_count * 2 + normalize_followers(follower_count) * 1.5)


def passes_engagement_gate(likes: int, created_at: datetime) -> bool:
    """INST-03: 200+ likes AND post created within last 8 hours (strictly < 8.0h).

    Args:
        likes: Number of likes on the post.
        created_at: Timezone-aware datetime when the post was published.

    Returns:
        True if both thresholds are satisfied, False otherwise.
    """
    if likes < 200:
        return False
    now = datetime.now(timezone.utc)
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    age_hours = (now - created_at).total_seconds() / 3600.0
    return age_hours < 8.0


def select_top_posts(scored_posts: list[dict], top_n: int = 3) -> list[dict]:
    """INST-04: Select top N posts by score, descending.

    Args:
        scored_posts: List of post dicts, each expected to have a ``score`` key.
        top_n: Maximum number of posts to return.

    Returns:
        Up to top_n posts sorted by score descending.
    """
    def _score(p: dict) -> float:
        return float(p.get("score", 0))

    qualifying = [p for p in scored_posts if _score(p) > 0]
    qualifying.sort(key=_score, reverse=True)
    return qualifying[:top_n]


# ---------------------------------------------------------------------------
# InstagramAgent class skeleton (INST-01 through INST-12)
# ---------------------------------------------------------------------------

class InstagramAgent:
    """Instagram Agent — Apify scrape, filter, score, draft pipeline.

    Requirements: INST-01 through INST-12
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.apify_client = ApifyClientAsync(token=settings.apify_api_token)
        self.anthropic = AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def run(self) -> None:
        """Entry point called by APScheduler every 4 hours."""
        async with AsyncSessionLocal() as session:
            agent_run = AgentRun(
                agent_name="instagram_agent",
                status="running",
                started_at=datetime.now(timezone.utc),
                items_found=0,
                items_queued=0,
                items_filtered=0,
            )
            session.add(agent_run)
            await session.commit()
            try:
                await self._run_pipeline(session, agent_run)
                agent_run.status = "completed"
            except Exception as exc:
                agent_run.status = "failed"
                agent_run.errors = str(exc)
                logger.error("InstagramAgent run failed: %s", exc, exc_info=True)
            finally:
                agent_run.ended_at = datetime.now(timezone.utc)
                await session.commit()

    async def _run_pipeline(self, session: AsyncSession, agent_run: AgentRun) -> None:
        """Full pipeline: fetch, filter, score, draft, persist. Implemented across Plans 02-04."""
        # Step 1: Load config
        max_per_hashtag = int(await self._get_config(session, "instagram_max_posts_per_hashtag", "50"))
        max_per_account = int(await self._get_config(session, "instagram_max_posts_per_account", "10"))
        top_n = int(await self._get_config(session, "instagram_top_n", "3"))

        # Step 2: Load hashtags and watchlist
        hashtags = await self._load_keywords(session)
        watchlist = await self._load_watchlist(session)

        # Step 3: Parallel fetch via Apify
        hashtag_posts, account_posts = await asyncio.gather(
            self._fetch_hashtag_posts(hashtags, max_per_hashtag),
            self._fetch_account_posts(watchlist, max_per_account),
        )

        # Step 4: Merge and deduplicate by shortCode
        all_posts = self._deduplicate_posts(hashtag_posts + account_posts)
        agent_run.items_found = len(all_posts)

        # Step 5: Filter by engagement gate (200+ likes, within 8h)
        qualifying = []
        for p in all_posts:
            ts = p.get("timestamp")
            if not ts:
                continue
            try:
                if isinstance(ts, str):
                    created = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                else:
                    created = ts
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                if passes_engagement_gate(likes=p.get("likesCount", 0), created_at=created):
                    qualifying.append(p)
            except (ValueError, TypeError):
                continue
        agent_run.items_filtered = len(all_posts) - len(qualifying)

        # Step 6: Score and select top N
        for p in qualifying:
            follower_count = p.get("ownerFollowersCount") or p.get("followersCount") or 0
            p["score"] = calculate_instagram_score(
                likes=p.get("likesCount", 0),
                comment_count=p.get("commentsCount", 0),
                follower_count=follower_count,
            )
        top_posts = select_top_posts(qualifying, top_n=top_n)

        # Steps 7-9 implemented in Plan 03 (draft, compliance, persist)
        # Step 10 implemented in Plan 04 (health monitoring)

    async def _get_config(self, session: AsyncSession, key: str, default: str) -> str:
        """Read a config value from the Config table, with default fallback."""
        result = await session.execute(
            select(Config.value).where(Config.key == key)
        )
        row = result.scalar_one_or_none()
        return row if row is not None else default

    async def _load_keywords(self, session: AsyncSession) -> list[str]:
        """Load active Instagram hashtags from keywords table."""
        result = await session.execute(
            select(Keyword.term).where(
                Keyword.platform == "instagram",
                Keyword.active == True,
            )
        )
        return [row for row in result.scalars().all()]

    async def _load_watchlist(self, session: AsyncSession) -> list[dict]:
        """Load active Instagram watchlist accounts."""
        result = await session.execute(
            select(Watchlist).where(
                Watchlist.platform == "instagram",
                Watchlist.active == True,
            )
        )
        return [
            {"handle": w.account_handle, "notes": w.notes}
            for w in result.scalars().all()
        ]

    async def _fetch_hashtag_posts(self, hashtags: list[str], max_per_hashtag: int) -> list[dict]:
        """Fetch posts for each hashtag via Apify instagram-scraper."""
        lookback_date = datetime.now(timezone.utc) - timedelta(hours=24)
        all_items: list[dict] = []
        for tag in hashtags:
            clean_tag = tag.lstrip("#")
            run_input = {
                "directUrls": [f"https://www.instagram.com/explore/tags/{clean_tag}/"],
                "resultsType": "posts",
                "resultsLimit": max_per_hashtag,
                "onlyPostsNewerThan": lookback_date.strftime("%Y-%m-%d"),
            }
            items = await self._call_apify_actor(run_input)
            for item in items:
                item["_source_tag"] = clean_tag
            all_items.extend(items)
        return all_items

    async def _fetch_account_posts(self, watchlist: list[dict], max_per_account: int) -> list[dict]:
        """Fetch posts for each watchlist account via Apify instagram-scraper."""
        lookback_date = datetime.now(timezone.utc) - timedelta(hours=24)
        all_items: list[dict] = []
        for account in watchlist:
            handle = account["handle"]
            run_input = {
                "directUrls": [f"https://www.instagram.com/{handle}/"],
                "resultsType": "posts",
                "resultsLimit": max_per_account,
                "onlyPostsNewerThan": lookback_date.strftime("%Y-%m-%d"),
            }
            items = await self._call_apify_actor(run_input)
            all_items.extend(items)
        return all_items

    async def _call_apify_actor(self, run_input: dict) -> list[dict]:
        """Call apify/instagram-scraper and return dataset items. Plan 04 adds retry."""
        actor_client = self.apify_client.actor("apify/instagram-scraper")
        run_result = await actor_client.call(run_input=run_input)
        if run_result is None:
            return []
        dataset_id = run_result.get("defaultDatasetId")
        if not dataset_id:
            return []
        dataset_client = self.apify_client.dataset(dataset_id)
        items_result = await dataset_client.list_items()
        return items_result.items if items_result else []

    def _deduplicate_posts(self, posts: list[dict]) -> list[dict]:
        """Deduplicate by shortCode (Apify unique post identifier)."""
        seen: set[str] = set()
        unique: list[dict] = []
        for p in posts:
            code = p.get("shortCode", "")
            if code and code not in seen:
                seen.add(code)
                unique.append(p)
        return unique
