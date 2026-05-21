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

# Wave 1 (10-02-PLAN.md) flipped this file GREEN by replacing the Phase 9
# STUB DEFENCE_NEWS_SYSTEM_PROMPT with the production Janes/CSIS-voice prompt.

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


# ---------------------------------------------------------------------------
# Phase 15 Plan 15-02 (JSWEEP-04) — JUNO_SWEEPER_SYSTEM_PROMPT tests.
#
# These tests pin the contracts of the NEW dedicated Juno sweeper system
# prompt (D-04). The existing 7 tests above for DEFENCE_NEWS_SYSTEM_PROMPT
# (Phase 10) remain byte-identical-protected per D-10.
#
# Critical contract: the FORBID anti-tactical clause bytes MUST appear
# verbatim in BOTH DEFENCE_NEWS_SYSTEM_PROMPT AND JUNO_SWEEPER_SYSTEM_PROMPT
# (string-equality contract per D-04 — load-bearing for Anthropic
# content-policy compliance per RESEARCH §4 Anthropic-Pentagon dispute).
# ---------------------------------------------------------------------------

# Verbatim bytes of the FORBID anti-tactical clause from
# scheduler/companies/juno/prompts.py:21-22 (Phase 10 DEFENCE_NEWS_SYSTEM_PROMPT).
# Re-stated here as a literal string so test_sweeper_prompt_contains_anti_tactical_clause_verbatim
# can assert it appears as a substring in BOTH prompts (D-04 contract).
ANTI_TACTICAL_CLAUSE_VERBATIM = (
    "FORBID — anti-tactical framing clause:\n"
    "You produce market/industry commentary on the defence sector. "
    "You do NOT produce operational, tactical, targeting, force posture, "
    "order of battle (OOB), capability gap, or troop movement analysis. "
    "If a source story crosses into operational territory, summarize the "
    "market/industry implications only and explicitly note the operational "
    "details were excluded."
)


def _sweeper_prompt() -> str:
    from companies.juno.prompts import JUNO_SWEEPER_SYSTEM_PROMPT

    return JUNO_SWEEPER_SYSTEM_PROMPT


def test_sweeper_prompt_constant_exists():
    """D-04 — JUNO_SWEEPER_SYSTEM_PROMPT importable + non-trivial length."""
    prompt = _sweeper_prompt()
    assert isinstance(prompt, str)
    assert len(prompt) > 100, (
        f"JUNO_SWEEPER_SYSTEM_PROMPT length {len(prompt)} too short — "
        f"expected a multi-paragraph system prompt"
    )


def test_sweeper_prompt_contains_anti_tactical_clause_verbatim():
    """D-04 STRING-EQUALITY CONTRACT — the FORBID anti-tactical clause bytes
    MUST appear verbatim in BOTH DEFENCE_NEWS_SYSTEM_PROMPT AND
    JUNO_SWEEPER_SYSTEM_PROMPT. Load-bearing for Anthropic content-policy
    compliance per RESEARCH §4."""
    from companies.juno.prompts import (
        DEFENCE_NEWS_SYSTEM_PROMPT,
        JUNO_SWEEPER_SYSTEM_PROMPT,
    )
    assert ANTI_TACTICAL_CLAUSE_VERBATIM in DEFENCE_NEWS_SYSTEM_PROMPT, (
        "ANTI_TACTICAL_CLAUSE_VERBATIM not in DEFENCE_NEWS_SYSTEM_PROMPT — "
        "Phase 10 prompt drifted (D-10 violation)"
    )
    assert ANTI_TACTICAL_CLAUSE_VERBATIM in JUNO_SWEEPER_SYSTEM_PROMPT, (
        "ANTI_TACTICAL_CLAUSE_VERBATIM not in JUNO_SWEEPER_SYSTEM_PROMPT — "
        "D-04 string-equality contract violated"
    )


def test_sweeper_prompt_has_voice_anchor():
    """D-04 + RESEARCH §4 element 1 — Janes/CSIS desk voice anchor."""
    prompt = _sweeper_prompt()
    assert "Janes" in prompt, "Voice anchor missing 'Janes'"
    has_secondary_anchor = (
        "CSIS" in prompt
        or "IISS" in prompt
        or "Defense News editorial" in prompt
    )
    assert has_secondary_anchor, (
        "Voice anchor requires Janes + at least one of CSIS, IISS, or "
        "Defense News editorial per D-04"
    )


def test_sweeper_prompt_demands_exactly_3_angles():
    """D-04 + RESEARCH §4 element 3 — 'exactly 3 content angles' + 3 markers."""
    prompt = _sweeper_prompt()
    assert "exactly 3 content angles" in prompt
    assert "### Angle 1:" in prompt
    assert "### Angle 2:" in prompt
    assert "### Angle 3:" in prompt


def test_sweeper_prompt_connects_x_signal_with_news_signal():
    """D-04 — sweeper task connects an X signal with a news signal."""
    prompt = _sweeper_prompt()
    lowered = prompt.lower()
    assert "x signal" in lowered or "x (twitter) signal" in lowered, (
        "Sweeper prompt must mention 'X signal' or 'X (Twitter) signal'"
    )
    assert "news signal" in lowered, "Sweeper prompt must mention 'news signal'"


def test_sweeper_prompt_grounding_rule_anti_hallucination():
    """RESEARCH §4 element 3 — grounding rule + anti-hallucination clause
    (mirrors Seva weekly_sweeper.py:208)."""
    prompt = _sweeper_prompt()
    assert "Use ONLY facts" in prompt, (
        "Sweeper prompt missing 'Use ONLY facts' grounding rule"
    )
    assert "hallucinate" in prompt.lower(), (
        "Sweeper prompt missing anti-hallucination clause"
    )


def test_sweeper_prompt_excludes_equity_signals_on_defence_primes():
    """PROJECT.md anti-feature — defence-prime cashtags / equity signals
    explicitly listed in negative-space DO NOT."""
    prompt = _sweeper_prompt()
    assert "LMT" in prompt, (
        "Sweeper prompt negative-space list must cite LMT ticker per PROJECT.md "
        "anti-feature on defence-prime equity signals"
    )
    assert "RTX" in prompt, (
        "Sweeper prompt negative-space list must cite RTX ticker per PROJECT.md "
        "anti-feature on defence-prime equity signals"
    )


def test_sweeper_prompt_neutral_on_conflict_inverts_seva_bull_bias():
    """D-04 + RESEARCH §4 element 4 — defence prompt is NEUTRAL on conflict,
    must NOT clone Seva's gold-bull-thesis framing.

    Asserts:
      - 'neutral-on-conflict' or 'neutral on conflict' appears (case-insensitive)
      - 'bull thesis' does NOT appear (case-insensitive)
      - standalone 'gold' token does NOT appear (word-boundary regex)
    """
    import re

    prompt = _sweeper_prompt()
    lowered = prompt.lower()
    assert "neutral-on-conflict" in lowered or "neutral on conflict" in lowered, (
        "Sweeper prompt must explicitly state neutral-on-conflict stance "
        "(D-04 bias inversion vs Seva gold-bull-thesis)"
    )
    assert "bull thesis" not in lowered, (
        "Sweeper prompt must NOT contain 'bull thesis' — defence is neutral, "
        "not bull-biased (D-04)"
    )
    assert not re.search(r"\bgold\b", lowered), (
        "Sweeper prompt contains standalone 'gold' token — defence prompt "
        "must not clone the Seva gold-news prompt (D-04)"
    )
