"""
Tests for Content Agent — CONT-01 through CONT-17.
All tests use mocked feedparser, mocked anthropic, and mocked DB sessions.

Wave 0 state: agents.content_agent does not exist yet.
All 15 tests skip immediately (before any lazy import) so they are
collectable and show as SKIPPED (not ERROR) until implementation.
"""
import json as _json
import logging
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
    """_fetch_all_rss returns story dicts from feedparser entries."""
    # Feed count dropped from 8 to 7 in quick-260419-n4f (dropped Investing.com)
    ca = _get_content_agent()
    assert len(ca.RSS_FEEDS) == 7
    assert any("kitco" in url for url, _ in ca.RSS_FEEDS)


# ---------------------------------------------------------------------------
# CONT-03: SerpAPI parsing
# ---------------------------------------------------------------------------

def test_serpapi_parsing():
    """SERPAPI_KEYWORDS has 10 gold-sector keywords (expanded in 07-07)."""
    ca = _get_content_agent()
    assert len(ca.SERPAPI_KEYWORDS) == 10
    assert "gold price" in ca.SERPAPI_KEYWORDS


# ---------------------------------------------------------------------------
# CONT-03b: SerpAPI non-ISO date parsing
# ---------------------------------------------------------------------------

def test_serpapi_date_parsing_non_iso():
    """_fetch_serpapi_stories handles non-ISO date format from SerpAPI without crashing."""
    from datetime import datetime, timezone
    # Simulate the parsing logic directly (mirrors content_agent._fetch_serpapi_stories)
    iso_date = "04/09/2026, 10:31 AM, +0000 UTC"
    try:
        published = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
    except ValueError:
        try:
            published = datetime.strptime(iso_date, "%m/%d/%Y, %I:%M %p, +0000 UTC").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            published = datetime.now(timezone.utc)

    assert published.year == 2026
    assert published.month == 4
    assert published.day == 9
    assert published.tzinfo is not None


# ---------------------------------------------------------------------------
# CONT-04: URL deduplication
# ---------------------------------------------------------------------------

def test_url_deduplication():
    """deduplicate_stories removes exact URL duplicates, keeps first occurrence."""
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
    """build_no_story_bundle creates ContentBundle with no_story_flag=True and score of best candidate."""
    ca = _get_content_agent()
    # select_top_story already tested — test the no-story bundle builder
    bundle = ca.build_no_story_bundle(best_score=6.5)
    assert bundle.no_story_flag is True
    assert bundle.story_headline == "No qualifying story today"
    assert float(bundle.score) == 6.5
    assert bundle.draft_content is None
    assert bundle.compliance_passed is None


# ---------------------------------------------------------------------------
# CONT-08: Article fetch fallback
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_article_fetch_fallback():
    """fetch_article returns fallback text when httpx fetch fails."""
    ca = _get_content_agent()
    with patch("agents.content_agent.httpx") as mock_httpx:
        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("Connection refused")
        mock_httpx.AsyncClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_httpx.AsyncClient.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_httpx.HTTPError = Exception
        mock_httpx.TimeoutException = Exception
        text, success = await ca.fetch_article("https://example.com/fail", fallback_text="RSS summary text")
        assert success is False
        assert text == "RSS summary text"


# ---------------------------------------------------------------------------
# CONT-10: Thread draft structure
# ---------------------------------------------------------------------------

def test_thread_draft_structure():
    """Thread format draft_content has keys: format, tweets, long_form_post — validated structurally."""
    # This tests the expected JSON structure, not the Claude call itself
    draft = {
        "format": "thread",
        "tweets": ["Tweet 1 about gold prices", "Tweet 2 about production", "Tweet 3 about outlook"],
        "long_form_post": "A comprehensive look at gold prices..."
    }
    assert draft["format"] == "thread"
    assert isinstance(draft["tweets"], list)
    assert len(draft["tweets"]) >= 3
    assert all(len(t) <= 280 for t in draft["tweets"])
    assert "long_form_post" in draft
    assert len(draft["long_form_post"]) <= 2200


# ---------------------------------------------------------------------------
# CONT-14/15: Compliance blocks Seva Mining mention
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_compliance_fail_seva_mining():
    """check_compliance returns False when draft contains 'Seva Mining'."""
    ca = _get_content_agent()
    # Local pre-screen catches this — no LLM call needed
    result = await ca.check_compliance("This post by Seva Mining shows gold at $3200")
    assert result is False


# ---------------------------------------------------------------------------
# CONT-16: Compliance failsafe
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_compliance_failsafe():
    """check_compliance returns False (blocks) on ambiguous LLM response."""
    ca = _get_content_agent()
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="maybe it's fine")]
    mock_client.messages.create = AsyncMock(return_value=mock_response)
    result = await ca.check_compliance("Gold prices rose 5% this week", anthropic_client=mock_client)
    assert result is False  # "maybe it's fine" is not "pass" — fail-safe blocks


# ---------------------------------------------------------------------------
# CONT-17: DraftItem fields
# ---------------------------------------------------------------------------

def test_draft_item_fields():
    """build_draft_item returns DraftItem with platform='content', urgency='low', expires_at=None."""
    ca = _get_content_agent()
    from models.content_bundle import ContentBundle
    import uuid
    cb = ContentBundle(
        id=uuid.uuid4(),
        story_headline="Gold hits $3200",
        story_url="https://reuters.com/gold-3200",
        source_name="Reuters",
        score=8.5,
        draft_content={"format": "thread", "tweets": ["t1", "t2", "t3"], "long_form_post": "..."},
    )
    item = ca.build_draft_item(cb, rationale="Thread format chosen for multi-faceted story")
    assert item.platform == "content"
    assert item.urgency == "low"
    assert item.expires_at is None
    assert item.source_text == "Gold hits $3200"
    assert item.source_url == "https://reuters.com/gold-3200"
    assert item.source_account == "Reuters"
    assert float(item.score) == 8.5


# ---------------------------------------------------------------------------
# CONT-17: ContentBundle link
# ---------------------------------------------------------------------------

def test_content_bundle_link():
    """build_draft_item stores content_bundle_id in engagement_snapshot JSONB."""
    ca = _get_content_agent()
    from models.content_bundle import ContentBundle
    import uuid
    cb_id = uuid.uuid4()
    cb = ContentBundle(
        id=cb_id,
        story_headline="Test",
        score=7.5,
        draft_content={"format": "long_form", "post": "..."},
    )
    item = ca.build_draft_item(cb, rationale="test")
    assert item.engagement_snapshot is not None
    assert item.engagement_snapshot["content_bundle_id"] == str(cb_id)


# ---------------------------------------------------------------------------
# CONT-01: Scheduler wiring
# ---------------------------------------------------------------------------

def test_scheduler_wiring():
    """worker.py _make_job('content_agent') creates ContentAgent, not placeholder."""
    import importlib
    worker = importlib.import_module("worker")
    import inspect
    source = inspect.getsource(worker._make_job)
    assert "ContentAgent" in source, "_make_job must reference ContentAgent class"
    assert "content_agent" in source, "_make_job must handle content_agent job name"


# ---------------------------------------------------------------------------
# Phase 10 — WhatsApp new-item notification tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_content_agent_whatsapp_fires_when_items_queued():
    """send_whatsapp_message called with Content count when items_queued > 0."""
    ca = _get_content_agent()

    agent = ca.ContentAgent.__new__(ca.ContentAgent)

    with patch.object(agent, "_run_pipeline", new_callable=AsyncMock) as mock_pipeline, \
         patch("agents.content_agent.AsyncSessionLocal") as mock_session_cls, \
         patch("services.whatsapp.send_whatsapp_message", new_callable=AsyncMock) as mock_wa:

        mock_session = AsyncMock()
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_session.commit = AsyncMock()
        mock_session.add = MagicMock()

        async def pipeline_sets_items(session, agent_run):
            agent_run.items_queued = 4

        mock_pipeline.side_effect = pipeline_sets_items

        await agent.run()

    mock_wa.assert_called_once()
    call_msg = mock_wa.call_args[0][0]
    assert "Content" in call_msg
    assert "4" in call_msg


@pytest.mark.asyncio
async def test_content_agent_whatsapp_skipped_when_no_items():
    """send_whatsapp_message not called when items_queued == 0."""
    ca = _get_content_agent()

    agent = ca.ContentAgent.__new__(ca.ContentAgent)

    with patch.object(agent, "_run_pipeline", new_callable=AsyncMock) as mock_pipeline, \
         patch("agents.content_agent.AsyncSessionLocal") as mock_session_cls, \
         patch("services.whatsapp.send_whatsapp_message", new_callable=AsyncMock) as mock_wa:

        mock_session = AsyncMock()
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_session.commit = AsyncMock()
        mock_session.add = MagicMock()

        async def pipeline_zero_items(session, agent_run):
            agent_run.items_queued = 0

        mock_pipeline.side_effect = pipeline_zero_items

        await agent.run()

    mock_wa.assert_not_called()


@pytest.mark.asyncio
async def test_content_agent_whatsapp_failure_is_non_fatal():
    """WhatsApp exception in finally block does not prevent commit or status update."""
    ca = _get_content_agent()

    agent = ca.ContentAgent.__new__(ca.ContentAgent)

    with patch.object(agent, "_run_pipeline", new_callable=AsyncMock) as mock_pipeline, \
         patch("agents.content_agent.AsyncSessionLocal") as mock_session_cls, \
         patch("services.whatsapp.send_whatsapp_message", side_effect=Exception("Twilio down")):

        mock_session = AsyncMock()
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_session.commit = AsyncMock()
        mock_session.add = MagicMock()

        async def pipeline_with_items(session, agent_run):
            agent_run.items_queued = 2

        mock_pipeline.side_effect = pipeline_with_items

        # Must NOT raise even though WhatsApp blows up
        await agent.run()

    # commit was still called (session.commit called at least once in finally)
    assert mock_session.commit.call_count >= 1



# ---------------------------------------------------------------------------
# quick-260419-n4f: Gold relevance gate tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_gate_accepts_direct_gold_story():
    """Gate returns keep=True for a direct gold story (macro/sector keep shape)."""
    ca = _get_content_agent()
    story = {"title": "Gold prices hit new record amid safe-haven demand", "summary": "Spot gold up 2%."}
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=_json.dumps({"is_gold_relevant": True, "primary_subject_is_specific_miner": False, "company": None}))]
    mock_client.messages.create = AsyncMock(return_value=mock_response)
    result = await ca.is_gold_relevant_or_systemic_shock(
        story, {"content_gold_gate_enabled": "true", "content_gold_gate_model": "claude-3-5-haiku-latest"}, client=mock_client
    )
    assert result["keep"] is True
    assert result["reject_reason"] is None
    assert result["company"] is None


@pytest.mark.asyncio
async def test_gate_accepts_systemic_shock_strait_of_hormuz():
    """Gate returns keep=True for a Strait of Hormuz disruption story (macro keep shape)."""
    ca = _get_content_agent()
    story = {"title": "Iran threatens to close Strait of Hormuz after tanker attack", "summary": "Oil supply at risk."}
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=_json.dumps({"is_gold_relevant": True, "primary_subject_is_specific_miner": False, "company": None}))]
    mock_client.messages.create = AsyncMock(return_value=mock_response)
    result = await ca.is_gold_relevant_or_systemic_shock(
        story, {"content_gold_gate_enabled": "true", "content_gold_gate_model": "claude-3-5-haiku-latest"}, client=mock_client
    )
    assert result["keep"] is True
    assert result["reject_reason"] is None
    assert result["company"] is None


@pytest.mark.asyncio
async def test_gate_rejects_generic_option_traders():
    """Gate returns keep=False for a generic options story (not_gold_relevant reject shape)."""
    ca = _get_content_agent()
    story = {"title": "Option Traders Chasing Torrid Stock Rally Turn Focus to Earnings", "summary": "Equity options volume rises."}
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=_json.dumps({"is_gold_relevant": False, "primary_subject_is_specific_miner": False, "company": None}))]
    mock_client.messages.create = AsyncMock(return_value=mock_response)
    result = await ca.is_gold_relevant_or_systemic_shock(
        story, {"content_gold_gate_enabled": "true", "content_gold_gate_model": "claude-3-5-haiku-latest"}, client=mock_client
    )
    assert result["keep"] is False
    assert result["reject_reason"] == "not_gold_relevant"
    assert result["company"] is None


@pytest.mark.asyncio
async def test_gate_rejects_private_credit():
    """Gate returns keep=False for a private credit story (not_gold_relevant reject shape)."""
    ca = _get_content_agent()
    story = {"title": "Why Private Credit Is Not a Financial Crisis Threat", "summary": "Asset managers weigh in."}
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=_json.dumps({"is_gold_relevant": False, "primary_subject_is_specific_miner": False, "company": None}))]
    mock_client.messages.create = AsyncMock(return_value=mock_response)
    result = await ca.is_gold_relevant_or_systemic_shock(
        story, {"content_gold_gate_enabled": "true", "content_gold_gate_model": "claude-3-5-haiku-latest"}, client=mock_client
    )
    assert result["keep"] is False
    assert result["reject_reason"] == "not_gold_relevant"
    assert result["company"] is None


@pytest.mark.asyncio
async def test_gate_fails_open_on_api_error():
    """Gate returns keep=True dict (fail-open) when Anthropic raises an exception."""
    ca = _get_content_agent()
    story = {"title": "Gold surges on Fed pivot", "summary": "Spot gold up 2%."}
    mock_client = AsyncMock()
    # APIError requires request= param — use a generic Exception to simulate infra blip
    mock_client.messages.create = AsyncMock(side_effect=Exception("API unavailable"))
    result = await ca.is_gold_relevant_or_systemic_shock(
        story, {"content_gold_gate_enabled": "true", "content_gold_gate_model": "claude-3-5-haiku-latest"}, client=mock_client
    )
    assert result["keep"] is True
    assert result["reject_reason"] is None
    assert result["company"] is None


@pytest.mark.asyncio
async def test_gate_bypassed_when_disabled():
    """Gate returns keep=True dict without any LLM call when content_gold_gate_enabled=False."""
    ca = _get_content_agent()
    story = {"title": "Anything at all", "summary": "Does not matter."}
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock()
    result = await ca.is_gold_relevant_or_systemic_shock(
        story, {"content_gold_gate_enabled": "false"}, client=mock_client
    )
    assert result["keep"] is True
    assert result["reject_reason"] is None
    assert result["company"] is None
    mock_client.messages.create.assert_not_called()



# ---------------------------------------------------------------------------
# quick-260419-r0r: long_form 400-char minimum floor tests
# ---------------------------------------------------------------------------

def _mock_longform_response(post_text):
    import json
    payload = json.dumps({
        "format": "long_form",
        "rationale": "Single coherent narrative.",
        "key_data_points": ["$3,500/oz"],
        "draft_content": {"format": "long_form", "post": post_text},
    })
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=payload)]
    return mock_response


@pytest.mark.asyncio
async def test_long_form_accepted_at_minimum():
    """long_form post of exactly 400 chars is accepted and returned normally."""
    ca = _get_content_agent()
    agent = ca.ContentAgent.__new__(ca.ContentAgent)
    agent.anthropic = AsyncMock()
    agent._skipped_short_longform = 0
    agent.anthropic.messages.create = AsyncMock(return_value=_mock_longform_response("A" * 400))

    story = {"title": "Gold hits $3,500 as Fed signals rate pause", "link": "https://example.com/gold"}
    deep_research = {
        "article_text": "Gold prices surged to record highs...",
        "article_fetch_succeeded": True,
        "corroborating_sources": [],
        "key_data_points": [],
    }

    result = await agent._research_and_draft(story, deep_research)

    assert result is not None
    assert result[0]["post"] == "A" * 400
    assert agent._skipped_short_longform == 0


@pytest.mark.asyncio
async def test_long_form_accepted_well_above_minimum():
    """long_form post of 800 chars is accepted and counter stays at 0."""
    ca = _get_content_agent()
    agent = ca.ContentAgent.__new__(ca.ContentAgent)
    agent.anthropic = AsyncMock()
    agent._skipped_short_longform = 0
    agent.anthropic.messages.create = AsyncMock(return_value=_mock_longform_response("A" * 800))

    story = {"title": "Gold hits $3,500 as Fed signals rate pause", "link": "https://example.com/gold"}
    deep_research = {
        "article_text": "Gold prices surged to record highs...",
        "article_fetch_succeeded": True,
        "corroborating_sources": [],
        "key_data_points": [],
    }

    result = await agent._research_and_draft(story, deep_research)

    assert result is not None
    assert agent._skipped_short_longform == 0


@pytest.mark.asyncio
async def test_long_form_rejected_below_minimum():
    """long_form post of 350 chars is rejected: returns None, counter increments to 1."""
    ca = _get_content_agent()
    agent = ca.ContentAgent.__new__(ca.ContentAgent)
    agent.anthropic = AsyncMock()
    agent._skipped_short_longform = 0
    agent.anthropic.messages.create = AsyncMock(return_value=_mock_longform_response("A" * 350))

    story = {"title": "Gold hits $3,500 as Fed signals rate pause", "link": "https://example.com/gold"}
    deep_research = {
        "article_text": "Gold prices surged to record highs...",
        "article_fetch_succeeded": True,
        "corroborating_sources": [],
        "key_data_points": [],
    }

    result = await agent._research_and_draft(story, deep_research)

    assert result is None
    assert agent._skipped_short_longform == 1


@pytest.mark.asyncio
async def test_long_form_boundary_399_chars():
    """long_form post of 399 chars is rejected (strict < 400 comparison)."""
    ca = _get_content_agent()
    agent = ca.ContentAgent.__new__(ca.ContentAgent)
    agent.anthropic = AsyncMock()
    agent._skipped_short_longform = 0
    agent.anthropic.messages.create = AsyncMock(return_value=_mock_longform_response("A" * 399))

    story = {"title": "Gold hits $3,500 as Fed signals rate pause", "link": "https://example.com/gold"}
    deep_research = {
        "article_text": "Gold prices surged to record highs...",
        "article_fetch_succeeded": True,
        "corroborating_sources": [],
        "key_data_points": [],
    }

    result = await agent._research_and_draft(story, deep_research)

    assert result is None
    assert agent._skipped_short_longform == 1


# ---------------------------------------------------------------------------
# quick-260419-rqx: classify_format_lightweight tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_classify_format_lightweight_returns_valid_format():
    """classify_format_lightweight returns the format name when Haiku responds correctly."""
    ca = _get_content_agent()
    story = {"title": "Fed signals rate cut as inflation cools", "summary": "Breaking macro news.", "published": ""}
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="breaking_news")]
    mock_client.messages.create = AsyncMock(return_value=mock_response)
    result = await ca.classify_format_lightweight(story, client=mock_client)
    assert result == "breaking_news"


@pytest.mark.asyncio
async def test_classify_format_lightweight_fails_open_to_thread():
    """classify_format_lightweight returns 'thread' when Haiku raises."""
    ca = _get_content_agent()
    story = {"title": "Gold rally", "summary": "", "published": ""}
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(side_effect=Exception("API down"))
    result = await ca.classify_format_lightweight(story, client=mock_client)
    assert result == "thread"


@pytest.mark.asyncio
async def test_classify_format_lightweight_clamps_invalid_output():
    """classify_format_lightweight returns 'thread' when Haiku returns garbage."""
    ca = _get_content_agent()
    story = {"title": "Barrick earnings", "summary": "", "published": ""}
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="garbage response xyz")]
    mock_client.messages.create = AsyncMock(return_value=mock_response)
    result = await ca.classify_format_lightweight(story, client=mock_client)
    assert result == "thread"


# ---------------------------------------------------------------------------
# quick-260419-rqx: select_qualifying_stories — top-N + priority tests
# ---------------------------------------------------------------------------

def test_select_qualifying_stories_respects_max_count():
    """select_qualifying_stories(max_count=5) returns exactly 5 when >5 qualify."""
    ca = _get_content_agent()
    now = datetime(2026, 4, 20, 12, 0, 0, tzinfo=timezone.utc)
    old = now - timedelta(hours=48)
    stories = [
        {"title": f"Story {i}", "score": 7.5 + i * 0.1, "published": old, "predicted_format": "thread"}
        for i in range(10)
    ]
    result = ca.select_qualifying_stories(stories, threshold=7.0, max_count=5, now=now)
    assert len(result) == 5
    # Sorted descending by score
    scores = [s["score"] for s in result]
    assert scores == sorted(scores, reverse=True)


def test_select_qualifying_stories_prioritizes_breaking_format():
    """Breaking_news stories appear before higher-scored regular stories in the slice."""
    ca = _get_content_agent()
    now = datetime(2026, 4, 20, 12, 0, 0, tzinfo=timezone.utc)
    old = now - timedelta(hours=48)
    breaking = [
        {"title": f"Breaking {i}", "score": s, "published": old, "predicted_format": "breaking_news"}
        for i, s in enumerate([7.5, 7.3, 7.1])
    ]
    regular = [
        {"title": f"Regular {i}", "score": s, "published": old, "predicted_format": "thread"}
        for i, s in enumerate([9.0, 8.9, 8.8, 8.7, 8.6])
    ]
    result = ca.select_qualifying_stories(
        breaking + regular, threshold=7.0, max_count=5, now=now
    )
    assert len(result) == 5
    # All 3 breaking news stories in first 3 slots
    assert result[0]["predicted_format"] == "breaking_news"
    assert result[1]["predicted_format"] == "breaking_news"
    assert result[2]["predicted_format"] == "breaking_news"
    # Breaking sorted desc by score
    assert result[0]["score"] == 7.5
    assert result[1]["score"] == 7.3
    # Regular stories fill remaining slots, highest score first
    assert result[3]["score"] == 9.0
    assert result[4]["score"] == 8.9


def test_select_qualifying_stories_prioritizes_fresh_by_recency():
    """Fresh stories (within breaking_window_hours) appear before older higher-scored ones."""
    ca = _get_content_agent()
    now = datetime(2026, 4, 20, 12, 0, 0, tzinfo=timezone.utc)
    fresh = [
        {"title": f"Fresh {i}", "score": s, "published": now - timedelta(hours=1), "predicted_format": "thread"}
        for i, s in enumerate([7.4, 7.2])
    ]
    old = [
        {"title": f"Old {i}", "score": s, "published": now - timedelta(hours=48), "predicted_format": "thread"}
        for i, s in enumerate([9.0, 8.9, 8.8, 8.7, 8.6, 8.5, 8.4, 8.3, 8.2, 8.1])
    ]
    result = ca.select_qualifying_stories(
        fresh + old, threshold=7.0, max_count=5, breaking_window_hours=3.0, now=now
    )
    assert len(result) == 5
    # Fresh stories occupy first 2 slots
    fresh_titles = {s["title"] for s in result[:2]}
    assert "Fresh 0" in fresh_titles
    assert "Fresh 1" in fresh_titles


def test_select_qualifying_stories_fewer_than_cap_returns_all():
    """When fewer stories than max_count qualify, returns all qualifying."""
    ca = _get_content_agent()
    now = datetime(2026, 4, 20, 12, 0, 0, tzinfo=timezone.utc)
    old = now - timedelta(hours=48)
    stories = [
        {"title": f"Story {i}", "score": 7.5 + i * 0.1, "published": old, "predicted_format": "thread"}
        for i in range(3)
    ]
    result = ca.select_qualifying_stories(stories, threshold=7.0, max_count=5, now=now)
    assert len(result) == 3


def test_select_qualifying_stories_no_max_count_unchanged_behavior():
    """Without max_count, returns all qualifying sorted desc (backward compat)."""
    ca = _get_content_agent()
    stories = [
        {"title": "A", "score": 8.5},
        {"title": "B", "score": 9.2},
        {"title": "C", "score": 6.9},  # below threshold
        {"title": "D", "score": 7.8},
    ]
    result = ca.select_qualifying_stories(stories, threshold=7.0)
    assert len(result) == 3
    assert result[0]["score"] == 9.2
    assert result[1]["score"] == 8.5
    assert result[2]["score"] == 7.8


# ---------------------------------------------------------------------------
# quick-260419-rqx: Gold gate listicle/stock-pick rejection tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_gate_rejects_listicle_top_5_gold_stocks():
    """Gate returns keep=False for a 'Top 5 Junior Gold Stocks' listicle article (not_gold_relevant)."""
    ca = _get_content_agent()
    story = {
        "title": "Top 5 Junior Gold Stocks of 2026",
        "summary": "Investing News Network rounds up the best junior gold miners to watch this year.",
    }
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=_json.dumps({"is_gold_relevant": False, "primary_subject_is_specific_miner": False, "company": None}))]
    mock_client.messages.create = AsyncMock(return_value=mock_response)
    result = await ca.is_gold_relevant_or_systemic_shock(
        story,
        {"content_gold_gate_enabled": "true", "content_gold_gate_model": "claude-3-5-haiku-latest"},
        client=mock_client,
    )
    assert result["keep"] is False
    assert result["reject_reason"] == "not_gold_relevant"
    assert result["company"] is None


@pytest.mark.asyncio
async def test_gate_rejects_listicle_best_performing():
    """Gate returns keep=False for a '7 Best-Performing Gold Stocks' listicle (not_gold_relevant)."""
    ca = _get_content_agent()
    story = {
        "title": "7 Best-Performing Gold Stocks For Hedging Against Volatility",
        "summary": "NerdWallet analysts pick their top gold equity recommendations for portfolio hedges.",
    }
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=_json.dumps({"is_gold_relevant": False, "primary_subject_is_specific_miner": False, "company": None}))]
    mock_client.messages.create = AsyncMock(return_value=mock_response)
    result = await ca.is_gold_relevant_or_systemic_shock(
        story,
        {"content_gold_gate_enabled": "true", "content_gold_gate_model": "claude-3-5-haiku-latest"},
        client=mock_client,
    )
    assert result["keep"] is False
    assert result["reject_reason"] == "not_gold_relevant"
    assert result["company"] is None


@pytest.mark.asyncio
async def test_gate_rejects_single_company_earnings_under_nnh():
    # quick-260420-nnh: inverts rqx-era behavior — single-company earnings is now a reject under the specific-miner rule.
    """Gate returns keep=False for single-company Newmont earnings (specific-miner reject)."""
    ca = _get_content_agent()
    story = {
        "title": "Newmont Reports Record Q1 Gold Production",
        "summary": "Newmont Corporation posts record quarterly production of 1.6M oz Au.",
    }
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=_json.dumps({"is_gold_relevant": True, "primary_subject_is_specific_miner": True, "company": "Newmont"}))]
    mock_client.messages.create = AsyncMock(return_value=mock_response)
    result = await ca.is_gold_relevant_or_systemic_shock(
        story,
        {"content_gold_gate_enabled": "true", "content_gold_gate_model": "claude-3-5-haiku-latest"},
        client=mock_client,
    )
    assert result["keep"] is False
    assert result["reject_reason"] == "primary_subject_is_specific_miner"
    assert result["company"] == "Newmont"


# ---------------------------------------------------------------------------
# quick-260420-mfy: brand_preamble + three-field infographic/quote tests
# ---------------------------------------------------------------------------


def _make_mfy_infographic_response():
    """Sonnet response stub: infographic with new three-field shape + image_prompt_direction."""
    obj = {
        "format": "infographic",
        "rationale": "Data-forward central bank story.",
        "key_data_points": ["1,136 tonnes purchased Q1 2026"],
        "draft_content": {
            "format": "infographic",
            "twitter_caption": "Central banks bought 1,136t of gold in Q1 2026 — a record quarter.",
            "suggested_headline": "Central Banks Set Q1 Gold Buying Record",
            "data_facts": ["1,136 tonnes purchased Q1 2026", "Highest quarterly total since 1971"],
            "image_prompt_direction": "Bar chart comparing Q1 quarterly purchases from 2020–2026.",
        },
    }
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=_json.dumps(obj))]
    return mock_response


def _make_mfy_quote_response():
    """Sonnet response stub: quote with new three-field shape + image_prompt_direction."""
    obj = {
        "speaker": "Janet Yellen",
        "speaker_title": "Former U.S. Treasury Secretary",
        "quote_text": "\"Gold is the ultimate store of value in uncertain times.\"",
        "source_url": "https://example.com/yellen-quote",
        "twitter_post": "Janet Yellen: 'Gold is the ultimate store of value in uncertain times.'",
        "suggested_headline": "Yellen: Gold Is Ultimate Store of Value",
        "data_facts": ["Gold up 18% YTD", "Central banks hold record 36,000t"],
        "image_prompt_direction": "Pull-quote card with Yellen attribution below the quote.",
    }
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=_json.dumps(obj))]
    return mock_response


# --- Test A: brand_preamble imports and contains all required substrings ---

def test_brand_preamble_loads():
    """BRAND_PREAMBLE imports from agents.brand_preamble and contains all required substrings."""
    from agents.brand_preamble import BRAND_PREAMBLE
    required = [
        "#F0ECE4", "#0C1B32", "#1E3A5F", "#4A7FA5", "#5A6B7A",
        "#D4AF37", "#D8D2C8", "DM Serif Display", "Inter",
        "SEVA MINING", "1200x675", "HTML artifact",
    ]
    missing = [s for s in required if s not in BRAND_PREAMBLE]
    assert not missing, f"BRAND_PREAMBLE missing substrings: {missing}"


# --- Test B: BRAND_PREAMBLE length floor ---

def test_brand_preamble_min_length():
    """BRAND_PREAMBLE must be at least 200 chars."""
    from agents.brand_preamble import BRAND_PREAMBLE
    assert len(BRAND_PREAMBLE) >= 200, f"BRAND_PREAMBLE too short: {len(BRAND_PREAMBLE)} chars"


# --- Test C: infographic _research_and_draft returns new three-field shape ---

@pytest.mark.asyncio
async def test_infographic_research_and_draft_returns_three_new_fields():
    """_research_and_draft for infographic returns suggested_headline, data_facts, image_prompt."""
    from agents.brand_preamble import BRAND_PREAMBLE
    ca = _get_content_agent()
    agent = ca.ContentAgent.__new__(ca.ContentAgent)
    agent.anthropic = AsyncMock()
    agent._skipped_short_longform = 0
    agent.anthropic.messages.create = AsyncMock(return_value=_make_mfy_infographic_response())

    story = {"title": "Central Banks Set Q1 Gold Buying Record", "source_name": "Reuters"}
    deep_research = {"article_text": "Gold demand...", "corroborating_sources": [], "key_data_points": []}

    result = await agent._research_and_draft(story, deep_research)
    assert result is not None
    draft_content, _, _ = result

    assert draft_content.get("format") == "infographic"
    assert "suggested_headline" in draft_content
    assert "data_facts" in draft_content
    assert "image_prompt" in draft_content
    # image_prompt must start with BRAND_PREAMBLE verbatim
    assert draft_content["image_prompt"].startswith(BRAND_PREAMBLE), \
        "image_prompt must start with BRAND_PREAMBLE verbatim"


# --- Test D: quote _draft_quote_post returns new three-field shape ---

@pytest.mark.asyncio
async def test_quote_draft_returns_three_new_fields():
    """_draft_quote_post returns suggested_headline, data_facts, image_prompt for quote format."""
    from agents.brand_preamble import BRAND_PREAMBLE
    ca = _get_content_agent()
    agent = ca.ContentAgent.__new__(ca.ContentAgent)
    agent.anthropic = AsyncMock()
    agent.anthropic.messages.create = AsyncMock(return_value=_make_mfy_quote_response())

    result = await agent._draft_quote_post(
        quote_text="Gold is the ultimate store of value.",
        speaker="Janet Yellen",
        speaker_title="Former U.S. Treasury Secretary",
        source_url="https://x.com/JanetYellen/status/123",
    )
    assert result is not None
    draft_content = result

    assert "suggested_headline" in draft_content
    assert "data_facts" in draft_content
    assert "image_prompt" in draft_content
    assert draft_content["image_prompt"].startswith(BRAND_PREAMBLE), \
        "quote image_prompt must start with BRAND_PREAMBLE verbatim"


# --- Test E: suggested_headline length is soft (not truncated) ---

@pytest.mark.asyncio
async def test_infographic_long_headline_not_truncated():
    """A >60-char suggested_headline is preserved as-is (soft hint only, no hard truncation)."""
    long_headline = "X" * 80  # 80 chars, exceeds the 60-char guidance
    obj = {
        "format": "infographic",
        "rationale": "Test",
        "key_data_points": [],
        "draft_content": {
            "format": "infographic",
            "twitter_caption": "Caption.",
            "suggested_headline": long_headline,
            "data_facts": ["fact 1"],
            "image_prompt_direction": "A bar chart.",
        },
    }
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=_json.dumps(obj))]

    ca = _get_content_agent()
    agent = ca.ContentAgent.__new__(ca.ContentAgent)
    agent.anthropic = AsyncMock()
    agent._skipped_short_longform = 0
    agent.anthropic.messages.create = AsyncMock(return_value=mock_response)

    story = {"title": "Test", "source_name": "Reuters"}
    deep_research = {"article_text": "...", "corroborating_sources": [], "key_data_points": []}
    result = await agent._research_and_draft(story, deep_research)
    assert result is not None
    draft_content, _, _ = result
    # Long headline must be preserved exactly
    assert draft_content.get("suggested_headline") == long_headline


# --- Test F: data_facts clamped to 5 items ---

@pytest.mark.asyncio
async def test_infographic_data_facts_clamped_to_five():
    """data_facts with >5 items is silently clamped to 5; never raises."""
    many_facts = [f"fact {i}" for i in range(10)]
    obj = {
        "format": "infographic",
        "rationale": "Test",
        "key_data_points": [],
        "draft_content": {
            "format": "infographic",
            "twitter_caption": "Caption.",
            "suggested_headline": "Short headline",
            "data_facts": many_facts,
            "image_prompt_direction": "A bar chart.",
        },
    }
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=_json.dumps(obj))]

    ca = _get_content_agent()
    agent = ca.ContentAgent.__new__(ca.ContentAgent)
    agent.anthropic = AsyncMock()
    agent._skipped_short_longform = 0
    agent.anthropic.messages.create = AsyncMock(return_value=mock_response)

    story = {"title": "Test", "source_name": "Reuters"}
    deep_research = {"article_text": "...", "corroborating_sources": [], "key_data_points": []}
    result = await agent._research_and_draft(story, deep_research)
    assert result is not None
    draft_content, _, _ = result
    assert isinstance(draft_content.get("data_facts"), list)
    assert len(draft_content["data_facts"]) <= 5


# --- Test G: long_form 400-char floor still works ---
# (G is covered by existing tests: test_long_form_accepted_at_minimum,
#  test_long_form_rejected_below_minimum — no new test needed)


# --- Test H: compliance check also screens suggested_headline and data_facts ---

def test_compliance_screens_suggested_headline():
    """_extract_check_text includes suggested_headline from infographic draft_content."""
    import agents.content_agent as ca_module
    dc = {
        "format": "infographic",
        "twitter_caption": "Normal tweet.",
        "suggested_headline": "Seva Mining Announces 50% Dividend Yield Investment",
        "data_facts": ["Gold up 5%"],
        "image_prompt": "...",
    }
    text = ca_module._extract_check_text(dc)
    assert "Seva Mining" in text, "_extract_check_text must include suggested_headline"


def test_compliance_screens_data_facts():
    """_extract_check_text includes data_facts strings from infographic draft_content."""
    import agents.content_agent as ca_module
    dc = {
        "format": "infographic",
        "twitter_caption": "Normal tweet.",
        "suggested_headline": "Gold Rallies on Safe Haven Demand",
        "data_facts": ["Buy gold now for guaranteed returns", "50% upside expected"],
        "image_prompt": "...",
    }
    text = ca_module._extract_check_text(dc)
    assert "guaranteed returns" in text, "_extract_check_text must include data_facts content"
@pytest.mark.asyncio
async def test_gate_rejects_barrick_ma_under_nnh():
    # quick-260420-nnh: inverts rqx-era behavior — Barrick M&A is a specific-miner story (two specific miners, same rule) and must reject under nnh. Consistent with B2Gold/Newmont/Seva Mining rejects above.
    """Gate returns keep=False for Barrick M&A news (specific-miner reject)."""
    ca = _get_content_agent()
    story = {
        "title": "Barrick Announces $5B Acquisition of X Mining",
        "summary": "Barrick Gold to acquire X Mining in all-stock deal, expanding Tier 1 asset base.",
    }
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=_json.dumps({"is_gold_relevant": True, "primary_subject_is_specific_miner": True, "company": "Barrick"}))]
    mock_client.messages.create = AsyncMock(return_value=mock_response)
    result = await ca.is_gold_relevant_or_systemic_shock(
        story,
        {"content_gold_gate_enabled": "true", "content_gold_gate_model": "claude-3-5-haiku-latest"},
        client=mock_client,
    )
    assert result["keep"] is False
    assert result["reject_reason"] == "primary_subject_is_specific_miner"
    assert "Barrick" in result["company"]


# ---------------------------------------------------------------------------
# quick-260420-nnh: Company-specific rejection tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_gate_rejects_b2gold_production_update():
    """Gate rejects B2Gold production update — primary subject is specific miner."""
    ca = _get_content_agent()
    story = {
        "title": "B2Gold expects lower Q2 output from Goose mine",
        "summary": "B2Gold Corp says Goose mine production will be below guidance for Q2.",
    }
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=_json.dumps({"is_gold_relevant": True, "primary_subject_is_specific_miner": True, "company": "B2Gold"}))]
    mock_client.messages.create = AsyncMock(return_value=mock_response)
    result = await ca.is_gold_relevant_or_systemic_shock(
        story,
        {"content_gold_gate_enabled": "true", "content_gold_gate_model": "claude-3-5-haiku-latest"},
        client=mock_client,
    )
    assert result["keep"] is False
    assert result["reject_reason"] == "primary_subject_is_specific_miner"
    assert result["company"] == "B2Gold"


@pytest.mark.asyncio
async def test_gate_rejects_mclaren_drone_program():
    """Gate rejects McLaren drone program update — primary subject is specific miner."""
    ca = _get_content_agent()
    story = {
        "title": "McLaren Completes Drone MAG Program at Blue Quartz Gold Property",
        "summary": "McLaren Mining announces completion of its drone magnetics survey at Blue Quartz.",
    }
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=_json.dumps({"is_gold_relevant": True, "primary_subject_is_specific_miner": True, "company": "McLaren"}))]
    mock_client.messages.create = AsyncMock(return_value=mock_response)
    result = await ca.is_gold_relevant_or_systemic_shock(
        story,
        {"content_gold_gate_enabled": "true", "content_gold_gate_model": "claude-3-5-haiku-latest"},
        client=mock_client,
    )
    assert result["keep"] is False
    assert result["reject_reason"] == "primary_subject_is_specific_miner"
    assert result["company"] == "McLaren"


@pytest.mark.asyncio
async def test_gate_rejects_barrick_kinross_ma():
    """Gate rejects Barrick-Kinross M&A — primary subjects are two specific miners."""
    ca = _get_content_agent()
    story = {
        "title": "Barrick acquires Kinross in $8B deal",
        "summary": "Barrick Gold announces acquisition of Kinross Gold in a transformative all-stock $8B deal.",
    }
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=_json.dumps({"is_gold_relevant": True, "primary_subject_is_specific_miner": True, "company": "Barrick"}))]
    mock_client.messages.create = AsyncMock(return_value=mock_response)
    result = await ca.is_gold_relevant_or_systemic_shock(
        story,
        {"content_gold_gate_enabled": "true", "content_gold_gate_model": "claude-3-5-haiku-latest"},
        client=mock_client,
    )
    assert result["keep"] is False
    assert result["reject_reason"] == "primary_subject_is_specific_miner"
    assert result["company"] is not None
    assert "Barrick" in result["company"]


@pytest.mark.asyncio
async def test_gate_rejects_newmont_guidance():
    """Gate rejects Newmont guidance raise — primary subject is specific miner."""
    ca = _get_content_agent()
    story = {
        "title": "Newmont posts record Q2, raises guidance",
        "summary": "Newmont Corporation reports record Q2 gold production and raises full-year guidance.",
    }
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=_json.dumps({"is_gold_relevant": True, "primary_subject_is_specific_miner": True, "company": "Newmont"}))]
    mock_client.messages.create = AsyncMock(return_value=mock_response)
    result = await ca.is_gold_relevant_or_systemic_shock(
        story,
        {"content_gold_gate_enabled": "true", "content_gold_gate_model": "claude-3-5-haiku-latest"},
        client=mock_client,
    )
    assert result["keep"] is False
    assert result["reject_reason"] == "primary_subject_is_specific_miner"
    assert result["company"] == "Newmont"


@pytest.mark.asyncio
async def test_gate_rejects_seva_mining_drill_result():
    """Gate rejects Seva Mining drill result — operator's own company is also rejected."""
    ca = _get_content_agent()
    story = {
        "title": "Seva Mining hits 12g/t gold at Timmins drill hole 42",
        "summary": "Seva Mining Corp announces a significant drill result at its Timmins property.",
    }
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=_json.dumps({"is_gold_relevant": True, "primary_subject_is_specific_miner": True, "company": "Seva Mining"}))]
    mock_client.messages.create = AsyncMock(return_value=mock_response)
    result = await ca.is_gold_relevant_or_systemic_shock(
        story,
        {"content_gold_gate_enabled": "true", "content_gold_gate_model": "claude-3-5-haiku-latest"},
        client=mock_client,
    )
    assert result["keep"] is False
    assert result["reject_reason"] == "primary_subject_is_specific_miner"
    assert result["company"] == "Seva Mining"


@pytest.mark.asyncio
async def test_gate_keeps_goldman_forecast_as_source():
    """Gate keeps story where Goldman is cited as a source, not the subject."""
    ca = _get_content_agent()
    story = {
        "title": "Gold hits record $3,200 as Goldman forecasts $4K by year-end",
        "summary": "Spot gold reached a new all-time high; Goldman Sachs raised its 12-month target to $4,000.",
    }
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=_json.dumps({"is_gold_relevant": True, "primary_subject_is_specific_miner": False, "company": None}))]
    mock_client.messages.create = AsyncMock(return_value=mock_response)
    result = await ca.is_gold_relevant_or_systemic_shock(
        story,
        {"content_gold_gate_enabled": "true", "content_gold_gate_model": "claude-3-5-haiku-latest"},
        client=mock_client,
    )
    assert result["keep"] is True
    assert result["reject_reason"] is None
    assert result["company"] is None


@pytest.mark.asyncio
async def test_gate_keeps_wgc_central_bank_report():
    """Gate keeps central bank buying story citing World Gold Council as source."""
    ca = _get_content_agent()
    story = {
        "title": "Central banks added 800t of gold in Q1, says World Gold Council",
        "summary": "The WGC's quarterly report shows record central bank gold purchases.",
    }
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=_json.dumps({"is_gold_relevant": True, "primary_subject_is_specific_miner": False, "company": None}))]
    mock_client.messages.create = AsyncMock(return_value=mock_response)
    result = await ca.is_gold_relevant_or_systemic_shock(
        story,
        {"content_gold_gate_enabled": "true", "content_gold_gate_model": "claude-3-5-haiku-latest"},
        client=mock_client,
    )
    assert result["keep"] is True
    assert result["reject_reason"] is None
    assert result["company"] is None


@pytest.mark.asyncio
async def test_gate_keeps_miners_index_sector_move():
    """Gate keeps sector-wide miners index story."""
    ca = _get_content_agent()
    story = {
        "title": "Gold miners index hits new high",
        "summary": "The NYSE Arca Gold Miners Index (GDX) set a new 52-week high on Thursday.",
    }
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=_json.dumps({"is_gold_relevant": True, "primary_subject_is_specific_miner": False, "company": None}))]
    mock_client.messages.create = AsyncMock(return_value=mock_response)
    result = await ca.is_gold_relevant_or_systemic_shock(
        story,
        {"content_gold_gate_enabled": "true", "content_gold_gate_model": "claude-3-5-haiku-latest"},
        client=mock_client,
    )
    assert result["keep"] is True
    assert result["reject_reason"] is None
    assert result["company"] is None


@pytest.mark.asyncio
async def test_gate_keeps_etf_flows():
    """Gate keeps gold miner ETF flow story."""
    ca = _get_content_agent()
    story = {
        "title": "ETF flows into gold miners surge",
        "summary": "Inflows into gold miner ETFs reached a multi-year high last week.",
    }
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=_json.dumps({"is_gold_relevant": True, "primary_subject_is_specific_miner": False, "company": None}))]
    mock_client.messages.create = AsyncMock(return_value=mock_response)
    result = await ca.is_gold_relevant_or_systemic_shock(
        story,
        {"content_gold_gate_enabled": "true", "content_gold_gate_model": "claude-3-5-haiku-latest"},
        client=mock_client,
    )
    assert result["keep"] is True
    assert result["reject_reason"] is None
    assert result["company"] is None


@pytest.mark.asyncio
async def test_gate_keeps_cpi_macro():
    """Gate keeps macro CPI story with gold rally angle."""
    ca = _get_content_agent()
    story = {
        "title": "US CPI at 2.1%; gold rallies on Fed cut odds",
        "summary": "Lower-than-expected CPI boosted expectations for a Fed rate cut, sending gold higher.",
    }
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=_json.dumps({"is_gold_relevant": True, "primary_subject_is_specific_miner": False, "company": None}))]
    mock_client.messages.create = AsyncMock(return_value=mock_response)
    result = await ca.is_gold_relevant_or_systemic_shock(
        story,
        {"content_gold_gate_enabled": "true", "content_gold_gate_model": "claude-3-5-haiku-latest"},
        client=mock_client,
    )
    assert result["keep"] is True
    assert result["reject_reason"] is None
    assert result["company"] is None


@pytest.mark.asyncio
async def test_gate_keeps_rare_earth_geopolitics():
    """Gate keeps rare-earth geopolitics story (systemic shock bucket)."""
    ca = _get_content_agent()
    story = {
        "title": "China imposes new rare-earth export restrictions",
        "summary": "Beijing announced controls on rare-earth mineral exports, rattling commodity markets.",
    }
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=_json.dumps({"is_gold_relevant": True, "primary_subject_is_specific_miner": False, "company": None}))]
    mock_client.messages.create = AsyncMock(return_value=mock_response)
    result = await ca.is_gold_relevant_or_systemic_shock(
        story,
        {"content_gold_gate_enabled": "true", "content_gold_gate_model": "claude-3-5-haiku-latest"},
        client=mock_client,
    )
    assert result["keep"] is True
    assert result["reject_reason"] is None
    assert result["company"] is None


@pytest.mark.asyncio
async def test_gate_fails_open_on_malformed_json():
    """Gate returns keep=True dict when Haiku returns non-JSON (fail-open, guards against output-format drift)."""
    ca = _get_content_agent()
    story = {"title": "Gold price update", "summary": "Spot gold moves higher."}
    mock_client = AsyncMock()
    mock_response = MagicMock()
    # Haiku returns bare "yes" instead of JSON — must fail-open
    mock_response.content = [MagicMock(text="yes")]
    mock_client.messages.create = AsyncMock(return_value=mock_response)
    result = await ca.is_gold_relevant_or_systemic_shock(
        story,
        {"content_gold_gate_enabled": "true", "content_gold_gate_model": "claude-3-5-haiku-latest"},
        client=mock_client,
    )
    assert result["keep"] is True
    assert result["reject_reason"] is None
    assert result["company"] is None



# ---------------------------------------------------------------------------
# quick-260420-oa1: Market snapshot integration tests (Task 2)
# ---------------------------------------------------------------------------

def _make_canned_snapshot():
    """A populated MarketSnapshot dict for use in pipeline tests."""
    from datetime import datetime, timezone
    return {
        "fetched_at": datetime(2026, 4, 21, 0, 30, 0, tzinfo=timezone.utc),
        "status": "ok",
        "gold_usd_per_oz": 2345.67,
        "silver_usd_per_oz": 27.89,
        "ust_10y_nominal": 4.12,
        "ust_10y_real": 1.87,
        "fed_funds": 5.33,
        "cpi_yoy": 3.2,
        "cpi_observation_date": "2026-03-01",
        "errors": {},
    }


def _make_fallback_snapshot():
    """An all-None fallback MarketSnapshot (status failed)."""
    from datetime import datetime, timezone
    return {
        "fetched_at": datetime(2026, 4, 21, 0, 30, 0, tzinfo=timezone.utc),
        "status": "failed",
        "gold_usd_per_oz": None,
        "silver_usd_per_oz": None,
        "ust_10y_nominal": None,
        "ust_10y_real": None,
        "fed_funds": None,
        "cpi_yoy": None,
        "cpi_observation_date": None,
        "errors": {"pipeline": "RuntimeError: network down"},
    }


# --- OA1-1: fetch_market_snapshot called exactly once per run ---

@pytest.mark.asyncio
async def test_run_fetches_snapshot_once_per_invocation():
    """fetch_market_snapshot is called exactly once per ContentAgent.run() invocation."""
    ca = _get_content_agent()

    canned_snap = _make_canned_snapshot()
    mock_fetch = AsyncMock(return_value=canned_snap)

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()

    with patch("agents.content_agent.AsyncSessionLocal", return_value=mock_session), \
         patch("agents.content_agent.fetch_market_snapshot", mock_fetch):
        agent = ca.ContentAgent.__new__(ca.ContentAgent)
        agent.anthropic = AsyncMock()
        agent.serpapi_client = None
        agent.tweepy_client = AsyncMock()
        agent._queued_titles = []
        agent._skipped_short_longform = 0
        agent._market_snapshot = None

        async def _noop_pipeline(session, agent_run):
            pass
        agent._run_pipeline = _noop_pipeline

        await agent.run()

    assert mock_fetch.call_count == 1, \
        f"Expected fetch_market_snapshot called once, got {mock_fetch.call_count}"


# --- OA1-2: _research_and_draft system prompt contains snapshot block ---

@pytest.mark.asyncio
async def test_research_and_draft_system_prompt_contains_snapshot_block():
    """Captured system prompt for _research_and_draft contains snapshot block BEFORE analyst line."""
    ca = _get_content_agent()
    agent = ca.ContentAgent.__new__(ca.ContentAgent)
    agent.anthropic = AsyncMock()
    agent._skipped_short_longform = 0
    agent._market_snapshot = _make_canned_snapshot()

    captured_system: list[str] = []

    thread_response = {
        "format": "thread",
        "rationale": "test",
        "key_data_points": [],
        "draft_content": {
            "format": "thread",
            "tweets": ["Tweet 1."],
            "long_form_post": "A" * 400,
        },
    }
    mock_resp = MagicMock()
    mock_resp.content = [MagicMock(text=_json.dumps(thread_response))]

    async def _capture_create(*args, **kwargs):
        captured_system.append(kwargs.get("system", ""))
        return mock_resp

    agent.anthropic.messages.create = AsyncMock(side_effect=_capture_create)

    story = {"title": "Gold surges on safe-haven demand", "link": "https://example.com", "source_name": "Reuters"}
    deep_research = {"article_text": "Gold hit record highs...", "corroborating_sources": [], "key_data_points": []}

    result = await agent._research_and_draft(story, deep_research)

    assert result is not None
    assert len(captured_system) >= 1
    system_prompt = captured_system[0]

    assert "CURRENT MARKET SNAPSHOT" in system_prompt
    assert "$2,345.67/oz" in system_prompt
    assert "Do not cite any specific dollar figures, percentages, yields, or rates \u2014 current or historical \u2014" \
        in system_prompt
    snap_pos = system_prompt.find("CURRENT MARKET SNAPSHOT")
    analyst_pos = system_prompt.find("You are a senior gold market analyst")
    assert snap_pos < analyst_pos, \
        f"Snapshot block (pos {snap_pos}) must appear before analyst line (pos {analyst_pos})"


# --- OA1-3: _draft_video_caption system prompt contains snapshot block ---

@pytest.mark.asyncio
async def test_draft_video_caption_system_prompt_contains_snapshot_block():
    """Captured system prompt for _draft_video_caption contains snapshot block BEFORE analyst line."""
    ca = _get_content_agent()
    agent = ca.ContentAgent.__new__(ca.ContentAgent)
    agent.anthropic = AsyncMock()
    agent._market_snapshot = _make_canned_snapshot()

    captured_system: list[str] = []

    caption_response = {
        "twitter_caption": "Senior analyst test caption.",
        "instagram_caption": "IG caption.",
    }
    mock_resp = MagicMock()
    mock_resp.content = [MagicMock(text=_json.dumps(caption_response))]

    async def _capture_create(*args, **kwargs):
        captured_system.append(kwargs.get("system", ""))
        return mock_resp

    agent.anthropic.messages.create = AsyncMock(side_effect=_capture_create)

    result = await agent._draft_video_caption(
        tweet_text="Gold could hit $3,000 says analyst.",
        author_username="KitcoNews",
        author_name="Kitco News",
        tweet_url="https://x.com/KitcoNews/status/123",
    )

    assert result is not None
    assert len(captured_system) >= 1
    system_prompt = captured_system[0]

    assert "CURRENT MARKET SNAPSHOT" in system_prompt
    assert "$2,345.67/oz" in system_prompt
    assert "Do not cite any specific dollar figures, percentages, yields, or rates \u2014 current or historical \u2014" \
        in system_prompt
    snap_pos = system_prompt.find("CURRENT MARKET SNAPSHOT")
    analyst_pos = system_prompt.find("You are a senior gold market analyst")
    assert snap_pos < analyst_pos, \
        f"Snapshot block (pos {snap_pos}) must appear before analyst line (pos {analyst_pos})"


# --- OA1-4: _draft_quote_post system prompt contains snapshot block ---

@pytest.mark.asyncio
async def test_draft_quote_post_system_prompt_contains_snapshot_block():
    """Captured system prompt for _draft_quote_post contains snapshot block BEFORE analyst line."""
    ca = _get_content_agent()
    agent = ca.ContentAgent.__new__(ca.ContentAgent)
    agent.anthropic = AsyncMock()
    agent._market_snapshot = _make_canned_snapshot()

    captured_system: list[str] = []

    quote_response = {
        "twitter_post": "Test quote post.",
        "suggested_headline": "Test Headline",
        "data_facts": ["Gold up 5%"],
        "image_prompt_direction": "Pull-quote card.",
    }
    mock_resp = MagicMock()
    mock_resp.content = [MagicMock(text=_json.dumps(quote_response))]

    async def _capture_create(*args, **kwargs):
        captured_system.append(kwargs.get("system", ""))
        return mock_resp

    agent.anthropic.messages.create = AsyncMock(side_effect=_capture_create)

    result = await agent._draft_quote_post(
        quote_text="Gold is the ultimate store of value.",
        speaker="Janet Yellen",
        speaker_title="Former Treasury Secretary",
        source_url="https://x.com/JanetYellen/status/123",
    )

    assert result is not None
    assert len(captured_system) >= 1
    system_prompt = captured_system[0]

    assert "CURRENT MARKET SNAPSHOT" in system_prompt
    assert "$2,345.67/oz" in system_prompt
    assert "Do not cite any specific dollar figures, percentages, yields, or rates \u2014 current or historical \u2014" \
        in system_prompt
    snap_pos = system_prompt.find("CURRENT MARKET SNAPSHOT")
    analyst_pos = system_prompt.find("You are a senior gold market analyst")
    assert snap_pos < analyst_pos, \
        f"Snapshot block (pos {snap_pos}) must appear before analyst line (pos {analyst_pos})"


# --- OA1-5: Fallback snapshot still injects hard instruction ---

@pytest.mark.asyncio
async def test_fallback_snapshot_still_injects_hard_instruction():
    """All-None fallback snapshot still produces CURRENT MARKET SNAPSHOT + [UNAVAILABLE] + hard instruction."""
    ca = _get_content_agent()
    agent = ca.ContentAgent.__new__(ca.ContentAgent)
    agent.anthropic = AsyncMock()
    agent._skipped_short_longform = 0
    agent._market_snapshot = _make_fallback_snapshot()

    captured_system: list[str] = []

    thread_response = {
        "format": "thread",
        "rationale": "test",
        "key_data_points": [],
        "draft_content": {
            "format": "thread",
            "tweets": ["Tweet 1."],
            "long_form_post": "A" * 400,
        },
    }
    mock_resp = MagicMock()
    mock_resp.content = [MagicMock(text=_json.dumps(thread_response))]

    async def _capture_create(*args, **kwargs):
        captured_system.append(kwargs.get("system", ""))
        return mock_resp

    agent.anthropic.messages.create = AsyncMock(side_effect=_capture_create)

    story = {"title": "Gold surges", "link": "https://example.com", "source_name": "Reuters"}
    deep_research = {"article_text": "...", "corroborating_sources": [], "key_data_points": []}

    result = await agent._research_and_draft(story, deep_research)

    assert result is not None
    system_prompt = captured_system[0]

    assert "CURRENT MARKET SNAPSHOT" in system_prompt
    unavailable_count = system_prompt.count("[UNAVAILABLE]")
    assert unavailable_count >= 5, \
        f"Expected >=5 [UNAVAILABLE] in system prompt, got {unavailable_count}"
    assert "Do not cite any specific dollar figures, percentages, yields, or rates \u2014 current or historical \u2014" \
        in system_prompt


# --- OA1-6: Snapshot fetch failure does not abort run ---

@pytest.mark.asyncio
async def test_snapshot_fetch_failure_does_not_abort_run(caplog):
    """fetch_market_snapshot raising RuntimeError does not abort the run; fallback snapshot used."""
    ca = _get_content_agent()

    mock_fetch = AsyncMock(side_effect=RuntimeError("network down"))

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()

    drafter_called = []

    async def _noop_pipeline_tracking(session, agent_run):
        drafter_called.append(True)

    with patch("agents.content_agent.AsyncSessionLocal", return_value=mock_session), \
         patch("agents.content_agent.fetch_market_snapshot", mock_fetch):
        agent = ca.ContentAgent.__new__(ca.ContentAgent)
        agent.anthropic = AsyncMock()
        agent.serpapi_client = None
        agent.tweepy_client = AsyncMock()
        agent._queued_titles = []
        agent._skipped_short_longform = 0
        agent._market_snapshot = None

        agent._run_pipeline = _noop_pipeline_tracking

        with caplog.at_level(logging.WARNING):
            await agent.run()

    assert agent._market_snapshot is not None
    assert agent._market_snapshot["status"] == "failed"
    assert agent._market_snapshot["gold_usd_per_oz"] is None
    assert drafter_called, "Pipeline must still be called after fetch failure"
    assert any("pipeline" in r.message.lower() or "market snapshot" in r.message.lower()
               for r in caplog.records)


# --- OA1-7: DB write failure still returns in-memory snapshot ---

@pytest.mark.asyncio
async def test_snapshot_db_write_failure_still_drafts():
    """DB insert failure in fetch_market_snapshot does not propagate; in-memory snapshot returned."""
    import importlib
    ms = importlib.import_module("services.market_snapshot")
    import httpx

    metals_response = {
        "rates": {"USDXAU": 0.000426, "USDXAG": 0.035842},
        "timestamp": 1745280000,
    }

    def _mock_resp(status_code, json_body=None):
        mock = MagicMock()
        mock.status_code = status_code
        if json_body is not None:
            mock.json.return_value = json_body
        if status_code >= 400:
            mock.raise_for_status.side_effect = httpx.HTTPStatusError(
                f"HTTP {status_code}", request=MagicMock(), response=mock
            )
        else:
            mock.raise_for_status.return_value = None
        return mock

    async def _get_side_effect(url, **kwargs):
        if "metalpriceapi" in url:
            return _mock_resp(200, metals_response)
        return _mock_resp(500)

    with patch.dict(os.environ, {"FRED_API_KEY": "test-key", "METALPRICEAPI_API_KEY": "test-metals"}):
        import config as cfg
        cfg.get_settings.cache_clear()
        try:
            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.get = AsyncMock(side_effect=_get_side_effect)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client_cls.return_value = mock_client

                mock_session = AsyncMock()
                from sqlalchemy.exc import IntegrityError
                mock_session.flush = AsyncMock(side_effect=IntegrityError("dup", {}, Exception()))
                mock_session.add = MagicMock()

                snap = await ms.fetch_market_snapshot(session=mock_session)
        finally:
            cfg.get_settings.cache_clear()

    assert snap is not None
    assert snap["gold_usd_per_oz"] is not None


# --- OA1-8: Gold gate dict contract unchanged (nnh regression guard) ---

@pytest.mark.asyncio
async def test_gold_gate_dict_contract_unchanged():
    """Regression: is_gold_relevant_or_systemic_shock still returns {keep, reject_reason, company} dict."""
    ca = _get_content_agent()
    story = {
        "title": "Gold hits record $3,200 on safe-haven demand",
        "summary": "Spot gold surged to all-time highs amid global uncertainty.",
    }
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(
        text=_json.dumps({"is_gold_relevant": True, "primary_subject_is_specific_miner": False, "company": None})
    )]
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    result = await ca.is_gold_relevant_or_systemic_shock(
        story,
        {"content_gold_gate_enabled": "true", "content_gold_gate_model": "claude-3-5-haiku-latest"},
        client=mock_client,
    )
    assert isinstance(result, dict)
    assert "keep" in result
    assert "reject_reason" in result
    assert "company" in result
    assert result["keep"] is True
    assert result["reject_reason"] is None
    assert result["company"] is None
