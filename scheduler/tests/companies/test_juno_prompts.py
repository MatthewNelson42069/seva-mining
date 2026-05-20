"""Wave 0 RED tests for scheduler/companies/juno/prompts.py (DEF-03).

Phase 9 ships a STUB DEFENCE_NEWS_SYSTEM_PROMPT placeholder. Wave 1
(10-02-PLAN.md) replaces it with the real Janes/CSIS-voice prompt + the
anti-tactical clause + 3 section markers. Wave 1's final task removes the
module-level skip below to turn this file GREEN.

Contracts asserted (verbatim from 10-CONTEXT.md §D-01, §D-02 + RESEARCH
§Pattern 2):
- Anti-tactical clause substring: "market/industry commentary on the defence sector"
- 7 forbidden tactical keywords in the FORBID paragraph (verbatim D-02)
- 3 section markers: "🛡️ Defence News", "🇨🇦 Canadian Procurement",
  "🌐 World Events Relevant to Defence"
- Voice anchor: Janes + (CSIS | IISS | Defense News editorial)
- Bullet rule: vendor names + contract values
- NOT a stub (no "STUB" substring)
- NO gold-prompt language ("bull", "bull thesis", "gold")
"""
from __future__ import annotations

import os
import sys

import pytest

# Wave 1 (10-02-PLAN.md) removes this skip line to turn the module GREEN.
pytest.skip(
    "Wave 0 RED — production DEFENCE_NEWS_SYSTEM_PROMPT lands in Wave 1 "
    "(10-02-PLAN.md). Remove this skip line in that wave's task to turn "
    "tests GREEN.",
    allow_module_level=True,
)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _prompt() -> str:
    from companies.juno.prompts import DEFENCE_NEWS_SYSTEM_PROMPT

    return DEFENCE_NEWS_SYSTEM_PROMPT


def test_prompt_has_anti_tactical_clause():
    """D-02 verbatim — anti-tactical framing clause must be present."""
    prompt = _prompt()
    assert "market/industry commentary on the defence sector" in prompt


@pytest.mark.parametrize(
    "forbidden_keyword",
    [
        "force posture",
        "order of battle",
        "OOB",
        "troop movement",
        "capability gap",
        "targeting",
        "operational",
    ],
)
def test_prompt_has_forbid_keywords(forbidden_keyword):
    """Each of the 7 D-02 anti-tactical keywords must appear in the prompt."""
    prompt = _prompt()
    assert forbidden_keyword in prompt, (
        f"Anti-tactical FORBID keyword {forbidden_keyword!r} missing from "
        f"DEFENCE_NEWS_SYSTEM_PROMPT"
    )


def test_prompt_has_three_section_markers():
    """RESEARCH §Pattern 2 — prompt enumerates the 3 section headings."""
    prompt = _prompt()
    assert "### 🛡️ Defence News" in prompt
    assert "### 🇨🇦 Canadian Procurement" in prompt
    assert "### 🌐 World Events Relevant to Defence" in prompt


def test_prompt_voice_anchor():
    """D-01 voice anchor — Janes + at least one of CSIS/IISS/Defense News editorial."""
    prompt = _prompt()
    assert "Janes" in prompt
    has_secondary_anchor = (
        "CSIS" in prompt
        or "IISS" in prompt
        or "Defense News editorial" in prompt
    )
    assert has_secondary_anchor, (
        "Voice anchor requires Janes + at least one of CSIS, IISS, or "
        "Defense News editorial per D-01"
    )


def test_prompt_bullet_rule():
    """RESEARCH §Pattern 2 element 4 — bullet rule references vendors + contract values."""
    prompt = _prompt()
    assert "vendor" in prompt
    assert "contract value" in prompt


def test_prompt_not_stub():
    """Wave 1 must replace the Phase 9 STUB placeholder."""
    prompt = _prompt()
    assert "STUB" not in prompt, (
        "DEFENCE_NEWS_SYSTEM_PROMPT still contains 'STUB' — Wave 1 must "
        "replace the Phase 9 placeholder with the real prompt"
    )


def test_prompt_no_gold_bull_language():
    """D-01 — defence prompt MUST NOT clone gold prompt (no bull/gold language)."""
    prompt = _prompt()
    # Case-insensitive scan; tolerates 'bullet' which contains 'bull'.
    lowered = prompt.lower()
    # We forbid 'bull thesis' (gold-specific) but allow 'bullet'.
    assert "bull thesis" not in lowered
    assert "bull/bear" not in lowered
    # 'gold' as a sector reference is forbidden (defence != gold).
    # Tolerate 'gold-standard' / 'goldenrod' etc. by requiring the standalone word.
    import re

    # Word-boundary match on 'gold' as a standalone token
    assert not re.search(r"\bgold\b", lowered), (
        "DEFENCE_NEWS_SYSTEM_PROMPT contains standalone 'gold' token — "
        "defence prompt must not clone the Seva gold-news prompt (D-01)"
    )
