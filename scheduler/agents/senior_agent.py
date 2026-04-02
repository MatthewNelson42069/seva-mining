"""
Senior Agent — story deduplication, queue cap enforcement, expiry sweep,
breaking news alerts, engagement alerts, and morning digest dispatch.

Requirements: SENR-01 through SENR-09, WHAT-01 through WHAT-03, WHAT-05
"""
from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, func, update, or_
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from database import AsyncSessionLocal
from models.agent_run import AgentRun
from models.config import Config
from models.draft_item import DraftItem
from models.watchlist import Watchlist
from services.whatsapp import send_whatsapp_template

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Stopwords for fingerprint token extraction (SENR-02)
# These high-frequency words carry no story-identity signal.
# ---------------------------------------------------------------------------
STOPWORDS: frozenset[str] = frozenset({
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "as", "is", "are", "was", "were", "be",
    "been", "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "shall", "can", "not",
    "this", "that", "these", "those", "it", "its", "they", "their", "he",
    "she", "we", "you", "i", "me", "my", "our", "your", "his", "her",
    "said", "says", "also", "via", "per", "just", "new", "today",
    "following", "after", "before", "over", "under", "about", "into",
})


# ---------------------------------------------------------------------------
# Pure functions — no DB required (SENR-02)
# ---------------------------------------------------------------------------

def extract_fingerprint_tokens(text: str | None) -> frozenset[str]:
    """Return a frozenset of meaningful lowercase tokens from *text*.

    Preserves cashtags (e.g. ``$gld``), numbers, company names, and
    domain-specific terms.  Strips stopwords and single-character tokens.

    Args:
        text: Raw text to tokenise.  ``None`` or empty string returns an
              empty frozenset without raising.

    Returns:
        frozenset of normalised token strings.
    """
    if not text:
        return frozenset()

    lowered = text.lower().strip()
    # Match cashtags first (e.g. $gld, $2400) then regular word tokens.
    # The cashtag pattern \$[a-z0-9]+ captures both ticker symbols and
    # price figures prefixed with $.
    raw_tokens = re.findall(r"\$[a-z0-9]+|\b\w+\b", lowered)

    return frozenset(
        tok for tok in raw_tokens
        if tok not in STOPWORDS and len(tok) > 1
    )


def jaccard_similarity(set_a: frozenset, set_b: frozenset) -> float:
    """Compute Jaccard similarity between two token frozensets.

    ``|A ∩ B| / |A ∪ B|``  — returns ``0.0`` when both sets are empty.

    Args:
        set_a: First token set.
        set_b: Second token set.

    Returns:
        Float in [0.0, 1.0].
    """
    if not set_a and not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


# ---------------------------------------------------------------------------
# SeniorAgent class
# ---------------------------------------------------------------------------

class SeniorAgent:
    """Orchestrates queue management, deduplication, alerts, and digests."""

    def __init__(self) -> None:
        self.settings = get_settings()

    # ------------------------------------------------------------------
    # Config helper
    # ------------------------------------------------------------------

    async def _get_config(
        self, session: AsyncSession, key: str, default: str
    ) -> str:
        """Fetch a single config value by *key* or return *default*."""
        result = await session.execute(
            select(Config.value).where(Config.key == key)
        )
        return result.scalar_one_or_none() or default

    # ------------------------------------------------------------------
    # SENR-02: Story deduplication
    # ------------------------------------------------------------------

    async def _run_deduplication(
        self, session: AsyncSession, new_item_id: uuid.UUID
    ) -> None:
        """Set ``related_id`` on *new_item* when a similar pending item exists.

        Compares the new item's fingerprint tokens against all ``pending``
        items created in the last 24 hours.  If any existing item shares
        ≥ ``senior_dedup_threshold`` (default 0.40) token overlap (Jaccard),
        the newer item's ``related_id`` is set to the older item's ``id``.

        Both items remain in the queue — neither is dropped.

        Args:
            session: Active async SQLAlchemy session.
            new_item_id: UUID of the freshly persisted ``DraftItem``.
        """
        threshold = float(
            await self._get_config(session, "senior_dedup_threshold", "0.40")
        )
        lookback_hours = int(
            await self._get_config(session, "senior_dedup_lookback_hours", "24")
        )

        new_item = await session.get(DraftItem, new_item_id)
        if new_item is None:
            logger.warning("_run_deduplication: DraftItem %s not found", new_item_id)
            return

        new_text = (new_item.source_text or "") + " " + (new_item.rationale or "")
        new_tokens = extract_fingerprint_tokens(new_text)
        if not new_tokens:
            return

        cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
        result = await session.execute(
            select(DraftItem)
            .where(
                DraftItem.status == "pending",
                DraftItem.created_at >= cutoff,
                DraftItem.id != new_item_id,
            )
            .order_by(DraftItem.created_at.asc())
        )
        existing_items = result.scalars().all()

        best_score = 0.0
        best_match = None

        for item in existing_items:
            item_text = (item.source_text or "") + " " + (item.rationale or "")
            item_tokens = extract_fingerprint_tokens(item_text)
            if not item_tokens:
                continue
            score = jaccard_similarity(new_tokens, item_tokens)
            if score >= threshold and score > best_score:
                best_score = score
                best_match = item

        if best_match is not None:
            new_item.related_id = best_match.id
            logger.info(
                "Dedup: item %s linked to %s (Jaccard=%.3f)",
                new_item_id,
                best_match.id,
                best_score,
            )

    # ------------------------------------------------------------------
    # SENR-01 / SENR-03 / SENR-04: Queue cap enforcement
    # ------------------------------------------------------------------

    async def _enforce_queue_cap(
        self, session: AsyncSession, new_item_id: uuid.UUID
    ) -> None:
        """Enforce the 15-item pending queue cap.

        When the queue is at capacity and a new item arrives:
        - If the new item's score is strictly greater than the lowest-scoring
          pending item, delete the lowest-scoring item (new item stays).
        - Otherwise delete the new item (discard the lower-priority arrival).

        Tiebreaking: when two items share the lowest score, the one with the
        earlier ``expires_at`` (less time remaining) is displaced first.
        This is achieved by ``ORDER BY score ASC, expires_at ASC``.

        Args:
            session: Active async SQLAlchemy session.
            new_item_id: UUID of the freshly persisted ``DraftItem``.
        """
        cap = int(await self._get_config(session, "senior_queue_cap", "15"))

        # Count pending items that are NOT the new item
        count_result = await session.execute(
            select(func.count())
            .select_from(DraftItem)
            .where(
                DraftItem.status == "pending",
                DraftItem.id != new_item_id,
            )
        )
        existing_count = count_result.scalar_one()

        if existing_count < cap:
            # Queue has room — accept new item without displacement
            return

        # Queue is at or over cap — compare new item against the lowest-scoring existing item
        new_item = await session.get(DraftItem, new_item_id)
        if new_item is None:
            logger.warning("_enforce_queue_cap: DraftItem %s not found", new_item_id)
            return

        lowest_result = await session.execute(
            select(DraftItem)
            .where(
                DraftItem.status == "pending",
                DraftItem.id != new_item_id,
            )
            .order_by(DraftItem.score.asc(), DraftItem.expires_at.asc())
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        lowest = lowest_result.scalar_one_or_none()

        if lowest is None:
            # Shouldn't happen if count > 0, but guard defensively
            return

        new_score = float(new_item.score or 0)
        low_score = float(lowest.score or 0)

        if new_score > low_score:
            # New item wins — displace the lowest-scoring existing item
            logger.info(
                "Queue cap: displacing item %s (score=%.2f) in favour of %s (score=%.2f)",
                lowest.id,
                low_score,
                new_item_id,
                new_score,
            )
            await session.delete(lowest)
        else:
            # New item loses — discard it
            logger.info(
                "Queue cap: discarding new item %s (score=%.2f) — queue full, lowest=%.2f",
                new_item_id,
                new_score,
                low_score,
            )
            await session.delete(new_item)

    # ------------------------------------------------------------------
    # WHAT-02: Breaking news alert
    # ------------------------------------------------------------------

    async def _check_breaking_news_alert(
        self, session: AsyncSession, item_id: uuid.UUID
    ) -> None:
        """Fire a WhatsApp breaking news alert when item score >= threshold.

        Reads ``senior_breaking_news_threshold`` from config (default ``"8.5"``).
        Fires once per item.  Errors are logged but do not propagate.

        Args:
            session: Active async SQLAlchemy session.
            item_id: UUID of the DraftItem to check.
        """
        item = await session.get(DraftItem, item_id)
        if item is None:
            logger.warning("_check_breaking_news_alert: DraftItem %s not found", item_id)
            return

        threshold = float(
            await self._get_config(session, "senior_breaking_news_threshold", "8.5")
        )
        if float(item.score or 0) < threshold:
            return

        # Extract headline: first sentence of rationale
        rationale = item.rationale or ""
        parts = rationale.split(". ")
        headline = parts[0] + "." if parts else rationale

        dashboard_url = await self._get_config(
            session, "dashboard_url", "https://app.sevamining.com"
        )

        try:
            await send_whatsapp_template(
                "breaking_news",
                {
                    "1": headline,
                    "2": item.source_account or "unknown",
                    "3": str(round(float(item.score), 1)),
                    "4": dashboard_url,
                },
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "_check_breaking_news_alert: WhatsApp send failed for item %s: %s",
                item_id,
                exc,
            )

    # ------------------------------------------------------------------
    # WHAT-03: Expiry alerts
    # ------------------------------------------------------------------

    async def _check_expiry_alerts(self, session: AsyncSession) -> None:
        """Fire expiry alerts for high-value items approaching expiry.

        Queries pending items where ``score >= senior_expiry_alert_score_threshold``
        AND ``expires_at`` is within the next ``senior_expiry_alert_minutes_before``
        minutes AND ``alerted_expiry_at IS NULL``.

        For each candidate, sends the ``expiry_alert`` WhatsApp template and
        sets ``alerted_expiry_at`` to prevent double-sends.

        Args:
            session: Active async SQLAlchemy session.
        """
        score_threshold = float(
            await self._get_config(session, "senior_expiry_alert_score_threshold", "7.0")
        )
        minutes_before = int(
            await self._get_config(session, "senior_expiry_alert_minutes_before", "60")
        )
        dashboard_url = await self._get_config(
            session, "dashboard_url", "https://app.sevamining.com"
        )

        now = datetime.now(timezone.utc)
        window_end = now + timedelta(minutes=minutes_before)

        result = await session.execute(
            select(DraftItem)
            .where(
                DraftItem.status == "pending",
                DraftItem.score >= score_threshold,
                DraftItem.expires_at != None,  # noqa: E711
                DraftItem.expires_at >= now,
                DraftItem.expires_at <= window_end,
                DraftItem.alerted_expiry_at == None,  # noqa: E711
            )
        )
        candidates = result.scalars().all()

        for item in candidates:
            rationale = item.rationale or ""
            parts = rationale.split(". ")
            headline = parts[0] + "." if parts else rationale

            minutes_remaining = max(
                0,
                int((item.expires_at - datetime.now(timezone.utc)).total_seconds() / 60),
            )

            try:
                await send_whatsapp_template(
                    "expiry_alert",
                    {
                        "1": item.platform or "unknown",
                        "2": headline,
                        "3": str(minutes_remaining),
                        "4": dashboard_url,
                    },
                )
                item.alerted_expiry_at = datetime.now(timezone.utc)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "_check_expiry_alerts: WhatsApp send failed for item %s: %s",
                    item.id,
                    exc,
                )

    # ------------------------------------------------------------------
    # WHAT-02 / WHAT-05: Engagement alerts
    # ------------------------------------------------------------------

    async def _send_engagement_alert(
        self, item: DraftItem, dashboard_url: str
    ) -> None:
        """Send a breaking_news WhatsApp alert for an engagement gate crossing.

        Template variables:
        - ``{{1}}``: first ~100 chars of ``source_text`` (word-boundary truncation)
        - ``{{2}}``: ``source_account``
        - ``{{3}}``: composite engagement score (likes + retweets*2 + replies*1.5)
        - ``{{4}}``: dashboard URL

        Args:
            item: The DraftItem that crossed an engagement threshold.
            dashboard_url: Dashboard URL from config.
        """
        snap = item.engagement_snapshot or {}
        likes = snap.get("likes", 0) or 0
        retweets = snap.get("retweets", 0) or 0
        replies = snap.get("replies", 0) or 0
        engagement_score = likes * 1 + retweets * 2 + replies * 1.5

        source_text = item.source_text or ""
        if len(source_text) > 100:
            # Truncate at word boundary
            truncated = source_text[:100]
            last_space = truncated.rfind(" ")
            excerpt = truncated[:last_space] if last_space > 0 else truncated
        else:
            excerpt = source_text

        try:
            await send_whatsapp_template(
                "breaking_news",
                {
                    "1": excerpt,
                    "2": item.source_account or "unknown",
                    "3": str(round(engagement_score, 1)),
                    "4": dashboard_url,
                },
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "_send_engagement_alert: WhatsApp send failed for item %s: %s",
                item.id,
                exc,
            )

    async def _check_engagement_alerts(self, session: AsyncSession) -> None:
        """Check pending Twitter items for engagement gate crossings and fire alerts.

        Watchlist items get TWO alerts:
        - Early signal: 50+ likes AND 5000+ views → level = ``"watchlist"``
        - Viral confirmation: 500+ likes AND 40000+ views → level = ``"viral"``

        Non-watchlist items get ONE alert:
        - Viral: 500+ likes AND 40000+ views → level = ``"viral"``

        Deduplication via ``engagement_alert_level`` column — items already at
        ``"viral"`` are excluded from the query entirely.

        Args:
            session: Active async SQLAlchemy session.
        """
        # Load active watchlist handles for twitter (lowercased, stripped @)
        wl_result = await session.execute(
            select(Watchlist.account_handle).where(
                Watchlist.platform == "twitter",
                Watchlist.active == True,  # noqa: E712
            )
        )
        watchlist_handles: set[str] = {
            row[0].lstrip("@").lower() for row in wl_result.all()
        }

        dashboard_url = await self._get_config(
            session, "dashboard_url", "https://app.sevamining.com"
        )

        # Candidates: pending twitter items NOT yet at viral level
        candidates_result = await session.execute(
            select(DraftItem).where(
                DraftItem.status == "pending",
                DraftItem.platform == "twitter",
                or_(
                    DraftItem.engagement_alert_level.is_(None),
                    DraftItem.engagement_alert_level == "watchlist",
                ),
            )
        )
        candidates = candidates_result.scalars().all()

        for item in candidates:
            snap = item.engagement_snapshot or {}
            likes = snap.get("likes", 0) or 0
            views = snap.get("views", 0) or 0

            is_watchlist = (item.source_account or "").lstrip("@").lower() in watchlist_handles
            current_level = item.engagement_alert_level

            if is_watchlist:
                if current_level is None and likes >= 50 and views >= 5000:
                    await self._send_engagement_alert(item, dashboard_url)
                    item.engagement_alert_level = "watchlist"
                elif current_level == "watchlist" and likes >= 500 and views >= 40000:
                    await self._send_engagement_alert(item, dashboard_url)
                    item.engagement_alert_level = "viral"
            else:
                if current_level is None and likes >= 500 and views >= 40000:
                    await self._send_engagement_alert(item, dashboard_url)
                    item.engagement_alert_level = "viral"

    # ------------------------------------------------------------------
    # SENR-05 / SENR-09: Expiry sweep job
    # ------------------------------------------------------------------

    async def run_expiry_sweep(self) -> None:
        """Run the 30-minute expiry sweep job.

        Responsibilities:
        1. Bulk-expire stale items (``expires_at < now()``).
        2. Fire expiry alerts for high-value items approaching expiry.
        3. Fire engagement alerts for posts crossing like/view thresholds.

        Logs to ``AgentRun`` with ``agent_name='expiry_sweep'``.
        Errors are captured and do not propagate (EXEC-04).
        """
        async with AsyncSessionLocal() as session:
            run = AgentRun(
                agent_name="expiry_sweep",
                started_at=datetime.now(timezone.utc),
                status="running",
            )
            session.add(run)
            await session.flush()

            try:
                # Step 1: Bulk-expire stale items
                result = await session.execute(
                    update(DraftItem)
                    .where(
                        DraftItem.status == "pending",
                        DraftItem.expires_at != None,  # noqa: E711
                        DraftItem.expires_at < func.now(),
                    )
                    .values(status="expired", updated_at=func.now())
                )
                items_expired = result.rowcount
                logger.info("run_expiry_sweep: marked %d items as expired", items_expired)

                # Step 2: Fire expiry alerts for approaching expirations
                await self._check_expiry_alerts(session)

                # Step 3: Fire engagement alerts for threshold crossings
                await self._check_engagement_alerts(session)

                run.status = "completed"
                run.ended_at = datetime.now(timezone.utc)
                await session.commit()

            except Exception as exc:  # noqa: BLE001
                logger.exception("run_expiry_sweep failed: %s", exc)
                run.status = "failed"
                run.errors = [str(exc)]
                run.ended_at = datetime.now(timezone.utc)
                try:
                    await session.commit()
                except Exception:
                    await session.rollback()

    # ------------------------------------------------------------------
    # SENR-01: process_new_item — sub-agent entry point
    # ------------------------------------------------------------------

    async def process_new_item(self, item_id: uuid.UUID) -> None:
        """Process a newly written DraftItem through the Senior Agent pipeline.

        Called by sub-agents immediately after persisting a ``DraftItem``.
        Runs deduplication, queue cap enforcement, and breaking news alert
        check within a single DB session.  Errors are captured in
        ``AgentRun.errors`` and do not propagate (EXEC-04).

        Args:
            item_id: UUID of the freshly committed ``DraftItem``.
        """
        async with AsyncSessionLocal() as session:
            run = AgentRun(
                agent_name="senior_agent_intake",
                started_at=datetime.now(timezone.utc),
                status="running",
            )
            session.add(run)
            await session.flush()

            try:
                await self._run_deduplication(session, item_id)
                await self._enforce_queue_cap(session, item_id)
                await self._check_breaking_news_alert(session, item_id)

                run.status = "completed"
                run.ended_at = datetime.now(timezone.utc)
                await session.commit()

            except Exception as exc:  # noqa: BLE001
                logger.exception("process_new_item failed for item %s: %s", item_id, exc)
                run.status = "failed"
                run.errors = [str(exc)]
                run.ended_at = datetime.now(timezone.utc)
                try:
                    await session.commit()
                except Exception:
                    await session.rollback()


# ---------------------------------------------------------------------------
# Module-level convenience function — avoids circular imports from sub-agents
# ---------------------------------------------------------------------------

async def process_new_items(item_ids: list[uuid.UUID]) -> None:
    """Create a SeniorAgent and process each item in *item_ids* sequentially.

    Designed to be called from TwitterAgent (and future sub-agents) after
    writing DraftItems to the database.  Using a module-level function avoids
    a direct class import inside the sub-agent, which would create a circular
    dependency if SeniorAgent ever imports sub-agent models directly.

    Args:
        item_ids: List of DraftItem UUIDs to process through the Senior Agent.
    """
    agent = SeniorAgent()
    for item_id in item_ids:
        await agent.process_new_item(item_id)
