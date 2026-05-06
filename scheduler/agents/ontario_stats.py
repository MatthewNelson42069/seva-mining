"""v2.0 Phase 3 — Ontario Stats ingestion via StatCan WDS direct vector poll.

Replaces the Phase 1 _build_ontario_stats_section() stub in daily_summary.py.

Scope (STAT-01..STAT-05):
  - Direct poll of StatCan WDS endpoint — no RSS trigger, no LLM, no SerpAPI
  - vectorId 1146004456 = Ontario gold recoverable production (kg), Table 16-10-0019
  - State machine: 'fresh' | 'no_new_data' | 'error'
  - Freshness gated by lexicographic comparison of releaseTime against prior snapshot
  - On error, caller preserves last-good JSONB snapshot (this module is stateless)

API cost: $0 — public StatCan WDS endpoint, no authentication required.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Locked constants (CONTEXT.md — D-Locked: verified 2026-05-06)
# ---------------------------------------------------------------------------

WDS_ENDPOINT = "https://www150.statcan.gc.ca/t1/wds/rest/getDataFromVectorsAndLatestNPeriods"
ONTARIO_GOLD_VECTOR_ID = 1146004456  # CONTEXT.md D-Locked: Ontario gold recoverable, kg
WDS_LATEST_N = 3  # current + 2 priors → enables MoM comparison
WDS_TIMEOUT_SECONDS = 15.0  # network resilience — slow WDS shouldn't kill the cron


# ---------------------------------------------------------------------------
# Result dataclass — public return type of fetch_ontario_stats_snapshot
# ---------------------------------------------------------------------------

@dataclass
class OntarioStatsResult:
    """Result of one WDS poll.

    state: 'fresh' | 'no_new_data' | 'error'
    On 'no_new_data', all data fields are None — caller propagates prior snapshot.
    On 'error', all data fields are None and error_text is set.
    On 'fresh', figure_kg/period/release_time are set; prior_* may be None if
    WDS only returned 1 datapoint.
    """
    state: str  # "fresh" | "no_new_data" | "error"
    figure_kg: float | None = None
    period: str | None = None  # "YYYY-MM"
    release_time: str | None = None  # "YYYY-MM-DDThh:mm"
    prior_period: str | None = None
    prior_figure_kg: float | None = None
    error_text: str | None = None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def fetch_ontario_stats_snapshot(
    previous_release_time: str | None = None,
) -> OntarioStatsResult:
    """Poll StatCan WDS for the latest Ontario gold production data.

    Args:
        previous_release_time: The releaseTime from the prior snapshot (or None
            on the first-ever fire). Lexicographically compared against the WDS
            response to detect fresh data.

    Returns:
        OntarioStatsResult with state 'fresh', 'no_new_data', or 'error'.
        On any exception or malformed response → state='error'.
        On 'no_new_data' → all data fields are None (caller propagates prior).
    """
    try:
        async with httpx.AsyncClient(timeout=WDS_TIMEOUT_SECONDS) as client:
            resp = await client.post(
                WDS_ENDPOINT,
                json=[{"vectorId": ONTARIO_GOLD_VECTOR_ID, "latestN": WDS_LATEST_N}],
            )
            resp.raise_for_status()

            payload = resp.json()

            # WDS returns a list with one element per requested vector
            entry = payload[0]
            status = entry.get("status", "")
            if status != "SUCCESS":
                error_text = f"WDS non-SUCCESS status: {status}"
                logger.warning("ontario_stats: %s", error_text)
                return OntarioStatsResult(state="error", error_text=error_text)

            dps = entry["object"]["vectorDataPoint"]
            if not dps:
                error_text = "WDS returned no datapoints"
                logger.warning("ontario_stats: %s", error_text)
                return OntarioStatsResult(state="error", error_text=error_text)

            # StatCan returns datapoints ascending by refPer — latest is last
            latest = dps[-1]
            prior = dps[-2] if len(dps) >= 2 else None

            current_release_time: str = latest["releaseTime"]
            # refPer is "YYYY-MM-DD" — slice to "YYYY-MM"
            current_period: str = latest["refPer"][:7]
            figure_kg: float = float(latest["value"])

            # Freshness check: None previous_release_time is always fresh
            if previous_release_time is None or current_release_time > previous_release_time:
                prior_period: str | None = None
                prior_figure_kg: float | None = None
                if prior is not None:
                    prior_period = prior["refPer"][:7]
                    prior_figure_kg = float(prior["value"])
                return OntarioStatsResult(
                    state="fresh",
                    figure_kg=figure_kg,
                    period=current_period,
                    release_time=current_release_time,
                    prior_period=prior_period,
                    prior_figure_kg=prior_figure_kg,
                )

            # Same or older releaseTime — no new data
            return OntarioStatsResult(state="no_new_data")

    except Exception as exc:  # noqa: BLE001 — any failure → state='error'
        error_text = f"{type(exc).__name__}: {str(exc)[:200]}"
        logger.warning("ontario_stats: WDS poll failed — %s", error_text)
        return OntarioStatsResult(state="error", error_text=error_text)


# ---------------------------------------------------------------------------
# Helper: next-release estimate formula
# ---------------------------------------------------------------------------

def _compute_next_release_estimate(period_str: str) -> str:
    """Compute the estimated next StatCan release date.

    StatCan releases Monthly Mineral Production Survey data ~M+2 months later,
    around the 19th-21st. This function returns "around {Month} 20, {Year}".

    Args:
        period_str: Reference period in "YYYY-MM" format (e.g. "2026-02").

    Returns:
        e.g. "around May 20, 2026" for input "2026-02".
             "around March 20, 2027" for input "2026-12" (year rollover).
    """
    dt = datetime.strptime(period_str, "%Y-%m")
    year, month = dt.year, dt.month + 3
    while month > 12:
        month -= 12
        year += 1
    next_dt = datetime(year, month, 20)
    return f"around {next_dt.strftime('%B')} 20, {year}"


# ---------------------------------------------------------------------------
# Markdown formatters (pure functions)
# ---------------------------------------------------------------------------

def format_fresh_markdown(result: OntarioStatsResult) -> str:
    """Render fresh-data markdown for the Ontario Stats section (STAT-04).

    Template:
      **Ontario gold production for {Month YYYY}: {figure:,.0f} kg**
      (vs {prior:,.0f} kg in {prior_month}, {pct:+.1f}% MoM)

      Source: Statistics Canada, Table 16-10-0019, released {YYYY-MM-DD}.

    If prior_figure_kg is None, the MoM parenthetical is omitted.
    """
    period_label = datetime.strptime(result.period, "%Y-%m").strftime("%B %Y")
    figure_str = f"{result.figure_kg:,.0f}"
    release_date = (result.release_time or "")[:10]

    if result.prior_figure_kg is not None and result.prior_period is not None:
        prior_label = datetime.strptime(result.prior_period, "%Y-%m").strftime("%B %Y")
        prior_str = f"{result.prior_figure_kg:,.0f}"
        pct = ((result.figure_kg - result.prior_figure_kg) / result.prior_figure_kg) * 100
        mom_part = f" (vs {prior_str} kg in {prior_label}, {pct:+.1f}% MoM)"
    else:
        mom_part = ""

    return (
        f"**Ontario gold production for {period_label}: {figure_str} kg**{mom_part}\n\n"
        f"Source: Statistics Canada, Table 16-10-0019, released {release_date}."
    )


def format_no_new_data_markdown(prior_snapshot: dict | None) -> str:
    """Render no-new-data markdown for the Ontario Stats section (STAT-05).

    Two cases:
      - prior_snapshot is None (first-ever fire on a non-release day) → awaiting copy
      - prior_snapshot present → last-data copy with computed next-release estimate
    """
    if prior_snapshot is None:
        return (
            "Ontario production statistics are released monthly with a ~2-month lag. "
            "Awaiting first StatCan release."
        )

    period = prior_snapshot["period"]  # "YYYY-MM"
    figure_kg = prior_snapshot["figure_kg"]
    next_release_estimate = _compute_next_release_estimate(period)
    figure_str = f"{figure_kg:,.0f}"

    return (
        f"No new production statistics released today. "
        f"Next Monthly Mineral Production Survey release expected {next_release_estimate}. "
        f"Last data: {period} — Ontario gold production: {figure_str} kg."
    )


def format_error_markdown(error_text: str, agent_run_id: str) -> str:
    """Render error markdown for the Ontario Stats section (STAT-05 error path).

    Includes the warning glyph and first 8 chars of agent_run_id for traceability.
    """
    short_error = (error_text or "unknown")[:120]
    short_id = agent_run_id[:8]
    return (
        f"⚠ Ontario production statistics ingestion failed: {short_error}. "
        f"agent_run_id: {short_id} — see agent-runs log for details."
    )
