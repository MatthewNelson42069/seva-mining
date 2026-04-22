"""
Real-time market snapshot service — quick-260420-oa1.

Fetches spot gold + silver (metalpriceapi.com) and macro indicators
(FRED: 10Y nominal, 10Y real, Fed funds, CPI) once per content_agent cron
cycle (every 3h). Persists a market_snapshots row for audit. Injects a
CURRENT MARKET SNAPSHOT block + hard hallucination-guard instruction into
the Sonnet drafter system prompt at all three call sites.

Fail-open contract:
- Missing API key → WARNING log + [UNAVAILABLE] for that source
- Source HTTP error → [UNAVAILABLE] for that source only (other source unaffected)
- DB write failure → ERROR log but in-memory snapshot returned to caller
- Pipeline-level exception is caught by caller (ContentAgent._run_pipeline)

Module usage:
    from services.market_snapshot import fetch_market_snapshot, render_snapshot_block
    snap = await fetch_market_snapshot(session=session)
    block = render_snapshot_block(snap)
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional, TypedDict

import httpx
from sqlalchemy import Float, and_, cast, func, select

from config import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FRED series IDs
# ---------------------------------------------------------------------------

FRED_SERIES: dict[str, str] = {
    "ust_10y_nominal": "DGS10",    # 10Y Treasury Constant Maturity (daily, %)
    "ust_10y_real": "DFII10",      # 10Y Treasury Inflation-Indexed / TIPS (daily, %)
    "fed_funds": "DFF",             # Federal Funds Effective Rate (daily, %)
    "cpi_yoy": "CPIAUCSL",         # CPI All Urban Consumers (monthly, index — compute YoY)
}

FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"
METALS_URL = "https://api.metalpriceapi.com/v1/latest"

# ---------------------------------------------------------------------------
# Locked log format (verified at plan check time)
# ---------------------------------------------------------------------------

_LOG_FMT = (
    "ContentAgent: market snapshot fetch — %s failed (%s: %s) — "
    "falling back to [UNAVAILABLE] for this source."
)

_LOG_FMT_KEY = (
    "ContentAgent: market snapshot fetch — %s failed (missing_api_key: %s not set) — "
    "falling back to [UNAVAILABLE] for this source."
)

# ---------------------------------------------------------------------------
# Hard instruction (verbatim — plan spec)
# ---------------------------------------------------------------------------

_HARD_INSTRUCTION = (
    "Do not cite any specific dollar figures, percentages, yields, or rates — "
    "current or historical — that do not appear verbatim in this snapshot. "
    "Use qualitative language ('near recent highs', 'elevated', 'multi-year high') "
    "or omit the claim entirely.\n\n"
    "Do NOT claim the current price is 'at highs', 'at a new high', 'at an "
    "all-time high', 'breaking out', 'at a record', or 'hitting a new record' "
    "unless the snapshot emits `at_52w_high: true`. Do NOT claim specific "
    "intraday moves ('$100+ intraday', 'whipsaws $X', 'X% move today') unless "
    "the 24h high minus 24h low in this snapshot supports the magnitude. "
    "When in doubt, use qualitative hedges ('elevated', 'near recent highs', "
    "'volatile intraday') or omit the claim."
)


# ---------------------------------------------------------------------------
# MarketSnapshot TypedDict — in-memory shape
# ---------------------------------------------------------------------------

class MarketSnapshot(TypedDict, total=False):
    fetched_at: datetime
    status: Literal["ok", "partial", "failed"]
    gold_usd_per_oz: Optional[float]
    silver_usd_per_oz: Optional[float]
    ust_10y_nominal: Optional[float]
    ust_10y_real: Optional[float]
    fed_funds: Optional[float]
    cpi_yoy: Optional[float]
    cpi_observation_date: Optional[str]  # ISO date string "YYYY-MM-DD"
    # --- ep9 temporal anchors (quick-260422-ep9) ---
    gold_24h_high: Optional[float]
    gold_24h_low: Optional[float]
    gold_prior_close: Optional[float]
    gold_52w_high: Optional[float]
    gold_52w_low: Optional[float]
    at_52w_high: Optional[bool]        # None → [UNAVAILABLE]; True/False when gold_52w_high known
    tracking_since: Optional[str]      # ISO date "YYYY-MM-DD" (matches cpi_observation_date style)
    errors: dict  # per-source error messages


# ---------------------------------------------------------------------------
# FRED fetcher
# ---------------------------------------------------------------------------

async def _fetch_fred_series(
    client: httpx.AsyncClient,
    series_id: str,
    api_key: str,
    is_cpi: bool = False,
) -> dict | None:
    """Fetch a single FRED series. Returns parsed observations dict or None on failure.

    For rate series (DGS10/DFII10/DFF): requests limit=2, falls back to 2nd obs if latest is '.'.
    For CPIAUCSL: requests limit=13 to get 12-month-apart pair for YoY computation.
    """
    limit = 13 if is_cpi else 2
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "sort_order": "desc",
        "limit": limit,
    }
    try:
        r = await client.get(FRED_BASE_URL, params=params, timeout=10.0)
        r.raise_for_status()
        data = r.json()
        return data
    except Exception as exc:
        raise exc


def _parse_rate_value(observations: list[dict]) -> Optional[float]:
    """Parse a rate (non-CPI) series. Returns float or None. Guards '.' sentinel."""
    for obs in observations:
        val = obs.get("value", ".")
        if val != ".":
            try:
                return float(val)
            except (ValueError, TypeError):
                continue
    return None


def _parse_cpi_yoy(observations: list[dict]) -> tuple[Optional[float], Optional[str]]:
    """Compute CPI YoY from FRED observations (limit=13, sort_order=desc).

    Returns (yoy_pct, observation_date_str) or (None, None) if insufficient data.
    The year-ago observation is the 13th item in desc-sorted list (index 12).
    """
    # Filter out '.' values to get real observations
    valid_obs = [o for o in observations if o.get("value", ".") != "."]
    if len(valid_obs) < 2:
        return None, None

    # Latest valid observation
    latest = valid_obs[0]
    latest_date_str = latest.get("date", "")

    try:
        latest_val = float(latest["value"])
        latest_date = datetime.strptime(latest_date_str, "%Y-%m-%d")
    except (ValueError, KeyError):
        return None, None

    # Find the observation 12 months prior
    target_year = latest_date.year - 1
    target_month = latest_date.month
    # target_day stays same (FRED uses 1st of month)

    year_ago_val: Optional[float] = None
    for obs in valid_obs[1:]:
        try:
            obs_date = datetime.strptime(obs["date"], "%Y-%m-%d")
            if obs_date.year == target_year and obs_date.month == target_month:
                year_ago_val = float(obs["value"])
                break
        except (ValueError, KeyError):
            continue

    if year_ago_val is None or year_ago_val == 0:
        return None, None

    yoy = (latest_val - year_ago_val) / year_ago_val * 100
    return yoy, latest_date_str


# ---------------------------------------------------------------------------
# Metals fetcher
# ---------------------------------------------------------------------------

class MetalsFetcher:
    """Protocol-compatible interface for metals price fetching."""

    async def fetch(self, client: httpx.AsyncClient) -> dict | None:
        raise NotImplementedError


class MetalpriceAPIFetcher:
    """Fetches spot gold + silver from metalpriceapi.com.

    Response shape with base=USD returns USDXAU and USDXAG as direct USD-per-oz
    prices (e.g. USDXAU≈4816.39 means gold is $4,816.39/oz); read as-is, no
    inversion. The reciprocal fields XAU/XAG (without the USD prefix) are ignored.
    """

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    async def fetch(self, client: httpx.AsyncClient) -> dict | None:
        params = {
            "api_key": self.api_key,
            "base": "USD",
            "currencies": "XAU,XAG",
        }
        try:
            r = await client.get(METALS_URL, params=params, timeout=10.0)
            r.raise_for_status()
            data = r.json()
            rates = data.get("rates", {})
            gold = rates.get("USDXAU")
            silver = rates.get("USDXAG")
            return {"gold_usd_per_oz": gold, "silver_usd_per_oz": silver}
        except Exception as exc:
            raise exc


# ---------------------------------------------------------------------------
# Temporal anchors (ep9) — computed from market_snapshots table history
# ---------------------------------------------------------------------------

_ANCHOR_KEYS = (
    "gold_24h_high",
    "gold_24h_low",
    "gold_prior_close",
    "gold_52w_high",
    "gold_52w_low",
    "at_52w_high",
    "tracking_since",
)


async def _compute_gold_anchors(session, current_spot: Optional[float]) -> dict:
    """Compute gold temporal anchors from market_snapshots table history.

    Returns dict with 7 keys (24h high/low, prior_close, 52w high/low, at_52w_high
    binary, tracking_since ISO date). All values Optional — None on empty history.

    MUST be invoked BEFORE session.add(current_row) so `prior_close` reflects the
    last-written snapshot, not the in-flight one.

    Fail-open: any exception → all-None dict returned, error logged at ERROR level.
    Queries filter to rows where gold_usd_per_oz is not null AND status in ('ok',
    'partial') — status='failed' rows carry data.gold_usd_per_oz=null and must not
    contaminate anchors.
    """
    from models.market_snapshot import MarketSnapshot as MarketSnapshotORM  # noqa: PLC0415

    now = datetime.now(timezone.utc)
    gold_price = cast(MarketSnapshotORM.data["gold_usd_per_oz"].astext, Float)
    valid_row = and_(
        MarketSnapshotORM.data["gold_usd_per_oz"].astext != "null",
        MarketSnapshotORM.data["gold_usd_per_oz"].astext.isnot(None),
        MarketSnapshotORM.status.in_(("ok", "partial")),
    )

    # Combined aggregate query (5 labelled results in one row)
    q = select(
        func.max(gold_price).filter(
            and_(valid_row, MarketSnapshotORM.fetched_at >= now - timedelta(hours=24))
        ).label("h24_high"),
        func.min(gold_price).filter(
            and_(valid_row, MarketSnapshotORM.fetched_at >= now - timedelta(hours=24))
        ).label("h24_low"),
        func.max(gold_price).filter(
            and_(valid_row, MarketSnapshotORM.fetched_at >= now - timedelta(weeks=52))
        ).label("w52_high"),
        func.min(gold_price).filter(
            and_(valid_row, MarketSnapshotORM.fetched_at >= now - timedelta(weeks=52))
        ).label("w52_low"),
        func.min(MarketSnapshotORM.fetched_at).filter(valid_row).label("tracking_since"),
    )
    result = await session.execute(q)
    row = result.one()

    # Prior close = most recent valid row (can't compose with aggregates above)
    prior_q = (
        select(gold_price)
        .where(valid_row)
        .order_by(MarketSnapshotORM.fetched_at.desc())
        .limit(1)
    )
    prior_result = await session.execute(prior_q)
    prior_close = prior_result.scalar_one_or_none()

    # Strict-equality at_52w_high (Decision 4)
    at_52w_high: Optional[bool]
    if row.w52_high is None or current_spot is None:
        at_52w_high = None
    else:
        at_52w_high = current_spot >= row.w52_high

    tracking_since_str: Optional[str] = None
    if row.tracking_since is not None:
        try:
            tracking_since_str = row.tracking_since.date().isoformat()
        except AttributeError:
            tracking_since_str = None

    return {
        "gold_24h_high": row.h24_high,
        "gold_24h_low": row.h24_low,
        "gold_prior_close": prior_close,
        "gold_52w_high": row.w52_high,
        "gold_52w_low": row.w52_low,
        "at_52w_high": at_52w_high,
        "tracking_since": tracking_since_str,
    }


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def fetch_market_snapshot(
    session=None,  # AsyncSession | None
) -> MarketSnapshot:
    """Fetch market snapshot from FRED + metalpriceapi. Persist to DB if session provided.

    Fail-open at every layer:
    - Missing API key: log WARNING, skip source
    - Source HTTP error: log ERROR, [UNAVAILABLE] for that source
    - DB write failure: log ERROR, return in-memory snapshot to caller

    Returns a MarketSnapshot TypedDict. All fields may be None if sources fail.
    """
    settings = get_settings()
    fred_key = settings.fred_api_key or ""
    metals_key = settings.metalpriceapi_api_key or ""

    errors: dict[str, str] = {}

    # Snapshot fields
    gold: Optional[float] = None
    silver: Optional[float] = None
    ust_10y_nominal: Optional[float] = None
    ust_10y_real: Optional[float] = None
    fed_funds: Optional[float] = None
    cpi_yoy: Optional[float] = None
    cpi_observation_date: Optional[str] = None

    # Check for missing keys before making HTTP calls
    fred_available = bool(fred_key)
    metals_available = bool(metals_key)

    if not fred_available:
        logger.warning(_LOG_FMT_KEY, "FRED", "FRED_API_KEY")
        errors["fred"] = "missing_api_key: FRED_API_KEY not set"

    if not metals_available:
        logger.warning(_LOG_FMT_KEY, "metalpriceapi", "METALPRICEAPI_API_KEY")
        errors["metals"] = "missing_api_key: METALPRICEAPI_API_KEY not set"

    async with httpx.AsyncClient() as client:
        # Build concurrent tasks
        tasks: list = []
        task_labels: list[str] = []

        if fred_available:
            for field_name, series_id in FRED_SERIES.items():
                is_cpi = series_id == "CPIAUCSL"
                tasks.append(_fetch_fred_series(client, series_id, fred_key, is_cpi=is_cpi))
                task_labels.append(f"fred:{field_name}")

        if metals_available:
            fetcher = MetalpriceAPIFetcher(metals_key)
            tasks.append(fetcher.fetch(client))
            task_labels.append("metals")

        if not tasks:
            # Both keys missing — fail immediately
            now = datetime.now(timezone.utc)
            return MarketSnapshot(
                fetched_at=now,
                status="failed",
                gold_usd_per_oz=None,
                silver_usd_per_oz=None,
                ust_10y_nominal=None,
                ust_10y_real=None,
                fed_funds=None,
                cpi_yoy=None,
                cpi_observation_date=None,
                errors=errors,
            )

        results = await asyncio.gather(*tasks, return_exceptions=True)

    # --- Parse results ---
    fred_failed = False

    for label, result in zip(task_labels, results):
        if isinstance(result, BaseException):
            error_type = type(result).__name__
            error_msg = str(result)[:120]
            logger.error(_LOG_FMT, label, error_type, error_msg)
            if label.startswith("fred:"):
                # Record per-source FRED error once
                if "fred" not in errors:
                    errors["fred"] = f"{error_type}: {error_msg}"
                fred_failed = True
            else:
                errors["metals"] = f"{error_type}: {error_msg}"
            continue

        if label == "fred:ust_10y_nominal":
            if result is not None:
                try:
                    obs = result.get("observations", [])
                    ust_10y_nominal = _parse_rate_value(obs)
                except Exception as exc:
                    logger.error(_LOG_FMT, label, type(exc).__name__, str(exc)[:120])
                    fred_failed = True

        elif label == "fred:ust_10y_real":
            if result is not None:
                try:
                    obs = result.get("observations", [])
                    ust_10y_real = _parse_rate_value(obs)
                except Exception as exc:
                    logger.error(_LOG_FMT, label, type(exc).__name__, str(exc)[:120])
                    fred_failed = True

        elif label == "fred:fed_funds":
            if result is not None:
                try:
                    obs = result.get("observations", [])
                    fed_funds = _parse_rate_value(obs)
                except Exception as exc:
                    logger.error(_LOG_FMT, label, type(exc).__name__, str(exc)[:120])
                    fred_failed = True

        elif label == "fred:cpi_yoy":
            if result is not None:
                try:
                    obs = result.get("observations", [])
                    cpi_yoy, cpi_observation_date = _parse_cpi_yoy(obs)
                except Exception as exc:
                    logger.error(_LOG_FMT, label, type(exc).__name__, str(exc)[:120])
                    fred_failed = True

        elif label == "metals":
            if result is not None:
                try:
                    gold = result.get("gold_usd_per_oz")
                    silver = result.get("silver_usd_per_oz")
                except Exception as exc:
                    logger.error(_LOG_FMT, label, type(exc).__name__, str(exc)[:120])

    # --- Determine status ---
    all_populated = (
        ust_10y_nominal is not None
        and ust_10y_real is not None
        and fed_funds is not None
        and cpi_yoy is not None
        and gold is not None
        and silver is not None
    )
    none_populated = (
        ust_10y_nominal is None
        and ust_10y_real is None
        and fed_funds is None
        and cpi_yoy is None
        and gold is None
        and silver is None
    )

    if all_populated:
        status: Literal["ok", "partial", "failed"] = "ok"
    elif none_populated:
        status = "failed"
    else:
        status = "partial"

    # Consolidate FRED error if any series failed
    if fred_failed and "fred" not in errors:
        errors["fred"] = "one or more FRED series failed"

    # --- Compute gold temporal anchors (ep9) — MUST run before session.add below ---
    anchors: dict = {k: None for k in _ANCHOR_KEYS}
    if session is not None:
        try:
            anchors = await _compute_gold_anchors(session, gold)
        except Exception as exc:
            logger.error(
                "ContentAgent: market snapshot anchor compute failed (%s: %s) — "
                "continuing without anchors.",
                type(exc).__name__, str(exc)[:120],
            )

    now = datetime.now(timezone.utc)
    snap: MarketSnapshot = {
        "fetched_at": now,
        "status": status,
        "gold_usd_per_oz": gold,
        "silver_usd_per_oz": silver,
        "ust_10y_nominal": ust_10y_nominal,
        "ust_10y_real": ust_10y_real,
        "fed_funds": fed_funds,
        "cpi_yoy": cpi_yoy,
        "cpi_observation_date": cpi_observation_date,
        **anchors,  # 7 anchor fields spread into the TypedDict
        "errors": errors,
    }

    # --- Persist to DB (fail-open) ---
    if session is not None:
        try:
            from models.market_snapshot import MarketSnapshot as MarketSnapshotORM  # noqa: PLC0415
            # Build JSONB data payload (drop non-serialisable datetime from data field)
            data_payload = {
                k: v for k, v in snap.items()
                if k not in ("fetched_at", "status", "errors")
            }
            row = MarketSnapshotORM(
                fetched_at=now,
                data=data_payload,
                status=status,
                error_detail=errors if errors else None,
            )
            session.add(row)
            await session.flush()
        except Exception as exc:
            logger.error(
                "ContentAgent: market snapshot DB write failed (%s: %s) — "
                "continuing with in-memory snapshot.",
                type(exc).__name__, str(exc)[:120],
            )

    return snap


# ---------------------------------------------------------------------------
# Prompt block renderer
# ---------------------------------------------------------------------------

def render_snapshot_block(snap: MarketSnapshot | dict) -> str:
    """Build the CURRENT MARKET SNAPSHOT prompt block for injection into Sonnet system prompt.

    Two branches:
    - Populated (status ok/partial): header "as of <UTC>", real values
    - Failed (all None): header "fetch failed at <UTC>", [UNAVAILABLE] placeholders

    Both branches always append the hard instruction verbatim.
    """
    fetched_at: datetime = snap.get("fetched_at") or datetime.now(timezone.utc)
    status = snap.get("status", "failed")

    ts = fetched_at.strftime("%Y-%m-%d %H:%M UTC")

    if status == "failed" and snap.get("gold_usd_per_oz") is None and snap.get("ust_10y_nominal") is None:
        header = f"CURRENT MARKET SNAPSHOT (fetch failed at {ts})"
    else:
        header = f"CURRENT MARKET SNAPSHOT (as of {ts})"

    def _fmt_price(val: Optional[float]) -> str:
        if val is None:
            return "[UNAVAILABLE]"
        return f"${val:,.2f}/oz"

    def _fmt_pct(val: Optional[float]) -> str:
        if val is None:
            return "[UNAVAILABLE]"
        return f"{val:.2f}%"

    def _fmt_cpi(val: Optional[float], obs_date: Optional[str]) -> str:
        if val is None:
            return "[UNAVAILABLE]"
        pct_str = f"{val:.2f}%"
        if obs_date:
            try:
                dt = datetime.strptime(obs_date, "%Y-%m-%d")
                label = dt.strftime("%B %Y print")
                return f"{pct_str} ({label})"
            except ValueError:
                return pct_str
        return pct_str

    def _fmt_gold_range(window: str) -> str:
        """Format 'Gold {window} range:' line. window ∈ {'24h', '52w'}.

        Populated → '$lo – $hi/oz (suffix)' where suffix is prior_close (24h) or
        at_52w_high binary (52w).
        Empty (hi & lo both None): '[UNAVAILABLE — first snapshot]' if no
        tracking_since, else '[UNAVAILABLE — tracking since YYYY-MM-DD, N day(s) of history]'.
        """
        if window == "24h":
            hi = snap.get("gold_24h_high")
            lo = snap.get("gold_24h_low")
            suffix_val = snap.get("gold_prior_close")
            suffix_label = "prior close"
        else:  # 52w
            hi = snap.get("gold_52w_high")
            lo = snap.get("gold_52w_low")
            suffix_val = snap.get("at_52w_high")
            suffix_label = "at_52w_high"

        tracking_since = snap.get("tracking_since")

        # Both hi and lo None → [UNAVAILABLE] branch
        if hi is None and lo is None:
            if tracking_since:
                try:
                    ts_date = datetime.strptime(tracking_since, "%Y-%m-%d").date()
                    now_source = snap.get("fetched_at") or datetime.now(timezone.utc)
                    now_date = now_source.date()
                    days = (now_date - ts_date).days
                    day_word = "day" if days == 1 else "days"
                    return (
                        f"[UNAVAILABLE — tracking since {tracking_since}, "
                        f"{days} {day_word} of history]"
                    )
                except (ValueError, AttributeError):
                    return f"[UNAVAILABLE — tracking since {tracking_since}]"
            return "[UNAVAILABLE — first snapshot]"

        # Populated case
        range_str = f"${lo:,.2f} – ${hi:,.2f}/oz"
        if window == "24h":
            if suffix_val is not None:
                return f"{range_str} ({suffix_label}: ${suffix_val:,.2f}/oz)"
            return range_str
        # 52w
        if suffix_val is None:
            suffix_render = "[UNAVAILABLE]"
        else:
            suffix_render = "true" if suffix_val else "false"
        return f"{range_str} ({suffix_label}: {suffix_render})"

    gold = snap.get("gold_usd_per_oz")
    silver = snap.get("silver_usd_per_oz")
    ust_10y = snap.get("ust_10y_nominal")
    ust_real = snap.get("ust_10y_real")
    ff = snap.get("fed_funds")
    cpi = snap.get("cpi_yoy")
    cpi_date = snap.get("cpi_observation_date")

    lines = [
        header,
        f"- Spot gold: {_fmt_price(gold)}",
        f"- Spot silver: {_fmt_price(silver)}",
        f"- Gold 24h range: {_fmt_gold_range('24h')}",
        f"- Gold 52w range: {_fmt_gold_range('52w')}",
        f"- 10Y Treasury yield: {_fmt_pct(ust_10y)}",
        f"- 10Y TIPS (real) yield: {_fmt_pct(ust_real)}",
        f"- Fed funds effective rate: {_fmt_pct(ff)}",
        f"- CPI (YoY): {_fmt_cpi(cpi, cpi_date)}",
        "",
        _HARD_INSTRUCTION,
    ]

    return "\n".join(lines)
