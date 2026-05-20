"""Wave 0 RED tests for Juno per-feed health-check (DEF-04).

Production helper lands in Wave 2 (10-03-PLAN.md) — either as a new module
`scheduler/agents/juno_health_check.py` or as an inline helper inside
`scheduler/agents/daily_summary.py::run_juno_daily_summary`. The Wave 2
executor picks the location; this test imports the canonical name and
removes the module-level skip below to turn the file GREEN.

Contracts asserted (verbatim from 10-CONTEXT.md §D-12):
- bozo flag triggers per-feed flag
- empty entries triggers per-feed flag
- today's count < 30% of 7-day average → flag
- exactly 3 flagged feeds + healthy feeds → status='partial'
- 2 flagged + healthy → status='completed' (under 3-flag threshold)
- zero entries across all feeds → status='failed' + WhatsApp alert (WHA-03)
- agent_runs.notes carries feed_entry_counts dict {source_name: int}
"""
from __future__ import annotations

import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

# Wave 2 (10-03-PLAN.md) removes this skip line to turn the module GREEN.
pytest.skip(
    "Wave 0 RED — Juno health-check helper lands in Wave 2 (10-03-PLAN.md). "
    "Remove this skip line in that wave's task to turn tests GREEN.",
    allow_module_level=True,
)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _mk_feed(bozo: int, entry_count: int):
    """Build a SimpleNamespace mimicking feedparser.parse() return shape."""
    entries = [SimpleNamespace(title=f"entry-{i}") for i in range(entry_count)]
    return SimpleNamespace(bozo=bozo, entries=entries, bozo_exception=None)


# ---------------------------------------------------------------------------
# Per-feed bozo / empty-entries flag detection
# ---------------------------------------------------------------------------


def test_bozo_flag():
    """feedparser bozo=1 (parse error) flags the feed."""
    from agents.juno_health_check import flag_feed

    feed = _mk_feed(bozo=1, entry_count=0)
    flagged = flag_feed(source_name="war_gov", feed=feed, history_avg=0)
    assert flagged is True


def test_empty_entries_flag():
    """bozo=0 but entries=[] flags the feed."""
    from agents.juno_health_check import flag_feed

    feed = _mk_feed(bozo=0, entry_count=0)
    flagged = flag_feed(source_name="defense_news_pentagon", feed=feed, history_avg=0)
    assert flagged is True


def test_healthy_feed_not_flagged():
    """bozo=0 with entries does NOT flag, when entries >= 30% of history."""
    from agents.juno_health_check import flag_feed

    feed = _mk_feed(bozo=0, entry_count=25)
    flagged = flag_feed(
        source_name="defense_news_industry", feed=feed, history_avg=20
    )
    assert flagged is False


# ---------------------------------------------------------------------------
# 7-day history threshold (< 30% of 7-day avg)
# ---------------------------------------------------------------------------


def test_history_threshold_below_30pct():
    """Today's count (2) < 30% of 7-day avg (10) → flagged."""
    from agents.juno_health_check import flag_feed

    feed = _mk_feed(bozo=0, entry_count=2)
    flagged = flag_feed(source_name="rusi_commentary", feed=feed, history_avg=10)
    assert flagged is True


def test_history_threshold_at_30pct():
    """Today's count exactly 30% of avg → NOT flagged (strict less-than per D-12)."""
    from agents.juno_health_check import flag_feed

    feed = _mk_feed(bozo=0, entry_count=3)
    flagged = flag_feed(source_name="rusi_commentary", feed=feed, history_avg=10)
    assert flagged is False


def test_history_threshold_no_history():
    """Zero-history (new feed) → not flagged on history; bozo check still applies."""
    from agents.juno_health_check import flag_feed

    feed = _mk_feed(bozo=0, entry_count=5)
    flagged = flag_feed(source_name="new_feed", feed=feed, history_avg=0)
    assert flagged is False

    # But bozo=1 still flags even with no history
    bozo_feed = _mk_feed(bozo=1, entry_count=0)
    flagged_bozo = flag_feed(
        source_name="new_feed", feed=bozo_feed, history_avg=0
    )
    assert flagged_bozo is True


# ---------------------------------------------------------------------------
# Aggregate status (status='partial' on 3+ flags; 'failed' on zero entries)
# ---------------------------------------------------------------------------


def test_three_flags_partial():
    """3 flagged feeds + 10 healthy → status='partial'."""
    from agents.juno_health_check import derive_run_status

    flagged_feeds = ["war_gov", "nato_news", "canada_ca_defence"]
    healthy_feeds = [f"feed_{i}" for i in range(10)]
    feed_entry_counts = {
        **{name: 0 for name in flagged_feeds},
        **{name: 25 for name in healthy_feeds},
    }
    status = derive_run_status(
        flagged_feeds=flagged_feeds, feed_entry_counts=feed_entry_counts
    )
    assert status == "partial"


def test_two_flags_completed():
    """2 flagged + 11 healthy → status='completed' (under 3-flag threshold)."""
    from agents.juno_health_check import derive_run_status

    flagged_feeds = ["war_gov", "nato_news"]
    healthy_feeds = [f"feed_{i}" for i in range(11)]
    feed_entry_counts = {
        **{name: 0 for name in flagged_feeds},
        **{name: 25 for name in healthy_feeds},
    }
    status = derive_run_status(
        flagged_feeds=flagged_feeds, feed_entry_counts=feed_entry_counts
    )
    assert status == "completed"


def test_zero_entries_all_feeds_failed():
    """All feeds flagged AND zero entries → status='failed' (WhatsApp WHA-03)."""
    from agents.juno_health_check import derive_run_status

    all_feeds = [f"feed_{i}" for i in range(13)]
    flagged_feeds = list(all_feeds)
    feed_entry_counts = {name: 0 for name in all_feeds}
    status = derive_run_status(
        flagged_feeds=flagged_feeds, feed_entry_counts=feed_entry_counts
    )
    assert status == "failed"


# ---------------------------------------------------------------------------
# agent_runs.notes telemetry shape (D-12)
# ---------------------------------------------------------------------------


def test_feed_entry_counts_telemetry_shape():
    """build_notes_payload(...) returns the canonical D-12 notes shape."""
    from agents.juno_health_check import build_notes_payload

    feed_entry_counts = {
        "defense_news_industry": 25,
        "defense_news_pentagon": 25,
        "war_gov": 0,
    }
    flagged_feeds = ["war_gov"]

    payload = build_notes_payload(
        feed_entry_counts=feed_entry_counts,
        flagged_feeds=flagged_feeds,
    )

    assert isinstance(payload, dict)
    assert "feed_entry_counts" in payload
    assert isinstance(payload["feed_entry_counts"], dict)
    for name, count in payload["feed_entry_counts"].items():
        assert isinstance(name, str)
        assert isinstance(count, int)
    assert "flagged_feeds" in payload
    assert payload["flagged_feeds"] == ["war_gov"]
    assert payload["company_id"] == "juno"
