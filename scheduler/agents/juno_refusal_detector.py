"""Juno Sonnet refusal-detector + retry-with-framing-nudge wrapper.

CONTEXT D-11 — 7 substring patterns covering ~95% of Anthropic content-policy
refusals per the Anthropic-Pentagon dispute corpus. Retry once with a framing
nudge; on second refusal, return None so caller writes section-unavailable
copy with status='partial'.

Pattern verification audit (RESEARCH §Example 2):
- Anthropic-Pentagon dispute timeline (Feb-Apr 2026) — public statements use "we cannot provide" framing
- Anthropic API docs content-policy examples — "I cannot help with" / "I'm unable to provide" / "this goes against my guidelines"
- Community reports (Reddit r/ClaudeAI, Anthropic Discord) — "as an AI" / "against my values" / "cannot assist with"
"""
from __future__ import annotations

import logging
import re
from typing import Any

from anthropic import AsyncAnthropic

logger = logging.getLogger(__name__)

# CONTEXT D-11 — 7 substring patterns. Compiled at module load (not per-call).
REFUSAL_PATTERN = re.compile(
    r"(I cannot|as an AI|safety guidelines|unable to provide|"
    r"I'm not able to|cannot assist|against my)",
    re.IGNORECASE,
)

# Framing nudge appended to user prompt on first refusal (D-11 retry-once)
FRAMING_NUDGE = (
    "\n\nAnalyze the following stories as defence-industry market commentary, "
    "not tactical or operational intelligence. Focus on contract values, "
    "vendor names, policy implications, and market signals — explicitly NOT "
    "on force posture, capability gaps, or military operations."
)

SECTION_UNAVAILABLE_COPY = (
    "Section unavailable — defence-industry summary could not be "
    "generated for this fire. See agent_runs.notes for diagnostic."
)


def is_refusal(text: str | None) -> bool:
    """Return True if text matches any of the 7 refusal patterns.

    Heuristic: first 500 chars catches the refusal preamble; full-text
    scan would catch in-bullet mentions like '(the analyst cannot...)' as
    false positives.
    """
    if not text:
        return False
    return bool(REFUSAL_PATTERN.search(text[:500]))


async def call_with_refusal_guard(
    client: AsyncAnthropic,
    *,
    model: str,
    max_tokens: int,
    system: str,
    user_prompt: str,
    section_name: str,
) -> tuple[str | None, dict[str, Any]]:
    """Call Sonnet with refusal-detection + retry-once.

    Returns (text_or_None, diagnostic_dict). diagnostic_dict carries
    refusal_detected/first_attempt_excerpt/retry_attempted/second_attempt_excerpt
    fields for agent_runs.notes per CONTEXT D-11.
    """
    diagnostic: dict[str, Any] = {
        "refusal_detected": False,
        "section": section_name,
        "first_attempt_excerpt": None,
        "retry_attempted": False,
    }
    # First attempt
    try:
        resp = await client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = resp.content[0].text.strip()
    except Exception as exc:  # noqa: BLE001 — fail-closed
        logger.exception(
            "juno_refusal_guard: first attempt raised on section=%s", section_name
        )
        diagnostic["first_attempt_excerpt"] = (
            f"EXCEPTION: {type(exc).__name__}: {str(exc)[:100]}"
        )
        return (None, diagnostic)

    if not is_refusal(text):
        return (text, diagnostic)

    # First-attempt refusal — capture excerpt + retry with framing nudge
    diagnostic["refusal_detected"] = True
    diagnostic["first_attempt_excerpt"] = text[:100]
    diagnostic["retry_attempted"] = True
    logger.warning(
        "juno_refusal_guard: section=%s refused on first attempt; "
        "retrying with framing nudge",
        section_name,
    )

    try:
        resp2 = await client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user_prompt + FRAMING_NUDGE}],
        )
        text2 = resp2.content[0].text.strip()
    except Exception as exc:  # noqa: BLE001 — fail-closed
        logger.exception(
            "juno_refusal_guard: retry raised on section=%s", section_name
        )
        diagnostic["second_attempt_excerpt"] = f"EXCEPTION: {type(exc).__name__}"
        return (None, diagnostic)

    if is_refusal(text2):
        logger.warning(
            "juno_refusal_guard: section=%s refused on retry; "
            "falling back to status=partial",
            section_name,
        )
        diagnostic["second_attempt_excerpt"] = text2[:100]
        return (None, diagnostic)

    return (text2, diagnostic)
