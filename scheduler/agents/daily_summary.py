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

import json
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from anthropic import AsyncAnthropic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import serpapi

from agents.content_agent import fetch_stories
from agents.ontario_law import fetch_ontario_law_hits
from agents.ontario_stats import (
    fetch_ontario_stats_snapshot,
    format_error_markdown,
    format_fresh_markdown,
    format_no_new_data_markdown,
)
from config import get_settings
from database import AsyncSessionLocal
from models.agent_run import AgentRun
from models.daily_summary import DailySummary
from services.market_snapshot import fetch_market_snapshot
from services.whatsapp import (
    deliver_summary_failure_alert,
    deliver_summary_teaser,
)

logger = logging.getLogger(__name__)

LA_TZ = ZoneInfo("America/Los_Angeles")
GOLD_SCORE_FLOOR = 6.0          # GOLD-01 — locked in research SUMMARY.md
GOLD_TOP_N = 12                 # quick-260512-of1 — bumped from 5 for bull-thesis brief
SONNET_MODEL = "claude-sonnet-4-6"  # locked — Sonnet for the WRITE call only
SONNET_MAX_TOKENS = 1500        # quick-260512-of1 — bumped from 800; bull-thesis brief is structurally larger
IDEMPOTENCY_WINDOW_MIN = 30     # CRIT-3 — match misfire_grace_time

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


async def _idempotency_skip(session: AsyncSession, now_utc: datetime) -> bool:
    """CRIT-3 / SUM-03 — return True if a recent run already wrote a row."""
    cutoff = now_utc - timedelta(minutes=IDEMPOTENCY_WINDOW_MIN)
    stmt = (
        select(DailySummary.id)
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
    anthropic_client = AsyncAnthropic(
        api_key=settings.anthropic_api_key, timeout=60.0,
    )

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
            stmt = (
                select(DailySummary.raw_sources_jsonb)
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
