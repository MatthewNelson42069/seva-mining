"""
Tests for Content Agent — CONT-01 through CONT-17.
All tests use mocked feedparser, mocked anthropic, and mocked DB sessions.

Wave 0 state: agents.content_agent does not exist yet.
All 15 tests skip immediately (before any lazy import) so they are
collectable and show as SKIPPED (not ERROR) until implementation.
"""
import os
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Set required env vars before any imports
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://fake-pooler.neon.tech/db?sslmode=require")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test-fake")
os.environ.setdefault("TWILIO_ACCOUNT_SID", "x")
os.environ.setdefault("TWILIO_AUTH_TOKEN", "x")
os.environ.setdefault("TWILIO_WHATSAPP_FROM", "whatsapp:+1x")
os.environ.setdefault("DIGEST_WHATSAPP_TO", "whatsapp:+1x")
os.environ.setdefault("X_API_BEARER_TOKEN", "test-bearer-token")
os.environ.setdefault("X_API_KEY", "test-key")
os.environ.setdefault("X_API_SECRET", "test-secret")
os.environ.setdefault("APIFY_API_TOKEN", "test-apify-token")
os.environ.setdefault("SERPAPI_API_KEY", "x")
os.environ.setdefault("FRONTEND_URL", "https://x.com")


def _get_content_agent():
    """Import agents.content_agent lazily; only called after the skip guard in each test."""
    import importlib
    return importlib.import_module("agents.content_agent")


# ---------------------------------------------------------------------------
# CONT-02: RSS feed parsing
# ---------------------------------------------------------------------------

def test_rss_feed_parsing():
    """parse_rss_entries returns list of dicts with title, link, published, summary, source_name."""
    pytest.skip("Wave 0 stub — agents.content_agent not implemented yet")
    ca = _get_content_agent()
    # Mock feedparser.parse to return a fake feed with 2 entries
    # Verify returned list has keys: title, link, published, summary, source_name
    ...


# ---------------------------------------------------------------------------
# CONT-03: SerpAPI parsing
# ---------------------------------------------------------------------------

def test_serpapi_parsing():
    """parse_serpapi_results returns list of dicts with title, link, source_name, snippet, published."""
    pytest.skip("Wave 0 stub — agents.content_agent not implemented yet")
    ca = _get_content_agent()
    ...


# ---------------------------------------------------------------------------
# CONT-04: URL deduplication
# ---------------------------------------------------------------------------

def test_url_deduplication():
    """deduplicate_stories removes exact URL duplicates, keeps first occurrence."""
    pytest.skip("Wave 0 stub — agents.content_agent not implemented yet")
    ca = _get_content_agent()
    stories = [
        {"title": "Gold hits $3200", "link": "https://example.com/a", "source_name": "Reuters"},
        {"title": "Gold reaches $3200", "link": "https://example.com/a", "source_name": "Kitco"},
    ]
    result = ca.deduplicate_stories(stories)
    assert len(result) == 1
    assert result[0]["source_name"] == "Reuters"


# ---------------------------------------------------------------------------
# CONT-04: Headline deduplication
# ---------------------------------------------------------------------------

def test_headline_deduplication():
    """deduplicate_stories removes headline-similar (>=0.85) stories, keeps more credible source."""
    pytest.skip("Wave 0 stub — agents.content_agent not implemented yet")
    ca = _get_content_agent()
    stories = [
        {"title": "Gold price surges to record high of $3200", "link": "https://a.com/1", "source_name": "kitco.com"},
        {"title": "Gold price surges to a record high of $3200", "link": "https://b.com/2", "source_name": "reuters.com"},
    ]
    result = ca.deduplicate_stories(stories)
    assert len(result) == 1
    assert result[0]["source_name"] == "reuters.com"  # More credible


# ---------------------------------------------------------------------------
# CONT-05: Recency score
# ---------------------------------------------------------------------------

def test_recency_score():
    """recency_score returns 1.0 for <3h, 0.8 for <6h, 0.6 for <12h, 0.4 for <24h, 0.2 for >=24h."""
    pytest.skip("Wave 0 stub — agents.content_agent not implemented yet")
    ca = _get_content_agent()
    now = datetime.now(timezone.utc)
    assert ca.recency_score(now - timedelta(hours=1)) == 1.0
    assert ca.recency_score(now - timedelta(hours=4)) == 0.8
    assert ca.recency_score(now - timedelta(hours=8)) == 0.6
    assert ca.recency_score(now - timedelta(hours=20)) == 0.4
    assert ca.recency_score(now - timedelta(hours=30)) == 0.2


# ---------------------------------------------------------------------------
# CONT-05: Credibility score
# ---------------------------------------------------------------------------

def test_credibility_score():
    """credibility_score returns tier-based score: reuters=1.0, kitco=0.8, unknown=0.4."""
    pytest.skip("Wave 0 stub — agents.content_agent not implemented yet")
    ca = _get_content_agent()
    assert ca.credibility_score("reuters.com") == 1.0
    assert ca.credibility_score("bloomberg.com") == 1.0
    assert ca.credibility_score("worldgoldcouncil.org") == 0.9
    assert ca.credibility_score("kitco.com") == 0.8
    assert ca.credibility_score("mining.com") == 0.8
    assert ca.credibility_score("juniorminingnetwork.com") == 0.7
    assert ca.credibility_score("randomsite.com") == 0.4


# ---------------------------------------------------------------------------
# CONT-05: Final score formula
# ---------------------------------------------------------------------------

def test_final_score_formula():
    """calculate_story_score combines relevance*0.4 + recency*0.3 + credibility*0.3, scaled to 0-10."""
    pytest.skip("Wave 0 stub — agents.content_agent not implemented yet")
    ca = _get_content_agent()
    # relevance=0.9, recency=1.0, credibility=0.8
    # (0.9*0.4 + 1.0*0.3 + 0.8*0.3) * 10 = (0.36 + 0.30 + 0.24) * 10 = 9.0
    score = ca.calculate_story_score(relevance=0.9, recency=1.0, credibility=0.8)
    assert abs(score - 9.0) < 0.01


# ---------------------------------------------------------------------------
# CONT-06: Select top story
# ---------------------------------------------------------------------------

def test_select_top_story():
    """select_top_story returns highest-scoring story above threshold, or None."""
    pytest.skip("Wave 0 stub — agents.content_agent not implemented yet")
    ca = _get_content_agent()
    stories = [
        {"title": "A", "score": 8.5},
        {"title": "B", "score": 6.0},
        {"title": "C", "score": 7.2},
    ]
    result = ca.select_top_story(stories, threshold=7.0)
    assert result is not None
    assert result["title"] == "A"


# ---------------------------------------------------------------------------
# CONT-07: No-story flag
# ---------------------------------------------------------------------------

def test_no_story_flag():
    """select_top_story returns None when all stories are below threshold."""
    pytest.skip("Wave 0 stub — agents.content_agent not implemented yet")
    ca = _get_content_agent()
    stories = [{"title": "A", "score": 5.0}, {"title": "B", "score": 6.9}]
    result = ca.select_top_story(stories, threshold=7.0)
    assert result is None


# ---------------------------------------------------------------------------
# CONT-08: Article fetch fallback
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_article_fetch_fallback():
    """fetch_article returns RSS summary when httpx fetch fails (403, timeout)."""
    pytest.skip("Wave 0 stub — agents.content_agent not implemented yet")
    ca = _get_content_agent()
    # Mock httpx to raise HTTPError
    # Verify function returns fallback_text parameter
    ...


# ---------------------------------------------------------------------------
# CONT-10: Thread draft structure
# ---------------------------------------------------------------------------

def test_thread_draft_structure():
    """Thread format draft_content has keys: format, tweets, long_form_post."""
    pytest.skip("Wave 0 stub — agents.content_agent not implemented yet")
    draft = {"format": "thread", "tweets": ["t1", "t2", "t3"], "long_form_post": "full post"}
    assert draft["format"] == "thread"
    assert isinstance(draft["tweets"], list)
    assert len(draft["tweets"]) >= 3
    assert "long_form_post" in draft


# ---------------------------------------------------------------------------
# CONT-14/15: Compliance blocks Seva Mining mention
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_compliance_fail_seva_mining():
    """check_compliance returns False when draft contains 'Seva Mining'."""
    pytest.skip("Wave 0 stub — agents.content_agent not implemented yet")
    ca = _get_content_agent()
    # Mock anthropic to return "fail: mentions Seva Mining"
    result = await ca.check_compliance("This post by Seva Mining shows gold at $3200")
    assert result is False


# ---------------------------------------------------------------------------
# CONT-16: Compliance failsafe
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_compliance_failsafe():
    """check_compliance returns False (blocks) on ambiguous LLM response."""
    pytest.skip("Wave 0 stub — agents.content_agent not implemented yet")
    ca = _get_content_agent()
    # Mock anthropic to return "maybe" (ambiguous)
    result = await ca.check_compliance("Some text")
    assert result is False


# ---------------------------------------------------------------------------
# CONT-17: DraftItem fields
# ---------------------------------------------------------------------------

def test_draft_item_fields():
    """build_draft_item returns DraftItem with platform='content', urgency='low', expires_at=None."""
    pytest.skip("Wave 0 stub — agents.content_agent not implemented yet")
    ca = _get_content_agent()
    # Verify build_draft_item produces correct field values
    ...


# ---------------------------------------------------------------------------
# CONT-17: ContentBundle link
# ---------------------------------------------------------------------------

def test_content_bundle_link():
    """build_draft_item stores content_bundle_id in engagement_snapshot JSONB."""
    pytest.skip("Wave 0 stub — agents.content_agent not implemented yet")
    ca = _get_content_agent()
    # Verify engagement_snapshot contains {"content_bundle_id": "..."}
    ...


# ---------------------------------------------------------------------------
# CONT-01: Scheduler wiring
# ---------------------------------------------------------------------------

def test_scheduler_wiring():
    """worker.py _make_job('content_agent') creates ContentAgent, not placeholder."""
    pytest.skip("Wave 0 stub — agents.content_agent not implemented yet")
    import importlib
    worker = importlib.import_module("worker")
    # Verify content_agent branch exists in _make_job
    import inspect
    source = inspect.getsource(worker._make_job)
    assert "ContentAgent" in source
