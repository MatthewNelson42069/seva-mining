"""Breaking News sub-agent — self-contained drafter.

Part of the 7-agent split (quick-260421-eoe). Runs every hour on its own
APScheduler cron — clock-aligned at HH:00 UTC post-m49 (was IntervalTrigger
with start_date=now+10s, which fired on every Railway redeploy and produced
visible "every few minutes" cadence drift to the user during deploy churn;
quick-260427-m49 moved the trigger to CronTrigger(minute=0) which is restart-
immune). History: m9k introduced 1h → vxg reverted 1h→2h citing duplicate-
story churn → kqa restored 1h after user observed perceived ~30 min cadence
(actually Railway-restart-induced) → m49 made the cron clock-aligned to
eliminate the restart-trigger. Quality gate post-j5i+m49 at
BREAKING_NEWS_MIN_SCORE=6.0 (j5i shipped 6.5; m49 dropped to 6.0 after live
telemetry showed 69% floor rate exceeding j5i's own 70% drop-trigger
boundary) + max_count=3 + composite-score sort plus fetch_stories()'s 30-min
TTL cache keep duplicate-story churn bounded even at 1h cadence.

Filters ``content_agent.fetch_stories()`` to the breaking_news predicted_format
and drafts short, urgency-first tweets. Writes a ContentBundle row with
``content_type="breaking_news"`` in a single transaction after running
``content_agent.review()`` inline.
"""
from __future__ import annotations

import json
import logging

from anthropic import AsyncAnthropic

from agents.content import run_text_story_cycle
from services.market_snapshot import render_snapshot_block

logger = logging.getLogger(__name__)

CONTENT_TYPE: str = "breaking_news"
AGENT_NAME: str = "sub_breaking_news"

# quick-260424-j5i D2: composite-score floor for the "top-of-top" cut. Stories
# whose (relevance*0.4 + recency*0.3 + credibility*0.3)*10 score is below this
# value skip DraftItem creation (ContentBundle row is still persisted for
# forensics). Per-agent tunable — raise to tighten, lower to loosen.
# quick-260427-m49: dropped 6.5 → 6.0 after live DB telemetry showed a 69%
# floor rate over the last 24h (40 of 58 drafted stories floored across 10
# completed runs), exceeding j5i's own "drop to 6.0 if >70% floors" trigger
# at the boundary. j5i Q5 projected ~62% retention at 6.0 vs ~41% at 6.5;
# user observed empty queue so loosening the gate matters more right now
# than maintaining the highest-quality cut.
BREAKING_NEWS_MIN_SCORE: float = 6.0


async def _draft(
    story: dict,
    deep_research: dict,
    market_snapshot: dict | None,
    *,
    client: AsyncAnthropic,
) -> dict | None:
    """Draft a breaking_news ContentBundle payload via Claude Sonnet.

    Single-format version of the pre-split ``_research_and_draft`` — specialized
    to ONLY produce breaking_news format. Returns draft_content dict on success,
    None on JSON parse failure.
    """
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
        "This story has clear urgency (major price moves, major announcements, breaking developments) — "
        "produce a BREAKING_NEWS draft."
    )
    user_prompt = f"""Based on the following research, produce a BREAKING_NEWS post for X (Twitter).

## Story
Headline: {story.get('title', '')}
Source: {story.get('source_name', '')} ({story.get('link', '')})

## Full Article
{article_block}

## Corroborating Sources
{corr_lines}

## Instructions
1. Extract 5-8 key data points from the research.
2. Draft 1-3 punchy lines, ALL CAPS for key terms, no hashtags.
3. Provide a brief rationale for the format choice (1-2 sentences).

Respond in valid JSON with this structure:
{{
  "format": "breaking_news",
  "rationale": "...",
  "key_data_points": ["...", "..."],
  "draft_content": {{
    "format": "breaking_news",
    "tweet": "1-3 line breaking news tweet with ALL CAPS key terms, no hashtags",
    "infographic_brief": null
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
        logger.error("breaking_news._draft JSON parse failed: %s", exc)
        return None

    draft_content = parsed.get("draft_content", {}) or {}
    draft_content.setdefault("format", "breaking_news")
    draft_content["_rationale"] = parsed.get("rationale", "")
    draft_content["_key_data_points"] = parsed.get("key_data_points", [])
    return draft_content


async def run_draft_cycle() -> None:
    """Single-tick pipeline: fetch → filter → draft → review → write.

    quick-260424-j5i D1+D2: tighten selection to "top-of-top" — cap at
    max_count=3 successful persists per run, sort candidates by composite score
    (desc, recency tiebreaker) so the best stories win, and apply a
    BREAKING_NEWS_MIN_SCORE=6.5 floor so floored items persist a bundle but
    skip the DraftItem (silent firehose on quiet runs is preferred over
    forcing mediocre content into the top-N slots).
    """
    await run_text_story_cycle(
        agent_name=AGENT_NAME,
        content_type=CONTENT_TYPE,
        draft_fn=_draft,
        max_count=3,
        sort_by="score",
        min_score=BREAKING_NEWS_MIN_SCORE,
    )
