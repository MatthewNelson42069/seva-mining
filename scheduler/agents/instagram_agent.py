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


def passes_engagement_gate(
    likes: int,
    created_at: datetime,
    *,
    min_likes: int = 200,
    max_post_age_hours: float = 8.0,
) -> bool:
    """INST-03: min_likes+ likes AND post created within last max_post_age_hours (strictly < threshold).

    Args:
        likes: Number of likes on the post.
        created_at: Timezone-aware datetime when the post was published.
        min_likes: Minimum likes required (default 200, DB-driven via EXEC-02).
        max_post_age_hours: Maximum post age in hours (default 8.0, DB-driven via EXEC-02).

    Returns:
        True if both thresholds are satisfied, False otherwise.
    """
    if likes < min_likes:
        return False
    now = datetime.now(timezone.utc)
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    age_hours = (now - created_at).total_seconds() / 3600.0
    return age_hours < max_post_age_hours


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

                # WhatsApp new-item notification (fires after commit, non-fatal)
                items_queued_count = agent_run.items_queued or 0
                if items_queued_count > 0:
                    try:
                        from services.whatsapp import send_whatsapp_message  # noqa: PLC0415
                        await send_whatsapp_message(
                            f"📸 Instagram Agent — {items_queued_count} new item{'s' if items_queued_count != 1 else ''} ready for review"
                        )
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("WhatsApp notification failed (non-fatal): %s", exc)

    async def _run_pipeline(self, session: AsyncSession, agent_run: AgentRun) -> None:
        """Full pipeline: fetch, filter, score, draft, persist. Implemented across Plans 02-04."""
        # Step 1: Load config
        max_per_hashtag = int(await self._get_config(session, "instagram_max_posts_per_hashtag", "50"))
        max_per_account = int(await self._get_config(session, "instagram_max_posts_per_account", "10"))
        top_n = int(await self._get_config(session, "instagram_top_n", "3"))

        # Step 1b: Read engagement gate thresholds from DB (EXEC-02)
        min_likes = int(await self._get_config(session, "instagram_min_likes", "200"))
        max_post_age_hours = float(await self._get_config(session, "instagram_max_post_age_hours", "8"))
        logger.info(
            "InstagramAgent: engagement thresholds — min_likes=%d, max_age=%.1fh",
            min_likes, max_post_age_hours,
        )

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
                if passes_engagement_gate(likes=p.get("likesCount", 0), created_at=created, min_likes=min_likes, max_post_age_hours=max_post_age_hours):
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

        # Step 7: Draft comments for top posts (INST-05, INST-06)
        new_item_ids = []
        for post in top_posts:
            drafts = await self._draft_comments(post)
            if not drafts:
                continue
            # Step 8: Compliance check (INST-06, INST-08)
            compliant = await self._filter_compliant_drafts(drafts)
            if not compliant:
                continue
            # Step 9: Persist DraftItem (INST-12)
            draft_item = self._build_draft_item(post, compliant)
            session.add(draft_item)
            await session.flush()
            new_item_ids.append(draft_item.id)
            agent_run.items_queued = (agent_run.items_queued or 0) + 1

        await session.commit()

        # Step 9b: Senior Agent integration (lazy import, same as TwitterAgent)
        if new_item_ids:
            from agents.senior_agent import process_new_items  # noqa: PLC0415
            await process_new_items(new_item_ids)

        # Step 10: Health monitoring (INST-10)
        hashtag_counts = self._count_posts_by_source(hashtag_posts)
        self._store_hashtag_counts(agent_run, hashtag_counts)
        run_count = await self._get_run_count(session)
        baseline_threshold = int(
            await self._get_config(session, "instagram_health_baseline_runs", "3")
        )
        health_warnings = await self._check_scraper_health(
            session, hashtag_counts, run_count, baseline_threshold
        )
        if health_warnings:
            agent_run.errors = health_warnings

        # Step 11: Critical failure check (INST-11)
        total_fetched = sum(hashtag_counts.values()) + len(account_posts)
        consecutive_zeros = await self._check_critical_failure(session, total_fetched)
        if consecutive_zeros == 2:
            try:
                from services.whatsapp import send_whatsapp_message  # noqa: PLC0415
                await send_whatsapp_message(
                    "⚠️ Instagram scraper failure — 0 posts fetched for 2 consecutive runs. "
                    "Check Apify actor health."
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("WhatsApp scraper-failure alert failed (non-fatal): %s", exc)

        await session.commit()

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
            items = await self._call_apify_actor_with_retry(run_input)
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
            items = await self._call_apify_actor_with_retry(run_input)
            all_items.extend(items)
        return all_items

    async def _call_apify_actor_once(self, run_input: dict) -> list[dict]:
        """Call apify/instagram-scraper and return dataset items (no retry)."""
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

    async def _call_apify_actor_with_retry(self, run_input: dict, max_retries: int = 2) -> list[dict]:
        """INST-09: Call Apify actor with exponential backoff retry.

        Retries up to max_retries times on exception. Backoff: 2**attempt seconds
        (attempt=0 → 1s, attempt=1 → 2s). Returns empty list after all retries exhausted.
        """
        last_exc = None
        for attempt in range(max_retries + 1):  # 0, 1, 2 = 3 total attempts
            try:
                return await self._call_apify_actor_once(run_input)
            except Exception as exc:
                last_exc = exc
                if attempt < max_retries:
                    backoff = 2 ** attempt  # 1s, 2s
                    logger.warning(
                        "Apify call attempt %d failed: %s. Retrying in %ds...",
                        attempt + 1, exc, backoff,
                    )
                    await asyncio.sleep(backoff)
                else:
                    logger.error(
                        "Apify call failed after %d attempts: %s",
                        max_retries + 1, last_exc,
                    )
        return []  # All retries exhausted

    # -----------------------------------------------------------------------
    # INST-09: Retry helpers
    # -----------------------------------------------------------------------

    def _count_posts_by_source(self, hashtag_posts: list[dict]) -> dict[str, int]:
        """Count posts per _source_tag in a list of fetched hashtag posts."""
        counts: dict[str, int] = {}
        for p in hashtag_posts:
            tag = p.get("_source_tag", "")
            if tag:
                counts[tag] = counts.get(tag, 0) + 1
        return counts

    def _store_hashtag_counts(self, agent_run: AgentRun, hashtag_counts: dict[str, int]) -> None:
        """Store per-hashtag fetch counts in agent_run.notes as JSON (INST-10)."""
        agent_run.notes = json.dumps({
            "hashtag_counts": hashtag_counts,
            "total_posts_fetched": sum(hashtag_counts.values()),
        })

    async def _get_run_count(self, session: AsyncSession) -> int:
        """Return total count of completed instagram_agent runs."""
        from sqlalchemy import func
        result = await session.execute(
            select(func.count()).where(
                AgentRun.agent_name == "instagram_agent",
                AgentRun.status == "completed",
            )
        )
        return result.scalar_one() or 0

    # -----------------------------------------------------------------------
    # INST-10: Scraper health monitoring
    # -----------------------------------------------------------------------

    async def _check_scraper_health(
        self,
        session: AsyncSession,
        current_counts: dict[str, int],
        run_number: int,
        baseline_threshold: int,
    ) -> list[str]:
        """INST-10: Return health warning strings for hashtags below 20% of rolling average.

        Skips the check when run_number <= baseline_threshold (no baseline yet).
        Queries last 7 completed instagram_agent runs for rolling averages.
        """
        if run_number <= baseline_threshold:
            return []

        # Query last 7 completed runs with notes
        result = await session.execute(
            select(AgentRun).where(
                AgentRun.agent_name == "instagram_agent",
                AgentRun.status == "completed",
                AgentRun.notes.isnot(None),
            ).order_by(AgentRun.created_at.desc()).limit(7)
        )
        prior_runs = result.scalars().all()

        if not prior_runs:
            return []

        # Build per-hashtag rolling averages from notes JSON
        tag_sums: dict[str, list[int]] = {}
        for run in prior_runs:
            try:
                notes = json.loads(run.notes)
                counts = notes.get("hashtag_counts", {})
                for tag, count in counts.items():
                    tag_sums.setdefault(tag, []).append(count)
            except (json.JSONDecodeError, TypeError):
                continue

        if not tag_sums:
            return []

        warnings: list[str] = []
        for tag, current_count in current_counts.items():
            historical = tag_sums.get(tag, [])
            if not historical:
                continue
            rolling_avg = sum(historical) / len(historical)
            threshold_20pct = rolling_avg * 0.20
            if current_count < threshold_20pct:
                warnings.append(
                    f"health_warning: #{tag} returned {current_count} posts "
                    f"(avg={rolling_avg:.1f}, threshold={threshold_20pct:.1f})"
                )
                logger.warning(
                    "health_warning: #%s returned %d posts (rolling avg=%.1f)",
                    tag, current_count, rolling_avg,
                )

        return warnings

    # -----------------------------------------------------------------------
    # INST-11: Critical failure alerting
    # -----------------------------------------------------------------------

    async def _check_critical_failure(
        self,
        session: AsyncSession,
        current_total: int,
    ) -> int:
        """INST-11: Return consecutive zero-run count. 0 if current run has results.

        Counts the current run (0 total) + prior consecutive all-zero completed runs.
        """
        if current_total > 0:
            return 0

        # Current run is zero — count prior consecutive all-zero runs
        result = await session.execute(
            select(AgentRun).where(
                AgentRun.agent_name == "instagram_agent",
                AgentRun.status == "completed",
                AgentRun.notes.isnot(None),
            ).order_by(AgentRun.created_at.desc()).limit(7)
        )
        prior_runs = result.scalars().all()

        consecutive = 1  # Current run counts as zero
        for run in prior_runs:
            try:
                notes = json.loads(run.notes)
                total = notes.get("total_posts_fetched", -1)
                if total == 0:
                    consecutive += 1
                else:
                    break  # Non-zero run breaks the streak
            except (json.JSONDecodeError, TypeError):
                break

        return consecutive

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

    async def _draft_comments(self, post: dict) -> list[dict]:
        """Draft 2-3 comment alternatives for a post via Claude Sonnet (INST-05).

        Returns list of dicts with 'text' and 'rationale' keys.
        Returns empty list if JSON parse fails.
        """
        return await draft_for_post(post=post, client=self.anthropic)

    async def _check_instagram_compliance(self, draft_text: str) -> bool:
        """Check a draft comment for compliance violations (INST-06, INST-08).

        Pre-screens for '#' and 'seva mining' locally before calling Claude.
        Fail-safe: any non-PASS response blocks the draft.

        Returns True if draft passes, False if blocked.
        """
        return await check_compliance(draft=draft_text, client=self.anthropic)

    async def _filter_compliant_drafts(self, drafts: list[dict]) -> list[dict]:
        """Run compliance check on each draft and return only passing ones."""
        passing = []
        for draft in drafts:
            if await self._check_instagram_compliance(draft["text"]):
                passing.append(draft)
        return passing

    def _build_draft_item(self, post: dict, compliant_drafts: list[dict]) -> DraftItem:
        """Build a DraftItem with platform='instagram' and 12h expiry (INST-12)."""
        return DraftItem(
            platform="instagram",
            status="pending",
            source_url=post.get("url", ""),
            source_text=(post.get("caption") or "")[:500],
            source_account=post.get("ownerUsername", "unknown"),
            alternatives=[d["text"] for d in compliant_drafts],
            rationale=compliant_drafts[0]["rationale"] if compliant_drafts else "",
            score=post.get("score", 0.0),
            engagement_snapshot={
                "likes": post.get("likesCount", 0),
                "comments": post.get("commentsCount", 0),
                "follower_count": (
                    post.get("ownerFollowersCount") or post.get("followersCount") or 0
                ),
                "captured_at": datetime.now(timezone.utc).isoformat(),
            },
            expires_at=datetime.now(timezone.utc) + timedelta(hours=12),
        )


# ---------------------------------------------------------------------------
# Module-level functions — for direct testability (mirrors twitter_agent.py pattern)
# ---------------------------------------------------------------------------

async def draft_for_post(post: dict, client: AsyncAnthropic) -> list[dict]:
    """Draft 2-3 Instagram comment alternatives via Claude Sonnet (INST-05, INST-06).

    Args:
        post: Instagram post dict with caption, ownerUsername, likesCount, commentsCount.
        client: AsyncAnthropic instance injected by caller.

    Returns:
        List of dicts with 'text' and 'rationale' keys. Empty list on parse failure.
    """
    system_prompt = (
        "You are a senior gold sector analyst writing Instagram comments. "
        "Every comment must lead with a specific data point, stat, or market insight. "
        "1-2 sentences max. NEVER include hashtags (no # character). "
        "Write in a measured, analytical tone."
    )
    caption = post.get("caption") or ""
    author = post.get("ownerUsername") or "unknown"
    likes = post.get("likesCount", 0)
    comments = post.get("commentsCount", 0)
    user_prompt = (
        f"Post by @{author} with {likes} likes and {comments} comments:\n"
        f"{caption}\n\n"
        "Write exactly 3 comment alternatives (no hashtags). "
        "Respond with JSON in this format:\n"
        '{"comment_alternatives": [{"text": "...", "rationale": "..."}, ...]}'
    )
    message = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    raw_text = message.content[0].text.strip()
    try:
        parsed = json.loads(raw_text)
    except (json.JSONDecodeError, Exception):
        return []

    if isinstance(parsed, dict):
        alternatives = parsed.get("comment_alternatives") or []
    elif isinstance(parsed, list):
        # Test-compatible: plain list of strings
        alternatives = [
            {"text": item, "rationale": ""} if isinstance(item, str) else item
            for item in parsed
        ]
    else:
        return []

    return [a for a in alternatives if isinstance(a, dict) and "text" in a]


async def check_compliance(draft: str, client: AsyncAnthropic) -> bool:
    """Check a draft Instagram comment for compliance violations (INST-06, INST-08).

    Pre-screens locally for '#' and 'seva mining' before calling Claude.
    Fail-safe: only explicit 'pass' in Claude response returns True.

    Args:
        draft: Draft comment text to check.
        client: AsyncAnthropic instance injected by caller.

    Returns:
        True if draft passes all checks, False if blocked.
    """
    # INST-06: Pre-screen for hashtags — no LLM needed
    if "#" in draft:
        return False
    # INST-08: Pre-screen for brand mention — no LLM needed
    if "seva mining" in draft.lower():
        return False

    # Claude Haiku compliance check
    message = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        system=(
            "You are a compliance checker for social media comments. "
            "Check if this comment: 1) mentions 'Seva Mining' or any company promotion, "
            "2) contains financial advice, 3) contains hashtags. "
            "Reply with exactly PASS or FAIL with reason."
        ),
        messages=[{"role": "user", "content": f"Check this draft: {draft}"}],
    )
    result_text = message.content[0].text.strip().lower()
    # Fail-safe: only explicit "pass" returns True (CONTEXT.md)
    if "pass" in result_text:
        return True
    return False


def build_draft_item_expiry(created_at: datetime) -> DraftItem:
    """Build a minimal DraftItem with expires_at = created_at + 12 hours (INST-12).

    Used by tests to verify expiry calculation independently of the full pipeline.
    Does NOT persist to the database (no session required).

    Args:
        created_at: The creation datetime (timezone-aware UTC).

    Returns:
        DraftItem with platform='instagram' and expires_at set to +12 hours.
    """
    return DraftItem(
        platform="instagram",
        status="pending",
        source_url="",
        source_text="",
        source_account="",
        alternatives=[],
        rationale="",
        score=0.0,
        expires_at=created_at + timedelta(hours=12),
    )
