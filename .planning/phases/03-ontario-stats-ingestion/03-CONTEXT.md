# Phase 3: Ontario Stats Ingestion - Context

**Gathered:** 2026-04-27
**Status:** Ready for planning
**Mode:** Smart-discuss (autonomous), build-time WDS verification complete

<domain>
## Phase Boundary

Replace the Phase 1 Ontario Stats section stub with a real StatCan WDS ingestion. Each daily_summary fire (08:00 PT + 12:00 PT) polls StatCan for the canonical "Ontario gold production" vector. On a release day (~19th-21st of M+2 monthly), the section renders the fresh figure with month-over-month comparison. On all other days (the default — ~29/30 days/month), the section renders an anchored empty-state with the last known figure. A separate visual treatment distinguishes `no_new_data` (expected) from `error` (broken ingestion).

**In scope:**
- New module: `scheduler/agents/ontario_stats.py` exposing `fetch_ontario_stats_snapshot()` → returns `{state: 'fresh' | 'no_new_data' | 'error', figure_kg: float | None, period: 'YYYY-MM', release_time: str, prior_period_figure: float | None, error_text: str | None}`
- Direct poll of StatCan WDS — no "The Daily" RSS trigger (simpler than the research's original suggestion; more reliable)
- Compare current `releaseTime` against stored snapshot's `releaseTime` to detect fresh data
- Wire `_build_ontario_stats_section()` in `scheduler/agents/daily_summary.py` (replacing the stub from Phase 1)
- Extend `OntarioStatsState` Pydantic model with full snapshot shape
- Persist snapshot in `daily_summaries.raw_sources_jsonb.ontario_stats` for empty-state continuity across fires
- Tests: fresh-data path, no_new_data path (empty state), error path, release-time advance detection, MoM comparison rendering

**Out of scope:**
- "The Daily" RSS feed monitoring — direct WDS poll is simpler and more reliable
- Annual data fallback (StatCan Table 16-10-0022) — sticking with the monthly Table 16-10-0019
- Custom geographic regions (only Ontario, not other provinces)
- Custom commodities (only gold, not silver/copper/etc.)
- Phase 4 prune cron (separate phase)

**Requirements covered (5):** STAT-01, STAT-02, STAT-03, STAT-04, STAT-05

</domain>

<decisions>
## Implementation Decisions

### StatCan WDS Source (build-time verified 2026-05-06)

**Locked WDS parameters** (no need to query metadata at runtime):
- **Table (productId):** `16100019` (Production of metallic minerals in quantities, monthly)
- **Geography member:** `8` (Ontario)
- **Product member:** `16` (Gold, recoverable, kilograms — the canonical industry figure)
- **Variable member:** `1` (Quantity produced)
- **Coordinate string:** `"8.16.1.0.0.0.0.0.0.0"` (10-position dot-padded format)
- **vectorId:** `1146004456` (resolved from the coordinate; usable directly in the simpler endpoint)
- **Unit:** kilograms (always — no scalar conversion needed)

### API Strategy: Direct Vector Poll (NOT RSS Trigger)

**Deviated from research SUMMARY.md** which suggested "StatCan 'The Daily' RSS trigger + WDS API call on release day." Rationale: direct vector poll is strictly simpler:
- One HTTP call per fire instead of two (RSS + conditional WDS)
- No RSS XML parsing
- No false-positive triggers (The Daily covers all gov stats; would fire spuriously for unrelated tables)
- WDS responses include a `releaseTime` field on every datapoint — we use that as the freshness oracle

**Endpoint (POST, JSON):**
```
https://www150.statcan.gc.ca/t1/wds/rest/getDataFromVectorsAndLatestNPeriods
```

**Request body:**
```json
[{"vectorId": 1146004456, "latestN": 3}]
```

`latestN=3` returns the most recent 3 monthly periods — current + 2 priors. Current period gives us "fresh figure"; prior period gives us "MoM comparison" for STAT-04.

**Response sample (verified 2026-05-06):**
```json
{
  "status": "SUCCESS",
  "object": {
    "vectorId": 1146004456,
    "vectorDataPoint": [
      {"refPer": "2025-12-01", "value": 9203.0, "releaseTime": "2026-04-20T08:30"},
      {"refPer": "2026-01-01", "value": 7559.0, "releaseTime": "2026-04-20T08:30"},
      {"refPer": "2026-02-01", "value": 7359.0, "releaseTime": "2026-04-20T08:30"}
    ]
  }
}
```

### Freshness Detection

State machine (in `fetch_ontario_stats_snapshot()`):
1. Read previous summary's `raw_sources_jsonb.ontario_stats.release_time` from DB.
2. Call WDS endpoint with `latestN=3`.
3. Extract the most-recent datapoint's `releaseTime`.
4. **If WDS call raises** (httpx error, JSON parse fail, status != "SUCCESS") → return `state="error"`. Pass error text up to the section builder, which renders the "error" visual treatment.
5. **If returned `releaseTime` > stored `releaseTime`** (or stored is null) → `state="fresh"`. Update JSONB with new snapshot. Render fresh figure + MoM comparison.
6. **Else** → `state="no_new_data"`. Use stored figure for empty-state continuity.

The release_time string is StatCan's release timestamp (always `YYYY-MM-DDThh:mm` format). Lexicographic string comparison Just Works for ISO timestamps.

### Markdown Output

**Fresh data path** (rare — happens once per month):
```
**Ontario gold production for {Month YYYY}: {figure} kg** (vs {prior_figure} kg in {prior_month}, {pct_change}% MoM)

Source: Statistics Canada, Table 16-10-0019, released {YYYY-MM-DD}.
```

Example for Feb 2026 release:
```
**Ontario gold production for February 2026: 7,359 kg** (vs 7,559 kg in January 2026, -2.6% MoM)

Source: Statistics Canada, Table 16-10-0019, released 2026-04-20.
```

Numbers formatted with thousands separators. Percentage rounded to 1 decimal. MoM sign included (`+1.4%` or `-2.6%`).

**No-new-data path** (default — ~29/30 days/month):

Verbatim from REQUIREMENTS.md STAT-05, with computed values:
```
No new production statistics released today. Next Monthly Mineral Production Survey release expected around {next_release_estimate}. Last data: {YYYY-MM} — Ontario gold production: {last_known_figure} kg.
```

Where:
- `{next_release_estimate}` = formula-based: take stored snapshot's `refPer`, add 3 months, then "the 19th-21st" → e.g. snapshot is 2026-02 → next release is for May 2026 data → ~2026-05-20. Format: "around May 20, 2026".
- `{YYYY-MM}` = `last_known_period` (e.g. "2026-02")
- `{last_known_figure}` = formatted with thousands separators

Fallback when no `last_known_figure` exists (first-ever fire on a non-release day):
```
Ontario production statistics are released monthly with a ~2-month lag. Awaiting first StatCan release.
```

**Error path** — distinct visual treatment so operator can distinguish "expected silence" from "broken ingestion":
```
⚠ Ontario production statistics ingestion failed: {short_error}. agent_run_id: {short_id} — see agent-runs log for details.
```

The frontend SectionBlock will render this with a red border / amber-pill severity badge (handled in Phase 1's existing styling — no frontend changes in Phase 3).

### Pydantic Schema Extension

`OntarioStatsState` (in `backend/app/schemas/daily_summary.py`) extends to:
```python
class OntarioStatsSnapshot(BaseModel):
    """One StatCan polled state."""
    period: str  # "YYYY-MM"
    figure_kg: float
    release_time: str  # "YYYY-MM-DDThh:mm"
    prior_period: str | None = None
    prior_figure_kg: float | None = None

class OntarioStatsState(BaseModel):
    snapshot: OntarioStatsSnapshot | None = None
    last_state: Literal["fresh", "no_new_data", "error"] | None = None
    last_error_text: str | None = None
```

The `RawSources` model already exposes `ontario_stats: OntarioStatsState`. Phase 1's stub left it as `OntarioStatsState()` (empty). Phase 3 populates the snapshot.

### Cross-Module Wiring

- `scheduler/agents/daily_summary.py:_build_ontario_stats_section()` — replace body. Sequence:
  1. Read previous summary's `raw_sources.ontario_stats.snapshot` (if any) → pass `previous_release_time` to the fetch call
  2. Call `fetch_ontario_stats_snapshot(previous_release_time)`
  3. Branch on `state`:
     - `fresh` → render fresh markdown + update `raw_sources.ontario_stats.snapshot` with new data
     - `no_new_data` → render no-new-data markdown using prior snapshot (or fallback if first-ever fire) + propagate snapshot forward
     - `error` → render error markdown + persist `last_state="error"`, `last_error_text` to JSONB; do NOT overwrite the existing snapshot (so we keep our last good data)
- `scheduler/agents/ontario_stats.py` — NEW file. Exports `fetch_ontario_stats_snapshot(previous_release_time: str | None = None)` and `_compute_next_release_estimate(period_str: str) -> str`. Uses existing `httpx.AsyncClient` from the project pool.
- `scheduler/tests/agents/test_ontario_stats.py` — NEW file. Mirrors structure of `test_ontario_law.py`.
- `backend/app/schemas/daily_summary.py` — extend with `OntarioStatsSnapshot`. The new `OntarioStatsState` fields are backward-compat (additive, all default None).
- No DB migration. No new pip packages.

### Telemetry

Add 3 new keys to `agent_runs.notes`:
- `candidates_stats_state`: `"fresh" | "no_new_data" | "error"`
- `candidates_stats_period`: e.g. `"2026-02"` (or null)
- `candidates_stats_release_time`: e.g. `"2026-04-20T08:30"` (or null on error)

These nest under the existing `notes` JSONB without schema migration.

### Test Strategy

- **Fresh-data path:** Mock httpx to return canned WDS response with `releaseTime > previous_release_time`. Assert state="fresh", correct figure parsed, correct MoM computation, JSONB snapshot updated.
- **No-new-data path:** Mock httpx to return same `releaseTime` as previously stored. Assert state="no_new_data", figures preserved, empty-state copy renders with `next_release_estimate` formula.
- **First-ever fire path:** No previous summary at all. WDS returns valid data → state="fresh". Assert no `previous_release_time` reference crash.
- **Error path:** Mock httpx to raise `httpx.HTTPError`. Assert state="error", error text captured, JSONB snapshot NOT overwritten (preserves last good data).
- **WDS status not SUCCESS:** Mock response with `{"status": "FAILED"}`. Assert state="error".
- **MoM percentage formatting:** Assert `+1.4%` and `-2.6%` formatting (sign + 1 decimal).
- **Real WDS smoke test (gated by env):** If `STATCAN_LIVE_TESTS=1`, hit the real endpoint; assert success, vector matches, value > 0. Skip in CI.
- **Next-release-estimate formula:** Assert `_compute_next_release_estimate("2026-02")` = `"around May 20, 2026"` (or similar dated string).
- **Daily summary integration test:** End-to-end with mocked WDS + previous summary in DB. Assert correct branch is taken.

### Cross-cutting (locked from prior phases, not re-decided here)

- httpx for the WDS call (existing dep)
- AsyncSessionLocal + select() for the previous-summary read (post-m51 pattern)
- All async; no blocking I/O
- Tests in `scheduler/tests/agents/test_ontario_stats.py` (mirrors test_ontario_law.py)
- Ruff clean; pytest -x green
- Phase 1 + Phase 2 functionality preserved (no regression)

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets

- `scheduler/agents/daily_summary.py` — has the stub `_build_ontario_stats_section()` placeholder from Phase 1. Replace its body in Phase 3. Phase 2's `_build_ontario_law_section()` already established the "read previous summary's JSONB → propagate forward" pattern — Phase 3 mirrors that exactly.
- `scheduler/agents/ontario_law.py` — Phase 2's reference for module structure: pure functions where possible, asyncio.gather for parallelism, structured Pydantic returns, comprehensive tests.
- `backend/app/schemas/daily_summary.py` — has `OntarioStatsState` (currently empty placeholder from Phase 1). Phase 3 extends it with `OntarioStatsSnapshot`.
- `scheduler/db.py` — `AsyncSessionLocal` for the previous-summary read.
- httpx is already in scheduler dependencies (used by existing scrapers).

### Established Patterns

- **Previous-summary read:** Phase 2 (Ontario Law) already does `select(DailySummary).order_by(DailySummary.generated_at.desc()).limit(1)` in `_build_ontario_law_section`. Mirror that exactly.
- **Pydantic JSON validation:** `RawSources(...).model_dump_json()` on write, `RawSources.model_validate_json(row.raw_sources_jsonb)` on read — established in Phase 1.
- **State branching in section builder:** Phase 2 `_build_ontario_law_section` branches on "have surviving hits?" — Phase 3 branches on `state ∈ {fresh, no_new_data, error}`.
- **Telemetry:** Phase 1 + Phase 2 both add keys to `agent_runs.notes`. Phase 3 adds 3 more.

### Integration Points

- `scheduler/agents/daily_summary.py:_build_ontario_stats_section()`: replace body. Signature stays the same.
- `scheduler/agents/ontario_stats.py`: NEW file with `fetch_ontario_stats_snapshot(previous_release_time)` + `_compute_next_release_estimate(period)`.
- `scheduler/tests/agents/test_ontario_stats.py`: NEW.
- `backend/app/schemas/daily_summary.py`: add `OntarioStatsSnapshot` model.
- `scheduler/agents/ontario_stats.py` does NOT need a config setting — no model selection, no env-gated behavior, no API key. Pure HTTP poll of a public endpoint.

</code_context>

<specifics>
## Specific Ideas

- **Real release cadence:** StatCan released Feb 2026 data on April 20 2026 — exactly M+2 + ~20 days. So the formula `current_period + 3 months → 19th-21st of that month` is well-calibrated.
- **No SerpAPI usage in Phase 3** — Phase 3 doesn't search; it polls a known endpoint. SerpAPI quota is preserved for Phase 2 (Ontario Law) and any future use.
- **Anthropic API not used in Phase 3** — no LLM call at all. Phase 3 is pure data fetching + formatting. Cost = $0/month for the stats section.
- **Numbers formatting:** Python f-string `f"{figure:,.0f} kg"` produces `"7,359 kg"`. Use that pattern.
- **Month names:** `datetime.strptime(period, "%Y-%m").strftime("%B %Y")` → "February 2026". Standard library, no new deps.

</specifics>

<deferred>
## Deferred Ideas

- **The Daily RSS feed integration** — explicitly deferred. Direct WDS poll is simpler and more reliable. If StatCan ever changes its WDS schema in a way that needs RSS-based change detection, revisit.
- **Annual fallback (Table 16-10-0022)** — deferred. Monthly Table 16-10-0019 covers v2.0 needs. If monthly data ever becomes unreliable or the table is retired, fall back to annual.
- **Other commodities (silver, copper)** — deferred. v2.0 is gold-only per project Core Value.
- **Other provinces (Quebec, BC)** — deferred. v2.0 is Ontario-only per locked decision.
- **YoY comparison** — only MoM in Phase 3. YoY needs `latestN=13` and a different lookup.
- **Cross-summary continuity** — already deferred for the law section (CSC-01); same applies here. The stats section is a single figure, not a narrative — continuity adds nothing.

</deferred>
