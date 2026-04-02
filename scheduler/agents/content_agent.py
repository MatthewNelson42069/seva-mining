"""
Content Agent — ingest, deduplicate, score, and select daily gold sector stories.

Monitors RSS feeds (Kitco, Mining.com, JMN, WGC) and SerpAPI news search every
~6 hours for qualifying stories. Applies scoring (relevance, recency, credibility),
deduplication (URL + headline similarity), and selects the single highest-scoring
story above the 7.0/10 quality threshold.

Requirements: CONT-01 through CONT-17
"""
from __future__ import annotations

import difflib
import logging
from datetime import datetime, timezone

from anthropic import AsyncAnthropic

from config import get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Credibility tier lookup — module-level constant (CONT-05)
# ---------------------------------------------------------------------------

CREDIBILITY_TIERS: dict[str, float] = {
    "reuters.com": 1.0,
    "bloomberg.com": 1.0,
    "worldgoldcouncil.org": 0.9,
    "gold.org": 0.9,
    "kitco.com": 0.8,
    "mining.com": 0.8,
    "juniorminingnetwork.com": 0.7,
}
DEFAULT_CREDIBILITY = 0.4


# ---------------------------------------------------------------------------
# Pure scoring functions — module-level for direct testability (CONT-05)
# ---------------------------------------------------------------------------

def recency_score(published: datetime) -> float:
    """CONT-05: Return recency score based on story age.

    Returns:
        1.0 for <3h, 0.8 for <6h, 0.6 for <12h, 0.4 for <24h, 0.2 for >=24h
    """
    now = datetime.now(timezone.utc)
    if published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)
    age_hours = (now - published).total_seconds() / 3600
    if age_hours < 3:
        return 1.0
    if age_hours < 6:
        return 0.8
    if age_hours < 12:
        return 0.6
    if age_hours < 24:
        return 0.4
    return 0.2


def credibility_score(source_domain: str) -> float:
    """CONT-05: Return credibility score for a source domain.

    Args:
        source_domain: Domain name e.g. 'reuters.com'. Matched exactly against tier dict.

    Returns:
        Score from CREDIBILITY_TIERS, or DEFAULT_CREDIBILITY (0.4) for unknown sources.
    """
    return CREDIBILITY_TIERS.get(source_domain, DEFAULT_CREDIBILITY)


def calculate_story_score(relevance: float, recency: float, credibility: float) -> float:
    """CONT-05: Compute composite story score.

    Formula: (relevance * 0.4 + recency * 0.3 + credibility * 0.3) * 10
    Scaled to 0-10 range.

    Args:
        relevance: 0.0-1.0 relevance score (assigned by Claude relevance pass)
        recency: 0.0-1.0 recency score from recency_score()
        credibility: 0.0-1.0 credibility score from credibility_score()

    Returns:
        Score in 0-10 range.
    """
    return (relevance * 0.4 + recency * 0.3 + credibility * 0.3) * 10


# ---------------------------------------------------------------------------
# Deduplication — URL + headline similarity (CONT-04)
# ---------------------------------------------------------------------------

def deduplicate_stories(stories: list[dict]) -> list[dict]:
    """CONT-04: Remove duplicate stories by URL and headline similarity.

    Step 1: URL dedup — keep first occurrence of each URL.
    Step 2: Headline dedup — if SequenceMatcher ratio >= 0.85 between any two
            remaining titles, keep the one with higher credibility_score(source_name).
            On tie, keep the earlier (first encountered) entry.

    Args:
        stories: List of story dicts. Each must have 'link', 'title', and 'source_name' keys.

    Returns:
        Deduplicated list of story dicts.
    """
    # Step 1: URL deduplication — seen set, keep first
    seen_urls: set[str] = set()
    url_deduped: list[dict] = []
    for story in stories:
        url = story.get("link", "")
        if url and url in seen_urls:
            continue
        if url:
            seen_urls.add(url)
        url_deduped.append(story)

    # Step 2: Headline similarity deduplication
    # For each story, check if it is similar (>=0.85) to any already-kept story.
    # If similar: keep the one with higher credibility; on tie, keep earlier (already kept).
    kept: list[dict] = []
    for candidate in url_deduped:
        candidate_title = candidate.get("title", "")
        candidate_cred = credibility_score(candidate.get("source_name", ""))

        displaced_idx: int | None = None
        similar_found = False

        for idx, existing in enumerate(kept):
            existing_title = existing.get("title", "")
            ratio = difflib.SequenceMatcher(
                None, candidate_title.lower(), existing_title.lower()
            ).ratio()
            if ratio >= 0.85:
                similar_found = True
                existing_cred = credibility_score(existing.get("source_name", ""))
                # Candidate wins if strictly more credible
                if candidate_cred > existing_cred:
                    displaced_idx = idx
                # Otherwise keep existing (tie or candidate less credible)
                break

        if not similar_found:
            kept.append(candidate)
        elif displaced_idx is not None:
            # Replace the less-credible existing entry with the candidate
            kept[displaced_idx] = candidate

    return kept


# ---------------------------------------------------------------------------
# Top story selection (CONT-06, CONT-07)
# ---------------------------------------------------------------------------

def select_top_story(stories: list[dict], threshold: float) -> dict | None:
    """CONT-06/07: Return single highest-scoring story above threshold, or None.

    Args:
        stories: List of story dicts, each with a 'score' key (float).
        threshold: Minimum score to qualify (exclusive: must be > threshold to pass,
                   but spec says "above threshold" which means strictly > threshold).

    Returns:
        The story with the highest score that is strictly above threshold, or None if
        no stories meet the bar ("no story today" flag).
    """
    qualifying = [s for s in stories if s.get("score", 0) > threshold]
    if not qualifying:
        return None
    return max(qualifying, key=lambda s: s.get("score", 0))


# ---------------------------------------------------------------------------
# Compliance checker — fail-safe pattern (CONT-14, CONT-15, CONT-16)
# ---------------------------------------------------------------------------

async def check_compliance(text: str, anthropic_client=None) -> bool:
    """Check content for compliance. Returns True only on explicit 'pass'.
    Fail-safe: ambiguous response = block (returns False).
    Pre-screens locally for 'seva mining' before calling Claude Haiku.

    Args:
        text: Draft text to check for compliance.
        anthropic_client: Optional AsyncAnthropic instance; created from settings if None.

    Returns:
        True only if Claude responds with exactly 'pass'. False otherwise (fail-safe).
    """
    text_lower = text.lower()
    # Local pre-screen — no LLM cost for obvious blocks
    if "seva mining" in text_lower:
        return False

    if anthropic_client is None:
        settings = get_settings()
        anthropic_client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    try:
        response = await anthropic_client.messages.create(
            model="claude-haiku-3-20240307",
            max_tokens=50,
            system="You are a compliance checker. Evaluate the following content. Reply with exactly 'pass' if the content does NOT mention Seva Mining and does NOT contain financial advice (recommendations to buy, sell, invest, or any action-oriented investment guidance). Reply with 'fail: [reason]' otherwise.",
            messages=[{"role": "user", "content": text}],
        )
        result = response.content[0].text.strip().lower()
        # Fail-safe: only explicit 'pass' returns True
        return result == "pass"
    except Exception as exc:
        logger.warning("Compliance check failed with error: %s — blocking by default", exc)
        return False


# ---------------------------------------------------------------------------
# RSS and SerpAPI parsing helpers (CONT-02, CONT-03) — stubs for Plan 03
# ---------------------------------------------------------------------------

def parse_rss_entries(feed_url: str, source_name: str) -> list[dict]:
    """CONT-02: Parse an RSS feed and return normalized story dicts.

    Each dict has: title, link, published (datetime), summary, source_name.
    Implemented in Plan 03 (ingestion wave).
    """
    # Stub — full implementation in Plan 03
    return []


def parse_serpapi_results(results: list[dict], source_name: str = "serpapi") -> list[dict]:
    """CONT-03: Parse SerpAPI news results into normalized story dicts.

    Each dict has: title, link, source_name, snippet, published (datetime).
    Implemented in Plan 03 (ingestion wave).
    """
    # Stub — full implementation in Plan 03
    return []


# ---------------------------------------------------------------------------
# ContentAgent class skeleton (CONT-01)
# ---------------------------------------------------------------------------

class ContentAgent:
    """Content Agent — RSS + SerpAPI ingestion, scoring, dedup, draft pipeline.

    Requirements: CONT-01 through CONT-17
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.anthropic = AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def run(self) -> None:
        """Entry point called by APScheduler. Full pipeline implemented in Plan 05."""
        # Full pipeline — implemented in Plan 05
        pass
