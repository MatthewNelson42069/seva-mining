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

import feedparser
import httpx
import serpapi
from anthropic import AsyncAnthropic
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
# Draft text extractor for compliance checking
# ---------------------------------------------------------------------------

def _extract_check_text(draft_content: dict) -> str:
    """Extract all text from draft_content for compliance checking."""
    fmt = draft_content.get("format", "")
    parts = []
    if fmt == "thread":
        parts.extend(draft_content.get("tweets", []))
        parts.append(draft_content.get("long_form_post", ""))
    elif fmt == "long_form":
        parts.append(draft_content.get("post", ""))
    elif fmt == "infographic":
        parts.append(draft_content.get("headline", ""))
        parts.append(draft_content.get("caption_text", ""))
        for stat in draft_content.get("key_stats", []):
            parts.append(stat.get("stat", ""))
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

    async def _get_config(self, session: AsyncSession, key: str, default: str) -> str:
        """Read a config value from the DB by key. Returns default if not found."""
        result = await session.execute(select(Config).where(Config.key == key))
        row = result.scalar_one_or_none()
        return row.value if row else default

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
                published = (
                    datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
                    if iso_date else datetime.now(timezone.utc)
                )
                source_name = (item.get("source") or {}).get("name", "unknown")
                stories.append({
                    "title": item.get("title", ""),
                    "link": item.get("link", ""),
                    "published": published,
                    "summary": item.get("snippet", ""),
                    "source_name": source_name,
                })
        return stories

    async def _score_relevance(self, title: str, summary: str) -> float:
        """CONT-05: Claude Haiku call to classify gold-sector relevance on 0-1 scale."""
        try:
            response = await self.anthropic.messages.create(
                model="claude-haiku-3-20240307",
                max_tokens=10,
                system="Rate the relevance of this news story to the gold mining and precious metals sector on a scale of 0.0 to 1.0. Reply with only a decimal number.",
                messages=[{"role": "user", "content": f"Title: {title}\nSummary: {summary}"}],
            )
            score = float(response.content[0].text.strip())
            return max(0.0, min(1.0, score))
        except Exception as exc:
            logger.warning("Relevance scoring failed for '%s': %s", title[:50], exc)
            return 0.5  # Neutral default on failure

    async def _run_pipeline(self, session: AsyncSession, agent_run: AgentRun) -> None:
        """CONT-01: Orchestrate the full ingest-dedup-score-research-draft-comply-persist flow."""
        # 1. Read config
        threshold = float(await self._get_config(session, "content_quality_threshold", "7.0"))
        rel_weight = float(await self._get_config(session, "content_relevance_weight", "0.40"))
        rec_weight = float(await self._get_config(session, "content_recency_weight", "0.30"))
        cred_weight = float(await self._get_config(session, "content_credibility_weight", "0.30"))

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

        # 3. Deduplicate
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

        # 5. Select top story
        top = select_top_story(scored, threshold=threshold)

        if top is None:
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

        # 6. Deep research
        article_text, fetch_ok = await fetch_article(top["link"], fallback_text=top.get("summary", ""))
        corroborating = await self._search_corroborating(top["title"])
        deep_research = {
            "article_text": article_text[:5000],  # Cap at 5000 chars
            "article_fetch_succeeded": fetch_ok,
            "corroborating_sources": corroborating,
            "key_data_points": [],  # Filled by Sonnet prompt
        }

        # 7. Format decision + drafting (combined Sonnet call)
        draft_result = await self._research_and_draft(top, deep_research)
        if draft_result is None:
            logger.error("Drafting failed for '%s'", top["title"][:60])
            from models.content_bundle import ContentBundle  # noqa: PLC0415
            bundle = ContentBundle(
                story_headline=top["title"],
                story_url=top["link"],
                source_name=top.get("source_name"),
                score=top["score"],
                deep_research=deep_research,
                compliance_passed=False,
            )
            session.add(bundle)
            agent_run.errors = "Drafting failed — Claude returned unparseable response"
            return
        draft_content, deep_research, rationale = draft_result

        # 8. Compliance check
        check_text = _extract_check_text(draft_content)
        compliance_ok = await check_compliance(check_text, self.anthropic)

        # 9. Persist ContentBundle
        from models.content_bundle import ContentBundle  # noqa: PLC0415
        bundle = ContentBundle(
            story_headline=top["title"],
            story_url=top["link"],
            source_name=top.get("source_name"),
            content_type=draft_content.get("format"),
            score=top["score"],
            deep_research=deep_research,
            draft_content=draft_content,
            compliance_passed=compliance_ok,
        )
        session.add(bundle)
        await session.flush()  # Get bundle.id

        if not compliance_ok:
            logger.warning("Compliance check failed for '%s'", top["title"][:60])
            agent_run.errors = "Compliance check failed — draft blocked"
            agent_run.notes = json.dumps({
                "story": top["title"][:200],
                "score": float(top["score"]),
                "blocked": True,
            })
            return

        # 10. Create DraftItem + call Senior Agent
        item = build_draft_item(bundle, rationale)
        session.add(item)
        await session.flush()  # Get item.id

        # Lazy import to avoid circular deps
        from agents.senior_agent import process_new_items  # noqa: PLC0415
        await process_new_items([item.id])

        agent_run.items_queued = 1
        agent_run.notes = json.dumps({
            "story": top["title"][:200],
            "score": float(top["score"]),
            "format": draft_content.get("format"),
            "content_bundle_id": str(bundle.id),
        })
        logger.info(
            "Content Agent queued: '%s' (score=%.1f, format=%s)",
            top["title"][:60], top["score"], draft_content.get("format"),
        )

    async def run(self) -> None:
        """Entry point called by APScheduler. Runs the full pipeline."""
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
