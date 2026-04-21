"""Tests for agents.content.threads sub-agent (quick-260421-eoe)."""
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
from agents.content import threads  # noqa: E402


def test_module_surface():
    assert threads.CONTENT_TYPE == "thread"
    assert threads.AGENT_NAME == "sub_threads"
    assert callable(threads.run_draft_cycle)
    assert callable(threads._draft)


@pytest.mark.asyncio
async def test_draft_returns_draft_content_shape():
    client = AsyncMock()
    response = MagicMock()
    response.content = [MagicMock(text='{"format":"thread","rationale":"r","key_data_points":["a"],"draft_content":{"format":"thread","tweets":["t1","t2","t3"],"long_form_post":"lf"}}')]
    client.messages.create = AsyncMock(return_value=response)

    story = {"title": "T", "link": "http://x", "source_name": "kitco"}
    draft = await threads._draft(
        story, {"article_text": "body", "corroborating_sources": []}, None, client=client,
    )

    assert draft is not None
    assert draft["format"] == "thread"
    assert draft["tweets"] == ["t1", "t2", "t3"]
    assert draft["_rationale"] == "r"


@pytest.mark.asyncio
async def test_draft_returns_none_on_json_parse_failure():
    client = AsyncMock()
    response = MagicMock()
    response.content = [MagicMock(text="not valid json")]
    client.messages.create = AsyncMock(return_value=response)

    draft = await threads._draft(
        {"title": "T", "link": "http://x", "source_name": "kitco"},
        {"article_text": "body", "corroborating_sources": []}, None, client=client,
    )
    assert draft is None


@pytest.mark.asyncio
async def test_run_draft_cycle_no_candidates_exits_cleanly():
    stories = [{"title": "A", "link": "http://a", "source_name": "x",
                "predicted_format": "breaking_news", "score": 5.0}]

    session = AsyncMock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("agents.content.AsyncSessionLocal", return_value=ctx), \
         patch("agents.content.fetch_market_snapshot", new=AsyncMock(return_value=None)), \
         patch.object(content_agent, "fetch_stories", new=AsyncMock(return_value=stories)):
        await threads.run_draft_cycle()

    assert session.commit.await_count >= 2
