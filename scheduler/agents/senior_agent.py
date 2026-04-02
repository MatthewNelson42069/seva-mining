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

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from database import AsyncSessionLocal
from models.agent_run import AgentRun
from models.config import Config
from models.draft_item import DraftItem

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
