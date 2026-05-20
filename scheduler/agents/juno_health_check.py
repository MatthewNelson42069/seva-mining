"""Juno per-feed health-check pure helpers — Phase 10 DEF-04 / CONTEXT D-12.

These three pure functions are imported both by the daily_summary
orchestrator and by tests/agents/test_juno_health_check.py. Keeping them
in their own module preserves clear seams:

- flag_feed(source_name, feed, history_avg) -> bool
  Per-feed bozo / empty / <30%-of-7d-avg flagging rule (D-12).

- derive_run_status(flagged_feeds, feed_entry_counts) -> str
  Aggregate status mapping (D-12):
    zero entries across all feeds → 'failed' (triggers WHA-03)
    3+ flagged feeds              → 'partial'
    else                          → 'completed'

- build_notes_payload(feed_entry_counts, flagged_feeds) -> dict
  Canonical D-12 telemetry shape written to agent_runs.notes.

The daily_summary orchestrator drives the feedparser.parse() + 7-day-avg
SELECT around these helpers — they remain pure (no I/O, no async).
"""
from __future__ import annotations

from typing import Any

# CONTEXT D-12 — fraction of 7-day avg below which today's count is flagged.
HISTORY_THRESHOLD_FRACTION = 0.3
# CONTEXT D-12 — number of flagged feeds (inclusive) that trips 'partial'.
PARTIAL_FLAG_THRESHOLD = 3


def flag_feed(*, source_name: str, feed: Any, history_avg: float) -> bool:
    """Per-feed bozo / empty / <30%-of-7d-avg flag rule.

    Returns True if the feed should be flagged this fire. Used by
    daily_summary's RSS ingestion loop to append source_name to
    `flagged_feeds`.

    Logic (D-12):
      1. bozo == 1 → flag (feedparser parse error)
      2. entries == [] → flag (empty feed)
      3. history_avg > 0 AND today's count < 0.3 * history_avg → flag
      4. otherwise → not flagged

    `feed` is the SimpleNamespace-like object returned by feedparser.parse(),
    with `.bozo` (int) and `.entries` (list) attributes.
    """
    bozo = getattr(feed, "bozo", 0)
    entries = getattr(feed, "entries", []) or []
    n_entries = len(entries)

    if bozo:
        return True
    if n_entries == 0:
        return True
    if history_avg > 0 and n_entries < (HISTORY_THRESHOLD_FRACTION * history_avg):
        return True
    return False


def derive_run_status(
    *,
    flagged_feeds: list[str],
    feed_entry_counts: dict[str, int],
) -> str:
    """Aggregate per-feed flags into the daily_summaries row status (D-12).

    - 'failed':    zero entries across all feeds (triggers WhatsApp WHA-03)
    - 'partial':   PARTIAL_FLAG_THRESHOLD (3) or more flagged feeds
    - 'completed': otherwise
    """
    total_entries = sum(feed_entry_counts.values()) if feed_entry_counts else 0
    if total_entries == 0:
        return "failed"
    if len(flagged_feeds) >= PARTIAL_FLAG_THRESHOLD:
        return "partial"
    return "completed"


def build_notes_payload(
    *,
    feed_entry_counts: dict[str, int],
    flagged_feeds: list[str],
) -> dict[str, Any]:
    """Build the canonical D-12 agent_runs.notes telemetry shape.

    Used by daily_summary.run_juno_daily_summary as the base of the
    `agent_runs.notes` JSON. Caller may extend with refusal diagnostics
    and SerpAPI counters before writing.
    """
    return {
        "company_id": "juno",
        "feed_entry_counts": dict(feed_entry_counts),
        "flagged_feeds": list(flagged_feeds),
    }
