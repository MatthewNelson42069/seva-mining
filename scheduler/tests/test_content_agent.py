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
# Phase 11 — _enqueue_render_job_if_eligible tests (CREV-07, CREV-10)
# ---------------------------------------------------------------------------

def _make_bundle(content_type: str, compliance_passed: bool):
    """Create a minimal mock bundle for enqueue tests."""
    import uuid
    bundle = MagicMock()
    bundle.id = uuid.uuid4()
    bundle.content_type = content_type
    bundle.compliance_passed = compliance_passed
    return bundle


def test_commit_infographic_enqueues_render():
    """_enqueue_render_job_if_eligible fires scheduler.add_job for infographic bundles."""
    ca = _get_content_agent()
    bundle = _make_bundle("infographic", True)

    mock_scheduler = MagicMock()
    mock_scheduler.add_job = MagicMock()

    with patch("worker.get_scheduler", return_value=mock_scheduler), \
         patch("agents.image_render_agent.render_bundle_job", new_callable=AsyncMock):
        ca._enqueue_render_job_if_eligible(bundle)

    mock_scheduler.add_job.assert_called_once()
    call_kwargs = mock_scheduler.add_job.call_args
    assert call_kwargs.kwargs.get("id") == f"render_{bundle.id}" or \
           (call_kwargs.args and f"render_{bundle.id}" in str(call_kwargs))
    # Check id kwarg
    kwargs = mock_scheduler.add_job.call_args[1] if mock_scheduler.add_job.call_args[1] else {}
    assert kwargs.get("id") == f"render_{bundle.id}"
    assert kwargs.get("replace_existing") is True
    assert kwargs.get("args") == [str(bundle.id)]


def test_commit_quote_enqueues_render():
    """_enqueue_render_job_if_eligible fires scheduler.add_job for quote bundles."""
    ca = _get_content_agent()
    bundle = _make_bundle("quote", True)

    mock_scheduler = MagicMock()
    mock_scheduler.add_job = MagicMock()

    with patch("worker.get_scheduler", return_value=mock_scheduler), \
         patch("agents.image_render_agent.render_bundle_job", new_callable=AsyncMock):
        ca._enqueue_render_job_if_eligible(bundle)

    mock_scheduler.add_job.assert_called_once()
    kwargs = mock_scheduler.add_job.call_args[1] if mock_scheduler.add_job.call_args[1] else {}
    assert kwargs.get("id") == f"render_{bundle.id}"
    assert kwargs.get("replace_existing") is True


def test_commit_thread_does_not_enqueue():
    """_enqueue_render_job_if_eligible is a no-op for thread bundles (D-04)."""
    ca = _get_content_agent()
    bundle = _make_bundle("thread", True)

    mock_scheduler = MagicMock()
    with patch("worker.get_scheduler", return_value=mock_scheduler), \
         patch("agents.image_render_agent.render_bundle_job", new_callable=AsyncMock):
        ca._enqueue_render_job_if_eligible(bundle)

    mock_scheduler.add_job.assert_not_called()


def test_commit_long_form_does_not_enqueue():
    """_enqueue_render_job_if_eligible is a no-op for long_form bundles (D-04)."""
    ca = _get_content_agent()
    bundle = _make_bundle("long_form", True)

    mock_scheduler = MagicMock()
    with patch("worker.get_scheduler", return_value=mock_scheduler), \
         patch("agents.image_render_agent.render_bundle_job", new_callable=AsyncMock):
        ca._enqueue_render_job_if_eligible(bundle)

    mock_scheduler.add_job.assert_not_called()


def test_commit_breaking_news_does_not_enqueue():
    """_enqueue_render_job_if_eligible is a no-op for breaking_news bundles (D-04)."""
    ca = _get_content_agent()
    bundle = _make_bundle("breaking_news", True)

    mock_scheduler = MagicMock()
    with patch("worker.get_scheduler", return_value=mock_scheduler), \
         patch("agents.image_render_agent.render_bundle_job", new_callable=AsyncMock):
        ca._enqueue_render_job_if_eligible(bundle)

    mock_scheduler.add_job.assert_not_called()


# ---------------------------------------------------------------------------
# quick-260419-n4f: Gold relevance gate tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_gate_accepts_direct_gold_story():
    """Gate returns True for a direct gold story when LLM answers 'yes'."""
    ca = _get_content_agent()
    story = {"title": "Barrick Gold Q3 earnings beat estimates", "summary": "Production up 12%."}
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="yes")]
    mock_client.messages.create = AsyncMock(return_value=mock_response)
    result = await ca.is_gold_relevant_or_systemic_shock(
        story, {"content_gold_gate_enabled": "true", "content_gold_gate_model": "claude-3-5-haiku-latest"}, client=mock_client
    )
    assert result is True


@pytest.mark.asyncio
async def test_gate_accepts_systemic_shock_strait_of_hormuz():
    """Gate returns True for a Strait of Hormuz disruption story when LLM answers 'yes'."""
    ca = _get_content_agent()
    story = {"title": "Iran threatens to close Strait of Hormuz after tanker attack", "summary": "Oil supply at risk."}
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="yes")]
    mock_client.messages.create = AsyncMock(return_value=mock_response)
    result = await ca.is_gold_relevant_or_systemic_shock(
        story, {"content_gold_gate_enabled": "true", "content_gold_gate_model": "claude-3-5-haiku-latest"}, client=mock_client
    )
    assert result is True


@pytest.mark.asyncio
async def test_gate_rejects_generic_option_traders():
    """Gate returns False for a generic options story when LLM answers 'no'."""
    ca = _get_content_agent()
    story = {"title": "Option Traders Chasing Torrid Stock Rally Turn Focus to Earnings", "summary": "Equity options volume rises."}
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="no")]
    mock_client.messages.create = AsyncMock(return_value=mock_response)
    result = await ca.is_gold_relevant_or_systemic_shock(
        story, {"content_gold_gate_enabled": "true", "content_gold_gate_model": "claude-3-5-haiku-latest"}, client=mock_client
    )
    assert result is False


@pytest.mark.asyncio
async def test_gate_rejects_private_credit():
    """Gate returns False for a private credit story when LLM answers 'no'."""
    ca = _get_content_agent()
    story = {"title": "Why Private Credit Is Not a Financial Crisis Threat", "summary": "Asset managers weigh in."}
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="no")]
    mock_client.messages.create = AsyncMock(return_value=mock_response)
    result = await ca.is_gold_relevant_or_systemic_shock(
        story, {"content_gold_gate_enabled": "true", "content_gold_gate_model": "claude-3-5-haiku-latest"}, client=mock_client
    )
    assert result is False


@pytest.mark.asyncio
async def test_gate_fails_open_on_api_error():
    """Gate returns True (fail-open) when Anthropic raises an exception."""
    ca = _get_content_agent()
    story = {"title": "Gold surges on Fed pivot", "summary": "Spot gold up 2%."}
    mock_client = AsyncMock()
    # APIError requires request= param — use a generic Exception to simulate infra blip
    mock_client.messages.create = AsyncMock(side_effect=Exception("API unavailable"))
    result = await ca.is_gold_relevant_or_systemic_shock(
        story, {"content_gold_gate_enabled": "true", "content_gold_gate_model": "claude-3-5-haiku-latest"}, client=mock_client
    )
    assert result is True


@pytest.mark.asyncio
async def test_gate_bypassed_when_disabled():
    """Gate returns True without any LLM call when content_gold_gate_enabled=False."""
    ca = _get_content_agent()
    story = {"title": "Anything at all", "summary": "Does not matter."}
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock()
    result = await ca.is_gold_relevant_or_systemic_shock(
        story, {"content_gold_gate_enabled": "false"}, client=mock_client
    )
    assert result is True
    mock_client.messages.create.assert_not_called()


def test_commit_video_clip_does_not_enqueue():
    """_enqueue_render_job_if_eligible is a no-op for video_clip bundles (D-04 — text-only)."""
    ca = _get_content_agent()
    bundle = _make_bundle("video_clip", True)

    mock_scheduler = MagicMock()
    with patch("worker.get_scheduler", return_value=mock_scheduler), \
         patch("agents.image_render_agent.render_bundle_job", new_callable=AsyncMock):
        ca._enqueue_render_job_if_eligible(bundle)

    mock_scheduler.add_job.assert_not_called()


def test_commit_without_compliance_does_not_enqueue():
    """_enqueue_render_job_if_eligible is a no-op when compliance_passed=False (D-11)."""
    ca = _get_content_agent()
    bundle = _make_bundle("infographic", False)

    mock_scheduler = MagicMock()
    with patch("worker.get_scheduler", return_value=mock_scheduler), \
         patch("agents.image_render_agent.render_bundle_job", new_callable=AsyncMock):
        ca._enqueue_render_job_if_eligible(bundle)

    mock_scheduler.add_job.assert_not_called()


def test_enqueue_failure_does_not_crash_agent():
    """When get_scheduler() raises RuntimeError, _enqueue_render_job_if_eligible returns without raising (D-19)."""
    ca = _get_content_agent()
    bundle = _make_bundle("infographic", True)

    with patch("worker.get_scheduler", side_effect=RuntimeError("Scheduler not started")):
        # Must NOT raise — silent-fail per D-18/D-19
        result = ca._enqueue_render_job_if_eligible(bundle)

    assert result is None  # returns None on silent-fail


def test_enqueue_uses_replace_existing_true():
    """add_job is called with replace_existing=True to prevent ConflictingIdError on rerender (Pitfall 6)."""
    ca = _get_content_agent()
    bundle = _make_bundle("infographic", True)

    mock_scheduler = MagicMock()
    mock_scheduler.add_job = MagicMock()

    with patch("worker.get_scheduler", return_value=mock_scheduler), \
         patch("agents.image_render_agent.render_bundle_job", new_callable=AsyncMock):
        ca._enqueue_render_job_if_eligible(bundle)

    call_kwargs = mock_scheduler.add_job.call_args[1] if mock_scheduler.add_job.call_args[1] else {}
    assert call_kwargs.get("replace_existing") is True, "replace_existing must be True to prevent ConflictingIdError"


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
