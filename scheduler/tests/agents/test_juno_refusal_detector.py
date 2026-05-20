"""Wave 0 RED tests for scheduler/agents/juno_refusal_detector.py (DEF-07).

Production module lands in Wave 2 (10-03-PLAN.md). Wave 2's final task
removes the module-level skip below to turn this entire file GREEN.

Contracts asserted (verbatim from 10-CONTEXT.md §D-11):
- REFUSAL_PATTERN regex (7 substrings, case-insensitive)
- FRAMING_NUDGE constant (anti-tactical framing string)
- SECTION_UNAVAILABLE_COPY constant (operator-facing fallback copy)
- is_refusal(text: str | None) -> bool — first-500-chars scan
- call_with_refusal_guard(...) async wrapper:
    - retry-once with FRAMING_NUDGE on first refusal
    - on second refusal: return (None, diagnostic_dict)
    - diagnostic_dict carries refusal_detected, retry_attempted,
      second_attempt_excerpt fields
"""
from __future__ import annotations

import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

# Wave 2 (10-03-PLAN.md) removes this skip line to turn the module GREEN.
pytest.skip(
    "Wave 0 RED — production scheduler/agents/juno_refusal_detector.py "
    "lands in Wave 2 (10-03-PLAN.md). Remove this skip line in that wave's "
    "task to turn tests GREEN.",
    allow_module_level=True,
)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test-fake")


# ---------------------------------------------------------------------------
# is_refusal() — substring-pattern detection (D-11)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "refusal_text",
    [
        "I cannot do that for you",
        "as an AI, I have to decline",
        "This violates my safety guidelines",
        "I am unable to provide that analysis",
        "I'm not able to discuss operational details",
        "I cannot assist with that request",
        "That goes against my values",
    ],
)
def test_is_refusal_patterns(refusal_text):
    """Each of the 7 substring patterns from D-11 triggers detection."""
    from agents.juno_refusal_detector import is_refusal

    assert is_refusal(refusal_text) is True


def test_is_refusal_case_insensitive():
    """Refusal patterns match case-insensitively."""
    from agents.juno_refusal_detector import is_refusal

    assert is_refusal("I CANNOT do that") is True
    assert is_refusal("As An AI assistant") is True
    assert is_refusal("SAFETY GUIDELINES prevent me") is True


def test_is_refusal_first_500_chars_only():
    """Refusal detection scans only the first 500 chars per D-11."""
    from agents.juno_refusal_detector import is_refusal

    # Pad with 600+ chars of clean defence copy, then refusal at the END.
    padding = "Lockheed Martin announced a $1.8B contract. " * 20  # ~900 chars
    text_with_late_refusal = padding + "I cannot continue this analysis."
    assert is_refusal(text_with_late_refusal) is False

    # Same refusal at the START → detected
    text_with_early_refusal = "I cannot continue. " + padding
    assert is_refusal(text_with_early_refusal) is True


def test_is_refusal_none_and_empty_input():
    from agents.juno_refusal_detector import is_refusal

    assert is_refusal(None) is False
    assert is_refusal("") is False


def test_is_refusal_no_match():
    """Clean defence markdown returns False (no false positives)."""
    from agents.juno_refusal_detector import is_refusal

    clean = (
        "### 🛡️ Defence News\n"
        "- Lockheed wins $1.8B F-35 contract (Defense News)\n"
        "- Breaking Defense reports new RUSI commentary (Breaking Defense)\n"
        "- SIPRI publishes annual military spending review (SIPRI)\n"
    )
    assert is_refusal(clean) is False


# ---------------------------------------------------------------------------
# Constants — FRAMING_NUDGE + SECTION_UNAVAILABLE_COPY
# ---------------------------------------------------------------------------


def test_framing_nudge_constant():
    """FRAMING_NUDGE contains anti-tactical framing markers from D-11."""
    from agents.juno_refusal_detector import FRAMING_NUDGE

    assert "defence-industry market commentary" in FRAMING_NUDGE
    assert "NOT on force posture" in FRAMING_NUDGE
    assert "contract values" in FRAMING_NUDGE
    assert "vendor names" in FRAMING_NUDGE


def test_section_unavailable_copy_constant():
    """SECTION_UNAVAILABLE_COPY is the verbatim operator-facing fallback."""
    from agents.juno_refusal_detector import SECTION_UNAVAILABLE_COPY

    assert SECTION_UNAVAILABLE_COPY == (
        "Section unavailable — defence-industry summary could not be "
        "generated for this fire. See agent_runs.notes for diagnostic."
    )


# ---------------------------------------------------------------------------
# call_with_refusal_guard() — retry-once + second-refusal fallback
# ---------------------------------------------------------------------------


def _mock_response_with_text(text: str):
    """Build a MagicMock anthropic response whose content[0].text == text."""
    block = MagicMock()
    block.text = text
    response = MagicMock()
    response.content = [block]
    return response


@pytest.mark.asyncio
async def test_retry_with_nudge_first_refusal_then_success():
    """First call refuses → retry with FRAMING_NUDGE → second call returns clean text."""
    from agents.juno_refusal_detector import call_with_refusal_guard

    refusal_text = "I cannot provide that analysis."
    clean_text = (
        "### 🛡️ Defence News\n"
        "- Lockheed wins $1.8B F-35 contract (Defense News)"
    )

    client = MagicMock()
    client.messages = MagicMock()
    client.messages.create = AsyncMock(
        side_effect=[
            _mock_response_with_text(refusal_text),
            _mock_response_with_text(clean_text),
        ]
    )

    text, diagnostic = await call_with_refusal_guard(
        client,
        model="claude-sonnet-4-6",
        max_tokens=1000,
        system="You are a defence-industry analyst.",
        user_prompt="Summarize these stories: ...",
        section_name="defence_news",
    )

    assert text == clean_text
    assert diagnostic["refusal_detected"] is True
    assert diagnostic["retry_attempted"] is True
    assert diagnostic["section"] == "defence_news"
    # Two calls were made (initial + retry)
    assert client.messages.create.await_count == 2


@pytest.mark.asyncio
async def test_second_refusal_fallback():
    """Both calls refuse → return (None, diagnostic) with status='partial' marker."""
    from agents.juno_refusal_detector import call_with_refusal_guard

    first_refusal = "I cannot help with that request."
    second_refusal = "As an AI, I am not able to provide this analysis."

    client = MagicMock()
    client.messages = MagicMock()
    client.messages.create = AsyncMock(
        side_effect=[
            _mock_response_with_text(first_refusal),
            _mock_response_with_text(second_refusal),
        ]
    )

    text, diagnostic = await call_with_refusal_guard(
        client,
        model="claude-sonnet-4-6",
        max_tokens=1000,
        system="You are a defence-industry analyst.",
        user_prompt="Summarize these stories: ...",
        section_name="defence_news",
    )

    assert text is None  # signals caller to write SECTION_UNAVAILABLE_COPY
    assert diagnostic["refusal_detected"] is True
    assert diagnostic["retry_attempted"] is True
    assert diagnostic["section"] == "defence_news"
    # Diagnostic carries the second-attempt excerpt for agent_runs.notes
    assert "second_attempt_excerpt" in diagnostic
    assert diagnostic["second_attempt_excerpt"].startswith(second_refusal[:50])
    assert client.messages.create.await_count == 2


@pytest.mark.asyncio
async def test_first_call_success_no_retry():
    """When the first call returns clean text, no retry is attempted."""
    from agents.juno_refusal_detector import call_with_refusal_guard

    clean_text = (
        "### 🛡️ Defence News\n"
        "- SIPRI annual review released (SIPRI)\n"
        "- RUSI commentary on NATO 2% (RUSI)"
    )

    client = MagicMock()
    client.messages = MagicMock()
    client.messages.create = AsyncMock(
        return_value=_mock_response_with_text(clean_text)
    )

    text, diagnostic = await call_with_refusal_guard(
        client,
        model="claude-sonnet-4-6",
        max_tokens=1000,
        system="You are a defence-industry analyst.",
        user_prompt="Summarize: ...",
        section_name="defence_news",
    )

    assert text == clean_text
    assert diagnostic["refusal_detected"] is False
    assert diagnostic.get("retry_attempted", False) is False
    assert client.messages.create.await_count == 1
