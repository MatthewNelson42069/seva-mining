"""Quotes sub-agent — self-contained drafter.

Part of the 7-agent split (quick-260421-eoe). Filters
``content_agent.fetch_stories()`` to the quote predicted_format and drafts
pull-quote style posts: quote + attribution + 1-2 lines of analyst context,
plus the paste-ready ``image_prompt`` for the operator's claude.ai render.
Writes a ContentBundle with ``content_type="quote"``.
"""
from __future__ import annotations

import json
import logging

from anthropic import AsyncAnthropic

from agents.brand_preamble import BRAND_PREAMBLE
from agents.content import run_text_story_cycle
from services.market_snapshot import render_snapshot_block

logger = logging.getLogger(__name__)

CONTENT_TYPE: str = "quote"
AGENT_NAME: str = "sub_quotes"


async def _draft(
    story: dict,
    deep_research: dict,
    market_snapshot: dict | None,
    *,
    client: AsyncAnthropic,
) -> dict | None:
    """Draft a quote ContentBundle payload via Claude Sonnet."""
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
        "Opening rule: Lead with the quote itself. "
        "Differentiation: Every draft must surface ONE non-obvious insight not in the original article — "
        "a pattern, implication, or comparison no one else made. "
        "You never mention Seva Mining. You never give financial advice. "
        "Produce a QUOTE draft: quote in quotation marks, attribution, 1-2 lines of analyst context, "
        "plus the visual-render prompt fields (suggested_headline, data_facts, image_prompt_direction) "
        "the operator will paste into claude.ai to render the pull-quote card."
    )
    user_prompt = f"""Based on the following research, produce a QUOTE post for X (Twitter).

## Story
Headline: {story.get('title', '')}
Source: {story.get('source_name', '')} ({story.get('link', '')})

## Full Article
{article_block}

## Corroborating Sources
{corr_lines}

## Instructions
1. Find a verbatim, attributed statement from a credible named figure
   (bank analyst, central bank official, WGC, IMF, Fed speaker, etc.)
   in the article content. The story is chosen only when such a quote stands on its own.
2. Draft the pull-quote post (quote + attribution + 1-2 lines analyst context) and
   the claude.ai render fields.
3. Provide a brief rationale for the format choice (1-2 sentences).

Respond in valid JSON with this structure:
{{
  "format": "quote",
  "rationale": "...",
  "key_data_points": ["...", "..."],
  "draft_content": {{
    "format": "quote",
    "speaker": "Full Name",
    "speaker_title": "title/credentials",
    "quote_text": "\\"the exact quote in quotation marks\\"",
    "source_url": "{story.get('link', '')}",
    "twitter_post": "quote + attribution + 1-2 lines analyst context for X",
    "suggested_headline": "short editorial title for the artifact, ideally <=60 chars",
    "data_facts": ["1-5 key facts or data points that contextualize this quote — each <=120 chars"],
    "image_prompt_direction": "2-4 sentences describing what the pull-quote card should look like: how to present the quote as hero element, attribution placement, any context stats to feature. Focus on STORY-SPECIFIC visual direction only — brand palette and dimensions are applied automatically."
  }}
}}"""

    try:
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
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
        logger.error("quotes._draft JSON parse failed: %s", exc)
        return None

    draft_content = parsed.get("draft_content", {}) or {}
    draft_content.setdefault("format", "quote")

    # Build paste-ready image_prompt — parity with pre-split _draft_quote_post.
    direction = str(draft_content.pop("image_prompt_direction", "")).strip()
    facts = draft_content.get("data_facts") or []
    if not isinstance(facts, list):
        facts = []
    draft_content["data_facts"] = facts[:5]
    headline = draft_content.get("suggested_headline", "")
    facts_block = "\n".join(f"- {f}" for f in draft_content["data_facts"])
    draft_content["image_prompt"] = (
        f"{BRAND_PREAMBLE}\n\n"
        f"ARTIFACT TYPE: pull-quote card (NOT a chart — center the quote itself as the hero element).\n\n"
        f"HEADLINE FOR THIS VISUAL:\n{headline}\n\n"
        f"KEY FACTS TO FEATURE:\n{facts_block}\n\n"
        f"STORY-SPECIFIC DIRECTION:\n{direction}"
    )

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
