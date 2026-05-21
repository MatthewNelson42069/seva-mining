"""v2.0 daily_summary cron — Phase 1 / Phase 2 / Phase 3.

Fires at 08:00 PT and 12:00 PT (registered in worker.py via _make_daily_summary_job).
Writes one daily_summaries row + one agent_runs row per fire.

Pitfall mitigations bundled here:
  CRIT-3 (multiple fires from misfire) — DB-level idempotency check at start.
  HIGH-4 (JSONB schema drift)         — raw_sources_jsonb built from a fixed dict shape.
  HIGH-5 (WhatsApp >1600 chars)       — uses deliver_summary_teaser (teaser-only pattern).
  MOD-5 (hallucinated dates)          — published_at injected into Sonnet user prompt.
  MOD-6 (failure alert deadlock)      — deliver_summary_failure_alert wraps its send.
  SUM-04 (telemetry)                  — notes JSON dumped on the agent_runs row.
  SUM-05 (status assembly)            — completed/partial/failed mapped from per-section
                                        success counts.
  GOLD-01 (score >= 6.0, top 5)       — applied after fetch_stories.
  GOLD-02 (markdown structure)        — Sonnet prompt template enforces.
  GOLD-03 (empty-state)               — pulls price range from market_snapshot service.
  STAT-01..STAT-05                    — Phase 3 StatCan WDS direct vector poll.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import feedparser

from anthropic import AsyncAnthropic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import serpapi

from agents.content_agent import fetch_stories
from agents.ontario_law import fetch_ontario_law_hits
from anthropic_client import get_anthropic_client
from agents.ontario_stats import (
    fetch_ontario_stats_snapshot,
    format_error_markdown,
    format_fresh_markdown,
    format_no_new_data_markdown,
)
# v3.0 Phase 10 (DEF-04..07) — Juno defence news funnel imports. Module-level
# imports (rather than symbol-level) so test patches on
# `companies.juno.feeds.JUNO_DEFENCE_FEEDS` etc. take effect at call time.
from agents import juno_health_check as juno_hc
from agents.juno_refusal_detector import (
    call_with_refusal_guard,
    SECTION_UNAVAILABLE_COPY,
)
from agents.juno_relevance import (
    classify_story,
    survives_threshold,
    DefenceRelevance,
)
from companies.juno import feeds as juno_feeds
from companies.juno import serpapi as juno_serpapi_cfg
from companies.juno.prompts import DEFENCE_NEWS_SYSTEM_PROMPT
from config import get_settings
from database import AsyncSessionLocal
from models.agent_run import AgentRun
from models.daily_summary import DailySummary
# v3.0 Phase 9 (TENANT-03) — scheduler-side scoped helpers. The CI grep gate
# at scripts/verify-tenant-isolation.sh requires every multi-tenant select to
# route through this module; the prior raw select-of-DailySummary call sites
# below have been rewritten to use scoped_summaries('seva').
from queries.scoped import scoped_summaries
from services.market_snapshot import fetch_market_snapshot
from services.whatsapp import (
    deliver_summary_failure_alert,
    deliver_summary_teaser,
)

logger = logging.getLogger(__name__)

LA_TZ = ZoneInfo("America/Los_Angeles")
GOLD_SCORE_FLOOR = 6.0          # GOLD-01 — locked in research SUMMARY.md
GOLD_TOP_N = 20                 # quick-260518-fyq — bumped 12→20; analyst content was getting edged out on heavy M&A days (Equinox/Orla saturated 05-17 fires while Goldman gold-target story missed)
SONNET_MODEL = "claude-sonnet-4-6"  # locked — Sonnet for the WRITE call only
SONNET_MAX_TOKENS = 1500        # quick-260512-of1 — bumped from 800; bull-thesis brief is structurally larger
IDEMPOTENCY_WINDOW_MIN = 30     # CRIT-3 — see note below
# Originally specced to match misfire_grace_time (which was 1800s = 30 min).
# On 2026-05-21 misfire_grace_time was bumped to 14400s (4 hours) to recover
# from a deploy-cadence outage. IDEMPOTENCY_WINDOW_MIN intentionally STAYS
# at 30 minutes — bumping it to 240 would cause the 12:00 PT scheduled fire
# to skip itself when the 08:00 PT fire is exactly 4 hours older (within
# the new window), losing one of two daily summaries. Trade-off: in the
# narrow case where a delayed-catchup fire for 08:00 PT lands within 30 min
# of 12:00 PT, the 12:00 PT fire will skip (idempotency). That's acceptable —
# better one summary than zero. A future hardening could make the check
# period_label-aware so 08:00 PT and 12:00 PT fires never collide.

# v3.0 Phase 10 (DEF-04..07) — Juno synthesis token budget per section.
# Token math: 3 sections × ~1500 tokens × ~$3/M output = ~$0.01/fire ≈ $0.60/mo
# at 60 fires/month (08:05 + 12:05 PT each day). Inside the ~$30-50/mo Anthropic
# budget per CLAUDE.md.
JUNO_SONNET_MODEL = "claude-sonnet-4-6"
JUNO_SONNET_MAX_DEFENCE = 1500     # 7-bullet Defence News output (raised from 1000 per CONTEXT)
JUNO_SONNET_MAX_PROCUREMENT = 1000
JUNO_SONNET_MAX_WORLD = 1500
JUNO_SONNET_TIMEOUT = 60.0         # Phase 7 D-11 baseline

# World Events RSS feeds — generic world news passes through Haiku classifier
# filter (CONTEXT D-08). Distinct from JUNO_DEFENCE_FEEDS — only items at
# confidence >= 0.7 AND is_relevant=True flow to Sonnet synthesis.
# Phase-0 verification may have flagged some endpoints; runtime per-feed
# health-check (DEF-04) downgrades to status='partial' if 3+ flag in one fire.
JUNO_WORLD_EVENTS_FEEDS: list[tuple[str, str]] = [
    (
        "reuters_world",
        "https://www.reutersagency.com/feed/?best-topics=world&post_type=best",
    ),
    ("ap_world", "https://feeds.apnews.com/rss/apf-worldnews"),
    ("bbc_world", "https://feeds.bbci.co.uk/news/world/rss.xml"),
]
# Cap classifier calls per fire — bounds cost and latency. 100 entries × Haiku
# 4.5 (~$0.50/M input + $2.50/M output) × 400-token responses ≈ $0.10/fire =
# $6/mo at 60 fires/month.
JUNO_WORLD_EVENTS_CLASSIFIER_CAP = 100

# GOLD-02 prompt template — quick-260512-of1 refactored from "1-3 headline-grouped
# stories" to a curated bull-thesis brief with 4 labeled sub-sections (Top Gold
# Headlines, Top Macro Headlines, Analyst & Bank Predictions, Macro Economic
# Stats) plus an optional Bearish Risk section. Every story surfaced must
# advance the thesis "gold price goes higher" — see user verbatim feedback in
# .planning/quick/260512-of1-refine-gold-news-section-into-bull-thesi/. Live
# macro stat indicators (10Y real yield, DXY, CPI, gold/silver ratio) will ship
# in v2.1; for v2.0 the Macro Economic Stats sub-section surfaces any hard
# numerical macro data already embedded in the supplied story summaries.
GOLD_NEWS_SYSTEM_PROMPT = """\
You are the writer for a daily gold-sector intelligence brief. The reader is a gold-sector operator producing social-media content for a gold-focused audience. Every story you surface must answer the question: "Does this point to a higher gold price?"

Stories that DO NOT advance the bull thesis for gold should be excluded. This is a curated bull-thesis brief, not balanced market commentary. You may briefly note bearish risks ONLY when macro data genuinely contradicts the bull case (see Bearish Risk section below).

**Bullet rule (applies to all sections):** Every bullet must explicitly tie the fact back to the gold bull case. State the fact, then make the connection — e.g., "Fed paused rate hikes" + "real yields drop, gold's inflation-hedge thesis strengthens". Descriptive bullets ("X happened") without the gold connection should be rewritten or dropped.

**Tier-1 analyst/bank promotion rule (MANDATORY):** If any supplied story names one of these analysts or institutions AND makes a specific gold price target, allocation recommendation, or named catalyst narrative — that story MUST go into the **Analyst & Bank Predictions** section. Do NOT bucket it under Top Gold Headlines or Top Macro Headlines, even if it would also fit there. This is the highest-leverage content type for the reader and must be surfaced consistently.

Tier-1 list (any of these triggers the promotion rule):
- People: Pierre Lassonde, Peter Schiff, Egon von Greyerz, Matthew Piepenburg, Frank Giustra, John Hathaway, Rick Rule, Mike Maloney, Jeffrey Gundlach (when on gold)
- Banks: Goldman Sachs, JPMorgan, Bank of America, UBS, Morgan Stanley, Citigroup, Deutsche Bank (when issuing a gold target or thesis)
- Authorities: World Gold Council (WGC), IMF (when on gold), BIS (when on gold)

Example: a Bloomberg story headlined "Goldman says central banks to step up gold buying, aiding prices" is a Goldman-named call with a catalyst (central-bank demand) and an outcome (aiding prices) — it goes to the **Analyst & Bank Predictions** section as a single entry like "**Goldman Sachs — central-bank gold buying to step up, aiding prices** / [2-3 bullets unpacking the mechanism]". It does NOT go under Top Macro Headlines.

Output MUST be markdown in this exact structure (no preamble, no postamble):

### 🟡 Top Gold Headlines

Direct gold-sector news that supports higher gold prices: central bank gold buying, gold-price moves, major producer news, M&A, exploration results from credible miners, supply constraints, large ETF inflows.

Format: 1-3 grouped headlines. Each headline is **bold** on its own line. Underneath, 2-4 bullets explaining why this is bullish for gold. Each bullet ≤ 35 words, ends with `(Source Name)`.

### 🌐 Top Macro Headlines (Why It Matters for Gold)

Macro stories that support higher gold prices: rising inflation, dovish Fed, USD weakness, real-yield compression, geopolitical risk, debt-crisis warnings, banking-system stress, sovereign-debt concerns.

Format: 1-2 grouped headlines. Each headline is **bold** on its own line, followed by a 1-sentence "why this points to higher gold" framing. Then 2-3 bullets unpacking the mechanism. Each bullet ≤ 35 words, ends with `(Source Name)`.

### 🎯 Analyst & Bank Predictions

Specific named-analyst or named-bank calls on gold: price targets, catalyst narratives, allocation recommendations. Prioritize: Pierre Lassonde, Peter Schiff, Egon von Greyerz, Matthew Piepenburg, Frank Giustra, John Hathaway, Rick Rule, Mike Maloney, Goldman Sachs, JPMorgan, Bank of America, UBS, World Gold Council. Specific price targets ($X target for gold) and named catalysts are highest-signal.

Format: 1-3 entries. Each formatted as **{Name/Bank} — {target or thesis headline}** on its own line, then 2-3 bullets unpacking their reasoning, catalysts, and timeframe. Each bullet ≤ 35 words, ends with `(Source Name)`. If NO analyst/bank call appears in today's candidates, write the single line: "No major analyst or bank calls today." (no bullets).

### 📊 Macro Economic Stats

*Live indicators (10Y real yield, DXY, Fed funds rate, CPI, gold/silver ratio) ship in v2.1. For now, surface any hard numerical macro data points already embedded in the supplied stories — e.g., "April CPI: 3.2% y/y", "10Y yield: 4.5%". Each as a single line in this format: `**{indicator}:** {value} ({direction-vs-prior}) — {gold implication in ≤ 12 words}`. Max 3-5 lines. If no embedded numerical macro data is available, write the single line: "No fresh macro data today." (no bullets).*

### ⚠️ Bearish Risk to Watch

Include this section ONLY when one or more supplied stories presents a clear bearish-for-gold catalyst (e.g., hawkish Fed surprise, real-yield spike, dollar strength, gold technical breakdown, ETF outflows). Format: single italicized sentence acknowledging the risk. If no such risk surfaced today, OMIT this section entirely.

---

Rules across all sub-sections:
- Use markdown headings (###) for sub-sections — do NOT skip them.
- Each story bullet ends with `(Source Name)` citation — match the source the story came from.
- Use ONLY dates explicitly stated in the supplied articles. Do not infer, estimate, or use training knowledge for dates. If a story has no date, write "recently" rather than inventing one.
- Do NOT emit tables. Do NOT emit blockquotes (except the italicized Bearish Risk line).
- Do NOT pad. If a sub-section has nothing worth showing, write its empty-state line and move on.
- Bias toward specific people, specific numbers, specific catalysts. "Sentiment improved" is weak. "Lassonde says $17,250 gold from $40T US debt crisis" is strong.

### Example bullets (use these as a model)

* **Top Gold Headlines example:** Spot gold surged 3.6% on May 6, topping $4,700 — confirms safe-haven bid as Iran-deal hopes briefly cooled then reignited the geopolitical risk premium that supports gold. (mining.com)
* **Top Macro Headlines example:** US April CPI rose driven by gas, rent, and food costs — sticky inflation keeps real yields suppressed and undermines Fed rate-cut optimism, supports gold's inflation-hedge thesis. (Bloomberg)
* **Analyst & Bank Predictions example:** Lassonde points to $40T US debt as the catalyst — debasement risk plus political unwillingness to allow real fiscal pain drives gold's monetary premium higher. (Kitco)
"""

# GOLD-03 empty-state copy (locked CONTEXT decision):
EMPTY_STATE_TEMPLATE_WITH_RANGE = "No major moves in gold today — prices ranging ${low}–${high}."
EMPTY_STATE_FALLBACK = "No major moves in gold today."

def _derive_period_label(now_la: datetime) -> str:
    """Return '08:00 PT' or '12:00 PT' from a datetime in America/Los_Angeles.

    Robust to misfire_grace_time skew: any hour < 11 maps to '08:00 PT'.
    """
    return "08:00 PT" if now_la.hour < 11 else "12:00 PT"


def _is_juno_morning_fire(now_la: datetime) -> bool:
    """Return True for the 08:05 PT Juno fire.

    Post-CLEANUP-01 (Phase 11, 2026-05-19): SerpAPI no longer gates on
    morning-only — both 08:05 PT and 12:05 PT fires execute the 7
    Canadian-procurement SerpAPI queries. This helper is retained because
    `agent_runs.notes.is_morning_fire` is still useful diagnostic data
    (lets dashboards distinguish the two daily fires) and the value is
    passed through to `_build_juno_canadian_procurement_section` for
    telemetry-only purposes.

    Implemented as a module-level function so tests can monkeypatch it
    when they need to assert period-label behaviour.
    """
    return now_la.hour < 10


async def _idempotency_skip(session: AsyncSession, now_utc: datetime) -> bool:
    """CRIT-3 / SUM-03 — return True if a recent Seva run already wrote a row.

    v3.0 Phase 9 (TENANT-03): tenant-scoped to 'seva' via scoped_summaries.
    This keeps the existing Seva-only behaviour byte-equivalent — when Juno
    fires its own daily_summary at hour="8,12", minute=5, the per-company
    idempotency check inside run_juno_daily_summary uses scoped_summaries('juno')
    independently.
    """
    cutoff = now_utc - timedelta(minutes=IDEMPOTENCY_WINDOW_MIN)
    # Wrap the scoped Select to add the recency + status filters. The
    # `with_only_columns(DailySummary.id)` keeps the original column-select
    # optimization (avoid hydrating the whole row just to test existence).
    stmt = (
        scoped_summaries("seva")
        .with_only_columns(DailySummary.id)
        .where(DailySummary.generated_at >= cutoff)
        .where(DailySummary.status.in_(["running", "completed"]))
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None


async def _build_gold_news_section(
    anthropic_client: AsyncAnthropic,
) -> tuple[str | None, list[dict], dict[str, int]]:
    """GOLD-01/02/03. Returns (markdown_or_None, raw_stories_for_jsonb, counts).

    Returns (None, [], counts) on hard failure so the caller marks the section as failed.
    Returns (empty_state_md, [], counts) when no stories clear the score floor.

    quick-260507-drw — added 4 telemetry counters in `counts`:
      - rss: pre-filter count of stories tagged `_source_type='rss'`
      - serpapi: pre-filter count of stories tagged `_source_type='serpapi'`
      - total: total candidates returned by fetch_stories (post-dedup)
      - after_floor: count of stories that cleared the >= 6.0 score floor
    These nest into agent_runs.notes JSONB so the operator can see at a glance
    if SerpAPI is contributing zero stories (likely missing API key).
    """
    counts: dict[str, object] = {
        "rss": 0, "serpapi": 0, "total": 0, "after_floor": 0,
        "last_error": None,  # quick-260514-jny: captures exception text for agent_runs.errors
    }
    try:
        stories = await fetch_stories()
    except Exception as exc:
        logger.exception("daily_summary: fetch_stories raised — gold section failed")
        counts["last_error"] = f"fetch_stories: {type(exc).__name__}: {exc}"
        return (None, [], counts)

    # quick-260507-drw — break down by ingestion path BEFORE any filtering.
    counts["total"] = len(stories)
    counts["rss"] = sum(1 for s in stories if s.get("_source_type") == "rss")
    counts["serpapi"] = sum(1 for s in stories if s.get("_source_type") == "serpapi")

    if not stories:
        return (await _gold_empty_state(), [], counts)

    # GOLD-01 — score floor + top N
    relevant = [s for s in stories if (s.get("score") or 0) >= GOLD_SCORE_FLOOR]
    counts["after_floor"] = len(relevant)
    top = sorted(relevant, key=lambda s: s.get("score") or 0, reverse=True)[:GOLD_TOP_N]

    if not top:
        return (await _gold_empty_state(), [], counts)

    # Build raw_sources entry for JSONB (HIGH-4 shape) BEFORE the Sonnet
    # try/except. quick-260508-dj5: this MUST happen up front so the failure
    # path returns JSON-serializable data — datetime objects in s["published"]
    # would otherwise crash the daily_summaries INSERT with
    # "TypeError: Object of type datetime is not JSON serializable" (this is
    # what crashed the 2026-05-08 08:00 PT fire when Sonnet timed out).
    raw = [
        {
            "title": s.get("title", ""),
            "link": s.get("link", ""),
            "source_name": s.get("source_name", ""),
            "score": float(s.get("score") or 0.0),
            "published_at": (
                s.get("published").isoformat()
                if hasattr(s.get("published"), "isoformat")
                else str(s.get("published") or "")
            ) or None,
        }
        for s in top
    ]

    # MOD-5 grounding: published_at is in each story dict already.
    # Build the user prompt with explicit per-story context.
    user_prompt_parts = ["Top gold-sector stories from the last 24 hours:\n"]
    for i, s in enumerate(top, start=1):
        user_prompt_parts.append(
            f"\n[Story {i}]\n"
            f"Title: {s.get('title', '')}\n"
            f"Source: {s.get('source_name', 'unknown')}\n"
            f"Published: {s.get('published', 'unknown')}\n"
            f"Summary: {s.get('summary', '')[:500]}\n"
        )
    user_prompt = "".join(user_prompt_parts)

    try:
        response = await anthropic_client.messages.create(
            model=SONNET_MODEL,
            max_tokens=SONNET_MAX_TOKENS,
            system=GOLD_NEWS_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        md = response.content[0].text.strip()
    except Exception as exc:
        # quick-260514-jny: capture exception text into counts so it lands in
        # agent_runs.errors via run_daily_summary. logger.exception still writes
        # the full traceback to Railway logs; counts["last_error"] gives DB-level
        # visibility without log access. Format: "{stage}: {ExceptionType}: {message}"
        logger.exception("daily_summary: Sonnet write call raised")
        counts["last_error"] = f"sonnet_write: {type(exc).__name__}: {exc}"
        return (None, raw, counts)  # quick-260508-dj5: return JSON-safe raw, not top

    return (md, raw, counts)


async def _gold_empty_state() -> str:
    """GOLD-03 — render the empty state with price range when available."""
    try:
        snap = await fetch_market_snapshot()
        # market_snapshot returns dict; gold low/high may be in different keys
        # depending on its current shape. Defensive lookup with fallback:
        gold_low = snap.get("gold_low") or snap.get("gold_24h_low")
        gold_high = snap.get("gold_high") or snap.get("gold_24h_high")
        if gold_low and gold_high:
            return EMPTY_STATE_TEMPLATE_WITH_RANGE.format(
                low=f"{float(gold_low):,.0f}",
                high=f"{float(gold_high):,.0f}",
            )
    except Exception:
        logger.warning("market_snapshot lookup failed for empty-state — using fallback")
    return EMPTY_STATE_FALLBACK


async def _build_ontario_law_section(
    *,
    anthropic_client: AsyncAnthropic,
    serpapi_client: "serpapi.Client | None",
    model: str,
    previous_last_known_law: dict | None,
) -> tuple[str | None, list[dict], dict | None, dict[str, int]]:
    """Phase 2 — real ingestion + Haiku filter + last_known_law continuity.

    Returns (markdown, hits_for_jsonb, new_last_known_law, counts):
      markdown: str on success (may be empty-state copy), None on hard failure
      hits_for_jsonb: list[dict] for raw_sources_jsonb.ontario_law.hits
      new_last_known_law: dict for raw_sources_jsonb.ontario_law.last_known_law
                          (propagated from previous if no fresh hits)
      counts: telemetry — keys serpapi/nrcan/after_dedup/after_filter

    Signature note: this function now requires kwargs. The caller (run_daily_summary)
    constructs the serpapi_client + reads previous_last_known_law from the most
    recent daily_summaries row before invoking.
    """
    counts: dict[str, object] = {
        "serpapi": 0, "nrcan": 0, "after_dedup": 0, "after_filter": 0,
        "last_error": None,  # quick-260514-jny: captures exception text for agent_runs.errors
    }
    try:
        survivors, fetched_counts = await fetch_ontario_law_hits(
            serpapi_client=serpapi_client,
            anthropic_client=anthropic_client,
            model=model,
        )
        # Merge fetched counts in (preserve last_error key)
        counts.update(fetched_counts)
        counts.setdefault("last_error", None)
    except Exception as exc:
        logger.exception("ontario_law: fetch_ontario_law_hits raised — section failed")
        counts["last_error"] = f"fetch_ontario_law_hits: {type(exc).__name__}: {exc}"
        return (None, [], previous_last_known_law, counts)

    if survivors:
        # Render bullets per CONTEXT.md D-Bullet: * **{bill_or_reg_number}** — {reason}
        bullets = "\n".join(
            f"* **{h.bill_or_reg_number}** — {h.reason or 'no summary available'}"
            for h in survivors
        )
        # Update last_known_law from the highest-priority (first) survivor
        first = survivors[0]
        new_lkl: dict | None = {
            "date": datetime.now(timezone.utc).date().isoformat(),
            "law_name": first.bill_or_reg_number or (first.title[:80] if first.title else "Unknown"),
            "url": first.link,
        }
        hits_jsonb = [h.model_dump(mode="json") for h in survivors]
        return (bullets, hits_jsonb, new_lkl, counts)

    # Empty state — propagate previous last_known_law if any (LAW-04 continuity)
    if previous_last_known_law:
        lkl_date = previous_last_known_law.get("date", "")
        lkl_name = previous_last_known_law.get("law_name", "")
        md = (
            f"No new Ontario mining-related laws today. "
            f"Last update: {lkl_date} — {lkl_name}."
        )
        return (md, [], previous_last_known_law, counts)

    return ("No new Ontario mining-related laws today.", [], None, counts)


async def _build_ontario_stats_section(
    *,
    previous_snapshot: "dict | None",
    previous_release_time: "str | None",
    agent_run_id: str,
) -> "tuple[str | None, dict, dict]":
    """Phase 3 — real StatCan WDS ingestion (replaces Phase 1 stub).

    Returns (markdown, ontario_stats_jsonb, telemetry_dict):
      markdown: str on fresh/no_new_data/error branches; None only on hard unexpected exception
      ontario_stats_jsonb: {snapshot, last_state, last_error_text} for raw_sources
      telemetry_dict: keys candidates_stats_state, candidates_stats_period,
                      candidates_stats_release_time
    """
    telemetry: dict = {
        "candidates_stats_state": "error",  # default; overwritten on success
        "candidates_stats_period": None,
        "candidates_stats_release_time": None,
    }

    try:
        result = await fetch_ontario_stats_snapshot(
            previous_release_time=previous_release_time
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("ontario_stats: fetch raised unexpectedly")
        err_str = f"{type(exc).__name__}: {str(exc)[:120]}"
        md = format_error_markdown(err_str, agent_run_id)
        jsonb = {
            "snapshot": previous_snapshot,  # preserve last good
            "last_state": "error",
            "last_error_text": f"{type(exc).__name__}: {str(exc)[:200]}",
        }
        telemetry["candidates_stats_state"] = "error"
        return (md, jsonb, telemetry)

    telemetry["candidates_stats_state"] = result.state

    if result.state == "fresh":
        md = format_fresh_markdown(result)
        new_snapshot = {
            "period": result.period,
            "figure_kg": result.figure_kg,
            "release_time": result.release_time,
            "prior_period": result.prior_period,
            "prior_figure_kg": result.prior_figure_kg,
        }
        telemetry["candidates_stats_period"] = result.period
        telemetry["candidates_stats_release_time"] = result.release_time
        jsonb = {"snapshot": new_snapshot, "last_state": "fresh", "last_error_text": None}
        return (md, jsonb, telemetry)

    if result.state == "no_new_data":
        md = format_no_new_data_markdown(previous_snapshot)
        if previous_snapshot:
            telemetry["candidates_stats_period"] = previous_snapshot.get("period")
            telemetry["candidates_stats_release_time"] = previous_snapshot.get("release_time")
        jsonb = {
            "snapshot": previous_snapshot,
            "last_state": "no_new_data",
            "last_error_text": None,
        }
        return (md, jsonb, telemetry)

    # state == "error" (returned, not raised)
    md = format_error_markdown(result.error_text or "unknown", agent_run_id)
    jsonb = {
        "snapshot": previous_snapshot,  # do NOT overwrite — preserve last good
        "last_state": "error",
        "last_error_text": result.error_text,
    }
    return (md, jsonb, telemetry)


def _extract_lead(gold_news_md: str | None) -> str:
    """Pull the 1-sentence lead from gold-news markdown for the WhatsApp teaser.

    The Sonnet prompt structure (GOLD_NEWS_SYSTEM_PROMPT) puts the lead on the
    first non-empty line. We trim and return up to ~250 chars defensively.
    """
    if not gold_news_md:
        return "No major moves in gold today."
    for line in gold_news_md.split("\n"):
        stripped = line.strip()
        if stripped and not stripped.startswith("*"):
            return stripped[:250]
    return "Daily summary available."


async def run_daily_summary() -> None:
    """Entry point. Called from worker.py via _make_daily_summary_job + with_advisory_lock.

    Steps:
      1. Resolve period_label from current LA time.
      2. CRIT-3 idempotency check — skip if a row already exists in window.
      3. Insert agent_runs row (status='running').
      4. Build 3 sections (1 real + 2 stubs in Phase 1).
      5. Compose status (completed | partial | failed).
      6. Insert daily_summaries row with raw_sources_jsonb shaped to HIGH-4 contract.
      7. Send WhatsApp teaser via deliver_summary_teaser (gated by env).
      8. Update agent_runs row (status, ended_at, structured notes per SUM-04).
      On unhandled exception: log, mark agent_run failed, send failure alert
      (failure alert is isolated in deliver_summary_failure_alert per MOD-6).
    """
    now_utc = datetime.now(timezone.utc)
    now_la = now_utc.astimezone(LA_TZ)
    period_label = _derive_period_label(now_la)

    async with AsyncSessionLocal() as session:
        # CRIT-3 / SUM-03 — bail BEFORE any side effects if a recent row exists.
        if await _idempotency_skip(session, now_utc):
            logger.info(
                "daily_summary idempotency_skip period=%s — recent row exists in %dmin window",
                period_label, IDEMPOTENCY_WINDOW_MIN,
            )
            return

    # Insert agent_runs row first (status='running'). reconcile_stale_runs
    # will sweep this row back to 'failed' if the worker is hard-killed.
    agent_run = AgentRun(
        agent_name="daily_summary",
        started_at=now_utc,
        items_found=0,
        items_queued=0,
        items_filtered=0,
        status="running",
    )
    async with AsyncSessionLocal() as session:
        session.add(agent_run)
        await session.commit()
        await session.refresh(agent_run)

    agent_run_id_str = str(agent_run.id)
    sections_completed: list[str] = []
    sections_failed: list[str] = []
    gold_news_md: str | None = None
    ontario_law_md: str | None = None
    ontario_stats_md: str | None = None
    gold_raw: list[dict] = []
    ontario_law_hits: list[dict] = []
    new_last_known_law: dict | None = None
    candidates_gold = 0
    # Phase 2: initialize law_counts defensively so the finally block always has it
    law_counts: dict[str, int] = {
        "serpapi": 0, "nrcan": 0, "after_dedup": 0, "after_filter": 0
    }
    # Phase 3: initialize stats telemetry + JSONB defensively
    stats_telemetry: dict = {
        "candidates_stats_state": None,
        "candidates_stats_period": None,
        "candidates_stats_release_time": None,
    }
    stats_jsonb: dict = {"snapshot": None, "last_state": None, "last_error_text": None}
    whatsapp_sent = False
    run_status = "failed"
    error_text: str | None = None

    settings = get_settings()
    # quick-260514-ii6: bumped from 30s → 60s. The bull-thesis prompt (of1/oxr)
    # tripled the gold section's effective compute: 12 candidates × ~3 KB each
    # in the user prompt + 1500-token output target + 4-sub-section structural
    # ask. The 30s ceiling caused the 2026-05-14 12:00 PT fire to fall back to
    # status=partial when Sonnet's WRITE call hit timeout. 60s gives headroom
    # for heavy-news days without being reckless (cron is daily, so 2-min wall
    # time is still well under any misfire concern).
    # v3.1 Phase 12 — Seva Sonnet routes through per-tenant resolver (D-07, D-09).
    anthropic_client = get_anthropic_client("seva", timeout=60.0)

    # Construct SerpAPI client if credentials are available (mirrors content_agent pattern)
    serpapi_client: "serpapi.Client | None" = (
        serpapi.Client(api_key=settings.serpapi_api_key)
        if settings.serpapi_api_key
        else None
    )

    # Read previous summary's raw_sources_jsonb for LAW-04 continuity + Phase 3 stats snapshot.
    # Single SELECT combines both reads — no second query needed.
    previous_last_known_law: dict | None = None
    previous_stats_snapshot: dict | None = None
    previous_stats_release_time: str | None = None
    try:
        async with AsyncSessionLocal() as session:
            # v3.0 Phase 9 (TENANT-03): route through scoped_summaries('seva')
            # so the previous-summary read for LAW-04 continuity + Phase 3 stats
            # snapshot is tenant-scoped. The CI grep gate at
            # scripts/verify-tenant-isolation.sh blocks raw select-of-DailySummary.
            stmt = (
                scoped_summaries("seva")
                .with_only_columns(DailySummary.raw_sources_jsonb)
                .order_by(DailySummary.generated_at.desc())
                .limit(1)
            )
            result = await session.execute(stmt)
            prev_jsonb = result.scalar_one_or_none()
            if prev_jsonb and isinstance(prev_jsonb, dict):
                prev_law = (prev_jsonb.get("ontario_law") or {}).get("last_known_law")
                if prev_law:
                    previous_last_known_law = prev_law
                prev_stats = prev_jsonb.get("ontario_stats") or {}
                prev_snap = prev_stats.get("snapshot")
                if prev_snap and isinstance(prev_snap, dict):
                    previous_stats_snapshot = prev_snap
                    previous_stats_release_time = prev_snap.get("release_time")
    except Exception:
        logger.warning(
            "previous-summary read failed — proceeding with no continuity"
        )

    # quick-260507-drw — gold-section telemetry counts (rss/serpapi/total/after_floor)
    gold_counts: dict[str, int] = {"rss": 0, "serpapi": 0, "total": 0, "after_floor": 0}

    try:
        # --- Section 1: Gold News (real) ---
        gold_news_md, gold_raw, gold_counts = await _build_gold_news_section(anthropic_client)
        candidates_gold = len(gold_raw)
        if gold_news_md is not None:
            sections_completed.append("gold_news")
        else:
            sections_failed.append("gold_news")

        # --- Section 2: Ontario Law (Phase 2 — real ingestion + Haiku filter) ---
        ontario_law_md, ontario_law_hits, new_last_known_law, law_counts = (
            await _build_ontario_law_section(
                anthropic_client=anthropic_client,
                serpapi_client=serpapi_client,
                model=settings.ontario_law_filter_model,
                previous_last_known_law=previous_last_known_law,
            )
        )
        if ontario_law_md is not None:
            sections_completed.append("ontario_law")
        else:
            sections_failed.append("ontario_law")

        # --- Section 3: Ontario Stats (Phase 3 — real StatCan WDS ingestion) ---
        ontario_stats_md, stats_jsonb, stats_telemetry = (
            await _build_ontario_stats_section(
                previous_snapshot=previous_stats_snapshot,
                previous_release_time=previous_stats_release_time,
                agent_run_id=agent_run_id_str,
            )
        )
        if ontario_stats_md is not None:
            sections_completed.append("ontario_stats")
        else:
            sections_failed.append("ontario_stats")

        # SUM-05 status mapping
        failed_count = len(sections_failed)
        if failed_count == 0:
            run_status = "completed"
        elif failed_count < 3:
            run_status = "partial"
        else:
            run_status = "failed"

        # HIGH-4 — raw_sources_jsonb shape locked. DO NOT add fields here without
        # bumping the RawSources Pydantic model in backend/app/schemas/daily_summary.py.
        raw_sources = {
            "gold_news": gold_raw,
            "ontario_law": {
                "hits": ontario_law_hits,
                "last_known_law": new_last_known_law,
            },
            "ontario_stats": stats_jsonb,  # Phase 3: {snapshot, last_state, last_error_text}
        }

        # Persist daily_summaries row.
        async with AsyncSessionLocal() as session:
            summary_row = DailySummary(
                # v3.0 Phase 9 (TENANT-01) — explicit Seva tenant on every write.
                # server_default='seva' would cover the omission too, but
                # being explicit makes the per-company contract grep-able.
                company_id="seva",
                generated_at=now_utc,
                period_label=period_label,
                gold_news_md=gold_news_md,
                ontario_law_md=ontario_law_md,
                ontario_stats_md=ontario_stats_md,
                raw_sources_jsonb=raw_sources,
                status=run_status,
                error_text=None,
                agent_run_id=agent_run.id,
            )
            session.add(summary_row)
            await session.commit()

        # WHA-01 — send teaser via Plan 03 helper (env-gated; logs on simulate).
        if run_status in ("completed", "partial") and gold_news_md:
            try:
                sid = await deliver_summary_teaser(
                    period_label, _extract_lead(gold_news_md),
                )
                whatsapp_sent = sid is not None
            except Exception:
                logger.exception("daily_summary teaser send raised — continuing")

    except Exception as run_exc:  # noqa: BLE001
        logger.exception("daily_summary run failed: %s", run_exc)
        error_text = f"{type(run_exc).__name__}: {str(run_exc)[:500]}"
        run_status = "failed"
        # Best-effort summary row write so the failure is observable in the feed.
        try:
            async with AsyncSessionLocal() as session:
                failure_row = DailySummary(
                    # v3.0 Phase 9 (TENANT-01) — explicit Seva tenant.
                    company_id="seva",
                    generated_at=now_utc,
                    period_label=period_label,
                    gold_news_md=None,
                    ontario_law_md=None,
                    ontario_stats_md=None,
                    raw_sources_jsonb={
                        "gold_news": [],
                        "ontario_law": {"hits": [], "last_known_law": None},
                        "ontario_stats": {
                            "snapshot": None,
                            "last_state": "error",
                            "last_error_text": error_text,
                        },
                    },
                    status="failed",
                    error_text=error_text,
                    agent_run_id=agent_run.id,
                )
                session.add(failure_row)
                await session.commit()
        except Exception:
            logger.exception("daily_summary failure-row write ALSO failed")
        # MOD-6 — failure alert is isolated inside deliver_summary_failure_alert.
        await deliver_summary_failure_alert(
            period_label,
            sections_failed if sections_failed else ["all"],
            agent_run_id_str,
        )

    finally:
        # Telemetry write (SUM-04). Never raise out of this finally.
        try:
            notes_payload = {
                "candidates_gold": candidates_gold,
                # quick-260507-drw — raw-count telemetry per ingestion path
                "candidates_gold_rss": gold_counts.get("rss", 0),
                "candidates_gold_serpapi": gold_counts.get("serpapi", 0),
                "candidates_gold_total": gold_counts.get("total", 0),
                "candidates_gold_after_floor": gold_counts.get("after_floor", 0),
                "candidates_law": law_counts.get("after_filter", 0),  # Phase 2: real count
                "candidates_law_serpapi": law_counts.get("serpapi", 0),
                "candidates_law_nrcan": law_counts.get("nrcan", 0),
                "candidates_law_after_dedup": law_counts.get("after_dedup", 0),
                "candidates_law_after_filter": law_counts.get("after_filter", 0),
                "candidates_stats": 0,  # legacy scalar — kept for backward compat
                "candidates_stats_state": stats_telemetry.get("candidates_stats_state"),
                "candidates_stats_period": stats_telemetry.get("candidates_stats_period"),
                "candidates_stats_release_time": stats_telemetry.get("candidates_stats_release_time"),
                "sections_completed": sections_completed,
                "sections_failed": sections_failed,
                "whatsapp_sent": whatsapp_sent,
            }
            # quick-260514-jny — collect per-section errors so failures land in
            # agent_runs.errors (not just Railway logs). Format: list of
            # "{section}: {ExceptionType}: {message}" strings.
            per_section_errors: list[str] = []
            gold_err = gold_counts.get("last_error") if isinstance(gold_counts, dict) else None
            if gold_err:
                per_section_errors.append(f"gold_news: {gold_err}")
            law_err = law_counts.get("last_error") if isinstance(law_counts, dict) else None
            if law_err:
                per_section_errors.append(f"ontario_law: {law_err}")
            stats_err = (
                stats_jsonb.get("last_error_text")
                if isinstance(stats_jsonb, dict) else None
            )
            if stats_err:
                per_section_errors.append(f"ontario_stats: {stats_err}")

            async with AsyncSessionLocal() as session:
                fresh = await session.get(AgentRun, agent_run.id)
                if fresh is not None:
                    fresh.status = run_status
                    fresh.ended_at = datetime.now(timezone.utc)
                    fresh.items_found = candidates_gold
                    fresh.items_queued = len(sections_completed)
                    fresh.items_filtered = len(sections_failed)
                    fresh.notes = json.dumps(notes_payload)
                    # Combine top-level run error (if any) with per-section errors
                    combined_errors = [
                        e for e in ([error_text] + per_section_errors) if e
                    ]
                    if combined_errors:
                        fresh.errors = combined_errors
                    await session.commit()
        except Exception:
            logger.exception("daily_summary agent_runs telemetry update failed")


async def _fetch_7day_avg_for_feed(
    session: AsyncSession, source_name: str
) -> float:
    """Query agent_runs.notes JSONB for last 7-day avg entry count.

    CONTEXT D-12 — recent-history threshold helper. Reads
    `defence_feed_entry_counts` (preferred) OR `feed_entry_counts` (graceful
    fallback per research) from each `agent_runs.notes` row for
    `juno_daily_summary` runs in the last 7 days with status in
    ('completed', 'partial').

    Returns 0.0 when no history is available (treats as no-history baseline;
    `flag_feed()` still applies the bozo/empty rules independently).
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    try:
        stmt = (
            select(AgentRun.notes)
            .where(AgentRun.agent_name == "juno_daily_summary")
            .where(AgentRun.started_at >= cutoff)
            .where(AgentRun.status.in_(["completed", "partial"]))
        )
        result = await session.execute(stmt)
        rows = result.scalars().all()
    except Exception as exc:  # noqa: BLE001 — fail-closed, no history is fine
        logger.warning(
            "juno: _fetch_7day_avg_for_feed query raised (%s); treating as no-history",
            type(exc).__name__,
        )
        return 0.0

    counts: list[int] = []
    try:
        iterable = list(rows)
    except TypeError:
        return 0.0
    for notes_raw in iterable:
        if notes_raw is None:
            continue
        try:
            notes = (
                json.loads(notes_raw)
                if isinstance(notes_raw, str)
                else notes_raw
            )
            if not isinstance(notes, dict):
                continue
            fec = (
                notes.get("defence_feed_entry_counts")
                or notes.get("feed_entry_counts")
                or {}
            )
            if isinstance(fec, dict) and source_name in fec:
                counts.append(int(fec[source_name]))
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
    return sum(counts) / len(counts) if counts else 0.0


async def _run_juno_health_check(
    session: AsyncSession,
    feeds: list[tuple[str, str]],
) -> tuple[list[dict], dict[str, int], list[str]]:
    """Per-feed bozo + recent-history health-check per CONTEXT D-12.

    Returns:
      all_entries: flat list of entry dicts (source-tagged)
      feed_entry_counts: dict {source_name: int}
      flagged_feeds: list of source_names that failed bozo OR empty OR
        <30% of 7d avg

    Status decision (per D-12) is made by caller via
    `juno_hc.derive_run_status(...)`:
      - all_entries == [] → 'failed' (triggers WHA-03)
      - len(flagged) >= 3 → 'partial'
      - else → 'completed'
    """
    loop = asyncio.get_event_loop()
    feed_entry_counts: dict[str, int] = {}
    flagged_feeds: list[str] = []
    all_entries: list[dict] = []

    for source_name, feed_url in feeds:
        try:
            feed = await loop.run_in_executor(None, feedparser.parse, feed_url)
        except Exception as exc:  # noqa: BLE001 — fail-closed per-feed
            logger.warning(
                "juno: feedparser raised on %s (%s) — flagging",
                source_name,
                type(exc).__name__,
            )
            flagged_feeds.append(source_name)
            feed_entry_counts[source_name] = 0
            continue

        entries = list(getattr(feed, "entries", []) or [])
        n_entries = len(entries)
        feed_entry_counts[source_name] = n_entries

        avg_7d = await _fetch_7day_avg_for_feed(session, source_name)
        flagged = juno_hc.flag_feed(
            source_name=source_name, feed=feed, history_avg=avg_7d
        )
        if flagged:
            flagged_feeds.append(source_name)
            if n_entries == 0:
                # Empty or bozo-error → skip entry collection.
                continue
            # n_entries > 0 but history-low — still ingest (informational flag).

        for entry in entries:
            all_entries.append({
                "source_name": source_name,
                "title": str(getattr(entry, "title", ""))[:500],
                "summary": str(getattr(entry, "summary", ""))[:1500],
                "link": str(getattr(entry, "link", "")),
                "published": str(getattr(entry, "published", "")),
            })
    return all_entries, feed_entry_counts, flagged_feeds


async def _build_juno_defence_news_section(
    client: AsyncAnthropic,
    entries: list[dict],
) -> tuple[str | None, dict, list[dict]]:
    """Call Sonnet 4.6 for the Defence News section.

    Returns (markdown_or_None, diagnostic, persisted_entries). On refusal:
    markdown=None, diagnostic carries refusal flags. Caller writes
    SECTION_UNAVAILABLE_COPY as the fallback.

    v3.1 Phase 15 D-03a: persisted_entries is the post-health-check filtered
    entries list (capped at 30 to mirror the prompt-input cap) which the
    orchestrator writes into raw_sources_jsonb['defence_news'] so that the
    Phase 15 Sunday sweeper's virality compute substrate read returns the
    real story URLs (not just diagnostic counts). See
    .planning/phases/15-juno-weekly-viral-sweeper/15-RESEARCH.md §3.
    """
    bullets = "\n\n".join(
        f"- **{e.get('source_name','?')}**: {e.get('title','')}\n  "
        f"{(e.get('summary','') or '')[:500]}"
        for e in entries[:30]  # cap input to bound token count
    )
    user_prompt = (
        "Synthesize the following defence-industry stories into a Defence News "
        "section. Output 3-7 bullets in markdown, each ending with "
        "`(Source Name)` attribution. Use the section header "
        f"`### 🛡️ Defence News`.\n\n{bullets or '(no stories ingested this fire)'}"
    )
    text, diagnostic = await call_with_refusal_guard(
        client,
        model=JUNO_SONNET_MODEL,
        max_tokens=JUNO_SONNET_MAX_DEFENCE,
        system=DEFENCE_NEWS_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        section_name="defence_news",
    )
    # v3.1 Phase 15 D-03a — persist story entries (cap mirrors bullets[:30]).
    return (text, diagnostic, list(entries[:30]))


async def _build_juno_canadian_procurement_section(
    client: AsyncAnthropic,
    serpapi_client: "serpapi.Client | None",
    is_morning_fire: bool,
) -> tuple[str | None, dict, int, list[dict]]:
    """Call SerpAPI for Canadian procurement queries + Sonnet 4.6
    synthesis with refusal-guard. Runs on BOTH daily fires (08:05 PT +
    12:05 PT) per CLEANUP-01 — operator preference is a full 3-section
    brief twice daily; budget delta ~$3/mo (210 → ~420 SerpAPI calls/mo,
    inside the $50/mo SerpAPI cap with ~$41 headroom).

    `is_morning_fire` is retained on the signature for telemetry
    (`agent_runs.notes.is_morning_fire`) but no longer gates execution.

    Returns (markdown_or_None, diagnostic, serpapi_count, persisted_entries).

    v3.1 Phase 15 D-03a: persisted_entries normalizes the SerpAPI `flat`
    hits to the same entry-dict shape used by the defence/world sections so
    the sweeper's virality compute can treat all three substrates uniformly.
    Capped at 20 to bound raw_sources_jsonb size (mirrors bullets[:20] cap).
    """
    if serpapi_client is None:
        return ("", {"skipped_reason": "no_serpapi_client"}, 0, [])

    queries = list(getattr(juno_serpapi_cfg, "JUNO_SERPAPI_QUERIES", []) or [])
    loop = asyncio.get_event_loop()

    async def _one_query(q: str) -> list[dict]:
        def _call() -> object:
            return serpapi_client.search({
                "engine": "google_news",
                "q": q,
                "tbs": "qdr:d",  # last 24h (matches Ontario Law pattern)
                "num": 10,
            })
        try:
            results = await loop.run_in_executor(None, _call)
        except Exception as exc:  # noqa: BLE001 — per-query fail-closed
            logger.warning(
                "juno_serpapi: query '%s' failed (%s)",
                q,
                type(exc).__name__,
            )
            return []
        try:
            hits = results.get("news_results") if hasattr(results, "get") else None
        except Exception:  # noqa: BLE001
            hits = None
        if not isinstance(hits, list):
            return []
        return hits

    try:
        all_hits = await asyncio.gather(*[_one_query(q) for q in queries])
    except Exception as exc:  # noqa: BLE001
        logger.warning("juno_serpapi: gather raised (%s)", type(exc).__name__)
        all_hits = []
    flat = [item for batch in all_hits for item in batch]
    serpapi_count = len(queries)

    # Synthesize even when SerpAPI returned no hits — Sonnet writes a
    # "no signal today" Canadian Procurement section. This keeps the section
    # shape consistent (always 1+ bullets via Sonnet) and lets the
    # refusal-detector wrap a real call instead of writing a hard-coded
    # empty-state.
    bullets = "\n\n".join(
        f"- {h.get('title','')}\n  "
        f"{(h.get('snippet','') or '')[:300]} "
        f"({(h.get('source') or {}).get('name','SerpAPI')})"
        for h in flat[:20]
    )
    bullets_or_empty = bullets or (
        "(no SerpAPI hits this fire — write a 1-bullet no-signal-today section)."
    )
    user_prompt = (
        "Synthesize the following Canadian defence procurement signals into a "
        "Canadian Procurement section. Output 3-5 bullets in markdown, each "
        "ending with `(Source Name)` attribution. Extract contract values "
        "where present. Use the section header "
        "`### 🇨🇦 Canadian Procurement`.\n\n"
        f"{bullets_or_empty}"
    )
    text, diagnostic = await call_with_refusal_guard(
        client,
        model=JUNO_SONNET_MODEL,
        max_tokens=JUNO_SONNET_MAX_PROCUREMENT,
        system=DEFENCE_NEWS_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        section_name="canadian_procurement",
    )
    diagnostic["serpapi_hit_count"] = len(flat)
    # v3.1 Phase 15 D-03a — normalize SerpAPI hits to the standard entry-dict
    # shape so the sweeper's virality compute (Plan 15-05) can union the
    # three substrate sub-arrays uniformly. Cap at 20 (mirrors bullets[:20]).
    procurement_entries: list[dict] = [
        {
            "source_name": (h.get("source") or {}).get("name", "SerpAPI"),
            "title": h.get("title", ""),
            "summary": (h.get("snippet", "") or "")[:1500],
            "link": h.get("link", ""),
            "published": h.get("date", ""),
        }
        for h in flat[:20]
    ]
    return (text, diagnostic, serpapi_count, procurement_entries)


async def _build_juno_world_events_section(
    client: AsyncAnthropic,
    session: AsyncSession,
) -> tuple[str | None, dict, list[dict]]:
    """Ingest world-events RSS → Haiku classifier filter → Sonnet 4.6.

    Returns (markdown_or_None, diagnostic, persisted_entries). diagnostic
    carries:
      - world_events_total_seen
      - world_events_survived (confidence >= 0.7 AND is_relevant AND
        category != not_relevant)
      - world_events_categories: dict of category → count
      - refusal_detected / first_attempt_excerpt (from call_with_refusal_guard)

    v3.1 Phase 15 D-03a: persisted_entries normalizes the post-classifier
    `survived` list to the same entry-dict shape used by the defence/
    procurement sections (with extra `category` + `confidence` fields
    retained from the classifier output). The orchestrator writes this into
    raw_sources_jsonb['world_events'] for the sweeper's virality compute.
    Capped at 25 to mirror the bullets[:25] prompt-input cap.
    """
    all_entries, _ec, _ff = await _run_juno_health_check(
        session, JUNO_WORLD_EVENTS_FEEDS
    )
    if not all_entries:
        return (
            "",
            {
                "reason": "no_world_events_ingested",
                "world_events_total_seen": 0,
                "world_events_survived": 0,
                "world_events_categories": {},
                "haiku_validation_errors": [],
            },
            [],
        )

    survived: list[tuple[dict, DefenceRelevance]] = []
    categories: dict[str, int] = {}
    # CLEANUP-05 — collect Haiku ValidationError entries per-call for
    # surfacing into agent_runs.notes['haiku_validation_errors']. The
    # accumulator is OWNED by this function; classify_story appends to it
    # on schema-mismatch and continues to fail-closed (return None).
    validation_errors: list[dict] = []
    for entry in all_entries[:JUNO_WORLD_EVENTS_CLASSIFIER_CAP]:
        try:
            result = await classify_story(
                client,
                title=entry.get("title", ""),
                snippet=entry.get("summary", ""),
                validation_errors=validation_errors,
            )
        except Exception as exc:  # noqa: BLE001 — fail-closed per entry
            logger.warning(
                "juno_world_events: classify_story raised (%s)",
                type(exc).__name__,
            )
            continue
        if survives_threshold(result):
            survived.append((entry, result))  # type: ignore[arg-type]
            categories[result.category] = categories.get(result.category, 0) + 1

    if not survived:
        return (
            "",
            {
                "world_events_total_seen": len(all_entries),
                "world_events_survived": 0,
                "world_events_categories": {},
                "haiku_validation_errors": validation_errors,
            },
            [],
        )

    bullets = "\n\n".join(
        f"- **{rel.category}** ({rel.confidence:.2f}): {e.get('title','')}\n"
        f"  {(e.get('summary','') or '')[:400]} ({e.get('source_name','?')})"
        for (e, rel) in survived[:25]
    )
    user_prompt = (
        "Synthesize the following defence-relevant world-events stories "
        "(pre-filtered by relevance classifier) into a World Events Relevant "
        "to Defence section. Output 5-7 bullets in markdown, each ending with "
        "`(Source Name)`. Use the section header "
        f"`### 🌐 World Events Relevant to Defence`.\n\n{bullets}"
    )
    text, diagnostic = await call_with_refusal_guard(
        client,
        model=JUNO_SONNET_MODEL,
        max_tokens=JUNO_SONNET_MAX_WORLD,
        system=DEFENCE_NEWS_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        section_name="world_events",
    )
    diagnostic["world_events_total_seen"] = len(all_entries)
    diagnostic["world_events_survived"] = len(survived)
    diagnostic["world_events_categories"] = categories
    diagnostic["haiku_validation_errors"] = validation_errors
    # v3.1 Phase 15 D-03a — normalize survived entries to standard shape +
    # retain classifier category/confidence so the sweeper can weight by
    # category if needed. Cap at 25 (mirrors bullets[:25]).
    world_entries: list[dict] = [
        {
            "source_name": e.get("source_name", "?"),
            "title": e.get("title", ""),
            "summary": (e.get("summary", "") or "")[:1500],
            "link": e.get("link", ""),
            "published": e.get("published", ""),
            "category": rel.category,
            "confidence": float(rel.confidence),
        }
        for (e, rel) in survived[:25]
    ]
    return (text, diagnostic, world_entries)


async def run_juno_daily_summary() -> None:
    """Juno daily_summary entry point — v3.0 Phase 10 real synthesis.

    Fires at 08:05 PT + 12:05 PT (5-min stagger from Seva, per Phase 9 D-01a).
    Synthesizes the 3-section Defence News Funnel:

      1. Defence News      — Tier-1 defence RSS feeds (DEF-01) + Sonnet 4.6
      2. Canadian Procurement — SerpAPI google_news queries (DEF-05; morning
                                fire only per RESEARCH §Open Q 1) + Sonnet
      3. World Events Relevant to Defence — Reuters/AP/BBC World RSS → Haiku
                                4.5 relevance classifier (DEF-06) → Sonnet

    Each Sonnet call is wrapped by `call_with_refusal_guard` (DEF-07) which
    retries once with a framing nudge on the first refusal and falls back to
    SECTION_UNAVAILABLE_COPY on the second refusal. Per-feed bozo +
    recent-history health-check (DEF-04) downgrades the row to
    `status='partial'` when 3+ feeds flag in one fire.

    Idempotency (Phase 9 fix, PRESERVED): per-company check via
    scoped_summaries('juno') filtered by status.in_(['running','completed',
    'partial']). Phase 10 writes 'partial' rows frequently (refusal-detector
    trips, health-check trips, classifier sparseness) so the 'partial'
    inclusion is essential — without it, every Juno cron fire would write a
    duplicate row inside the 30-min window.

    Status mapping (CONTEXT D-12 + D-11):
      - 'failed':    zero entries across all defence feeds (triggers WHA-03)
      - 'partial':   >=1 section refused OR >=3 feeds flagged
      - 'completed': all sections returned text + <3 flagged feeds
    """
    now_utc = datetime.now(timezone.utc)
    now_la = now_utc.astimezone(LA_TZ)
    period_label = _derive_period_label(now_la)
    is_morning_fire = _is_juno_morning_fire(now_la)

    # Idempotency — per-company check (uses scoped_summaries('juno')).
    # CRITICAL: status.in_(['running', 'completed', 'partial']) is the Phase 9
    # D-01b correction. Phase 10 writes 'partial' rows often (refusal-detector
    # trips, 3+ flagged feeds, classifier sparseness). Without 'partial' in
    # the filter, back-to-back fires would duplicate rows in the 30-min
    # window. See Phase 9 09-05 smoke-test bug for the failure mode.
    async with AsyncSessionLocal() as session:
        cutoff = now_utc - timedelta(minutes=IDEMPOTENCY_WINDOW_MIN)
        stmt = (
            scoped_summaries("juno")
            .with_only_columns(DailySummary.id)
            .where(DailySummary.generated_at >= cutoff)
            .where(DailySummary.status.in_(["running", "completed", "partial"]))
            .limit(1)
        )
        result = await session.execute(stmt)
        if result.scalar_one_or_none() is not None:
            logger.info(
                "juno_daily_summary idempotency_skip period=%s — recent Juno "
                "row exists in %dmin window",
                period_label,
                IDEMPOTENCY_WINDOW_MIN,
            )
            return

    # Insert agent_runs row (status='running'). reconcile_stale_runs will
    # sweep this row back to 'failed' if the worker is hard-killed mid-job.
    agent_run = AgentRun(
        agent_name="juno_daily_summary",
        started_at=now_utc,
        items_found=0,
        items_queued=0,
        items_filtered=0,
        status="running",
        notes=json.dumps({"company_id": "juno"}),
    )
    async with AsyncSessionLocal() as session:
        session.add(agent_run)
        await session.commit()
        await session.refresh(agent_run)

    settings = get_settings()
    # Per Phase 7 D-11 baseline: 60s timeout (3-section synthesis x ~1500
    # tokens = ~5-7s actual; 60s leaves wide headroom for refusal-retry).
    # v3.1 Phase 12 — Juno Sonnet routes through per-tenant resolver (D-07, D-09).
    anthropic_client = get_anthropic_client("juno", timeout=JUNO_SONNET_TIMEOUT)
    # SerpAPI client: instantiated on BOTH fires per CLEANUP-01. The
    # `_build_juno_canadian_procurement_section` no longer short-circuits
    # at noon; the only remaining skip path is "no API key configured".
    # Wrap instantiation in try/except so missing/invalid key doesn't kill
    # the whole run — section just skips with diagnostic 'no_serpapi_client'.
    serpapi_client: "serpapi.Client | None" = None
    try:
        if settings.serpapi_api_key:
            serpapi_client = serpapi.Client(api_key=settings.serpapi_api_key)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "juno: serpapi.Client instantiation failed (%s) — section will skip",
            type(exc).__name__,
        )
        serpapi_client = None

    # --- Section 1: Defence News (RSS + Sonnet) ---
    defence_entries: list[dict] = []
    defence_counts: dict[str, int] = {}
    defence_flags: list[str] = []
    defence_md: str | None = None
    defence_diag: dict = {}
    # v3.1 Phase 15 D-03a — story-array substrate for the Sunday sweeper's
    # virality compute. Initialized to [] so per-section exceptions leave the
    # raw_sources_jsonb key as an empty list (NOT undefined) downstream.
    defence_news_entries: list[dict] = []
    procurement_entries: list[dict] = []
    world_entries: list[dict] = []
    try:
        async with AsyncSessionLocal() as session:
            defence_entries, defence_counts, defence_flags = (
                await _run_juno_health_check(
                    session,
                    list(getattr(juno_feeds, "JUNO_DEFENCE_FEEDS", []) or []),
                )
            )
        defence_md, defence_diag, defence_news_entries = (
            await _build_juno_defence_news_section(
                anthropic_client, defence_entries
            )
        )
    except Exception as exc:  # noqa: BLE001 — per-section fail-closed
        logger.exception(
            "juno: defence news section raised — falling back to SECTION_UNAVAILABLE_COPY"
        )
        defence_md = None
        defence_diag = {"exception": f"{type(exc).__name__}: {str(exc)[:200]}"}

    # --- Section 2: Canadian Procurement (SerpAPI [morning only] + Sonnet) ---
    procurement_md: str | None = None
    procurement_diag: dict = {}
    serpapi_count = 0
    try:
        procurement_md, procurement_diag, serpapi_count, procurement_entries = (
            await _build_juno_canadian_procurement_section(
                anthropic_client, serpapi_client, is_morning_fire
            )
        )
    except Exception as exc:  # noqa: BLE001 — per-section fail-closed
        logger.exception(
            "juno: canadian procurement section raised — falling back to SECTION_UNAVAILABLE_COPY"
        )
        procurement_md = None
        procurement_diag = {"exception": f"{type(exc).__name__}: {str(exc)[:200]}"}

    # --- Section 3: World Events (RSS → Haiku classifier filter → Sonnet) ---
    world_md: str | None = None
    world_diag: dict = {}
    try:
        async with AsyncSessionLocal() as session:
            world_md, world_diag, world_entries = (
                await _build_juno_world_events_section(
                    anthropic_client, session
                )
            )
    except Exception as exc:  # noqa: BLE001 — per-section fail-closed
        logger.exception(
            "juno: world events section raised — falling back to SECTION_UNAVAILABLE_COPY"
        )
        world_md = None
        world_diag = {"exception": f"{type(exc).__name__}: {str(exc)[:200]}"}

    # --- Status mapping (CONTEXT D-12 + D-11) ---
    # `None` returned from a section means: refusal-guard exhausted retries
    # OR section raised an unhandled exception. Empty-string ("") means: section
    # intentionally skipped (e.g., procurement on the 12:05 PT fire).
    sections_refused = sum(
        1 for md in (defence_md, procurement_md, world_md) if md is None
    )
    error_text: str | None = None
    if not defence_entries:
        overall_status = "failed"
        error_text = (
            "Defence News ingestion produced zero entries across all feeds"
        )
    elif sections_refused >= 1 or len(defence_flags) >= juno_hc.PARTIAL_FLAG_THRESHOLD:
        overall_status = "partial"
        error_text = (
            f"{sections_refused} section(s) returned None (refusal/error); "
            f"{len(defence_flags)} feed(s) flagged"
        )
    else:
        overall_status = "completed"

    # Markdown fallback for refused/errored sections. Empty-string ("") for
    # intentionally-skipped sections (e.g., 12:05 PT procurement) flows
    # through as-is so the SummaryCard renders a blank slot rather than the
    # operator-facing fallback copy.
    final_defence_md = (
        defence_md if defence_md is not None else SECTION_UNAVAILABLE_COPY
    )
    final_procurement_md = (
        procurement_md if procurement_md is not None else SECTION_UNAVAILABLE_COPY
    )
    final_world_md = (
        world_md if world_md is not None else SECTION_UNAVAILABLE_COPY
    )

    # Telemetry — agent_runs.notes per CONTEXT D-12. The
    # `defence_feed_entry_counts` key is the canonical history-lookback key
    # consumed by _fetch_7day_avg_for_feed on the NEXT fire.
    base_payload = juno_hc.build_notes_payload(
        feed_entry_counts=defence_counts,
        flagged_feeds=defence_flags,
    )
    notes_dict: dict = {
        **base_payload,
        # History-lookback key (CONTEXT D-12 + graceful fallback).
        "defence_feed_entry_counts": dict(defence_counts),
        "defence_diagnostic": defence_diag,
        "procurement_diagnostic": procurement_diag,
        "world_events_diagnostic": world_diag,
        "serpapi_query_count": serpapi_count,
        "is_morning_fire": is_morning_fire,
        "overall_status": overall_status,
        # CLEANUP-05 (Phase 11) — Haiku ValidationError observability.
        # Empty list on the happy path; populated only when Haiku returns
        # schema-violating structured output. Behavioral fail-closed is
        # preserved upstream in classify_story.
        "haiku_validation_errors": list(world_diag.get("haiku_validation_errors", []) or []),
        # v3.1 Phase 15 D-03a — story arrays for the Sweeper's virality
        # compute substrate. Phase 10 stored only diagnostic counts; Phase
        # 15 adds story-URL arrays so the Sunday sweeper can cross-reference
        # X signals against the past 7 days of Juno daily-summary stories
        # (defence_news + canadian_procurement + world_events union).
        # See .planning/phases/15-juno-weekly-viral-sweeper/15-RESEARCH.md §3.
        # D-03b: existing pre-Phase-15 Juno rows have empty arrays here —
        # first 0-2 sweeps post-deploy may trip status='partial' with
        # diagnostic note "substrate accumulating from new schema".
        "defence_news": defence_news_entries,
        "canadian_procurement": procurement_entries,
        "world_events": world_entries,
    }

    try:
        # Write the daily_summaries row (semantic field-reuse per Phase 9 D-08).
        # The 3 physical columns map to Juno's logical section names:
        #   gold_news_md     → Defence News
        #   ontario_law_md   → Canadian Procurement
        #   ontario_stats_md → World Events Relevant to Defence
        async with AsyncSessionLocal() as session:
            summary_row = DailySummary(
                company_id="juno",
                generated_at=now_utc,
                period_label=period_label,
                gold_news_md=final_defence_md,
                ontario_law_md=final_procurement_md,
                ontario_stats_md=final_world_md,
                raw_sources_jsonb=notes_dict,
                status=overall_status,
                error_text=error_text,
                agent_run_id=agent_run.id,
            )
            session.add(summary_row)
            await session.commit()

        # Update agent_run status. 'failed' on the row maps to agent_run='failed';
        # 'completed' and 'partial' both map to agent_run='completed' (the worker
        # successfully wrote a row, even if the row carries partial markdown).
        agent_run_status = "completed" if overall_status != "failed" else "failed"
        async with AsyncSessionLocal() as session:
            fresh = await session.get(AgentRun, agent_run.id)
            if fresh is not None:
                fresh.status = agent_run_status
                fresh.ended_at = datetime.now(timezone.utc)
                fresh.notes = json.dumps(notes_dict, default=str)
                await session.commit()

    except Exception as exc:  # noqa: BLE001
        logger.exception("juno_daily_summary failed: %s", exc)
        async with AsyncSessionLocal() as session:
            fresh = await session.get(AgentRun, agent_run.id)
            if fresh is not None:
                fresh.status = "failed"
                fresh.ended_at = datetime.now(timezone.utc)
                fresh.errors = [
                    f"{type(exc).__name__}: {str(exc)[:200]}"
                ]
                await session.commit()

