---
phase: 04-prune-cron-operations-hardening
plan: "01"
subsystem: scheduler
tags: [apscheduler, postgres, cron, retention, telemetry, dead-code-retirement]

# Dependency graph
requires:
  - phase: 01-gold-news-card-web-feed
    provides: daily_summary cron + AgentRun telemetry pattern (Phase 1 Plan 05)
  - phase: 01-gold-news-card-web-feed
    provides: JOB_LOCK_IDS with daily_summary_prune=1018 pre-reserved (Phase 1 Plan 05)
provides:
  - run_daily_summary_prune() — 30-day retention DELETE on daily_summaries + agent_runs telemetry
  - daily_summary_prune cron registered at 03:00 PT under advisory lock 1018
  - CONTENT_CRON_AGENTS emptied — all 6 v1.0 sub-agent crons deregistered
  - OPS-04 retirement audit document (04-RETIREMENT-AUDIT.md)
  - parseRunNotes export enabling direct OPS-03 unit tests
affects: [v2.1-cleanup, future-scheduler-changes]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "_make_X_job(engine) lazy-import factory pattern (mirrors _make_daily_summary_job)"
    - "Dead-code-only retirement: empty list, keep source files + JOB_LOCK_IDS entries"
    - "OPS-03 graceful-null pattern: unrecognized notes keys → parseRunNotes returns null → caller suppresses subtitle"

key-files:
  created:
    - scheduler/agents/daily_summary_prune.py
    - scheduler/tests/agents/test_daily_summary_prune.py
    - .planning/phases/04-prune-cron-operations-hardening/04-RETIREMENT-AUDIT.md
  modified:
    - scheduler/worker.py
    - scheduler/tests/test_worker.py
    - frontend/src/pages/PerAgentQueuePage.tsx
    - frontend/src/pages/PerAgentQueuePage.test.tsx

key-decisions:
  - "CONTENT_CRON_AGENTS emptied in Task 4 (not Task 2) so Task 2 audit reflects accurate post-deregistration state"
  - "Sub-agent source files preserved on disk; JOB_LOCK_IDS 1010-1016 preserved as dead code — strip in v2.1+"
  - "parseRunNotes OPS-03 contract: returns null for daily_summary notes (no recognized keys) — v2.0 acceptance; pretty-render deferred to v2.1+"
  - "Task 4 execution order: before Task 2 (audit reflects true state); confirmed by user-approved scope expansion 2026-04-27"
  - "post_to_x.py + x_poster.py are STILL ACTIVE Phase B code — excluded from dead-code retirement"

patterns-established:
  - "Prune cron writes agent_runs telemetry with notes={deleted_count:N, cutoff_at:ISO8601}"
  - "reconcile_stale_runs sweeps daily_summary_prune orphans automatically (no new code needed)"

requirements-completed: [OPS-01, OPS-03, OPS-04]

# Metrics
duration: 11min
completed: 2026-05-06
---

# Phase 04 Plan 01: Prune Cron + Operations Hardening Summary

**30-day daily_summaries retention cron at 03:00 PT (lock 1018), 6 v1.0 sub-agent crons deregistered via CONTENT_CRON_AGENTS=[], and OPS-04 audit confirming retire-via-deregistration discipline upheld**

## Performance

- **Duration:** ~11 min
- **Started:** 2026-05-06T18:16:19Z
- **Completed:** 2026-05-06T18:26:54Z
- **Tasks:** 4 (3 planned + 1 user-approved expansion)
- **Files modified:** 7

## Accomplishments

- OPS-01: `run_daily_summary_prune()` deletes `daily_summaries` rows where `generated_at < now - 30d`; writes `agent_runs` row with `notes={"deleted_count":N,"cutoff_at":"ISO8601"}`; registered at `CronTrigger(hour=3, minute=0, timezone="America/Los_Angeles")` under advisory lock 1018
- Task 4 (user expansion): CONTENT_CRON_AGENTS emptied — all 6 v1.0 sub-agent crons deregistered; source files + JOB_LOCK_IDS 1010-1016 preserved as dead code; imports removed from worker.py
- OPS-04: `04-RETIREMENT-AUDIT.md` attests 14/14 source files present, zero v2.0 deletions, PASS
- OPS-03: `parseRunNotes` exported; 4 new tests lock in graceful-null contract for daily_summary and prune notes payloads; regression guard preserves sub-agent telemetry rendering

## Test Counts

- **New prune agent tests:** 5 (scheduler/tests/agents/test_daily_summary_prune.py)
- **New/updated worker tests:** 8 (test_worker.py — 3 new prune-specific + 2 new deregistration + 8 updated for empty CONTENT_CRON_AGENTS)
- **New frontend tests:** 4 (PerAgentQueuePage.test.tsx OPS-03 block)
- **Total scheduler tests:** 305 passed + 1 skipped
- **Total frontend tests:** 85 passed (13 files)

## Task Commits

Each task was committed atomically:

1. **Task 1: Build daily_summary_prune cron + register at 03:00 PT** - `bd7a585` (feat)
2. **Task 4: Deregister 6 v1.0 sub-agent crons** - `3a43ec0` (feat — user-approved expansion)
3. **Task 2: OPS-04 retirement audit** - `fd8879d` (docs)
4. **Task 3: OPS-03 parseRunNotes graceful fallback** - `ca8d50c` (feat)

## Files Created/Modified

- `scheduler/agents/daily_summary_prune.py` — run_daily_summary_prune() with 30d DELETE + agent_runs telemetry
- `scheduler/tests/agents/test_daily_summary_prune.py` — 5 TDD tests (deletion, idempotency, telemetry, EXEC-04 failure, callable)
- `scheduler/worker.py` — _make_daily_summary_prune_job factory + scheduler.add_job at 03:00 PT; CONTENT_CRON_AGENTS set to []; sub-agent imports removed
- `scheduler/tests/test_worker.py` — 8 tests added/updated; all sub-agent tests updated for empty CONTENT_CRON_AGENTS state
- `.planning/phases/04-prune-cron-operations-hardening/04-RETIREMENT-AUDIT.md` — OPS-04 attestation with real grep/ls evidence
- `frontend/src/pages/PerAgentQueuePage.tsx` — added `export` keyword to parseRunNotes (single-keyword change)
- `frontend/src/pages/PerAgentQueuePage.test.tsx` — 4 OPS-03 tests + import of parseRunNotes

## Decisions Made

- **Execution order:** Task 4 (deregistration) moved before Task 2 (audit) so the audit reflects the true post-deregistration state. User had recommended this order explicitly.
- **CONTENT_CRON_AGENTS = []:** Empty the list rather than removing the loop — the loop is a no-op and preserves the pattern for potential future re-population; this also avoids removing more code than necessary.
- **Imports removed from worker.py:** `from agents.content import (breaking_news, ...)` was removed since it became ruff F401 once CONTENT_CRON_AGENTS was empty. Comment added explaining why.
- **post_to_x.py STILL ACTIVE:** Phase B post-to-X is user-initiated approval code, not a v1.0 dead-code retirement target. Audit correctly marks it STILL ACTIVE.
- **OPS-03 v2.0 acceptance:** parseRunNotes returns null for daily_summary notes (no matched keys). Pretty-rendering daily_summary-specific labels (`candidates_gold`, `sections_completed`, etc.) deferred to v2.1+ as a UX enhancement.

## Deviations from Plan

**1. [Rule 1 - Bug] Unused imports after CONTENT_CRON_AGENTS emptied**
- **Found during:** Task 4 (deregistering sub-agent crons)
- **Issue:** Emptying CONTENT_CRON_AGENTS caused ruff F401 for all 6 `agents.content.*` imports that the list previously referenced
- **Fix:** Removed the `from agents.content import (...)` block; replaced with a comment explaining the removal
- **Files modified:** scheduler/worker.py
- **Committed in:** `3a43ec0` (Task 4 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — bug/ruff error caused directly by Task 4 changes)
**Impact on plan:** Required fix. No scope creep. Source files still exist on disk as dead code per plan.

## Issues Encountered

- SQLite/aiosqlite not installed in scheduler venv — prune tests initially used SQLite in-memory but switched to the AsyncMock factory pattern used by the existing daily_summary tests. Cleaner result: no extra test dependency, consistent with project test conventions.

## v2.0 Milestone Complete

Phase 4 closes v2.0. All requirements satisfied:
- OPS-01: daily_summary_prune cron at 03:00 PT
- OPS-03: parseRunNotes graceful fallback verified
- OPS-04: retirement audit PASS

## Post-deploy Metrics Estimate

After 30 days of deployment: ~2 daily_summary rows/day × 30d = ~60 rows in the window at steady state. Each prune run deletes the oldest row(s) as new ones push past the 30d cutoff. Expected `deleted_count` per run: 2 (one per 08:00 + 12:00 PT fire).

## v2.1+ Follow-up (from audit)

These files may be deleted once 30-day post-deploy stability is confirmed:
- `scheduler/agents/content/{breaking_news,threads,quotes,infographics,gold_media,gold_history}.py`
- `frontend/src/components/approval/` — all 6 components
- `scheduler/worker.py`: `_make_sub_agent_job`, `CONTENT_CRON_AGENTS` block, JOB_LOCK_IDS 1010-1016 and midday_digest=1005 entries

## Next Phase Readiness

v2.0 milestone complete. No blockers. System ready for:
- v2.1 cleanup (dead-code deletion after 30-day stability)
- Potential UX enhancement: pretty-render daily_summary notes in PerAgentQueuePage

## Self-Check: PASSED

- FOUND: scheduler/agents/daily_summary_prune.py
- FOUND: scheduler/tests/agents/test_daily_summary_prune.py
- FOUND: .planning/phases/04-prune-cron-operations-hardening/04-RETIREMENT-AUDIT.md
- FOUND: .planning/phases/04-prune-cron-operations-hardening/04-01-SUMMARY.md
- FOUND: bd7a585 (Task 1 commit)
- FOUND: 3a43ec0 (Task 4 commit)
- FOUND: fd8879d (Task 2 commit)
- FOUND: ca8d50c (Task 3 commit)

---
*Phase: 04-prune-cron-operations-hardening*
*Completed: 2026-05-06*
