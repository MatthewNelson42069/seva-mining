"""v2.0 daily_summary cron — Phase 1.

Fires at 08:00 PT and 12:00 PT (registered in worker.py via _make_daily_summary_job).
Writes one daily_summaries row + one agent_runs row per fire.

Pitfall mitigations bundled here:
  CRIT-3 (multiple fires from misfire) — DB-level idempotency check at start.
  HIGH-4 (JSONB schema drift)         — raw_sources_jsonb built from a fixed dict shape.
  HIGH-5 (WhatsApp >1600 chars)       — uses deliver_summary_teaser (NOT build_chunks).
  MOD-5 (hallucinated dates)          — published_at injected into Sonnet user prompt.
  MOD-6 (failure alert deadlock)      — deliver_summary_failure_alert wraps its send.
  SUM-04 (telemetry)                  — notes JSON dumped on the agent_runs row.
  SUM-05 (status assembly)            — completed/partial/failed mapped from per-section
                                        success counts.
  GOLD-01 (score >= 6.0, top 5)       — applied after fetch_stories.
  GOLD-02 (markdown structure)        — Sonnet prompt template enforces.
  GOLD-03 (empty-state)               — pulls price range from market_snapshot service.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from anthropic import AsyncAnthropic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.content_agent import fetch_stories
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
GOLD_TOP_N = 5                  # GOLD-01
SONNET_MODEL = "claude-sonnet-4-6"  # locked — Sonnet for the WRITE call only
SONNET_MAX_TOKENS = 800         # ~1200 chars target (locked SUMMARY.md budget)
IDEMPOTENCY_WINDOW_MIN = 30     # CRIT-3 — match misfire_grace_time

# GOLD-02 prompt template — kept as a module-level constant so tests can
# grep for the locked structural elements (1-sentence lead, 3-5 bullets,
# inline source citation, ≤ 25 words per bullet).
GOLD_NEWS_SYSTEM_PROMPT = """\
You are the writer for a daily gold-sector intelligence summary.

Output MUST be markdown in this exact structure (no preamble, no postamble):

1. ONE sentence on its own line — a "Why it matters" lead that synthesises the
   top story's significance for gold investors. This lead is reused as the
   WhatsApp teaser body, so make it self-contained.
2. A blank line.
3. 3 to 5 markdown bullet points (use `*` style). Choose the count adaptively
   based on how many of the supplied stories deserve a bullet — do not pad.
   Each bullet:
     - Maximum 25 words.
     - Ends with `(Source Name)` referencing the article's source.
     - Does NOT repeat the lead.
     - Uses ONLY dates explicitly stated in the supplied articles. Do not
       infer, estimate, or use training knowledge for dates. If a story has
       no date, write 'recently' rather than inventing one.

Do NOT emit headings (#, ##, ###). Do NOT emit a 'Sources:' footnote section.
Do NOT use tables. Do NOT use blockquotes.
"""

# GOLD-03 empty-state copy (locked CONTEXT decision):
EMPTY_STATE_TEMPLATE_WITH_RANGE = "No major moves in gold today — prices ranging ${low}–${high}."
EMPTY_STATE_FALLBACK = "No major moves in gold today."

ONTARIO_LAW_STUB_MD = "(stub) Ontario law section — populated in Phase 2."
ONTARIO_STATS_STUB_MD = "(stub) Ontario stats section — populated in Phase 3."


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
) -> tuple[str | None, list[dict]]:
    """GOLD-01/02/03. Returns (markdown_or_None, raw_stories_for_jsonb).

    Returns (None, []) on hard failure so the caller marks the section as failed.
    Returns (empty_state_md, []) when no stories clear the score floor.
    """
    try:
        stories = await fetch_stories()
    except Exception:
        logger.exception("daily_summary: fetch_stories raised — gold section failed")
        return (None, [])

    if not stories:
        return (await _gold_empty_state(), [])

    # GOLD-01 — score floor + top N
    relevant = [s for s in stories if (s.get("score") or 0) >= GOLD_SCORE_FLOOR]
    top = sorted(relevant, key=lambda s: s.get("score") or 0, reverse=True)[:GOLD_TOP_N]

    if not top:
        return (await _gold_empty_state(), [])

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
    except Exception:
        logger.exception("daily_summary: Sonnet write call raised")
        return (None, top)

    # Build raw_sources entry for JSONB (HIGH-4 shape):
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
    return (md, raw)


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


async def _build_ontario_law_section() -> tuple[str, list[dict]]:
    """Phase 1 stub. Phase 2 replaces this with real ingestion + Haiku filter."""
    return (ONTARIO_LAW_STUB_MD, [])


async def _build_ontario_stats_section() -> tuple[str, list[dict]]:
    """Phase 1 stub. Phase 3 replaces this with StatCan WDS ingestion."""
    return (ONTARIO_STATS_STUB_MD, [])


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
    candidates_gold = 0
    whatsapp_sent = False
    run_status = "failed"
    error_text: str | None = None

    settings = get_settings()
    anthropic_client = AsyncAnthropic(
        api_key=settings.anthropic_api_key, timeout=30.0,
    )

    try:
        # --- Section 1: Gold News (real) ---
        gold_news_md, gold_raw = await _build_gold_news_section(anthropic_client)
        candidates_gold = len(gold_raw)
        if gold_news_md is not None:
            sections_completed.append("gold_news")
        else:
            sections_failed.append("gold_news")

        # --- Section 2: Ontario Law (stub in Phase 1) ---
        ontario_law_md, _ = await _build_ontario_law_section()
        sections_completed.append("ontario_law")

        # --- Section 3: Ontario Stats (stub in Phase 1) ---
        ontario_stats_md, _ = await _build_ontario_stats_section()
        sections_completed.append("ontario_stats")

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
            "ontario_law": {"hits": [], "last_known_law": None},
            "ontario_stats": {
                "snapshot_date": "",
                "last_known_figure": None,
                "fresh_data": None,
            },
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
                            "snapshot_date": "",
                            "last_known_figure": None,
                            "fresh_data": None,
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
                "candidates_law": 0,            # Phase 2 fills this
                "candidates_stats": 0,          # Phase 3 fills this
                "sections_completed": sections_completed,
                "sections_failed": sections_failed,
                "whatsapp_sent": whatsapp_sent,
            }
            async with AsyncSessionLocal() as session:
                fresh = await session.get(AgentRun, agent_run.id)
                if fresh is not None:
                    fresh.status = run_status
                    fresh.ended_at = datetime.now(timezone.utc)
                    fresh.items_found = candidates_gold
                    fresh.items_queued = len(sections_completed)
                    fresh.items_filtered = len(sections_failed)
                    fresh.notes = json.dumps(notes_payload)
                    if error_text:
                        fresh.errors = [error_text]
                    await session.commit()
        except Exception:
            logger.exception("daily_summary agent_runs telemetry update failed")
