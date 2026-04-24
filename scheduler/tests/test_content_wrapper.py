"""
Tests for the per-run WhatsApp firehose hook in agents.content.run_text_story_cycle.

quick-260424-i8b: verifies that:
- The hook fires only for sub_breaking_news + sub_threads with items_queued > 0.
- Empty runs (items_queued == 0) do NOT trigger WhatsApp.
- Other agents (e.g. sub_quotes) never trigger the hook.
- Twilio failures are silent-continue: agent_run.status stays 'completed' and
  agent_run.notes is a JSON dict with whatsapp_per_run_failed merged alongside
  any existing keys (never string-concatenated).
- Happy-path sends merge whatsapp_per_run_sent into notes JSON.
"""

import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://fake-pooler.neon.tech/db?sslmode=require"
)
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
from agents.content import run_text_story_cycle  # noqa: E402
from twilio.base.exceptions import TwilioRestException  # noqa: E402


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _session_ctx(agent_run_notes="{}"):
    """Build an async-context-manager mock yielding an AsyncMock session."""
    session = AsyncMock()
    session.flush = AsyncMock(return_value=None)
    session.commit = AsyncMock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx, session


def _story(idx, source_name="Reuters"):
    return {
        "title": f"Gold Story {idx}",
        "link": f"http://example.com/{idx}",
        "source_name": source_name,
        "score": 8.0,
        "summary": "Gold content.",
        "published_at": "2026-04-24T10:00:00Z",
    }


async def _run_cycle(
    agent_name,
    content_type,
    stories,
    draft_result,
    mock_send_notification=None,
    items_queued_cap=None,
):
    """Drive run_text_story_cycle with a patched send_agent_run_notification.

    Returns the AgentRun mock object after the run completes.
    """
    ctx, session = _session_ctx()

    # Build a mock AgentRun that tracks status/notes writes
    agent_run = MagicMock()
    agent_run.id = 42
    agent_run.items_queued = 0
    agent_run.notes = json.dumps({"candidates": len(stories)})
    agent_run.status = "running"
    session.flush = AsyncMock(return_value=None)

    if mock_send_notification is None:
        mock_send_notification = AsyncMock(return_value=["SM_test"])

    with (
        patch("agents.content.AsyncSessionLocal", return_value=ctx),
        patch("agents.content.fetch_market_snapshot", new=AsyncMock(return_value=None)),
        patch("agents.content._is_already_covered_today", new=AsyncMock(return_value=False)),
        patch.object(content_agent, "fetch_stories", new=AsyncMock(return_value=stories)),
        patch.object(
            content_agent,
            "is_gold_relevant_or_systemic_shock",
            new=AsyncMock(return_value={"keep": True}),
        ),
        patch.object(
            content_agent,
            "fetch_article",
            new=AsyncMock(return_value=("article body", True)),
        ),
        patch.object(
            content_agent,
            "search_corroborating",
            new=AsyncMock(return_value=[]),
        ),
        patch.object(
            content_agent,
            "review",
            new=AsyncMock(return_value={"compliance_passed": True, "rationale": "ok"}),
        ),
        patch.object(
            content_agent,
            "build_draft_item",
            new=MagicMock(return_value=MagicMock()),
        ),
        patch("agents.content.AgentRun", return_value=agent_run),
        patch(
            "agents.content.whatsapp.send_agent_run_notification",
            new=mock_send_notification,
        ),
    ):
        await run_text_story_cycle(
            agent_name=agent_name,
            content_type=content_type,
            draft_fn=AsyncMock(return_value=draft_result),
        )

    return agent_run


# ---------------------------------------------------------------------------
# T1 Tests: hook dispatch and gating
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_per_run_hook_fires_for_breaking_news_with_items_queued_gt_zero():
    """Hook fires for sub_breaking_news when items_queued > 0."""
    stories = [_story(1)]
    draft_result = {
        "format": "breaking_news",
        "_rationale": "r",
        "_key_data_points": [],
        "tweet": "Gold surges to $3100 on strong ETF inflows. #Gold",
    }
    mock_send = AsyncMock(return_value=["SM_abc"])

    await _run_cycle(
        agent_name="sub_breaking_news",
        content_type="breaking_news",
        stories=stories,
        draft_result=draft_result,
        mock_send_notification=mock_send,
    )

    mock_send.assert_awaited_once()
    call_kwargs = mock_send.call_args
    assert call_kwargs.kwargs.get("agent_name") == "sub_breaking_news" or (
        call_kwargs.args and call_kwargs.args[0] == "sub_breaking_news"
    ), f"agent_name not passed correctly: {call_kwargs}"


@pytest.mark.asyncio
async def test_per_run_hook_fires_for_threads_with_items_queued_gt_zero():
    """Hook fires for sub_threads; thread text is joined from 'tweets' list."""
    stories = [_story(1)]
    draft_result = {
        "format": "thread",
        "_rationale": "r",
        "_key_data_points": [],
        "tweets": ["tweet A", "tweet B"],
    }
    mock_send = AsyncMock(return_value=["SM_thread"])

    await _run_cycle(
        agent_name="sub_threads",
        content_type="thread",
        stories=stories,
        draft_result=draft_result,
        mock_send_notification=mock_send,
    )

    mock_send.assert_awaited_once()
    # items list passed should contain joined tweet text
    call_args = mock_send.call_args
    items_arg = call_args.kwargs.get("items") or (call_args.args[1] if len(call_args.args) > 1 else None)
    assert items_arg is not None, "items must be passed to send_agent_run_notification"
    assert len(items_arg) >= 1
    # Each item should be the joined thread tweets
    assert "tweet A" in items_arg[0] and "tweet B" in items_arg[0], (
        f"Expected joined thread tweets in items, got: {items_arg}"
    )


@pytest.mark.asyncio
async def test_per_run_hook_skipped_for_other_agents():
    """Hook is NOT fired for sub_quotes or other non-firehose agents."""
    stories = [_story(1)]
    draft_result = {
        "format": "quote",
        "_rationale": "r",
        "_key_data_points": [],
        "post": "A gold quote.",
    }
    mock_send = AsyncMock(return_value=["SM_skip"])

    await _run_cycle(
        agent_name="sub_quotes",
        content_type="quote",
        stories=stories,
        draft_result=draft_result,
        mock_send_notification=mock_send,
    )

    mock_send.assert_not_awaited()


@pytest.mark.asyncio
async def test_per_run_hook_skipped_when_items_queued_zero():
    """Hook is NOT fired when all items are compliance-blocked (items_queued == 0)."""
    stories = [_story(1)]
    draft_result = {
        "format": "breaking_news",
        "_rationale": "r",
        "_key_data_points": [],
        "tweet": "Blocked tweet",
    }
    mock_send = AsyncMock(return_value=["SM_skip"])

    ctx, session = _session_ctx()
    agent_run = MagicMock()
    agent_run.id = 99
    agent_run.items_queued = 0
    agent_run.notes = json.dumps({"candidates": 1})
    agent_run.status = "running"

    with (
        patch("agents.content.AsyncSessionLocal", return_value=ctx),
        patch("agents.content.fetch_market_snapshot", new=AsyncMock(return_value=None)),
        patch("agents.content._is_already_covered_today", new=AsyncMock(return_value=False)),
        patch.object(content_agent, "fetch_stories", new=AsyncMock(return_value=stories)),
        patch.object(
            content_agent,
            "is_gold_relevant_or_systemic_shock",
            new=AsyncMock(return_value={"keep": True}),
        ),
        patch.object(
            content_agent,
            "fetch_article",
            new=AsyncMock(return_value=("article body", True)),
        ),
        patch.object(content_agent, "search_corroborating", new=AsyncMock(return_value=[])),
        # Block compliance for all items
        patch.object(
            content_agent,
            "review",
            new=AsyncMock(return_value={"compliance_passed": False, "rationale": "blocked"}),
        ),
        patch.object(content_agent, "build_draft_item", new=MagicMock(return_value=MagicMock())),
        patch("agents.content.AgentRun", return_value=agent_run),
        patch(
            "agents.content.whatsapp.send_agent_run_notification",
            new=mock_send,
        ),
    ):
        await run_text_story_cycle(
            agent_name="sub_breaking_news",
            content_type="breaking_news",
            draft_fn=AsyncMock(return_value=draft_result),
        )

    mock_send.assert_not_awaited()


@pytest.mark.asyncio
async def test_per_run_hook_twilio_failure_is_silent():
    """TwilioRestException from send_agent_run_notification: run stays 'completed', notes has whatsapp_per_run_failed key."""
    stories = [_story(1)]
    draft_result = {
        "format": "breaking_news",
        "_rationale": "r",
        "_key_data_points": [],
        "tweet": "Gold at all-time high. Buy signal triggered.",
    }

    exc = TwilioRestException(status=500, uri="/messages", msg="Twilio down")
    mock_send = AsyncMock(side_effect=exc)

    agent_run = await _run_cycle(
        agent_name="sub_breaking_news",
        content_type="breaking_news",
        stories=stories,
        draft_result=draft_result,
        mock_send_notification=mock_send,
    )

    # agent_run.status must stay "completed" — Twilio failure is non-fatal
    assert agent_run.status == "completed", (
        f"Expected status='completed' after Twilio failure, got {agent_run.status!r}"
    )
    # notes must be parseable JSON dict (not a concatenated string)
    notes_raw = agent_run.notes
    assert notes_raw is not None, "agent_run.notes must not be None"
    try:
        notes_dict = json.loads(notes_raw)
    except (json.JSONDecodeError, TypeError) as e:
        pytest.fail(
            f"agent_run.notes must be parseable JSON after Twilio failure, got {notes_raw!r}: {e}"
        )
    assert isinstance(notes_dict, dict), (
        f"agent_run.notes must be a JSON dict, got {type(notes_dict)}"
    )
    assert "whatsapp_per_run_failed" in notes_dict, (
        f"Expected 'whatsapp_per_run_failed' key in notes, got keys: {list(notes_dict.keys())}"
    )
    # Must also preserve existing candidates key
    assert "candidates" in notes_dict, (
        "'candidates' key must be preserved in notes dict alongside whatsapp status"
    )


@pytest.mark.asyncio
async def test_per_run_hook_success_merges_into_notes_dict():
    """Happy path: send returns ['SM_1']; notes JSON contains whatsapp_per_run_sent alongside candidates."""
    stories = [_story(1)]
    draft_result = {
        "format": "breaking_news",
        "_rationale": "r",
        "_key_data_points": [],
        "tweet": "Gold surges — central bank buys confirmed.",
    }
    mock_send = AsyncMock(return_value=["SM_1"])

    agent_run = await _run_cycle(
        agent_name="sub_breaking_news",
        content_type="breaking_news",
        stories=stories,
        draft_result=draft_result,
        mock_send_notification=mock_send,
    )

    assert agent_run.status == "completed"
    notes_raw = agent_run.notes
    assert notes_raw is not None
    try:
        notes_dict = json.loads(notes_raw)
    except (json.JSONDecodeError, TypeError) as e:
        pytest.fail(f"agent_run.notes must be parseable JSON, got {notes_raw!r}: {e}")

    assert isinstance(notes_dict, dict)
    assert "whatsapp_per_run_sent" in notes_dict, (
        f"Expected 'whatsapp_per_run_sent' in notes dict, got keys: {list(notes_dict.keys())}"
    )
    assert "SM_1" in notes_dict["whatsapp_per_run_sent"], (
        f"Expected SID 'SM_1' in whatsapp_per_run_sent value, got {notes_dict['whatsapp_per_run_sent']!r}"
    )
    # candidates key must still be present
    assert "candidates" in notes_dict, (
        "'candidates' key must be preserved in notes dict"
    )


# ---------------------------------------------------------------------------
# T1 Tests: quick-260424-j5i — min_score floor + floored_by_min_score telemetry
# ---------------------------------------------------------------------------


async def _run_cycle_with_min_score(
    agent_name,
    content_type,
    stories,
    draft_result,
    min_score,
    max_count=None,
):
    """Variant of _run_cycle that passes `min_score` (and optional `max_count`) through.

    Returns (agent_run, build_draft_item_mock, session) so tests can inspect how
    many DraftItems were built vs how many ContentBundles got flushed.
    """
    ctx, session = _session_ctx()

    agent_run = MagicMock()
    agent_run.id = 42
    agent_run.items_queued = 0
    agent_run.notes = json.dumps({"candidates": len(stories)})
    agent_run.status = "running"
    session.flush = AsyncMock(return_value=None)

    mock_build_draft_item = MagicMock(return_value=MagicMock())
    mock_send = AsyncMock(return_value=["SM_test"])

    with (
        patch("agents.content.AsyncSessionLocal", return_value=ctx),
        patch("agents.content.fetch_market_snapshot", new=AsyncMock(return_value=None)),
        patch("agents.content._is_already_covered_today", new=AsyncMock(return_value=False)),
        patch.object(content_agent, "fetch_stories", new=AsyncMock(return_value=stories)),
        patch.object(
            content_agent,
            "is_gold_relevant_or_systemic_shock",
            new=AsyncMock(return_value={"keep": True}),
        ),
        patch.object(
            content_agent,
            "fetch_article",
            new=AsyncMock(return_value=("article body", True)),
        ),
        patch.object(
            content_agent,
            "search_corroborating",
            new=AsyncMock(return_value=[]),
        ),
        patch.object(
            content_agent,
            "review",
            new=AsyncMock(return_value={"compliance_passed": True, "rationale": "ok"}),
        ),
        patch.object(content_agent, "build_draft_item", new=mock_build_draft_item),
        patch("agents.content.AgentRun", return_value=agent_run),
        patch(
            "agents.content.whatsapp.send_agent_run_notification",
            new=mock_send,
        ),
    ):
        kwargs = dict(
            agent_name=agent_name,
            content_type=content_type,
            draft_fn=AsyncMock(return_value=draft_result),
            min_score=min_score,
        )
        if max_count is not None:
            kwargs["max_count"] = max_count
        await run_text_story_cycle(**kwargs)

    return agent_run, mock_build_draft_item, session


@pytest.mark.asyncio
async def test_min_score_filters_below_threshold():
    """j5i D2/D6: min_score skips DraftItem creation for stories whose score is below
    the floor, but the ContentBundle row is still persisted (compliance_passed=True
    branch, just no DraftItem).
    """
    stories = [
        {
            "title": "Top story (score 8.0)",
            "link": "http://example.com/1",
            "source_name": "Reuters",
            "score": 8.0,
            "summary": "Gold content.",
            "published_at": "2026-04-24T10:00:00Z",
        },
        {
            "title": "Mid story (score 6.0 — floored)",
            "link": "http://example.com/2",
            "source_name": "Reuters",
            "score": 6.0,
            "summary": "Gold content.",
            "published_at": "2026-04-24T09:00:00Z",
        },
        {
            "title": "Low story (score 5.5 — floored)",
            "link": "http://example.com/3",
            "source_name": "Reuters",
            "score": 5.5,
            "summary": "Gold content.",
            "published_at": "2026-04-24T08:00:00Z",
        },
    ]
    draft_result = {
        "format": "breaking_news",
        "_rationale": "r",
        "_key_data_points": [],
        "tweet": "A draft.",
    }

    agent_run, mock_build_draft_item, _session = await _run_cycle_with_min_score(
        agent_name="sub_breaking_news",
        content_type="breaking_news",
        stories=stories,
        draft_result=draft_result,
        min_score=6.5,
    )

    # Only 1 of 3 stories should have produced a DraftItem (the 8.0 one).
    assert mock_build_draft_item.call_count == 1, (
        f"Expected 1 DraftItem built (score 8.0 passes), got {mock_build_draft_item.call_count}"
    )
    assert agent_run.items_queued == 1, f"Expected items_queued=1, got {agent_run.items_queued}"


@pytest.mark.asyncio
async def test_floored_by_min_score_counter_populated():
    """j5i D7: agent_run.notes contains 'floored_by_min_score': 2 after the
    above run-shape (3 stories, 2 below 6.5 floor).
    """
    stories = [
        {
            "title": "Top (8.0)",
            "link": "http://example.com/1",
            "source_name": "Reuters",
            "score": 8.0,
            "summary": "",
            "published_at": "2026-04-24T10:00:00Z",
        },
        {
            "title": "Mid (6.0)",
            "link": "http://example.com/2",
            "source_name": "Reuters",
            "score": 6.0,
            "summary": "",
            "published_at": "2026-04-24T09:00:00Z",
        },
        {
            "title": "Low (5.5)",
            "link": "http://example.com/3",
            "source_name": "Reuters",
            "score": 5.5,
            "summary": "",
            "published_at": "2026-04-24T08:00:00Z",
        },
    ]
    draft_result = {
        "format": "breaking_news",
        "_rationale": "r",
        "_key_data_points": [],
        "tweet": "A draft.",
    }

    agent_run, _build, _session = await _run_cycle_with_min_score(
        agent_name="sub_breaking_news",
        content_type="breaking_news",
        stories=stories,
        draft_result=draft_result,
        min_score=6.5,
    )

    notes = json.loads(agent_run.notes)
    assert "floored_by_min_score" in notes, (
        f"Expected 'floored_by_min_score' in notes, got keys: {list(notes.keys())}"
    )
    assert notes["floored_by_min_score"] == 2, (
        f"Expected floored_by_min_score=2, got {notes['floored_by_min_score']}"
    )


@pytest.mark.asyncio
async def test_all_stories_floored_returns_empty_not_failed():
    """j5i D6: when ALL stories fall below min_score, items_queued stays 0 and
    agent_run.status == 'completed' (NOT 'failed'). Empty runs are the silent
    firehose contract from i8b — the hook does not fire and no WhatsApp goes out.
    """
    stories = [
        {
            "title": f"Low story {i}",
            "link": f"http://example.com/{i}",
            "source_name": "Reuters",
            "score": 5.0,
            "summary": "",
            "published_at": "2026-04-24T10:00:00Z",
        }
        for i in range(3)
    ]
    draft_result = {
        "format": "breaking_news",
        "_rationale": "r",
        "_key_data_points": [],
        "tweet": "A draft.",
    }

    agent_run, mock_build, _session = await _run_cycle_with_min_score(
        agent_name="sub_breaking_news",
        content_type="breaking_news",
        stories=stories,
        draft_result=draft_result,
        min_score=6.5,
    )

    assert agent_run.items_queued == 0
    assert agent_run.status == "completed", (
        f"Expected status='completed' on empty run, got {agent_run.status!r}"
    )
    assert mock_build.call_count == 0, (
        f"Expected 0 DraftItems built (all floored), got {mock_build.call_count}"
    )
    notes = json.loads(agent_run.notes)
    assert notes.get("floored_by_min_score", 0) >= 1, (
        f"Expected floored_by_min_score>=1, got {notes.get('floored_by_min_score')}"
    )
