"""Tests for scheduler/agents/ontario_stats.py — Phase 3, Plan 01.

Coverage (tests matching plan behaviour list):
  FRESH: WDS returns new releaseTime > previous → state='fresh', correct parsing
  NO_NEW_DATA: WDS returns same releaseTime → state='no_new_data'
  FIRST_EVER_FIRE: previous_release_time=None + valid WDS data → state='fresh', no crash
  ERROR_HTTPX: httpx.HTTPError raised → state='error'
  ERROR_TIMEOUT: httpx.TimeoutException raised → state='error'
  ERROR_STATUS_NOT_SUCCESS: WDS status='FAILED' → state='error'
  ERROR_EMPTY_DATAPOINTS: WDS returns empty vectorDataPoint → state='error'
  MOM_POSITIVE: prior 7000, current 7140 → '+2.0%'
  MOM_NEGATIVE: prior 7559, current 7359 → '-2.6%'
  NUMBER_FORMATTING: 7359.0 → '7,359 kg'; 12345.0 → '12,345 kg'
  NEXT_RELEASE_FORMULA: 2026-02 → 'around May 20, 2026'; 2026-12 → 'around March 20, 2027'
  ENDPOINT_AND_BODY: httpx called with verbatim URL + JSON body
  CONSTANTS: WDS_ENDPOINT and ONTARIO_GOLD_VECTOR_ID exported with correct values
"""
from __future__ import annotations

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://fake-pooler.neon.tech/db?sslmode=require"
)
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test-fake")
os.environ.setdefault("X_API_BEARER_TOKEN", "x")
os.environ.setdefault("SERPAPI_API_KEY", "x")


from agents.ontario_stats import (  # noqa: E402
    ONTARIO_GOLD_VECTOR_ID,
    WDS_ENDPOINT,
    _compute_next_release_estimate,
    fetch_ontario_stats_snapshot,
    format_error_markdown,
    format_fresh_markdown,
    format_no_new_data_markdown,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_wds_payload(
    datapoints: list[dict] | None = None,
    status: str = "SUCCESS",
) -> list[dict]:
    """Build a minimal WDS-style response payload."""
    if datapoints is None:
        datapoints = [
            {"refPer": "2025-12-01", "value": 9203.0, "releaseTime": "2026-04-20T08:30"},
            {"refPer": "2026-01-01", "value": 7559.0, "releaseTime": "2026-04-20T08:30"},
            {"refPer": "2026-02-01", "value": 7359.0, "releaseTime": "2026-04-20T08:30"},
        ]
    return [{"status": status, "object": {"vectorId": ONTARIO_GOLD_VECTOR_ID, "vectorDataPoint": datapoints}}]


def _make_mock_client(payload: list[dict]) -> MagicMock:
    """Build a mock httpx.AsyncClient that returns the given payload."""
    mock_response = MagicMock()
    mock_response.json = MagicMock(return_value=payload)
    mock_response.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(return_value=mock_response)
    return mock_client


# ---------------------------------------------------------------------------
# Test FRESH — WDS returns releaseTime > previous
# ---------------------------------------------------------------------------

async def test_fresh_data_path():
    """FRESH: releaseTime > previous_release_time → state='fresh', correct fields."""
    payload = _make_wds_payload()
    mock_client = _make_mock_client(payload)

    with patch("agents.ontario_stats.httpx.AsyncClient", return_value=mock_client):
        result = await fetch_ontario_stats_snapshot(previous_release_time="2026-03-20T08:30")

    assert result.state == "fresh"
    assert result.figure_kg == 7359.0
    assert result.period == "2026-02"
    assert result.prior_period == "2026-01"
    assert result.prior_figure_kg == 7559.0
    assert result.release_time == "2026-04-20T08:30"
    assert result.error_text is None


# ---------------------------------------------------------------------------
# Test NO_NEW_DATA — same releaseTime as previous
# ---------------------------------------------------------------------------

async def test_no_new_data_path():
    """NO_NEW_DATA: releaseTime == previous_release_time → state='no_new_data'."""
    payload = _make_wds_payload()
    mock_client = _make_mock_client(payload)

    with patch("agents.ontario_stats.httpx.AsyncClient", return_value=mock_client):
        result = await fetch_ontario_stats_snapshot(previous_release_time="2026-04-20T08:30")

    assert result.state == "no_new_data"
    # All data fields should be None — caller propagates prior snapshot
    assert result.figure_kg is None
    assert result.period is None
    assert result.release_time is None
    assert result.error_text is None


# ---------------------------------------------------------------------------
# Test FIRST_EVER_FIRE — no previous_release_time (None) + valid WDS data
# ---------------------------------------------------------------------------

async def test_first_ever_fire_with_valid_data():
    """FIRST_EVER_FIRE: previous_release_time=None → state='fresh', does NOT crash."""
    payload = _make_wds_payload()
    mock_client = _make_mock_client(payload)

    with patch("agents.ontario_stats.httpx.AsyncClient", return_value=mock_client):
        result = await fetch_ontario_stats_snapshot(previous_release_time=None)

    assert result.state == "fresh"
    assert result.figure_kg == 7359.0
    assert result.period == "2026-02"


# ---------------------------------------------------------------------------
# Test ERROR_HTTPX — httpx.HTTPError raised
# ---------------------------------------------------------------------------

async def test_error_on_httpx_error():
    """ERROR_HTTPX: httpx.HTTPError → state='error', error_text set."""
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(side_effect=httpx.HTTPError("connection refused"))

    with patch("agents.ontario_stats.httpx.AsyncClient", return_value=mock_client):
        result = await fetch_ontario_stats_snapshot(previous_release_time=None)

    assert result.state == "error"
    assert result.error_text is not None
    assert result.figure_kg is None
    assert result.period is None
    assert result.release_time is None


# ---------------------------------------------------------------------------
# Test ERROR_TIMEOUT — httpx.TimeoutException raised
# ---------------------------------------------------------------------------

async def test_error_on_timeout_exception():
    """ERROR_TIMEOUT: httpx.TimeoutException → state='error', error_text mentions timeout."""
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timed out"))

    with patch("agents.ontario_stats.httpx.AsyncClient", return_value=mock_client):
        result = await fetch_ontario_stats_snapshot(previous_release_time=None)

    assert result.state == "error"
    assert result.error_text is not None
    # TimeoutException type name should appear in error text
    assert "Timeout" in result.error_text or "timeout" in result.error_text.lower()


# ---------------------------------------------------------------------------
# Test ERROR_STATUS_NOT_SUCCESS — WDS returns non-SUCCESS status
# ---------------------------------------------------------------------------

async def test_error_on_wds_non_success_status():
    """ERROR_STATUS_NOT_SUCCESS: WDS status='FAILED' → state='error'."""
    payload = _make_wds_payload(status="FAILED")
    mock_client = _make_mock_client(payload)

    with patch("agents.ontario_stats.httpx.AsyncClient", return_value=mock_client):
        result = await fetch_ontario_stats_snapshot(previous_release_time=None)

    assert result.state == "error"
    assert result.error_text is not None
    assert "FAILED" in result.error_text or "non-SUCCESS" in result.error_text or "SUCCESS" in result.error_text


# ---------------------------------------------------------------------------
# Test ERROR_EMPTY_DATAPOINTS — WDS returns empty vectorDataPoint list
# ---------------------------------------------------------------------------

async def test_error_on_empty_datapoints():
    """ERROR_EMPTY_DATAPOINTS: empty vectorDataPoint → state='error'."""
    payload = _make_wds_payload(datapoints=[])
    mock_client = _make_mock_client(payload)

    with patch("agents.ontario_stats.httpx.AsyncClient", return_value=mock_client):
        result = await fetch_ontario_stats_snapshot(previous_release_time=None)

    assert result.state == "error"
    assert result.error_text is not None
    assert (
        "no datapoints" in result.error_text.lower()
        or "empty" in result.error_text.lower()
    )


# ---------------------------------------------------------------------------
# Test MOM_POSITIVE — positive month-over-month percentage
# ---------------------------------------------------------------------------

async def test_mom_positive_percentage():
    """MOM_POSITIVE: prior=7000, current=7140 → markdown contains '+2.0%'."""
    from agents.ontario_stats import OntarioStatsResult

    result = OntarioStatsResult(
        state="fresh",
        figure_kg=7140.0,
        period="2026-02",
        release_time="2026-04-20T08:30",
        prior_period="2026-01",
        prior_figure_kg=7000.0,
    )
    md = format_fresh_markdown(result)
    assert "+2.0%" in md, f"Expected '+2.0%' in markdown, got: {md!r}"


# ---------------------------------------------------------------------------
# Test MOM_NEGATIVE — negative month-over-month percentage
# ---------------------------------------------------------------------------

async def test_mom_negative_percentage():
    """MOM_NEGATIVE: prior=7559, current=7359 → markdown contains '-2.6%'."""
    from agents.ontario_stats import OntarioStatsResult

    result = OntarioStatsResult(
        state="fresh",
        figure_kg=7359.0,
        period="2026-02",
        release_time="2026-04-20T08:30",
        prior_period="2026-01",
        prior_figure_kg=7559.0,
    )
    md = format_fresh_markdown(result)
    assert "-2.6%" in md, f"Expected '-2.6%' in markdown, got: {md!r}"


# ---------------------------------------------------------------------------
# Test NUMBER_FORMATTING — thousands separators
# ---------------------------------------------------------------------------

async def test_number_formatting_thousands_separator():
    """NUMBER_FORMATTING: 7359.0 → '7,359 kg'; 12345.0 → '12,345 kg'."""
    from agents.ontario_stats import OntarioStatsResult

    result = OntarioStatsResult(
        state="fresh",
        figure_kg=7359.0,
        period="2026-02",
        release_time="2026-04-20T08:30",
        prior_period=None,
        prior_figure_kg=None,
    )
    md = format_fresh_markdown(result)
    assert "7,359 kg" in md, f"Expected '7,359 kg' in markdown, got: {md!r}"

    result2 = OntarioStatsResult(
        state="fresh",
        figure_kg=12345.0,
        period="2026-02",
        release_time="2026-04-20T08:30",
        prior_period=None,
        prior_figure_kg=None,
    )
    md2 = format_fresh_markdown(result2)
    assert "12,345 kg" in md2, f"Expected '12,345 kg' in markdown, got: {md2!r}"


# ---------------------------------------------------------------------------
# Test NEXT_RELEASE_FORMULA — including year rollover
# ---------------------------------------------------------------------------

def test_next_release_estimate_basic():
    """NEXT_RELEASE_FORMULA: 2026-02 → 'around May 20, 2026'."""
    result = _compute_next_release_estimate("2026-02")
    assert result == "around May 20, 2026", f"Expected 'around May 20, 2026', got: {result!r}"


def test_next_release_estimate_year_rollover():
    """NEXT_RELEASE_FORMULA: 2026-12 → 'around March 20, 2027' (year rollover)."""
    result = _compute_next_release_estimate("2026-12")
    assert result == "around March 20, 2027", f"Expected 'around March 20, 2027', got: {result!r}"


def test_next_release_estimate_october():
    """NEXT_RELEASE_FORMULA: 2026-10 → 'around January 20, 2027' (year rollover)."""
    result = _compute_next_release_estimate("2026-10")
    assert result == "around January 20, 2027", f"Expected 'around January 20, 2027', got: {result!r}"


# ---------------------------------------------------------------------------
# Test ENDPOINT_AND_BODY — httpx called with verbatim URL + JSON body
# ---------------------------------------------------------------------------

async def test_endpoint_and_body():
    """ENDPOINT_AND_BODY: httpx.post called with exact URL and JSON body."""
    payload = _make_wds_payload()
    mock_client = _make_mock_client(payload)

    with patch("agents.ontario_stats.httpx.AsyncClient", return_value=mock_client):
        await fetch_ontario_stats_snapshot(previous_release_time=None)

    mock_client.post.assert_called_once()
    call_args = mock_client.post.call_args
    # URL is the first positional arg
    assert call_args.args[0] == (
        "https://www150.statcan.gc.ca/t1/wds/rest/getDataFromVectorsAndLatestNPeriods"
    ), f"Wrong URL: {call_args.args[0]}"
    # JSON body must be exactly [{"vectorId": 1146004456, "latestN": 3}]
    assert call_args.kwargs.get("json") == [{"vectorId": 1146004456, "latestN": 3}], (
        f"Wrong JSON body: {call_args.kwargs.get('json')}"
    )


# ---------------------------------------------------------------------------
# Test CONSTANTS — module-level constants exposed with correct values
# ---------------------------------------------------------------------------

def test_wds_endpoint_constant():
    """WDS_ENDPOINT must equal the verbatim endpoint URL."""
    expected = (
        "https://www150.statcan.gc.ca/t1/wds/rest/getDataFromVectorsAndLatestNPeriods"
    )
    assert WDS_ENDPOINT == expected, f"WDS_ENDPOINT mismatch: {WDS_ENDPOINT!r}"


def test_ontario_gold_vector_id_constant():
    """ONTARIO_GOLD_VECTOR_ID must equal 1146004456."""
    assert ONTARIO_GOLD_VECTOR_ID == 1146004456, (
        f"ONTARIO_GOLD_VECTOR_ID mismatch: {ONTARIO_GOLD_VECTOR_ID}"
    )


# ---------------------------------------------------------------------------
# Additional format tests
# ---------------------------------------------------------------------------

def test_format_fresh_markdown_with_mom_and_source():
    """format_fresh_markdown renders full template with MoM and source citation."""
    from agents.ontario_stats import OntarioStatsResult

    result = OntarioStatsResult(
        state="fresh",
        figure_kg=7359.0,
        period="2026-02",
        release_time="2026-04-20T08:30",
        prior_period="2026-01",
        prior_figure_kg=7559.0,
    )
    md = format_fresh_markdown(result)
    assert "**Ontario gold production for February 2026: 7,359 kg**" in md
    assert "vs 7,559 kg in January 2026" in md
    assert "Statistics Canada, Table 16-10-0019" in md
    assert "2026-04-20" in md


def test_format_no_new_data_markdown_with_prior_snapshot():
    """format_no_new_data_markdown with prior snapshot renders last data + estimate."""
    prior = {"period": "2026-02", "figure_kg": 7359.0, "release_time": "2026-04-20T08:30"}
    md = format_no_new_data_markdown(prior)
    assert "No new production statistics released today" in md
    assert "around May 20, 2026" in md
    assert "2026-02" in md
    assert "7,359 kg" in md


def test_format_no_new_data_markdown_first_ever_fire():
    """format_no_new_data_markdown with no prior snapshot → awaiting copy."""
    md = format_no_new_data_markdown(None)
    assert "Awaiting first StatCan release" in md


def test_format_error_markdown():
    """format_error_markdown renders warning glyph + agent_run_id."""
    md = format_error_markdown("HTTPError: connection refused", "abcdef12-1234-5678-abcd-ef1234567890")
    assert "⚠" in md
    assert "Ontario production statistics ingestion failed" in md
    assert "abcdef12" in md  # first 8 chars of UUID
    assert "agent_run_id" in md


def test_no_anthropic_or_serpapi_imports():
    """ontario_stats.py must NOT import anthropic or serpapi."""
    import agents.ontario_stats as stats_module
    assert not hasattr(stats_module, "AsyncAnthropic"), "anthropic must NOT be imported"
    assert not hasattr(stats_module, "serpapi"), "serpapi must NOT be imported"
