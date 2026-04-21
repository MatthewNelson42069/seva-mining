"""Tests for agents.content.breaking_news sub-agent (quick-260421-eoe)."""
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

from agents import content_agent  # noqa: E402
from agents.content import breaking_news  # noqa: E402


def test_module_surface():
    assert breaking_news.CONTENT_TYPE == "breaking_news"
    assert breaking_news.AGENT_NAME == "sub_breaking_news"
    assert callable(breaking_news.run_draft_cycle)
    assert callable(breaking_news._draft)


@pytest.mark.asyncio
async def test_draft_returns_draft_content_shape():
    """_draft parses valid JSON and returns draft_content + rationale + key_data_points."""
    client = AsyncMock()
    response = MagicMock()
    response.content = [MagicMock(text='{"format":"breaking_news","rationale":"r","key_data_points":["a","b"],"draft_content":{"format":"breaking_news","tweet":"GOLD: $2500","infographic_brief":null}}')]
    client.messages.create = AsyncMock(return_value=response)

    story = {"title": "T", "link": "http://x", "source_name": "kitco"}
    deep_research = {"article_text": "body", "corroborating_sources": []}
    draft = await breaking_news._draft(story, deep_research, None, client=client)

    assert draft is not None
    assert draft["format"] == "breaking_news"
    assert draft["tweet"] == "GOLD: $2500"
    assert draft["_rationale"] == "r"
    assert draft["_key_data_points"] == ["a", "b"]


@pytest.mark.asyncio
async def test_draft_returns_none_on_json_parse_failure():
    """Invalid JSON from Claude returns None, doesn't raise."""
    client = AsyncMock()
    response = MagicMock()
    response.content = [MagicMock(text="not json at all!!!")]
    client.messages.create = AsyncMock(return_value=response)

    story = {"title": "T", "link": "http://x", "source_name": "kitco"}
    draft = await breaking_news._draft(
        story, {"article_text": "body", "corroborating_sources": []}, None, client=client,
    )
    assert draft is None


@pytest.mark.asyncio
async def test_run_draft_cycle_no_candidates_exits_cleanly():
    """When no stories match predicted_format='breaking_news', cycle no-ops."""
    # fetch_stories returns only stories with unrelated formats → breaking_news filter rejects all
    stories = [{"title": "A", "link": "http://a", "source_name": "x",
                "predicted_format": "thread", "score": 5.0}]

    session = AsyncMock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("agents.content.AsyncSessionLocal", return_value=ctx), \
         patch("agents.content.fetch_market_snapshot", new=AsyncMock(return_value=None)), \
         patch.object(content_agent, "fetch_stories", new=AsyncMock(return_value=stories)):
        await breaking_news.run_draft_cycle()

    # agent_run was created and committed (twice: initial + final)
    assert session.commit.await_count >= 2
