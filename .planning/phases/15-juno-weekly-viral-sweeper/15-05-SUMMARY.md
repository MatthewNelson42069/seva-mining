---
phase: 15-juno-weekly-viral-sweeper
plan: 05
subsystem: scheduler
tags: [juno, weekly-sweeper, orchestrator, sonnet, x-api, refusal-detector, virality, phase-15, wave-2]

# Dependency graph
requires:
  - phase: 15-01
    provides: "raw_sources_jsonb keys defence_news / canadian_procurement / world_events persisted on every NEW Juno daily_summaries row (Plan 15-01 D-03a substrate fix)"
  - phase: 15-02
    provides: "JUNO_SWEEPER_SYSTEM_PROMPT (Janes/CSIS voice + verbatim FORBID + 3-angles) + JUNO_SWEEPER_X_QUERY (11 corrected handles + 2 hashtags, 261 chars) as importable constants"
  - phase: 12-per-tenant-anthropic-api-key
    provides: "get_anthropic_client('juno', timeout=...) per-tenant resolver (Phase 12 D-07 hardcoded literal contract)"
  - phase: 10-juno-defence-news-funnel
    provides: "call_with_refusal_guard from agents.juno_refusal_detector + FRAMING_NUDGE retry-with-nudge pattern (D-05 reuse verbatim)"
  - phase: 09-multi-tenant-foundation
    provides: "scoped_summaries('juno') + scoped_weekly_sweeps('juno') tenant-scoped query helpers (TENANT-03 CI grep gate)"
  - phase: 07-weekly-viral-sweeper
    provides: "Seva run_weekly_sweeper orchestrator shape + canonical_url + _sunday_of_this_week helpers (imported verbatim via D-06 LOCKED decision)"
provides:
  - "scheduler/agents/juno_weekly_sweeper.py — new orchestrator module exporting run_juno_weekly_sweeper() async entry point + 4 module-public helpers (_compute_juno_virality, _idempotency_skip, _call_sonnet_for_juno_angles, _build_x_posts_md/_build_virality_md)"
  - "17 unit tests in scheduler/tests/agents/test_juno_weekly_sweeper.py covering JSWEEP-02/-03/-04 invariants + D-06 helper-share identity contract"
  - "__main__ block for operator smoke fire (python -m agents.juno_weekly_sweeper per D-07 step 2)"
affects:
  - 15-06-PLAN  # worker.py cron registration imports run_juno_weekly_sweeper
  - 15-07-PLAN  # voice UAT runs against this module's first production fire

# Tech tracking
tech-stack:
  added: []  # pure-Python — no new libraries
  patterns:
    - "Cross-module helper-share without file edit: importing a leading-underscore helper (_sunday_of_this_week) from a sister module is Python-legal (underscore is advisory). Tests assert identity (`is`) not equality to lock the import-from path against future copy-paste refactors."
    - "Refusal-guard wrap as a sonnet-call composition: caller builds prompt → routes through call_with_refusal_guard → unpacks (text_or_None, diagnostic) → caller-owned status mapping branches on `text is None` (refusal-second-attempt fail) → diagnostic persisted in raw_sources_jsonb for operator visibility"
    - "Substrate-summary diagnostic block: raw_sources_jsonb.substrate_summary carries {x_posts_count, viral_stories_count, insufficient_signal_path} so operator can distinguish D-03b backfill-window 'partial' rows from refusal-detector 'partial' rows at a glance"
    - "Status mapping inverts Seva's sparse-week-is-completed assumption for Juno: where Seva treats insufficient_signal as 'completed' (sparse-week-is-normal), Juno treats it as 'partial' (D-03b backfill window is more likely to fire and operators need visibility for the first 0-2 post-deploy sweeps)"

key-files:
  created:
    - scheduler/agents/juno_weekly_sweeper.py
    - scheduler/tests/agents/test_juno_weekly_sweeper.py
  modified: []  # zero-modify plan — D-10 byte-identical contract honored

key-decisions:
  - "D-06 helper-share IMPORT-FROM-SEVA path picked (LOCKED): `from agents.weekly_sweeper import canonical_url, _sunday_of_this_week` — Seva file UNTOUCHED. Avoids ~50 LOC of duplication for zero behavioral benefit. Test asserts identity (`juno_weekly_sweeper.canonical_url is weekly_sweeper.canonical_url`) so a future refactor that copy-pastes the helpers fails loudly."
  - "Status mapping for insufficient_signal is 'partial' (NOT 'completed' as Seva does): Juno's D-03b backfill window is more likely to trip insufficient_signal during the first 0-2 sweeps post-deploy than Seva ever experienced. Tagging these as 'partial' (with the INSUFFICIENT_SIGNAL_FALLBACK copy explaining 'substrate may still be accumulating') gives the operator visibility — and aligns with the Phase 9 idempotency-filter-includes-partial pattern so a retry within 60 min won't write a duplicate row."
  - "Refusal-detector wrap returns (text_or_None, diagnostic) tuple — caller-owned status mapping is cleaner than letting call_with_refusal_guard own the WeeklySweep row mutation. Sweeper's status mapping branches on `text is None` (second-attempt refusal) → status='partial' + REFUSAL_FALLBACK_COPY + persist diagnostic for operator visibility."
  - "JUNO_SWEEPER_SONNET_MAX_TOKENS = 1500 matches Phase 10's JUNO_SONNET_MAX_DEFENCE (the longest Sonnet output ceiling on the Juno side). 3 content angles fit comfortably; 1500 leaves headroom for refusal-retry expansion."
  - "X_POST_TRUNCATE_CHARS = 500 mirrors Seva's truncation (P7 token-budget overflow guard) — defence X posts are sometimes long-form analyst threads, but 500 chars is enough signal for cross-referencing against a news story."

patterns-established:
  - "Per-tenant sweeper orchestrator shape: idempotency check (scoped + status-includes-partial) → agent_runs INSERT (status='running') → per-tenant Anthropic resolver (hardcoded literal) → 3 sections (X ingest → virality → Sonnet via refusal-guard) → status mapping (refusal-aware) → weekly_sweeps INSERT (scoped) → finally telemetry. Reusable shape if a third tenant ever lands."
  - "Test fixtures for orchestrator mocks: _patch_orchestration helper monkey-patches fetch_top_x_posts + _compute_juno_virality + call_with_refusal_guard + _idempotency_skip + AsyncSessionLocal + get_anthropic_client in one call, returns (session_mock, resolver_calls) so test bodies stay focused on the assertion."
  - "D-06 helper-share identity test: assert `juno_weekly_sweeper.canonical_url is weekly_sweeper.canonical_url` (identity, not equality) catches the copy-paste-not-import refactor failure mode at the cheapest possible test cost."

requirements-completed: [JSWEEP-02, JSWEEP-03, JSWEEP-04]

# Metrics
duration: ~6.5min
completed: 2026-05-21
---

# Phase 15 Plan 05: Juno Weekly Sweeper Orchestrator Summary

**Landed `scheduler/agents/juno_weekly_sweeper.py` (588 LOC) — the Sunday-08:00-PT orchestrator that wires Plan 15-01 substrate keys, Plan 15-02 prompt/query constants, Phase 12 per-tenant Anthropic resolver (hardcoded `'juno'` literal), Phase 10 refusal-detector (D-05 reuse), and Phase 9 scoped helpers into a complete cron entry point. Imports `canonical_url` + `_sunday_of_this_week` from Seva's `weekly_sweeper.py` per D-06 LOCKED helper-share decision (no Seva file edit). 17 new unit tests assert JSWEEP-02/-03/-04 invariants including the D-06 identity contract; full scheduler suite 359 passed (342 baseline + 17 new).**

## Performance

- **Duration:** ~6.5 min
- **Started:** 2026-05-21T00:49:05Z
- **Completed:** 2026-05-21T00:55:36Z
- **Tasks:** 2 (both completed atomically; Task 1 production code, Task 2 tests)
- **Files created:** 2 (1 production module, 1 test file)
- **Files modified:** 0 (D-10 contract — zero edits to upstream dependencies)

## Module Structure: scheduler/agents/juno_weekly_sweeper.py

| Section | Lines | Purpose |
|---------|-------|---------|
| Module docstring | 1-47 | Phase 15 wiring narrative, Juno-vs-Seva diffs, pitfall mitigations, D-06/D-10 contracts |
| Imports + logger | 48-77 | content_agent.deduplicate_stories + juno_refusal_detector.call_with_refusal_guard + weekly_sweeper.{canonical_url,_sunday_of_this_week} + x_ingest.fetch_top_x_posts + anthropic_client.get_anthropic_client + companies.juno.{prompts,x_queries} + models + queries.scoped |
| Constants | 78-103 | AGENT_NAME, LA_TZ, JUNO_SWEEPER_SONNET_{MODEL,MAX_TOKENS,TIMEOUT}, IDEMPOTENCY_WINDOW_MIN, VIRALITY_{LOOKBACK_DAYS,TOP_N}, SUFFICIENT_SIGNAL_MIN, X_POST_TRUNCATE_CHARS, INSUFFICIENT_SIGNAL_FALLBACK, REFUSAL_FALLBACK_COPY |
| `_compute_juno_virality` | 110-201 | D-03 3-sub-array union (defence_news + canadian_procurement + world_events), canonical-URL dedup, distinct-source-count ranking, top-5 |
| `_build_x_posts_md` + `_build_virality_md` | 209-244 | Markdown builders (mirror Seva shape so Tab 3 multi-tenant renderer is identical) |
| `_call_sonnet_for_juno_angles` | 251-302 | User-prompt assembly + call_with_refusal_guard wrap; returns (text_or_None, diagnostic) |
| `_idempotency_skip` | 309-336 | scoped_weekly_sweeps('juno') with status.in_(['running','completed','partial']) — Phase 9 critical-fix |
| `run_juno_weekly_sweeper` | 343-541 | 6-step orchestrator: idempotency → agent_runs INSERT → resolver call (HARDCODED 'juno') → try {X ingest → virality → Sonnet via refusal-guard → status mapping → weekly_sweeps INSERT} → catastrophic-failure fallback row → finally telemetry |
| `__main__` block | 547-555 | Operator smoke-fire escape hatch (D-07 step 2: `python -m agents.juno_weekly_sweeper`) |

**Total LOC:** 588 (well above plan's 400 minimum)

## Helper-Share Decision (D-06 LOCKED)

Picked: **IMPORT-FROM-SEVA path.**

```python
# scheduler/agents/juno_weekly_sweeper.py:65
from agents.weekly_sweeper import canonical_url, _sunday_of_this_week
```

- `canonical_url` — module-public in Seva's weekly_sweeper.py (line 90); URL normalization for cross-source virality grouping
- `_sunday_of_this_week` — underscore-prefixed but Python's privacy convention is advisory, not enforced; the import is a read-only reference, does NOT modify weekly_sweeper.py

**D-10 byte-identical contract honored trivially.** `git status --porcelain scheduler/agents/weekly_sweeper.py` empty after this plan lands.

**Test guard against future copy-paste refactor:**
```python
# scheduler/tests/agents/test_juno_weekly_sweeper.py
def test_d10_helper_share_imports_from_seva_module():
    assert juno_weekly_sweeper.canonical_url is weekly_sweeper.canonical_url
    assert juno_weekly_sweeper._sunday_of_this_week is weekly_sweeper._sunday_of_this_week
```

Identity assertion (`is`) — only succeeds if the import path is honored; fails if a future refactor copy-pastes the helpers into juno_weekly_sweeper.py.

## Tests Delta: 17 new tests covering JSWEEP-02/-03/-04

| Group | Test | Requirement | What It Asserts |
|-------|------|------|------------------|
| A (virality) | `test_virality_compute_three_sub_array_union` | JSWEEP-02 D-03 | All 3 sub-arrays (defence_news + canadian_procurement + world_events) contribute to virality result |
| A | `test_virality_compute_dedupes_by_canonical_url` | JSWEEP-02 | Same canonical URL across rows + tracking-param variants groups to one entry; distinct_source_count = 2 |
| A | `test_virality_compute_returns_empty_on_no_juno_rows` | JSWEEP-02 | Empty DB (or scoped-out — only Seva rows) → [] without error |
| A | `test_virality_compute_null_raw_sources_guards` | JSWEEP-02 P3 | raw_sources_jsonb=None doesn't crash compute |
| B (idempotency) | `test_idempotency_skip_when_partial_exists` | JSWEEP-03 Phase 9 fix | Recent row with status='partial' → skip (Juno-specific, NOT in Seva's filter) |
| B | `test_idempotency_skip_returns_false_when_no_recent_row` | JSWEEP-03 | No recent row → no skip |
| B | `test_idempotency_filter_includes_partial_status_in_query` | JSWEEP-03 Phase 9 fix | Source-introspection guard: literals 'running','completed','partial' all present in `_idempotency_skip` source |
| C (E2E) | `test_run_happy_path_writes_weekly_sweeps_row` | JSWEEP-02 + JSWEEP-03 | 5 X posts + 5 viral + angles → status='completed', all 3 markdown columns + x_search_query persisted |
| C | `test_anthropic_client_called_with_hardcoded_juno_literal` | JSWEEP-04 Phase 12 D-07 | Resolver called with literal `"juno"` + timeout=JUNO_SWEEPER_SONNET_TIMEOUT |
| C | `test_persisted_row_has_company_id_juno` | JSWEEP-03 | Persisted row.company_id == 'juno' (zero cross-tenant write) |
| C | `test_x_search_query_persisted_in_raw_sources` | JSWEEP-02 | raw_sources_jsonb.x_search_query == JUNO_SWEEPER_X_QUERY |
| C | `test_refusal_first_attempt_retries_via_refusal_guard` | JSWEEP-04 D-05 | call_with_refusal_guard invoked with section_name='sweeper' + JUNO_SWEEPER_SYSTEM_PROMPT |
| C | `test_refusal_second_attempt_sets_partial` | JSWEEP-04 D-05 | (None, diag) return → status='partial' + refusal_diagnostic in raw_sources_jsonb |
| C | `test_idempotency_skip_blocks_orchestration` | JSWEEP-03 | When _idempotency_skip=True: no fetch call, no DB writes |
| C | `test_insufficient_signal_does_not_call_sonnet` | JSWEEP-04 D-03b | <3 X posts OR 0 viral → Sonnet NOT called, status='partial', INSUFFICIENT_SIGNAL_FALLBACK in angles_md |
| C | `test_juno_x_query_passed_to_fetch_top_x_posts` | JSWEEP-02 D-10 | fetch_top_x_posts called with JUNO_SWEEPER_X_QUERY (not Seva's X_SEARCH_QUERY) |
| C | `test_d10_helper_share_imports_from_seva_module` | D-06 LOCKED | canonical_url + _sunday_of_this_week are SAME function objects as Seva's (identity check) |

## Test Pass Counts

| Suite | Before | After | Delta |
|-------|--------|-------|-------|
| Full scheduler suite | 342 passed, 1 skipped | **359 passed, 1 skipped** | **+17** |
| Plan 15-05 new tests | 0 | 17 | +17 |
| Seva regression (test_weekly_sweeper.py + test_juno_daily_summary.py) | 24 passed | 24 passed | 0 (byte-identical) |

## Task Commits

Each task committed atomically with `--no-verify` per parallel-execution protocol:

1. **Task 1: feat(15-05): create juno_weekly_sweeper orchestrator module** — `44566d0` (1 file, +588 LOC)
2. **Task 2: test(15-05): add 17 unit tests for juno_weekly_sweeper** — `3e1e605` (1 file, +799 LOC)

## Files Created/Modified

- **CREATED** `scheduler/agents/juno_weekly_sweeper.py` (588 LOC) — orchestrator + 4 module-public helpers + 2 markdown builders + __main__ block
- **CREATED** `scheduler/tests/agents/test_juno_weekly_sweeper.py` (799 LOC) — 17 tests + helper fixtures + envvar setup
- **MODIFIED** none — D-10 zero-modify contract honored

## Decisions Made

- **D-06 LOCKED IMPORT-FROM-SEVA path** (not duplication). Trivially holds D-10 byte-identical contract; identity assertion in tests guards against future copy-paste refactors. Cost: 1 line of imports vs ~50 LOC of duplicated helpers.
- **Insufficient-signal status = 'partial' (NOT 'completed')** — diverges from Seva's sparse-week-is-normal convention. Rationale: Juno's D-03b backfill window is more likely to trip insufficient_signal during the first 0-2 post-deploy sweeps; tagging as 'partial' gives operator visibility AND aligns with the Phase 9 idempotency-filter-includes-partial pattern so retry within 60 min won't duplicate.
- **Sonnet call returns (text_or_None, diagnostic) tuple** — caller-owned status mapping is cleaner than letting `call_with_refusal_guard` own the WeeklySweep row mutation. Refusal diagnostic persisted in `raw_sources_jsonb.refusal_diagnostic` for operator visibility.
- **Test fixtures use MagicMock + monkeypatch + SimpleNamespace** — matches the existing scheduler test pattern (`tests/test_weekly_sweeper.py` + `tests/agents/test_juno_daily_summary.py`). The scheduler layer doesn't have SQLite test fixtures because the production schema uses Postgres-only types (JSONB + UUID columns). Mock-based tests run fast (0.54s for 17 tests).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] First test assertion used lowercase path in canonical URL**
- **Found during:** Task 2 acceptance verification (first pytest run)
- **Issue:** `test_virality_compute_three_sub_array_union` asserted `"https://defence.example/story-a"` (lowercase path) was in result URLs. But `canonical_url()` (imported from Seva's `weekly_sweeper.py`) lowercases ONLY the host, NOT the path. Test got `story-A`, expected `story-a` → 1 failed, 16 passed.
- **Fix:** Updated assertion to expect the correct preserved-case path (`story-A`, `story-B`, `story-C`) with inline comment documenting canonical_url's lowercase-host-only behavior. No production code change; test-data expectation aligned with the verbatim Seva canonical_url contract.
- **Files modified:** `scheduler/tests/agents/test_juno_weekly_sweeper.py` (test fixture only; not committed separately since fixed before Task 2 commit landed).
- **Verification:** 17/17 tests GREEN after fix.

**Total deviations:** 1 auto-fixed (test-expectation alignment with imported helper's contract; not a production-code issue). Fixed inside Task 2 before commit.

**Impact on plan:** None to production code or test count. The D-06 import-from-Seva path preserved the canonical_url contract verbatim — the test just needed to match the helper's actual behavior (host lowercase, path preserved).

## Authentication Gates

None encountered. This plan creates pure-Python orchestrator + test code with mock external services — no API key resolution, OAuth flow, or interactive credential prompts in the execution path.

## D-10 Zero-Regression Evidence

**Protected files BYTE-IDENTICAL after plan:**

```bash
$ git status --porcelain \
    scheduler/agents/weekly_sweeper.py \
    scheduler/agents/x_ingest.py \
    scheduler/agents/juno_refusal_detector.py \
    scheduler/anthropic_client.py \
    scheduler/queries/scoped.py \
    scheduler/companies/juno/prompts.py \
    scheduler/companies/juno/x_queries.py \
    scheduler/agents/daily_summary.py \
    scheduler/tests/test_weekly_sweeper.py \
    scheduler/tests/agents/test_juno_daily_summary.py
# (empty output — all 10 protected files untouched)
```

**Seva regression suite GREEN:**

```bash
$ cd scheduler && uv run pytest tests/test_weekly_sweeper.py tests/agents/test_juno_daily_summary.py -x
# 24 passed in 11.86s
```

**CI grep gates PASS:**

```bash
$ bash scripts/verify-anthropic-resolver.sh
PASS — all Anthropic client instantiations routed through scheduler/anthropic_client.py
$ bash scripts/verify-tenant-isolation.sh
PASS — all tenant-scoped selects routed through queries/scoped.py
```

**Full scheduler regression:**

```bash
$ cd scheduler && uv run pytest -q | tail -3
359 passed, 1 skipped, 4 warnings in 12.34s
```

359 passed (342 baseline + 17 new = 359). Perfect match. Pre-existing 4 `RuntimeWarning` on `daily_summary_prune.py` AsyncMock are unrelated to this plan (verified in Plan 15-02 summary).

## Grep Gates Verification

| Gate | Expected | Actual | Pass |
|------|----------|--------|------|
| `async def run_juno_weekly_sweeper` | == 1 | 1 | ✓ |
| `get_anthropic_client("juno"` (production call) | == 1 | 1 (line 394) | ✓ |
| `get_anthropic_client(company_id` (variable form forbidden) | == 0 (production code) | 0 (only in comment-line docstring) | ✓ |
| `get_anthropic_client('seva'` (cross-billing forbidden) | == 0 | 0 | ✓ |
| `JUNO_SWEEPER_X_QUERY` references | >= 2 | 4 | ✓ |
| `JUNO_SWEEPER_SYSTEM_PROMPT` references | >= 2 | 3 | ✓ |
| `call_with_refusal_guard` references | >= 2 | 5 | ✓ |
| `scoped_weekly_sweeps` references | >= 2 | 3 | ✓ |
| `scoped_summaries` references | >= 2 | 3 | ✓ |
| `fetch_top_x_posts` references | >= 2 | 2 | ✓ |
| `canonical_url` references | >= 2 | 11 | ✓ |
| `_sunday_of_this_week` references | >= 2 | 4 | ✓ |
| `'running', 'completed', 'partial'` literal (Phase 9 fix) | >= 1 | 2 | ✓ |
| 3-sub-array union pattern | >= 3 | 3 | ✓ |
| `company_id="juno"` (production INSERT) | >= 1 | 2 | ✓ |
| `AGENT_NAME = "juno_weekly_sweeper"` | == 1 | 1 | ✓ |
| `__main__` block | == 1 | 1 | ✓ |
| `asyncio.run(run_juno_weekly_sweeper())` | == 1 | 1 | ✓ |
| `Anthropic(api_key` (production code) | == 0 | 0 (1 match in comment line, exempt per CI gate filter) | ✓ |
| Raw `select(WeeklySweep)` / `select(DailySummary)` | == 0 | 0 | ✓ |
| Production file line count | >= 400 | 588 | ✓ |
| Test file `def test_` count | >= 12 | 17 | ✓ |
| Test file line count | >= 300 | 799 | ✓ |

All 22 acceptance grep gates pass.

## Issues Encountered

None during execution. The single test fixture issue (lowercase URL path expectation) was self-fixed during Task 2 acceptance verification before the Task 2 commit landed (~1 min iteration). No blockers, no scope creep, no carry-over.

## Self-Check: PASSED

- `scheduler/agents/juno_weekly_sweeper.py` exists — FOUND
- `scheduler/tests/agents/test_juno_weekly_sweeper.py` exists — FOUND
- `.planning/phases/15-juno-weekly-viral-sweeper/15-05-SUMMARY.md` exists — FOUND (this file)
- Commit `44566d0` (Task 1: feat) — FOUND in git log
- Commit `3e1e605` (Task 2: test) — FOUND in git log
- 17/17 new tests GREEN — VERIFIED
- 359 passed in full suite (342 baseline + 17 new) — VERIFIED
- D-10 byte-identical contract — VERIFIED (10 protected files, empty `git status --porcelain`)
- CI grep gates PASS — VERIFIED (verify-anthropic-resolver.sh + verify-tenant-isolation.sh)
- ruff lint clean — VERIFIED on both new files
- Phase 12 D-07 hardcoded literal contract — VERIFIED (`get_anthropic_client("juno", timeout=JUNO_SWEEPER_SONNET_TIMEOUT)` at line 394; production code uses double-quoted literal; CI grep gate exempts comment-line docstring mentions)
- Phase 9 idempotency-filter-includes-partial — VERIFIED (line 332: `status.in_(["running", "completed", "partial"])`)
- D-06 helper-share LOCKED — VERIFIED (line 65: `from agents.weekly_sweeper import canonical_url, _sunday_of_this_week`; test `test_d10_helper_share_imports_from_seva_module` enforces identity)
- D-05 refusal-detector reused verbatim — VERIFIED (line 56: `from agents.juno_refusal_detector import call_with_refusal_guard`)
- __main__ smoke-fire escape hatch present — VERIFIED (lines 547-555)

## User Setup Required

None — no external service configuration. Plan 15-06 (Wave 3) will register the cron in worker.py and add the `JUNO_SWEEPER_CRON_ENABLED` env-gate. Operator smoke fire (D-07 step 2) runs via `python -m agents.juno_weekly_sweeper` against the production DB once Plan 15-06 lands AND Plan 15-01's substrate-keys writer is deployed to Railway scheduler service (so the virality compute has non-empty Juno daily-summary rows to read from).

## Next Phase Readiness

- **Plan 15-06 (Wave 3 — next) UNBLOCKED:** worker.py can `from agents.juno_weekly_sweeper import run_juno_weekly_sweeper` and register the cron at lock 1021 with `CronTrigger(day_of_week='sun', hour=8, minute=0, timezone='America/Los_Angeles')` env-gated by `JUNO_SWEEPER_CRON_ENABLED`.
- **No blockers** for Plan 15-06's worker.py changes — the import surface is stable; Plan 15-06 only adds the cron registration block (mirrors Phase 10's `JUNO_CRON_ENABLED` pattern).
- **Plan 15-07 (Wave 3 — final) operator voice UAT** depends on Plan 15-06 landing + Railway env flip + manual smoke fire producing 3 angles for the operator to evaluate. This plan delivers the synthesis module that Plan 15-07's UAT will assess.

## Outstanding Concerns

- **First production smoke fire risk:** When Plan 15-06's cron registration lands and operator runs `python -m agents.juno_weekly_sweeper` for the first time, the virality compute will read Juno daily-summary rows. Per Plan 15-01's D-03b backfill-window note, rows written BEFORE Plan 15-01's deploy carry empty/missing substrate keys; rows written AFTER carry populated arrays. First 0-2 sweeps may produce `status='partial'` with INSUFFICIENT_SIGNAL_FALLBACK copy. **This is acceptable per CONTEXT D-03b** — the test `test_insufficient_signal_does_not_call_sonnet` exercises this path and the orchestrator correctly tags it 'partial' with explanatory copy.
- **X handle verification (D-02 RESEARCH §1 corrections):** Plan 15-02's `JUNO_SWEEPER_X_QUERY` constant already uses the 4 corrected handle spellings (`defense_news`, `CDAInstitute`, `CanadianForces`, `JanesINTEL`) + 2 added Tier-2 Canadians (`DavePerryCGAI`, `Murray_Brewster`). No re-verification needed in this plan.

## Phase 15 Wave 2 Status

This plan + the parallel Plan 15-06 form Wave 2. Plan 15-06 (cron registration in worker.py) imports this module's `run_juno_weekly_sweeper`. After both Wave 2 plans land + Plan 15-07 voice UAT, Phase 15 is verifier-ready.

---
*Phase: 15-juno-weekly-viral-sweeper*
*Plan: 05*
*Completed: 2026-05-21*
