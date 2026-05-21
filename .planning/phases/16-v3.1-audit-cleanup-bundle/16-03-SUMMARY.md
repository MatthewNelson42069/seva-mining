---
phase: 16-v3.1-audit-cleanup-bundle
plan: 03
subsystem: testing
tags: [ruff, lint, F401, scheduler, cleanup, tech-debt]

# Dependency graph
requires:
  - phase: 11-audit-cleanup-bundle
    provides: "audit-cleanup-bundle shape (single-task-per-cleanup-item plans)"
  - phase: 10-juno-defence-news-funnel
    provides: "agents/juno_relevance.py exports including HAIKU_MODEL (subsequently became unused in daily_summary.py)"
  - phase: 9-tenant-isolation
    provides: "scoped_* helper migration that left `from sqlalchemy import select` orphaned in weekly_sweeper.py"
provides:
  - "Scheduler F401 baseline: cd scheduler && uv run ruff check exits 0 (was: 6 errors)"
  - "5 scheduler files lint-clean for F401 (4 plan-listed + 1 surfaced-during-fix)"
  - "Zero noqa F401 suppressions added"
affects: [v3.1-milestone-archive, ci-lint-gates, future-scheduler-imports]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Conservative ruff --fix as canonical removal path for F401 (vs. manual edits)"
    - "Plan-vs-reality drift handling: when --fix surfaces an additional F401 in a file not on plan, apply Rule 3 (blocking) to satisfy the authoritative tool-exit-code gate"

key-files:
  created:
    - ".planning/phases/16-v3.1-audit-cleanup-bundle/16-03-SUMMARY.md"
  modified:
    - "scheduler/agents/daily_summary.py — removed unused HAIKU_MODEL import"
    - "scheduler/agents/weekly_sweeper.py — removed unused `from sqlalchemy import select`"
    - "scheduler/scripts/uat_voice_calibration.py — removed unused _build_juno_world_events_section"
    - "scheduler/tests/agents/test_juno_health_check.py — removed unused MagicMock + pytest"
    - "scheduler/models/weekly_sweep.py — removed unused `from datetime import datetime` (Rule 3 deviation)"

key-decisions:
  - "Trusted ruff --fix for all 6 F401 removals — tool handles surgical compound-import edits (e.g., keeping 3 of 4 symbols from `from agents.juno_relevance import (...)`) more reliably than manual edits"
  - "Applied Rule 3 (blocking) to include scheduler/models/weekly_sweep.py — it carried a 6th F401 (`from datetime import datetime`) not enumerated in the plan, but the plan's authoritative gate is `uv run ruff check exits 0` and that cannot be satisfied while leaving any F401 unfixed"
  - "Did NOT add `# noqa: F401` to any import — all 6 flagged symbols verified true-unused via grep pre-fix"

patterns-established:
  - "F401 cleanup pattern: grep-verify true-unused → ruff --fix → verify exit 0 → run test baseline → smoke-import-check"
  - "Authoritative-gate-over-enumerated-count: when plan lists N expected fixes but tool surfaces N+M, trust the tool exit code as the gate; document the delta as a deviation"

requirements-completed: [CLEAN-03]

# Metrics
duration: 4min
completed: 2026-05-20
---

# Phase 16 Plan 03: Scheduler ruff F401 cleanup Summary

**Removed 6 unused-import F401 errors across 5 scheduler files via `uv run ruff check --fix`; ruff now exits 0; scheduler tests stay at 363 pass baseline.**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-05-21T02:40:00Z (approx)
- **Completed:** 2026-05-21T02:44:00Z
- **Tasks:** 1 of 1
- **Files modified:** 5

## Accomplishments

- Scheduler ruff F401 baseline cleared: `cd scheduler && uv run ruff check` now exits 0 with "All checks passed!" (was: "Found 6 errors. [*] 6 fixable")
- All 6 unused imports removed surgically via `uv run ruff check --fix` — no manual edits required; ruff's auto-fix correctly handled compound `from X import (A, B, C)` blocks (keeping used symbols, dropping only the unused one)
- Zero `# noqa: F401` suppressions added — every flagged import verified true-unused via pre-fix grep
- Scheduler regression baseline preserved exactly: 363 passed (matches Phase 15 baseline per `.planning/v3.1-MILESTONE-AUDIT.md` regression_baseline.scheduler)
- Module-level import smoke check OK: `from agents.daily_summary import run_juno_daily_summary; from agents.weekly_sweeper import run_weekly_sweeper` prints `OK` — confirming deleted imports were not silent re-exports
- CI grep gates remain green: `verify-anthropic-resolver.sh` PASS, `verify-tenant-isolation.sh` PASS

## Task Commits

1. **Task 1: CLEAN-03 — Scheduler ruff F401 cleanup (6 unused imports across 4+1 files)** — `bcae991` (fix)

_Note: All 6 F401 removals committed atomically in one task commit — they form a single semantic unit (one ruff --fix invocation, one acceptance gate)._

## Files Created/Modified

### Per-file removals

| File | Symbol removed | Pre-fix usage check | Verdict |
| ---- | -------------- | ------------------- | ------- |
| `scheduler/agents/daily_summary.py:57` | `HAIKU_MODEL` | `grep -c HAIKU_MODEL` returned 1 (import only) | True unused — removed |
| `scheduler/agents/weekly_sweeper.py:44` | `from sqlalchemy import select` | `grep -nE '\bselect\(' ` returned 0 (no callsites) | True unused — removed (whole line) |
| `scheduler/scripts/uat_voice_calibration.py:56` | `_build_juno_world_events_section` | `grep -nE '_build_juno_world_events_section\('` returned 0 | True unused — removed |
| `scheduler/tests/agents/test_juno_health_check.py:23` | `MagicMock` (from `unittest.mock`) | `grep -nE '\bMagicMock\b'` returned 1 (import only) | True unused — removed |
| `scheduler/tests/agents/test_juno_health_check.py:25` | `pytest` | `grep -nE '\bpytest\.'` returned 0 (no pytest.X uses, no fixture decorators) | True unused — removed |
| `scheduler/models/weekly_sweep.py:2` | `from datetime import datetime` | `grep -c datetime` returned 1 (import only) | True unused — removed (NOT plan-enumerated; see Deviations) |

### test_juno_health_check.py — the newly-surfaced F401s detail

The plan said "MagicMock + pytest (+ possibly 1 more)" surfaced during audit. Live audit run showed exactly **2** F401s in this file: `MagicMock` and `pytest`. The "+1 more" hedge in the plan was conservative — there were only 2 in this file. The 6th overall F401 was in a different file entirely: `scheduler/models/weekly_sweep.py` (see Deviations).

### Compound-import surgical handling (audit notes)

Two of the files had compound `from X import (A, B, C, D)` blocks where only one symbol was unused — ruff's auto-fix handled these correctly:

- `scheduler/agents/daily_summary.py:53-58` pre-fix had `from agents.juno_relevance import (classify_story, survives_threshold, DefenceRelevance, HAIKU_MODEL,)`. Post-fix: 3 symbols remain (HAIKU_MODEL gone, trailing comma + parens preserved). Verified via `git diff`.
- `scheduler/scripts/uat_voice_calibration.py:54-60` pre-fix had `from agents.daily_summary import (_build_juno_defence_news_section, _build_juno_world_events_section, JUNO_SONNET_MODEL, JUNO_SONNET_MAX_PROCUREMENT, JUNO_SONNET_TIMEOUT,)`. Post-fix: 4 symbols remain (`_build_juno_world_events_section` gone). Verified via `git diff`.
- `scheduler/tests/agents/test_juno_health_check.py:23` pre-fix had `from unittest.mock import MagicMock` — single-symbol, ruff deleted the whole line. The file did NOT share that import line with `AsyncMock` or others (the original plan worried about this — no such concern materialized).

### Smoke check

```bash
cd /Users/matthewnelson/seva-mining/scheduler && uv run python -c \
  "from agents.daily_summary import run_juno_daily_summary; \
   from agents.weekly_sweeper import run_weekly_sweeper; \
   print('OK')"
# Output: OK
```

### Scheduler test pass count

```
363 passed, 1 skipped, 4 warnings in 12.88s
```

Matches Phase 15 baseline exactly (`.planning/v3.1-MILESTONE-AUDIT.md` regression_baseline.scheduler = 363). The 4 warnings are pre-existing `RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited` in `test_daily_summary_prune.py` — unrelated to this plan (owned by Plan 16-04's domain, file-disjoint from any file I touched).

## Decisions Made

- **Trusted `uv run ruff check --fix` over manual edits** — ruff's removal logic is conservative (only removes imports it's certain are unused, never breaks re-exports or type-only imports) and handles compound-import surgical edits cleanly. All 6 removals applied via one tool invocation; subsequent `git diff` inspection confirmed only the unused symbols were removed.
- **Authoritative gate over enumerated count** — when ruff surfaced a 6th F401 in a non-plan-listed file (`scheduler/models/weekly_sweep.py`), I applied Rule 3 (blocking) rather than leaving it. The plan's stated acceptance gate is `cd scheduler && uv run ruff check exits 0`, and that cannot be satisfied while any F401 remains. Documented as deviation below.
- **No noqa suppressions** — all 6 symbols verified true-unused via grep. Adding `# noqa: F401` would mask real tech debt and defeat CLEAN-03's intent.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] Included `scheduler/models/weekly_sweep.py` in the fix scope**
- **Found during:** Task 1 (initial ruff baseline run, before `--fix`)
- **Issue:** The plan enumerated 4 files (`daily_summary.py`, `weekly_sweeper.py`, `uat_voice_calibration.py`, `test_juno_health_check.py`) carrying 6 F401 errors. Live ruff output showed the 6 errors distributed as: 1 in daily_summary, 1 in weekly_sweeper, 1 in uat_voice_calibration, 2 in test_juno_health_check, **and 1 in `models/weekly_sweep.py`** (`from datetime import datetime` unused). The plan's "+ 1 more F401 in same test_juno_health_check.py file" hedge was wrong — the 6th F401 was in a different file. Without including `models/weekly_sweep.py` in the fix, the authoritative gate (`uv run ruff check exits 0`) would still fail with 1 remaining F401.
- **Fix:** Allowed `uv run ruff check --fix` to remove the unused `from datetime import datetime` import from `scheduler/models/weekly_sweep.py:2`. Pre-fix grep confirmed `datetime` appeared exactly 1 time in the file (the import line itself) — true unused, no false-positive risk.
- **Files modified:** `scheduler/models/weekly_sweep.py` (1 line removed, no behavior change — it's a SQLAlchemy model with `Date` + `DateTime` columns from `sqlalchemy`, not the stdlib `datetime`)
- **Verification:** `grep -c datetime scheduler/models/weekly_sweep.py` returned 1 (import only) pre-fix → returned 0 post-fix. Scheduler test suite still 363 passed (no test broke from the removal). Module imports clean.
- **Committed in:** `bcae991` (Task 1 commit)
- **Coordination note:** `backend/app/models/weekly_sweep.py` (the SQLAlchemy twin in the backend service) is being modified by another parallel executor (likely 16-02) — that's a different file in a different service. My touch was scoped to `scheduler/models/weekly_sweep.py` only. `git diff --stat scheduler/` confirms I only touched scheduler/.

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** The deviation was required to satisfy the plan's own acceptance gate. The plan's `files_modified` list was authored on slightly stale information; the live ruff output (the plan's stated source of truth) showed 5 files with F401s, not 4. Scope creep risk = zero (1 trivial unused-import line in a model file with no behavior change). No other ruff rules touched; no noqa suppressions added; no broader file-touching.

## Issues Encountered

- **Plan-enumerated file count drift:** the plan's `files_modified` listed 4 files but the live audit surfaced a 5th file with an F401. Handled via Rule 3 (blocking) deviation. Lesson for future audit-cleanup plans: when the plan's stated gate is a tool-exit-code, prefer "modify whatever the tool reports" over hard-listing files — or alternatively, re-run the audit at plan-write time to lock in the exact file set.
- **None other** — the `--fix` was the canonical one-shot path; no manual edits, no compound-import breakage, no test regressions.

## User Setup Required

None — no external service configuration required. This was a pure-code lint cleanup.

## Next Phase Readiness

- **CLEAN-03 closed.** 1 of 5 v3.1 audit cleanup items complete; contributes to the v3.1 milestone archive unblock at 5/5 phases (16-01/02/03/04/05 are running in parallel as Wave 1).
- **No blockers for downstream plans in this phase** — file-disjoint from 16-01/02/04/05.
- **Scheduler lint baseline now clean** — future scheduler plans inherit a "ruff exits 0" baseline; any new F401 introduced will be caught immediately by CI.
- **Coordination with 16-04 verified:** I did NOT touch `scheduler/tests/agents/test_daily_summary_prune.py` (16-04's scope). `git show --stat HEAD` confirms my commit touched only the 5 files listed above.

---
*Phase: 16-v3.1-audit-cleanup-bundle*
*Plan: 03 (CLEAN-03 — scheduler ruff F401 cleanup)*
*Completed: 2026-05-20*

## Self-Check: PASSED

- File exists: `scheduler/agents/daily_summary.py` (modified) — FOUND
- File exists: `scheduler/agents/weekly_sweeper.py` (modified) — FOUND
- File exists: `scheduler/scripts/uat_voice_calibration.py` (modified) — FOUND
- File exists: `scheduler/tests/agents/test_juno_health_check.py` (modified) — FOUND
- File exists: `scheduler/models/weekly_sweep.py` (modified, deviation) — FOUND
- File exists: `.planning/phases/16-v3.1-audit-cleanup-bundle/16-03-SUMMARY.md` (this file) — FOUND
- Commit exists: `bcae991` (fix(16-03): remove 6 F401 unused imports) — FOUND
- Ruff exit code: 0 (verified `cd scheduler && uv run ruff check` → "All checks passed!")
- Test count: 363 passed (matches baseline)
- CI gates: `verify-anthropic-resolver.sh` PASS exit 0; `verify-tenant-isolation.sh` PASS exit 0
- No noqa F401 added: `grep -rc "# noqa: F401" scheduler/ | grep -v ':0$' | wc -l` = 0
