"""Juno World Events relevance classifier — Phase 10 DEF-06.

Haiku 4.5 + Anthropic structured outputs via messages.parse(). Returns a
Pydantic-validated DefenceRelevance per story. Sub-second per call, ~$1-2/mo
at projected volume.

Per D-05: Haiku 4.5 + Anthropic structured outputs (current GA syntax —
client.messages.parse(output_format=PydanticModel); the deprecated beta
parameter name from earlier SDK versions is intentionally NOT used here).

Per D-06: 9 inclusion categories (active_conflict, alignment_shifts,
spending_policy, sanctions_export, energy_critmin, semiconductors, space,
hypersonic_ai_auto, treaty_events) + not_relevant exclusion.

Per D-07: only items with is_relevant=True AND confidence >= 0.7 AND
category != 'not_relevant' flow to Sonnet synthesis.
"""
from __future__ import annotations

import logging
from typing import Literal

from anthropic import AsyncAnthropic
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

HAIKU_MODEL = "claude-haiku-4-5"
HAIKU_MAX_TOKENS = 400
HAIKU_TIMEOUT_S = 30.0
CONFIDENCE_THRESHOLD = 0.7  # CONTEXT D-07


class DefenceRelevance(BaseModel):
    """One world-events item classified for defence relevance.

    9 inclusion categories per CONTEXT D-06. is_relevant=True AND
    confidence >= 0.7 items flow to Sonnet synthesis; below-threshold items
    are logged to agent_runs.notes for operator review (not surfaced).
    """

    is_relevant: bool = Field(description="True if defence-industry-relevant")
    category: Literal[
        "active_conflict",      # Ukraine, Gaza, Taiwan Strait, Yemen, Korea, Iran
        "alignment_shifts",     # NATO accession, BRICS, AUKUS-style deals
        "spending_policy",      # defence budgets, NATO 2%, SIPRI annual
        "sanctions_export",     # semiconductor export bans, denial lists
        "energy_critmin",       # lithium, cobalt, REE, LNG-defence links
        "semiconductors",       # CHIPS act, fabs, EUV controls
        "space",                # Starlink-defence, sat-intel, ASAT, launch contracts
        "hypersonic_ai_auto",   # DARPA, JADC2, autonomous systems, AI export
        "treaty_events",        # New START, INF, conventional arms control
        "not_relevant",
    ]
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = Field(max_length=200, description="One-sentence justification")


RELEVANCE_SYSTEM_PROMPT = """\
You classify general world-news items for relevance to the defence industry.

A story is defence-industry-relevant if it falls into one of 9 categories:
- active_conflict: Ukraine, Gaza, Taiwan Strait, Yemen, Korea, Iran developments
- alignment_shifts: NATO accession, BRICS expansion, AUKUS-style deals, basing
- spending_policy: defence budget bills, NATO 2% commitments, SIPRI reports
- sanctions_export: semiconductor export bans, denial lists, ITAR/EAR actions
- energy_critmin: lithium, cobalt, REE, LNG-vs-defence-supply-chain links
- semiconductors: CHIPS Act, fab news, EUV controls, advanced-node access
- space: Starlink-defence, satellite intelligence, ASAT, commercial launch contracts
- hypersonic_ai_auto: DARPA, JADC2, autonomous-systems contracts, AI export controls
- treaty_events: New START, INF, conventional-arms-control, non-proliferation

EXCLUDE (return is_relevant=false, category=not_relevant):
- Consumer device launches (phones, tablets) unless manufacturer announces defence contract
- General AI/LLM releases (GPT, Claude, Gemini) unless announcement specifically targets defence/intelligence
- Cryptocurrency price moves and exchange news
- Sports, entertainment, celebrity news under any framing
- Pure climate/weather news unless tied to military operations or basing

Return confidence as a float in [0.0, 1.0]. Use >=0.85 for strong signal, 0.7-0.85
for moderate signal, <0.7 for borderline. The downstream pipeline filters at 0.7.
Reasoning: one sentence, <= 200 chars.
"""


async def classify_story(
    client: AsyncAnthropic,
    *,
    title: str,
    snippet: str,
) -> DefenceRelevance | None:
    """Run the Haiku classifier on one story. Returns None on hard failure.

    Fail-closed: on exception, log + return None. Caller treats None as
    is_relevant=False (drop the story) rather than retrying.
    """
    user_message = (
        f"Title: {title}\n\n"
        f"Snippet: {snippet[:1500]}\n\n"
        f"Classify this story for defence-industry relevance."
    )
    try:
        response = await client.messages.parse(
            model=HAIKU_MODEL,
            max_tokens=HAIKU_MAX_TOKENS,
            system=RELEVANCE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
            output_format=DefenceRelevance,
        )
        return response.parsed_output
    except Exception as exc:  # noqa: BLE001 — fail-closed
        logger.warning(
            "juno_relevance: classify_story failed on '%s' (%s)",
            (title or "")[:60],
            type(exc).__name__,
        )
        return None


def survives_threshold(result: DefenceRelevance | None) -> bool:
    """CONTEXT D-07 — is_relevant=True AND confidence >= 0.7 AND category != 'not_relevant'."""
    return (
        result is not None
        and result.is_relevant
        and result.confidence >= CONFIDENCE_THRESHOLD
        and result.category != "not_relevant"
    )
