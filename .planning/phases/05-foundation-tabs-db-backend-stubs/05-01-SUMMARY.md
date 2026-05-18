---
phase: 05-foundation-tabs-db-backend-stubs
plan: 01
subsystem: infra
tags: [apscheduler, advisory-lock, scheduler, postgres, cron-ordering]

# Dependency graph
requires:
  - phase: 04-prune-cron-operations-hardening
    provides: "JOB_LOCK_IDS dict + OPS-02 uniqueness assertion at worker.py:118"
provides:
  - "weekly_sweeper advisory lock ID 1019 reserved in scheduler/worker.py JOB_LOCK_IDS"
  - "Contract: any future code holding lock 1019 must reference JOB_LOCK_IDS[\"weekly_sweeper\"]"
affects: [07-weekly-viral-sweeper, sweeper-cron, SWEEP-03]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Reserve-before-implement: advisory lock IDs registered in JOB_LOCK_IDS before the cron job factory or scheduler registration is written, so OPS-02's startup uniqueness assertion locks the ID against accidental reuse from Phase 7 onward."

key-files:
  created: []
  modified:
    - scheduler/worker.py

key-decisions:
  - "Reserve lock ID 1019 (next-free above 1018) — do NOT reuse retired dead-code IDs 1010-1016 even though they are dormant, preserving an audit-clean ID history."
  - "Land the dict entry in Phase 5 (no factory, no add_job) — Phase 7 will add the _make_weekly_sweeper_job factory and CronTrigger registration when the sweeper itself is built; the entry alone enforces the OPS-02 contract today."

patterns-established:
  - "Lock-ID reservation pattern: a JOB_LOCK_IDS entry with no corresponding scheduler.add_job is a valid 'reservation-only' state — OPS-02 still asserts uniqueness, and the comment annotates the future-phase owner."

requirements-completed: []  # PLAN.md frontmatter requirements is [] — SWEEP-03 is a Phase 7 requirement; this plan is the ordering pre-requisite per PITFALLS.md.

# Metrics
duration: 1min
completed: 2026-05-18
---

# Phase 05 Plan 01: Reserve weekly_sweeper Advisory Lock ID 1019 Summary

**3-line addition to `scheduler/worker.py` JOB_LOCK_IDS reserving advisory lock ID 1019 for the future Phase 7 weekly_sweeper cron — no factory, no registration, just the contract.**

## Performance

- **Duration:** 1 min
- **Started:** 2026-05-18T21:33:59Z
- **Completed:** 2026-05-18T21:34:39Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments
- Reserved advisory lock ID 1019 under key `"weekly_sweeper"` in `JOB_LOCK_IDS` (now 10 entries / 10 unique values).
- OPS-02 startup uniqueness assertion at `worker.py:118` continues to pass (`uv run python -c "import worker"` exits 0).
- Established the lock-ID reservation contract: any Phase 7 code that holds advisory lock 1019 must look it up via `JOB_LOCK_IDS["weekly_sweeper"]`, not by hardcoded integer, so OPS-02 cannot be bypassed.

## Task Commits

Each task was committed atomically:

1. **Task 1: Reserve weekly_sweeper lock ID 1019 in JOB_LOCK_IDS** — `2a4c37a` (feat)

**Plan metadata:** _pending final commit after self-check_ (docs: complete 05-01 plan)

## Files Created/Modified
- `scheduler/worker.py` — Added `"weekly_sweeper": 1019` entry (plus 2 comment lines documenting v2.1 Phase 5 reservation and Phase 7 ownership) to the `JOB_LOCK_IDS` dict. Diff is exactly +3 lines; no other lines touched.

## Verification Commands Run

All commands run from `/Users/matthewnelson/seva-mining`.

1. **Primary automated check (from `<verify>`):**
   ```
   cd scheduler && uv run python -c "from worker import JOB_LOCK_IDS; \
     assert JOB_LOCK_IDS['weekly_sweeper'] == 1019, ...; \
     assert len(set(JOB_LOCK_IDS.values())) == len(JOB_LOCK_IDS), 'OPS-02 ...'; \
     print('OK: 1019 reserved, OPS-02 passes')"
   ```
   **Output:** `OK: 1019 reserved, OPS-02 passes`

2. **Acceptance criteria sweep (all 7 PASS):**
   - `grep -c '"weekly_sweeper": 1019' scheduler/worker.py` → `1`
   - `from worker import JOB_LOCK_IDS; print(JOB_LOCK_IDS['weekly_sweeper'])` → `1019`
   - `cd scheduler && uv run python -c "import worker"` → exit 0 (no AssertionError)
   - `grep -c "_make_weekly_sweeper_job" scheduler/worker.py` → `0` (factory NOT added — Phase 7 work)
   - `grep -c 'scheduler.add_job.*weekly_sweeper' scheduler/worker.py` → `0` (cron registration NOT added — Phase 7 work)
   - `grep -c '"midday_digest": 1005' scheduler/worker.py` → `1` (preserved)
   - `grep -c '"daily_summary_prune": 1018' scheduler/worker.py` → `1` (preserved)

3. **Diff shape:** `git diff scheduler/worker.py` shows exactly +3 lines, 0 lines removed, contained entirely within the JOB_LOCK_IDS dict literal — matches `<verification>` "diff shows exactly +3 lines: the comment + the new entry".

## Decisions Made

- **Why ID 1019 and not 1019/1020 (PITFALLS.md proposed range):** Worker.py's existing comment on lines 108-110 explicitly states that lock IDs 1017/1018 were "confirmed next-free by architecture-researcher direct grep" which "rejects PITFALLS.md proposal of 1020/1021". 1019 is the next monotonic integer after 1018, with 1010-1016 reserved as dead code (retired 6 sub-agents). This continues the post-Phase-4 numbering convention.
- **Why no factory / no `add_job`:** The plan's `<objective>` and acceptance criteria are explicit — Phase 7 builds the sweeper. Landing the dict entry alone (a) establishes the OPS-02 contract immediately and (b) prevents any future commit from claiming 1019 for a different job without tripping the import-time assertion.

## Deviations from Plan

None — plan executed exactly as written. The diff matches the `<action>` block byte-for-byte (entry + 2-line comment, inserted as the last item before the closing brace, preserving existing entry order).

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Lock ID 1019 is reserved and asserted unique on every worker startup. Phase 7's `_make_weekly_sweeper_job` factory can safely reference `JOB_LOCK_IDS["weekly_sweeper"]` without further coordination with Phase 5.
- No blockers for Phase 5 plans 02-05 — this plan touched a single file (`scheduler/worker.py`) that none of the remaining wave-1 plans modify, so the parallel executor wave can proceed independently.

## Self-Check: PASSED

- `[ -f scheduler/worker.py ]` → present, modified
- `git log --oneline | grep -q 2a4c37a` → commit `2a4c37a` present (feat(05-01): reserve weekly_sweeper advisory lock ID 1019)
- SUMMARY.md exists at `.planning/phases/05-foundation-tabs-db-backend-stubs/05-01-SUMMARY.md`

---
*Phase: 05-foundation-tabs-db-backend-stubs*
*Completed: 2026-05-18*
