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
        await breaking_news.run_draft_cycle()

    # agent_run was created and committed (twice: initial + final)
    assert session.commit.await_count >= 2


# ---------------------------------------------------------------------------
# quick-260424-j5i — min_score constant + selection kwargs propagation
# ---------------------------------------------------------------------------


def test_breaking_news_min_score_constant():
    """BREAKING_NEWS_MIN_SCORE is a module-level tunable at 6.0
    (j5i shipped 6.5; m49 dropped to 6.0 after live telemetry showed 69%
    floor rate exceeding j5i's own 70% drop-trigger).
    """
    assert breaking_news.BREAKING_NEWS_MIN_SCORE == 6.0


@pytest.mark.asyncio
async def test_breaking_news_passes_selection_kwargs():
    """j5i D1+D2: run_draft_cycle passes max_count=3, sort_by='score',
    min_score=BREAKING_NEWS_MIN_SCORE (=6.0 post-m49) through to
    run_text_story_cycle. Mirrors test_infographics.py:120-145's
    call_kwargs idiom.
    """
    call_kwargs: dict = {}

    async def fake_cycle(**kwargs):
        call_kwargs.update(kwargs)
        return 0

    with patch(
        "agents.content.breaking_news.run_text_story_cycle",
        new=AsyncMock(side_effect=fake_cycle),
    ):
        await breaking_news.run_draft_cycle()

    assert call_kwargs.get("agent_name") == "sub_breaking_news"
    assert call_kwargs.get("content_type") == "breaking_news"
    assert callable(call_kwargs.get("draft_fn"))
    assert call_kwargs.get("max_count") == 3, (
        f"Expected max_count=3, got {call_kwargs.get('max_count')}"
    )
    assert call_kwargs.get("sort_by") == "score", (
        f"Expected sort_by='score', got {call_kwargs.get('sort_by')}"
    )
    assert call_kwargs.get("min_score") == 6.0, (
        f"Expected min_score=6.0, got {call_kwargs.get('min_score')}"
    )
