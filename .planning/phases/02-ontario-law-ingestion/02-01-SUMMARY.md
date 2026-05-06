---
phase: 02-ontario-law-ingestion
plan: "01"
subsystem: scheduler/agent
tags: [ontario-law, serpapi, nrcan, haiku, relevance-filter, last-known-law, continuity, LAW-01, LAW-02, LAW-03, LAW-04, HIGH-1, HIGH-2, HIGH-6]

# Dependency graph
requires:
  - 01-05 (scheduler/agents/daily_summary.py stub to replace)
  - 01-01 (backend/app/schemas/daily_summary.py Pydantic models to extend)
provides:
  - scheduler/agents/ontario_law.py: fetch_ontario_law_hits() + source fetchers + Haiku filter
  - backend/app/schemas/daily_summary.py: LastKnownLaw model + OntarioLawHit.reason field
  - scheduler/config.py: ontario_law_filter_model env var
  - backend/app/config.py: ontario_law_filter_model env var (parity)
  - scheduler/agents/daily_summary.py: real _build_ontario_law_section() + 4 new telemetry keys
affects:
  - Phase 3 (_build_ontario_stats_section stub is the only remaining placeholder)
  - Phase 4 (daily_summary_prune uses same rows this plan writes to)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "ontario_law: SerpAPI (tbs=qdr:d 24h) + NRCan Atom via asyncio.gather(return_exceptions=True)"
    - "Haiku relevance filter with 3 verbatim REJECT/ACCEPT examples (HIGH-1) + 1500-char body (HIGH-2)"
    - "D-Survival rule: is_law AND bill_or_reg_number AND favour_or_neutral != against"
    - "last_known_law JSONB propagation: SELECT prev raw_sources_jsonb → carry forward on empty days"
    - "OntarioLawHit local mirror dataclass in scheduler (byte-identical to backend schema)"
    - "D-NoMigration: Pydantic validates LastKnownLaw shape on JSONB write; no Alembic file"

key-files:
  created:
    - scheduler/agents/ontario_law.py
    - scheduler/tests/agents/test_ontario_law.py
    - scheduler/tests/test_config.py
  modified:
    - backend/app/schemas/daily_summary.py
    - scheduler/config.py
    - backend/app/config.py
    - scheduler/agents/daily_summary.py
    - scheduler/tests/agents/test_daily_summary.py
    - backend/tests/test_daily_summary_schema.py
    - backend/tests/test_config.py

key-decisions:
  - "OntarioLawHit mirrored locally in ontario_law.py as dataclass — scheduler has no backend/ on sys.path"
  - "reason field added to OntarioLawHit (both backend schema + local mirror) for D-Bullet rendering"
  - "LastKnownLaw replaces OntarioLawHit for last_known_law field — narrower, more specific shape"
  - "Phase 1 stub never persisted a real OntarioLawHit in last_known_law (always None) — no DB row migration"
  - "_is_fake_api_key() helper to gate Test A — handles empty string ANTHROPIC_API_KEY from env"

requirements-completed:
  - LAW-01
  - LAW-02
  - LAW-03
  - LAW-04

# Metrics
duration: ~10 min
completed: "2026-05-06"
---

# Phase 2 Plan 01: Ontario Law Ingestion Summary

**SerpAPI + NRCan concurrent ingestion + claude-haiku-4-5 relevance filter + last_known_law JSONB continuity wired into daily_summary cron — replaces Phase 1 stub entirely**

## Performance

- **Duration:** ~10 min
- **Completed:** 2026-05-06
- **Tasks:** 3 (Task 1: Pydantic + config; Task 2: ontario_law.py module; Task 3: wiring + tests)
- **Files created:** 3
- **Files modified:** 7
- **Tests added:** 37 (19 in test_ontario_law.py + 9 new in test_daily_summary.py + 4 schema + 2 scheduler config + 2 backend config)
- **Total scheduler tests:** 266 passed, 1 skipped (real-API Haiku test gated by ANTHROPIC_API_KEY)
- **Total backend tests:** 112 passed, 5 skipped

## Accomplishments

### backend/app/schemas/daily_summary.py

- Added `LastKnownLaw` Pydantic model with `date`/`law_name`/`url` string fields for LAW-04 continuity
- Added `reason: str | None = None` to `OntarioLawHit` for D-Bullet rendering (pure addition, no migration)
- Updated `OntarioLawState.last_known_law` annotation from `OntarioLawHit | None` to `LastKnownLaw | None`
  (Phase 1 stub never wrote a real value — always `None` — so no DB row migration is needed)

### scheduler/config.py + backend/app/config.py

- Added `ontario_law_filter_model: str = "claude-haiku-4-5"` to both `Settings` classes
- Env-tunable via `ONTARIO_LAW_FILTER_MODEL` (parity between scheduler and backend)
- HIGH-6 guard: default is Haiku, not Sonnet; comment explicitly warns against Sonnet

### scheduler/agents/ontario_law.py (NEW, 340+ lines)

- `OntarioLawHit` local mirror dataclass (byte-identical fields to backend schema, including new `reason`)
- `NRCAN_ATOM_URL` locked constant (verbatim from CONTEXT.md D-Source-A)
- `SERPAPI_QUERY` + `SERPAPI_DATE_FILTER = "qdr:d"` constants
- `FILTER_BODY_MAX_CHARS = 1500` (HIGH-2 mitigation)
- `FILTER_SYSTEM_PROMPT` with 3 verbatim REJECT/ACCEPT examples (HIGH-1 mitigation):
  1. "Minister speaks at mining association gala" → is_law=false
  2. "Government announces consultation on critical minerals strategy" → is_law=false
  3. "Bill 71 (Building Ontario Act) receives Royal Assent — amends Mining Act sections 21-24" → is_law=true
- `_fetch_serpapi_candidates()`: asyncio run_in_executor, tbs=qdr:d, num=25
- `_fetch_nrcan_candidates()`: httpx AsyncClient + feedparser, hits exact NRCan Atom URL
- `_dedup_by_url()`: URL-based deduplication (first occurrence wins)
- `_filter_one()`: Haiku call with fail-closed parse error handling; strips markdown fences defensively
- `_survives()`: D-Survival rule (is_law AND bill_or_reg_number AND favour_or_neutral != "against")
- `fetch_ontario_law_hits()`: full orchestrator returning `(survivors, counts)` tuple
  - `asyncio.gather(..., return_exceptions=True)` for source fetching (D-Resilience)
  - `asyncio.gather(..., return_exceptions=True)` for parallel filter fan-out
  - Telemetry counts: serpapi, nrcan, after_dedup, after_filter

### scheduler/agents/daily_summary.py

- Removed `ONTARIO_LAW_STUB_MD` constant
- Replaced `_build_ontario_law_section()` stub with real Phase 2 implementation (4-tuple return)
- Added `serpapi_client` construction using `settings.serpapi_api_key`
- Added previous-summary `SELECT ... LIMIT 1` for LAW-04 `last_known_law` continuity
- Updated `raw_sources["ontario_law"]` to include real `hits` + `new_last_known_law`
- Extended `notes_payload` with 4 Phase 2 telemetry keys:
  - `candidates_law_serpapi`, `candidates_law_nrcan`, `candidates_law_after_dedup`, `candidates_law_after_filter`
  - `candidates_law` now reflects `law_counts["after_filter"]` (was hard-coded 0)

## Task Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Pydantic LastKnownLaw + dual config env var | `d296fd7` | backend/app/schemas/daily_summary.py, scheduler/config.py, backend/app/config.py, backend/tests/test_daily_summary_schema.py, scheduler/tests/test_config.py, backend/tests/test_config.py |
| 2 | ontario_law.py module + comprehensive tests | `4ca6325` | scheduler/agents/ontario_law.py, scheduler/tests/agents/test_ontario_law.py |
| 3 | Wire _build_ontario_law_section() + telemetry | `bdd6d3c` | scheduler/agents/daily_summary.py, scheduler/tests/agents/test_daily_summary.py |

## Pitfall Coverage Matrix

| Pitfall | Closed | Where |
|---------|--------|-------|
| HIGH-1 (false positives — political speech) | YES | 3 verbatim REJECT examples in FILTER_SYSTEM_PROMPT |
| HIGH-2 (false negatives — opaque bill names) | YES | FILTER_BODY_MAX_CHARS=1500, body included in filter input |
| HIGH-6 (cost — Sonnet ban) | YES | claude-haiku-4-5 default + comment guard in both config files |
| Source-failure resilience | YES | asyncio.gather(return_exceptions=True) ×2 (source fetch + filter fan-out) |

## Test Coverage (Phase 2 additions)

### scheduler/tests/agents/test_ontario_law.py (19 tests, 1 skipped in CI)
- Test A: real Haiku positive call (gated by `_is_fake_api_key()`)
- Tests B-D: mocked REJECT-1, REJECT-2, ACCEPT — verify verbatim prompt examples present
- Test E: 5000-char body truncated to 1500 chars (HIGH-2)
- Test F: URL deduplication (2 dupes → 2 unique)
- Test G: 5-case survival rule truth table (2 pass, 3 reject)
- Test H: SerpAPI tbs=qdr:d date filter + keyword query verification
- Test I: NRCan exact URL assertion
- Tests J-K: source-failure resilience (SerpAPI raises / NRCan raises)
- Test L: both sources empty → filter NOT called
- Test M: 4-key telemetry counts in return tuple
- Constant verification: NRCan URL, 1500 chars, FILTER_SYSTEM_PROMPT examples, reason field

### scheduler/tests/agents/test_daily_summary.py (9 new Phase 2 tests)
- U1: survivors → bullet markdown + last_known_law set from first survivor
- U2: empty + prior last_known_law → continuity copy propagated forward
- U3: empty + no prior → "No new Ontario mining-related laws today." (no date)
- U4: 4 new telemetry keys in agent_runs.notes JSON
- U5: _build_ontario_law_section signature has required kwargs
- U6: fetch_ontario_law_hits wired into daily_summary namespace
- U7: settings.ontario_law_filter_model resolves filter model
- U8: fetch_ontario_law_hits raises → (None, [], ...) → section failed

### backend/tests/ (7 new tests)
- 4 schema tests: LastKnownLaw construction, round-trip, OntarioLawState accepts None/LastKnownLaw, field annotation
- 2 backend config tests: default + env override for ontario_law_filter_model
- 2 scheduler config tests: default + env override for ontario_law_filter_model

## Telemetry Keys Added to agent_runs.notes

| Key | Phase | Description |
|-----|-------|-------------|
| `candidates_law` | Phase 1 (was 0) | Now reflects `after_filter` count (real survivors) |
| `candidates_law_serpapi` | Phase 2 NEW | Raw SerpAPI hit count before dedup |
| `candidates_law_nrcan` | Phase 2 NEW | Raw NRCan hit count before dedup |
| `candidates_law_after_dedup` | Phase 2 NEW | Candidates after URL deduplication |
| `candidates_law_after_filter` | Phase 2 NEW | Survivors after Haiku relevance filter |

## Deviations from Plan

### Auto-added (Rule 2 / planned in Task 3 action)

**1. [Addition] reason field added to OntarioLawHit**
- **Found during:** Task 3 planning (plan explicitly notes this)
- **Issue:** D-Bullet format `* **{bill}** — {reason}` requires reason per hit; OntarioLawHit lacked reason field
- **Fix:** Added `reason: str | None = None` to backend `OntarioLawHit` + local mirror in ontario_law.py
- **Files modified:** backend/app/schemas/daily_summary.py, scheduler/agents/ontario_law.py
- **Commit:** `d296fd7` (schema), `4ca6325` (local mirror)

**2. [Rule 1 - Bug] _is_fake_api_key() helper added to test**
- **Found during:** Test A execution — ANTHROPIC_API_KEY env was set to empty string "" which doesn't start with "sk-test-"
- **Issue:** skipif condition `key.startswith("sk-test-")` doesn't catch empty string or truly absent key
- **Fix:** Added `_is_fake_api_key()` function checking `not key or key.startswith("sk-test-")`
- **Files modified:** scheduler/tests/agents/test_ontario_law.py
- **Commit:** `4ca6325`

**3. [Rule 2 - Missing] Session count updated in existing tests**
- **Found during:** Task 3 — Phase 2 adds prev-summary SELECT between session 2 (agent_run insert) and session 3 (DailySummary insert)
- **Issue:** Existing tests (Test 7, Test 10, Test 11) used hardcoded session indices that shifted by 1
- **Fix:** Updated all 3 tests to add prev-summary read at session index 3 (shifting DailySummary insert to index 4)
- **Files modified:** scheduler/tests/agents/test_daily_summary.py
- **Commit:** `bdd6d3c`

## Phase 3 Readiness

`_build_ontario_stats_section()` stub is the only remaining placeholder in `run_daily_summary()`. Phase 3 wires StatCan WDS table 16-10-0019-01 ingestion.

---
*Phase: 02-ontario-law-ingestion*
*Completed: 2026-05-06*

## Self-Check: PASSED

- FOUND: scheduler/agents/ontario_law.py
- FOUND: scheduler/tests/agents/test_ontario_law.py
- FOUND: scheduler/tests/test_config.py
- FOUND: backend/app/schemas/daily_summary.py (LastKnownLaw + reason field)
- FOUND: scheduler/config.py (ontario_law_filter_model field)
- FOUND: backend/app/config.py (ontario_law_filter_model field)
- FOUND: .planning/phases/02-ontario-law-ingestion/02-01-SUMMARY.md
- FOUND commit: d296fd7 (Task 1 — Pydantic + config)
- FOUND commit: 4ca6325 (Task 2 — ontario_law.py module)
- FOUND commit: bdd6d3c (Task 3 — wiring + telemetry)
