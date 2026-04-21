"""
Content Agent — ingest, deduplicate, score, and select daily gold sector stories.

Monitors RSS feeds (Kitco, Mining.com, JMN, WGC, Reuters, Bloomberg (commodities),
GoldSeek) and SerpAPI news search every ~6 hours for qualifying stories.
Applies scoring (relevance, recency, credibility), deduplication (URL + headline
similarity), cross-run deduplication, and selects ALL stories above the 7.0/10
quality threshold for multi-story output.

Requirements: CONT-01 through CONT-17
"""
from __future__ import annotations

import asyncio
import difflib
import json
import logging
from datetime import date, datetime, timezone

import feedparser
import httpx
import serpapi
import tweepy.asynchronous
from anthropic import AsyncAnthropic
from bs4 import BeautifulSoup
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.brand_preamble import BRAND_PREAMBLE
from config import get_settings
from database import AsyncSessionLocal
from models.agent_run import AgentRun
from models.config import Config

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# RSS feed list — module-level constant (CONT-02)
# ---------------------------------------------------------------------------

RSS_FEEDS = [
    ("https://www.kitco.com/rss/news.xml", "kitco.com"),
    ("https://www.mining.com/feed/", "mining.com"),
    ("https://www.juniorminingnetwork.com/feed", "juniorminingnetwork.com"),
    ("https://www.gold.org/goldhub/news/feed", "gold.org"),
    ("https://feeds.reuters.com/reuters/businessNews", "reuters.com"),
    ("https://feeds.bloomberg.com/commodities/news.rss", "bloomberg.com"),
    ("https://goldseek.com/feed/", "goldseek.com"),
]

# ---------------------------------------------------------------------------
# SerpAPI keyword list — module-level constant (CONT-03)
# ---------------------------------------------------------------------------

SERPAPI_KEYWORDS = [
    "gold exploration",
    "gold price",
    "central bank gold",
    "gold ETF",
    "junior miners",
    "gold reserves",
    "gold inflation hedge",
    "Fed gold",
    "dollar gold",
    "recession gold",
]

# ---------------------------------------------------------------------------
# Twitter video clip and quote account lists (CONT-09, CONT-13)
# ---------------------------------------------------------------------------

VIDEO_ACCOUNTS = [
    "Kitco",
    "CNBC",
    "Bloomberg",
    "BarrickGold",
    "WorldGoldCouncil",
    "Mining",
    "Newaborngold",
]

QUOTE_ACCOUNTS = [
    "PeterSchiff",
    "jimrickards",
    "JimRickards",
    "RealJimRogers",
    "RobertKiyosaki",
]

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
    "goldseek.com": 0.6,
    "investing.com": 0.6,
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

    Kept for backward compatibility — prefer select_qualifying_stories() for
    multi-story output.

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


def _is_within_window(
    published,
    window_hours: float,
    now: "datetime | None" = None,
) -> bool:
    """Return True if published is within window_hours of now.

    Accepts datetime objects (as stored by RSS/SerpAPI ingest) or ISO strings.
    Mirrors recency_score() timezone handling.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    if isinstance(published, str):
        try:
            published = datetime.fromisoformat(published.replace("Z", "+00:00"))
        except ValueError:
            return False
    if published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)
    age_hours = (now - published).total_seconds() / 3600
    return age_hours <= window_hours


async def classify_format_lightweight(story: dict, *, client) -> str:
    """Lightweight Haiku format classifier for slice-priority decision.

    Uses claude-3-5-haiku-latest (cheap) — full Sonnet format+draft call happens
    later only for the top-N selected stories.

    Returns one of: breaking_news | thread | long_form | infographic | quote.
    Fail-open: returns "thread" (current ambiguous default) on any error or
    unexpected output.
    """
    valid_formats = {"breaking_news", "thread", "long_form", "infographic", "quote"}
    try:
        response = await client.messages.create(
            model="claude-3-5-haiku-latest",
            max_tokens=20,
            system="You are a content format classifier. Reply with one word.",
            messages=[{
                "role": "user",
                "content": (
                    f"Title: {story['title']}\n"
                    f"Summary: {story.get('summary', '')[:500]}\n"
                    f"Published: {story.get('published', '')}\n\n"
                    "Which content format best fits? Choose exactly one: "
                    "breaking_news | thread | long_form | infographic | quote. "
                    "Reply with ONLY the format name."
                ),
            }],
        )
        result = response.content[0].text.strip().lower()
        if result in valid_formats:
            return result
        logger.warning(
            "classify_format_lightweight returned unexpected value '%s' — defaulting to 'thread'",
            result,
        )
        return "thread"
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "classify_format_lightweight failed (%s) — defaulting to 'thread'",
            type(exc).__name__,
        )
        return "thread"


def select_qualifying_stories(
    stories: list[dict],
    threshold: float,
    *,
    max_count: int | None = None,
    breaking_window_hours: float | None = None,
    now: datetime | None = None,
) -> list[dict]:
    """Return stories scoring above threshold, optionally capped at max_count.

    When max_count is None: returns ALL qualifying sorted by score desc (unchanged).
    When max_count is set: breaking_news format and fresh stories (within
    breaking_window_hours) are prioritized — they fill the front of the slice
    regardless of score; remaining slots go to highest-score regular stories.

    Args:
        stories: List of story dicts, each with a 'score' key (float).
                 Format-classified stories have 'predicted_format' set.
        threshold: Minimum score (strictly >).
        max_count: Maximum stories to return. None = no cap (backward compat).
        breaking_window_hours: Stories published within this window are treated
                               as priority. None = no recency-based priority.
        now: Reference time for recency check. Defaults to datetime.now(UTC).
             Inject in tests for determinism.

    Returns:
        Qualifying stories, priority-first, sorted by score desc within each tier.
        At most max_count if set.
    """
    qualifying = [s for s in stories if s.get("score", 0) > threshold]
    if not qualifying:
        return []

    if max_count is None:
        qualifying.sort(key=lambda s: s.get("score", 0), reverse=True)
        return qualifying

    # Priority split: breaking_news format OR within recency window
    _now = now or datetime.now(timezone.utc)

    def _is_priority(s: dict) -> bool:
        if s.get("predicted_format") == "breaking_news":
            return True
        if breaking_window_hours is not None:
            return _is_within_window(s.get("published"), breaking_window_hours, _now)
        return False

    priority = [s for s in qualifying if _is_priority(s)]
    regular = [s for s in qualifying if not _is_priority(s)]

    priority.sort(key=lambda s: s.get("score", 0), reverse=True)
    regular.sort(key=lambda s: s.get("score", 0), reverse=True)

    combined = priority + regular
    return combined[:max_count]


# ---------------------------------------------------------------------------
# Article fetch + BeautifulSoup extraction (CONT-08)
# ---------------------------------------------------------------------------

def extract_article_text(html: str) -> str:
    """Extract main article text from HTML, stripping boilerplate.

    Strips nav/header/footer/aside/script/style tags, then tries semantic
    content selectors in priority order. Falls back to full body text.
    """
    soup = BeautifulSoup(html, "html.parser")
    # Strip boilerplate tags
    for tag in soup.find_all(["nav", "header", "footer", "aside", "script", "style"]):
        tag.decompose()
    # Try semantic main content tags in priority order
    for selector in ["article", "main", "[role='main']", "div.content", "div.article-body"]:
        node = soup.select_one(selector)
        if node:
            return node.get_text(separator=" ", strip=True)
    # Fallback: full body text
    return soup.get_text(separator=" ", strip=True)


async def fetch_article(url: str, fallback_text: str = "") -> tuple[str, bool]:
    """Fetch full article text via httpx. Returns (text, success_flag).

    Falls back to fallback_text on any HTTP error, timeout, non-200 status,
    or if extracted text is < 100 chars (likely paywall/JS-rendered).
    """
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0 SevaBot/1.0"})
            if resp.status_code != 200:
                logger.warning("Article fetch %s returned %d, using fallback", url, resp.status_code)
                return fallback_text, False
            text = extract_article_text(resp.text)
            if len(text) < 100:  # Too short = likely paywall/JS-rendered
                logger.warning("Article fetch %s extracted <100 chars, using fallback", url)
                return fallback_text, False
            return text, True
    except (httpx.HTTPError, httpx.TimeoutException, Exception) as exc:
        logger.warning("Article fetch %s failed: %s, using fallback", url, exc)
        return fallback_text, False


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
            model="claude-sonnet-4-6",
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


async def is_gold_relevant_or_systemic_shock(
    story: dict,
    config: dict,
    client: "AsyncAnthropic | None" = None,
) -> dict:
    """Two-bucket gold relevance gate (Haiku). Returns structured decision dict.

    Bucket A: Directly about gold/precious metals/gold mining macro/sector → keep.
    Bucket B: Systemic financial/geopolitical shock plausibly moving gold → keep.
    Bucket C: Primary subject is a specific gold/mining company → reject (nnh rule).
    Everything else (off-topic, listicles, stock picks) → reject.

    Return shape:
        {"keep": bool, "reject_reason": str | None, "company": str | None}
        - Keep:          {"keep": True, "reject_reason": None, "company": None}
        - Not gold:      {"keep": False, "reject_reason": "not_gold_relevant", "company": None}
        - Specific miner: {"keep": False, "reject_reason": "primary_subject_is_specific_miner",
                           "company": "<name>"}

    Fail-open: API errors or malformed JSON return {"keep": True, ...} so infra
    blips never silence real gold stories.
    Bypassed when config key content_gold_gate_enabled is False.

    Requirements: NNH-01, NNH-02, NNH-03, NNH-04, NNH-05.

    Args:
        story: Story dict with 'title' and 'summary' keys.
        config: Dict of config key→value strings (content_gold_gate_enabled,
                content_gold_gate_model).
        client: Optional AsyncAnthropic instance. If None, creates one.

    Returns:
        dict with keys: keep (bool), reject_reason (str|None), company (str|None).
    """
    _KEEP = {"keep": True, "reject_reason": None, "company": None}

    # Bypass when gate is disabled
    enabled_str = config.get("content_gold_gate_enabled", "true")
    if str(enabled_str).lower() in ("false", "0", "no"):
        return _KEEP

    title = story.get("title", "")
    summary = story.get("summary", "")
    model = config.get("content_gold_gate_model", "claude-3-5-haiku-latest")

    anthropic_client = client or AsyncAnthropic()
    try:
        response = await anthropic_client.messages.create(
            model=model,
            max_tokens=100,
            system=(
                "You are a content filter for a gold-sector social media account. "
                "Evaluate whether this news story should be kept (drafted into content) "
                "or rejected, based on the rules below.\n\n"
                "KEEP (is_gold_relevant=true) if the story is:\n"
                "- Macro/sector gold or precious metals news: gold price moves, "
                "central bank buying, gold supply/demand, gold ETF flows, miners-index moves.\n"
                "- A systemic financial/geopolitical shock plausibly moving gold prices "
                "(major war, sanctions, Strait of Hormuz disruption, Fed/USD policy shock, "
                "oil supply shock, currency crisis, rare-earth restrictions).\n"
                "- A story that CITES a financial institution (Goldman Sachs, BlackRock, "
                "JPMorgan, Morgan Stanley, World Gold Council, IMF, Federal Reserve, "
                "central banks) as a SOURCE providing a forecast, data, or analysis — "
                "these are sources, not subjects. Their presence does NOT trigger rejection.\n\n"
                "REJECT — primary_subject_is_specific_miner "
                "(is_gold_relevant=true but primary_subject_is_specific_miner=true) if the story "
                "is primarily about a single gold/mining company's own news: drilling results, "
                "production updates, earnings/guidance, M&A where a specific miner is buyer or "
                "target, executive changes, project milestones, financing/raises, resource "
                "estimates. This applies even if gold price is mentioned incidentally.\n"
                "Examples of REJECT (specific miner): "
                "'B2Gold expects lower Q2 output from Goose mine' (B2Gold), "
                "'McLaren Completes Drone MAG Program at Blue Quartz Gold Property' (McLaren), "
                "'Barrick acquires Kinross in $8B deal' (Barrick+Kinross), "
                "'Newmont posts record Q2, raises guidance' (Newmont), "
                "'Seva Mining hits 12g/t gold at Timmins drill hole 42' (Seva Mining).\n\n"
                "REJECT — not_gold_relevant "
                "(is_gold_relevant=false) for:\n"
                "- Listicles or rankings of gold stocks "
                "('Top 5 Gold Stocks', '7 Best-Performing Gold Stocks For...', "
                "'Best Gold Stocks to Buy Now', 'Gold Stocks to Watch').\n"
                "- Multi-stock analytical picks roundups or recommendation lists.\n"
                "- Generic buying advice or educational content about gold investing.\n"
                "- Unrelated business/financial news with no gold/metals/systemic-shock angle.\n\n"
                "Examples of KEEP (macro/sector/source): "
                "'Gold hits record $3,200 as Goldman forecasts $4K by year-end' (Goldman is a source), "
                "'Central banks added 800t of gold in Q1, says World Gold Council' (WGC is a source), "
                "'Gold miners index hits new high' (sector-wide), "
                "'ETF flows into gold miners surge' (sector flow), "
                "'US CPI at 2.1%; gold rallies on Fed cut odds' (macro), "
                "'China imposes new rare-earth export restrictions' (geopolitics/systemic shock).\n\n"
                "Respond with ONLY a compact JSON object, no other text:\n"
                '{"is_gold_relevant": true|false, '
                '"primary_subject_is_specific_miner": true|false, '
                '"company": null|"<company name if primary_subject_is_specific_miner is true>"}'
            ),
            messages=[{"role": "user", "content": f"Title: {title}\nSummary: {summary}"}],
        )
        raw = response.content[0].text.strip()
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            logger.warning(
                "Gold gate returned non-JSON for '%s' — fail-open (keeping story): %r",
                title[:50], raw[:80],
            )
            return _KEEP

        # Sanitize parsed fields
        is_gold = bool(parsed.get("is_gold_relevant", True))
        is_specific_miner = bool(parsed.get("primary_subject_is_specific_miner", False))
        company_raw = parsed.get("company")
        company = str(company_raw).strip() if company_raw else None
        if not company:
            company = None

        if not is_gold:
            return {"keep": False, "reject_reason": "not_gold_relevant", "company": None}
        if is_specific_miner:
            return {
                "keep": False,
                "reject_reason": "primary_subject_is_specific_miner",
                "company": company,
            }
        return _KEEP

    except Exception as exc:  # noqa: BLE001 — fail-open on infra blip
        logger.warning(
            "Gold gate API failed for '%s' (%s) — fail-open (keeping story)",
            title[:50], type(exc).__name__,
        )
        return _KEEP


# ---------------------------------------------------------------------------
# No-story flag and ContentBundle builder (CONT-07)
# ---------------------------------------------------------------------------

def build_no_story_bundle(best_score: float):
    """Create a ContentBundle with no_story_flag=True for days with no qualifying story.

    Args:
        best_score: Score of the best candidate story that failed threshold.

    Returns:
        ContentBundle with no_story_flag=True and all draft fields as None.
    """
    from models.content_bundle import ContentBundle  # noqa: PLC0415
    return ContentBundle(
        story_headline="No qualifying story today",
        no_story_flag=True,
        score=best_score,
        # All other fields left as None
    )


# ---------------------------------------------------------------------------
# DraftItem builder for Senior Agent integration (CONT-17)
# ---------------------------------------------------------------------------

def build_draft_item(content_bundle, rationale: str):
    """Create a DraftItem from a ContentBundle for Senior Agent queue.
    platform='content', urgency='low', expires_at=None (evergreen content).
    Stores content_bundle.id in engagement_snapshot for Phase 8 linking.

    Args:
        content_bundle: ContentBundle instance to build DraftItem from.
        rationale: Format decision rationale string.

    Returns:
        DraftItem ready to be persisted to the database.
    """
    from models.draft_item import DraftItem  # noqa: PLC0415

    # Extract actual copyable draft text for the alternatives field.
    # The frontend reads alternatives[0].text and copies it to clipboard on Approve —
    # so this must be real post/tweet content, NOT a description string.

    draft = content_bundle.draft_content or {}
    fmt = draft.get("format", "unknown")

    if fmt == "breaking_news":
        # Primary copyable text: the tweet. Append infographic brief as a note if present.
        tweet_text = draft.get("tweet", "")
        infographic_brief = draft.get("infographic_brief")
        if infographic_brief and isinstance(infographic_brief, dict):
            brief_note = (
                f"\n\n---\nInfographic: {infographic_brief.get('headline', '')}\n"
                + "\n".join(f"• {p}" for p in infographic_brief.get("data_points", []))
            )
            draft_text = tweet_text + brief_note if tweet_text else brief_note
        else:
            draft_text = tweet_text

    elif fmt == "thread":
        # Join individual tweets with blank lines so the reviewer can copy the full thread.
        tweets = draft.get("tweets", [])
        if isinstance(tweets, list):
            draft_text = "\n\n".join(str(t) for t in tweets if t)
        else:
            draft_text = str(tweets)

    elif fmt == "long_form":
        draft_text = draft.get("post", "")

    elif fmt == "infographic":
        # Infographic: use twitter_caption as primary copyable text.
        # Fall back to first chart title if caption is missing.
        caption = draft.get("twitter_caption", "")
        if not caption:
            charts = draft.get("charts", [])
            if charts and isinstance(charts[0], dict):
                caption = charts[0].get("title", "")
        draft_text = caption

    elif fmt == "gold_history":
        # Combine thread tweets and/or Instagram carousel as multi-part draft.
        tweets = draft.get("tweets", [])
        carousel = draft.get("instagram_carousel", [])
        parts = []
        if tweets:
            parts.append("=== Thread ===\n" + "\n\n".join(str(t) for t in tweets if t))
        if carousel:
            parts.append("=== Instagram Carousel ===\n" + "\n\n".join(
                f"Slide {i+1}: {slide}" if isinstance(slide, str) else f"Slide {i+1}: {slide.get('text', '')}"
                for i, slide in enumerate(carousel)
            ))
        draft_text = "\n\n".join(parts) if parts else f"Gold History: {draft.get('story_title', '')}"

    elif fmt == "video_clip":
        # Draft stores twitter_caption and instagram_caption — use twitter version as primary.
        draft_text = (
            draft.get("twitter_caption", "")
            or draft.get("instagram_caption", "")
            or f"Video clip from @{draft.get('source_account', 'unknown')}"
        )

    elif fmt == "quote":
        # Draft stores twitter_post and instagram_post — use the formatted twitter post.
        draft_text = (
            draft.get("twitter_post", "")
            or draft.get("instagram_post", "")
            or f'"{draft.get("quote_text", "")}" — {draft.get("speaker", "")}'
        )

    else:
        # Unknown format — store whatever text fields exist, or a minimal fallback.
        draft_text = (
            draft.get("text", "")
            or draft.get("tweet", "")
            or draft.get("post", "")
            or f"Content draft ({fmt})"
        )

    return DraftItem(
        platform="content",
        source_text=content_bundle.story_headline,
        source_url=content_bundle.story_url,
        source_account=content_bundle.source_name,
        alternatives=[{"type": fmt, "text": draft_text}],
        rationale=rationale,
        score=float(content_bundle.score or content_bundle.quality_score or 0.0),
        expires_at=None,
        urgency="low",
        engagement_snapshot={"content_bundle_id": str(content_bundle.id)},
    )


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
# Draft text extractor for compliance checking
# ---------------------------------------------------------------------------

def _extract_check_text(draft_content: dict) -> str:
    """Extract all text from draft_content for compliance checking."""
    fmt = draft_content.get("format", "")
    parts = []
    if fmt == "breaking_news":
        parts.append(draft_content.get("tweet", ""))
        brief = draft_content.get("infographic_brief")
        if brief and isinstance(brief, dict):
            parts.append(brief.get("headline", ""))
            parts.append(brief.get("caption", ""))
    elif fmt == "thread":
        parts.extend(draft_content.get("tweets", []))
        parts.append(draft_content.get("long_form_post", ""))
    elif fmt == "long_form":
        parts.append(draft_content.get("post", ""))
    elif fmt == "infographic":
        parts.append(draft_content.get("twitter_caption", ""))
        parts.append(draft_content.get("suggested_headline", ""))
        parts.extend(draft_content.get("data_facts", []) or [])
        # Do NOT compliance-check image_prompt — it's brand preamble + derived text, not novel content
    elif fmt == "gold_history":
        parts.extend(draft_content.get("tweets", []))
        for slide in draft_content.get("instagram_carousel", []):
            if isinstance(slide, dict):
                parts.append(slide.get("headline", ""))
                parts.append(slide.get("body", ""))
        parts.append(draft_content.get("instagram_caption", ""))
    elif fmt == "video_clip":
        parts.append(draft_content.get("twitter_caption", ""))
        parts.append(draft_content.get("instagram_caption", ""))
    elif fmt == "quote":
        parts.append(draft_content.get("twitter_post", ""))
        parts.append(draft_content.get("quote_text", ""))
        parts.append(draft_content.get("suggested_headline", ""))
        parts.extend(draft_content.get("data_facts", []) or [])
        # Do NOT compliance-check image_prompt — it's brand preamble + derived text, not novel content
    return " ".join(p for p in parts if p)


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
        self.serpapi_client = (
            serpapi.Client(api_key=settings.serpapi_api_key)
            if settings.serpapi_api_key
            else None
        )
        self.tweepy_client = tweepy.asynchronous.AsyncClient(
            bearer_token=settings.x_api_bearer_token,
            wait_on_rate_limit=True,
        )
        self._queued_titles: list[str] = []
        self._skipped_short_longform: int = 0

    async def _search_corroborating(self, headline: str) -> list[dict]:
        """CONT-09: Find 2-3 corroborating sources via SerpAPI Google News.

        Runs synchronous serpapi call in executor to avoid blocking the event loop.

        Returns:
            List of dicts with keys: title, url, source, snippet.
        """
        loop = asyncio.get_event_loop()
        try:
            def _call():
                return self.serpapi_client.search({
                    "engine": "google_news",
                    "q": headline,
                    "num": 3,
                })
            results = await loop.run_in_executor(None, _call)
            sources = []
            for item in results.get("news_results", [])[:3]:
                sources.append({
                    "title": item.get("title", ""),
                    "url": item.get("link", ""),
                    "source": (item.get("source") or {}).get("name", "unknown"),
                    "snippet": item.get("snippet", ""),
                })
            return sources
        except Exception as exc:
            logger.warning("Corroboration search failed: %s", exc)
            return []

    async def _search_video_clips(self, session: AsyncSession) -> list[dict]:
        """Search Twitter for gold sector video posts from credible accounts.

        Uses has:videos operator to find only tweets with video attachments.
        Filters to only keep tweets where at least one media attachment is type='video'.
        Respects monthly quota — returns empty list if quota is near cap.

        Returns:
            List of dicts with keys: tweet_id, text, author_username, author_name,
            tweet_url, public_metrics, created_at.
        """
        # Quota check — within 500 of 10,000 cap → skip
        current_count_str = await self._get_config(session, "twitter_monthly_tweet_count", "0")
        quota_limit_str = await self._get_config(session, "twitter_monthly_quota_limit", "10000")
        current_count = int(current_count_str)
        quota_limit = int(quota_limit_str)
        if quota_limit - current_count < 500:
            logger.info(
                "Twitter quota near cap (%d/%d) — skipping video clip search",
                current_count, quota_limit,
            )
            return []

        # Build query using first 5 VIDEO_ACCOUNTS (API query length limits)
        accounts_clause = " OR ".join(f"from:{acct}" for acct in VIDEO_ACCOUNTS[:5])
        query = f"({accounts_clause}) has:videos gold -is:retweet"

        try:
            response = await self.tweepy_client.search_recent_tweets(
                query=query,
                max_results=10,
                tweet_fields=["created_at", "public_metrics", "author_id", "text", "attachments"],
                expansions=["author_id", "attachments.media_keys"],
                user_fields=["username", "public_metrics"],
                media_fields=["type", "duration_ms", "preview_image_url"],
            )

            if not response.data:
                return []

            # Build lookup maps
            users_data = (response.includes or {}).get("users") or []
            media_data = (response.includes or {}).get("media") or []
            user_map = {str(u.id): u for u in users_data}
            media_map = {m.media_key: m for m in media_data} if media_data else {}

            results = []
            for tweet in response.data:
                # Only keep tweets with at least one video attachment
                attachment_keys = (tweet.attachments or {}).get("media_keys", []) if tweet.attachments else []
                has_video = any(
                    media_map.get(k) and media_map[k].type == "video"
                    for k in attachment_keys
                )
                if not has_video:
                    continue

                user = user_map.get(str(tweet.author_id))
                username = user.username if user else "unknown"
                author_name = user.name if user else "unknown"
                tweet_url = f"https://twitter.com/{username}/status/{tweet.id}"

                results.append({
                    "tweet_id": str(tweet.id),
                    "text": tweet.text,
                    "author_username": username,
                    "author_name": author_name,
                    "tweet_url": tweet_url,
                    "public_metrics": tweet.public_metrics or {},
                    "created_at": tweet.created_at,
                })

            # Increment quota by number of tweets returned by API (not filtered)
            total_returned = len(response.data)
            new_count = current_count + total_returned
            await self._set_config_str(session, "twitter_monthly_tweet_count", str(new_count))

            logger.info(
                "Video clip search returned %d tweets (%d passed video filter)",
                total_returned, len(results),
            )
            return results

        except Exception as exc:
            logger.warning("Video clip Twitter search failed: %s", exc)
            return []

    async def _search_quote_tweets(self, session: AsyncSession) -> list[dict]:
        """Search Twitter for gold sector text quote posts from credible figures.

        Uses -has:media operator to find text-only tweets (no media attachments).
        Filters to minimum 10 likes (low bar for curated accounts).
        Respects monthly quota — returns empty list if quota is near cap.

        Returns:
            List of dicts with keys: tweet_id, text, author_username, author_name,
            tweet_url, public_metrics, created_at.
        """
        # Quota check — within 500 of 10,000 cap → skip
        current_count_str = await self._get_config(session, "twitter_monthly_tweet_count", "0")
        quota_limit_str = await self._get_config(session, "twitter_monthly_quota_limit", "10000")
        current_count = int(current_count_str)
        quota_limit = int(quota_limit_str)
        if quota_limit - current_count < 500:
            logger.info(
                "Twitter quota near cap (%d/%d) — skipping quote tweet search",
                current_count, quota_limit,
            )
            return []

        # Build query using QUOTE_ACCOUNTS
        accounts_clause = " OR ".join(f"from:{acct}" for acct in QUOTE_ACCOUNTS)
        query = f"({accounts_clause}) gold -has:media -is:retweet"

        try:
            response = await self.tweepy_client.search_recent_tweets(
                query=query,
                max_results=10,
                tweet_fields=["created_at", "public_metrics", "author_id", "text"],
                expansions=["author_id"],
                user_fields=["username", "public_metrics"],
            )

            if not response.data:
                return []

            # Build user map
            users_data = (response.includes or {}).get("users") or []
            user_map = {str(u.id): u for u in users_data}

            results = []
            for tweet in response.data:
                # Filter: minimum 10 likes
                metrics = tweet.public_metrics or {}
                if metrics.get("like_count", 0) < 10:
                    continue

                user = user_map.get(str(tweet.author_id))
                username = user.username if user else "unknown"
                author_name = user.name if user else "unknown"
                tweet_url = f"https://twitter.com/{username}/status/{tweet.id}"

                results.append({
                    "tweet_id": str(tweet.id),
                    "text": tweet.text,
                    "author_username": username,
                    "author_name": author_name,
                    "tweet_url": tweet_url,
                    "public_metrics": metrics,
                    "created_at": tweet.created_at,
                })

            # Increment quota by number of tweets returned by API (not filtered)
            total_returned = len(response.data)
            new_count = current_count + total_returned
            await self._set_config_str(session, "twitter_monthly_tweet_count", str(new_count))

            logger.info(
                "Quote tweet search returned %d tweets (%d passed like filter)",
                total_returned, len(results),
            )
            return results

        except Exception as exc:
            logger.warning("Quote tweet Twitter search failed: %s", exc)
            return []

    async def _set_config_str(self, session: AsyncSession, key: str, value: str) -> None:
        """Upsert a config key with a string value."""
        result = await session.execute(select(Config).where(Config.key == key))
        row = result.scalar_one_or_none()
        if row is None:
            session.add(Config(key=key, value=value))
        else:
            row.value = value

    async def _draft_video_caption(
        self,
        tweet_text: str,
        author_username: str,
        author_name: str,
        tweet_url: str,
    ) -> dict | None:
        """Draft a quote-tweet style caption for a video clip from a credible account.

        Calls Claude Sonnet with senior analyst voice. Produces dual-platform output:
        a short caption for Twitter quote-tweet and an Instagram-adapted version.

        Args:
            tweet_text: Original tweet text accompanying the video.
            author_username: Twitter handle of the account that posted the video.
            author_name: Display name of the account.
            tweet_url: Direct URL to the tweet.

        Returns:
            draft_content dict with format=video_clip, twitter_caption, instagram_caption.
            Returns None on JSON parse failure.
        """
        system_prompt = (
            "You are a senior gold market analyst. You write quote-tweet style captions "
            "for video clips from gold sector figures. Write 1-3 sentences: who said it, "
            "what the key claim is, why it matters to gold investors. Lead with the data "
            "or the insight — not preamble. Also provide an Instagram-adapted version "
            "(same content, slightly more context for a less technical audience). "
            "You never mention Seva Mining. You never give financial advice."
        )
        user_prompt = f"""Write a caption for this video clip from @{author_username} ({author_name}).

Tweet text: {tweet_text}
Video URL: {tweet_url}

Respond in valid JSON:
{{
  "twitter_caption": "1-3 sentences for X quote-tweet (data-forward, senior analyst voice)",
  "instagram_caption": "same content adapted for Instagram (slightly more context)"
}}"""

        try:
            response = await self.anthropic.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=512,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            raw = response.content[0].text.strip()
            if raw.startswith("```"):
                raw = raw.split("```", 2)[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.rsplit("```", 1)[0].strip()
            parsed = json.loads(raw)
        except Exception as exc:
            logger.warning("_draft_video_caption JSON parse failed: %s", exc)
            return None

        return {
            "format": "video_clip",
            "source_account": author_username,
            "tweet_url": tweet_url,
            "twitter_caption": parsed.get("twitter_caption", ""),
            "instagram_caption": parsed.get("instagram_caption", ""),
        }

    async def _draft_quote_post(
        self,
        quote_text: str,
        speaker: str,
        speaker_title: str,
        source_url: str,
    ) -> dict | None:
        """Draft a pull-quote post for X and Instagram from a notable gold sector figure.

        Calls Claude Sonnet with senior analyst voice. Formats quote with attribution
        and 1-2 lines of analyst context. Produces dual-platform output.

        Args:
            quote_text: The tweet/quote text from the speaker.
            speaker: Speaker's display name.
            speaker_title: Speaker's title or credentials.
            source_url: URL to the original tweet.

        Returns:
            draft_content dict with format=quote, speaker, speaker_title, quote_text,
            source_url, twitter_post, instagram_post.
            Returns None on JSON parse failure.
        """
        system_prompt = (
            "You are a senior gold market analyst. You draft pull-quote posts about "
            "notable statements from gold sector figures. Format: quote in quotation "
            "marks, attribution line, then 1-2 lines of analyst context explaining why "
            "this matters for the gold market. Lead with the quote. "
            "You never mention Seva Mining. You never give financial advice."
        )
        user_prompt = f"""Draft a pull-quote post for this statement from {speaker} ({speaker_title}).

Quote: {quote_text}
Source URL: {source_url}

Respond in valid JSON:
{{
  "twitter_post": "full formatted quote post for X (quote + attribution + 1-2 lines analyst context)",
  "suggested_headline": "short editorial title for the visual artifact, ideally <=60 chars",
  "data_facts": ["1-5 key facts or data points that contextualize this quote — each <=120 chars"],
  "image_prompt_direction": "2-4 sentences describing what the pull-quote card should look like: how to present the quote as hero element, attribution placement, any context stats to feature. Focus on STORY-SPECIFIC visual direction only — brand palette and dimensions are applied automatically."
}}"""

        try:
            response = await self.anthropic.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=512,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            raw = response.content[0].text.strip()
            if raw.startswith("```"):
                raw = raw.split("```", 2)[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.rsplit("```", 1)[0].strip()
            parsed = json.loads(raw)
        except Exception as exc:
            logger.warning("_draft_quote_post JSON parse failed: %s", exc)
            return None

        # Build image_prompt for quote (mfy pivot — operator pastes into claude.ai)
        direction = parsed.pop("image_prompt_direction", "").strip()
        facts = parsed.get("data_facts") or []
        if not isinstance(facts, list):
            facts = []
        parsed["data_facts"] = facts[:5]
        headline = parsed.get("suggested_headline", "")
        facts_block = "\n".join(f"- {f}" for f in parsed["data_facts"])
        parsed["image_prompt"] = (
            f"{BRAND_PREAMBLE}\n\n"
            f"ARTIFACT TYPE: pull-quote card (NOT a chart — center the quote itself as the hero element).\n\n"
            f"HEADLINE FOR THIS VISUAL:\n{headline}\n\n"
            f"KEY FACTS TO FEATURE:\n{facts_block}\n\n"
            f"STORY-SPECIFIC DIRECTION:\n{direction}"
        )

        return {
            "format": "quote",
            "speaker": speaker,
            "speaker_title": speaker_title,
            "quote_text": quote_text,
            "source_url": source_url,
            "twitter_post": parsed.get("twitter_post", ""),
            "suggested_headline": parsed.get("suggested_headline", ""),
            "data_facts": parsed.get("data_facts", []),
            "image_prompt": parsed.get("image_prompt", ""),
        }

    async def _research_and_draft(
        self, story: dict, deep_research: dict
    ) -> tuple[dict, dict, str] | None:
        """CONT-10/11/12/13: Combined Claude Sonnet call for format decision + drafting.

        Sends the full research bundle (article text + corroborating sources + story
        metadata) to Claude Sonnet in a single API call. Claude decides the best
        format (thread/long_form/infographic) and produces the draft.

        Returns:
            (draft_content_dict, updated_deep_research_dict, rationale_string)
            or None on JSON parse failure.
        """
        article_text = deep_research.get("article_text", "")
        corroborating = deep_research.get("corroborating_sources", [])

        # Build corroborating sources block
        if corroborating:
            corr_lines = "\n".join(
                f"- {s.get('title', '')} ({s.get('source', '')}) — {s.get('snippet', '')}"
                for s in corroborating
            )
        else:
            corr_lines = "None found."

        article_block = article_text if article_text else "Article text unavailable — use corroborating sources and headline."

        user_prompt = f"""Based on the following research, produce original content for publication on X (Twitter) and Instagram.

## Story
Headline: {story.get('title', '')}
Source: {story.get('source_name', '')} ({story.get('link', '')})

## Full Article
{article_block}

## Corroborating Sources
{corr_lines}

## Instructions
1. Extract 5-8 key data points from the research (numbers, percentages, dates, production figures).
2. Decide the best format for this content. Choose from these options:

   - "thread" — for fact-rich stories where a few data points or facts can be strung together into a narrative. Each tweet carries one fact or angle. Use when the story is a collection of data points rather than one sustained argument. Produces BOTH a tweet thread (3-5 tweets, each <=280 chars) AND a long-form X post (<=2200 chars). Default for ambiguous stories.
   - "long_form" — for article-style analysis: a single sustained piece built around one powerful argument or insight, like a short analyst op-ed. Must read like an article, not a long social post — with a clear thesis, supporting evidence, and a sharpened takeaway. Single X post 400-2200 chars. Minimum 400 chars — if you cannot write at least 400 chars of article-quality analyst prose, choose a different format instead.
   - "breaking_news" — for urgency/speed stories ("this just happened, pay attention"): major price moves, major announcements, stories where speed is the value. 1-3 punchy lines, ALL CAPS for key terms, no hashtags. Optional infographic pairing if story also has strong visual data.
   - "infographic" — for stories with clear comparison, trend, or historical parallel with >=4 stats — better visualized than narrated. Choose this when the data is the story. Produces a tweet caption PLUS three fields (suggested_headline, data_facts, image_prompt) the operator will paste into claude.ai to render the visual.
   - "quote" — when a strong text quote from a credible named figure is found in the article content. Pull-quote format: quote in quotation marks, attribution, 1-2 lines of analyst context. Produces a tweet post plus three fields (suggested_headline, data_facts, image_prompt) for the operator to render in claude.ai.
   - "video_clip" — NOT chosen here; produced by direct Twitter search of credible gold sector video accounts. Skip this option.
   - "gold_history" — NOT chosen here; produced by a separate bi-weekly Gold History job. Skip this option.

   Default (ambiguous story): "thread"

3. Draft the content in your chosen format.
4. Provide a brief rationale for your format choice (1-2 sentences).

Respond in valid JSON with this structure:
{{
  "format": "thread" | "long_form" | "breaking_news" | "infographic" | "quote",
  "rationale": "...",
  "key_data_points": ["...", "..."],
  "draft_content": {{ ... }}
}}

For "thread" format, draft_content must have:
{{"format": "thread", "tweets": ["tweet1 (<=280 chars)", "tweet2", "...up to 5"], "long_form_post": "single X post <=2200 chars"}}

For "long_form" format, draft_content must have:
{{"format": "long_form", "post": "single X post 400-2200 chars (minimum 400 required)"}}

For "breaking_news" format, draft_content must have:
{{"format": "breaking_news", "tweet": "1-3 line breaking news tweet with ALL CAPS key terms, no hashtags", "infographic_brief": null}}

For "infographic" format, draft_content must have:
{{"format": "infographic",
  "twitter_caption": "1-3 sentences for X in senior analyst voice",
  "suggested_headline": "short editorial title for the artifact, ideally <=60 chars",
  "data_facts": ["1-5 key numbers, percentages, quotes, or data points the image should feature — each <=120 chars"],
  "image_prompt_direction": "2-4 sentences telling claude.ai what kind of visual to build: which chart type (bar / line / stat-callouts / comparison-table / timeline), what the X and Y axes should be, what specific numbers/labels to use, and what the visual hierarchy should be. DO NOT restate the brand palette or layout rules — those are applied automatically. Focus on the STORY-SPECIFIC visual direction."
}}

For "quote" format, draft_content must have:
{{"format": "quote", "speaker": "Full Name", "speaker_title": "title/credentials", "quote_text": "\\"the exact quote in quotation marks\\"", "source_url": "...", "twitter_post": "quote + attribution + 1-2 lines analyst context for X",
  "suggested_headline": "short editorial title for the artifact, ideally <=60 chars",
  "data_facts": ["1-5 key facts or data points that contextualize this quote — each <=120 chars"],
  "image_prompt_direction": "2-4 sentences describing what the quote card should look like: how to present the pull-quote, attribution placement, any context stats to feature. Focus on STORY-SPECIFIC visual direction only."
}}"""

        system_prompt = (
            "You are a senior gold market analyst. Authoritative, inside-the-room perspective. "
            "Tone: Precise + punchy. Data-forward. Every sentence earns its place. "
            "Opening rule: First line is always the most impactful data point or fact. Lead with the number. "
            "Differentiation: Every draft must surface ONE non-obvious insight not in the original article — "
            "a pattern, implication, or comparison no one else made. "
            "You never mention Seva Mining. You never give financial advice. You never use "
            'phrases like "buy", "sell", "invest in", "I recommend", or "you should". '
            "When a story has clear urgency (major price moves, major announcements, breaking developments), "
            "prefer breaking_news format."
        )

        try:
            response = await self.anthropic.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4096,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            raw = response.content[0].text.strip()
            # Strip markdown code fences if present
            if raw.startswith("```"):
                raw = raw.split("```", 2)[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.rsplit("```", 1)[0].strip()
            parsed = json.loads(raw)
        except Exception as exc:
            logger.error("_research_and_draft JSON parse failed: %s", exc)
            return None

        draft_content = parsed.get("draft_content", {})
        rationale = parsed.get("rationale", "")
        key_data_points = parsed.get("key_data_points", [])

        # Long-form minimum length enforcement — thin long-form posts feel undersized on the dashboard.
        # Hard floor at 400 chars; skip the bundle if Claude produced a short one despite prompt instructions.
        if draft_content.get("format") == "long_form":
            post_text = draft_content.get("post", "")
            if len(post_text) < 400:
                logger.warning(
                    "Skipping story — long_form post below 400 char minimum (got %d): %s",
                    len(post_text),
                    story.get("title", "")[:80],
                )
                self._skipped_short_longform += 1
                return None

        # Build image_prompt for infographic format (mfy pivot — operator pastes into claude.ai).
        if draft_content.get("format") == "infographic":
            direction = draft_content.pop("image_prompt_direction", "").strip()
            # Clamp data_facts to 1-5 items
            facts = draft_content.get("data_facts") or []
            if not isinstance(facts, list):
                facts = []
            draft_content["data_facts"] = facts[:5]
            # Build final paste-ready prompt
            headline = draft_content.get("suggested_headline", "")
            facts_block = "\n".join(f"- {f}" for f in draft_content["data_facts"])
            draft_content["image_prompt"] = (
                f"{BRAND_PREAMBLE}\n\n"
                f"HEADLINE FOR THIS VISUAL:\n{headline}\n\n"
                f"KEY FACTS TO FEATURE:\n{facts_block}\n\n"
                f"STORY-SPECIFIC DIRECTION:\n{direction}"
            )

        # Update deep_research with extracted key data points
        updated_research = dict(deep_research)
        updated_research["key_data_points"] = key_data_points

        return draft_content, updated_research, rationale

    async def _get_config(self, session: AsyncSession, key: str, default: str) -> str:
        """Read a config value from the DB by key. Returns default if not found."""
        result = await session.execute(select(Config).where(Config.key == key))
        row = result.scalar_one_or_none()
        return row.value if row else default

    async def _is_already_covered_today(
        self, session: AsyncSession, story_url: str, story_headline: str
    ) -> bool:
        """Check whether this story was already processed in an earlier run today.

        Queries today's ContentBundle records (no_story_flag=False) and checks for:
        - Exact URL match, or
        - Headline similarity >= 0.85 (case-insensitive)

        Returns True if the story is already covered today.
        """
        from models.content_bundle import ContentBundle  # noqa: PLC0415

        today_utc = date.today()
        result = await session.execute(
            select(ContentBundle).where(
                func.date(ContentBundle.created_at) == today_utc,
                ContentBundle.no_story_flag.is_(False),
            )
        )
        existing_bundles = result.scalars().all()

        headline_lower = story_headline.lower()
        for bundle in existing_bundles:
            # URL exact match
            if bundle.story_url and bundle.story_url == story_url:
                return True
            # Headline similarity
            if bundle.story_headline:
                ratio = difflib.SequenceMatcher(
                    None, headline_lower, bundle.story_headline.lower()
                ).ratio()
                if ratio >= 0.85:
                    return True

        return False

    async def _fetch_all_rss(self) -> list[dict]:
        """CONT-02: Fetch all RSS feeds concurrently using asyncio.gather + run_in_executor."""
        loop = asyncio.get_event_loop()
        tasks = []
        for url, source in RSS_FEEDS:
            tasks.append(loop.run_in_executor(None, feedparser.parse, url))
        feeds = await asyncio.gather(*tasks, return_exceptions=True)
        stories = []
        for (url, source), feed in zip(RSS_FEEDS, feeds):
            if isinstance(feed, Exception):
                logger.warning("RSS feed %s failed: %s", url, feed)
                continue
            for entry in feed.entries:
                published_parsed = entry.get("published_parsed")
                published = (
                    datetime(*published_parsed[:6], tzinfo=timezone.utc)
                    if published_parsed else datetime.now(timezone.utc)
                )
                stories.append({
                    "title": entry.get("title", ""),
                    "link": entry.get("link", ""),
                    "published": published,
                    "summary": entry.get("summary", ""),
                    "source_name": source,
                })
        return stories

    async def _fetch_all_serpapi(self) -> list[dict]:
        """CONT-03: Run SerpAPI keyword searches concurrently via asyncio.gather + run_in_executor."""
        if self.serpapi_client is None:
            logger.warning("SerpAPI key not configured — skipping keyword searches, using RSS only.")
            return []
        loop = asyncio.get_event_loop()
        tasks = []
        for keyword in SERPAPI_KEYWORDS:
            def _call(q=keyword):
                return self.serpapi_client.search({
                    "engine": "google_news",
                    "q": q,
                    "num": 5,
                })
            tasks.append(loop.run_in_executor(None, _call))
        results = await asyncio.gather(*tasks, return_exceptions=True)
        stories = []
        for keyword, result in zip(SERPAPI_KEYWORDS, results):
            if isinstance(result, Exception):
                logger.warning("SerpAPI search '%s' failed: %s", keyword, result)
                continue
            for item in result.get("news_results", [])[:5]:
                iso_date = item.get("date")
                if iso_date:
                    try:
                        published = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
                    except ValueError:
                        try:
                            published = datetime.strptime(iso_date, "%m/%d/%Y, %I:%M %p, +0000 UTC").replace(
                                tzinfo=timezone.utc
                            )
                        except ValueError:
                            published = datetime.now(timezone.utc)
                else:
                    published = datetime.now(timezone.utc)
                source_name = (item.get("source") or {}).get("name", "unknown")
                stories.append({
                    "title": item.get("title", ""),
                    "link": item.get("link", ""),
                    "published": published,
                    "summary": item.get("snippet", ""),
                    "source_name": source_name,
                })
        return stories

    @staticmethod
    def _keyword_relevance(title: str, summary: str) -> float:
        """Fast keyword-based relevance score as fallback when Anthropic is unavailable.

        Counts gold/mining keyword hits and returns a 0.0-1.0 score.
        High-signal keywords (gold, silver, mining) → 0.7-0.9.
        Zero hits → 0.3 (some relevance assumed since we only ingest gold RSS/news sources).
        """
        text = (title + " " + summary).lower()
        HIGH_SIGNAL = ["gold price", "gold mining", "precious metal", "bullion", "gold reserve",
                       "central bank gold", "gold standard", "gold etf", "gold miner"]
        MED_SIGNAL = ["gold", "silver", "platinum", "copper", "mining", "miner", "ore", "drill",
                      "royalty", "streaming", "ounce", "oz", "troy", "vein", "deposit",
                      "exploration", "production", "refinery", "smelter"]
        hits_high = sum(1 for kw in HIGH_SIGNAL if kw in text)
        hits_med = sum(1 for kw in MED_SIGNAL if kw in text)
        if hits_high >= 2:
            return 0.9
        if hits_high == 1:
            return 0.8
        if hits_med >= 3:
            return 0.75
        if hits_med >= 1:
            return 0.65
        return 0.3

    async def _score_relevance(self, title: str, summary: str) -> float:
        """CONT-05: Claude call to classify gold-sector relevance on 0-1 scale.

        Falls back to keyword-based scoring if Anthropic API is unavailable.
        Keyword fallback produces 0.3-0.9 scores (not flat 0.5) so stories can
        be meaningfully ranked even when the API is down.
        """
        try:
            response = await self.anthropic.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=10,
                system=(
                    "Rate the relevance of this news story to the gold sector using these bands:\n"
                    "0.7-1.0: Directly about gold, precious metals, gold mining, gold ETFs, central bank gold, or gold-specific analysis.\n"
                    "0.5-0.8: Systemic financial or geopolitical shock that would plausibly move gold prices — "
                    "e.g. major war escalation, sanctions on oil exporters, Strait of Hormuz disruption, "
                    "Fed/USD policy shock, currency crisis, or global recession signal.\n"
                    "0.0-0.3: Generic business, equity markets, sector news unrelated to gold, "
                    "option traders, private credit, quizzes, or financial clickbait with no gold angle.\n"
                    "Reply with only a decimal number."
                ),
                messages=[{"role": "user", "content": f"Title: {title}\nSummary: {summary}"}],
            )
            score = float(response.content[0].text.strip())
            return max(0.0, min(1.0, score))
        except Exception as exc:
            logger.warning(
                "Relevance scoring API failed for '%s' (%s) — using keyword fallback",
                title[:50], type(exc).__name__,
            )
            return self._keyword_relevance(title, summary)

    async def _run_pipeline(self, session: AsyncSession, agent_run: AgentRun) -> None:
        """CONT-01: Orchestrate the full ingest-dedup-score-research-draft-comply-persist flow.

        Multi-story: processes ALL stories above threshold per run.
        Cross-run dedup: skips stories already covered in today's earlier runs.
        Per-story error isolation: one story failure does not abort remaining stories.
        """
        # 1. Read config
        threshold = float(await self._get_config(session, "content_quality_threshold", "7.0"))
        rel_weight = float(await self._get_config(session, "content_relevance_weight", "0.40"))
        rec_weight = float(await self._get_config(session, "content_recency_weight", "0.30"))
        cred_weight = float(await self._get_config(session, "content_credibility_weight", "0.30"))
        gate_enabled = await self._get_config(session, "content_gold_gate_enabled", "true")
        gate_model = await self._get_config(session, "content_gold_gate_model", "claude-3-5-haiku-latest")
        gate_config = {
            "content_gold_gate_enabled": gate_enabled,
            "content_gold_gate_model": gate_model,
        }

        # 2. Ingest RSS + SerpAPI concurrently
        rss_stories, serpapi_stories = await asyncio.gather(
            self._fetch_all_rss(),
            self._fetch_all_serpapi(),
        )
        all_stories = rss_stories + serpapi_stories
        agent_run.items_found = len(all_stories)
        logger.info(
            "Ingested %d stories (%d RSS, %d SerpAPI)",
            len(all_stories), len(rss_stories), len(serpapi_stories),
        )

        # 3. Deduplicate (within-run)
        unique_stories = deduplicate_stories(all_stories)
        agent_run.items_filtered = len(all_stories) - len(unique_stories)
        logger.info(
            "After dedup: %d unique stories (filtered %d)",
            len(unique_stories), agent_run.items_filtered,
        )

        if not unique_stories:
            bundle = build_no_story_bundle(best_score=0.0)
            session.add(bundle)
            agent_run.notes = json.dumps({"best_candidate": None, "best_score": 0.0})
            return

        # 4. Score each story
        scored = []
        for story in unique_stories:
            relevance = await self._score_relevance(story["title"], story["summary"])
            rec = recency_score(story["published"])
            cred = credibility_score(story.get("source_name", ""))
            story["score"] = (relevance * rel_weight + rec * rec_weight + cred * cred_weight) * 10
            scored.append(story)

        # 4b. Classify format per story for slice-priority decision (format-first pipeline).
        # Uses cheap Haiku call — full Sonnet draft happens later only for top-N selected.
        format_labels = await asyncio.gather(*[
            classify_format_lightweight(s, client=self.anthropic) for s in scored
        ])
        for s, fmt in zip(scored, format_labels):
            s["predicted_format"] = fmt

        # 5. Select top-N qualifying stories (multi-story, breaking/fresh priority)
        max_count = int(await self._get_config(session, "content_agent_max_stories_per_run", "5"))
        breaking_window = float(await self._get_config(session, "content_agent_breaking_window_hours", "3"))
        qualifying = select_qualifying_stories(
            scored,
            threshold=threshold,
            max_count=max_count,
            breaking_window_hours=breaking_window,
        )
        priority_count = sum(
            1 for s in qualifying
            if s.get("predicted_format") == "breaking_news"
            or _is_within_window(s.get("published"), breaking_window)
        )
        logger.info(
            "Top-%d slice: %d priority (breaking/fresh) + %d regular",
            len(qualifying), priority_count, len(qualifying) - priority_count,
        )

        if not qualifying:
            best = max(scored, key=lambda s: s["score"])
            bundle = build_no_story_bundle(best_score=best["score"])
            session.add(bundle)
            agent_run.notes = json.dumps({
                "best_candidate": best["title"][:200],
                "best_score": float(best["score"]),
            })
            logger.info(
                "No story cleared threshold %.1f (best: %.1f '%s')",
                threshold, best["score"], best["title"][:60],
            )
            return

        # 6. Process each qualifying story with cross-run dedup + per-story error isolation
        items_queued = 0
        all_already_covered = True
        story_notes = []
        skipped_by_gate = 0

        for story in qualifying:
            try:
                # Cross-run dedup: skip if already covered in an earlier run today
                already_covered = await self._is_already_covered_today(
                    session, story["link"], story["title"]
                )
                if already_covered:
                    logger.info(
                        "Skipping (already covered today): '%s'", story["title"][:60]
                    )
                    continue

                all_already_covered = False

                # Gold relevance gate: hard-reject non-gold articles that passed threshold
                gate_decision = await is_gold_relevant_or_systemic_shock(
                    story, gate_config, client=self.anthropic
                )
                if not gate_decision["keep"]:
                    skipped_by_gate += 1
                    reason = gate_decision.get("reject_reason")
                    company = gate_decision.get("company")
                    if reason == "primary_subject_is_specific_miner":
                        if company:
                            logger.info(
                                "ContentAgent: rejected story %r — primary subject is specific miner (%s).",
                                story["title"][:120], company,
                            )
                        else:
                            logger.info(
                                "ContentAgent: rejected story %r — primary subject is specific miner.",
                                story["title"][:120],
                            )
                    else:
                        # Preserve existing log shape for non-gold / listicle / systemic rejects
                        logger.info(
                            "Gold gate rejected (skipped_by_gate=%d): %r",
                            skipped_by_gate, story["title"][:60],
                        )
                    continue

                # Deep research
                article_text, fetch_ok = await fetch_article(
                    story["link"], fallback_text=story.get("summary", "")
                )
                corroborating = await self._search_corroborating(story["title"])
                deep_research = {
                    "article_text": article_text[:5000],  # Cap at 5000 chars
                    "article_fetch_succeeded": fetch_ok,
                    "corroborating_sources": corroborating,
                    "key_data_points": [],  # Filled by Sonnet prompt
                }

                # Format decision + drafting (combined Sonnet call)
                draft_result = await self._research_and_draft(story, deep_research)
                if draft_result is None:
                    logger.error("Drafting failed for '%s'", story["title"][:60])
                    from models.content_bundle import ContentBundle  # noqa: PLC0415
                    bundle = ContentBundle(
                        story_headline=story["title"],
                        story_url=story["link"],
                        source_name=story.get("source_name"),
                        score=story["score"],
                        deep_research=deep_research,
                        compliance_passed=False,
                    )
                    session.add(bundle)
                    continue
                draft_content, deep_research, rationale = draft_result

                # Compliance check
                check_text = _extract_check_text(draft_content)
                compliance_ok = await check_compliance(check_text, self.anthropic)

                # Persist ContentBundle
                from models.content_bundle import ContentBundle  # noqa: PLC0415
                bundle = ContentBundle(
                    story_headline=story["title"],
                    story_url=story["link"],
                    source_name=story.get("source_name"),
                    content_type=draft_content.get("format"),
                    score=story["score"],
                    deep_research=deep_research,
                    draft_content=draft_content,
                    compliance_passed=compliance_ok,
                )
                session.add(bundle)
                await session.flush()  # Get bundle.id

                if not compliance_ok:
                    logger.warning(
                        "Compliance check failed for '%s'", story["title"][:60]
                    )
                    story_notes.append({
                        "story": story["title"][:200],
                        "score": float(story["score"]),
                        "blocked": True,
                    })
                    continue

                # Create DraftItem + call Senior Agent
                item = build_draft_item(bundle, rationale)
                session.add(item)
                await session.flush()  # Get item.id

                # Lazy import to avoid circular deps
                from agents.senior_agent import process_new_items  # noqa: PLC0415
                await process_new_items([item.id])

                items_queued += 1
                self._queued_titles.append(story["title"][:80])
                story_notes.append({
                    "story": story["title"][:200],
                    "score": float(story["score"]),
                    "format": draft_content.get("format"),
                    "content_bundle_id": str(bundle.id),
                })
                logger.info(
                    "Content Agent queued: '%s' (score=%.1f, format=%s)",
                    story["title"][:60], story["score"], draft_content.get("format"),
                )

            except Exception as exc:
                logger.error(
                    "Error processing story '%s': %s",
                    story.get("title", "")[:60], exc,
                    exc_info=True,
                )
                # Per-story error isolation — continue with remaining stories

        if skipped_by_gate:
            logger.info("Gold gate rejected %d stories this run", skipped_by_gate)
        if self._skipped_short_longform:
            logger.info(
                "Content agent run: skipped_short_longform=%d",
                self._skipped_short_longform,
            )

        # Handle the case where ALL qualifying stories were already covered
        if all_already_covered:
            logger.info(
                "All %d qualifying stories already covered in earlier run today",
                len(qualifying),
            )
            from models.content_bundle import ContentBundle  # noqa: PLC0415
            bundle = ContentBundle(
                story_headline="All qualifying stories already covered in earlier run",
                no_story_flag=True,
                score=qualifying[0]["score"] if qualifying else 0.0,
            )
            session.add(bundle)
            agent_run.notes = json.dumps({
                "reason": "All qualifying stories already covered in earlier run",
                "qualifying_count": len(qualifying),
            })
            return

        agent_run.items_queued = items_queued
        agent_run.notes = json.dumps({"stories": story_notes})

        # 11. Twitter video clip + quote search (runs after main RSS/SerpAPI story loop)
        await self._run_twitter_content_search(session, agent_run)

    async def _run_twitter_content_search(
        self, session: AsyncSession, agent_run: AgentRun
    ) -> None:
        """Search Twitter for video clips and quotes; draft, comply, and persist each.

        Called at the end of _run_pipeline() after the main RSS/SerpAPI story loop.
        Each item is wrapped in try/except for error isolation — individual failures
        do not abort remaining items.
        """
        from models.content_bundle import ContentBundle  # noqa: PLC0415
        from agents.senior_agent import process_new_items  # noqa: PLC0415

        # --- Video clips ---
        video_clips = await self._search_video_clips(session)
        for clip in video_clips:
            try:
                tweet_url = clip["tweet_url"]
                # Cross-run dedup: skip if this tweet_url already in today's bundles
                today_utc = datetime.now(timezone.utc).date()
                from sqlalchemy import func as sqlfunc  # noqa: PLC0415
                existing = await session.execute(
                    select(ContentBundle).where(
                        sqlfunc.date(ContentBundle.created_at) == today_utc,
                        ContentBundle.story_url == tweet_url,
                        ContentBundle.no_story_flag.is_(False),
                    )
                )
                if existing.scalar_one_or_none() is not None:
                    logger.info("Video clip already covered today: %s", tweet_url)
                    continue

                draft_content = await self._draft_video_caption(
                    tweet_text=clip["text"],
                    author_username=clip["author_username"],
                    author_name=clip["author_name"],
                    tweet_url=tweet_url,
                )
                if draft_content is None:
                    logger.warning("Video caption draft failed for %s", tweet_url)
                    continue

                check_text = _extract_check_text(draft_content)
                compliance_ok = await check_compliance(check_text, self.anthropic)

                vc_bundle = ContentBundle(
                    story_headline=clip["text"][:200],
                    story_url=tweet_url,
                    source_name=clip["author_username"],
                    content_type="video_clip",
                    score=7.5,  # Fixed score for Twitter-sourced content
                    draft_content=draft_content,
                    compliance_passed=compliance_ok,
                )
                session.add(vc_bundle)
                await session.flush()

                if compliance_ok:
                    rationale = f"Video clip from @{clip['author_username']} on gold sector"
                    vc_item = build_draft_item(vc_bundle, rationale)
                    session.add(vc_item)
                    await session.flush()
                    await process_new_items([vc_item.id])
                    agent_run.items_queued = (agent_run.items_queued or 0) + 1
                    self._queued_titles.append(f"Video: @{clip['author_username']}")
                    logger.info("Video clip queued from @%s", clip["author_username"])
                else:
                    logger.warning("Video clip compliance failed for %s", tweet_url)

            except Exception as exc:
                logger.error("Video clip processing error for %s: %s", clip.get("tweet_url", "?"), exc)

        # --- Quote tweets ---
        quote_tweets = await self._search_quote_tweets(session)
        for qt in quote_tweets:
            try:
                tweet_url = qt["tweet_url"]
                # Cross-run dedup
                today_utc = datetime.now(timezone.utc).date()
                from sqlalchemy import func as sqlfunc  # noqa: PLC0415
                existing = await session.execute(
                    select(ContentBundle).where(
                        sqlfunc.date(ContentBundle.created_at) == today_utc,
                        ContentBundle.story_url == tweet_url,
                        ContentBundle.no_story_flag.is_(False),
                    )
                )
                if existing.scalar_one_or_none() is not None:
                    logger.info("Quote tweet already covered today: %s", tweet_url)
                    continue

                speaker_title = "Author, macro investor"  # Default; Claude will improve
                draft_content = await self._draft_quote_post(
                    quote_text=qt["text"],
                    speaker=qt["author_name"],
                    speaker_title=speaker_title,
                    source_url=tweet_url,
                )
                if draft_content is None:
                    logger.warning("Quote post draft failed for %s", tweet_url)
                    continue

                check_text = _extract_check_text(draft_content)
                compliance_ok = await check_compliance(check_text, self.anthropic)

                q_bundle = ContentBundle(
                    story_headline=qt["text"][:200],
                    story_url=tweet_url,
                    source_name=qt["author_username"],
                    content_type="quote",
                    score=7.5,  # Fixed score for Twitter-sourced content
                    draft_content=draft_content,
                    compliance_passed=compliance_ok,
                )
                session.add(q_bundle)
                await session.flush()

                if compliance_ok:
                    rationale = f"Quote from {qt['author_name']} on gold sector"
                    q_item = build_draft_item(q_bundle, rationale)
                    session.add(q_item)
                    await session.flush()
                    await process_new_items([q_item.id])
                    agent_run.items_queued = (agent_run.items_queued or 0) + 1
                    self._queued_titles.append(f"Quote: {qt['author_name']}")
                    logger.info("Quote tweet queued from %s", qt["author_name"])
                else:
                    logger.warning("Quote tweet compliance failed for %s", tweet_url)

            except Exception as exc:
                logger.error("Quote tweet processing error for %s: %s", qt.get("tweet_url", "?"), exc)

    async def run(self) -> None:
        """Entry point called by APScheduler. Runs the full pipeline."""
        self._queued_titles: list[str] = []  # reset each run
        async with AsyncSessionLocal() as session:
            agent_run = AgentRun(
                agent_name="content_agent",
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
                logger.error("ContentAgent run failed: %s", exc, exc_info=True)
            finally:
                agent_run.ended_at = datetime.now(timezone.utc)
                await session.commit()

                # WhatsApp new-item notification (fires after commit, non-fatal)
                items_queued_count = agent_run.items_queued or 0
                if items_queued_count > 0:
                    try:
                        from services.whatsapp import send_whatsapp_message  # noqa: PLC0415
                        titles = self._queued_titles
                        if titles:
                            title_lines = "\n".join(f"  • {t}" for t in titles)
                            msg = (
                                f"📰 Content Agent — {items_queued_count} new "
                                f"item{'s' if items_queued_count != 1 else ''} ready for review:\n"
                                f"{title_lines}"
                            )
                        else:
                            msg = (
                                f"📰 Content Agent — {items_queued_count} new "
                                f"item{'s' if items_queued_count != 1 else ''} ready for review"
                            )
                        await send_whatsapp_message(msg)
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("WhatsApp notification failed (non-fatal): %s", exc)
