"""Tests for agents.content.infographics sub-agent (quick-260421-eoe)."""
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
from agents.content import infographics  # noqa: E402


def test_module_surface():
    assert infographics.CONTENT_TYPE == "infographic"
    assert infographics.AGENT_NAME == "sub_infographics"
    assert callable(infographics.run_draft_cycle)
    assert callable(infographics._draft)


@pytest.mark.asyncio
async def test_draft_returns_draft_content_shape():
    client = AsyncMock()
    response = MagicMock()
    response.content = [MagicMock(text='{"format":"infographic","rationale":"r","key_data_points":["a"],"draft_content":{"format":"infographic","suggested_headline":"Gold reserves 2026","data_facts":["fact1","fact2","fact3"],"image_prompt":"minimal gold chart","twitter_caption":"cap","charts":[{"title":"Gold reserves","data":[1,2,3]}]}}')]
    client.messages.create = AsyncMock(return_value=response)

    story = {"title": "T", "link": "http://x", "source_name": "kitco"}
    draft = await infographics._draft(
        story, {"article_text": "body", "corroborating_sources": []}, None, client=client,
    )

    assert draft is not None
    assert draft["format"] == "infographic"
    assert draft["suggested_headline"] == "Gold reserves 2026"
    assert draft["_rationale"] == "r"


@pytest.mark.asyncio
async def test_draft_returns_none_on_json_parse_failure():
    client = AsyncMock()
    response = MagicMock()
    response.content = [MagicMock(text="not valid json")]
    client.messages.create = AsyncMock(return_value=response)

    draft = await infographics._draft(
        {"title": "T", "link": "http://x", "source_name": "kitco"},
        {"article_text": "body", "corroborating_sources": []}, None, client=client,
    )
    assert draft is None


@pytest.mark.asyncio
async def test_run_draft_cycle_completes_with_stories():
    """run_draft_cycle runs to completion regardless of predicted_format label.

    The predicted_format filter was removed (debug 260422-zid): all stories are
    candidates now. The cycle still completes cleanly (agent_run committed twice:
    initial + final). The story proceeds to the gold gate — which is NOT mocked
    here so it may error internally; the story-level try/except handles that
    gracefully and the cycle still completes.
    """
    stories = [{"title": "A", "link": "http://a", "source_name": "x",
                "predicted_format": "thread", "score": 5.0}]

    session = AsyncMock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("agents.content.AsyncSessionLocal", return_value=ctx), \
         patch("agents.content.fetch_market_snapshot", new=AsyncMock(return_value=None)), \
         patch.object(content_agent, "fetch_stories", new=AsyncMock(return_value=stories)):
        await infographics.run_draft_cycle()

    assert session.commit.await_count >= 2
