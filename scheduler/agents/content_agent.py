"""
Content Agent — ingest, deduplicate, score, and select daily gold sector stories.

Monitors RSS feeds (Kitco, Mining.com, JMN, WGC) and SerpAPI news search every
~6 hours for qualifying stories. Applies scoring (relevance, recency, credibility),
deduplication (URL + headline similarity), and selects the single highest-scoring
story above the 7.0/10 quality threshold.

Requirements: CONT-01 through CONT-17
"""
from __future__ import annotations

import asyncio
import difflib
import json
import logging
from datetime import datetime, timezone

import httpx
import serpapi
from anthropic import AsyncAnthropic
from bs4 import BeautifulSoup

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
    import json  # noqa: PLC0415
    from models.draft_item import DraftItem  # noqa: PLC0415

    # Build a brief summary from draft_content for the alternatives field
    draft = content_bundle.draft_content or {}
    fmt = draft.get("format", "unknown")
    if fmt == "thread":
        summary = f"Thread ({len(draft.get('tweets', []))} tweets) + long-form post"
    elif fmt == "long_form":
        summary = f"Long-form post ({len(draft.get('post', ''))} chars)"
    elif fmt == "infographic":
        summary = f"Infographic brief: {draft.get('headline', 'N/A')}"
    else:
        summary = f"Content draft ({fmt})"

    return DraftItem(
        platform="content",
        source_text=content_bundle.story_headline,
        source_url=content_bundle.story_url,
        source_account=content_bundle.source_name,
        alternatives=json.dumps([summary]),
        rationale=rationale,
        score=float(content_bundle.score) if content_bundle.score else 0.0,
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
# ContentAgent class skeleton (CONT-01)
# ---------------------------------------------------------------------------

class ContentAgent:
    """Content Agent — RSS + SerpAPI ingestion, scoring, dedup, draft pipeline.

    Requirements: CONT-01 through CONT-17
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.anthropic = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.serpapi_client = serpapi.Client(api_key=settings.serpapi_api_key)

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

        user_prompt = f"""Based on the following research, produce original content for publication on X (Twitter).

## Story
Headline: {story.get('title', '')}
Source: {story.get('source_name', '')} ({story.get('link', '')})

## Full Article
{article_block}

## Corroborating Sources
{corr_lines}

## Instructions
1. Extract 5-8 key data points from the research (numbers, percentages, dates, production figures).
2. Decide the best format for this content:
   - "thread" — for multi-faceted stories that benefit from sequential presentation (produces BOTH a tweet thread of 3-5 tweets each <=280 chars AND a single long-form X post <=2200 chars)
   - "long_form" — for focused stories that work as a single extended post (<=2200 chars)
   - "infographic" — for data-heavy stories with strong visual potential (produces headline, 5-8 key stats with sources, visual structure suggestion from ["bar chart", "timeline", "comparison table", "stat callouts", "map"], and full caption text)
3. Draft the content in your chosen format.
4. Provide a brief rationale for your format choice (1-2 sentences).

Respond in valid JSON with this structure:
{{
  "format": "thread" | "long_form" | "infographic",
  "rationale": "...",
  "key_data_points": ["...", "..."],
  "draft_content": {{ ... }}
}}

For "thread" format, draft_content must have: {{"format": "thread", "tweets": ["t1", ...], "long_form_post": "..."}}
For "long_form" format, draft_content must have: {{"format": "long_form", "post": "..."}}
For "infographic" format, draft_content must have: {{"format": "infographic", "headline": "...", "key_stats": [{{"stat": "...", "source": "...", "source_url": "..."}}], "visual_structure": "bar chart", "caption_text": "..."}}"""

        system_prompt = (
            "You are a senior gold market analyst. You produce original content about the gold and mining sector "
            "based on research provided. You write in a data-driven, measured tone. You cite specific numbers, "
            "dates, and sources. You never mention Seva Mining. You never give financial advice. You never use "
            'phrases like "buy", "sell", "invest in", "I recommend", or "you should".'
        )

        try:
            response = await self.anthropic.messages.create(
                model="claude-sonnet-4-20250514",
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

        # Update deep_research with extracted key data points
        updated_research = dict(deep_research)
        updated_research["key_data_points"] = key_data_points

        return draft_content, updated_research, rationale

    async def run(self) -> None:
        """Entry point called by APScheduler. Full pipeline implemented in Plan 05."""
        # Full pipeline — implemented in Plan 05
        pass
