"""
Content Agent — review-service-only module.

Post quick-260421-eoe, the Content Agent is NO LONGER a scheduled agent. It is a
library module that the 7 content sub-agents (under scheduler/agents/content/)
call into. It exposes:

- ``fetch_stories()``: Shared SerpAPI + RSS ingestion with a 30-min in-memory
  cache keyed on ``int(time.time() // 1800)``. Returns scored, deduped stories
  with ``predicted_format`` labels so each sub-agent can filter to its own
  content_type. Process-local cache — Railway runs the scheduler as a single
  worker, so this is safe.
- ``review(draft)``: Haiku compliance gate. Pure function over a draft dict;
  no DB I/O. Returns ``{"compliance_passed": bool, "rationale": str}``.
- ``classify_format_lightweight(story, *, client)``: Retained helper export.
  Returns one of ``breaking_news | thread | long_form | infographic | quote``.

Sub-agents are responsible for the per-story deep research + drafting + persistence.
This module also keeps a handful of shared helpers the sub-agents call directly:
``fetch_article`` / ``extract_article_text`` / ``deduplicate_stories`` /
``recency_score`` / ``credibility_score`` / ``calculate_story_score`` /
``is_gold_relevant_or_systemic_shock`` / ``build_draft_item`` /
``build_no_story_bundle`` / ``check_compliance`` / ``_extract_check_text``.

Requirements: CONT-01 through CONT-17 (coverage split across the 7 sub-agents).
"""
from __future__ import annotations

import asyncio
import difflib
import json
import logging
import time
from datetime import datetime, timezone

import feedparser
import httpx
import serpapi
from anthropic import AsyncAnthropic
from bs4 import BeautifulSoup

from config import get_settings

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

    Returns one of: breaking_news | thread | long_form | infographic | quote.
    Fail-open: returns "thread" (current ambiguous default) on any error or
    unexpected output.
    """
    valid_formats = {"breaking_news", "thread", "long_form", "infographic", "quote"}
    try:
        response = await client.messages.create(
            model="claude-haiku-4-5",
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
                logger.warning("Article fetch %s returned %d, using fallback", url, resp.status_code)
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
            return serpapi_client.search({
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


# ---------------------------------------------------------------------------
# Compliance checker — fail-safe pattern (CONT-14, CONT-15, CONT-16)
# ---------------------------------------------------------------------------

async def check_compliance(text: str, anthropic_client=None) -> bool:
    """Check content for compliance. Returns True only on explicit 'pass'.
    Fail-safe: ambiguous response = block (returns False).
    Pre-screens locally for 'seva mining' before calling Claude Haiku.
    """
    text_lower = text.lower()
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
    Bucket D: Gold-relevant but bearish-toward-gold sentiment → reject (new J7X rule).
    Everything else (off-topic, listicles, stock picks) → reject.

    Return shape:
        {"keep": bool, "reject_reason": str | None, "company": str | None, "sentiment": str | None}

    New reject_reason value:
        - "bearish_toward_gold"  (sentiment="bearish" from Haiku, when bearish filter on)

    Fail-open: API errors or malformed JSON return {"keep": True, ...} so infra
    blips never silence real gold stories.
    Bypassed when config key content_gold_gate_enabled is False.
    Bearish check alone bypassed when content_bearish_filter_enabled is False.

    Requirements: NNH-01, NNH-02, NNH-03, NNH-04, NNH-05, J7X-01, J7X-02, J7X-03, J7X-04, J7X-05, J7X-06.
    """
    _KEEP = {"keep": True, "reject_reason": None, "company": None, "sentiment": None}

    enabled_str = config.get("content_gold_gate_enabled", "true")
    if str(enabled_str).lower() in ("false", "0", "no"):
        return _KEEP

    bearish_enabled_str = config.get("content_bearish_filter_enabled", "true")
    bearish_filter_on = str(bearish_enabled_str).lower() not in ("false", "0", "no")

    title = story.get("title", "")
    summary = story.get("summary", "")
    model = config.get("content_gold_gate_model", "claude-haiku-4-5")

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
                "these are sources, not subjects. Their presence does NOT trigger is_gold_relevant=false rejection — but the forecast's direction still determines sentiment (a bearish forecast from Goldman/Morgan Stanley yields sentiment=bearish and is rejected by the bearish filter).\n\n"
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
                "REJECT — bearish_toward_gold\n"
                "(is_gold_relevant=true but sentiment=\"bearish\") if the story's angle\n"
                "is negative toward gold or its price. Three categories:\n"
                "  1. Price-bearish forecasts or predictions: analyst cuts gold price\n"
                "     target, bank downgrades gold outlook, \"expect pullback/correction\"\n"
                "     framing. Example: \"Morgan Stanley cuts gold price forecast by ~10%\".\n"
                "  2. Anti-gold narrative: gold dismissed in favor of alternatives,\n"
                "     gold losing relevance/appeal, bitcoin/crypto replacing gold.\n"
                "     Example: \"Bitcoin replaces gold as reserve asset of choice\".\n"
                "  3. Factual-negative price movement: gold fell / dropped / slumped /\n"
                "     pulled back. Example: \"Gold fell 1.2% today on stronger dollar\".\n"
                "DIRECTION matters, not the word \"forecast\": upside forecasts\n"
                "(\"Goldman sees gold at $4K\") are sentiment=\"bullish\" and KEPT.\n"
                "Neutral factual (\"gold hits new record high\") is sentiment=\"neutral\"\n"
                "and KEPT.\n"
                "Mixed or flat movement stories (\"gold holds steady\", \"gold flat\", \"gold mixed\") are sentiment=\"neutral\" and KEPT.\n\n"
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
                '"company": null|"<company name if primary_subject_is_specific_miner is true>", '
                '"sentiment": "bullish"|"neutral"|"bearish"}'
            ),
            messages=[{"role": "user", "content": f"Title: {title}\nSummary: {summary}"}],
        )
        raw = response.content[0].text.strip()
        try:
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.rsplit("```", 1)[0].strip()
            parsed = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            logger.warning(
                "Gold gate returned non-JSON for '%s' — fail-open (keeping story): %r",
                title[:50], raw[:80],
            )
            return _KEEP

        is_gold = bool(parsed.get("is_gold_relevant", True))
        is_specific_miner = bool(parsed.get("primary_subject_is_specific_miner", False))
        company_raw = parsed.get("company")
        company = str(company_raw).strip() if company_raw else None
        if not company:
            company = None

        sentiment_raw = parsed.get("sentiment")
        sentiment = str(sentiment_raw).strip().lower() if sentiment_raw else None
        if sentiment not in ("bullish", "neutral", "bearish"):
            sentiment = None  # defensive: unknown → treat as missing (fail-open on this axis)

        if not is_gold:
            return {"keep": False, "reject_reason": "not_gold_relevant", "company": None, "sentiment": sentiment}
        if is_specific_miner:
            return {
                "keep": False,
                "reject_reason": "primary_subject_is_specific_miner",
                "company": company,
                "sentiment": sentiment,
            }
        if bearish_filter_on and sentiment == "bearish":
            logger.info(
                "Gold gate rejected bearish-toward-gold: %r (sentiment=bearish)",
                title[:60],
            )
            return {
                "keep": False,
                "reject_reason": "bearish_toward_gold",
                "company": None,
                "sentiment": "bearish",
            }
        return {"keep": True, "reject_reason": None, "company": None, "sentiment": sentiment}

    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Gold gate API failed for '%s' (%s) — fail-open (keeping story)",
            title[:50], type(exc).__name__,
        )
        return _KEEP


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

    elif fmt == "long_form":
        draft_text = draft.get("post", "")

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
            parts.append("=== Instagram Carousel ===\n" + "\n\n".join(
                f"Slide {i+1}: {slide}" if isinstance(slide, str) else f"Slide {i+1}: {slide.get('text', '')}"
                for i, slide in enumerate(carousel)
            ))
        draft_text = "\n\n".join(parts) if parts else f"Gold History: {draft.get('story_title', '')}"

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
# Draft text extractor for compliance checking (used by review())
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
        # Do NOT compliance-check image_prompt — brand preamble + derived text, not novel content
    elif fmt == "gold_history":
        parts.extend(draft_content.get("tweets", []))
        for slide in draft_content.get("instagram_carousel", []):
            if isinstance(slide, dict):
                parts.append(slide.get("headline", ""))
                parts.append(slide.get("body", ""))
        parts.append(draft_content.get("instagram_caption", ""))
    elif fmt == "gold_media":
        parts.append(draft_content.get("twitter_caption", ""))
        parts.append(draft_content.get("instagram_caption", ""))
    elif fmt == "quote":
        parts.append(draft_content.get("twitter_post", ""))
        parts.append(draft_content.get("quote_text", ""))
        parts.append(draft_content.get("suggested_headline", ""))
        parts.extend(draft_content.get("data_facts", []) or [])
        # Do NOT compliance-check image_prompt
    return " ".join(p for p in parts if p)


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


async def _fetch_all_serpapi(serpapi_client: "serpapi.Client | None") -> list[dict]:
    """CONT-03: Run SerpAPI keyword searches concurrently via asyncio.gather + run_in_executor."""
    if serpapi_client is None:
        logger.warning("SerpAPI key not configured — skipping keyword searches, using RSS only.")
        return []
    loop = asyncio.get_event_loop()
    tasks = []
    for keyword in SERPAPI_KEYWORDS:
        def _call(q=keyword):
            return serpapi_client.search({
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


def _keyword_relevance(title: str, summary: str) -> float:
    """Fast keyword-based relevance score as fallback when Anthropic is unavailable.

    Counts gold/mining keyword hits and returns a 0.0-1.0 score.
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
            title[:50], type(exc).__name__,
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
_CACHE_LOCK: asyncio.Lock = asyncio.Lock()


def _cache_bucket() -> int:
    """Return the current 30-minute timestamp bucket key."""
    return int(time.time() // 1800)


async def fetch_stories() -> list[dict]:
    """Shared SerpAPI + RSS ingestion with TTL-30min in-memory cache.

    Keyed on ``int(time.time() // 1800)`` — every 30-minute wall-clock bucket
    gets one network fetch; within that bucket, every caller gets the cached
    list. Process-local cache; Railway's scheduler runs as a single worker so
    multiple sub-agents firing back-to-back within their stagger window all
    share one fetch.

    On cache miss under the module-level asyncio.Lock, this runs the ingestion
    stage that ``ContentAgent._run_pipeline`` used to run inline:

        1. RSS ingestion (``_fetch_all_rss``)
        2. SerpAPI ingestion (``_fetch_all_serpapi``)
        3. Dedup (``deduplicate_stories``)
        4. Relevance scoring per story (``_score_relevance``)
        5. Composite score (``calculate_story_score`` via inline formula)
        6. Lightweight format classification (``classify_format_lightweight``)

    Each story returned includes ``score`` (0-10) and ``predicted_format``
    (one of breaking_news/thread/long_form/infographic/quote). Sub-agents
    filter this list by ``predicted_format`` (or by content-type specific
    eligibility rules) before drafting.

    Fetch failures log a warning and return [] — preserving the existing
    "skip this cycle on fetch failure" behavior.
    """
    bucket = _cache_bucket()

    # Fast path: bucket already populated.
    cached = _STORIES_CACHE.get(bucket)
    if cached is not None:
        return cached

    async with _CACHE_LOCK:
        # Re-check under the lock in case another coroutine just populated it.
        cached = _STORIES_CACHE.get(bucket)
        if cached is not None:
            return cached

        # Evict any stale buckets to keep the cache bounded.
        stale_keys = [k for k in _STORIES_CACHE if k < bucket]
        for k in stale_keys:
            _STORIES_CACHE.pop(k, None)

        settings = get_settings()
        anthropic_client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        serpapi_client = (
            serpapi.Client(api_key=settings.serpapi_api_key)
            if settings.serpapi_api_key
            else None
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
            _STORIES_CACHE[bucket] = []
            return []

        all_stories = rss_stories + serpapi_stories
        logger.info(
            "fetch_stories ingested %d stories (%d RSS, %d SerpAPI)",
            len(all_stories), len(rss_stories), len(serpapi_stories),
        )

        unique_stories = deduplicate_stories(all_stories)
        if not unique_stories:
            _STORIES_CACHE[bucket] = []
            return []

        # Score and classify each unique story (relevance + recency + credibility).
        # Use default weights — sub-agents can re-score if they override, but the
        # shared cache uses the CONT-05 defaults (0.4 / 0.3 / 0.3).
        rel_weight, rec_weight, cred_weight = 0.4, 0.3, 0.3
        scored: list[dict] = []
        for story in unique_stories:
            relevance = await _score_relevance(
                story["title"], story.get("summary", ""), client=anthropic_client
            )
            rec = recency_score(story["published"])
            cred = credibility_score(story.get("source_name", ""))
            story["score"] = (
                relevance * rel_weight + rec * rec_weight + cred * cred_weight
            ) * 10
            scored.append(story)

        # Predicted format via lightweight Haiku classifier.
        try:
            format_labels = await asyncio.gather(*[
                classify_format_lightweight(s, client=anthropic_client) for s in scored
            ])
            for s, fmt in zip(scored, format_labels):
                s["predicted_format"] = fmt
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "fetch_stories: format classifier batch failed (%s) — defaulting all to 'thread'",
                type(exc).__name__,
            )
            for s in scored:
                s["predicted_format"] = "thread"

        _STORIES_CACHE[bucket] = scored
        return scored


# ---------------------------------------------------------------------------
# review(draft) — Haiku compliance gate (no DB I/O)
# ---------------------------------------------------------------------------

async def review(draft: dict) -> dict:
    """Haiku compliance gate. Pure function — no DB I/O.

    Extracts the checkable text from the draft_content payload (via
    ``_extract_check_text``) and runs the shared ``check_compliance`` helper.
    Sub-agents call this inline before writing their ContentBundle row.

    Args:
        draft: The draft_content dict a sub-agent produced. Must contain a
               ``format`` key matching one of the known content_type values.

    Returns:
        ``{"compliance_passed": bool, "rationale": str}``. ``rationale`` is
        a short English string for logging/audit — NOT guaranteed stable
        wording; consumers should key off ``compliance_passed`` only.
    """
    check_text = _extract_check_text(draft)
    if not check_text:
        # Nothing to check — treat as pass, but note it for audit.
        return {"compliance_passed": True, "rationale": "no checkable text"}

    passed = await check_compliance(check_text)
    if passed:
        return {"compliance_passed": True, "rationale": "haiku pass"}
    return {
        "compliance_passed": False,
        "rationale": "haiku blocked (seva mining mention or financial advice)",
    }
