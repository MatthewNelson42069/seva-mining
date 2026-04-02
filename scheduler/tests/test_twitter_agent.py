"""
Tests for Twitter Agent — TWIT-01 through TWIT-14.
All tests use mocked tweepy, mocked anthropic, and mocked DB sessions.

Pure function tests (scoring, gates, decay) run without mocking.
Integration tests mock tweepy.asynchronous.AsyncClient and AsyncAnthropic.
"""
import os
import sys
import inspect
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Set required env vars before any imports (Settings validates at import time)
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://fake-pooler.neon.tech/db?sslmode=require")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test-fake")
os.environ.setdefault("TWILIO_ACCOUNT_SID", "x")
os.environ.setdefault("TWILIO_AUTH_TOKEN", "x")
os.environ.setdefault("TWILIO_WHATSAPP_FROM", "whatsapp:+1x")
os.environ.setdefault("DIGEST_WHATSAPP_TO", "whatsapp:+1x")
os.environ.setdefault("X_API_BEARER_TOKEN", "test-bearer-token")
os.environ.setdefault("X_API_KEY", "test-key")
os.environ.setdefault("X_API_SECRET", "test-secret")
os.environ.setdefault("APIFY_API_TOKEN", "x")
os.environ.setdefault("SERPAPI_API_KEY", "x")
os.environ.setdefault("FRONTEND_URL", "https://x.com")

twitter_agent_mod = pytest.importorskip(
    "agents.twitter_agent",
    reason="agents.twitter_agent not yet implemented",
)
calculate_engagement_score = twitter_agent_mod.calculate_engagement_score
calculate_composite_score = twitter_agent_mod.calculate_composite_score
apply_recency_decay = twitter_agent_mod.apply_recency_decay
passes_engagement_gate = twitter_agent_mod.passes_engagement_gate
select_top_posts = twitter_agent_mod.select_top_posts
TwitterAgent = twitter_agent_mod.TwitterAgent


# ---------------------------------------------------------------------------
# TWIT-03: Engagement formula — likes*1 + retweets*2 + replies*1.5
# ---------------------------------------------------------------------------

def test_engagement_formula_basic():
    """TWIT-03: engagement = likes*1 + retweets*2 + replies*1.5"""
    result = calculate_engagement_score(likes=100, retweets=50, replies=30)
    assert result == 245.0, f"Expected 245.0, got {result}"


def test_engagement_formula_zeros():
    """TWIT-03: all-zero inputs produce 0.0"""
    result = calculate_engagement_score(likes=0, retweets=0, replies=0)
    assert result == 0.0


def test_engagement_formula_retweet_weight():
    """TWIT-03: retweets carry weight 2 (double likes)"""
    result = calculate_engagement_score(likes=0, retweets=1, replies=0)
    assert result == 2.0


def test_engagement_formula_reply_weight():
    """TWIT-03: replies carry weight 1.5"""
    result = calculate_engagement_score(likes=0, retweets=0, replies=2)
    assert result == 3.0


# ---------------------------------------------------------------------------
# TWIT-02: Composite score — engagement 40% + authority 30% + relevance 30%
# ---------------------------------------------------------------------------

def test_scoring_formula():
    """TWIT-02: composite = engagement*0.4 + authority*0.3 + relevance*0.3"""
    result = calculate_composite_score(
        engagement_norm=0.8, authority_norm=0.6, relevance_norm=0.9
    )
    expected = 0.8 * 0.4 + 0.6 * 0.3 + 0.9 * 0.3
    assert abs(result - expected) < 1e-9, f"Expected {expected}, got {result}"


def test_scoring_formula_equal_weights_sum():
    """TWIT-02: 40% + 30% + 30% = 100% — perfect normalized scores produce 1.0"""
    result = calculate_composite_score(
        engagement_norm=1.0, authority_norm=1.0, relevance_norm=1.0
    )
    assert abs(result - 1.0) < 1e-9


# ---------------------------------------------------------------------------
# TWIT-05: Recency decay — full <1h, linear 100%->50% from 1h->4h, 0 at >=6h
# ---------------------------------------------------------------------------

def test_recency_decay_under_1h():
    """TWIT-05: full score returned for age < 1h"""
    result = apply_recency_decay(score=100.0, age_hours=0.5)
    assert result == 100.0


def test_recency_decay_exactly_1h():
    """TWIT-05: exactly 1h still returns full score"""
    result = apply_recency_decay(score=100.0, age_hours=1.0)
    assert result == 100.0


def test_recency_decay_at_2_5h():
    """TWIT-05: linear interpolation between 1h (100%) and 4h (50%)"""
    result = apply_recency_decay(score=100.0, age_hours=2.5)
    # 1.0 - 0.5 * (2.5 - 1.0) / 3.0 = 1.0 - 0.5 * 0.5 = 0.75
    assert abs(result - 75.0) < 1e-9, f"Expected 75.0, got {result}"


def test_recency_decay_at_4h():
    """TWIT-05: 50% score returned at exactly 4h"""
    result = apply_recency_decay(score=100.0, age_hours=4.0)
    assert abs(result - 50.0) < 1e-9, f"Expected 50.0, got {result}"


def test_recency_decay_at_6h():
    """TWIT-05: 0 score returned at exactly 6h (expired)"""
    result = apply_recency_decay(score=100.0, age_hours=6.0)
    assert result == 0.0


def test_recency_decay_past_6h():
    """TWIT-05: 0 score returned for age well past 6h"""
    result = apply_recency_decay(score=100.0, age_hours=10.0)
    assert result == 0.0


# ---------------------------------------------------------------------------
# TWIT-04: Engagement gate — watchlist 50+ likes AND 5000+ views;
#          non-watchlist 500+ likes AND 40000+ views
# ---------------------------------------------------------------------------

def test_engagement_gate_watchlist_passes():
    """TWIT-04: watchlist account passes with 50+ likes AND 5000+ views"""
    assert passes_engagement_gate(likes=50, views=5000, is_watchlist=True) is True


def test_engagement_gate_watchlist_fails_likes():
    """TWIT-04: watchlist fails with 49 likes (below 50)"""
    assert passes_engagement_gate(likes=49, views=5000, is_watchlist=True) is False


def test_engagement_gate_watchlist_fails_views():
    """TWIT-04: watchlist fails with 4999 views (below 5000)"""
    assert passes_engagement_gate(likes=50, views=4999, is_watchlist=True) is False


def test_engagement_gate_non_watchlist_passes():
    """TWIT-04: non-watchlist passes with 500+ likes AND 40000+ views"""
    assert passes_engagement_gate(likes=500, views=40000, is_watchlist=False) is True


def test_engagement_gate_non_watchlist_fails_likes():
    """TWIT-04: non-watchlist fails with 499 likes"""
    assert passes_engagement_gate(likes=499, views=40000, is_watchlist=False) is False


def test_engagement_gate_non_watchlist_fails_views():
    """TWIT-04: non-watchlist fails with 39999 views"""
    assert passes_engagement_gate(likes=500, views=39999, is_watchlist=False) is False


def test_engagement_gate_none_views():
    """TWIT-04: None impression_count treated as 0 — fails view gate"""
    assert passes_engagement_gate(likes=500, views=None, is_watchlist=False) is False
    assert passes_engagement_gate(likes=50, views=None, is_watchlist=True) is False


# ---------------------------------------------------------------------------
# TWIT-06: Top-N selection — top 3-5 posts by composite score descending
# ---------------------------------------------------------------------------

def test_top_n_selection():
    """TWIT-06: top 3-5 posts selected by composite_score descending"""
    posts = [
        {"id": "1", "composite_score": 0.9},
        {"id": "2", "composite_score": 0.5},
        {"id": "3", "composite_score": 0.8},
        {"id": "4", "composite_score": 0.3},
        {"id": "5", "composite_score": 0.7},
        {"id": "6", "composite_score": 0.6},
    ]
    result = select_top_posts(posts, max_count=5)
    # Should return top 5 in descending order, filtered to max_count
    assert len(result) <= 5
    assert result[0]["id"] == "1"  # 0.9 is highest
    assert result[1]["id"] == "3"  # 0.8 is second


def test_top_n_filters_zero_score():
    """TWIT-06: posts with composite_score <= 0 (expired via recency) are excluded"""
    posts = [
        {"id": "1", "composite_score": 0.7},
        {"id": "2", "composite_score": 0.0},   # expired
        {"id": "3", "composite_score": -0.1},  # expired
        {"id": "4", "composite_score": 0.5},
    ]
    result = select_top_posts(posts, max_count=5)
    ids = [p["id"] for p in result]
    assert "2" not in ids
    assert "3" not in ids
    assert "1" in ids


def test_top_n_minimum_3():
    """TWIT-06: returns at least 3 posts if 3+ are available"""
    posts = [{"id": str(i), "composite_score": float(i) * 0.1} for i in range(1, 6)]
    result = select_top_posts(posts, max_count=5)
    assert len(result) >= 3


# ---------------------------------------------------------------------------
# TWIT-01: TwitterAgent is async callable
# ---------------------------------------------------------------------------

def test_scheduler_wiring():
    """TWIT-01: TwitterAgent.run() is an async coroutine function"""
    agent = TwitterAgent.__new__(TwitterAgent)
    assert inspect.iscoroutinefunction(agent.run), (
        "TwitterAgent.run must be an async def"
    )


# ---------------------------------------------------------------------------
# TWIT-11, TWIT-12: Quota counter — increment, hard-stop, month reset
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_quota_counter_increments():
    """TWIT-11: tweet count incremented by number of tweets read from API"""
    agent = TwitterAgent.__new__(TwitterAgent)
    mock_session = AsyncMock()

    # Config row showing current count is 100
    mock_config_row = MagicMock()
    mock_config_row.value = "100"
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_config_row

    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()

    await agent._increment_quota(mock_session, tweet_count=25)

    # Should have called execute (to update) and commit
    assert mock_session.execute.called
    assert mock_session.commit.called


@pytest.mark.asyncio
async def test_quota_hard_stop():
    """TWIT-12: agent returns early when quota >= (10000 - safety_margin)"""
    agent = TwitterAgent.__new__(TwitterAgent)
    mock_session = AsyncMock()

    # Simulate: count = 8600, safety_margin = 1500 → 8600 >= 8500 → hard stop
    count_row = MagicMock()
    count_row.value = "8600"
    margin_row = MagicMock()
    margin_row.value = "1500"
    reset_row = MagicMock()
    reset_row.value = datetime.now(timezone.utc).strftime("%Y-%m")

    def side_effect_execute(stmt, *args, **kwargs):
        mock_result = MagicMock()
        # Return different values based on call order
        mock_result.scalar_one_or_none.return_value = count_row
        return mock_result

    mock_session.execute = AsyncMock(return_value=MagicMock(
        scalar_one_or_none=MagicMock(side_effect=[count_row, reset_row, margin_row])
    ))
    mock_session.commit = AsyncMock()

    can_proceed, count = await agent._check_quota(mock_session)

    # With 8600 tweets read and 1500 safety margin: 8600 >= 8500 → cannot proceed
    assert can_proceed is False


@pytest.mark.asyncio
async def test_quota_month_reset():
    """TWIT-11: counter resets on first run of new calendar month"""
    agent = TwitterAgent.__new__(TwitterAgent)
    mock_session = AsyncMock()

    # Simulate: reset_date is previous month
    prev_month = (datetime.now(timezone.utc) - timedelta(days=32)).strftime("%Y-%m")
    reset_row = MagicMock()
    reset_row.value = prev_month
    count_row = MagicMock()
    count_row.value = "5000"  # old month's count
    margin_row = MagicMock()
    margin_row.value = "1500"

    # _check_quota calls _get_config 3 times (count, reset, margin),
    # then on reset detection calls _set_config twice (count→0, reset_date→now)
    # each _set_config calls _get_config first — provide extra return values.
    # After the initial 3 reads, return existing rows for subsequent _set_config reads.
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.side_effect = [
        count_row,   # initial count read
        reset_row,   # initial reset_date read
        margin_row,  # initial margin read
        count_row,   # _set_config count check (exists → update in place)
        reset_row,   # _set_config reset_date check (exists → update in place)
    ]
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()
    # session.add is called for new Config rows — mock it
    mock_session.add = MagicMock()

    # After reset, count should be treated as 0 → can proceed
    can_proceed, count = await agent._check_quota(mock_session)
    assert can_proceed is True


@pytest.mark.asyncio
async def test_quota_readable():
    """TWIT-13: config table quota value can be read"""
    agent = TwitterAgent.__new__(TwitterAgent)
    mock_session = AsyncMock()

    count_row = MagicMock()
    count_row.value = "350"
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = count_row
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()

    # _check_quota should return the current count
    can_proceed, count = await agent._check_quota(mock_session)
    # Count should reflect what's in the config (or 0 after reset)
    assert isinstance(count, int)


# ---------------------------------------------------------------------------
# TWIT-07, TWIT-08: Draft produces reply + RT with 2-3 alternatives each
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_draft_produces_reply_and_rt():
    """TWIT-07: each qualifying post yields reply draft AND retweet-with-comment draft"""
    # This test verifies the structure of the draft output
    # Full implementation is in Plan 03 — stub checks the interface contract
    agent = TwitterAgent.__new__(TwitterAgent)
    assert hasattr(agent, "run"), "TwitterAgent must have a run() method"
    # TWIT-07 is validated end-to-end in Plan 03 drafting tests


@pytest.mark.asyncio
async def test_draft_has_2_to_3_alternatives():
    """TWIT-08: each draft type produces 2-3 alternatives"""
    # TWIT-08 is validated in Plan 03 drafting implementation
    # This stub ensures the test is collected and will be fleshed out
    pass


# ---------------------------------------------------------------------------
# TWIT-09, TWIT-10: Compliance checker per alternative
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_compliance_called_per_alternative():
    """TWIT-09, TWIT-10: compliance checker invoked once per alternative, separately from drafting"""
    # TWIT-10 compliance checker is implemented in Plan 03
    # This stub ensures test collection
    pass


@pytest.mark.asyncio
async def test_compliance_failure_drops_alternative():
    """TWIT-10: failing alternative is removed; passing alternatives are kept"""
    # TWIT-10 is validated in Plan 03
    pass


@pytest.mark.asyncio
async def test_compliance_all_fail_skips_post():
    """TWIT-10: if all alternatives fail compliance, post is not queued"""
    # TWIT-10 is validated in Plan 03
    pass


# ---------------------------------------------------------------------------
# TWIT-14: Every DraftItem.rationale is a non-empty string
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rationale_populated():
    """TWIT-14: every DraftItem.rationale is non-empty string explaining why post matters"""
    # TWIT-14 validated in Plan 03 when DraftItem records are created
    pass
