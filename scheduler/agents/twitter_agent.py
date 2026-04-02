"""
Twitter Agent — fetch, filter, score pipeline.

Monitors X (Twitter) every 2 hours for qualifying gold-sector posts.
Applies engagement gate, composite scoring with recency decay, and
selects top 3-5 posts to pass to drafting (Plan 03).

Requirements: TWIT-01 through TWIT-14
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

import tweepy.asynchronous
from anthropic import AsyncAnthropic
from sqlalchemy import select, text
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
# Gold-sector keyword list for topic filtering (TWIT-01)
# Used in _apply_topic_filter() as a fast case-insensitive keyword check
# before falling back to Claude classification for watchlist tweets.
# ---------------------------------------------------------------------------
GOLD_KEYWORDS: list[str] = [
    "gold",
    "$GLD",
    "$GC",
    "bullion",
    "precious metals",
    "#goldmining",
    "#gold",
    "central bank",
    "gold reserve",
    "gold price",
    "Au",
    "troy ounce",
    "junior miners",
    "mining stock",
    "$GOLD",
    "$GDX",
    "$GDXJ",
    "$NEM",
    "#preciousmetals",
    "#goldprice",
    "#bullion",
    "#juniorminers",
    "#mining",
    "gold exploration",
    "gold ETF",
    "gold standard",
    "gold rally",
    "gold outlook",
]

# X API tweet fields to request in every search/fetch call
TWEET_FIELDS = ["created_at", "public_metrics", "author_id", "text"]
USER_FIELDS = ["username", "public_metrics"]


# ---------------------------------------------------------------------------
# Pure scoring functions — module-level for direct testability (TWIT-02-06)
# ---------------------------------------------------------------------------

def calculate_engagement_score(likes: int, retweets: int, replies: int) -> float:
    """TWIT-03: likes*1 + retweets*2 + replies*1.5"""
    return float(likes * 1 + retweets * 2 + replies * 1.5)


def calculate_composite_score(
    engagement_norm: float, authority_norm: float, relevance_norm: float
) -> float:
    """TWIT-02: engagement 40% + authority 30% + relevance 30%"""
    return engagement_norm * 0.4 + authority_norm * 0.3 + relevance_norm * 0.3


def apply_recency_decay(score: float, age_hours: float) -> float:
    """TWIT-05: full score <1h, linear 100%->50% from 1h->4h, linear 50%->0% from 4h->6h, 0 at >=6h.

    Args:
        score: The raw composite score to decay.
        age_hours: Age of the tweet in hours since creation.

    Returns:
        Decayed score. Returns 0.0 for tweets 6h or older.
    """
    if age_hours <= 1.0:
        return score
    elif age_hours < 4.0:
        # Linear from 100% at 1h to 50% at 4h
        fraction = 1.0 - 0.5 * (age_hours - 1.0) / 3.0
        return score * fraction
    elif age_hours < 6.0:
        # Linear from 50% at 4h to 0% at 6h
        fraction = 0.5 * (1.0 - (age_hours - 4.0) / 2.0)
        return score * fraction
    else:
        return 0.0


def passes_engagement_gate(
    likes: int,
    views: Optional[int],
    is_watchlist: bool,
) -> bool:
    """TWIT-04: Engagement gate check.

    Watchlist: 50+ likes AND 5000+ views (both required).
    Non-watchlist: 500+ likes AND 40000+ views (both required).
    None views treated as 0 — conservative, fails gate.

    Args:
        likes: like_count from public_metrics.
        views: impression_count from public_metrics (may be None).
        is_watchlist: True if tweet is from a watchlist account.

    Returns:
        True if tweet passes the gate, False otherwise.
    """
    safe_views = views if views is not None else 0
    if is_watchlist:
        return likes >= 50 and safe_views >= 5000
    else:
        return likes >= 500 and safe_views >= 40000


def select_top_posts(scored_posts: list[dict], max_count: int = 5) -> list[dict]:
    """TWIT-06: Select top 3-5 qualifying posts by composite_score.

    Args:
        scored_posts: List of post dicts with at least a "composite_score" key.
        max_count: Maximum number of posts to return (default 5).

    Returns:
        Top min(max_count, len) posts sorted descending by composite_score.
        Posts with composite_score <= 0 are excluded (expired via recency decay).
    """
    # Filter out expired posts (recency decay zeroed them out)
    qualifying = [p for p in scored_posts if p.get("composite_score", 0) > 0]

    # Sort descending by composite_score
    qualifying.sort(key=lambda p: p["composite_score"], reverse=True)

    # Return top N (between 3 and max_count if available)
    return qualifying[:max_count]


# ---------------------------------------------------------------------------
# TwitterAgent class
# ---------------------------------------------------------------------------

class TwitterAgent:
    """Twitter Agent — fetch, filter, score pipeline.

    Called by APScheduler every 2 hours. Fetches qualifying gold-sector tweets
    via Tweepy AsyncClient, applies engagement gate and composite scoring with
    recency decay, selects top 3-5 posts, and queues them for drafting (Plan 03).

    TWIT-01 through TWIT-12 are implemented here.
    TWIT-07 through TWIT-10 (drafting + compliance) are implemented in Plan 03.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.tweepy_client = tweepy.asynchronous.AsyncClient(
            bearer_token=settings.x_api_bearer_token,
            wait_on_rate_limit=False,  # We handle hard-stop ourselves (TWIT-12)
        )
        self.anthropic = AsyncAnthropic(api_key=settings.anthropic_api_key)

    # -----------------------------------------------------------------------
    # Quota management (TWIT-11, TWIT-12)
    # -----------------------------------------------------------------------

    async def _check_quota(
        self, session: AsyncSession
    ) -> tuple[bool, int]:
        """Check monthly tweet read quota against hard-stop limit.

        Reads twitter_monthly_tweet_count and twitter_quota_safety_margin from
        the config table. If the month has rolled over, resets the counter.

        Returns:
            (can_proceed: bool, current_count: int)
            can_proceed is False when count >= (10000 - safety_margin).
        """
        now = datetime.now(timezone.utc)
        current_month = now.strftime("%Y-%m")

        # Fetch existing config rows
        count_row = await self._get_config(session, "twitter_monthly_tweet_count")
        reset_row = await self._get_config(session, "twitter_monthly_reset_date")
        margin_row = await self._get_config(session, "twitter_quota_safety_margin")

        # Handle missing keys — initialize with defaults
        if count_row is None:
            await self._set_config(session, "twitter_monthly_tweet_count", "0")
            current_count = 0
        else:
            current_count = int(count_row.value)

        if reset_row is None:
            await self._set_config(session, "twitter_monthly_reset_date", current_month)
            stored_month = current_month
        else:
            stored_month = reset_row.value

        if margin_row is None:
            await self._set_config(session, "twitter_quota_safety_margin", "1500")
            safety_margin = 1500
        else:
            safety_margin = int(margin_row.value)

        await session.commit()

        # Reset counter if we've crossed into a new calendar month
        if stored_month != current_month:
            logger.info(
                "Quota reset: new month detected (was %s, now %s). "
                "Resetting tweet count from %d to 0.",
                stored_month,
                current_month,
                current_count,
            )
            await self._set_config(session, "twitter_monthly_tweet_count", "0")
            await self._set_config(session, "twitter_monthly_reset_date", current_month)
            await session.commit()
            current_count = 0

        # Hard-stop: remaining capacity < safety margin
        hard_stop_threshold = 10000 - safety_margin
        can_proceed = current_count < hard_stop_threshold

        if not can_proceed:
            logger.warning(
                "Quota hard-stop: %d tweets read this month (limit: %d, margin: %d).",
                current_count,
                10000,
                safety_margin,
            )

        return can_proceed, current_count

    async def _increment_quota(
        self, session: AsyncSession, tweet_count: int
    ) -> None:
        """Increment the monthly tweet read counter by tweet_count. (TWIT-11)"""
        count_row = await self._get_config(session, "twitter_monthly_tweet_count")
        current = int(count_row.value) if count_row else 0
        await self._set_config(
            session,
            "twitter_monthly_tweet_count",
            str(current + tweet_count),
        )
        await session.commit()

    async def _get_config(
        self, session: AsyncSession, key: str
    ) -> Optional[Config]:
        """Read a single config row by key."""
        result = await session.execute(
            select(Config).where(Config.key == key)
        )
        return result.scalar_one_or_none()

    async def _set_config(
        self, session: AsyncSession, key: str, value: str
    ) -> None:
        """Upsert a config row."""
        existing = await self._get_config(session, key)
        if existing is None:
            session.add(Config(key=key, value=value))
        else:
            existing.value = value
            existing.updated_at = datetime.now(timezone.utc)

    # -----------------------------------------------------------------------
    # Data loading
    # -----------------------------------------------------------------------

    async def _load_watchlist(self, session: AsyncSession) -> list[Watchlist]:
        """Load active Twitter watchlist accounts from DB."""
        result = await session.execute(
            select(Watchlist).where(
                Watchlist.platform == "twitter",
                Watchlist.active.is_(True),
            )
        )
        return list(result.scalars().all())

    async def _load_keywords(self, session: AsyncSession) -> list[Keyword]:
        """Load active keywords for Twitter (platform='twitter' or platform=NULL)."""
        result = await session.execute(
            select(Keyword).where(
                (Keyword.platform == "twitter") | (Keyword.platform.is_(None)),
                Keyword.active.is_(True),
            )
        )
        return list(result.scalars().all())

    async def _get_last_run_time(self, session: AsyncSession) -> datetime:
        """Return the ended_at time of the most recent completed twitter_agent run.

        Falls back to now() - 2h if no prior run exists.
        """
        result = await session.execute(
            select(AgentRun)
            .where(
                AgentRun.agent_name == "twitter_agent",
                AgentRun.status == "completed",
                AgentRun.ended_at.isnot(None),
            )
            .order_by(AgentRun.ended_at.desc())
            .limit(1)
        )
        run = result.scalar_one_or_none()
        if run and run.ended_at:
            return run.ended_at
        return datetime.now(timezone.utc) - timedelta(hours=2)

    # -----------------------------------------------------------------------
    # X API fetching
    # -----------------------------------------------------------------------

    async def _resolve_user_id(self, handle: str) -> Optional[str]:
        """Resolve Twitter handle to numeric user ID via get_user().

        Used for lazy-populating Watchlist.platform_user_id to avoid
        repeated resolution calls.

        Returns:
            Numeric user ID as string, or None on error.
        """
        try:
            response = await self.tweepy_client.get_user(
                username=handle.lstrip("@")
            )
            if response and response.data:
                return str(response.data.id)
        except Exception as exc:
            logger.warning("Failed to resolve user ID for @%s: %s", handle, exc)
        return None

    async def _fetch_watchlist_tweets(
        self,
        session: AsyncSession,
        watchlist: list[Watchlist],
        since: datetime,
    ) -> list[dict]:
        """Fetch recent tweets from watchlist accounts via get_users_tweets().

        Resolves platform_user_id lazily if missing. Marks each tweet dict with
        is_watchlist=True and includes relationship_value for authority scoring.
        """
        tweets: list[dict] = []
        total_fetched = 0

        for account in watchlist:
            # Resolve user ID if not cached
            if not account.platform_user_id:
                user_id = await self._resolve_user_id(account.account_handle)
                if user_id is None:
                    logger.warning(
                        "Skipping watchlist account @%s: could not resolve user ID.",
                        account.account_handle,
                    )
                    continue
                account.platform_user_id = user_id
                await session.commit()

            try:
                response = await self.tweepy_client.get_users_tweets(
                    id=account.platform_user_id,
                    max_results=10,
                    tweet_fields=TWEET_FIELDS,
                    expansions=["author_id"],
                    user_fields=USER_FIELDS,
                    start_time=since,
                )
            except Exception as exc:
                logger.warning(
                    "Failed to fetch tweets for @%s (id=%s): %s",
                    account.account_handle,
                    account.platform_user_id,
                    exc,
                )
                continue

            if not response or not response.data:
                continue

            for tweet in response.data:
                metrics = tweet.public_metrics or {}
                tweet_dict = {
                    "id": str(tweet.id),
                    "text": tweet.text,
                    "created_at": tweet.created_at,
                    "author_id": str(tweet.author_id),
                    "account_handle": account.account_handle,
                    "likes": metrics.get("like_count", 0),
                    "retweets": metrics.get("retweet_count", 0),
                    "replies": metrics.get("reply_count", 0),
                    "views": metrics.get("impression_count"),
                    "is_watchlist": True,
                    "relationship_value": account.relationship_value or 1,
                    "follower_count": None,  # populated from users expansion if needed
                }
                tweets.append(tweet_dict)
                total_fetched += 1

        # Count ALL fetched tweets against quota (including those that fail gate later)
        if total_fetched > 0:
            await self._increment_quota(session, total_fetched)

        return tweets

    async def _fetch_keyword_tweets(
        self,
        session: AsyncSession,
        keywords: list[Keyword],
        since: datetime,
    ) -> list[dict]:
        """Fetch tweets matching gold-sector keywords via search_recent_tweets().

        Builds X API v2 query strings from keyword list, splits at 512-char limit,
        deduplicates by tweet ID across queries.
        """
        if not keywords:
            return []

        # Build query strings from keywords, respecting 512-char limit
        queries = self._build_keyword_queries(keywords)
        seen_ids: set[str] = set()
        tweets: list[dict] = []
        total_fetched = 0

        for query in queries:
            try:
                response = await self.tweepy_client.search_recent_tweets(
                    query=query,
                    max_results=100,
                    tweet_fields=TWEET_FIELDS,
                    expansions=["author_id"],
                    user_fields=USER_FIELDS,
                    start_time=since,
                )
            except Exception as exc:
                logger.warning("Keyword search failed (query='%s...'): %s", query[:60], exc)
                continue

            if not response or not response.data:
                continue

            # Build user map from includes for follower counts
            user_map: dict[str, any] = {}
            if response.includes and response.includes.get("users"):
                for user in response.includes["users"]:
                    user_map[str(user.id)] = user

            for tweet in response.data:
                tweet_id = str(tweet.id)
                if tweet_id in seen_ids:
                    continue
                seen_ids.add(tweet_id)

                metrics = tweet.public_metrics or {}
                author = user_map.get(str(tweet.author_id))
                follower_count = None
                if author and author.public_metrics:
                    follower_count = author.public_metrics.get("followers_count")

                tweet_dict = {
                    "id": tweet_id,
                    "text": tweet.text,
                    "created_at": tweet.created_at,
                    "author_id": str(tweet.author_id),
                    "account_handle": author.username if author else None,
                    "likes": metrics.get("like_count", 0),
                    "retweets": metrics.get("retweet_count", 0),
                    "replies": metrics.get("reply_count", 0),
                    "views": metrics.get("impression_count"),
                    "is_watchlist": False,
                    "relationship_value": 1,
                    "follower_count": follower_count,
                }
                tweets.append(tweet_dict)
                total_fetched += 1

        # Count ALL fetched tweets against quota
        if total_fetched > 0:
            await self._increment_quota(session, total_fetched)

        return tweets

    def _build_keyword_queries(self, keywords: list[Keyword]) -> list[str]:
        """Build X API v2 query strings from keyword list.

        Appends -is:retweet lang:en to every query.
        Splits into multiple queries if combined query exceeds 512 chars.

        Returns:
            List of query strings, each <= 512 chars.
        """
        suffix = " -is:retweet lang:en"
        max_len = 512 - len(suffix)

        parts: list[str] = []
        for kw in keywords:
            term = kw.term.strip()
            # Quote multi-word terms; cashtags and hashtags don't need quotes
            if " " in term and not term.startswith(("$", "#")):
                parts.append(f'"{term}"')
            else:
                parts.append(term)

        # Combine with OR up to the 512-char limit
        queries: list[str] = []
        current_parts: list[str] = []
        current_len = 0

        for part in parts:
            # +4 for " OR " separator
            needed = len(part) + (4 if current_parts else 0)
            if current_len + needed > max_len and current_parts:
                queries.append(" OR ".join(current_parts) + suffix)
                current_parts = [part]
                current_len = len(part)
            else:
                current_parts.append(part)
                current_len += needed

        if current_parts:
            queries.append(" OR ".join(current_parts) + suffix)

        return queries

    # -----------------------------------------------------------------------
    # Topic filtering
    # -----------------------------------------------------------------------

    async def _apply_topic_filter(
        self,
        tweet_text: str,
        is_watchlist: bool = False,
    ) -> bool:
        """Filter tweet for gold-sector relevance.

        Step 1: Case-insensitive keyword check against GOLD_KEYWORDS list.
        Step 2 (watchlist only): Claude haiku classification fallback for borderline cases.

        Returns:
            True if tweet is gold-sector relevant, False otherwise.
        """
        text_lower = tweet_text.lower()
        for keyword in GOLD_KEYWORDS:
            if keyword.lower() in text_lower:
                return True

        # Keyword check failed — for watchlist tweets, use Claude as fallback
        if is_watchlist:
            try:
                message = await self.anthropic.messages.create(
                    model="claude-3-haiku-20240307",
                    max_tokens=10,
                    messages=[
                        {
                            "role": "user",
                            "content": (
                                "Is this tweet substantively about gold, precious metals, "
                                "or gold mining? Answer only YES or NO.\n\n"
                                f"Tweet: {tweet_text}"
                            ),
                        }
                    ],
                )
                answer = message.content[0].text.strip().upper()
                return answer == "YES"
            except Exception as exc:
                logger.warning("Claude topic filter failed: %s", exc)
                return False

        return False

    # -----------------------------------------------------------------------
    # Scoring pipeline
    # -----------------------------------------------------------------------

    def _score_tweet(self, tweet: dict) -> dict:
        """Calculate composite score with recency decay for a single tweet dict.

        Adds 'composite_score' and 'engagement_score' keys to the tweet dict.
        Authority score is derived from relationship_value (watchlist) or
        follower count (keyword search).
        """
        now = datetime.now(timezone.utc)
        created_at = tweet.get("created_at")

        # Calculate age in hours
        if created_at:
            if isinstance(created_at, str):
                # Tweepy may return ISO string in some versions
                created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            age_hours = (now - created_at).total_seconds() / 3600.0
        else:
            age_hours = 3.0  # Conservative default if missing

        # Engagement score (raw)
        raw_engagement = calculate_engagement_score(
            likes=tweet.get("likes", 0),
            retweets=tweet.get("retweets", 0),
            replies=tweet.get("replies", 0),
        )

        # Normalize engagement: cap at 10000 for normalization
        engagement_norm = min(raw_engagement / 10000.0, 1.0)

        # Authority score: relationship_value / 5 for watchlist;
        # log-scale follower count for keyword tweets
        if tweet.get("is_watchlist"):
            authority_norm = min((tweet.get("relationship_value", 1)) / 5.0, 1.0)
        else:
            followers = tweet.get("follower_count") or 0
            # log10(100_000) ≈ 5.0 → use as ceiling for normalization
            import math
            authority_norm = min(math.log10(max(followers, 1)) / 5.0, 1.0)

        # Relevance: fixed at 1.0 for posts that pass topic filter
        relevance_norm = 1.0

        raw_composite = calculate_composite_score(
            engagement_norm=engagement_norm,
            authority_norm=authority_norm,
            relevance_norm=relevance_norm,
        )

        # Apply recency decay
        final_composite = apply_recency_decay(raw_composite, age_hours)

        tweet["engagement_score"] = raw_engagement
        tweet["composite_score"] = final_composite
        tweet["age_hours"] = age_hours
        return tweet

    # -----------------------------------------------------------------------
    # Main pipeline
    # -----------------------------------------------------------------------

    async def run(self) -> None:
        """Execute the full Twitter Agent pipeline.

        Pipeline:
        1. Create AgentRun record (status="running")
        2. Check quota — hard-stop if over limit
        3. Load watchlist + keywords from DB
        4. Get 'since' time from last run
        5. Fetch watchlist tweets + keyword tweets
        6. Apply topic filter
        7. Apply engagement gate
        8. Calculate composite scores with recency decay
        9. Select top 3-5 posts
        10. [Drafting — Plan 03 will add this step]
        11. Update AgentRun record

        Errors are caught and logged — agent never crashes the worker (EXEC-04).
        """
        async with AsyncSessionLocal() as session:
            # Step 1: Create AgentRun record
            agent_run = AgentRun(
                agent_name="twitter_agent",
                started_at=datetime.now(timezone.utc),
                status="running",
                errors=[],
            )
            session.add(agent_run)
            await session.commit()

            try:
                await self._run_pipeline(session, agent_run)
            except Exception as exc:
                logger.error(
                    "TwitterAgent.run() unhandled exception: %s",
                    exc,
                    exc_info=True,
                )
                agent_run.status = "failed"
                agent_run.errors = (agent_run.errors or []) + [str(exc)]
                agent_run.ended_at = datetime.now(timezone.utc)
                await session.commit()

    async def _run_pipeline(
        self,
        session: AsyncSession,
        agent_run: AgentRun,
    ) -> None:
        """Inner pipeline — separated from run() for clean error isolation."""

        # Step 2: Quota check
        can_proceed, current_count = await self._check_quota(session)
        if not can_proceed:
            logger.warning(
                "TwitterAgent: quota hard-stop (%d tweets read this month). Skipping run.",
                current_count,
            )
            agent_run.status = "completed"
            agent_run.notes = f"quota exceeded: {current_count} tweets read this month"
            agent_run.ended_at = datetime.now(timezone.utc)
            await session.commit()
            return

        # Step 3: Load data
        watchlist = await self._load_watchlist(session)
        keywords = await self._load_keywords(session)
        logger.info(
            "TwitterAgent: %d watchlist accounts, %d keywords loaded.",
            len(watchlist),
            len(keywords),
        )

        # Step 4: Get since time
        since = await self._get_last_run_time(session)

        # Step 5: Fetch tweets
        watchlist_tweets = await self._fetch_watchlist_tweets(session, watchlist, since)
        keyword_tweets = await self._fetch_keyword_tweets(session, keywords, since)
        all_tweets = watchlist_tweets + keyword_tweets
        items_found = len(all_tweets)
        logger.info(
            "TwitterAgent: fetched %d watchlist tweets, %d keyword tweets (%d total).",
            len(watchlist_tweets),
            len(keyword_tweets),
            items_found,
        )

        # Step 6: Topic filter (watchlist tweets only — keyword tweets already matched)
        topic_filtered: list[dict] = []
        for tweet in all_tweets:
            relevant = await self._apply_topic_filter(
                tweet["text"],
                is_watchlist=tweet["is_watchlist"],
            )
            if relevant:
                topic_filtered.append(tweet)

        items_filtered_by_topic = items_found - len(topic_filtered)
        logger.info(
            "TwitterAgent: %d tweets after topic filter (%d filtered out).",
            len(topic_filtered),
            items_filtered_by_topic,
        )

        # Step 7: Engagement gate
        gate_passed: list[dict] = []
        for tweet in topic_filtered:
            if passes_engagement_gate(
                likes=tweet["likes"],
                views=tweet["views"],
                is_watchlist=tweet["is_watchlist"],
            ):
                gate_passed.append(tweet)

        items_filtered_by_gate = len(topic_filtered) - len(gate_passed)
        items_filtered = items_filtered_by_topic + items_filtered_by_gate
        logger.info(
            "TwitterAgent: %d tweets passed engagement gate (%d filtered out).",
            len(gate_passed),
            items_filtered_by_gate,
        )

        # Step 8: Score with recency decay
        scored_tweets = [self._score_tweet(tweet) for tweet in gate_passed]

        # Step 9: Select top 3-5
        top_posts = select_top_posts(scored_tweets, max_count=5)
        items_queued = len(top_posts)
        logger.info(
            "TwitterAgent: %d top posts selected for drafting.",
            items_queued,
        )

        # Step 10: TODO — Plan 03 will add drafting and DraftItem persistence here
        # For now, log the top posts for observability
        for i, post in enumerate(top_posts, 1):
            logger.info(
                "  [%d] @%s | score=%.3f | likes=%d | views=%s | age=%.1fh | %.80s",
                i,
                post.get("account_handle", "unknown"),
                post["composite_score"],
                post["likes"],
                post.get("views", "?"),
                post.get("age_hours", 0),
                post["text"],
            )

        # Step 11: Update AgentRun
        agent_run.items_found = items_found
        agent_run.items_filtered = items_filtered
        agent_run.items_queued = items_queued
        agent_run.status = "completed"
        agent_run.ended_at = datetime.now(timezone.utc)
        await session.commit()

        logger.info(
            "TwitterAgent run complete: found=%d filtered=%d queued=%d",
            items_found,
            items_filtered,
            items_queued,
        )
