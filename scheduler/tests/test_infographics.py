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


# ---------------------------------------------------------------------------
# New tests for quick-260422-of3: kwargs propagation + notes telemetry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_draft_cycle_passes_new_kwargs():
    """Covers D-04 + D-01 + D-02: run_draft_cycle passes max_count=2,
    sort_by='score', dedup_scope='same_type' to run_text_story_cycle.
    """
    call_kwargs: dict = {}

    async def fake_cycle(**kwargs):
        call_kwargs.update(kwargs)

    with patch("agents.content.infographics.run_text_story_cycle",
               new=AsyncMock(side_effect=fake_cycle)):
        await infographics.run_draft_cycle()

    assert call_kwargs.get("agent_name") == "sub_infographics"
    assert call_kwargs.get("content_type") == "infographic"
    assert callable(call_kwargs.get("draft_fn"))
    assert call_kwargs.get("max_count") == 2, (
        f"Expected max_count=2, got {call_kwargs.get('max_count')}"
    )
    assert call_kwargs.get("sort_by") == "score", (
        f"Expected sort_by='score', got {call_kwargs.get('sort_by')}"
    )
    assert call_kwargs.get("dedup_scope") == "same_type", (
        f"Expected dedup_scope='same_type', got {call_kwargs.get('dedup_scope')}"
    )


@pytest.mark.asyncio
async def test_run_draft_cycle_writes_structured_notes():
    """Covers D-04: end-to-end run populates AgentRun.notes with the 5-field
    structured payload {candidates, top_by_score, drafted, compliance_blocked,
    queued} when content_type == 'infographic'.

    3 stories all pass the gate; draft_fn returns a non-None draft for both of
    the 2 top-by-score stories (the 3rd is trimmed by max_count=2). Review
    returns compliance_passed=True for 1 and False for 1 → drafted=2,
    compliance_blocked=1, queued=1.
    """
    import json as _json  # noqa: PLC0415

    stories = [
        {"title": "Top A", "link": "http://a", "source_name": "Reuters",
         "predicted_format": "infographic", "score": 9.0,
         "published_at": "2026-04-21T12:00:00Z", "summary": "a"},
        {"title": "Top B", "link": "http://b", "source_name": "Reuters",
         "predicted_format": "infographic", "score": 8.0,
         "published_at": "2026-04-21T11:00:00Z", "summary": "b"},
        {"title": "Trimmed", "link": "http://c", "source_name": "Reuters",
         "predicted_format": "infographic", "score": 3.0,
         "published_at": "2026-04-21T13:00:00Z", "summary": "c"},
    ]

    captured_agent_runs: list = []
    session = AsyncMock()

    def _record_add(obj):
        # AgentRun is the first object added; ContentBundle/DraftItem come later.
        # Record them all so we can pluck the AgentRun at the end.
        captured_agent_runs.append(obj)

    session.add = MagicMock(side_effect=_record_add)

    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=False)

    # Alternate compliance_passed: first story True, second False
    review_results = iter([
        {"compliance_passed": True, "rationale": "ok"},
        {"compliance_passed": False, "rationale": "blocked"},
    ])

    async def fake_review(_draft):
        return next(review_results)

    async def fake_draft(story, deep_research, market_snapshot, *, client):
        return {"format": "infographic", "twitter_caption": "cap",
                "_rationale": "r", "_key_data_points": []}

    with patch("agents.content.AsyncSessionLocal", return_value=ctx), \
         patch("agents.content.fetch_market_snapshot", new=AsyncMock(return_value=None)), \
         patch("agents.content._is_already_covered_today", new=AsyncMock(return_value=False)), \
         patch("agents.content.infographics._draft", new=fake_draft), \
         patch.object(content_agent, "fetch_stories", new=AsyncMock(return_value=stories)), \
         patch.object(content_agent, "is_gold_relevant_or_systemic_shock",
                      new=AsyncMock(return_value={"keep": True})), \
         patch.object(content_agent, "fetch_article",
                      new=AsyncMock(return_value=("body", True))), \
         patch.object(content_agent, "search_corroborating",
                      new=AsyncMock(return_value=[])), \
         patch.object(content_agent, "review", new=fake_review), \
         patch.object(content_agent, "build_draft_item",
                      new=MagicMock(return_value=MagicMock())):
        await infographics.run_draft_cycle()

    # The first add() call is the AgentRun; later adds are bundles/items.
    agent_run = captured_agent_runs[0]
    assert agent_run.notes, "Expected agent_run.notes to be populated"
    payload = _json.loads(agent_run.notes)
    assert payload == {
        "candidates": 2,          # 3 stories → capped to top 2 by score
        "top_by_score": 2,        # max_count value
        "drafted": 2,             # both top-2 stories produced a non-None draft
        "compliance_blocked": 1,  # 1 of the 2 drafts failed review
        "queued": 1,              # 1 draft passed review and got a DraftItem
    }, f"Unexpected notes payload: {payload}"


@pytest.mark.asyncio
async def test_run_draft_cycle_writes_notes_on_empty_candidates():
    """Covers D-04 (empty-candidates branch): when fetch_stories returns no
    stories, the early-return path still writes zero-filled notes for
    infographics so the no4 UI subtitle has something to render.
    """
    import json as _json  # noqa: PLC0415

    captured: list = []
    session = AsyncMock()
    session.add = MagicMock(side_effect=lambda o: captured.append(o))

    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("agents.content.AsyncSessionLocal", return_value=ctx), \
         patch("agents.content.fetch_market_snapshot", new=AsyncMock(return_value=None)), \
         patch.object(content_agent, "fetch_stories", new=AsyncMock(return_value=[])):
        await infographics.run_draft_cycle()

    agent_run = captured[0]
    assert agent_run.notes, "Expected agent_run.notes even on empty-candidates run"
    payload = _json.loads(agent_run.notes)
    assert payload == {
        "candidates": 0,
        "top_by_score": 2,
        "drafted": 0,
        "compliance_blocked": 0,
        "queued": 0,
    }, f"Unexpected zero-filled notes payload: {payload}"
