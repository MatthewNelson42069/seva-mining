"""Tests for agents.content.gold_history sub-agent (quick-260422-lbb).

gold_history is the second bespoke sub-agent — does NOT call
content_agent.fetch_stories() (has its own curated historical-story source
guarded by the `gold_history_used_topics` Config key). DOES call
content_agent.review() inline before writing.

Curated-whitelist model (quick-260422-lbb): stories are pre-researched JSON
fact sheets in gold_history_stories/. The drafter is locked to verified_facts
via the FACT FIDELITY clause. The _pick_story and _verify_facts functions are
fully removed (no Claude-from-memory picker, no SerpAPI runtime verification).
"""
import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock

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


# ---------------------------------------------------------------------------
# Module surface
# ---------------------------------------------------------------------------

def test_module_surface():
    assert gold_history.CONTENT_TYPE == "gold_history"
    assert gold_history.AGENT_NAME == "sub_gold_history"
    assert callable(gold_history.run_draft_cycle)
    assert callable(gold_history._pick_fresh_slug)
    assert callable(gold_history._load_fact_sheet)
    assert callable(gold_history._draft_gold_history)
    assert callable(gold_history._get_used_topics)
    assert callable(gold_history._add_used_topic)
    # Old Claude-from-memory picker and SerpAPI verifier must be GONE.
    assert not hasattr(gold_history, "_pick_story"), (
        "_pick_story must be fully removed (curated-whitelist model does not use it)"
    )
    assert not hasattr(gold_history, "_verify_facts"), (
        "_verify_facts must be fully removed (no SerpAPI runtime verification)"
    )


# ---------------------------------------------------------------------------
# Whitelist loader tests (sync — no async needed)
# ---------------------------------------------------------------------------

def test_whitelist_loads_all_stories():
    """load_all_stories() must return at least 10 seeded stories with valid schema."""
    from agents.content.gold_history_stories import load_all_stories
    stories = load_all_stories()
    assert len(stories) >= 10, f"expected ≥10 seeded stories, got {len(stories)}"
    for s in stories:
        for k in ("story_slug", "story_title", "summary", "verified_facts", "sources"):
            assert k in s, f"{s.get('story_slug', '?')}: missing required key '{k}'"
        assert s["verified_facts"], f"{s['story_slug']}: verified_facts must be non-empty"
        for fact in s["verified_facts"]:
            assert fact.get("source_url"), (
                f"{s['story_slug']}: every fact must have a non-empty source_url — {fact}"
            )
        assert s["sources"], f"{s['story_slug']}: sources must be non-empty"
        for src in s["sources"]:
            assert src.get("url"), f"{s['story_slug']}: every source must have a url"
            assert src.get("publisher"), f"{s['story_slug']}: every source must have a publisher"


# ---------------------------------------------------------------------------
# _pick_fresh_slug tests
# ---------------------------------------------------------------------------

def test_pick_fresh_slug_excludes_used():
    """Filtered to slugs not in used_topics; returns from the remaining set."""
    whitelist = [{"story_slug": "a"}, {"story_slug": "b"}, {"story_slug": "c"}]
    slug = gold_history._pick_fresh_slug(["a", "b"], whitelist)
    assert slug == "c"


def test_pick_fresh_slug_returns_none_when_all_used():
    """Returns None when every whitelisted slug has been used."""
    whitelist = [{"story_slug": "a"}]
    assert gold_history._pick_fresh_slug(["a"], whitelist) is None


def test_pick_fresh_slug_returns_slug_when_none_used():
    """Returns a slug string when no topics have been used yet."""
    whitelist = [{"story_slug": "x"}, {"story_slug": "y"}]
    slug = gold_history._pick_fresh_slug([], whitelist)
    assert slug in ("x", "y")


def test_pick_fresh_slug_empty_whitelist():
    """Returns None for an empty whitelist."""
    assert gold_history._pick_fresh_slug([], []) is None


# ---------------------------------------------------------------------------
# _load_fact_sheet tests
# ---------------------------------------------------------------------------

def test_load_fact_sheet_returns_dict_for_known_slug():
    """Returns a dict with all required keys for any seeded slug."""
    from agents.content.gold_history_stories import load_all_stories
    some_slug = load_all_stories()[0]["story_slug"]
    sheet = gold_history._load_fact_sheet(some_slug)
    assert sheet is not None
    assert sheet["story_slug"] == some_slug
    assert "verified_facts" in sheet
    assert "sources" in sheet


def test_load_fact_sheet_returns_none_for_unknown_slug():
    """Returns None for a slug that does not match any committed JSON file."""
    assert gold_history._load_fact_sheet("nonexistent-slug-xyz-123") is None


# ---------------------------------------------------------------------------
# _get_used_topics tests (retained — helpers are unchanged)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# _draft_gold_history tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_draft_gold_history_includes_sources_field():
    """Drafter output dict must include a non-empty `sources` list."""
    client = AsyncMock()
    response = MagicMock()
    response.content = [MagicMock(text=json.dumps({
        "format": "gold_history",
        "story_title": "T",
        "story_slug": "t",
        "tweets": ["hook"],
        "instagram_carousel": [{"slide": 1, "headline": "h", "body": "b", "visual_note": "v"}],
        "instagram_caption": "cap",
        "sources": [{"ref": "[1]", "url": "https://x.example.com", "publisher": "X"}],
    }))]
    client.messages.create = AsyncMock(return_value=response)
    fact_sheet = {
        "story_slug": "t",
        "story_title": "T",
        "summary": "s",
        "recommended_arc": "h→r→c→p",
        "verified_facts": [{"claim": "c", "source_url": "https://x.example.com"}],
        "sources": [{"ref": "[1]", "url": "https://x.example.com", "publisher": "X"}],
    }
    draft = await gold_history._draft_gold_history(fact_sheet, client=client)
    assert draft is not None
    assert "sources" in draft
    assert len(draft["sources"]) >= 1


@pytest.mark.asyncio
async def test_draft_gold_history_prompt_contains_fact_fidelity_clause():
    """The drafter must embed the FACT FIDELITY clause in its prompt."""
    client = AsyncMock()
    response = MagicMock()
    response.content = [MagicMock(text=json.dumps({
        "format": "gold_history", "story_title": "T", "story_slug": "t",
        "tweets": ["h"], "instagram_carousel": [], "instagram_caption": "c",
        "sources": [{"ref": "[1]", "url": "https://x.example.com", "publisher": "X"}],
    }))]
    client.messages.create = AsyncMock(return_value=response)
    fact_sheet = {
        "story_slug": "t", "story_title": "T", "summary": "s",
        "recommended_arc": "arc",
        "verified_facts": [{"claim": "c", "source_url": "https://x.example.com"}],
        "sources": [{"ref": "[1]", "url": "https://x.example.com", "publisher": "X"}],
    }
    await gold_history._draft_gold_history(fact_sheet, client=client)
    # Inspect both system prompt and user message for the clause.
    _, kwargs = client.messages.create.call_args
    system = kwargs.get("system", "")
    user = kwargs["messages"][0]["content"]
    assert "FACT FIDELITY" in system or "FACT FIDELITY" in user, (
        "The FACT FIDELITY clause must appear in the composed prompt to constrain the drafter"
    )


@pytest.mark.asyncio
async def test_draft_gold_history_returns_none_on_missing_sources_key():
    """If Claude returns JSON without `sources`, _draft_gold_history returns None."""
    client = AsyncMock()
    response = MagicMock()
    # Missing `sources` key — drafter must reject this
    response.content = [MagicMock(text=json.dumps({
        "format": "gold_history",
        "story_title": "T",
        "story_slug": "t",
        "tweets": ["hook"],
        "instagram_carousel": [],
        "instagram_caption": "cap",
        # NOTE: `sources` intentionally absent
    }))]
    client.messages.create = AsyncMock(return_value=response)
    fact_sheet = {
        "story_slug": "t",
        "story_title": "T",
        "summary": "s",
        "recommended_arc": "arc",
        "verified_facts": [{"claim": "c", "source_url": "https://x.example.com"}],
        "sources": [{"ref": "[1]", "url": "https://x.example.com", "publisher": "X"}],
    }
    draft = await gold_history._draft_gold_history(fact_sheet, client=client)
    assert draft is None


@pytest.mark.asyncio
async def test_draft_gold_history_returns_none_on_bad_json():
    """Returns None when the Claude response cannot be parsed as JSON."""
    client = AsyncMock()
    response = MagicMock()
    response.content = [MagicMock(text="not valid json at all")]
    client.messages.create = AsyncMock(return_value=response)
    fact_sheet = {
        "story_slug": "t",
        "story_title": "T",
        "summary": "s",
        "recommended_arc": "arc",
        "verified_facts": [{"claim": "c", "source_url": "https://x.example.com"}],
        "sources": [{"ref": "[1]", "url": "https://x.example.com", "publisher": "X"}],
    }
    draft = await gold_history._draft_gold_history(fact_sheet, client=client)
    assert draft is None
