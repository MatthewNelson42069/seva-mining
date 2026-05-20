"""Wave 1 GREEN tests for scheduler/agents/juno_relevance.py (DEF-06).

Production module (`scheduler/agents/juno_relevance.py`) was landed by
`10-02-PLAN.md` Task 1; the module-level skip from Wave 0 was removed in
the same task to flip this entire file GREEN.

Contracts asserted (verbatim from 10-CONTEXT.md §D-05/D-06/D-07):
- DefenceRelevance Pydantic model with the 10-value Literal category enum
- classify_story(...) async function returning DefenceRelevance | None
- survives_threshold(...) filter (confidence >= 0.7 AND category != 'not_relevant')
- HAIKU_MODEL = 'claude-haiku-4-5'
- HAIKU_MAX_TOKENS = 400
- CONFIDENCE_THRESHOLD = 0.7
- Anthropic structured outputs via messages.parse(output_format=DefenceRelevance)
"""
from __future__ import annotations

import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

# Wave 1 (10-02-PLAN.md) flipped this file GREEN by landing
# scheduler/agents/juno_relevance.py.

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test-fake")


# ---------------------------------------------------------------------------
# DefenceRelevance Pydantic model — shape assertions
# ---------------------------------------------------------------------------


def test_defence_relevance_pydantic_model():
    """DefenceRelevance validates the contract from 10-CONTEXT §D-05/D-06."""
    from pydantic import ValidationError

    from agents.juno_relevance import DefenceRelevance

    # Valid construction
    inst = DefenceRelevance(
        is_relevant=True,
        category="spending_policy",
        confidence=0.92,
        reasoning="Lockheed F-35 follow-on contract awarded",
    )
    assert inst.is_relevant is True
    assert inst.category == "spending_policy"
    assert inst.confidence == 0.92
    assert "Lockheed" in inst.reasoning

    # Invalid category raises ValidationError (Literal enforced)
    with pytest.raises(ValidationError):
        DefenceRelevance(
            is_relevant=True,
            category="gold_news",  # not in the 10-value enum
            confidence=0.9,
            reasoning="x",
        )

    # confidence out of range
    with pytest.raises(ValidationError):
        DefenceRelevance(
            is_relevant=True,
            category="space",
            confidence=1.5,
            reasoning="x",
        )

    # reasoning too long (max_length=200)
    with pytest.raises(ValidationError):
        DefenceRelevance(
            is_relevant=True,
            category="space",
            confidence=0.8,
            reasoning="x" * 250,
        )


def test_haiku_model_constants():
    """Wave 1 must export the model/threshold constants verbatim."""
    from agents.juno_relevance import (
        CONFIDENCE_THRESHOLD,
        HAIKU_MAX_TOKENS,
        HAIKU_MODEL,
    )

    assert HAIKU_MODEL == "claude-haiku-4-5"
    assert HAIKU_MAX_TOKENS == 400
    assert CONFIDENCE_THRESHOLD == 0.7


# ---------------------------------------------------------------------------
# classify_story() — golden-input assertions per VALIDATION §Wave 0 corpus
# ---------------------------------------------------------------------------


def _mock_parse_response(parsed):
    """Build a MagicMock response object whose .parsed_output == parsed."""
    resp = MagicMock()
    resp.parsed_output = parsed
    return resp


@pytest.mark.asyncio
async def test_classify_story_defence_direct():
    """Lockheed F-35 contract → defence-direct, spending_policy, high confidence."""
    from agents.juno_relevance import DefenceRelevance, classify_story

    expected = DefenceRelevance(
        is_relevant=True,
        category="spending_policy",
        confidence=0.92,
        reasoning="Lockheed F-35 follow-on contract",
    )
    client = MagicMock()
    client.messages = MagicMock()
    client.messages.parse = AsyncMock(return_value=_mock_parse_response(expected))

    result = await classify_story(
        client,
        title="Lockheed Martin wins $1.8B F-35 follow-on contract",
        snippet="DoD announced today...",
    )

    assert result == expected
    assert result.is_relevant is True
    assert result.category == "spending_policy"


@pytest.mark.asyncio
async def test_classify_story_active_conflict():
    """Ukraine front-line update → active_conflict, high confidence."""
    from agents.juno_relevance import DefenceRelevance, classify_story

    expected = DefenceRelevance(
        is_relevant=True,
        category="active_conflict",
        confidence=0.88,
        reasoning="Active conflict zone update",
    )
    client = MagicMock()
    client.messages = MagicMock()
    client.messages.parse = AsyncMock(return_value=_mock_parse_response(expected))

    result = await classify_story(
        client,
        title="Ukraine reports Russian advance in Donetsk oblast",
        snippet="Front-line movement reported overnight...",
    )

    assert result is not None
    assert result.category == "active_conflict"
    assert result.confidence >= 0.7


@pytest.mark.asyncio
async def test_classify_story_sanctions():
    """EUV semiconductor export control → sanctions_export, high confidence."""
    from agents.juno_relevance import DefenceRelevance, classify_story

    expected = DefenceRelevance(
        is_relevant=True,
        category="sanctions_export",
        confidence=0.85,
        reasoning="EUV export control on advanced-node chips",
    )
    client = MagicMock()
    client.messages = MagicMock()
    client.messages.parse = AsyncMock(return_value=_mock_parse_response(expected))

    result = await classify_story(
        client,
        title="US tightens EUV export controls on advanced-node fabs",
        snippet="Commerce Department added 12 entities...",
    )

    assert result is not None
    assert result.category == "sanctions_export"


@pytest.mark.asyncio
async def test_classify_story_consumer_tech_reject():
    """Consumer iPhone announcement → not_relevant."""
    from agents.juno_relevance import DefenceRelevance, classify_story

    expected = DefenceRelevance(
        is_relevant=False,
        category="not_relevant",
        confidence=0.92,
        reasoning="Consumer product announcement; no defence linkage",
    )
    client = MagicMock()
    client.messages = MagicMock()
    client.messages.parse = AsyncMock(return_value=_mock_parse_response(expected))

    result = await classify_story(
        client,
        title="Apple unveils new iPhone 18 Pro with bigger battery",
        snippet="Cupertino — Apple Inc. today announced...",
    )

    assert result is not None
    assert result.is_relevant is False
    assert result.category == "not_relevant"


@pytest.mark.asyncio
async def test_classify_story_borderline():
    """Drone hobbyist regulation → energy_critmin/borderline confidence."""
    from agents.juno_relevance import DefenceRelevance, classify_story

    expected = DefenceRelevance(
        is_relevant=True,
        category="energy_critmin",
        confidence=0.65,
        reasoning="Dual-use drone regulation; borderline defence linkage",
    )
    client = MagicMock()
    client.messages = MagicMock()
    client.messages.parse = AsyncMock(return_value=_mock_parse_response(expected))

    result = await classify_story(
        client,
        title="FAA tightens hobbyist drone registration rules",
        snippet="Civil aviation regulator announces...",
    )

    assert result is not None
    # Borderline = ~0.5-0.7; test ensures the model can carry < 0.7 values
    assert result.confidence < 0.7


# ---------------------------------------------------------------------------
# survives_threshold() — filter gate (CONFIDENCE_THRESHOLD = 0.7 + category != not_relevant)
# ---------------------------------------------------------------------------


def test_survives_threshold_above_07():
    from agents.juno_relevance import DefenceRelevance, survives_threshold

    relevance = DefenceRelevance(
        is_relevant=True,
        category="space",
        confidence=0.75,
        reasoning="Starlink defence contract",
    )
    assert survives_threshold(relevance) is True


def test_survives_threshold_below_07():
    from agents.juno_relevance import DefenceRelevance, survives_threshold

    relevance = DefenceRelevance(
        is_relevant=True,
        category="space",
        confidence=0.65,
        reasoning="x",
    )
    assert survives_threshold(relevance) is False


def test_survives_threshold_at_07():
    """confidence == 0.7 is the boundary — survives (>=, not >)."""
    from agents.juno_relevance import DefenceRelevance, survives_threshold

    relevance = DefenceRelevance(
        is_relevant=True,
        category="treaty_events",
        confidence=0.7,
        reasoning="x",
    )
    assert survives_threshold(relevance) is True


def test_survives_threshold_not_relevant():
    """Category gate — even high-confidence 'not_relevant' filtered out."""
    from agents.juno_relevance import DefenceRelevance, survives_threshold

    relevance = DefenceRelevance(
        is_relevant=True,
        category="not_relevant",
        confidence=0.95,
        reasoning="High confidence not-relevant",
    )
    assert survives_threshold(relevance) is False


def test_survives_threshold_none_input():
    """None input (classifier failed / returned None) → fail-closed False."""
    from agents.juno_relevance import survives_threshold

    assert survives_threshold(None) is False
