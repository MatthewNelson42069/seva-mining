"""Tests for agents.content.run_text_story_cycle filter kwargs (quick-260421-mos).

Covers the 4 filter-logic states:
- source_whitelist drops non-whitelisted sources
- max_count caps candidates to top N by published_at desc
- source_whitelist=None is a no-op (all stories reach drafter)
- max_count=None is a no-op (all whitelist-matches reach drafter)

Note (debug 260422-zid): predicted_format is no longer used as a routing gate
— candidates = list(stories). The predicted_format field on story fixtures here
is inert / for realism only.

Does NOT re-test the 4 other sub-agents using run_text_story_cycle
(breaking_news, threads, long_form, infographics) — they pass neither whitelist
kwarg so the None-default no-op tests here cover them by construction.
"""
import os
import sys
from unittest.mock import AsyncMock, patch

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
from agents.content import run_text_story_cycle  # noqa: E402


def _session_ctx():
    """Build an async-context-manager mock yielding an AsyncMock session."""
    session = AsyncMock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx, session


def _story(idx, source_name, published_at="2026-04-21T00:00:00Z", predicted_format="quote"):
    return {
        "title": f"Headline {idx}",
        "link": f"http://example.com/{idx}",
        "source_name": source_name,
        "predicted_format": predicted_format,
        "score": 5.0,
        "summary": "body",
        "published_at": published_at,
    }


async def _run_with_stories(stories, *, max_count=None, source_whitelist=None):
    """Drive stories through run_text_story_cycle and return the list the drafter saw."""
    drafter_saw: list[dict] = []

    async def draft_fn(story, deep_research, market_snapshot, *, client):
        drafter_saw.append(story)
        return None  # triggers stub-bundle path; avoids review/build_draft_item coupling

    ctx, _ = _session_ctx()

    with patch("agents.content.AsyncSessionLocal", return_value=ctx), \
         patch("agents.content.fetch_market_snapshot", new=AsyncMock(return_value=None)), \
         patch("agents.content._is_already_covered_today", new=AsyncMock(return_value=False)), \
         patch.object(content_agent, "fetch_stories", new=AsyncMock(return_value=stories)), \
         patch.object(content_agent, "is_gold_relevant_or_systemic_shock",
                      new=AsyncMock(return_value={"keep": True})), \
         patch.object(content_agent, "fetch_article",
                      new=AsyncMock(return_value=("body", True))), \
         patch.object(content_agent, "search_corroborating",
                      new=AsyncMock(return_value=[])):
        await run_text_story_cycle(
            agent_name="test_agent",
            content_type="quote",
            draft_fn=draft_fn,
            max_count=max_count,
            source_whitelist=source_whitelist,
        )

    return drafter_saw


@pytest.mark.asyncio
async def test_source_whitelist_filters_stories():
    """Only stories whose source_name substring-matches the whitelist reach the drafter."""
    whitelist = frozenset({"reuters", "bloomberg"})
    stories = [
        _story(1, "Reuters"),        # matches "reuters" (case-insensitive)
        _story(2, "Bloomberg News"), # matches "bloomberg"
        _story(3, "Some Random Blog"),  # no match
    ]
    drafter_saw = await _run_with_stories(stories, source_whitelist=whitelist)
    seen_sources = {s["source_name"] for s in drafter_saw}
    assert seen_sources == {"Reuters", "Bloomberg News"}
    assert len(drafter_saw) == 2


@pytest.mark.asyncio
async def test_max_count_caps_candidates():
    """With 5 whitelist-matching stories, max_count=2 keeps only the top 2 by published_at desc."""
    whitelist = frozenset({"reuters"})
    stories = [
        _story(1, "Reuters", "2026-04-21T09:00:00Z"),
        _story(2, "Reuters", "2026-04-21T12:00:00Z"),  # newest
        _story(3, "Reuters", "2026-04-21T08:00:00Z"),
        _story(4, "Reuters", "2026-04-21T11:00:00Z"),  # 2nd newest
        _story(5, "Reuters", "2026-04-21T10:00:00Z"),
    ]
    drafter_saw = await _run_with_stories(stories, source_whitelist=whitelist, max_count=2)
    # Top 2 by published_at desc are story 2 (12:00) + story 4 (11:00).
    titles = {s["title"] for s in drafter_saw}
    assert titles == {"Headline 2", "Headline 4"}
    assert len(drafter_saw) == 2


@pytest.mark.asyncio
async def test_source_whitelist_none_is_noop():
    """source_whitelist=None (default) = all stories reach drafter — no whitelist or format gate applied."""
    stories = [
        _story(1, "Reuters"),
        _story(2, "Some Random Blog"),
        _story(3, "Another No-Name Source"),
    ]
    drafter_saw = await _run_with_stories(stories)  # no kwargs
    assert len(drafter_saw) == 3


@pytest.mark.asyncio
async def test_max_count_none_is_noop():
    """max_count=None (default) = no cap applied, all matches reach drafter."""
    whitelist = frozenset({"reuters"})
    stories = [_story(i, "Reuters", f"2026-04-21T{i:02d}:00:00Z") for i in range(5)]
    drafter_saw = await _run_with_stories(stories, source_whitelist=whitelist)  # no max_count
    assert len(drafter_saw) == 5
