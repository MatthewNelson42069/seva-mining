"""Tests for agents.content.gold_history sub-agent (quick-260421-eoe).

gold_history is the second bespoke sub-agent — does NOT call
content_agent.fetch_stories() (has its own curated historical-story source
guarded by the `gold_history_used_topics` Config key). DOES call
content_agent.review() inline before writing.
"""
import json
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

from agents.content import gold_history  # noqa: E402


def test_module_surface():
    assert gold_history.CONTENT_TYPE == "gold_history"
    assert gold_history.AGENT_NAME == "sub_gold_history"
    assert callable(gold_history.run_draft_cycle)
    assert callable(gold_history._pick_story)
    assert callable(gold_history._verify_facts)
    assert callable(gold_history._draft_gold_history)
    assert callable(gold_history._get_used_topics)
    assert callable(gold_history._add_used_topic)


@pytest.mark.asyncio
async def test_pick_story_returns_parsed_json():
    client = AsyncMock()
    response = MagicMock()
    response.content = [MagicMock(
        text='{"story_title":"Bre-X","story_slug":"bre-x-fraud","key_claims":["c1","c2"]}'
    )]
    client.messages.create = AsyncMock(return_value=response)

    story = await gold_history._pick_story([], client=client)
    assert story is not None
    assert story["story_slug"] == "bre-x-fraud"
    assert story["key_claims"] == ["c1", "c2"]


@pytest.mark.asyncio
async def test_pick_story_returns_none_on_parse_failure():
    client = AsyncMock()
    response = MagicMock()
    response.content = [MagicMock(text="not valid json")]
    client.messages.create = AsyncMock(return_value=response)

    story = await gold_history._pick_story([], client=client)
    assert story is None


@pytest.mark.asyncio
async def test_pick_story_sends_used_list_to_claude():
    """Claude is told which slugs have already been used so fresh picks are enforced."""
    client = AsyncMock()
    response = MagicMock()
    response.content = [MagicMock(
        text='{"story_title":"Klondike","story_slug":"klondike","key_claims":["a"]}'
    )]
    client.messages.create = AsyncMock(return_value=response)

    await gold_history._pick_story(["bre-x-fraud", "giustra-goldcorp"], client=client)
    _, kwargs = client.messages.create.call_args
    user_msg = kwargs["messages"][0]["content"]
    assert "bre-x-fraud" in user_msg
    assert "giustra-goldcorp" in user_msg


@pytest.mark.asyncio
async def test_get_used_topics_returns_empty_when_missing():
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=result)

    topics = await gold_history._get_used_topics(session)
    assert topics == []


@pytest.mark.asyncio
async def test_get_used_topics_parses_json_value():
    session = AsyncMock()
    row = MagicMock()
    row.value = json.dumps(["slug1", "slug2"])
    result = MagicMock()
    result.scalar_one_or_none.return_value = row
    session.execute = AsyncMock(return_value=result)

    topics = await gold_history._get_used_topics(session)
    assert topics == ["slug1", "slug2"]


@pytest.mark.asyncio
async def test_get_used_topics_handles_malformed_json():
    session = AsyncMock()
    row = MagicMock()
    row.value = "not valid json"
    result = MagicMock()
    result.scalar_one_or_none.return_value = row
    session.execute = AsyncMock(return_value=result)

    topics = await gold_history._get_used_topics(session)
    assert topics == []
