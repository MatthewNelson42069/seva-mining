"""Long-form sub-agent — self-contained drafter.

Part of the 7-agent split (quick-260421-eoe). Filters
``content_agent.fetch_stories()`` to the long_form predicted_format and drafts
a single sustained X post (400-2200 chars) with a clear thesis and supporting
evidence. Writes a ContentBundle with ``content_type="long_form"``.

Enforces the 400-char minimum floor that ContentAgent._research_and_draft used
to enforce pre-split — drafts below 400 chars are dropped rather than persisted,
preserving functional parity.
"""
from __future__ import annotations

import json
import logging

from anthropic import AsyncAnthropic

from agents.content import run_text_story_cycle
from services.market_snapshot import render_snapshot_block

logger = logging.getLogger(__name__)

CONTENT_TYPE: str = "long_form"
AGENT_NAME: str = "sub_long_form"

MIN_LONG_FORM_CHARS = 400


async def _draft(
    story: dict,
    deep_research: dict,
    market_snapshot: dict | None,
    *,
    client: AsyncAnthropic,
) -> dict | None:
    """Draft a long_form ContentBundle payload via Claude Sonnet."""
    article_text = deep_research.get("article_text", "")
    corroborating = deep_research.get("corroborating_sources", [])

    if corroborating:
        corr_lines = "\n".join(
            f"- {s.get('title', '')} ({s.get('source', '')}) — {s.get('snippet', '')}"
            for s in corroborating
        )
    else:
        corr_lines = "None found."

    article_block = (
        article_text if article_text
        else "Article text unavailable — use corroborating sources and headline."
    )

    snapshot_block = render_snapshot_block(market_snapshot) if market_snapshot else ""
    system_prompt = (
        f"{snapshot_block}\n\n"
        "You are a senior gold market analyst. Authoritative, inside-the-room perspective. "
        "Tone: Precise + punchy. Data-forward. Every sentence earns its place. "
        "Opening rule: First line is always the most impactful data point or fact. Lead with the number. "
        "Differentiation: Every draft must surface ONE non-obvious insight not in the original article — "
        "a pattern, implication, or comparison no one else made. "
        "You never mention Seva Mining. You never give financial advice. You never use "
        'phrases like "buy", "sell", "invest in", "I recommend", or "you should". '
        "Produce a LONG_FORM draft: article-style analysis, single sustained piece built around "
        "one powerful argument or insight, like a short analyst op-ed with thesis + evidence + "
        "takeaway."
    )
    user_prompt = f"""Based on the following research, produce a LONG_FORM post for X (Twitter).

## Story
Headline: {story.get('title', '')}
Source: {story.get('source_name', '')} ({story.get('link', '')})

## Full Article
{article_block}

## Corroborating Sources
{corr_lines}

## Instructions
1. Extract 5-8 key data points from the research.
2. Draft a single sustained X post 400-2200 chars (HARD MINIMUM: 400 characters).
   If you cannot write at least 400 characters of article-quality analyst prose,
   respond with an empty post field rather than padding it.
3. Provide a brief rationale for the format choice (1-2 sentences).

Respond in valid JSON with this structure:
{{
  "format": "long_form",
  "rationale": "...",
  "key_data_points": ["...", "..."],
  "draft_content": {{
    "format": "long_form",
    "post": "single X post 400-2200 chars (minimum 400 required)"
  }}
}}"""

    try:
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```", 2)[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.rsplit("```", 1)[0].strip()
        parsed = json.loads(raw)
    except Exception as exc:
        logger.error("long_form._draft JSON parse failed: %s", exc)
        return None

    draft_content = parsed.get("draft_content", {}) or {}
    draft_content.setdefault("format", "long_form")

    # Hard minimum floor — parity with pre-split behavior.
    post_text = draft_content.get("post", "") or ""
    if len(post_text) < MIN_LONG_FORM_CHARS:
        logger.warning(
            "long_form._draft: skipping — post below %d char minimum (got %d): %s",
            MIN_LONG_FORM_CHARS, len(post_text), story.get("title", "")[:80],
        )
        return None

    draft_content["_rationale"] = parsed.get("rationale", "")
    draft_content["_key_data_points"] = parsed.get("key_data_points", [])
    return draft_content


async def run_draft_cycle() -> None:
    """Single-tick pipeline: fetch → filter → draft → review → write."""
    await run_text_story_cycle(
        agent_name=AGENT_NAME,
        content_type=CONTENT_TYPE,
        draft_fn=_draft,
    )
