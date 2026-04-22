"""Tests for agents.content.video_clip sub-agent (quick-260421-eoe).

video_clip is the bespoke X API-backed sub-agent — does NOT call
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

from agents.content import video_clip  # noqa: E402


def test_module_surface():
    assert video_clip.CONTENT_TYPE == "video_clip"
    assert video_clip.AGENT_NAME == "sub_video_clip"
    assert callable(video_clip.run_draft_cycle)
    # X API quota pre-check helpers present
    assert callable(video_clip._search_video_clips)
    assert callable(video_clip._draft_video_caption)
    assert isinstance(video_clip.VIDEO_ACCOUNTS, list)
    assert "Kitco" in video_clip.VIDEO_ACCOUNTS


@pytest.mark.asyncio
async def test_search_video_clips_respects_quota_cap():
    """When remaining X API quota < 500, _search_video_clips returns [] without API call."""
    # _get_config returns current_count close to quota_limit
    session = AsyncMock()

    async def mock_get_config(sess, key, default):
        return {
            "twitter_monthly_tweet_count": "9700",
            "twitter_monthly_quota_limit": "10000",
        }.get(key, default)

    tweepy_client = AsyncMock()
    with patch.object(video_clip, "_get_config", side_effect=mock_get_config):
        result = await video_clip._search_video_clips(session, tweepy_client)
    assert result == []
    tweepy_client.search_recent_tweets.assert_not_called()


@pytest.mark.asyncio
async def test_draft_video_caption_returns_expected_shape():
    """_draft_video_caption parses valid JSON and returns video_clip draft structure."""
    client = AsyncMock()
    response = MagicMock()
    response.content = [MagicMock(text='{"twitter_caption":"cap","instagram_caption":"ig cap"}')]
    client.messages.create = AsyncMock(return_value=response)

    draft = await video_clip._draft_video_caption(
        tweet_text="Gold hit $2500 today.",
        author_username="Kitco",
        author_name="Kitco News",
        tweet_url="https://twitter.com/Kitco/status/1",
        market_snapshot=None,
        client=client,
    )
    assert draft is not None
    assert draft["format"] == "video_clip"
    assert draft["source_account"] == "Kitco"
    assert draft["twitter_caption"] == "cap"


@pytest.mark.asyncio
async def test_draft_video_caption_returns_none_on_parse_failure():
    client = AsyncMock()
    response = MagicMock()
    response.content = [MagicMock(text="not valid json")]
    client.messages.create = AsyncMock(return_value=response)

    draft = await video_clip._draft_video_caption(
        tweet_text="x", author_username="a", author_name="A",
        tweet_url="https://x", market_snapshot=None, client=client,
    )
    assert draft is None


def test_video_accounts_reordered_analyst_first():
    """VIDEO_ACCOUNTS is reordered post-vxg to favor analyst/economist media handles.

    Top 3 must be Kitco / CNBC / Bloomberg (analyst-interview-heavy).
    Corporate/sector accounts (BarrickGold, WorldGoldCouncil, Mining, Newaborngold)
    must be dropped — they posted PR-style clips, not analyst commentary.
    """
    assert video_clip.VIDEO_ACCOUNTS[:3] == ["Kitco", "CNBC", "Bloomberg"]
    assert "BarrickGold" not in video_clip.VIDEO_ACCOUNTS
    assert "WorldGoldCouncil" not in video_clip.VIDEO_ACCOUNTS
    assert "Mining" not in video_clip.VIDEO_ACCOUNTS
    assert "Newaborngold" not in video_clip.VIDEO_ACCOUNTS
    # New additions — analyst-heavy handles.
    assert "BloombergTV" in video_clip.VIDEO_ACCOUNTS
    assert "ReutersBiz" in video_clip.VIDEO_ACCOUNTS


@pytest.mark.asyncio
async def test_draft_video_caption_returns_none_on_reject(caplog):
    """_draft_video_caption returns None when Claude responds with {"reject": true, ...}."""
    client = AsyncMock()
    response = MagicMock()
    response.content = [MagicMock(text='{"reject": true, "rationale": "anonymous voice-over, no named speaker"}')]
    client.messages.create = AsyncMock(return_value=response)

    with caplog.at_level("INFO"):
        draft = await video_clip._draft_video_caption(
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
