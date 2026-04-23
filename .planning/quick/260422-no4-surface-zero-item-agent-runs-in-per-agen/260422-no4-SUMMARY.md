---
phase: 260422-no4
plan: 01
subsystem: frontend
tags: [per-agent-queue, zero-item-runs, telemetry, tdd]
key-files:
  modified:
    - frontend/src/pages/PerAgentQueuePage.tsx
    - frontend/src/pages/PerAgentQueuePage.test.tsx
decisions:
  - groupByRun now emits a group entry for every run in sorted, not only runs with matched items
  - items.length===0 && runs.length===0 keeps EmptyState; items=0 + runs>0 falls through to timeline
  - parseRunNotes helper (module-scope) handles all graceful degradation cases for notes telemetry
  - compliance_blocked suppressed when 0 per D-02 to keep subtitle short in the common case
metrics:
  duration: ~15 min
  completed: 2026-04-22
  tasks: 2
  files: 2
  tests_before: 52
  tests_after: 56
---

# Quick Task 260422-no4: Surface Zero-Item Agent Runs Summary

**One-liner:** `groupByRun` now emits every run (including 0-item) and renders "No content found" inline; `parseRunNotes` surfaces sub_gold_media telemetry as a muted subtitle under RunHeader with graceful degradation for null/malformed JSON.

## What Was Built

Every cron tick now appears in the per-agent queue timeline regardless of whether items were produced. Key changes to `PerAgentQueuePage.tsx`:

1. **`groupByRun` loop change** — the `if (groups.has(key))` guard was replaced with `groups.get(key) ?? { run, items: [] }` so every run in `sorted` gets an entry in the result.

2. **`items.length === 0` branch** — changed from `items.length === 0 ? <EmptyState />` to `items.length === 0 && runs.length === 0 ? <EmptyState />`. When runs exist but items don't, the code falls through to the `showRunGroups` path which calls `groupByRun([], runs)` — yielding one group per run, all empty.

3. **Zero-item group render** — inside the `showRunGroups` map, added `group.items.length === 0 ? <p>No content found</p> : group.items.map(...)`. RunHeader still renders above this row.

4. **`parseRunNotes` helper** — module-scope function that JSON.parses the `notes` string, extracts `x_candidates`, `llm_accepted`, `compliance_blocked` (only if >0), and `queued`; returns formatted ` · ` joined string or null for all failure modes (null, undefined, empty, malformed JSON, no known fields).

5. **Telemetry subtitle** — `{telemetry && <p className="text-xs text-muted-foreground -mt-2">{telemetry}</p>}` rendered directly after RunHeader inside each group wrapper.

## Tests Added (TDD Flow)

4 new tests in `PerAgentQueuePage.test.tsx`:

- **D-01**: Zero-item run renders "No content found" and RunHeader is still present.
- **D-03**: Two runs (runB newer/zero-item, runA older/has items) — "No content found" appears in DOM between the two RunHeaders (chronological order verified via `textContent.indexOf` positions).
- **D-02**: Notes telemetry 4 sub-cases — (a) all fields with blocked=0 suppressed, (b) blocked>0 shown, (c) null notes → no candidates/accepted text, (d) malformed JSON → no crash, no candidates text.
- **D-04 inverse**: items=0 AND runs>0 → timeline with "No content found"; EmptyState ("Queue is clear") absent.

## Validation Gates — All Passed

| Gate | Result |
|------|--------|
| `pnpm -C frontend lint` | Clean |
| `pnpm -C frontend exec tsc --noEmit` | Clean |
| `pnpm -C frontend test --run` | 56/56 (was 52, +4 new) |
| `pnpm -C frontend build` | Green |
| `grep video_clip\|VideoClipPreview` | 0 matches (grep-exit=1) |
| RunHeader props API unchanged | Verified — `{ displayTime, itemsQueued? }` untouched |
| ink's timestamp fallback preserved | Verified — `group.run ? group.run.started_at : group.items[0].created_at` |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test assertions used timezone-sensitive time strings**

- **Found during:** Task 1 RED verification
- **Issue:** Initial interleaving test used `'7:00 PM'` and `'5:00 PM'` string matching against `date-fns` formatted output, which is timezone-sensitive. Machine timezone is PDT (UTC-7) so `19:00Z` → `12:00 PM`, not `7:00 PM`. Test assertions would have been incorrect.
- **Fix:** Replaced time-string position checks with `textContent.indexOf('Pulled from agent run at')` double-occurrence check — first occurrence is runB (newer, zero-item), "No content found" between first and second occurrence, second occurrence is runA (older, has items).
- **Files modified:** `frontend/src/pages/PerAgentQueuePage.test.tsx`

**2. [Rule 1 - Bug] Notes sub-case (c) telemetry-absence assertion matched RunHeader timestamp**

- **Found during:** Task 2 GREEN verification
- **Issue:** `expect(screen.queryByText(/ · /)).not.toBeInTheDocument()` was matching the RunHeader's `"12:00 PM · Apr 22"` timestamp format (which uses the same ` · ` separator).
- **Fix:** Changed absence assertion to check for `queryByText(/candidates/)` and `queryByText(/accepted/)` — these are the actual telemetry field labels that would only appear from `parseRunNotes`, never in RunHeader.
- **Files modified:** `frontend/src/pages/PerAgentQueuePage.test.tsx`

## Commit

- `8080b4c`: `feat(frontend): surface zero-item agent runs in per-agent queue with 'no content found' (260422-no4)`

## Known Stubs

None — all data paths are wired to live API responses. `notes` telemetry is currently only populated by `sub_gold_media` (debug-260422-gmb); other agents return `null` which the UI handles silently per D-02.

## Self-Check: PASSED

- `frontend/src/pages/PerAgentQueuePage.tsx` — modified, verified
- `frontend/src/pages/PerAgentQueuePage.test.tsx` — modified, verified
- Commit `8080b4c` — verified in git log
