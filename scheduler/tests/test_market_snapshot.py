"""
Tests for services.market_snapshot — quick-260420-oa1.

All 12 unit tests covering:
  1.  Happy-path: both sources return good JSON
  2.  FRED 500 (partial)
  3.  Metals 429 (partial)
  4.  Both fail
  5.  Missing FRED key logs WARNING
  6.  Missing metalpriceapi key logs WARNING
  7.  Malformed JSON from a source
  8.  metalpriceapi direct price read (no inversion)
  9.  FRED "." missing-observation sentinel
  10. render_snapshot_block populated
  11. render_snapshot_block fallback (all None)
  12. CPI YoY computation from 12-month-apart observations
"""
import os
import sys
import logging
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Required env vars before any imports
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://fake-pooler.neon.tech/db?sslmode=require")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test-fake")
os.environ.setdefault("TWILIO_ACCOUNT_SID", "x")
os.environ.setdefault("TWILIO_AUTH_TOKEN", "x")
os.environ.setdefault("TWILIO_WHATSAPP_FROM", "whatsapp:+1x")
os.environ.setdefault("DIGEST_WHATSAPP_TO", "whatsapp:+1x")
os.environ.setdefault("X_API_BEARER_TOKEN", "test-bearer-token")
os.environ.setdefault("FRED_API_KEY", "test-fred-key")
os.environ.setdefault("METALPRICEAPI_API_KEY", "test-metals-key")


def _get_market_snapshot():
    """Lazy import so tests are collectable before module exists (TDD RED state)."""
    import importlib
    return importlib.import_module("services.market_snapshot")


# ---------------------------------------------------------------------------
# Helper: build mock httpx response
# ---------------------------------------------------------------------------

def _mock_httpx_response(status_code: int, json_body: dict | None = None, text_body: str | None = None):
    """Create a mock httpx.Response-like object."""
    mock = MagicMock()
    mock.status_code = status_code
    if json_body is not None:
        mock.json.return_value = json_body
    elif text_body is not None:
        mock.text = text_body
        mock.json.side_effect = Exception("invalid JSON")
    if status_code >= 400:
        import httpx
        mock.raise_for_status.side_effect = httpx.HTTPStatusError(
            f"HTTP {status_code}",
            request=MagicMock(),
            response=mock,
        )
    else:
        mock.raise_for_status.return_value = None
    return mock


# ---------------------------------------------------------------------------
# FRED response fixtures
# ---------------------------------------------------------------------------

FRED_DGS10_GOOD = {
    "observations": [
        {"date": "2026-04-19", "value": "4.12"},
        {"date": "2026-04-18", "value": "4.08"},
    ]
}

FRED_DFII10_GOOD = {
    "observations": [
        {"date": "2026-04-19", "value": "1.87"},
        {"date": "2026-04-18", "value": "1.85"},
    ]
}

FRED_DFF_GOOD = {
    "observations": [
        {"date": "2026-04-19", "value": "5.33"},
        {"date": "2026-04-18", "value": "5.33"},
    ]
}

# CPI: 13 observations for YoY — only latest and year-ago matter for the assertions
FRED_CPI_GOOD = {
    "observations": [
        {"date": "2026-03-01", "value": "310.326"},
        {"date": "2026-02-01", "value": "309.0"},
        {"date": "2026-01-01", "value": "308.0"},
        {"date": "2025-12-01", "value": "307.0"},
        {"date": "2025-11-01", "value": "306.0"},
        {"date": "2025-10-01", "value": "305.0"},
        {"date": "2025-09-01", "value": "304.0"},
        {"date": "2025-08-01", "value": "303.0"},
        {"date": "2025-07-01", "value": "302.0"},
        {"date": "2025-06-01", "value": "301.0"},
        {"date": "2025-05-01", "value": "300.0"},
        {"date": "2025-04-01", "value": "299.0"},
        {"date": "2025-03-01", "value": "300.84"},
    ]
}

METALS_GOOD = {
    "rates": {
        "USDXAU": 4816.39,
        "USDXAG": 79.58,
    },
    "timestamp": 1745280000,
}


def _make_fred_get_side_effect(dgs10=FRED_DGS10_GOOD, dfii10=FRED_DFII10_GOOD,
                                dff=FRED_DFF_GOOD, cpi=FRED_CPI_GOOD):
    """Returns an AsyncMock side_effect for client.get() that dispatches based on series_id param."""
    responses = {
        "DGS10": _mock_httpx_response(200, dgs10),
        "DFII10": _mock_httpx_response(200, dfii10),
        "DFF": _mock_httpx_response(200, dff),
        "CPIAUCSL": _mock_httpx_response(200, cpi),
    }

    async def _side_effect(url, **kwargs):
        params = kwargs.get("params", {})
        series_id = params.get("series_id", "")
        return responses.get(series_id, _mock_httpx_response(200, {"observations": []}))

    return _side_effect


# ---------------------------------------------------------------------------
# Test 1: Happy path — both sources return good JSON
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_snapshot_happy_path():
    """Both fetchers return good JSON. All 6 fields populated, status=='ok', no errors."""
    ms = _get_market_snapshot()

    async def _get_side_effect(url, **kwargs):
        if "metalpriceapi" in url:
            return _mock_httpx_response(200, METALS_GOOD)
        params = kwargs.get("params", {})
        series_id = params.get("series_id", "")
        responses = {
            "DGS10": _mock_httpx_response(200, FRED_DGS10_GOOD),
            "DFII10": _mock_httpx_response(200, FRED_DFII10_GOOD),
            "DFF": _mock_httpx_response(200, FRED_DFF_GOOD),
            "CPIAUCSL": _mock_httpx_response(200, FRED_CPI_GOOD),
        }
        return responses.get(series_id, _mock_httpx_response(200, {"observations": []}))

    with patch.dict(os.environ, {"FRED_API_KEY": "test-key", "METALPRICEAPI_API_KEY": "test-metals"}):
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=_get_side_effect)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            snap = await ms.fetch_market_snapshot(session=None)

    assert snap["gold_usd_per_oz"] is not None
    assert snap["silver_usd_per_oz"] is not None
    assert snap["ust_10y_nominal"] is not None
    assert snap["ust_10y_real"] is not None
    assert snap["fed_funds"] is not None
    assert snap["cpi_yoy"] is not None
    assert snap["cpi_observation_date"] is not None
    assert snap["status"] == "ok"
    assert snap["errors"] == {}


# ---------------------------------------------------------------------------
# Test 2: FRED 500 (partial) — metals OK, FRED all None
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_fred_500_partial():
    """FRED returns 500. FRED fields all None, metals populated, status=='partial'."""
    ms = _get_market_snapshot()

    async def _get_side_effect(url, **kwargs):
        if "metalpriceapi" in url:
            return _mock_httpx_response(200, METALS_GOOD)
        return _mock_httpx_response(500)

    with patch.dict(os.environ, {"FRED_API_KEY": "test-key", "METALPRICEAPI_API_KEY": "test-metals"}):
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=_get_side_effect)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            snap = await ms.fetch_market_snapshot(session=None)

    assert snap["ust_10y_nominal"] is None
    assert snap["ust_10y_real"] is None
    assert snap["fed_funds"] is None
    assert snap["cpi_yoy"] is None
    assert snap["gold_usd_per_oz"] is not None
    assert snap["silver_usd_per_oz"] is not None
    assert snap["status"] == "partial"
    assert "fred" in snap["errors"]


# ---------------------------------------------------------------------------
# Test 3: Metals 429 (partial) — FRED OK, metals None
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_metals_429_partial():
    """Metals returns 429. Metals fields None, FRED populated, status=='partial'."""
    ms = _get_market_snapshot()

    async def _get_side_effect(url, **kwargs):
        if "metalpriceapi" in url:
            return _mock_httpx_response(429)
        params = kwargs.get("params", {})
        series_id = params.get("series_id", "")
        responses = {
            "DGS10": _mock_httpx_response(200, FRED_DGS10_GOOD),
            "DFII10": _mock_httpx_response(200, FRED_DFII10_GOOD),
            "DFF": _mock_httpx_response(200, FRED_DFF_GOOD),
            "CPIAUCSL": _mock_httpx_response(200, FRED_CPI_GOOD),
        }
        return responses.get(series_id, _mock_httpx_response(200, {"observations": []}))

    with patch.dict(os.environ, {"FRED_API_KEY": "test-key", "METALPRICEAPI_API_KEY": "test-metals"}):
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=_get_side_effect)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            snap = await ms.fetch_market_snapshot(session=None)

    assert snap["gold_usd_per_oz"] is None
    assert snap["silver_usd_per_oz"] is None
    assert snap["ust_10y_nominal"] is not None
    assert snap["status"] == "partial"
    assert "metals" in snap["errors"]


# ---------------------------------------------------------------------------
# Test 4: Both fail — all 6 fields None, status=='failed'
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_both_fail():
    """Both sources raise. All 6 fields None, status=='failed', errors dict has 2 entries."""
    ms = _get_market_snapshot()
    import httpx

    async def _get_side_effect(url, **kwargs):
        raise httpx.HTTPStatusError("fail", request=MagicMock(), response=MagicMock())

    with patch.dict(os.environ, {"FRED_API_KEY": "test-key", "METALPRICEAPI_API_KEY": "test-metals"}):
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=_get_side_effect)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            snap = await ms.fetch_market_snapshot(session=None)

    assert snap["gold_usd_per_oz"] is None
    assert snap["silver_usd_per_oz"] is None
    assert snap["ust_10y_nominal"] is None
    assert snap["ust_10y_real"] is None
    assert snap["fed_funds"] is None
    assert snap["cpi_yoy"] is None
    assert snap["status"] == "failed"
    assert len(snap["errors"]) == 2


# ---------------------------------------------------------------------------
# Test 5: Missing FRED key logs WARNING
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_missing_fred_key_logs_warning(caplog):
    """settings.fred_api_key=None. FRED skipped with WARNING. Metals still runs."""
    ms = _get_market_snapshot()

    async def _get_side_effect(url, **kwargs):
        if "metalpriceapi" in url:
            return _mock_httpx_response(200, METALS_GOOD)
        raise AssertionError("FRED should not be called without API key")

    env_no_fred = {
        "FRED_API_KEY": "",
        "METALPRICEAPI_API_KEY": "test-metals",
    }
    with patch.dict(os.environ, env_no_fred):
        # Also reset the lru_cache to pick up new settings
        import config as cfg
        cfg.get_settings.cache_clear()
        try:
            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.get = AsyncMock(side_effect=_get_side_effect)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client_cls.return_value = mock_client

                with caplog.at_level(logging.WARNING):
                    snap = await ms.fetch_market_snapshot(session=None)
        finally:
            cfg.get_settings.cache_clear()

    # FRED fields should be None (skipped)
    assert snap["ust_10y_nominal"] is None
    assert snap["cpi_yoy"] is None
    # Metals should still be populated
    assert snap["gold_usd_per_oz"] is not None
    # WARNING must have been logged
    assert any("missing_api_key" in r.message.lower() or "fred_api_key" in r.message.lower()
               for r in caplog.records), \
        f"Expected WARNING about missing FRED key. Got: {[r.message for r in caplog.records]}"


# ---------------------------------------------------------------------------
# Test 6: Missing metalpriceapi key logs WARNING
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_missing_metalpriceapi_key_logs_warning(caplog):
    """settings.metalpriceapi_api_key=None. Metals skipped with WARNING. FRED still runs."""
    ms = _get_market_snapshot()

    async def _get_side_effect(url, **kwargs):
        if "metalpriceapi" in url:
            raise AssertionError("Metals should not be called without API key")
        params = kwargs.get("params", {})
        series_id = params.get("series_id", "")
        responses = {
            "DGS10": _mock_httpx_response(200, FRED_DGS10_GOOD),
            "DFII10": _mock_httpx_response(200, FRED_DFII10_GOOD),
            "DFF": _mock_httpx_response(200, FRED_DFF_GOOD),
            "CPIAUCSL": _mock_httpx_response(200, FRED_CPI_GOOD),
        }
        return responses.get(series_id, _mock_httpx_response(200, {"observations": []}))

    env_no_metals = {
        "FRED_API_KEY": "test-key",
        "METALPRICEAPI_API_KEY": "",
    }
    with patch.dict(os.environ, env_no_metals):
        import config as cfg
        cfg.get_settings.cache_clear()
        try:
            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.get = AsyncMock(side_effect=_get_side_effect)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client_cls.return_value = mock_client

                with caplog.at_level(logging.WARNING):
                    snap = await ms.fetch_market_snapshot(session=None)
        finally:
            cfg.get_settings.cache_clear()

    assert snap["gold_usd_per_oz"] is None
    assert snap["silver_usd_per_oz"] is None
    assert snap["ust_10y_nominal"] is not None
    assert any("missing_api_key" in r.message.lower() or "metalpriceapi_api_key" in r.message.lower()
               for r in caplog.records), \
        f"Expected WARNING about missing metals key. Got: {[r.message for r in caplog.records]}"


# ---------------------------------------------------------------------------
# Test 7: Malformed JSON from a source
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_malformed_json_from_source():
    """FRED returns 200 but body is '<html>crash</html>'. Returns [UNAVAILABLE] for FRED, no crash."""
    ms = _get_market_snapshot()

    async def _get_side_effect(url, **kwargs):
        if "metalpriceapi" in url:
            return _mock_httpx_response(200, METALS_GOOD)
        # FRED returns 200 but malformed JSON
        mock = MagicMock()
        mock.status_code = 200
        mock.raise_for_status.return_value = None
        mock.json.side_effect = Exception("invalid JSON: <html>crash</html>")
        return mock

    with patch.dict(os.environ, {"FRED_API_KEY": "test-key", "METALPRICEAPI_API_KEY": "test-metals"}):
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=_get_side_effect)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            snap = await ms.fetch_market_snapshot(session=None)

    # FRED fields None, no exception propagated
    assert snap["ust_10y_nominal"] is None
    assert snap["cpi_yoy"] is None
    # Metals still works
    assert snap["gold_usd_per_oz"] is not None


# ---------------------------------------------------------------------------
# Test 8: metalpriceapi direct price read (no inversion)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_metalpriceapi_direct_price_read():
    """USDXAU=4816.39 → gold=$4816.39/oz; USDXAG=79.58 → silver=$79.58/oz (direct USD/oz, no inversion)."""
    ms = _get_market_snapshot()

    metals_response = {
        "rates": {
            "USDXAU": 4816.39,
            "USDXAG": 79.58,
        },
        "timestamp": 1745280000,
    }

    async def _get_side_effect(url, **kwargs):
        if "metalpriceapi" in url:
            return _mock_httpx_response(200, metals_response)
        return _mock_httpx_response(500)  # FRED fails — we don't care for this test

    with patch.dict(os.environ, {"FRED_API_KEY": "test-key", "METALPRICEAPI_API_KEY": "test-metals"}):
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=_get_side_effect)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            snap = await ms.fetch_market_snapshot(session=None)

    assert snap["gold_usd_per_oz"] == pytest.approx(4816.39, rel=1e-4)
    assert snap["silver_usd_per_oz"] == pytest.approx(79.58, rel=1e-4)


# ---------------------------------------------------------------------------
# Test 9: FRED "." missing-observation sentinel
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fred_dot_missing_observation():
    """
    Case A: DGS10 returns '.' for latest, '4.12' for 2nd. Falls back to 4.12.
    Case B: CPI where both observations are '.'. Returns cpi_yoy=None (no crash).
    """
    ms = _get_market_snapshot()

    # Case A: DGS10 latest is ".", fallback to 2nd observation
    dgs10_with_dot = {
        "observations": [
            {"date": "2026-04-19", "value": "."},
            {"date": "2026-04-18", "value": "4.12"},
        ]
    }

    # Case B: CPI has both "." — YoY is None
    cpi_all_dots = {
        "observations": [
            {"date": "2026-04-01", "value": "."},
            {"date": "2026-03-01", "value": "."},
            {"date": "2026-02-01", "value": "."},
            {"date": "2026-01-01", "value": "."},
            {"date": "2025-12-01", "value": "."},
            {"date": "2025-11-01", "value": "."},
            {"date": "2025-10-01", "value": "."},
            {"date": "2025-09-01", "value": "."},
            {"date": "2025-08-01", "value": "."},
            {"date": "2025-07-01", "value": "."},
            {"date": "2025-06-01", "value": "."},
            {"date": "2025-05-01", "value": "."},
            {"date": "2025-04-01", "value": "."},
        ]
    }

    # First, test Case A (DGS10 fallback)
    async def _get_side_effect_a(url, **kwargs):
        if "metalpriceapi" in url:
            return _mock_httpx_response(200, METALS_GOOD)
        params = kwargs.get("params", {})
        series_id = params.get("series_id", "")
        responses = {
            "DGS10": _mock_httpx_response(200, dgs10_with_dot),
            "DFII10": _mock_httpx_response(200, FRED_DFII10_GOOD),
            "DFF": _mock_httpx_response(200, FRED_DFF_GOOD),
            "CPIAUCSL": _mock_httpx_response(200, FRED_CPI_GOOD),
        }
        return responses.get(series_id, _mock_httpx_response(200, {"observations": []}))

    with patch.dict(os.environ, {"FRED_API_KEY": "test-key", "METALPRICEAPI_API_KEY": "test-metals"}):
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=_get_side_effect_a)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            snap_a = await ms.fetch_market_snapshot(session=None)

    # Case A: Falls back to 2nd observation 4.12
    assert snap_a["ust_10y_nominal"] == pytest.approx(4.12, rel=1e-4)

    # Now test Case B (CPI all dots)
    async def _get_side_effect_b(url, **kwargs):
        if "metalpriceapi" in url:
            return _mock_httpx_response(200, METALS_GOOD)
        params = kwargs.get("params", {})
        series_id = params.get("series_id", "")
        responses = {
            "DGS10": _mock_httpx_response(200, FRED_DGS10_GOOD),
            "DFII10": _mock_httpx_response(200, FRED_DFII10_GOOD),
            "DFF": _mock_httpx_response(200, FRED_DFF_GOOD),
            "CPIAUCSL": _mock_httpx_response(200, cpi_all_dots),
        }
        return responses.get(series_id, _mock_httpx_response(200, {"observations": []}))

    with patch.dict(os.environ, {"FRED_API_KEY": "test-key", "METALPRICEAPI_API_KEY": "test-metals"}):
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=_get_side_effect_b)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            snap_b = await ms.fetch_market_snapshot(session=None)

    # Case B: cpi_yoy is None (all dots), no crash
    assert snap_b["cpi_yoy"] is None
    # DGS10 is still populated from good data
    assert snap_b["ust_10y_nominal"] is not None


# ---------------------------------------------------------------------------
# Test 10: render_snapshot_block populated
# ---------------------------------------------------------------------------

def test_render_snapshot_block_populated():
    """render_snapshot_block with all 6 fields returns the correct formatted block."""
    ms = _get_market_snapshot()

    snap = {
        "fetched_at": datetime(2026, 4, 21, 0, 30, 0, tzinfo=timezone.utc),
        "status": "ok",
        "gold_usd_per_oz": 2345.67,
        "silver_usd_per_oz": 27.89,
        "ust_10y_nominal": 4.12,
        "ust_10y_real": 1.87,
        "fed_funds": 5.33,
        "cpi_yoy": 3.2,
        "cpi_observation_date": "2026-03-01",
        "errors": {},
    }

    block = ms.render_snapshot_block(snap)

    # Header present
    assert "CURRENT MARKET SNAPSHOT" in block
    assert "2026-04-21" in block
    # Gold value formatted
    assert "$2,345.67/oz" in block
    # Silver value
    assert "$27.89/oz" in block
    # Yields with %
    assert "4.12%" in block
    assert "1.87%" in block
    assert "5.33%" in block
    # CPI with observation date
    assert "3.20%" in block or "3.2%" in block
    assert "March 2026 print" in block
    # Hard instruction
    assert "Do not cite any specific dollar figures, percentages, yields, or rates — current or historical —" in block
    # Snapshot block must precede "You are a senior gold market analyst" if injected first
    assert "as of" in block.lower()


# ---------------------------------------------------------------------------
# Test 11: render_snapshot_block fallback (all None)
# ---------------------------------------------------------------------------

def test_render_snapshot_block_unavailable():
    """Snapshot with all None fields renders fallback header + [UNAVAILABLE] + hard instruction."""
    ms = _get_market_snapshot()

    snap = {
        "fetched_at": datetime(2026, 4, 21, 0, 30, 0, tzinfo=timezone.utc),
        "status": "failed",
        "gold_usd_per_oz": None,
        "silver_usd_per_oz": None,
        "ust_10y_nominal": None,
        "ust_10y_real": None,
        "fed_funds": None,
        "cpi_yoy": None,
        "cpi_observation_date": None,
        "errors": {"fred": "500", "metals": "timeout"},
    }

    block = ms.render_snapshot_block(snap)

    # Fallback header
    assert "CURRENT MARKET SNAPSHOT" in block
    assert "fetch failed" in block.lower() or "failed" in block.lower()
    # All metrics show [UNAVAILABLE]
    unavailable_count = block.count("[UNAVAILABLE]")
    assert unavailable_count >= 5, f"Expected >=5 [UNAVAILABLE] entries, got {unavailable_count}"
    # Hard instruction still present
    assert "Do not cite any specific dollar figures, percentages, yields, or rates — current or historical —" in block


# ---------------------------------------------------------------------------
# Test 12: CPI YoY computation from 12-month-apart observations
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cpi_yoy_computation():
    """
    FRED CPI returns latest=310.326 (2026-03-01) and year-ago=300.84 (2025-03-01).
    Asserts cpi_yoy ≈ 3.15 and cpi_observation_date renders as 'March 2026 print'.
    """
    ms = _get_market_snapshot()

    cpi_data = {
        "observations": [
            {"date": "2026-03-01", "value": "310.326"},
            {"date": "2026-02-01", "value": "309.0"},
            {"date": "2026-01-01", "value": "308.0"},
            {"date": "2025-12-01", "value": "307.0"},
            {"date": "2025-11-01", "value": "306.0"},
            {"date": "2025-10-01", "value": "305.0"},
            {"date": "2025-09-01", "value": "304.0"},
            {"date": "2025-08-01", "value": "303.0"},
            {"date": "2025-07-01", "value": "302.0"},
            {"date": "2025-06-01", "value": "301.0"},
            {"date": "2025-05-01", "value": "300.0"},
            {"date": "2025-04-01", "value": "299.0"},
            {"date": "2025-03-01", "value": "300.84"},  # year-ago
        ]
    }

    async def _get_side_effect(url, **kwargs):
        if "metalpriceapi" in url:
            return _mock_httpx_response(200, METALS_GOOD)
        params = kwargs.get("params", {})
        series_id = params.get("series_id", "")
        responses = {
            "DGS10": _mock_httpx_response(200, FRED_DGS10_GOOD),
            "DFII10": _mock_httpx_response(200, FRED_DFII10_GOOD),
            "DFF": _mock_httpx_response(200, FRED_DFF_GOOD),
            "CPIAUCSL": _mock_httpx_response(200, cpi_data),
        }
        return responses.get(series_id, _mock_httpx_response(200, {"observations": []}))

    with patch.dict(os.environ, {"FRED_API_KEY": "test-key", "METALPRICEAPI_API_KEY": "test-metals"}):
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=_get_side_effect)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            snap = await ms.fetch_market_snapshot(session=None)

    # YoY: (310.326 - 300.84) / 300.84 * 100 ≈ 3.153
    assert snap["cpi_yoy"] == pytest.approx(3.15, abs=0.01)
    # Observation date should be 2026-03-01
    assert snap["cpi_observation_date"] == "2026-03-01"

    # Render block should contain "March 2026 print"
    block = ms.render_snapshot_block(snap)
    assert "March 2026 print" in block


# ---------------------------------------------------------------------------
# ep9 anchor tests (Tests 13-20) — temporal anchors + render + hard instruction
# ---------------------------------------------------------------------------


class _MockAnchorSession:
    """Mock AsyncSession for _compute_gold_anchors tests.

    Each call to execute() pops the next pre-built value from self._results.
    - Aggregate tuples (5-tuple of h24_high, h24_low, w52_high, w52_low, tracking_since)
      are wrapped to return .one() yielding a row whose attributes match those labels.
    - Scalar values (int/float/None) are returned via .scalar_one_or_none().

    The .add(...) / .flush() entry points mimic AsyncSession just enough that
    fetch_market_snapshot's DB-write block does not crash.
    """

    def __init__(self, combined_row, prior_close):
        self._results = [combined_row, prior_close]
        self.add = MagicMock()
        self.flush = AsyncMock()

    async def execute(self, q):  # noqa: ARG002 — query object unused in mock
        mock_result = MagicMock()
        val = self._results.pop(0)
        if isinstance(val, tuple):
            row = MagicMock()
            (
                row.h24_high,
                row.h24_low,
                row.w52_high,
                row.w52_low,
                row.tracking_since,
            ) = val
            mock_result.one.return_value = row
        else:
            mock_result.scalar_one_or_none.return_value = val
        return mock_result


def _build_fred_metals_side_effect(gold_spot: float = 4816.39):
    """Standard happy-path FRED + metals side_effect, with configurable gold spot."""
    metals_good = {
        "rates": {"USDXAU": gold_spot, "USDXAG": 79.58},
        "timestamp": 1745280000,
    }

    async def _get_side_effect(url, **kwargs):
        if "metalpriceapi" in url:
            return _mock_httpx_response(200, metals_good)
        params = kwargs.get("params", {})
        series_id = params.get("series_id", "")
        responses = {
            "DGS10": _mock_httpx_response(200, FRED_DGS10_GOOD),
            "DFII10": _mock_httpx_response(200, FRED_DFII10_GOOD),
            "DFF": _mock_httpx_response(200, FRED_DFF_GOOD),
            "CPIAUCSL": _mock_httpx_response(200, FRED_CPI_GOOD),
        }
        return responses.get(series_id, _mock_httpx_response(200, {"observations": []}))

    return _get_side_effect


# ---------------------------------------------------------------------------
# Test 13: anchors populated (full history, current below 52w high)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_anchors_populated_full_history():
    """Full history: 24h + 52w anchors populated, current_spot < 52w_high → at_52w_high false."""
    ms = _get_market_snapshot()

    # Current spot will be 4816.39 (from metals mock). 52w high = 4821.00 → below high.
    tracking_since_dt = datetime(2025, 4, 22, 12, 0, tzinfo=timezone.utc)
    combined_row = (4821.00, 4785.12, 4821.00, 3211.00, tracking_since_dt)
    prior_close = 4809.50
    session = _MockAnchorSession(combined_row, prior_close)

    with patch.dict(os.environ, {"FRED_API_KEY": "test-key", "METALPRICEAPI_API_KEY": "test-metals"}):
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=_build_fred_metals_side_effect(gold_spot=4816.39))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            snap = await ms.fetch_market_snapshot(session=session)

    assert snap["gold_24h_high"] == pytest.approx(4821.00, rel=1e-4)
    assert snap["gold_24h_low"] == pytest.approx(4785.12, rel=1e-4)
    assert snap["gold_52w_high"] == pytest.approx(4821.00, rel=1e-4)
    assert snap["gold_52w_low"] == pytest.approx(3211.00, rel=1e-4)
    assert snap["gold_prior_close"] == pytest.approx(4809.50, rel=1e-4)
    assert snap["at_52w_high"] is False  # 4816.39 < 4821.00
    assert snap["tracking_since"] == "2025-04-22"


# ---------------------------------------------------------------------------
# Test 14: anchors empty history (brand new DB — zero rows)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_anchors_empty_history():
    """Empty table: all 5 anchors None, at_52w_high None (NOT false), tracking_since None."""
    ms = _get_market_snapshot()

    combined_row = (None, None, None, None, None)
    prior_close = None
    session = _MockAnchorSession(combined_row, prior_close)

    with patch.dict(os.environ, {"FRED_API_KEY": "test-key", "METALPRICEAPI_API_KEY": "test-metals"}):
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=_build_fred_metals_side_effect())
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            snap = await ms.fetch_market_snapshot(session=session)

    assert snap["gold_24h_high"] is None
    assert snap["gold_24h_low"] is None
    assert snap["gold_52w_high"] is None
    assert snap["gold_52w_low"] is None
    assert snap["gold_prior_close"] is None
    assert snap["at_52w_high"] is None  # strictly None, not False
    assert snap["tracking_since"] is None
    # Snapshot fetch itself succeeded (metals + FRED both ok)
    assert snap["status"] == "ok"


# ---------------------------------------------------------------------------
# Test 15: anchors partial history — 24h populated, 52w None
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_anchors_partial_history_24h_only():
    """24h populated, 52w None (as if table only has last-24h rows). tracking_since is set."""
    ms = _get_market_snapshot()

    # 24h high/low populated; 52w high/low None (filter yielded nothing outside 24h)
    # NOTE: in the real query the 52w MAX/MIN *would* include 24h rows — this is a mock
    # that simulates the edge where the SQL returned all-None for 52w (unlikely in prod
    # but the render_block must handle it gracefully).
    tracking_since_dt = datetime(2026, 4, 21, 14, 0, tzinfo=timezone.utc)
    combined_row = (4821.00, 4785.12, None, None, tracking_since_dt)
    prior_close = 4809.50
    session = _MockAnchorSession(combined_row, prior_close)

    with patch.dict(os.environ, {"FRED_API_KEY": "test-key", "METALPRICEAPI_API_KEY": "test-metals"}):
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=_build_fred_metals_side_effect())
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            snap = await ms.fetch_market_snapshot(session=session)

    assert snap["gold_24h_high"] == pytest.approx(4821.00, rel=1e-4)
    assert snap["gold_24h_low"] == pytest.approx(4785.12, rel=1e-4)
    assert snap["gold_52w_high"] is None
    assert snap["gold_52w_low"] is None
    assert snap["gold_prior_close"] == pytest.approx(4809.50, rel=1e-4)
    assert snap["at_52w_high"] is None  # 52w high unknown
    assert snap["tracking_since"] == "2026-04-21"


# ---------------------------------------------------------------------------
# Test 16: render_block with populated anchors
# ---------------------------------------------------------------------------

def test_render_block_anchors_populated():
    """render_snapshot_block emits 'Gold 24h range:' and 'Gold 52w range:' lines with values."""
    ms = _get_market_snapshot()

    snap = {
        "fetched_at": datetime(2026, 4, 22, 20, 0, 0, tzinfo=timezone.utc),
        "status": "ok",
        "gold_usd_per_oz": 4816.39,
        "silver_usd_per_oz": 79.58,
        "ust_10y_nominal": 4.12,
        "ust_10y_real": 1.87,
        "fed_funds": 5.33,
        "cpi_yoy": 3.15,
        "cpi_observation_date": "2026-03-01",
        "gold_24h_high": 4821.00,
        "gold_24h_low": 4785.12,
        "gold_prior_close": 4809.50,
        "gold_52w_high": 4821.00,
        "gold_52w_low": 3211.00,
        "at_52w_high": False,
        "tracking_since": "2025-04-22",
        "errors": {},
    }

    block = ms.render_snapshot_block(snap)

    # Two new anchor lines present
    assert "Gold 24h range:" in block
    assert "Gold 52w range:" in block

    # Numeric values (use membership — separator may be en-dash or hyphen)
    assert "$4,785.12" in block
    assert "$4,821.00" in block
    assert "$3,211.00" in block

    # prior close inline suffix
    assert "prior close" in block
    assert "$4,809.50/oz" in block

    # at_52w_high binary
    assert "at_52w_high: false" in block

    # Position: after "Spot silver" and before "10Y Treasury yield"
    silver_idx = block.index("Spot silver")
    g24h_idx = block.index("Gold 24h range")
    g52w_idx = block.index("Gold 52w range")
    ust_idx = block.index("10Y Treasury yield")
    assert silver_idx < g24h_idx < g52w_idx < ust_idx


# ---------------------------------------------------------------------------
# Test 17: render_block anchors empty (first snapshot)
# ---------------------------------------------------------------------------

def test_render_block_anchors_empty():
    """All 5 anchors None + tracking_since None → '[UNAVAILABLE — first snapshot]' in both lines."""
    ms = _get_market_snapshot()

    snap = {
        "fetched_at": datetime(2026, 4, 22, 20, 0, 0, tzinfo=timezone.utc),
        "status": "ok",
        "gold_usd_per_oz": 4816.39,
        "silver_usd_per_oz": 79.58,
        "ust_10y_nominal": 4.12,
        "ust_10y_real": 1.87,
        "fed_funds": 5.33,
        "cpi_yoy": 3.15,
        "cpi_observation_date": "2026-03-01",
        "gold_24h_high": None,
        "gold_24h_low": None,
        "gold_prior_close": None,
        "gold_52w_high": None,
        "gold_52w_low": None,
        "at_52w_high": None,
        "tracking_since": None,
        "errors": {},
    }

    block = ms.render_snapshot_block(snap)

    assert "Gold 24h range: [UNAVAILABLE" in block
    assert "Gold 52w range: [UNAVAILABLE" in block
    assert "first snapshot" in block

    # No leaked None / literal "$None"
    assert "$None" not in block
    assert "None/oz" not in block


# ---------------------------------------------------------------------------
# Test 18: render_block anchors partial with tracking_since fallback
# ---------------------------------------------------------------------------

def test_render_block_anchors_partial_with_tracking_since():
    """24h populated, 52w None, tracking_since set → 52w line emits 'tracking since ...' + 'of history'."""
    ms = _get_market_snapshot()

    snap = {
        "fetched_at": datetime(2026, 4, 22, 20, 0, 0, tzinfo=timezone.utc),
        "status": "ok",
        "gold_usd_per_oz": 4816.39,
        "silver_usd_per_oz": 79.58,
        "ust_10y_nominal": 4.12,
        "ust_10y_real": 1.87,
        "fed_funds": 5.33,
        "cpi_yoy": 3.15,
        "cpi_observation_date": "2026-03-01",
        "gold_24h_high": 4821.00,
        "gold_24h_low": 4785.12,
        "gold_prior_close": 4809.50,
        "gold_52w_high": None,
        "gold_52w_low": None,
        "at_52w_high": None,
        "tracking_since": "2026-04-21",
        "errors": {},
    }

    block = ms.render_snapshot_block(snap)

    # 24h line has real values
    assert "$4,785.12" in block
    assert "$4,821.00" in block
    assert "prior close" in block

    # 52w line emits tracking_since fallback
    assert "tracking since 2026-04-21" in block
    assert "of history" in block


# ---------------------------------------------------------------------------
# Test 19: at_52w_high strict equality — ATH and 0.999*high cases
# ---------------------------------------------------------------------------

def test_at_52w_high_strict_equality():
    """Strict equality: current >= 52w_high → true; current = 0.999 * 52w_high → false."""
    ms = _get_market_snapshot()

    base_snap = {
        "fetched_at": datetime(2026, 4, 22, 20, 0, 0, tzinfo=timezone.utc),
        "status": "ok",
        "silver_usd_per_oz": 79.58,
        "ust_10y_nominal": 4.12,
        "ust_10y_real": 1.87,
        "fed_funds": 5.33,
        "cpi_yoy": 3.15,
        "cpi_observation_date": "2026-03-01",
        "gold_24h_high": 4821.00,
        "gold_24h_low": 4785.12,
        "gold_prior_close": 4809.50,
        "gold_52w_high": 4821.00,
        "gold_52w_low": 3211.00,
        "tracking_since": "2025-04-22",
        "errors": {},
    }

    # Case A: current == 52w high → at_52w_high True
    snap_a = {**base_snap, "gold_usd_per_oz": 4821.00, "at_52w_high": True}
    block_a = ms.render_snapshot_block(snap_a)
    assert "at_52w_high: true" in block_a

    # Case B: current = 0.999 * 52w high → at_52w_high False
    snap_b = {**base_snap, "gold_usd_per_oz": 4821.00 * 0.999, "at_52w_high": False}
    block_b = ms.render_snapshot_block(snap_b)
    assert "at_52w_high: false" in block_b


# ---------------------------------------------------------------------------
# Test 20: _HARD_INSTRUCTION extended forbidden-phrase list
# ---------------------------------------------------------------------------

def test_hard_instruction_contains_forbidden_phrases():
    """_HARD_INSTRUCTION module constant contains all forbidden-phrase guardrail tokens."""
    ms = _get_market_snapshot()

    hi = ms._HARD_INSTRUCTION
    # First paragraph (original, unchanged)
    assert "Do not cite any specific dollar figures" in hi

    # Second paragraph forbidden phrases
    assert "at highs" in hi
    assert "at a new high" in hi
    assert "at an all-time high" in hi
    assert "breaking out" in hi
    assert "at a record" in hi
    assert "hitting a new record" in hi

    # Intraday-move guidance
    assert "$100+ intraday" in hi
    assert "whipsaws" in hi
    assert "% move today" in hi

    # Signal reference
    assert "at_52w_high: true" in hi
