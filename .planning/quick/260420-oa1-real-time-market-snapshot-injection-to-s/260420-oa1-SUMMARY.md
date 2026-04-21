---
phase: quick-260420-oa1
plan: 01
subsystem: content-agent / market-snapshot
tags: [market-data, prompt-grounding, hallucination-guard, fred, metalpriceapi, alembic, tdd]
dependency_graph:
  requires: [quick-260420-nnh, phase-07-content-agent]
  provides: [market-snapshot-service, market-snapshot-grounded-drafts]
  affects: [content_agent.py, scheduler/services, scheduler/models, backend/app/models, alembic]
tech_stack:
  added: [httpx-direct FRED + metalpriceapi integration, MarketSnapshot TypedDict, MarketSnapshot ORM (scheduler + backend mirror)]
  patterns: [asyncio.gather return_exceptions, fail-open per-source try/except, TypedDict for in-memory shape, render_snapshot_block prompt builder]
key_files:
  created:
    - scheduler/services/market_snapshot.py (493 lines)
    - scheduler/models/market_snapshot.py (36 lines)
    - backend/app/models/market_snapshot.py (41 lines)
    - backend/alembic/versions/0007_add_market_snapshots.py (50 lines)
    - scheduler/tests/test_market_snapshot.py (690 lines)
  modified:
    - scheduler/config.py (added fred_api_key + metalpriceapi_api_key Optional[str]=None)
    - scheduler/models/__init__.py (registered MarketSnapshot)
    - backend/app/models/__init__.py (registered MarketSnapshot)
    - scheduler/agents/content_agent.py (import + run() fetch + 3 drafter injections)
    - scheduler/tests/test_content_agent.py (8 new integration tests, logging import)
    - .env.example (new section with both API keys + provisioning URLs)
decisions:
  - "httpx-direct over fredapi SDK — fredapi is sync-only, adds no value for 5 series in async arch"
  - "asyncio.gather with per-source try/except — FRED failure doesn't block metals fetch and vice versa"
  - "fetch in run() not _run_pipeline — enables test_run_fetches_snapshot_once_per_invocation to patch _run_pipeline as no-op"
  - "getattr(self, '_market_snapshot', None) guard — existing tests use __new__ without __init__; defensive getattr prevents AttributeError on agents created without initialization"
  - "respx not used — unittest.mock.AsyncMock on httpx.AsyncClient.get chosen to avoid adding a dev dep; simpler and consistent with existing test patterns"
  - "CPI YoY uses limit=13 observations sorted desc; finds year-ago obs by matching year-1/same-month from valid (non-dot) observations"
metrics:
  duration: "~30 min"
  completed: "2026-04-21"
  tasks: 2
  files: 10
---

# Quick 260420-oa1: Real-time Market Snapshot Injection — Summary

**One-liner:** Fetch FRED macro stack + metalpriceapi spot metals once per content_agent cron; inject `CURRENT MARKET SNAPSHOT` block + hard hallucination-guard instruction into all three Sonnet drafter call sites; persist row for audit; fail-open at every layer.

## Artifacts Created

| File | Lines | Purpose |
|------|-------|---------|
| `scheduler/services/market_snapshot.py` | 493 | `fetch_market_snapshot()` + `MetalpriceAPIFetcher` + `render_snapshot_block()` + `MarketSnapshot` TypedDict |
| `scheduler/models/market_snapshot.py` | 36 | SQLAlchemy ORM: id, fetched_at, data JSONB, status CHECK, error_detail JSONB |
| `backend/app/models/market_snapshot.py` | 41 | Backend mirror (manual-sync Phase 04 pattern) |
| `backend/alembic/versions/0007_add_market_snapshots.py` | 50 | Migration from 0006; creates table + fetched_at index |
| `scheduler/tests/test_market_snapshot.py` | 690 | All 12 locked unit tests |

## Artifacts Modified

| File | Change |
|------|--------|
| `scheduler/config.py` | +2 lines: `fred_api_key` + `metalpriceapi_api_key` Optional[str]=None |
| `scheduler/models/__init__.py` | +MarketSnapshot import + __all__ entry |
| `backend/app/models/__init__.py` | +MarketSnapshot import + __all__ entry |
| `scheduler/agents/content_agent.py` | Import; _market_snapshot=None in __init__; run() fetch block; 3 drafter injections |
| `scheduler/tests/test_content_agent.py` | +import logging; +8 new integration tests (OA1-1 through OA1-8) |
| `.env.example` | New section: FRED_API_KEY + METALPRICEAPI_API_KEY with provisioning URLs |

## Test Counts

- **12 new unit tests** in `scheduler/tests/test_market_snapshot.py` (all pass)
- **8 new integration tests** in `scheduler/tests/test_content_agent.py` (all pass)
- **118 pre-existing tests** pass without regression (total: 138 scheduler tests)

## Key Implementation Decisions

**HTTP stubbing approach:** Used `unittest.mock.AsyncMock` on `httpx.AsyncClient.get` rather than `respx`. No new dev dependency needed; consistent with existing test patterns in the project.

**fetch_market_snapshot location:** Placed in `run()` (before `_run_pipeline`), not inside `_run_pipeline` as the plan action described. The locked test `test_run_fetches_snapshot_once_per_invocation` patches `_run_pipeline` as a no-op and still asserts `call_count == 1` — so the fetch must be in `run()` itself. The test spec takes precedence over the implementation notes.

**getattr defensive guard:** All three drafter call sites use `getattr(self, "_market_snapshot", None)` not `self._market_snapshot`. Existing tests create `ContentAgent` via `__new__` (bypassing `__init__`), so `_market_snapshot` is never set as an attribute on those instances. The `getattr` guard prevents `AttributeError` and lets existing tests continue passing without modification.

**CPI YoY computation:** `fetch_market_snapshot` requests `limit=13` for `CPIAUCSL` (12 months + 1 for safety). Filters out FRED `"."` sentinel values, then finds the year-ago observation by matching `year-1/same-month` against valid observations. Both latest and year-ago being `"."` → `cpi_yoy=None`.

**FRED "." sentinel for rate series:** `_parse_rate_value()` iterates through observations and skips `"."` entries, returning the first valid float. With `limit=2`, the second observation serves as the fallback if the latest is `"."`.

**reciprocal-rate inversion:** `MetalpriceAPIFetcher.fetch()` applies `1 / USDXAU` to convert the reciprocal rate format to USD per oz. Test 8 asserts `1/0.000426 ≈ $2,347.42/oz` with `rel=1e-4`.

**render_snapshot_block format:**
- Populated: `CURRENT MARKET SNAPSHOT (as of 2026-04-21 00:30 UTC)` + 6 metric lines + blank line + hard instruction
- Fallback: `CURRENT MARKET SNAPSHOT (fetch failed at ...)` + 6 `[UNAVAILABLE]` lines + blank line + hard instruction

Hard instruction (verbatim): "Do not cite any specific dollar figures, percentages, yields, or rates — current or historical — that do not appear verbatim in this snapshot. Use qualitative language ('near recent highs', 'elevated', 'multi-year high') or omit the claim entirely."

## Deviations from Plan

**Auto-deviation (plan action vs. test spec conflict):**
The plan action (Step 2c) said to place the fetch block at the top of `_run_pipeline`. However, the locked test `test_run_fetches_snapshot_once_per_invocation` patches `_run_pipeline` as a no-op and still expects `fetch_market_snapshot.call_count == 1`. Since a no-op `_run_pipeline` would never call the fetch if it lived inside the pipeline, the fetch was moved to `run()` itself (before `await self._run_pipeline(...)`). This matches the plan's stated intent ("fetch once per cron cycle, before story ranking/drafting") while satisfying the locked test behavior.

**Auto-deviation (getattr guard not in plan):**
Plan mentioned `if self._market_snapshot else ""` for the edge-case guard. Changed to `if getattr(self, "_market_snapshot", None) else ""` because existing tests create `ContentAgent` via `__new__` — without calling `__init__` — meaning `_market_snapshot` is never set as an attribute, causing `AttributeError` on attribute access. The `getattr` form satisfies both test patterns (Rule 2 — missing correctness requirement).

## Known Follow-ups for Operator

1. **Provision `FRED_API_KEY`** in Railway scheduler env (free, instant): https://fredaccount.stlouisfed.org/ → API Keys → Request API Key
2. **Provision `METALPRICEAPI_API_KEY`** in Railway scheduler env (Basic plan $8.99/mo): https://metalpriceapi.com/ → Basic plan → Dashboard
3. **Redeploy scheduler** on Railway after setting both keys
4. **Watch next content_agent cron cycle** (every 3h) for:
   - A `market_snapshots` row written to DB (status `ok`/`partial`/`failed`)
   - Log line to grep: `ContentAgent: market snapshot fetch — <source> failed (<error_type>: <truncated>)` (appears on any per-source failure)
   - Drafter outputs should cite real numbers from the snapshot or use qualitative language ("near recent highs") — never a fabricated figure like "$3,500/oz in 2025"
5. **Subscribe to metalpriceapi Basic plan** ($8.99/mo) before deploying if not already done

## Validation Passed

- `uv run pytest tests/test_market_snapshot.py tests/test_content_agent.py -x`: 82/82 pass
- `uv run pytest` (full suite): 138/138 pass
- `uv run ruff check .`: clean
- `alembic upgrade head --sql` (offline): emits `CREATE TABLE market_snapshots` + `CREATE INDEX ix_market_snapshots_fetched_at`
- `grep -n "fetch_market_snapshot\|render_snapshot_block" content_agent.py`: confirms fetch at run() + render at all 3 call sites
- Hard instruction `"Do not cite any specific dollar figures, percentages, yields, or rates — current or historical —"` appears verbatim in `render_snapshot_block()`

## Self-Check: PASSED
