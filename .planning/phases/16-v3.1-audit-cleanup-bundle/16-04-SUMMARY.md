---
phase: 16-v3.1-audit-cleanup-bundle
plan: 04
subsystem: testing
tags: [pytest, asyncmock, magicmock, runtimewarning, sqlalchemy-async, scheduler, daily_summary_prune]

# Dependency graph
requires:
  - phase: 04-daily-summary-prune
    provides: run_daily_summary_prune + test_daily_summary_prune.py (the cron + its 5-test harness whose mocks Plan 16-04 corrects)
  - phase: 15-v3.1-juno-finish-line
    provides: D-10 scheduler regression baseline (363 tests) which Plan 16-04 must preserve
provides:
  - Zero RuntimeWarnings in test_daily_summary_prune.py (was 4 pre-existing carry-over)
  - Documented MagicMock-vs-AsyncMock convention for SQLAlchemy `session.add()` (sync) vs awaitable methods (commit/refresh/execute/get)
  - Dead helper code removal (`_make_session()` + `sessions_created` list) in the test factory
affects: [future-async-test-authoring, scheduler-test-conventions, async-mock-patterns]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "session.add() is SYNC on AsyncSession (SQLAlchemy queues the object without I/O) — mocks for sync methods on otherwise-async session must use MagicMock, not AsyncMock, or pytest emits `coroutine was never awaited` RuntimeWarning"
    - "Promoted-to-error mode (`pytest -W error::RuntimeWarning`) is the drift-tolerant authoritative gate for warning regressions — preferred over string-grep counts that drift with pytest version output formatting"

key-files:
  created: []
  modified:
    - scheduler/tests/agents/test_daily_summary_prune.py (mocks for sess1.add fixed; dead _make_session helper deleted)

key-decisions:
  - "Applied Pattern A (MagicMock substitution) for sess1.add only — kept AsyncMock for commit/refresh/execute/get since production code DOES await those"
  - "Applied Pattern C (dead-code deletion) for the orphan _make_session() helper at lines 76-81 — never invoked anywhere in the file; the actual factory closure is _factory() at lines 110+"
  - "Did NOT apply Pattern B (return_value=None) — none of the warnings traced to fire-and-forget awaited paths; all 4 traced to the same line: production session.add(agent_run) at daily_summary_prune.py:60"

patterns-established:
  - "MagicMock vs AsyncMock decision rule: if the production code does NOT `await` the call, use MagicMock; if it DOES, use AsyncMock. SQLAlchemy `session.add()` is sync; `session.commit()`, `session.refresh()`, `session.execute()`, `session.get()` are async."
  - "Use `-W error::RuntimeWarning` flag to promote warnings to errors for drift-tolerant CI gating on unawaited-coroutine regressions"

requirements-completed: [CLEAN-04]

# Metrics
duration: 9min
completed: 2026-05-20
---

# Phase 16 Plan 04: scheduler-test-runtimewarning-fix Summary

**Eliminated 4 pre-existing `RuntimeWarning: coroutine was never awaited` warnings in `test_daily_summary_prune.py` by switching `sess1.add` from AsyncMock to MagicMock (production `Session.add()` is sync) and deleting an unused helper — production prune module byte-identical.**

## Performance

- **Duration:** ~9 min
- **Started:** 2026-05-21T02:35:00Z (approximate, parallel Wave 1 start)
- **Completed:** 2026-05-21T02:44:39Z
- **Tasks:** 1
- **Files modified:** 1 (test only)

## Accomplishments

- CLEAN-04 closed — pytest output now shows 0 RuntimeWarnings for `test_daily_summary_prune.py` (was 4 per `.planning/v3.1-MILESTONE-AUDIT.md` tech_debt.pre_existing_carried_over → fourth bullet)
- Authoritative behavioral gate satisfied: `pytest tests/agents/test_daily_summary_prune.py -W error::RuntimeWarning -q` exits 0 (was: 4 warnings → 4 errors under promoted-to-error mode)
- Test count unchanged: 5/5 still pass
- D-10 regression baseline preserved: full scheduler suite still 363 passed, 1 skipped
- Production code byte-identical: `scheduler/agents/daily_summary_prune.py` MD5 `e33509b8dbedfc2a32d534902aecb837` before and after
- No warning suppressions introduced (`warnings.filterwarnings` count = 0) — the warnings are RESOLVED, not silenced
- Dead `_make_session()` helper + `sessions_created` list at lines 76-81 cleaned up (never invoked anywhere in file)
- Code comment added explaining the MagicMock-vs-AsyncMock convention so future test authors don't reintroduce the bug

## Task Commits

Each task was committed atomically with `--no-verify` (parallel Wave 1 protocol):

1. **Task 1: CLEAN-04 — Fix 4 unawaited-coroutine RuntimeWarnings in test_daily_summary_prune.py** — `5fc45f0` (fix)

_Note: The 5fc45f0 commit also swept in `frontend/src/pages/SummaryFeedPage.tsx` due to a race condition with parallel agent 16-05 staging files at the same moment. See "Issues Encountered" below. The test fix itself is correctly captured; the frontend hunk is 16-05's work attributed under 16-04's commit message due to git index race._

## Files Created/Modified

- `scheduler/tests/agents/test_daily_summary_prune.py` — Two `sess1.add = AsyncMock()` → `sess1.add = MagicMock()` substitutions (one in `_build_session_factory` helper at L83, one in inline factory inside `test_prune_writes_failure_telemetry_on_exception` at L237). Deleted dead helper `_make_session()` + `sessions_created` list at lines 76-81. Added inline comments explaining the convention. Net: 7 insertions, 10 deletions.

## Diagnosis (root cause walkthrough)

The 4 warnings all pointed to the same source line in production:

```
/Users/matthewnelson/seva-mining/scheduler/agents/daily_summary_prune.py:60: RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited
    session.add(agent_run)
```

Line 60 in `daily_summary_prune.py` is `session.add(agent_run)` — a **synchronous** call (SQLAlchemy's `AsyncSession.add()` just queues the object in the in-memory identity map; no I/O, no `await`).

The test factory set `sess1.add = AsyncMock()`. When the production code called `sess1.add(agent_run)` (no `await`, correctly), the AsyncMock returned a coroutine object that was then discarded. Python's GC eventually destroyed that coroutine without it ever being awaited → 1 RuntimeWarning per test that exercised this path. The 4 async tests in the file each triggered one warning; the 5th test (`test_prune_function_is_callable_with_no_args`) is sync and doesn't run the prune flow, so emits no warning.

**Fix pattern applied — Pattern A (MagicMock substitution):** `sess1.add` is now `MagicMock()`. The other session methods (`sess1.commit`, `sess1.refresh`, `sess2.execute`, `sess2.commit`, `sess3.get`, `sess3.commit`) remain `AsyncMock` because production code DOES `await` them. This is the surgical, correct fix.

**Bonus cleanup — Pattern C (dead code deletion):** The `_make_session()` closure and `sessions_created` list at lines 76-81 were defined but never invoked anywhere. Removed. Not the warning source, but auditing the file for the fix surfaced this dead code so it was cleaned up in the same commit.

## Verification (all gates PASS)

| Gate | Command | Expected | Actual |
| --- | --- | --- | --- |
| **Authoritative behavioral gate** | `cd scheduler && uv run pytest tests/agents/test_daily_summary_prune.py -W error::RuntimeWarning -q` | exit 0 | exit 0 (5 passed) |
| RuntimeWarning string count | `pytest tests/agents/test_daily_summary_prune.py 2>&1 \| grep -c "RuntimeWarning: coroutine was never awaited"` | 0 | 0 |
| Test count for file | `pytest tests/agents/test_daily_summary_prune.py -v` | 5 passed | 5 passed |
| Full scheduler suite | `pytest -q` | exit 0, >=363 pass | exit 0, **363 passed, 1 skipped** in 9.31s |
| No warning suppressions | `grep -c "warnings.filterwarnings" scheduler/tests/agents/test_daily_summary_prune.py` | 0 | 0 |
| Production code untouched | `md5 scheduler/agents/daily_summary_prune.py` | unchanged from baseline | `e33509b8dbedfc2a32d534902aecb837` (identical before & after) |
| Only test file modified for this plan's scope | `git diff --stat scheduler/tests/agents/test_daily_summary_prune.py` | 1 file, modified | 1 file, +7/-10 |

## Decisions Made

- **Pattern A over Pattern B:** Could have used `AsyncMock(return_value=None)` to make every call explicit, but Pattern A (MagicMock for sync methods) is the architecturally honest fix — it reflects the actual sync/async split in SQLAlchemy's API. Pattern B would have left the misleading "this is async" signal on a sync method.
- **Pattern C included in the same commit:** Bonus dead-code deletion was scoped to the same factory function being fixed; not a scope-creep concern, and atomic with the fix.
- **No `warnings.filterwarnings` suppression:** Explicitly rejected — the plan calls for RESOLVING the warnings, not silencing them. CLEAN-04 is a hygiene gate; silencing would defeat the purpose.
- **Did not touch `scheduler/agents/daily_summary_prune.py`:** The audit explicitly attributed the bug to "AsyncMock misconfig" in the test, not the production code. Production is byte-identical.

## Deviations from Plan

None — plan executed exactly as written. Pattern A (MagicMock substitution) and Pattern C (dead `_make_session()` deletion) were both listed in the plan's `<action>` as candidate patterns; the diagnostic in Step 1 revealed Pattern A as the root-cause fix, and Pattern C was applied as bonus cleanup since the same factory function was being edited.

## Issues Encountered

**1. Parallel-agent git index race condition (Wave 1)**
- **Symptom:** My `git add scheduler/tests/agents/test_daily_summary_prune.py && git commit` swept in `frontend/src/pages/SummaryFeedPage.tsx` — a file owned by parallel plan 16-05 (Juno empty-state copy refresh).
- **Cause:** Parallel executor 16-05 had staged its frontend file in the shared `.git/index` between my `git add` (which only specified the test file) and the `git commit` (which writes from the full staging area). Git's `commit` consumes everything currently staged, not just files added in the immediately-prior `add` call.
- **Resolution:** Did NOT revert — reverting would either lose 16-05's work or trigger a second race. The frontend hunk is correctly attributed to CLEAN-05 (Juno empty-state) in content; only the commit MESSAGE attributes it to 16-04. 16-05's own SUMMARY will reference the same file. The verifier can confirm both plans' file-disjoint contracts via `git log -p --follow` per file.
- **Impact:** Zero functional impact. Both plans' artifacts are in `HEAD`. CLEAN-04's authoritative gate (`pytest -W error::RuntimeWarning -q` exit 0) and CLEAN-04's file-scope contract (test file only modified) are both satisfied — the frontend file is NOT in the scope of CLEAN-04's `must_haves.artifacts` list.
- **Process note for future parallel waves:** The orchestrator should serialize `git add` + `git commit` per executor (lock the index) rather than rely on `git add <specific-file>` to scope the commit. The `--no-verify` parallel protocol is necessary but not sufficient; a per-executor commit lock is also needed. This is a tooling concern, not a CLEAN-04 issue.

## User Setup Required

None — pure test-infrastructure fix. No env vars, no service config, no migrations, no deploys. Production prune cron continues to run unchanged at 03:00 PT daily under advisory lock 1018.

## Next Phase Readiness

- **CLEAN-04 closed** — 1 of 5 v3.1 audit cleanup items complete; contributes to v3.1 milestone archive unblock.
- **Parallel Wave 1 status:** 16-04 done. 16-03 visible in log (`bcae991 fix(16-03): remove 6 F401 unused imports across scheduler (CLEAN-03)`). 16-01, 16-02, 16-05 should be landing in parallel; verifier will reconcile final phase state.
- **Convention to propagate:** The MagicMock-vs-AsyncMock decision rule (sync session methods use MagicMock; awaited methods use AsyncMock) should be added to scheduler test conventions if/when a CONVENTIONS.md or test-style guide is created. Currently documented inline in the test file via the comments added by this plan.
- **No blockers for Phase 17 / milestone archive** introduced by this plan.

## Self-Check: PASSED

- File `/Users/matthewnelson/seva-mining/scheduler/tests/agents/test_daily_summary_prune.py` exists and contains the fix (verified via `git show HEAD -- scheduler/tests/agents/test_daily_summary_prune.py`).
- Commit `5fc45f0` exists in `git log --oneline -3` and includes the test-file diff.
- Production file `/Users/matthewnelson/seva-mining/scheduler/agents/daily_summary_prune.py` exists, MD5 unchanged from baseline.
- Authoritative gate (`pytest -W error::RuntimeWarning -q`) confirmed exit 0 in this session.
- Full scheduler suite confirmed 363 passed / 1 skipped in this session.

---
*Phase: 16-v3.1-audit-cleanup-bundle*
*Plan: 04*
*Completed: 2026-05-20*
