"""
Tests for Twitter Agent — TWIT-01 through TWIT-14.
All tests use mocked tweepy, mocked anthropic, and mocked DB sessions.

Wave 0 state: agents.twitter_agent does not exist yet.
Tests will FAIL with ImportError until the agent module is implemented in Plans 02-03.
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


def _get_twitter_agent():
    """Import agents.twitter_agent, raising ImportError if not yet implemented."""
    import importlib
    return importlib.import_module("agents.twitter_agent")


# ---------------------------------------------------------------------------
# TWIT-01: Scheduler wiring — TwitterAgent.run() is async callable
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scheduler_wiring():
    """
    TwitterAgent.run() must be an async callable (coroutine function).
    Covers: TWIT-01
    """
    import inspect
    ta = _get_twitter_agent()
    agent = ta.TwitterAgent()
    assert inspect.iscoroutinefunction(agent.run), (
        "TwitterAgent.run must be an async def (coroutine function)"
    )


# ---------------------------------------------------------------------------
# TWIT-02: Composite scoring formula
# ---------------------------------------------------------------------------

def test_scoring_formula():
    """
    composite_score uses engagement(40%) + authority(30%) + relevance(30%) weights.
    Covers: TWIT-02
    """
    ta = _get_twitter_agent()

    # With all scores at 10.0 → composite = 10.0
    score = ta.calculate_composite_score(
        engagement_score=10.0,
        authority_score=10.0,
        relevance_score=10.0,
    )
    assert abs(score - 10.0) < 0.01, f"Expected 10.0, got {score}"

    # Test weight: engagement 40%
    score_engagement_only = ta.calculate_composite_score(
        engagement_score=10.0, authority_score=0.0, relevance_score=0.0
    )
    assert abs(score_engagement_only - 4.0) < 0.01, (
        f"Engagement weight should be 40% (4.0), got {score_engagement_only}"
    )

    # Test weight: authority 30%
    score_authority_only = ta.calculate_composite_score(
        engagement_score=0.0, authority_score=10.0, relevance_score=0.0
    )
    assert abs(score_authority_only - 3.0) < 0.01, (
        f"Authority weight should be 30% (3.0), got {score_authority_only}"
    )

    # Test weight: relevance 30%
    score_relevance_only = ta.calculate_composite_score(
        engagement_score=0.0, authority_score=0.0, relevance_score=10.0
    )
    assert abs(score_relevance_only - 3.0) < 0.01, (
        f"Relevance weight should be 30% (3.0), got {score_relevance_only}"
    )


# ---------------------------------------------------------------------------
# TWIT-03: Engagement score formula
# ---------------------------------------------------------------------------

def test_engagement_formula():
    """
    engagement_score = likes*1 + retweets*2 + replies*1.5
    Covers: TWIT-03
    """
    ta = _get_twitter_agent()

    # 100*1 + 50*2 + 40*1.5 = 100 + 100 + 60 = 260
    score = ta.calculate_engagement_score(likes=100, retweets=50, replies=40)
    assert score == 260.0, f"Expected 260.0, got {score}"

    assert ta.calculate_engagement_score(0, 0, 0) == 0.0
    # Only likes (weight 1)
    assert ta.calculate_engagement_score(likes=10, retweets=0, replies=0) == 10.0
    # Only retweets (weight 2)
    assert ta.calculate_engagement_score(likes=0, retweets=5, replies=0) == 10.0
    # Only replies (weight 1.5)
    assert ta.calculate_engagement_score(likes=0, retweets=0, replies=4) == 6.0


# ---------------------------------------------------------------------------
# TWIT-04: Engagement gate — watchlist accounts
# ---------------------------------------------------------------------------

def test_engagement_gate_watchlist():
    """
    Watchlist accounts must have 50+ likes AND 5000+ views to pass the engagement gate.
    Covers: TWIT-04
    """
    ta = _get_twitter_agent()

    # Pass: both thresholds met
    assert ta.passes_engagement_gate(likes=50, impression_count=5000, is_watchlist=True) is True
    # Fail: likes below threshold
    assert ta.passes_engagement_gate(likes=49, impression_count=5000, is_watchlist=True) is False
    # Fail: views below threshold
    assert ta.passes_engagement_gate(likes=50, impression_count=4999, is_watchlist=True) is False
    # Fail: both below threshold
    assert ta.passes_engagement_gate(likes=10, impression_count=100, is_watchlist=True) is False


def test_engagement_gate_non_watchlist():
    """
    Non-watchlist accounts must have 500+ likes AND 40000+ views to pass.
    Covers: TWIT-04
    """
    ta = _get_twitter_agent()

    # Pass: both thresholds met
    assert ta.passes_engagement_gate(likes=500, impression_count=40000, is_watchlist=False) is True
    # Fail: likes below threshold
    assert ta.passes_engagement_gate(likes=499, impression_count=40000, is_watchlist=False) is False
    # Fail: views below threshold
    assert ta.passes_engagement_gate(likes=500, impression_count=39999, is_watchlist=False) is False


def test_engagement_gate_none_views():
    """
    impression_count=None (Basic tier API doesn't return impressions) skips the
    views check — only likes are evaluated.
    Covers: TWIT-04
    """
    ta = _get_twitter_agent()

    # None views + sufficient likes → pass (views check skipped)
    assert ta.passes_engagement_gate(likes=50, impression_count=None, is_watchlist=True) is True
    assert ta.passes_engagement_gate(likes=500, impression_count=None, is_watchlist=False) is True

    # None views + insufficient likes → fail (likes check still enforced)
    assert ta.passes_engagement_gate(likes=49, impression_count=None, is_watchlist=True) is False
    assert ta.passes_engagement_gate(likes=499, impression_count=None, is_watchlist=False) is False


# ---------------------------------------------------------------------------
# TWIT-05: Recency decay
# ---------------------------------------------------------------------------

def test_recency_decay_under_1h():
    """
    Posts under 1 hour old receive full score (no decay, factor = 1.0).
    Covers: TWIT-05
    """
    ta = _get_twitter_agent()
    now = datetime.now(timezone.utc)
    created_at = now - timedelta(minutes=30)
    decayed = ta.apply_recency_decay(score=8.0, created_at=created_at)
    assert decayed == 8.0, f"Under 1h should return full score 8.0, got {decayed}"


def test_recency_decay_at_4h():
    """
    Posts at 4 hours old receive 50% score (decay factor = 0.5).
    Covers: TWIT-05
    """
    ta = _get_twitter_agent()
    now = datetime.now(timezone.utc)
    created_at = now - timedelta(hours=4)
    decayed = ta.apply_recency_decay(score=8.0, created_at=created_at)
    assert abs(decayed - 4.0) < 0.1, f"At 4h should return ~50% score (4.0), got {decayed}"


def test_recency_decay_at_6h():
    """
    Posts at 6 hours old or older receive 0 score (expired).
    Covers: TWIT-05
    """
    ta = _get_twitter_agent()
    now = datetime.now(timezone.utc)
    created_at = now - timedelta(hours=6)
    decayed = ta.apply_recency_decay(score=8.0, created_at=created_at)
    assert decayed == 0.0, f"At 6h should return 0 (expired), got {decayed}"

    # 7h also expired
    created_at_7h = now - timedelta(hours=7)
    assert ta.apply_recency_decay(score=5.0, created_at=created_at_7h) == 0.0


# ---------------------------------------------------------------------------
# TWIT-06: Top N selection
# ---------------------------------------------------------------------------

def test_top_n_selection():
    """
    Top 3-5 posts are selected by composite score descending.
    Covers: TWIT-06
    """
    ta = _get_twitter_agent()
    posts = [
        {"id": "1", "score": 3.0},
        {"id": "2", "score": 9.5},
        {"id": "3", "score": 7.2},
        {"id": "4", "score": 8.1},
        {"id": "5", "score": 5.5},
        {"id": "6", "score": 6.8},
        {"id": "7", "score": 2.1},
        {"id": "8", "score": 8.9},
    ]
    selected = ta.select_top_posts(posts, top_n=5)
    assert len(selected) == 5, f"Expected 5 posts, got {len(selected)}"
    scores = [p["score"] for p in selected]
    assert scores == sorted(scores, reverse=True), "Posts must be sorted by score descending"
    assert selected[0]["score"] == 9.5, "Top post must have highest score"

    # Fewer posts than top_n → return all
    few = [{"id": "a", "score": 5.0}, {"id": "b", "score": 3.0}]
    assert len(ta.select_top_posts(few, top_n=5)) == 2


# ---------------------------------------------------------------------------
# TWIT-07: Draft types — reply + retweet-with-comment
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_draft_produces_reply_and_rt():
    """
    Each post yields both a reply draft AND a retweet-with-comment draft.
    Covers: TWIT-07
    """
    ta = _get_twitter_agent()
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=MagicMock(
        content=[MagicMock(text='["draft text 1", "draft text 2", "draft text 3"]')]
    ))

    post = {
        "id": "tweet123",
        "text": "Gold hits $3000/oz as central banks increase reserves",
        "source_account": "@goldanalyst",
        "created_at": datetime.now(timezone.utc),
        "score": 8.5,
    }

    with patch("agents.twitter_agent.AsyncAnthropic", return_value=mock_client):
        result = await ta.draft_for_post(post=post, client=mock_client)

    assert "reply" in result, "Result must contain 'reply' key"
    assert "retweet_with_comment" in result, "Result must contain 'retweet_with_comment' key"


# ---------------------------------------------------------------------------
# TWIT-08: Draft alternatives (2-3 per draft type)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_draft_has_2_to_3_alternatives():
    """
    Each draft type (reply + RT) produces 2-3 alternatives.
    Covers: TWIT-08
    """
    ta = _get_twitter_agent()
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=MagicMock(
        content=[MagicMock(text='["alt 1", "alt 2", "alt 3"]')]
    ))

    post = {
        "id": "tweet456",
        "text": "Central bank gold demand at 40-year high",
        "source_account": "@centralbanker",
        "created_at": datetime.now(timezone.utc),
        "score": 7.0,
    }

    with patch("agents.twitter_agent.AsyncAnthropic", return_value=mock_client):
        result = await ta.draft_for_post(post=post, client=mock_client)

    reply_count = len(result["reply"])
    rt_count = len(result["retweet_with_comment"])
    assert 2 <= reply_count <= 3, f"Reply must have 2-3 alternatives, got {reply_count}"
    assert 2 <= rt_count <= 3, f"RT must have 2-3 alternatives, got {rt_count}"


# ---------------------------------------------------------------------------
# TWIT-09, TWIT-10: Compliance checker invoked per alternative
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_compliance_called_per_alternative():
    """
    Compliance checker is invoked once per alternative, separate from drafting.
    Covers: TWIT-09, TWIT-10
    """
    ta = _get_twitter_agent()
    mock_client = AsyncMock()
    # All pass compliance
    mock_client.messages.create = AsyncMock(return_value=MagicMock(
        content=[MagicMock(text="PASS")]
    ))

    alternatives = ["draft 1", "draft 2", "draft 3"]
    with patch("agents.twitter_agent.AsyncAnthropic", return_value=mock_client):
        result = await ta.filter_compliant_alternatives(
            alternatives=alternatives, client=mock_client
        )

    # Must have called check_compliance once per alternative (3 times)
    assert mock_client.messages.create.call_count == len(alternatives), (
        f"Expected {len(alternatives)} compliance checks, got {mock_client.messages.create.call_count}"
    )
    assert len(result) == 3, f"All passing → 3 alternatives kept, got {len(result)}"


@pytest.mark.asyncio
async def test_compliance_failure_drops_alternative():
    """
    Failing alternative is removed; passing alternatives are kept.
    Covers: TWIT-10
    """
    ta = _get_twitter_agent()
    mock_client = AsyncMock()
    # First passes, second fails, third passes
    mock_client.messages.create = AsyncMock(side_effect=[
        MagicMock(content=[MagicMock(text="PASS")]),
        MagicMock(content=[MagicMock(text="FAIL")]),
        MagicMock(content=[MagicMock(text="PASS")]),
    ])

    with patch("agents.twitter_agent.AsyncAnthropic", return_value=mock_client):
        result = await ta.filter_compliant_alternatives(
            alternatives=["alt 1", "alt 2", "alt 3"], client=mock_client
        )

    assert len(result) == 2, f"Expected 2 passing alternatives, got {len(result)}"
    assert "alt 2" not in result, "Failing alternative must be removed"
    assert "alt 1" in result and "alt 3" in result, "Passing alternatives must be kept"


@pytest.mark.asyncio
async def test_compliance_all_fail_skips_post():
    """
    If all alternatives fail compliance, the post is not queued (empty list returned).
    Covers: TWIT-10
    """
    ta = _get_twitter_agent()
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=MagicMock(
        content=[MagicMock(text="FAIL")]
    ))

    with patch("agents.twitter_agent.AsyncAnthropic", return_value=mock_client):
        result = await ta.filter_compliant_alternatives(
            alternatives=["alt 1", "alt 2"], client=mock_client
        )

    assert result == [], f"All-fail should return empty list, got {result}"


# ---------------------------------------------------------------------------
# TWIT-11, TWIT-13: Quota counter — read, increment, month reset
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_quota_counter_increments():
    """
    Tweet count is incremented by the number of tweets read from the API.
    Covers: TWIT-11
    """
    ta = _get_twitter_agent()
    mock_session = AsyncMock()
    mock_config = MagicMock()
    mock_config.value = "500"
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=mock_config)
    mock_session.execute = AsyncMock(return_value=mock_result)

    await ta.increment_quota(session=mock_session, count=150)

    assert mock_session.execute.called, "increment_quota must call session.execute"


@pytest.mark.asyncio
async def test_quota_readable():
    """
    Config table quota value can be read via get_quota().
    Covers: TWIT-13
    """
    ta = _get_twitter_agent()
    mock_session = AsyncMock()
    mock_config = MagicMock()
    mock_config.value = "7500"
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=mock_config)
    mock_session.execute = AsyncMock(return_value=mock_result)

    value = await ta.get_quota(session=mock_session)
    assert value == 7500, f"Expected quota 7500, got {value}"


@pytest.mark.asyncio
async def test_quota_month_reset():
    """
    Counter resets on the first run of a new calendar month.
    Covers: TWIT-11
    """
    ta = _get_twitter_agent()
    mock_session = AsyncMock()
    # Simulate last_reset stored as previous month
    last_month = (datetime.now(timezone.utc).replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
    mock_last_reset = MagicMock()
    mock_last_reset.value = last_month
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=mock_last_reset)
    mock_session.execute = AsyncMock(return_value=mock_result)

    reset_occurred = await ta.reset_quota_if_new_month(session=mock_session)
    assert reset_occurred is True, "Should return True when monthly reset is triggered"


# ---------------------------------------------------------------------------
# TWIT-12: Quota hard stop
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_quota_hard_stop():
    """
    Agent returns early when quota >= (20000 - safety_margin).
    Covers: TWIT-12
    """
    ta = _get_twitter_agent()
    mock_session = AsyncMock()

    # Quota at 19500 → should trigger hard stop (threshold = 20000 - 500)
    mock_config = MagicMock()
    mock_config.value = "19500"
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=mock_config)
    mock_session.execute = AsyncMock(return_value=mock_result)

    is_exceeded = await ta.is_quota_exceeded(session=mock_session)
    assert is_exceeded is True, "Should return True when quota reaches hard stop threshold"

    # Below threshold → no hard stop
    mock_config_low = MagicMock()
    mock_config_low.value = "5000"
    mock_result_low = MagicMock()
    mock_result_low.scalar_one_or_none = MagicMock(return_value=mock_config_low)
    mock_session.execute = AsyncMock(return_value=mock_result_low)

    is_exceeded_low = await ta.is_quota_exceeded(session=mock_session)
    assert is_exceeded_low is False, "Should return False when quota is below threshold"


# ---------------------------------------------------------------------------
# TWIT-14: Rationale populated on every DraftItem
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rationale_populated():
    """
    Every DraftItem.rationale is a non-empty string.
    Covers: TWIT-14
    """
    ta = _get_twitter_agent()
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=MagicMock(
        content=[MagicMock(text='["Gold sentiment is elevated due to central bank demand"]')]
    ))

    post = {
        "id": "tweet789",
        "text": "Gold prices surge as dollar weakens",
        "source_account": "@goldinvestor",
        "created_at": datetime.now(timezone.utc),
        "score": 9.0,
    }

    with patch("agents.twitter_agent.AsyncAnthropic", return_value=mock_client):
        draft_item = await ta.build_draft_item(post=post, client=mock_client)

    assert draft_item.rationale is not None, "DraftItem.rationale must not be None"
    assert isinstance(draft_item.rationale, str), "DraftItem.rationale must be a string"
    assert len(draft_item.rationale.strip()) > 0, "DraftItem.rationale must be non-empty"


# ---------------------------------------------------------------------------
# Phase 10 — WhatsApp new-item notification tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_twitter_whatsapp_notification_fires_when_items_queued():
    """send_whatsapp_message is called with Twitter item count when items_queued > 0."""
    import sys
    from agents.twitter_agent import TwitterAgent
    from unittest.mock import patch, AsyncMock, MagicMock

    agent = TwitterAgent.__new__(TwitterAgent)

    mock_session = AsyncMock()
    mock_agent_run = MagicMock()
    mock_agent_run.items_found = 0
    mock_agent_run.items_filtered = None
    mock_agent_run.errors = []

    # Inject a mock senior_agent module so lazy import inside _run_pipeline succeeds
    mock_senior = MagicMock()
    mock_senior.process_new_items = AsyncMock()

    # Patch all internal steps to return minimal valid data
    with patch.dict(sys.modules, {"agents.senior_agent": mock_senior}), \
         patch.object(agent, "_check_quota", return_value=(True, 0)), \
         patch.object(agent, "_get_config", return_value=MagicMock(value="500")), \
         patch.object(agent, "_load_watchlist", return_value=[]), \
         patch.object(agent, "_get_last_run_time", return_value=datetime.now(timezone.utc)), \
         patch.object(agent, "_fetch_watchlist_tweets", return_value=[]), \
         patch.object(agent, "_process_drafts", return_value=(3, 0, [], ["id1", "id2", "id3"])), \
         patch("services.whatsapp.send_whatsapp_message", new_callable=AsyncMock) as mock_wa:

        mock_session.commit = AsyncMock()
        await agent._run_pipeline(mock_session, mock_agent_run)

    mock_wa.assert_called_once()
    call_args = mock_wa.call_args[0][0]
    assert "Twitter" in call_args
    assert "3" in call_args


@pytest.mark.asyncio
async def test_twitter_whatsapp_notification_skipped_when_no_items():
    """send_whatsapp_message is NOT called when items_queued == 0."""
    from agents.twitter_agent import TwitterAgent
    from unittest.mock import patch, AsyncMock, MagicMock

    agent = TwitterAgent.__new__(TwitterAgent)

    mock_session = AsyncMock()
    mock_agent_run = MagicMock()
    mock_agent_run.items_found = 0
    mock_agent_run.items_filtered = None
    mock_agent_run.errors = []

    # No items queued so senior_agent lazy import is never triggered
    with patch.object(agent, "_check_quota", return_value=(True, 0)), \
         patch.object(agent, "_get_config", return_value=MagicMock(value="500")), \
         patch.object(agent, "_load_watchlist", return_value=[]), \
         patch.object(agent, "_get_last_run_time", return_value=datetime.now(timezone.utc)), \
         patch.object(agent, "_fetch_watchlist_tweets", return_value=[]), \
         patch.object(agent, "_process_drafts", return_value=(0, 0, [], [])), \
         patch("services.whatsapp.send_whatsapp_message", new_callable=AsyncMock) as mock_wa:

        mock_session.commit = AsyncMock()
        await agent._run_pipeline(mock_session, mock_agent_run)

    mock_wa.assert_not_called()


@pytest.mark.asyncio
async def test_twitter_whatsapp_failure_is_non_fatal():
    """WhatsApp exception does not propagate — agent_run is still completed."""
    import sys
    from agents.twitter_agent import TwitterAgent
    from unittest.mock import patch, AsyncMock, MagicMock

    agent = TwitterAgent.__new__(TwitterAgent)

    mock_session = AsyncMock()
    mock_agent_run = MagicMock()
    mock_agent_run.items_found = 0
    mock_agent_run.items_filtered = None
    mock_agent_run.errors = []

    mock_senior = MagicMock()
    mock_senior.process_new_items = AsyncMock()

    with patch.dict(sys.modules, {"agents.senior_agent": mock_senior}), \
         patch.object(agent, "_check_quota", return_value=(True, 0)), \
         patch.object(agent, "_get_config", return_value=MagicMock(value="500")), \
         patch.object(agent, "_load_watchlist", return_value=[]), \
         patch.object(agent, "_get_last_run_time", return_value=datetime.now(timezone.utc)), \
         patch.object(agent, "_fetch_watchlist_tweets", return_value=[]), \
         patch.object(agent, "_process_drafts", return_value=(2, 0, [], ["id1", "id2"])), \
         patch("services.whatsapp.send_whatsapp_message", side_effect=Exception("Twilio down")):

        mock_session.commit = AsyncMock()
        # Must NOT raise
        await agent._run_pipeline(mock_session, mock_agent_run)


# ---------------------------------------------------------------------------
# OP-LW4-04: Gold Telegraph universal bypass
# ---------------------------------------------------------------------------

def test_always_engage_handles_constant():
    """ALWAYS_ENGAGE_HANDLES constant exists and contains 'goldtelegraph_'."""
    from agents.twitter_agent import ALWAYS_ENGAGE_HANDLES
    assert "goldtelegraph_" in ALWAYS_ENGAGE_HANDLES, (
        "ALWAYS_ENGAGE_HANDLES must contain 'goldtelegraph_' (lowercased)"
    )


@pytest.mark.asyncio
async def test_gold_telegraph_bypasses_topic_and_engagement_filters(caplog):
    """GoldTelegraph_ tweet with 0 likes and no gold keyword reaches scoring.

    A Reuters tweet with the same properties (0 likes, no gold keyword) must NOT
    reach scoring. Asserts that:
    - _score_tweet is called exactly once (for GoldTelegraph_).
    - The bypass log lines appear for GoldTelegraph_ in both Step 6 and Step 7.
    - The Reuters tweet is silently dropped at the topic-filter step.
    """
    import sys
    import logging
    from agents.twitter_agent import TwitterAgent

    agent = TwitterAgent.__new__(TwitterAgent)

    # Two fake watchlist tweets — neither mentions gold, neither has likes.
    gt_tweet = {
        "id": "gt-tweet-1",
        "text": "The Fed just printed more money",
        "created_at": datetime.now(timezone.utc) - timedelta(hours=1),
        "author_id": "111",
        "account_handle": "GoldTelegraph_",
        "likes": 0,
        "retweets": 0,
        "replies": 0,
        "views": None,
        "is_watchlist": True,
        "relationship_value": 5,
        "follower_count": 50000,
    }
    reuters_tweet = {
        "id": "reuters-tweet-1",
        "text": "Oil prices rise on supply worries",
        "created_at": datetime.now(timezone.utc) - timedelta(hours=1),
        "author_id": "222",
        "account_handle": "Reuters",
        "likes": 0,
        "retweets": 0,
        "replies": 0,
        "views": None,
        "is_watchlist": True,
        "relationship_value": 1,
        "follower_count": 5000000,
    }

    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_agent_run = MagicMock()
    mock_agent_run.items_found = 0
    mock_agent_run.items_filtered = None
    mock_agent_run.errors = []

    score_tweet_calls: list[dict] = []

    def fake_score_tweet(tweet: dict) -> dict:
        score_tweet_calls.append(tweet)
        return {**tweet, "composite_score": 5.0, "engagement_score": 0.0}

    mock_senior = MagicMock()
    mock_senior.process_new_items = AsyncMock()

    with patch.dict(sys.modules, {"agents.senior_agent": mock_senior}), \
         patch.object(agent, "_check_quota", return_value=(True, 0)), \
         patch.object(agent, "_get_config", return_value=MagicMock(value="50")), \
         patch.object(agent, "_load_watchlist", return_value=[]), \
         patch.object(agent, "_get_last_run_time", return_value=datetime.now(timezone.utc)), \
         patch.object(agent, "_fetch_watchlist_tweets", return_value=[gt_tweet, reuters_tweet]), \
         patch.object(agent, "_score_tweet", side_effect=fake_score_tweet), \
         patch.object(agent, "_process_drafts", return_value=(1, 0, [], ["gt-tweet-1"])), \
         patch("services.whatsapp.send_whatsapp_message", new_callable=AsyncMock), \
         caplog.at_level(logging.INFO, logger="agents.twitter_agent"):

        await agent._run_pipeline(mock_session, mock_agent_run)

    # GoldTelegraph_ must have reached _score_tweet; Reuters must not have.
    assert len(score_tweet_calls) == 1, (
        f"Expected exactly 1 tweet to reach scoring (GoldTelegraph_), got {len(score_tweet_calls)}: "
        f"{[t.get('account_handle') for t in score_tweet_calls]}"
    )
    assert score_tweet_calls[0]["account_handle"] == "GoldTelegraph_", (
        "The tweet that reached scoring must be from GoldTelegraph_"
    )

    # Both bypass log lines must appear for GoldTelegraph_
    assert "always-engage bypass" in caplog.text, (
        "Expected 'always-engage bypass' log line for GoldTelegraph_ tweet"
    )
    assert "skipped topic filter" in caplog.text, (
        "Expected 'skipped topic filter' log entry for GoldTelegraph_"
    )
    assert "skipped engagement gate" in caplog.text, (
        "Expected 'skipped engagement gate' log entry for GoldTelegraph_"
    )
