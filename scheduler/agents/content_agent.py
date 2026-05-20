"""
Content Agent — ingestion + helpers module.

Post quick-260421-eoe, the Content Agent is NO LONGER a scheduled agent. It is a
library module that the 6 content sub-agents (under scheduler/agents/content/)
call into. It exposes:

- ``fetch_stories()``: Shared SerpAPI + RSS ingestion with a 30-min in-memory
  cache keyed on ``int(time.time() // 1800)``. Returns scored, deduped stories
  with ``predicted_format`` labels so each sub-agent can filter to its own
  content_type. Process-local cache — Railway runs the scheduler as a single
  worker, so this is safe.
- ``classify_format_lightweight(story, *, client)``: Retained helper export.
  Returns one of ``breaking_news | thread | infographic | quote``.

Sub-agents are responsible for the per-story deep research + drafting + persistence.
This module also keeps a handful of shared helpers the sub-agents call directly:
``fetch_article`` / ``extract_article_text`` / ``deduplicate_stories`` /
``recency_score`` / ``credibility_score`` / ``calculate_story_score`` /
``build_draft_item`` / ``build_no_story_bundle``.

v3.1 Phase 12 (quick-260520 / 12-02): The compliance/review sub-system
(``review``, ``check_compliance``, ``is_gold_relevant_or_systemic_shock``,
``_extract_check_text``) was surgically excised — those functions had no
production callers after the 260420-sn9 / 260423-k8n purges; they only
called each other and their tests. The LIVE exports (fetch_stories,
deduplicate_stories) are preserved verbatim. See 12-02-SUMMARY.md.

Requirements: CONT-01 through CONT-17 (coverage split across the 6 sub-agents).
"""

from __future__ import annotations

import asyncio
import difflib
import logging
import time
from datetime import datetime, timezone

import feedparser
import httpx
import serpapi
from anthropic import AsyncAnthropic
from bs4 import BeautifulSoup

from anthropic_client import get_anthropic_client
from config import get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# RSS feed list — module-level constant (CONT-02)
# ---------------------------------------------------------------------------
#
# quick-260506-i65 (2026-05-06): Live HTTP probe revealed the original 7-feed
# list had rotted to 1 working source. Modern news sites have largely killed
# public RSS:
#   - kitco.com/rss/news.xml         → 404 (no replacement; kitco removed RSS)
#   - juniorminingnetwork.com/feed   → 403 (anti-scraping, blocks browser UA)
#   - gold.org/goldhub/news/feed     → 404 (WGC removed RSS; no replacement)
#   - bnnbloomberg.ca/feed/          → 404
#   - feeds.bloomberg.com/commodities/news.rss → 404 (commodity-specific dead)
#   - goldseek.com/feed/             → 404
# Replaced the dead URLs with 3 verified-live, gold-relevant feeds:
#   - northernminer.com/feed         → 30 KB valid RSS, Canadian mining authority
#   - goldswitzerland.com/feed       → 14 KB pure gold commentary
#   - fxstreet.com/rss/news          → 17 KB gold + macro commodity market data
#
# quick-260506-inz (2026-05-06): Added back Bloomberg via the broader
# markets/news.rss feed (the original commodity-specific URL is still 404 but
# this broader markets feed is alive at ~33 KB / ~20 articles). Bloomberg's
# tier-1 credibility (1.0) means even though only ~5-15% of items are gold-
# relevant on a typical day, the few stories that are (central bank gold
# purchases, hedge fund gold positions, macro gold drivers) carry strong
# signal. The Sonnet relevance filter drops the ~85% non-gold content; net
# Anthropic cost increase is well within the $30-50/mo budget.
#
# Credibility tiers below updated to match. SerpAPI (broader keyword sweep)
# remains the heavy lifter; RSS is the long-tail catch.
RSS_FEEDS = [
    ("https://www.mining.com/feed/", "mining.com"),
    ("https://www.northernminer.com/feed/", "northernminer.com"),
    ("https://goldswitzerland.com/feed/", "goldswitzerland.com"),
    ("https://www.fxstreet.com/rss/news", "fxstreet.com"),
    ("https://feeds.bloomberg.com/markets/news.rss", "bloomberg.com"),
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
    # Expansion (htu) — critical minerals + sovereign gold coverage.
    # quick-260424-j5i D8 removed the unhyphenated rare-earth keyword (pulled too
    # many off-theme rare-earth policy pieces that did not map to gold). 8 → 7.
    "critical minerals",
    "strategic metals",
    "sovereign wealth fund gold",
    "treasury gold sale",
    "gold mining M&A",
    "US China metals",
    "mineral supply chain",
    # quick-260518-fyq — analyst & bank named-target keywords. User feedback after
    # 4 days of cards without surfacing any named-analyst calls (Bloomberg's
    # Goldman/JPMorgan gold-target stories etc. weren't reaching the Analyst &
    # Bank Predictions section). These keywords explicitly target the highest-
    # leverage content type: named-analyst price targets + catalyst narratives.
    "Goldman Sachs gold",
    "JPMorgan gold forecast",
    "Bank of America gold",
    "UBS gold target",
    "Pierre Lassonde",
    "Peter Schiff gold",
    "Egon von Greyerz",
    "World Gold Council central bank",
]

# ---------------------------------------------------------------------------
# Credibility tier lookup — module-level constant (CONT-05)
# ---------------------------------------------------------------------------

CREDIBILITY_TIERS: dict[str, float] = {
    # Tier 1 — institutional wire services / authoritative bodies
    "reuters.com": 1.0,
    "bloomberg.com": 1.0,
    "worldgoldcouncil.org": 0.9,
    "gold.org": 0.9,
    # Tier 2 — established mining trade press
    "kitco.com": 0.8,                # may appear in SerpAPI even though RSS is dead
    "mining.com": 0.8,
    "northernminer.com": 0.8,        # quick-260506-i65 — NEW, Canadian mining authority
    "juniorminingnetwork.com": 0.7,  # may appear in SerpAPI even though RSS is dead
    # Tier 3 — gold-focused commentary + market analysis
    "goldswitzerland.com": 0.6,      # quick-260506-i65 — NEW, Von Greyerz/Piepenburg gold commentary
    "goldseek.com": 0.6,             # may appear in SerpAPI
    "investing.com": 0.6,
    "fxstreet.com": 0.6,             # quick-260506-i65 — NEW, market analysis incl. gold
}
DEFAULT_CREDIBILITY = 0.4


# ---------------------------------------------------------------------------
# Pure scoring functions — module-level for direct testability (CONT-05)
# ---------------------------------------------------------------------------


def recency_score(published: datetime) -> float:
    """CONT-05: Return recency score based on story age.

    Returns:
        1.0 for <3h, 0.8 for <6h, 0.6 for <12h, 0.4 for <24h,
        0.3 for <48h (quick-260424-j5i D3 — softens the 24h cliff so
        high-credibility late-catch stories retain one more day of signal),
        0.2 for >=48h.
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
    if age_hours < 48:
        return 0.3
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
                if candidate_cred > existing_cred:
                    displaced_idx = idx
                break

        if not similar_found:
            kept.append(candidate)
        elif displaced_idx is not None:
            kept[displaced_idx] = candidate

    return kept


async def classify_format_lightweight(story: dict, *, client) -> str:
    """Lightweight Haiku format classifier for slice-priority decision.

    Uses claude-haiku-4-5 (cheap) — full Sonnet format+draft call happens
    later only for the top-N selected stories.

    Returns one of: breaking_news | thread | infographic | quote.
    Fail-open: returns "thread" (current ambiguous default) on any error or
    unexpected output.
    """
    valid_formats = {"breaking_news", "thread", "infographic", "quote"}
    try:
        response = await client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=20,
            system="You are a content format classifier. Reply with one word.",
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Title: {story['title']}\n"
                        f"Summary: {story.get('summary', '')[:500]}\n"
                        f"Published: {story.get('published', '')}\n\n"
                        "Which content format best fits? Choose exactly one: "
                        "breaking_news | thread | infographic | quote. "
                        "Reply with ONLY the format name."
                    ),
                }
            ],
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


# ---------------------------------------------------------------------------
# Article fetch + BeautifulSoup extraction (CONT-08)
# ---------------------------------------------------------------------------


def extract_article_text(html: str) -> str:
    """Extract main article text from HTML, stripping boilerplate.

    Strips nav/header/footer/aside/script/style tags, then tries semantic
    content selectors in priority order. Falls back to full body text.
    """
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(["nav", "header", "footer", "aside", "script", "style"]):
        tag.decompose()
    for selector in ["article", "main", "[role='main']", "div.content", "div.article-body"]:
        node = soup.select_one(selector)
        if node:
            return node.get_text(separator=" ", strip=True)
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
                logger.warning(
                    "Article fetch %s returned %d, using fallback", url, resp.status_code
                )
                return fallback_text, False
            text = extract_article_text(resp.text)
            if len(text) < 100:
                logger.warning("Article fetch %s extracted <100 chars, using fallback", url)
                return fallback_text, False
            return text, True
    except (httpx.HTTPError, httpx.TimeoutException, Exception) as exc:
        logger.warning("Article fetch %s failed: %s, using fallback", url, exc)
        return fallback_text, False


# ---------------------------------------------------------------------------
# Corroborating-sources search (CONT-09)
# ---------------------------------------------------------------------------


async def search_corroborating(
    headline: str,
    *,
    serpapi_client: "serpapi.Client | None" = None,
) -> list[dict]:
    """CONT-09: Find 2-3 corroborating sources via SerpAPI Google News.

    Runs synchronous serpapi call in executor to avoid blocking the event loop.
    If no client is passed, constructs one from settings.

    Returns:
        List of dicts with keys: title, url, source, snippet.
    """
    if serpapi_client is None:
        settings = get_settings()
        if not settings.serpapi_api_key:
            return []
        serpapi_client = serpapi.Client(api_key=settings.serpapi_api_key)

    loop = asyncio.get_event_loop()
    try:

        def _call():
            return serpapi_client.search(
                {
                    "engine": "google_news",
                    "q": headline,
                    "num": 3,
                }
            )

        results = await loop.run_in_executor(None, _call)
        sources = []
        for item in results.get("news_results", [])[:3]:
            sources.append(
                {
                    "title": item.get("title", ""),
                    "url": item.get("link", ""),
                    "source": (item.get("source") or {}).get("name", "unknown"),
                    "snippet": item.get("snippet", ""),
                }
            )
        return sources
    except Exception as exc:
        logger.warning("Corroboration search failed: %s", exc)
        return []


# ---------------------------------------------------------------------------
# No-story flag and ContentBundle builder (CONT-07)
# ---------------------------------------------------------------------------


def build_no_story_bundle(best_score: float):
    """Create a ContentBundle with no_story_flag=True for days with no qualifying story."""
    from models.content_bundle import ContentBundle  # noqa: PLC0415

    return ContentBundle(
        story_headline="No qualifying story today",
        no_story_flag=True,
        score=best_score,
    )


# ---------------------------------------------------------------------------
# DraftItem builder for the approval queue (CONT-17)
# ---------------------------------------------------------------------------


def build_draft_item(content_bundle, rationale: str):
    """Create a DraftItem from a ContentBundle for the approval queue.

    platform='content', urgency='low', expires_at=None (evergreen content).
    Stores content_bundle.id in engagement_snapshot for the frontend JSONB link
    (no direct FK on draft_items).
    """
    from models.draft_item import DraftItem  # noqa: PLC0415

    draft = content_bundle.draft_content or {}
    fmt = draft.get("format", "unknown")

    if fmt == "breaking_news":
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
        tweets = draft.get("tweets", [])
        if isinstance(tweets, list):
            draft_text = "\n\n".join(str(t) for t in tweets if t)
        else:
            draft_text = str(tweets)

    elif fmt == "infographic":
        caption = draft.get("twitter_caption", "")
        if not caption:
            charts = draft.get("charts", [])
            if charts and isinstance(charts[0], dict):
                caption = charts[0].get("title", "")
        draft_text = caption

    elif fmt == "gold_history":
        tweets = draft.get("tweets", [])
        carousel = draft.get("instagram_carousel", [])
        parts = []
        if tweets:
            parts.append("=== Thread ===\n" + "\n\n".join(str(t) for t in tweets if t))
        if carousel:
            # Per quick-260427-k5h: each slide is a dict with headline + body +
            # visual_note (see scheduler/agents/content/gold_history.py drafter
            # prompt — that's the source-of-truth schema). The pre-k5h code read
            # slide.get('text', '') which doesn't exist on any slide, so the
            # modal showed empty `Slide N:` lines. Render each present field on
            # its own indented line for readability + copy-into-image-generator.
            slide_lines = []
            for i, slide in enumerate(carousel):
                prefix = f"Slide {i + 1}:"
                if isinstance(slide, str):
                    slide_lines.append(f"{prefix} {slide}")
                    continue
                if not isinstance(slide, dict):
                    slide_lines.append(prefix)
                    continue
                headline = (slide.get("headline") or "").strip()
                body = (slide.get("body") or "").strip()
                visual = (slide.get("visual_note") or "").strip()
                block = [f"{prefix} {headline}" if headline else prefix]
                if body:
                    block.append(f"  {body}")
                if visual:
                    block.append(f"  Visual: {visual}")
                slide_lines.append("\n".join(block))
            parts.append("=== Instagram Carousel ===\n" + "\n\n".join(slide_lines))
        draft_text = (
            "\n\n".join(parts) if parts else f"Gold History: {draft.get('story_title', '')}"
        )

    elif fmt == "gold_media":
        draft_text = (
            draft.get("twitter_caption", "")
            or draft.get("instagram_caption", "")
            or f"Gold media clip from @{draft.get('source_account', 'unknown')}"
        )

    elif fmt == "quote":
        draft_text = (
            draft.get("twitter_post", "")
            or draft.get("instagram_post", "")
            or f'"{draft.get("quote_text", "")}" — {draft.get("speaker", "")}'
        )

    else:
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
# RSS and SerpAPI parsing helpers (CONT-02, CONT-03)
# ---------------------------------------------------------------------------


def parse_rss_entries(feed_url: str, source_name: str) -> list[dict]:
    """CONT-02: Parse an RSS feed and return normalized story dicts.

    Each dict has: title, link, published (datetime), summary, source_name.
    """
    return []


def parse_serpapi_results(results: list[dict], source_name: str = "serpapi") -> list[dict]:
    """CONT-03: Parse SerpAPI news results into normalized story dicts."""
    return []


# ---------------------------------------------------------------------------
# Shared ingestion: RSS + SerpAPI (called by fetch_stories only)
# ---------------------------------------------------------------------------


async def _fetch_all_rss() -> list[dict]:
    """CONT-02: Fetch all RSS feeds concurrently using asyncio.gather + run_in_executor."""
    loop = asyncio.get_event_loop()
    tasks = []
    for url, _source in RSS_FEEDS:
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
                if published_parsed
                else datetime.now(timezone.utc)
            )
            stories.append(
                {
                    "title": entry.get("title", ""),
                    "link": entry.get("link", ""),
                    "published": published,
                    "summary": entry.get("summary", ""),
                    "source_name": source,
                    # quick-260507-drw — tag for downstream telemetry
                    # so daily_summary can break down candidates by ingestion path.
                    "_source_type": "rss",
                }
            )
    return stories


async def _fetch_all_serpapi(serpapi_client: "serpapi.Client | None") -> list[dict]:
    """CONT-03: Run SerpAPI keyword searches concurrently via asyncio.gather + run_in_executor."""
    if serpapi_client is None:
        logger.warning("SerpAPI key not configured — skipping keyword searches, using RSS only.")
        return []
    loop = asyncio.get_event_loop()
    tasks = []
    for keyword in SERPAPI_KEYWORDS:

        def _call(q=keyword):
            return serpapi_client.search(
                {
                    "engine": "google_news",
                    "q": q,
                    "num": 5,
                }
            )

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
                        published = datetime.strptime(
                            iso_date, "%m/%d/%Y, %I:%M %p, +0000 UTC"
                        ).replace(tzinfo=timezone.utc)
                    except ValueError:
                        published = datetime.now(timezone.utc)
            else:
                published = datetime.now(timezone.utc)
            source_name = (item.get("source") or {}).get("name", "unknown")
            stories.append(
                {
                    "title": item.get("title", ""),
                    "link": item.get("link", ""),
                    "published": published,
                    "summary": item.get("snippet", ""),
                    "source_name": source_name,
                    # quick-260507-drw — tag for downstream telemetry
                    # so daily_summary can break down candidates by ingestion path.
                    "_source_type": "serpapi",
                }
            )
    return stories


async def fetch_analytical_historical_stories(queries: list[str]) -> list[dict]:
    """SerpAPI fetch for analytical/historical gold topics. Used by sub_infographics
    (fallback phase, quick-260423-lvp) AND sub_gold_history (primary fetch,
    quick-260424-e37). Accepts a caller-supplied query list; not cached.

    Mirrors _fetch_all_serpapi pattern but accepts a custom query list. Both
    callers pass a small, caller-specific query list (infographics:
    ANALYTICAL_HISTORICAL_QUERIES; gold_history: HISTORICAL_GOLD_QUERIES).
    Intentionally NOT cached: invoked rarely and the query list is caller-specific.

    Returns story dicts in the same shape as fetch_stories() per-story entries
    BEFORE scoring (keys: title, link, published, summary, source_name). The
    caller is responsible for gold-gate + draft + review + persist.

    Returns [] if SerpAPI is not configured or if all queries fail.
    """
    settings = get_settings()
    if not settings.serpapi_api_key:
        logger.warning(
            "fetch_analytical_historical_stories: SerpAPI not configured — returning []",
        )
        return []
    serpapi_client = serpapi.Client(api_key=settings.serpapi_api_key)
    loop = asyncio.get_event_loop()
    tasks = []
    for q in queries:

        def _call(query=q):
            return serpapi_client.search(
                {
                    "engine": "google_news",
                    "q": query,
                    "num": 5,
                }
            )

        tasks.append(loop.run_in_executor(None, _call))
    results = await asyncio.gather(*tasks, return_exceptions=True)
    stories: list[dict] = []
    for query, result in zip(queries, results):
        if isinstance(result, Exception):
            logger.warning(
                "fetch_analytical_historical_stories: query '%s' failed: %s",
                query,
                result,
            )
            continue
        for item in result.get("news_results", [])[:5]:
            iso_date = item.get("date")
            if iso_date:
                try:
                    published = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
                except ValueError:
                    try:
                        published = datetime.strptime(
                            iso_date,
                            "%m/%d/%Y, %I:%M %p, +0000 UTC",
                        ).replace(tzinfo=timezone.utc)
                    except ValueError:
                        published = datetime.now(timezone.utc)
            else:
                published = datetime.now(timezone.utc)
            source_name = (item.get("source") or {}).get("name", "unknown")
            stories.append(
                {
                    "title": item.get("title", ""),
                    "link": item.get("link", ""),
                    "published": published,
                    "summary": item.get("snippet", ""),
                    "source_name": source_name,
                }
            )
    logger.info(
        "fetch_analytical_historical_stories: %d queries → %d stories",
        len(queries),
        len(stories),
    )
    return stories


def _keyword_relevance(title: str, summary: str) -> float:
    """Fast keyword-based relevance score as fallback when Anthropic is unavailable.

    Counts gold/mining keyword hits and returns a 0.0-1.0 score.
    """
    text = (title + " " + summary).lower()
    HIGH_SIGNAL = [
        "gold price",
        "gold mining",
        "precious metal",
        "bullion",
        "gold reserve",
        "central bank gold",
        "gold standard",
        "gold etf",
        "gold miner",
    ]
    MED_SIGNAL = [
        "gold",
        "silver",
        "platinum",
        "copper",
        "mining",
        "miner",
        "ore",
        "drill",
        "royalty",
        "streaming",
        "ounce",
        "oz",
        "troy",
        "vein",
        "deposit",
        "exploration",
        "production",
        "refinery",
        "smelter",
    ]
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


async def _score_relevance(title: str, summary: str, *, client: AsyncAnthropic) -> float:
    """CONT-05: Claude call to classify gold-sector relevance on 0-1 scale.

    Falls back to keyword-based scoring if Anthropic API is unavailable.
    """
    try:
        response = await client.messages.create(
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
            title[:50],
            type(exc).__name__,
        )
        return _keyword_relevance(title, summary)


# ---------------------------------------------------------------------------
# fetch_stories() — shared SerpAPI + RSS ingestion with 30-min TTL cache
# ---------------------------------------------------------------------------

# Process-local cache. Keyed on the 30-minute timestamp bucket
# (``int(time.time() // 1800)``). Each sub-agent calls fetch_stories() as
# part of its own run_draft_cycle(); within a single 30-min window all callers
# share the cached result. Railway runs the scheduler as a single worker so
# this is safe. Not exposed publicly — tests should monkeypatch via
# ``content_agent._STORIES_CACHE`` if they need to clear it.
_STORIES_CACHE: dict[int, list[dict]] = {}

# _FETCH_IN_FLIGHT maps a bucket key → asyncio.Future whose result is the
# scored story list for that bucket. When a second caller arrives mid-fetch
# it awaits the existing Future rather than starting a duplicate fetch.
# Protected by _CACHE_LOCK, which is held only for dict look-ups/mutations
# (microseconds) — never during Anthropic calls. This is the coalesce pattern:
# one in-flight fetch shared by all concurrent callers, with NO long-held lock.
# Root cause of the prior deadlock: the old implementation held _CACHE_LOCK
# across 100+ sequential _score_relevance Anthropic calls (worst case
# 118 × 30 s = 3,540 s), blocking every other fetch_stories caller.
# (quick-260427-m51: replaces kro's 30 s timeout band-aid)
_FETCH_IN_FLIGHT: dict[int, "asyncio.Future[list[dict]]"] = {}
_CACHE_LOCK: asyncio.Lock = asyncio.Lock()


def _cache_bucket() -> int:
    """Return the current 30-minute timestamp bucket key."""
    return int(time.time() // 1800)


async def _do_fetch(bucket: int) -> list[dict]:
    """Execute one full fetch-score-classify cycle for ``bucket``.

    Caller is responsible for registering / resolving the in-flight Future
    and writing the result to _STORIES_CACHE. This function does the work
    only — no lock is held during any await inside here.
    """
    settings = get_settings()
    # Per-request timeout keeps individual Anthropic calls bounded at 30 s.
    # With scoring now parallelised via asyncio.gather the worst-case wall
    # time for the whole fetch drops from ~118 × 30 s = 59 min to ~30 s.
    # v3.1 Phase 12 — fetch_stories powers Seva-only daily summary scoring;
    # routes through per-tenant resolver (D-07, D-09 + planner-flagged
    # LIVE-site reclassification of line 1108 from CONTEXT.md's dead list).
    anthropic_client = get_anthropic_client("seva", timeout=30.0)
    serpapi_client = (
        serpapi.Client(api_key=settings.serpapi_api_key) if settings.serpapi_api_key else None
    )

    try:
        rss_stories, serpapi_stories = await asyncio.gather(
            _fetch_all_rss(),
            _fetch_all_serpapi(serpapi_client),
        )
    except Exception as exc:  # noqa: BLE001 — fetch-failure: return []
        logger.warning(
            "fetch_stories: ingestion failed (%s) — returning empty list",
            type(exc).__name__,
        )
        return []

    all_stories = rss_stories + serpapi_stories
    logger.info(
        "fetch_stories ingested %d stories (%d RSS, %d SerpAPI)",
        len(all_stories),
        len(rss_stories),
        len(serpapi_stories),
    )

    unique_stories = deduplicate_stories(all_stories)
    if not unique_stories:
        return []

    # Score all stories in parallel via asyncio.gather — eliminates the
    # sequential bottleneck that was the root cause of the cache-lock starvation
    # (previously one await per story in a for-loop while holding _CACHE_LOCK).
    rel_weight, rec_weight, cred_weight = 0.4, 0.3, 0.3

    async def _score_story(story: dict) -> dict:
        relevance = await _score_relevance(
            story["title"], story.get("summary", ""), client=anthropic_client
        )
        rec = recency_score(story["published"])
        cred = credibility_score(story.get("source_name", ""))
        story["score"] = (relevance * rel_weight + rec * rec_weight + cred * cred_weight) * 10
        return story

    scored: list[dict] = list(
        await asyncio.gather(*[_score_story(s) for s in unique_stories])
    )

    # Predicted format via lightweight Haiku classifier (already parallelised).
    try:
        format_labels = await asyncio.gather(
            *[classify_format_lightweight(s, client=anthropic_client) for s in scored]
        )
        for s, fmt in zip(scored, format_labels):
            s["predicted_format"] = fmt
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "fetch_stories: format classifier batch failed (%s) — defaulting all to 'thread'",
            type(exc).__name__,
        )
        for s in scored:
            s["predicted_format"] = "thread"

    return scored


async def fetch_stories() -> list[dict]:
    """Shared SerpAPI + RSS ingestion with TTL-30min in-memory cache.

    Keyed on ``int(time.time() // 1800)`` — every 30-minute wall-clock bucket
    gets one network fetch; within that bucket, every caller gets the cached
    list. Process-local cache; Railway's scheduler runs as a single worker so
    multiple sub-agents firing back-to-back within their stagger window all
    share one fetch.

    Concurrency model (coalesce pattern — quick-260427-m51):
    - _CACHE_LOCK is held ONLY for microsecond dict operations (read, write,
      Future registration). It is NEVER held during Anthropic API calls.
    - When a fetch is already in progress for the current bucket, new callers
      await the existing Future rather than starting a duplicate fetch.
    - Scoring runs via asyncio.gather (parallel), so worst-case wall time for
      ~120 stories drops from 118 × 30 s = 59 min to ~30 s.

    On cache miss this runs:
        1. RSS ingestion (``_fetch_all_rss``)
        2. SerpAPI ingestion (``_fetch_all_serpapi``)
        3. Dedup (``deduplicate_stories``)
        4. Relevance scoring — parallel asyncio.gather over ``_score_relevance``
        5. Composite score (``calculate_story_score`` via inline formula)
        6. Lightweight format classification (``classify_format_lightweight``)

    Each story returned includes ``score`` (0-10) and ``predicted_format``
    (one of breaking_news/thread/infographic/quote). Sub-agents
    filter this list by ``predicted_format`` (or by content-type specific
    eligibility rules) before drafting.

    Fetch failures log a warning and return [] — preserving the existing
    "skip this cycle on fetch failure" behavior.
    """
    bucket = _cache_bucket()

    # Fast path: bucket already populated (no lock needed for a dict read in
    # CPython — GIL protects the reference, and asyncio is single-threaded).
    cached = _STORIES_CACHE.get(bucket)
    if cached is not None:
        return cached

    # Determine whether WE are the designated fetcher or a waiter.
    # we_own is set inside the lock so no other coroutine can race on this
    # decision (asyncio is single-threaded; the lock serialises the check).
    fut: "asyncio.Future[list[dict]]"
    we_own: bool
    async with _CACHE_LOCK:
        # Re-check under the lock: another coroutine may have just populated
        # the cache or registered an in-flight Future.
        cached = _STORIES_CACHE.get(bucket)
        if cached is not None:
            return cached

        if bucket in _FETCH_IN_FLIGHT:
            # Another coroutine is already fetching — coalesce onto its Future.
            fut = _FETCH_IN_FLIGHT[bucket]
            we_own = False
        else:
            # We are first — register a Future so concurrent callers coalesce.
            loop = asyncio.get_event_loop()
            fut = loop.create_future()
            _FETCH_IN_FLIGHT[bucket] = fut
            we_own = True

            # Evict stale cache buckets while we hold the lock (cheap op).
            stale_keys = [k for k in _STORIES_CACHE if k < bucket]
            for k in stale_keys:
                _STORIES_CACHE.pop(k, None)

    # Lock is released here. All awaits below happen OUTSIDE the lock,
    # so no Anthropic or network I/O ever holds _CACHE_LOCK.

    if we_own:
        # We registered the Future — execute the fetch and resolve it.
        result: list[dict] = []
        try:
            result = await _do_fetch(bucket)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "fetch_stories: _do_fetch raised unexpectedly (%s) — resolving with []",
                type(exc).__name__,
            )
            result = []
        finally:
            # Write to cache and clean up in-flight entry (micro-hold on lock).
            async with _CACHE_LOCK:
                _STORIES_CACHE[bucket] = result
                _FETCH_IN_FLIGHT.pop(bucket, None)
            # Resolve the Future so all waiters unblock.
            if not fut.done():
                fut.set_result(result)
        return result
    else:
        # Another coroutine owns the fetch — await the shared Future.
        return await fut
