"""
Tests for scheduler/models/chart_spec.py — Pydantic v2 BundleCharts schema.

Pure Pydantic tests: no lazy imports, no skip guards.
Runnable with: cd scheduler && uv run pytest tests/test_chart_spec.py -x
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Set required env vars before any imports
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://fake-pooler.neon.tech/db?sslmode=require")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test-fake")
os.environ.setdefault("TWILIO_ACCOUNT_SID", "x")
os.environ.setdefault("TWILIO_AUTH_TOKEN", "x")
os.environ.setdefault("TWILIO_WHATSAPP_FROM", "whatsapp:+1x")
os.environ.setdefault("DIGEST_WHATSAPP_TO", "whatsapp:+1x")
os.environ.setdefault("X_API_BEARER_TOKEN", "test-bearer-token")
os.environ.setdefault("X_API_KEY", "test-key")
os.environ.setdefault("X_API_SECRET", "test-secret")
os.environ.setdefault("SERPAPI_API_KEY", "x")
os.environ.setdefault("FRONTEND_URL", "https://x.com")

import pytest
from pydantic import ValidationError

from models.chart_spec import (
    BundleCharts,
    ChartSpec,
    ChartType,
    DataPoint,
    StatCallout,
    TableRow,
    TimelineEvent,
)


# ---------------------------------------------------------------------------
# test_all_chart_types_parse
# ---------------------------------------------------------------------------

def test_all_chart_types_parse():
    """BundleCharts.model_validate parses a minimal valid spec for each of the 9 ChartType values."""
    for chart_type in ChartType:
        spec = ChartSpec(type=chart_type, title=f"Test {chart_type.value}")
        payload = BundleCharts(charts=[spec], twitter_caption="Test caption")
        assert payload.charts[0].type == chart_type


# ---------------------------------------------------------------------------
# test_max_two_charts
# ---------------------------------------------------------------------------

def test_max_two_charts():
    """BundleCharts with charts=[spec1, spec2, spec3] raises ValidationError."""
    spec = ChartSpec(type=ChartType.bar, title="Test")
    with pytest.raises(ValidationError):
        BundleCharts(charts=[spec, spec, spec], twitter_caption="Caption")


# ---------------------------------------------------------------------------
# test_invalid_type_raises
# ---------------------------------------------------------------------------

def test_invalid_type_raises():
    """ChartSpec with type='unknown' raises ValidationError."""
    with pytest.raises(ValidationError):
        ChartSpec(type="unknown", title="Test")


# ---------------------------------------------------------------------------
# test_width_height_defaults
# ---------------------------------------------------------------------------

def test_width_height_defaults():
    """ChartSpec() without width/height has width=1200, height=675."""
    spec = ChartSpec(type=ChartType.bar, title="Gold Price YTD")
    assert spec.width == 1200
    assert spec.height == 675


# ---------------------------------------------------------------------------
# test_bundle_charts_requires_caption
# ---------------------------------------------------------------------------

def test_bundle_charts_requires_caption():
    """BundleCharts without twitter_caption raises ValidationError."""
    spec = ChartSpec(type=ChartType.bar, title="Test")
    with pytest.raises(ValidationError):
        BundleCharts(charts=[spec])


# ---------------------------------------------------------------------------
# test_stat_callout_fields
# ---------------------------------------------------------------------------

def test_stat_callout_fields():
    """StatCallout(value='2,400', label='Gold $/oz') parses correctly."""
    stat = StatCallout(value="2,400", label="Gold $/oz")
    assert stat.value == "2,400"
    assert stat.label == "Gold $/oz"
    assert stat.source is None


# ---------------------------------------------------------------------------
# test_table_row_optional_col3
# ---------------------------------------------------------------------------

def test_table_row_optional_col3():
    """TableRow with only col1+col2 is valid; col3 defaults to None."""
    row = TableRow(label="Metric", col1="Value A", col2="Value B")
    assert row.col3 is None
    assert row.label == "Metric"
