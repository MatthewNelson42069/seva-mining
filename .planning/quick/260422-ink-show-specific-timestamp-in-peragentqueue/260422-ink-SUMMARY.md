---
phase: quick-260422-ink
plan: 01
subsystem: frontend
tags: [frontend, ui, per-agent-queue, run-header]
requires: []
provides:
  - "PerAgentQueuePage with widened (30-day) agent_runs fetch window"
  - "RunHeader fallback now renders specific timestamp from newest bucket item"
affects:
  - "frontend/src/pages/PerAgentQueuePage.tsx"
tech-stack:
  added: []
  patterns:
    - "Caller-resolved displayTime (Approach A): RunHeader receives pre-formatted string; no conditional branch inside component"
key-files:
  created: []
  modified:
    - "frontend/src/pages/PerAgentQueuePage.tsx"
decisions:
  - "Chose Approach A (caller resolves displayTime) over Approach B (fallbackTime prop). Approach A removes all conditional rendering from RunHeader — the component has zero knowledge of whether it's rendering a matched run or a no-run fallback. Cleaner than branching on a null prop inside the component."
metrics:
  duration: "~5 minutes (wall clock, single file change)"
  completed: "2026-04-22"
requirements:
  - INK-01
  - INK-02
---

# Quick Task 260422-ink: Show Specific Timestamp in PerAgentQueue RunHeader Fallback — Summary

One-liner: Replaced bare "(earlier)" RunHeader fallback with a specific `{h:mm a} · {MMM d}` timestamp derived from the newest item's `created_at`, and widened the `getAgentRuns` fetch window from 7 to 30 days.

## What Changed

Single file modified: `frontend/src/pages/PerAgentQueuePage.tsx`

1. **Widened fetch window (L107):** `getAgentRuns(tab.agentName, 7)` → `getAgentRuns(tab.agentName, 30)`. Addresses INK-01. Covers pre-eoe-split historical drafts (some Threads drafts from before 2026-04-21) so they match real runs instead of falling into the no-run bucket.

2. **RunHeader signature changed (L56-76):** Props went from `{ run: AgentRunResponse | null }` to `{ displayTime: string; itemsQueued?: number | null }`. The component no longer branches on `run` — it simply renders `Pulled from agent run at {displayTime}` unconditionally. The "(earlier)" literal and the ternary are both gone.

3. **Call site resolves the timestamp (L141-154):** For each group returned by `groupByRun`, the caller now computes:
   ```ts
   const sourceDate = group.run
     ? new Date(group.run.started_at)
     : new Date(group.items[0].created_at)   // newest item in no-run bucket
   const displayTime = `${format(sourceDate, 'h:mm a')} · ${format(sourceDate, 'MMM d')}`
   ```
   and passes `displayTime` + `group.run?.items_queued` into `RunHeader`. Addresses INK-02.

Net diff: +25 insertions, -13 deletions.

## Chosen Approach

**Approach A** (caller resolves `displayTime`). Preferred per the plan's guidance: RunHeader becomes a pure presentational component with no conditional logic — the timestamp-resolution concern stays entirely in the mapping loop where the group bucket (matched run vs. no-run) is already known.

Approach B (optional `fallbackTime` prop + keep `run` prop + branch inside component) would have kept branching logic in the component itself and required the caller to compute a fallback string anyway. A is strictly simpler.

## Tests

No new test was added. The plan marked test coverage as "RECOMMENDED, not strictly required," and the three grep gates plus full lint/tsc/test/build suite are sufficient to prove the fix:

- Gate: `(earlier)` must not appear anywhere in the file → 0 matches confirmed.
- Gate: `Pulled from agent run at` must appear unconditionally → 1 match (not inside a ternary branching on `run`).
- The existing test suite (5 `PerAgentQueuePage` tests) exercises the `showRunGroups === false` branch (runs mock returns `[]`), which does not hit `RunHeader`. These tests still pass, confirming no regression in the empty-runs path.

## Verification Gate Results (all 7 green)

| # | Gate | Result |
|---|------|--------|
| 1 | `grep -c "getAgentRuns(tab.agentName, 30)" frontend/src/pages/PerAgentQueuePage.tsx` | `1` (≥ 1 required) ✓ |
| 2 | `grep "(earlier)" frontend/src/pages/PerAgentQueuePage.tsx` | no matches (exit 1) ✓ |
| 3 | `grep -c "Pulled from agent run at" frontend/src/pages/PerAgentQueuePage.tsx` | `1` (≥ 1 required) ✓ |
| 4 | `pnpm -C frontend lint` | clean (no output, exit 0) ✓ |
| 5 | `pnpm -C frontend exec tsc --noEmit` | clean (no output, exit 0) ✓ |
| 6 | `pnpm -C frontend test --run` | `Test Files 8 passed (8) / Tests 52 passed (52)` ✓ |
| 7 | `pnpm -C frontend build` | `built in 199ms`, 2322 modules transformed ✓ |

## Deviations from Plan

None — plan executed exactly as written. No auto-fix rules triggered. No architectural decisions required.

One operational note: the isolated worktree's `frontend/node_modules` was absent (fresh worktree). Symlinked from the main repo's `frontend/node_modules` to run the pnpm-based gates. This is outside the git tree and has no effect on the commit.

## Commit

- **SHA:** `b629916` (full: `b629916b10a5d29e9e1b8326d3f56740b7bc8044`)
- **Branch:** `worktree-agent-a62ab261` (orchestrator will FF-merge into `quick/260422-ink-run-header-fallback-time` from this worktree)
- **Message:** `fix(frontend): show specific timestamp in PerAgentQueuePage RunHeader fallback (quick-260422-ink)`
- **Files changed:** 1 (`frontend/src/pages/PerAgentQueuePage.tsx`), +25 / -13.

## Self-Check: PASSED

- Created files exist:
  - `.planning/quick/260422-ink-show-specific-timestamp-in-peragentqueue/260422-ink-SUMMARY.md` — this file.
- Commit exists: `b629916` confirmed on branch `worktree-agent-a62ab261`.
- All 7 verification gates passed (see table above).
