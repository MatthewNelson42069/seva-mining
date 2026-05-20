---
phase: 11-audit-cleanup-bundle
plan: 1
subsystem: scheduler
tags: [serpapi, juno, daily-summary, cleanup, scheduler, tests, atomic-commit]

# Dependency graph
requires:
  - phase: 10-juno-defence-news-funnel
    provides: "_build_juno_canadian_procurement_section + run_juno_daily_summary live impl with morning-only SerpAPI gate"
provides:
  - "Both 08:05 PT and 12:05 PT Juno fires now execute the 7 Canadian-procurement SerpAPI queries"
  - "_build_juno_canadian_procurement_section short-circuit on is_morning_fire=False removed"
  - "serpapi.Client instantiation ungated in run_juno_daily_summary (only gated by env-var presence)"
  - "Test suite asserts both-fires-run-procurement contract (force-morning mocks dropped)"
affects: [11-03-cleanup-stale-section-divider, 11-05-haiku-validation-error-logging, post-Phase-11 v3.0.1 cron operation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Atomic code+test commit pattern for behavior changes that invalidate existing test assertions (Hard Part P1)"

key-files:
  created:
    - ".planning/phases/11-audit-cleanup-bundle/11-01-SUMMARY.md"
  modified:
    - "scheduler/agents/daily_summary.py"
    - "scheduler/tests/agents/test_juno_daily_summary.py"

key-decisions:
  - "Production code change + test refresh land in SAME commit per Hard Part P1 (test goes RED the moment the gate is removed without co-commit)"
  - "is_morning_fire parameter retained on _build_juno_canadian_procurement_section signature for telemetry (agent_runs.notes.is_morning_fire) but no longer gates execution"
  - "_is_juno_morning_fire helper kept (still used for period_label + telemetry) but its docstring refreshed to reflect that SerpAPI dispatch is no longer morning-only (Rule 1 auto-fix — stale doc would mislead future readers)"
  - "no_serpapi_client skip path preserved (env-var-missing fallback still emits diagnostic instead of crashing the run)"

patterns-established:
  - "CLEANUP-NN provenance comments inline at site of change (3 occurrences in test file) plus module-header context block — keeps the why-changed traceable from the test source"

requirements-completed: [CLEANUP-01]

# Metrics
duration: ~10min
completed: 2026-05-20
---

# Phase 11 Plan 1: Remove Morning-Only SerpAPI Gate (CLEANUP-01) Summary

**Both 08:05 PT and 12:05 PT Juno fires now execute the 7 Canadian-procurement SerpAPI queries — production code + test refresh landed atomically per Hard Part P1.**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-05-20T16:21:00Z (approx)
- **Completed:** 2026-05-20T16:31:29Z
- **Tasks:** 2 (committed as 1 atomic commit per Hard Part P1)
- **Files modified:** 2

## Accomplishments

- Removed the `if not is_morning_fire: return ("", {"skipped_reason": "non_morning_fire"}, 0)` short-circuit in `_build_juno_canadian_procurement_section` so noon-fire (12:05 PT) now dispatches SerpAPI instead of returning empty.
- Ungated `serpapi.Client` instantiation in `run_juno_daily_summary` — client constructed on both fires when `settings.serpapi_api_key` is set; the only remaining skip path is "no API key configured" (`no_serpapi_client` diagnostic).
- Updated `_build_juno_canadian_procurement_section` docstring to reflect both-fires contract; retained `is_morning_fire` parameter for telemetry use only.
- Refreshed `_is_juno_morning_fire` docstring (Rule 1 auto-fix — stale doc) so it no longer claims SerpAPI runs morning-only.
- Co-committed test refresh: dropped the two force-`_is_juno_morning_fire=True` patches from `test_serpapi_canadian_procurement` (line 318-320 pre-edit) and `test_canadian_procurement_section` (line 359-361 pre-edit). Added CLEANUP-01 provenance comments inline + a module-header context block.
- Verified: scheduler full pytest 328 passed / 1 skipped (no regressions); the 7 Juno daily-summary tests all GREEN.

## Task Commits

Both tasks committed atomically (Hard Part P1 — co-commit constraint):

1. **Task 1 + Task 2 (atomic):** `1e2c03f` — `feat(11-01): remove morning-only SerpAPI gate; both Juno fires run procurement (CLEANUP-01)`

_Note: Hard Part P1 explicitly required Task 1 (production edit) and Task 2 (test refresh) in the SAME commit. The plan's `task_count: 2` describes logical scope; the commit graph shows 1 atomic landing per the parallel-mode + co-commit constraint._

## Files Created/Modified

- `scheduler/agents/daily_summary.py` — three edits: (1) `_build_juno_canadian_procurement_section` gate + docstring; (2) `run_juno_daily_summary` SerpAPI client init unwrap; (3) `_is_juno_morning_fire` docstring refresh (deviation Rule 1).
- `scheduler/tests/agents/test_juno_daily_summary.py` — three edits: (1) module-header Phase 11 provenance note; (2) `test_serpapi_canadian_procurement` morning-fire patch dropped + CLEANUP-01 comment; (3) `test_canadian_procurement_section` morning-fire patch dropped + CLEANUP-01 comment.
- `.planning/phases/11-audit-cleanup-bundle/11-01-SUMMARY.md` — this file.

## Decisions Made

- **Co-commit Task 1 + Task 2 (Hard Part P1):** Test file references the production gate via `_is_juno_morning_fire=True` mocks; removing the production gate without simultaneously dropping the mocks would still pass tests (over-mocking masks the bug), but the cleaner contract is "tests assert both-fires-run-procurement." Atomic landing keeps git history honest about what shipped together.
- **Retain `is_morning_fire` parameter on signature:** The plan specified retention for telemetry (`agent_runs.notes.is_morning_fire` at line 1355 of `daily_summary.py`). Removing the parameter would force a 3-site refactor (function signature + caller + telemetry payload) with no behavioral benefit — telemetry value is operator-facing (dashboards distinguish the two fires). Plan was correct to retain.
- **Update `_is_juno_morning_fire` docstring (Rule 1 deviation):** Plan didn't mandate this edit, but the helper's docstring claimed "SerpAPI dispatched once per day on the morning fire" — that claim is now factually wrong post-CLEANUP-01. Updating the docstring is Rule 1 (auto-fix stale doc that would mislead future readers).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Stale Doc Bug] Updated `_is_juno_morning_fire` helper docstring**
- **Found during:** Task 1 acceptance criteria verification (grep `non_morning_fire` returned 1 instead of expected 0)
- **Issue:** The helper `_is_juno_morning_fire` (line 195-207 of `scheduler/agents/daily_summary.py`) had a docstring stating "SerpAPI dispatched once per day on the morning fire (saves ~$2-4/mo). The 12:05 PT fire passes is_morning_fire=False; the procurement section returns ('', {'skipped_reason': 'non_morning_fire'}, 0) ..." — this claim was now factually wrong post-CLEANUP-01 and would mislead future readers debugging procurement-section behavior.
- **Fix:** Replaced docstring with the post-CLEANUP-01 contract: "SerpAPI no longer gates on morning-only — both 08:05 PT and 12:05 PT fires execute the 7 Canadian-procurement SerpAPI queries. This helper is retained because `agent_runs.notes.is_morning_fire` is still useful diagnostic data..."
- **Files modified:** `scheduler/agents/daily_summary.py` (helper docstring at lines 195-207)
- **Verification:** Final grep for `non_morning_fire` returns 0 across the whole file; scheduler pytest 328 passed.
- **Committed in:** `1e2c03f` (atomic Task 1 + Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 stale doc / Rule 1)
**Impact on plan:** Single inline doc refresh, no behavioral change. Keeps the codebase truthful about its own contract.

## Issues Encountered

- **Acceptance-criterion grep mismatch (resolved):** Plan's Task 2 acceptance criterion stated "`grep -c '_is_juno_morning_fire'` returns 0" but final grep returned 1 — the lone match was in the module-header CLEANUP-01 provenance comment (line 231) that the plan's Edit 3 explicitly required us to write (it documents the historical force-mock that was dropped). The substantive criterion (no test forces the morning-fire path) is met — confirmed by `grep 'patch.*_is_juno_morning_fire'` returning 0. Documenting as an interpretation note rather than a failure.

## User Setup Required

None — no external service configuration required. Budget delta (~$5.25/mo → ~$8-9/mo Juno SerpAPI) was operator-approved this session; total Juno SerpAPI spend stays inside the $50/mo cap with ~$41 headroom. No Railway env-var changes; no Neon schema change.

## Next Phase Readiness

- Plan 11-01 unblocks Wave 2 (11-03 and 11-05) — both touch `scheduler/agents/daily_summary.py` and must run after 11-01 lands per the planner's wave layout.
- The 12:05 PT Juno cron fire will now write `canadian_procurement_md` non-empty (subject to SerpAPI availability + Sonnet refusal-guard pass) on its next execution. No code-level smoke needed — pytest 328 GREEN is the regression gate.
- Wave 1 sibling plans (11-02 + 11-04) run in parallel on disjoint files (`milestones/v3.0-REQUIREMENTS.md` + `milestones/v3.0-phases/*/VALIDATION.md`).
- Phase 11 success criterion #1 (12:05 PT writes full 3-section brief) is technically satisfied; operator-facing verification will land at the next production fire.

## Self-Check: PASSED

- File `scheduler/agents/daily_summary.py` modified — verified post-commit grep: `non_morning_fire` = 0, `is_morning_fire: bool,` = 1, `"is_morning_fire": is_morning_fire` = 1.
- File `scheduler/tests/agents/test_juno_daily_summary.py` modified — verified: `patch.*_is_juno_morning_fire` = 0; `CLEANUP-01` = 3 occurrences.
- Commit `1e2c03f` exists — `git log --oneline | grep -q 1e2c03f` returns true.
- `scheduler && uv run pytest tests/agents/test_juno_daily_summary.py -v` — 7 passed.
- `scheduler && uv run pytest -x -q` — 328 passed, 1 skipped, no regressions.

---
*Phase: 11-audit-cleanup-bundle*
*Plan: 1*
*Completed: 2026-05-20*
