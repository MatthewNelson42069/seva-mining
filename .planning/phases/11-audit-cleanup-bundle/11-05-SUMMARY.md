---
phase: 11-audit-cleanup-bundle
plan: 5
subsystem: observability
tags: [haiku, pydantic, validation-error, agent_runs, juno, accumulator]

# Dependency graph
requires:
  - phase: 10-defence-news-funnel
    provides: juno_relevance.classify_story (Haiku 4.5 + Anthropic structured outputs)
  - phase: 11-audit-cleanup-bundle/11-01
    provides: both-fires procurement path (Juno now classifies world-events on both 08:05 + 12:05 fires, doubling the surface area where ValidationError can fire)
provides:
  - Haiku ValidationError observability via caller-owned list[dict] accumulator (no module-globals, no re-raise, fail-closed behaviorally preserved)
  - agent_runs.notes['haiku_validation_errors'] surfaced for operator review
  - Forward-compatible accumulator pattern reusable by other Anthropic structured-output callers
affects: [v3.1, defence-news-funnel, juno_daily_summary]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Caller-owned accumulator: list[dict] | None = None keyword-only parameter; callee appends BEFORE fail-closing; caller surfaces into agent_runs.notes"
    - "Specific-then-broad exception arms: except ValidationError (observability + fail-close) → except Exception (broad fail-close safety net)"

key-files:
  created:
    - scheduler/tests/agents/test_juno_relevance.py (3 new tests appended)
  modified:
    - scheduler/agents/juno_relevance.py (classify_story gains validation_errors kwarg + ValidationError arm)
    - scheduler/agents/daily_summary.py (_build_juno_world_events_section threads accumulator; run_juno_daily_summary lifts into notes_dict)

key-decisions:
  - "Caller-owned accumulator chosen over module-global (test isolation) and over re-raise (would break fail-closed contract)"
  - "Backwards-compat default validation_errors=None preserves 2-arg signature; legacy callers in tests untouched"
  - "ValidationError-specific except arm runs FIRST inside try/except; broad-Exception arm preserved as final guard for non-schema failures (network, timeout)"
  - "Haiku temperature tuning explicitly DEFERRED to v3.1 — no production telemetry yet to justify a non-default value; observability-first lets us collect data before tuning"
  - "input_excerpt = title + ' | ' + snippet capped at 200 chars; error_msg = str(exc) capped at 200 chars — matches CLEANUP-05 acceptance spec"

patterns-established:
  - "Pattern: structured-output ValidationError observability — the v3.0 audit's Skydio dual-use exclusion incident exposed the gap; this pattern is reusable by any Anthropic messages.parse(output_format=...) caller"

requirements-completed: [CLEANUP-05]

# Metrics
duration: 11min
completed: 2026-05-20
---

# Phase 11 Plan 5: Haiku 4.5 ValidationError Observability Summary

**Caller-owned accumulator threads pydantic.ValidationError instances from Haiku's structured-output classifier into agent_runs.notes['haiku_validation_errors'] without breaking the fail-closed dual-use exclusion contract.**

## Performance

- **Duration:** ~11 min
- **Started:** 2026-05-20T16:29:47Z
- **Completed:** 2026-05-20T16:40:48Z
- **Tasks:** 2 (TDD: 1 RED→GREEN, 1 plumbing)
- **Files modified:** 3
- **Test delta:** 328 passed → 331 passed (+3 from Task 1's new tests); 1 skipped unchanged

## Accomplishments

- `classify_story` gains keyword-only `validation_errors: list[dict] | None = None` parameter; ValidationError-specific except arm appends `{input_excerpt, error_type, error_msg}` (each str field 200-char capped) BEFORE fail-closing
- Broad `except Exception` arm preserved as final safety net for non-schema failures (network, timeout, auth)
- `_build_juno_world_events_section` owns a local `validation_errors: list[dict]` accumulator, threads it into each `classify_story(...)` call, surfaces it in all 3 diagnostic-return paths under key `haiku_validation_errors`
- `run_juno_daily_summary` lifts `world_diag["haiku_validation_errors"]` into `notes_dict["haiku_validation_errors"]` → lands in `daily_summaries.raw_sources_jsonb` and `agent_runs.notes`
- Fail-closed contract (ROADMAP Hard Part P3) preserved verbatim: ValidationError → return None → item excluded from Sonnet synthesis. The dual-use exclusion behavior is observability-instrumented, not modified.

## Task Commits

Each task was committed atomically with `--no-verify` per parallel-mode protocol (Wave 2 alongside 11-03):

1. **Task 1: TDD RED→GREEN — classify_story validation_errors accumulator** — `54af8d0` (feat)
2. **Task 2: Plumb accumulator through daily_summary.py** — `c46c97b` (feat)

**Plan metadata:** _pending_ (this SUMMARY commit)

Note: Task 1 was landed as a single squashed commit (RED tests + GREEN implementation together) rather than 2 separate commits — the plan did not explicitly require 2-commit splitting, and the intermediate RED-only state was confirmed locally before the GREEN implementation was written (the `TypeError: classify_story() got an unexpected keyword argument 'validation_errors'` failure was observed on both new ValidationError tests before any production code was edited).

## Files Created/Modified

- `scheduler/agents/juno_relevance.py` — Added `ValidationError` to pydantic import; expanded `classify_story` docstring; added keyword-only `validation_errors` param with `None` default; added `except ValidationError` arm that appends to accumulator before fail-closing; broad `except Exception` arm preserved.
- `scheduler/agents/daily_summary.py` — `_build_juno_world_events_section` owns local `validation_errors: list[dict] = []` accumulator; threads it into `classify_story(...)`; surfaces it in all 3 return paths under key `haiku_validation_errors`. `run_juno_daily_summary` lifts `world_diag["haiku_validation_errors"]` into `notes_dict` for persistence to `daily_summaries.raw_sources_jsonb`.
- `scheduler/tests/agents/test_juno_relevance.py` — Appended 3 new tests at EOF covering: (a) ValidationError observability + fail-closed contract, (b) backwards-compat default `validation_errors=None`, (c) non-ValidationError exceptions do NOT pollute the accumulator.

## Decisions Made

**Accumulator pattern chosen over alternatives:**

- **Module-global** rejected — would pollute test isolation (pytest-asyncio shares the module across tests in the file; a global list would accumulate cross-test leakage and require fixture-level cleanup that the existing 12 tests don't have)
- **Re-raise from classify_story** rejected — would break the fail-closed contract because `_build_juno_world_events_section`'s `try/except Exception` would still fire-and-continue, but if the ValidationError leaked further upstream it could disable an entire world-events fire instead of just dropping one offending item
- **Caller-owned accumulator (chosen)** — caller passes a fresh `list[dict]` per fire; classify_story appends on ValidationError; caller surfaces via diagnostic. Clean separation between observability path and control-flow path. `None` default keeps the API backwards-compatible (legacy callers see no behavioral change).

**Haiku temperature tuning DEFERRED to v3.1.** Rationale: the current `client.messages.parse(...)` call uses SDK default temperature (~1.0). Lowering it to ~0.3 would reduce ValidationError rate but would also change the structured-output behavior across all 12 existing GREEN tests — most of which use simple AsyncMock that doesn't depend on temperature, but the new ValidationError test would be the only natural place to validate the new value. We have no production telemetry yet on ValidationError frequency from the now-doubled both-fires Juno cron (11-01); deferring tuning until we have production data is the lower-risk path. Documented in `<objective>` block of 11-05-PLAN.md.

**input_excerpt format = `f"{title} | {snippet}"[:200]`** — matches the operator-facing "Skydio incident" debugging pattern: the operator wants to see what the model was asked to classify, not just the title.

## Deviations from Plan

None — plan executed exactly as written. The plan's "STEP 1 RED → STEP 2 GREEN" ordering was followed verbatim; the 3 new tests were added, the RED state was confirmed locally (2 tests failed with the expected `TypeError`, 1 test passed because the legacy signature it tests was always going to pass — that's intentional, it's the backwards-compat assertion), then the implementation was written and the same test command flipped all 15 to GREEN.

## Issues Encountered

**Parallel-mode coordination with 11-03 agent** — both this plan (11-05) and the parallel 11-03 plan edit `scheduler/agents/daily_summary.py` in disjoint line ranges (11-03: lines 813-823 comment-block deletion; 11-05: lines 1099-1103 call site + 1347-1357 notes_dict). The parallel agent committed first (`8f9fb10` chore + `3736d00` docs), then my Task 1 (`54af8d0`), then my Task 2 (`c46c97b`). No merge conflicts. The diff verification step caught this — at one point my working tree had both 11-03's deletion (unstaged from the parallel worktree's filesystem state) and my additions, but checking `git diff HEAD` after 11-03's commit landed confirmed my changes were purely additive and clean to commit on top of 11-03's already-merged work.

## Verification

```
cd scheduler && uv run pytest -q
# 331 passed, 1 skipped, 4 warnings in 10.14s

cd scheduler && uv run pytest tests/agents/test_juno_relevance.py -v
# 15 passed (12 existing + 3 new from this plan)

cd scheduler && uv run pytest tests/agents/test_juno_daily_summary.py -v
# 7 passed (existing world-events test survived the new diagnostic-key addition)

grep -c 'haiku_validation_errors' scheduler/agents/daily_summary.py
# 5 (1 init reference + 3 diagnostic returns + 1 notes_dict surface)

grep -c 'validation_errors=validation_errors' scheduler/agents/daily_summary.py
# 1 (the classify_story call site)

grep -c 'except ValidationError' scheduler/agents/juno_relevance.py
# 1

grep -c 'except Exception' scheduler/agents/juno_relevance.py
# 1 (broad-Exception arm preserved as final guard)

cd scheduler && uv run python -c "import inspect; from agents.juno_relevance import classify_story; print('validation_errors' in inspect.signature(classify_story).parameters)"
# True
```

## User Setup Required

None — pure code change. No env vars, no migration, no external service config. The new `agent_runs.notes['haiku_validation_errors']` key is opt-in observability — empty list on the happy path, populated only when Haiku returns schema-violating structured output. Operators reviewing agent_runs.notes will see the new key alongside existing keys (no schema change to the JSONB column).

## Next Phase Readiness

- CLEANUP-05 closed; v3.0.1 milestone Wave 2 (11-03 + 11-05) both landed
- Verifier pass next (per orchestrator's plan); then `phase complete` after Wave 2 verifier signs off
- v3.1 carries the Haiku temperature-tuning decision forward: once production runs (08:05 + 12:05 PT both fires per 11-01) accumulate, the operator can review `agent_runs.notes['haiku_validation_errors']` frequency and decide whether to set `temperature=0.3` on the Haiku call

## Self-Check: PASSED

- [x] `scheduler/agents/juno_relevance.py` exists and contains `validation_errors` (verified: 5 hits via grep)
- [x] `scheduler/agents/daily_summary.py` exists and contains `haiku_validation_errors` (verified: 5 hits via grep)
- [x] `scheduler/tests/agents/test_juno_relevance.py` exists and contains the 3 new tests (verified: pytest collected 15 items, 3 new test names visible in `-v` output)
- [x] Commit `54af8d0` exists (Task 1: feat(11-05): add Haiku ValidationError accumulator…)
- [x] Commit `c46c97b` exists (Task 2: feat(11-05): plumb haiku_validation_errors accumulator…)
- [x] Full scheduler suite green: 331 passed, 1 skipped (+3 vs baseline)

---
*Phase: 11-audit-cleanup-bundle*
*Plan: 5 (CLEANUP-05)*
*Completed: 2026-05-20*
