"""Parity guard: scheduler-side DailySummary must expose identical columns to the backend.

If a future change renames or drops one of these, this test fails — keeping
backend `app/models/daily_summary.py` and `scheduler/models/daily_summary.py` in lockstep.

Phase 1, Plan 01.
"""
from models.daily_summary import DailySummary


def test_daily_summary_tablename():
    assert DailySummary.__tablename__ == "daily_summaries"


def test_daily_summary_has_id_column():
    assert hasattr(DailySummary, "id")


def test_daily_summary_has_generated_at_column():
    assert hasattr(DailySummary, "generated_at")


def test_daily_summary_has_period_label_column():
    assert hasattr(DailySummary, "period_label")


def test_daily_summary_has_gold_news_md_column():
    assert hasattr(DailySummary, "gold_news_md")


def test_daily_summary_has_ontario_law_md_column():
    assert hasattr(DailySummary, "ontario_law_md")


def test_daily_summary_has_ontario_stats_md_column():
    assert hasattr(DailySummary, "ontario_stats_md")


def test_daily_summary_has_raw_sources_jsonb_column():
    assert hasattr(DailySummary, "raw_sources_jsonb")


def test_daily_summary_has_status_column():
    assert hasattr(DailySummary, "status")


def test_daily_summary_has_error_text_column():
    assert hasattr(DailySummary, "error_text")


def test_daily_summary_has_agent_run_id_column():
    assert hasattr(DailySummary, "agent_run_id")


def test_daily_summary_has_created_at_column():
    assert hasattr(DailySummary, "created_at")
