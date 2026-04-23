"""Tests for agents.content.quotes sub-agent (quick-260421-eoe)."""
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
from agents.content import quotes  # noqa: E402


def test_module_surface():
    assert quotes.CONTENT_TYPE == "quote"
    assert quotes.AGENT_NAME == "sub_quotes"
    assert callable(quotes.run_draft_cycle)
    assert callable(quotes._draft)


@pytest.mark.asyncio
async def test_draft_returns_draft_content_shape():
    client = AsyncMock()
    response = MagicMock()
    response.content = [MagicMock(text='{"format":"quote","rationale":"r","key_data_points":["a"],"draft_content":{"format":"quote","quote_text":"Gold is money.","speaker":"JP Morgan","twitter_post":"q","instagram_post":"q","suggested_headline":"Gold","data_facts":["f"],"image_prompt":"x"}}')]
    client.messages.create = AsyncMock(return_value=response)

    story = {"title": "T", "link": "http://x", "source_name": "kitco"}
    draft = await quotes._draft(
        story, {"article_text": "body", "corroborating_sources": []}, None, client=client,
    )

    assert draft is not None
    assert draft["format"] == "quote"
    assert draft["speaker"] == "JP Morgan"
    assert draft["_rationale"] == "r"


@pytest.mark.asyncio
async def test_draft_returns_none_on_json_parse_failure():
    client = AsyncMock()
    response = MagicMock()
    response.content = [MagicMock(text="not valid json")]
    client.messages.create = AsyncMock(return_value=response)

    draft = await quotes._draft(
        {"title": "T", "link": "http://x", "source_name": "kitco"},
        {"article_text": "body", "corroborating_sources": []}, None, client=client,
    )
    assert draft is None


@pytest.mark.asyncio
async def test_run_draft_cycle_completes_with_stories():
    """run_draft_cycle runs to completion regardless of predicted_format label.

    The predicted_format filter was removed (debug 260422-zid): all stories are
    candidates now. The source_whitelist filter will drop "x" (not a reputable
    source), so the drafter is not called. The cycle still completes cleanly
    (agent_run committed twice: initial + final).
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
        await quotes.run_draft_cycle()

    assert session.commit.await_count >= 2


def test_reputable_sources_set_populated():
    """REPUTABLE_SOURCES covers tier-1 financial + gold-specialist + institutional aliases."""
    assert isinstance(quotes.REPUTABLE_SOURCES, frozenset)
    assert len(quotes.REPUTABLE_SOURCES) >= 10
    # Spot-check representative entries from each tier.
    assert "reuters" in quotes.REPUTABLE_SOURCES
    assert "bloomberg" in quotes.REPUTABLE_SOURCES
    assert "wgc" in quotes.REPUTABLE_SOURCES
    assert "kitco" in quotes.REPUTABLE_SOURCES


@pytest.mark.asyncio
async def test_draft_returns_none_on_reject(caplog):
    """_draft returns None when Claude responds with {"reject": true, ...} and logs the rationale."""
    client = AsyncMock()
    response = MagicMock()
    response.content = [MagicMock(text='{"reject": true, "rationale": "speaker is anonymous"}')]
    client.messages.create = AsyncMock(return_value=response)

    with caplog.at_level("INFO"):
        draft = await quotes._draft(
            {"title": "T", "link": "http://x", "source_name": "kitco"},
            {"article_text": "body", "corroborating_sources": []}, None, client=client,
        )
    assert draft is None
    assert "quality gate" in caplog.text
    assert "speaker is anonymous" in caplog.text


@pytest.mark.asyncio
async def test_run_draft_cycle_passes_filters():
    """run_draft_cycle passes max_count=2 and source_whitelist=REPUTABLE_SOURCES to the shared cycle."""
    with patch("agents.content.quotes.run_text_story_cycle", new=AsyncMock()) as mock_cycle:
        await quotes.run_draft_cycle()
    mock_cycle.assert_awaited_once()
    kwargs = mock_cycle.await_args.kwargs
    assert kwargs["agent_name"] == "sub_quotes"
    assert kwargs["content_type"] == "quote"
    assert kwargs["max_count"] == 1
    assert kwargs["source_whitelist"] is quotes.REPUTABLE_SOURCES
    assert callable(kwargs["draft_fn"])


@pytest.mark.asyncio
async def test_run_draft_cycle_passes_dedup_scope():
    """Covers d30: run_draft_cycle passes dedup_scope="same_type" to
    run_text_story_cycle so quotes runs independently — mirrors the
    independence model applied to sub_infographics (of3).
    Also re-asserts the vxg (max_count=1) + mos (source_whitelist) kwargs
    as a belt-and-suspenders guard against accidental regressions.
    """
    call_kwargs: dict = {}

    async def fake_cycle(**kwargs):
        call_kwargs.update(kwargs)

    with patch("agents.content.quotes.run_text_story_cycle",
               new=AsyncMock(side_effect=fake_cycle)):
        await quotes.run_draft_cycle()

    assert call_kwargs.get("agent_name") == "sub_quotes"
    assert call_kwargs.get("content_type") == "quote"
    assert callable(call_kwargs.get("draft_fn"))
    assert call_kwargs.get("max_count") == 1, (
        f"Expected max_count=1 (vxg), got {call_kwargs.get('max_count')}"
    )
    assert call_kwargs.get("source_whitelist") is quotes.REPUTABLE_SOURCES, (
        "Expected source_whitelist is REPUTABLE_SOURCES (mos)"
    )
    assert call_kwargs.get("dedup_scope") == "same_type", (
        f"Expected dedup_scope='same_type' (d30), got {call_kwargs.get('dedup_scope')}"
    )
