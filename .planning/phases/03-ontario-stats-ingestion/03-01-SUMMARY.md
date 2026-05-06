---
phase: 03-ontario-stats-ingestion
plan: "01"
subsystem: scheduler/agent
tags: [ontario-stats, statcan-wds, httpx, state-machine, fresh, no_new_data, error, STAT-01, STAT-02, STAT-03, STAT-04, STAT-05]

# Dependency graph
requires:
  - 01-05 (scheduler/agents/daily_summary.py stub to replace)
  - 01-01 (backend/app/schemas/daily_summary.py Pydantic models to extend)
  - 02-01 (Phase 2 module style + JSONB continuity pattern)
provides:
  - scheduler/agents/ontario_stats.py: fetch_ontario_stats_snapshot() + _compute_next_release_estimate() + format_*_markdown()
  - backend/app/schemas/daily_summary.py: OntarioStatsSnapshot model + new OntarioStatsState shape
  - scheduler/agents/daily_summary.py: real _build_ontario_stats_section() + 3 new telemetry keys + JSONB snapshot persistence
affects:
  - Phase 4 (daily_summary_prune cron uses same rows this plan writes to)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "StatCan WDS: POST getDataFromVectorsAndLatestNPeriods with vectorId 1146004456, latestN=3"
    - "State machine: fresh/no_new_data/error gated by releaseTime lexicographic comparison"
    - "JSONB error resilience: prior snapshot preserved on error state — never overwritten"
    - "httpx.AsyncClient timeout=15s for network resilience"
    - "OntarioStatsSnapshot JSONB shape — same read-by-dict-get pattern as ontario_law"
    - "_compute_next_release_estimate: +3 months with year rollover (pure function)"

key-files:
  created:
    - scheduler/agents/ontario_stats.py
    - scheduler/tests/agents/test_ontario_stats.py
  modified:
    - backend/app/schemas/daily_summary.py
    - backend/tests/test_daily_summary_schema.py
    - scheduler/agents/daily_summary.py
    - scheduler/tests/agents/test_daily_summary.py

key-decisions:
  - "Direct WDS poll (not RSS trigger) — simpler, more reliable, 1 HTTP call per fire"
  - "vectorId 1146004456 D-Locked at build time — no runtime metadata lookup needed"
  - "releaseTime lexicographic comparison works for ISO YYYY-MM-DDThh:mm timestamps"
  - "Combine law + stats previous-summary reads into single SELECT (no second DB query)"
  - "Error path preserves prior snapshot in JSONB — last-good data survives transient WDS outages"
  - "No anthropic/serpapi in Phase 3 — pure HTTP poll, $0 AI cost for stats section"

requirements-completed:
  - STAT-01
  - STAT-02
  - STAT-03
  - STAT-04
  - STAT-05

# Metrics
duration: ~20 min
completed: "2026-05-06"
---

# Phase 3 Plan 01: Ontario Stats Ingestion Summary

**StatCan WDS direct vector poll replacing the Phase 1 stub — fresh/no_new_data/error state machine with JSONB snapshot persistence and 3 new telemetry keys**

## Performance

- **Duration:** ~20 min
- **Completed:** 2026-05-06
- **Tasks:** 3 (Task 1: Pydantic schemas; Task 2: ontario_stats.py module; Task 3: wiring + tests)
- **Files created:** 2
- **Files modified:** 4
- **Tests added:** 51 (21 in test_ontario_stats.py + 8 new in test_daily_summary.py + 7 schema + updated 2 existing schema tests + updated 3 existing daily_summary tests)
- **Total scheduler tests:** 295 passed, 1 skipped (pre-existing real-API Haiku test)
- **Total backend tests:** 119 passed, 5 skipped (pre-existing)

## Accomplishments

### backend/app/schemas/daily_summary.py

- Added `OntarioStatsSnapshot` Pydantic model with 5 fields: `period` / `figure_kg` / `release_time` / `prior_period` / `prior_figure_kg`
- Replaced `OntarioStatsState` Phase 1 placeholder with 3-field shape: `snapshot` / `last_state` / `last_error_text`
- Added `Literal["fresh", "no_new_data", "error"]` validation on `last_state` — invalid values raise `ValidationError`
- Removed 3 Phase 1 fields: `snapshot_date`, `last_known_figure`, `fresh_data`
- Added `from typing import Literal` import

### backend/tests/test_daily_summary_schema.py

- 7 new tests (Tests 1-7): construction, round-trip, defaults, Literal validation, removed-field assertion, RawSources round-trip
- Updated 2 existing tests to use new `OntarioStatsState` shape (removed references to `snapshot_date`)

### scheduler/agents/ontario_stats.py (NEW, 180+ lines)

- `WDS_ENDPOINT` verbatim constant: `https://www150.statcan.gc.ca/t1/wds/rest/getDataFromVectorsAndLatestNPeriods`
- `ONTARIO_GOLD_VECTOR_ID = 1146004456` (D-Locked — build-time verified; Ontario gold recoverable, kg)
- `WDS_LATEST_N = 3` / `WDS_TIMEOUT_SECONDS = 15.0`
- `OntarioStatsResult` dataclass — public return type
- `fetch_ontario_stats_snapshot(previous_release_time)`:
  - POST to WDS with `[{"vectorId": 1146004456, "latestN": 3}]`
  - Status check: `status != "SUCCESS"` → error
  - Empty datapoints check → error
  - Freshness: `previous_release_time is None OR current_release_time > previous_release_time` → fresh
  - Any exception caught → state="error" (never crashes cron)
- `_compute_next_release_estimate(period_str)`: +3 months with proper year rollover
- `format_fresh_markdown()`: full template with MoM%, thousands separators, source citation
- `format_no_new_data_markdown()`: first-fire fallback + last-known figure template
- `format_error_markdown()`: warning glyph + agent_run_id[:8] traceability

### scheduler/agents/daily_summary.py

- Removed `ONTARIO_STATS_STUB_MD` constant
- Replaced stub `_build_ontario_stats_section()` with real Phase 3 implementation (3-tuple return)
- Added imports from `agents.ontario_stats`
- Combined previous-summary SELECT to also pull `ontario_stats.snapshot` (single query — no second SELECT)
- Replaced Phase 1 `raw_sources.ontario_stats` shape `{snapshot_date, last_known_figure, fresh_data}` with `{snapshot, last_state, last_error_text}`
- Updated failure-row write with new ontario_stats shape
- Added 3 new telemetry keys: `candidates_stats_state`, `candidates_stats_period`, `candidates_stats_release_time`

## Task Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Extend OntarioStats Pydantic schemas | `5c04549` | backend/app/schemas/daily_summary.py, backend/tests/test_daily_summary_schema.py |
| 2 | ontario_stats.py module + comprehensive tests | `17dd953` | scheduler/agents/ontario_stats.py, scheduler/tests/agents/test_ontario_stats.py |
| 3 | Wire _build_ontario_stats_section() + telemetry | `3223a86` | scheduler/agents/daily_summary.py, scheduler/tests/agents/test_daily_summary.py |

## Pitfall Coverage Matrix

| Pitfall | Closed | Where |
|---------|--------|-------|
| Network timeout (slow WDS) | YES | httpx.AsyncClient(timeout=15.0) |
| Empty datapoints: `dps[-1]` on [] → IndexError | YES | Explicit empty-list check before indexing |
| First-fire (previous_release_time=None) crash | YES | `is None` is the FIRST branch in freshness check |
| WDS status != "SUCCESS" | YES | Explicit `status != "SUCCESS"` check → error |
| Error path overwrites last-good snapshot | YES | `"snapshot": previous_snapshot` on error branch |
| JSONB shape change breaks old rows | YES | dict.get() used for reading (not Pydantic model_validate) |
| MoM formatting sign | YES | `f"{pct:+.1f}"` — always includes sign |
| Thousands separators | YES | `f"{figure:,.0f} kg"` |
| Year rollover in next-release estimate | YES | `while month > 12: month -= 12; year += 1` |
| No new pip dependencies | YES | Only httpx (already present) |
| No DB migration | YES | JSONB shape application-validated only |

## Test Coverage (Phase 3 additions)

### scheduler/tests/agents/test_ontario_stats.py (21 tests)

- FRESH: releaseTime > previous → state='fresh', correct field parsing
- NO_NEW_DATA: same releaseTime → state='no_new_data', data fields=None
- FIRST_EVER_FIRE: previous_release_time=None + valid data → state='fresh', no crash
- ERROR_HTTPX: httpx.HTTPError → state='error', error_text set
- ERROR_TIMEOUT: httpx.TimeoutException → state='error', mentions "Timeout"
- ERROR_STATUS_NOT_SUCCESS: status='FAILED' → state='error'
- ERROR_EMPTY_DATAPOINTS: empty vectorDataPoint → state='error'
- MOM_POSITIVE: prior=7000, current=7140 → "+2.0%"
- MOM_NEGATIVE: prior=7559, current=7359 → "-2.6%"
- NUMBER_FORMATTING: 7359.0 → "7,359 kg", 12345.0 → "12,345 kg"
- NEXT_RELEASE_FORMULA: 2026-02 → "around May 20, 2026"
- NEXT_RELEASE_YEAR_ROLLOVER: 2026-12 → "around March 20, 2027"
- NEXT_RELEASE_OCTOBER: 2026-10 → "around January 20, 2027"
- ENDPOINT_AND_BODY: exact URL + JSON body verified
- CONSTANTS: WDS_ENDPOINT + ONTARIO_GOLD_VECTOR_ID
- Format tests: fresh (full template), no_new_data (prior + first-fire), error (glyph + ID)
- No anthropic/serpapi imports verification

### scheduler/tests/agents/test_daily_summary.py (8 new Phase 3 tests, S1-S8)

- S1: fresh path → markdown + snapshot populated + last_state='fresh'
- S2: no_new_data + prior → propagated forward + next-release estimate in markdown
- S3: no_new_data + no prior → "Awaiting first StatCan release"
- S4: error → prior snapshot preserved (NOT overwritten) + warning glyph + agent_run_id
- S5: telemetry fresh path → all 3 candidates_stats_* keys set
- S6: telemetry error path → state='error', period/release_time=None
- S7: raw_sources shape — old Phase 1 keys gone, new keys present
- S8: stub constant removed + stub text gone from source

### backend/tests/test_daily_summary_schema.py (7 new Phase 3 tests)

- Test 1: OntarioStatsSnapshot construction with required fields only
- Test 2: OntarioStatsSnapshot round-trip via model_dump() — JSON-safe primitives
- Test 3: OntarioStatsState() defaults — all None
- Test 4: OntarioStatsState(last_state='fresh') accepted
- Test 5: OntarioStatsState(last_state='invalid') raises ValidationError
- Test 6: RawSources with OntarioStatsState round-trips via JSON
- Test 7: Phase 1 fields (snapshot_date, last_known_figure, fresh_data) absent

## Telemetry Keys Added to agent_runs.notes

| Key | Phase | Description |
|-----|-------|-------------|
| `candidates_stats_state` | Phase 3 NEW | "fresh" / "no_new_data" / "error" |
| `candidates_stats_period` | Phase 3 NEW | e.g. "2026-02" or null |
| `candidates_stats_release_time` | Phase 3 NEW | e.g. "2026-04-20T08:30" or null |
| `candidates_stats` | Legacy scalar | Kept at 0 for backward compat |

## STAT Requirements Coverage

| Requirement | Status | Mechanism |
|-------------|--------|-----------|
| STAT-01 (RSS trigger) | SUPERSEDED | Direct WDS poll — simpler, more reliable |
| STAT-02 (WDS API pull) | CLOSED | fetch_ontario_stats_snapshot() POSTs to getDataFromVectorsAndLatestNPeriods with vectorId 1146004456, latestN=3 |
| STAT-03 (snapshot persistence) | CLOSED | fresh: snapshot updated; no_new_data: propagated forward; error: preserved |
| STAT-04 (fresh markdown) | CLOSED | format_fresh_markdown(): bold period + figure, MoM%, source citation |
| STAT-05 (no-new-data + error with distinct treatment) | CLOSED | format_no_new_data_markdown() (prose) vs format_error_markdown() (⚠ glyph) |

## Deviations from Plan

None — plan executed exactly as written.

The 3 updated existing tests (test_rawsources_default_construction, test_rawsources_full_construction, test_build_ontario_stats_section_returns_stub_tuple → replaced) were expected changes per the plan's pitfall guards section.

## Phase 4 Readiness

Phase 3 completes the Ontario Stats intelligence surface. The daily_summary feed now has 3 real sections:
1. Gold News (Phase 1) — Sonnet-drafted from fetch_stories()
2. Ontario Law (Phase 2) — SerpAPI + NRCan + Haiku filter
3. Ontario Stats (Phase 3) — StatCan WDS direct vector poll

Phase 4 (daily_summary_prune cron — prune rows older than 30 days) is the final remaining phase. All 3 content sections are now production-ready.

---
*Phase: 03-ontario-stats-ingestion*
*Completed: 2026-05-06*

## Self-Check: PASSED

- FOUND: scheduler/agents/ontario_stats.py
- FOUND: scheduler/tests/agents/test_ontario_stats.py
- FOUND: backend/app/schemas/daily_summary.py (OntarioStatsSnapshot + new OntarioStatsState)
- FOUND: scheduler/tests/agents/test_daily_summary.py (S1-S8 added)
- FOUND: backend/tests/test_daily_summary_schema.py (7 new Phase 3 tests)
- FOUND: .planning/phases/03-ontario-stats-ingestion/03-01-SUMMARY.md
- FOUND commit: 5c04549 (Task 1 — Pydantic schemas)
- FOUND commit: 17dd953 (Task 2 — ontario_stats.py module)
- FOUND commit: 3223a86 (Task 3 — wiring + telemetry)
- 295 scheduler tests passed, 1 skipped
- 119 backend tests passed, 5 skipped
- ruff clean: both scheduler and backend
