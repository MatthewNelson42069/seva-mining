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

# Tier-1 source patterns for reputable-quote filtering (quick-260421-mos).
# Matched case-insensitive as substrings against story["source_name"].
# Deliberate over-inclusion of aliases (e.g. "wall street journal" AND "wsj")
# to catch both canonical names and common shorthand returned by SerpAPI.
REPUTABLE_SOURCES: frozenset[str] = frozenset({
    # Tier-1 financial
    "reuters", "bloomberg", "wsj", "wall street journal",
    "financial times", "ft.com", "barron", "marketwatch",
    "cnbc", "economist", "financial post",
    # Gold-specialist
    "kitco", "mining.com", "mining journal", "mining weekly",
    "northern miner", "gold hub",
    # Institutional (WGC, IMF, BIS, central banks, ratings agencies)
    "world gold council", "wgc", "imf", "bis.org",
    "federal reserve", "european central bank",
    "bank of england", "bank of japan", "people's bank",
    "s&p global", "moody's",
})


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

## Quality bar — a quote is ONLY "solid" if ALL hold:
1. **Speaker credibility:** Named figure with a verifiable senior role —
   chief economist/strategist at a tier-1 bank, central bank official
   (Fed/ECB/BoE/BoJ/PBoC), World Gold Council staff, IMF/BIS official,
   head of research at a major gold firm, or a well-known commodity
   analyst with a public track record. REJECT: anonymous "strategist at X",
   "market watcher", retail commentators, forum posters, generic
   "analysts at [unnamed firm]".
2. **Substance:** Verbatim statement containing AT LEAST ONE of:
   - A specific price target or range (e.g. "$2,800 by Q3")
   - A specific percentage (move, probability, allocation)
   - A specific timeframe or catalyst ("if the Fed cuts in September...")
   - A contrarian or non-consensus view with clear reasoning
3. **Freshness:** Quote is from this article's reporting (not a weeks-old rehash).
4. **Clarity:** Quote is self-contained — a reader can understand the claim
   without reading the full article.

## If NO quote in this article meets the quality bar, respond with:
{{
  "reject": true,
  "rationale": "1-2 sentence explanation of which criterion failed"
}}

Otherwise, respond with the draft JSON as specified below.

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

    if parsed.get("reject") is True:
        logger.info(
            "quotes._draft: story rejected by quality gate — %s",
            parsed.get("rationale", "no rationale given"),
        )
        return None  # returning None triggers run_text_story_cycle stub-bundle path

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
    """Single-tick pipeline: fetch → filter → reputable-only → top-1 → draft (quality-gated) → review → write.

    Configured per quick-260423-d30:
    - max_count=1: produce the single best reputable-source quote per cycle (vxg)
    - source_whitelist=REPUTABLE_SOURCES: tier-1 financial + gold-specialist
      + institutional sources only (mos)
    - dedup_scope="same_type": allow reuse of stories already drafted by
      breaking_news / threads / long_form; dedup only against other quotes
      within the same day (d30). Mirrors the independence model already
      applied to sub_infographics (of3), sub_gold_media, and sub_gold_history.
    """
    await run_text_story_cycle(
        agent_name=AGENT_NAME,
        content_type=CONTENT_TYPE,
        draft_fn=_draft,
        max_count=1,
        source_whitelist=REPUTABLE_SOURCES,
        dedup_scope="same_type",
    )
