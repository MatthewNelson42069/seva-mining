"""Tests for agents.content.gold_media sub-agent (quick-260421-eoe, renamed quick-260422-mfg).

gold_media is the bespoke X API-backed sub-agent — does NOT call
content_agent.fetch_stories(), does call content_agent.review() inline,
preserves the twitter_monthly_tweet_count / twitter_monthly_quota_limit
pre-check.
"""
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

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

from agents.content import gold_media  # noqa: E402


def test_module_surface():
    assert gold_media.CONTENT_TYPE == "gold_media"
    assert gold_media.AGENT_NAME == "sub_gold_media"
    assert callable(gold_media.run_draft_cycle)
    # X API quota pre-check helpers present
    assert callable(gold_media._search_gold_media_clips)
    assert callable(gold_media._draft_gold_media_caption)
    assert isinstance(gold_media.GOLD_MEDIA_ACCOUNTS, list)
    assert "Kitco" in gold_media.GOLD_MEDIA_ACCOUNTS


@pytest.mark.asyncio
async def test_search_gold_media_clips_respects_quota_cap():
    """When remaining X API quota < 500, _search_gold_media_clips returns [] without API call."""
    # _get_config returns current_count close to quota_limit
    session = AsyncMock()

    async def mock_get_config(sess, key, default):
        return {
            "twitter_monthly_tweet_count": "9700",
            "twitter_monthly_quota_limit": "10000",
        }.get(key, default)

    tweepy_client = AsyncMock()
    with patch.object(gold_media, "_get_config", side_effect=mock_get_config):
        result = await gold_media._search_gold_media_clips(session, tweepy_client)
    assert result == []
    tweepy_client.search_recent_tweets.assert_not_called()


@pytest.mark.asyncio
async def test_draft_gold_media_caption_returns_expected_shape():
    """_draft_gold_media_caption parses valid JSON and returns gold_media draft structure."""
    client = AsyncMock()
    response = MagicMock()
    response.content = [MagicMock(text='{"twitter_caption":"cap","instagram_caption":"ig cap"}')]
    client.messages.create = AsyncMock(return_value=response)

    draft = await gold_media._draft_gold_media_caption(
        tweet_text="Gold hit $2500 today.",
        author_username="Kitco",
        author_name="Kitco News",
        tweet_url="https://twitter.com/Kitco/status/1",
        market_snapshot=None,
        client=client,
    )
    assert draft is not None
    assert draft["format"] == "gold_media"
    assert draft["source_account"] == "Kitco"
    assert draft["twitter_caption"] == "cap"


@pytest.mark.asyncio
async def test_draft_gold_media_caption_returns_none_on_parse_failure():
    client = AsyncMock()
    response = MagicMock()
    response.content = [MagicMock(text="not valid json")]
    client.messages.create = AsyncMock(return_value=response)

    draft = await gold_media._draft_gold_media_caption(
        tweet_text="x", author_username="a", author_name="A",
        tweet_url="https://x", market_snapshot=None, client=client,
    )
    assert draft is None


def test_gold_media_accounts_reordered_analyst_first():
    """GOLD_MEDIA_ACCOUNTS is reordered post-vxg to favor analyst/economist media handles.

    Top 3 must be Kitco / CNBC / Bloomberg (analyst-interview-heavy).
    Corporate/sector accounts (BarrickGold, WorldGoldCouncil, Mining, Newaborngold)
    must be dropped — they posted PR-style clips, not analyst commentary.
    """
    assert gold_media.GOLD_MEDIA_ACCOUNTS[:3] == ["Kitco", "CNBC", "Bloomberg"]
    assert "BarrickGold" not in gold_media.GOLD_MEDIA_ACCOUNTS
    assert "WorldGoldCouncil" not in gold_media.GOLD_MEDIA_ACCOUNTS
    assert "Mining" not in gold_media.GOLD_MEDIA_ACCOUNTS
    assert "Newaborngold" not in gold_media.GOLD_MEDIA_ACCOUNTS
    # New additions — analyst-heavy handles.
    assert "BloombergTV" in gold_media.GOLD_MEDIA_ACCOUNTS
    assert "ReutersBiz" in gold_media.GOLD_MEDIA_ACCOUNTS


@pytest.mark.asyncio
async def test_draft_gold_media_caption_returns_none_on_reject(caplog):
    """_draft_gold_media_caption returns None when Claude responds with {"reject": true, ...}."""
    client = AsyncMock()
    response = MagicMock()
    response.content = [MagicMock(text='{"reject": true, "rationale": "anonymous voice-over, no named speaker"}')]
    client.messages.create = AsyncMock(return_value=response)

    with caplog.at_level("INFO"):
        draft = await gold_media._draft_gold_media_caption(
            tweet_text="Gold prices rose today.",
            author_username="Kitco",
            author_name="Kitco News",
            tweet_url="https://twitter.com/Kitco/status/1",
            market_snapshot=None,
            client=client,
        )
    assert draft is None
    assert "rejected" in caplog.text
    assert "anonymous" in caplog.text


@pytest.mark.asyncio
async def test_draft_rejects_bearish_analyst_clip(caplog):
    """_draft_gold_media_caption returns None when Sonnet rejects for bearish stance (criterion #4)."""
    client = AsyncMock()
    response = MagicMock()
    response.content = [MagicMock(text='{"reject": true, "rationale": "Speaker is predicting near-term gold price decline — violates Bullish or neutral stance criterion"}')]
    client.messages.create = AsyncMock(return_value=response)

    with caplog.at_level("INFO"):
        draft = await gold_media._draft_gold_media_caption(
            tweet_text="Analyst: expect gold to pull back to $2100 as dollar strengthens",
            author_username="Kitco",
            author_name="Kitco News",
            tweet_url="https://twitter.com/Kitco/status/99",
            market_snapshot=None,
            client=client,
        )
    # caplog assertion verifies the reject-log code path fires;
    # rationale wording is mocked, not tested against real model output.
    # (Real Sonnet rationales will vary — the phrase "Bullish or neutral"
    # appears here only because the mocked response string is authored
    # to contain it. This test asserts the logging wiring, not the
    # natural-language content of production rationales.)
    assert draft is None
    assert "rejected" in caplog.text


@pytest.mark.asyncio
async def test_draft_accepts_bullish_analyst_clip():
    """_draft_gold_media_caption returns a draft dict for bullish analyst clips (criterion #4 sanity)."""
    client = AsyncMock()
    response = MagicMock()
    response.content = [MagicMock(text='{"twitter_caption":"Central banks keep buying at these levels — structural tailwind.","instagram_caption":"Central bank gold buying remains strong..."}')]
    client.messages.create = AsyncMock(return_value=response)

    draft = await gold_media._draft_gold_media_caption(
        tweet_text="Central banks added record gold reserves in Q1 — structural demand intact.",
        author_username="Bloomberg",
        author_name="Bloomberg News",
        tweet_url="https://twitter.com/Bloomberg/status/100",
        market_snapshot=None,
        client=client,
    )
    assert draft is not None
    assert draft["format"] == "gold_media"
    assert draft["twitter_caption"] != ""
