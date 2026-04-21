"""Tests for content_agent — review-service-only module (post quick-260421-eoe).

The pre-split test_content_agent.py covered the monolithic ContentAgent class
(run/_run_pipeline, every _draft_* helper, whatsapp handoff, etc). Those
tests were retired alongside the methods they covered. This file now covers
only the public surface the 7 content sub-agents depend on:

- ``fetch_stories()``: 30-min TTL cache + fetch-failure handling.
- ``review(draft)``: Haiku compliance gate return shape.
- ``classify_format_lightweight(story, *, client)``: fixed string set.

Per-format drafting and pipeline behavior is covered in the per-agent test
files (test_breaking_news.py, test_threads.py, ...). Scoring / dedup / gold
gate helpers are covered inline here because they remain module-level in
content_agent.py and have no sub-agent-specific equivalent.
"""
import os
import sys
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Env vars must be set before importing settings-bound modules.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://fake-pooler.neon.tech/db?sslmode=require")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test-fake")
os.environ.setdefault("TWILIO_ACCOUNT_SID", "x")
os.environ.setdefault("TWILIO_AUTH_TOKEN", "x")
os.environ.setdefault("TWILIO_WHATSAPP_FROM", "whatsapp:+1x")
os.environ.setdefault("DIGEST_WHATSAPP_TO", "whatsapp:+1x")
os.environ.setdefault("X_API_BEARER_TOKEN", "test-bearer-token")
os.environ.setdefault("X_API_KEY", "test-key")
os.environ.setdefault("X_API_SECRET", "test-secret")
os.environ.setdefault("SERPAPI_API_KEY", "x")
os.environ.setdefault("FRONTEND_URL", "https://x.com")

from agents import content_agent  # noqa: E402


# ---------------------------------------------------------------------------
# Module-level constants — retained after split
# ---------------------------------------------------------------------------

def test_rss_feeds_constant_preserved():
    """RSS_FEEDS constant is preserved and reachable (CONT-02)."""
    assert len(content_agent.RSS_FEEDS) == 7
    assert any("kitco" in url for url, _ in content_agent.RSS_FEEDS)


def test_serpapi_keywords_constant_preserved():
    """SERPAPI_KEYWORDS is preserved (CONT-03)."""
    assert len(content_agent.SERPAPI_KEYWORDS) == 10
    assert "gold price" in content_agent.SERPAPI_KEYWORDS


# ---------------------------------------------------------------------------
# fetch_stories() — shared SerpAPI + RSS ingestion with 30-min TTL cache
# ---------------------------------------------------------------------------

def _clear_cache():
    content_agent._STORIES_CACHE.clear()


@pytest.mark.asyncio
async def test_fetch_stories_cache_hit_same_bucket():
    """Two calls within the same 30-min bucket issue one underlying fetch."""
    _clear_cache()
    stories = [{"title": "GOLD NEWS", "summary": "...", "link": "http://a",
                "source_name": "kitco.com", "published": None}]

    bucket = content_agent._cache_bucket()
    # Seed the cache directly — if fetch_stories respects the cache, no fetch
    # is invoked and the function returns our pre-seeded list.
    content_agent._STORIES_CACHE[bucket] = stories

    with patch.object(content_agent, "_fetch_all_rss", new=AsyncMock()) as mock_rss, \
         patch.object(content_agent, "_fetch_all_serpapi", new=AsyncMock()) as mock_serp:
        first = await content_agent.fetch_stories()
        second = await content_agent.fetch_stories()

    assert first is stories
    assert second is stories
    mock_rss.assert_not_called()
    mock_serp.assert_not_called()


@pytest.mark.asyncio
async def test_fetch_stories_cache_miss_new_bucket():
    """Advancing past the 30-min bucket triggers a second underlying fetch."""
    _clear_cache()

    # Put a value in an old bucket; current bucket should miss.
    old_bucket = content_agent._cache_bucket() - 1
    content_agent._STORIES_CACHE[old_bucket] = [{"title": "stale"}]

    fetched = [{"title": "fresh", "summary": "", "link": "http://b",
                "source_name": "kitco.com",
                "published": None}]

    with patch.object(content_agent, "_fetch_all_rss", new=AsyncMock(return_value=fetched)), \
         patch.object(content_agent, "_fetch_all_serpapi", new=AsyncMock(return_value=[])), \
         patch.object(content_agent, "deduplicate_stories", return_value=fetched), \
         patch.object(content_agent, "_score_relevance", new=AsyncMock(return_value=0.5)), \
         patch.object(content_agent, "recency_score", return_value=0.9), \
         patch.object(content_agent, "credibility_score", return_value=0.8), \
         patch.object(content_agent, "classify_format_lightweight",
                      new=AsyncMock(return_value="thread")):
        result = await content_agent.fetch_stories()

    assert len(result) == 1
    assert result[0]["title"] == "fresh"
    # Old bucket should have been evicted.
    assert old_bucket not in content_agent._STORIES_CACHE


@pytest.mark.asyncio
async def test_fetch_stories_fetch_failure_returns_empty():
    """Ingestion exceptions produce [] and log a warning, not re-raise."""
    _clear_cache()

    with patch.object(content_agent, "_fetch_all_rss",
                      new=AsyncMock(side_effect=RuntimeError("network down"))), \
         patch.object(content_agent, "_fetch_all_serpapi",
                      new=AsyncMock(return_value=[])):
        result = await content_agent.fetch_stories()

    assert result == []
    # Result is cached for the bucket so subsequent calls don't re-try.
    bucket = content_agent._cache_bucket()
    assert content_agent._STORIES_CACHE[bucket] == []


def test_cache_bucket_matches_30_min_formula():
    """_cache_bucket returns int(time.time() // 1800) at call time."""
    expected = int(time.time() // 1800)
    assert content_agent._cache_bucket() == expected


# ---------------------------------------------------------------------------
# review(draft) — Haiku compliance gate
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_review_pass_returns_compliance_passed_true():
    """When check_compliance passes, review returns compliance_passed=True."""
    draft = {"format": "breaking_news", "tweet": "Gold at $2400."}
    with patch.object(content_agent, "check_compliance",
                      new=AsyncMock(return_value=True)):
        result = await content_agent.review(draft)
    assert result["compliance_passed"] is True
    assert "rationale" in result


@pytest.mark.asyncio
async def test_review_fail_returns_compliance_passed_false():
    """When check_compliance fails, review returns compliance_passed=False + rationale."""
    draft = {"format": "breaking_news", "tweet": "You should buy gold now."}
    with patch.object(content_agent, "check_compliance",
                      new=AsyncMock(return_value=False)):
        result = await content_agent.review(draft)
    assert result["compliance_passed"] is False
    assert result["rationale"]


@pytest.mark.asyncio
async def test_review_empty_draft_treated_as_pass():
    """Drafts with no extractable text short-circuit to compliance_passed=True."""
    # A draft with no known format and no checkable text → _extract_check_text = ""
    # review() must treat empty text as pass (no compliance issue to flag).
    draft = {"format": "unknown_format"}
    with patch.object(content_agent, "_extract_check_text", return_value=""):
        result = await content_agent.review(draft)
    assert result["compliance_passed"] is True


# ---------------------------------------------------------------------------
# classify_format_lightweight — fixed string return set
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_classify_format_lightweight_returns_valid_format():
    """Classifier returns one of the 5 recognised format strings."""
    client = AsyncMock()
    response = MagicMock()
    response.content = [MagicMock(text="breaking_news")]
    client.messages.create = AsyncMock(return_value=response)

    result = await content_agent.classify_format_lightweight(
        {"title": "Gold hits record high", "summary": "short", "published": ""},
        client=client,
    )
    assert result == "breaking_news"


@pytest.mark.asyncio
async def test_classify_format_lightweight_fails_open_to_thread():
    """Any error in the Haiku call returns the 'thread' fallback."""
    client = AsyncMock()
    client.messages.create = AsyncMock(side_effect=RuntimeError("api down"))

    result = await content_agent.classify_format_lightweight(
        {"title": "x", "summary": "y", "published": ""},
        client=client,
    )
    assert result == "thread"


@pytest.mark.asyncio
async def test_classify_format_lightweight_clamps_invalid_output():
    """Unexpected classifier outputs are clamped to 'thread'."""
    client = AsyncMock()
    response = MagicMock()
    response.content = [MagicMock(text="some_new_format_we_do_not_support")]
    client.messages.create = AsyncMock(return_value=response)

    result = await content_agent.classify_format_lightweight(
        {"title": "x", "summary": "y", "published": ""},
        client=client,
    )
    assert result == "thread"


def test_classify_format_lightweight_returns_sub_agent_filter_strings():
    """The classifier's valid_formats set MUST match the 5 CONTENT_TYPE strings
    that text-story sub-agents filter on (per RESEARCH pitfall #6)."""
    import inspect
    source = inspect.getsource(content_agent.classify_format_lightweight)
    for expected in ("breaking_news", "thread", "long_form", "infographic", "quote"):
        assert f'"{expected}"' in source, f"missing classifier label {expected}"


# ---------------------------------------------------------------------------
# Compliance checker — retained module-level helper
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_compliance_screens_seva_mining_mention_locally():
    """check_compliance short-circuits on 'seva mining' substring — no API call."""
    client = AsyncMock()
    client.messages.create = AsyncMock()
    ok = await content_agent.check_compliance(
        "Seva Mining just hit a big drill result", anthropic_client=client
    )
    assert ok is False
    client.messages.create.assert_not_called()


@pytest.mark.asyncio
async def test_compliance_failsafe_on_api_error():
    """API errors during compliance check return False (fail-safe block)."""
    client = AsyncMock()
    client.messages.create = AsyncMock(side_effect=RuntimeError("rate limited"))
    ok = await content_agent.check_compliance(
        "A neutral gold market update", anthropic_client=client
    )
    assert ok is False


# ---------------------------------------------------------------------------
# Draft item / content bundle builder helpers — retained + used by sub-agents
# ---------------------------------------------------------------------------

def test_build_draft_item_stores_bundle_id_in_engagement_snapshot():
    """DraftItem.engagement_snapshot contains the content_bundle_id (pre-split pattern preserved)."""
    from uuid import uuid4
    bundle = MagicMock()
    bundle.id = uuid4()
    bundle.story_headline = "gold at record high"
    bundle.story_url = "http://example.com"
    bundle.source_name = "kitco"
    bundle.score = 8.5
    bundle.quality_score = None
    bundle.draft_content = {"format": "breaking_news", "tweet": "GOLD: $2500"}

    item = content_agent.build_draft_item(bundle, "test rationale")
    assert item.platform == "content"
    assert item.engagement_snapshot == {"content_bundle_id": str(bundle.id)}
