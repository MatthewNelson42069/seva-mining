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
async def test_run_draft_cycle_completes_with_stories():
    """run_draft_cycle runs to completion regardless of predicted_format label.

    The predicted_format filter was removed (debug 260422-zid): all stories are
    candidates now. The cycle still completes cleanly (agent_run committed twice:
    initial + final). The story proceeds to the gold gate — which is NOT mocked
    here so it may error internally; the story-level try/except handles that
    gracefully and the cycle still completes.
    """
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


# ---------------------------------------------------------------------------
# quick-260424-j5i — min_score constant + selection kwargs propagation
# ---------------------------------------------------------------------------


def test_threads_min_score_constant():
    """j5i D2: THREADS_MIN_SCORE is a module-level tunable at 6.5."""
    assert threads.THREADS_MIN_SCORE == 6.5


@pytest.mark.asyncio
async def test_threads_passes_selection_kwargs():
    """j5i D1+D2: run_draft_cycle passes max_count=2, sort_by='score',
    min_score=THREADS_MIN_SCORE (=6.5) through to run_text_story_cycle.
    max_count=2 is preserved from the zid cap; sort_by flips from the default
    published_at to score; min_score is new.
    """
    call_kwargs: dict = {}

    async def fake_cycle(**kwargs):
        call_kwargs.update(kwargs)
        return 0

    with patch(
        "agents.content.threads.run_text_story_cycle",
        new=AsyncMock(side_effect=fake_cycle),
    ):
        await threads.run_draft_cycle()

    assert call_kwargs.get("agent_name") == "sub_threads"
    assert call_kwargs.get("content_type") == "thread"
    assert callable(call_kwargs.get("draft_fn"))
    assert call_kwargs.get("max_count") == 2, (
        f"Expected max_count=2, got {call_kwargs.get('max_count')}"
    )
    assert call_kwargs.get("sort_by") == "score", (
        f"Expected sort_by='score', got {call_kwargs.get('sort_by')}"
    )
    assert call_kwargs.get("min_score") == 6.5, (
        f"Expected min_score=6.5, got {call_kwargs.get('min_score')}"
    )
