---
phase: 16-v3.1-audit-cleanup-bundle
plan: 01
subsystem: testing
tags: [eslint, typescript, react, react-hooks, react-refresh, vitest, frontend, cleanup]

# Dependency graph
requires:
  - phase: 11-audit-cleanup-bundle
    provides: "Single-plan-per-cleanup-item pattern — 16-01 mirrors 11-01 shape"
provides:
  - "Frontend lints clean: `cd frontend && npm run lint` exits 0 (was 15 errors)"
  - "Test-mock typing pattern: `as Partial<ReturnType<typeof hook>>` replaces `as any` in React Query hook mocks"
  - "Sibling-module pattern for non-component exports adjacent to page components (`perAgentQueueHelpers.ts`)"
  - "Justified per-line ESLint suppression pattern for intentional sync-state-from-props effects (DayCell)"
affects: [v3.1-milestone-audit-archive, future-frontend-test-authoring, future-page-component-helpers]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Type-narrowing in vitest mocks: `as Partial<ReturnType<typeof hook>>` (NOT `as any`) when mocking React Query hooks with partial shapes"
    - "Sibling-module extraction for non-component exports adjacent to page components — keeps Vite HMR fast-refresh working"
    - "react-hooks/set-state-in-effect: per-line suppression with multi-line rationale comment for intentional reconcile-from-props patterns"

key-files:
  created:
    - "frontend/src/pages/perAgentQueueHelpers.ts — parseRunNotes() extracted from PerAgentQueuePage.tsx to satisfy react-refresh/only-export-components"
  modified:
    - "frontend/src/pages/__tests__/SummaryFeedPage.test.tsx — removed unbacked react/display-name disable + 5× `as any` → `as Partial<UseSummariesResult>`"
    - "frontend/src/pages/PerAgentQueuePage.tsx — removed inline parseRunNotes export (moved to sibling); now imports from ./perAgentQueueHelpers"
    - "frontend/src/pages/PerAgentQueuePage.test.tsx — import parseRunNotes from ./perAgentQueueHelpers"
    - "frontend/src/api/__tests__/summaries.test.tsx — removed unbacked react/display-name disable"
    - "frontend/src/components/calendar/DayCell.tsx — per-line suppression on setCurrent inside useEffect with rationale (v2.1 Phase 6 sync-from-props reconciliation)"
    - "frontend/src/__tests__/weeklySweeps.test.tsx — removed unbacked react/display-name disable + 5× `as any` → `as Partial<UseWeeklySweepsResult>` (Rule 3 deviation — plan's audit-evidence mislabeled this file as PerAgentQueuePage.tsx)"

key-decisions:
  - "Used `as Partial<ReturnType<typeof hook>>` instead of populating full ~30-field React Query result objects — narrower than `any`, doesn't drift when @tanstack/react-query updates its result shape"
  - "Option (a) for react/display-name: removed unbacked disable directives (eslint-plugin-react NOT installed) — NOT option (b) of installing the plugin, which would scope-creep and add a heavy dep for unused rules"
  - "Option (a) for react-refresh/only-export-components: moved parseRunNotes to sibling module — cleaner than per-line suppression because parseRunNotes is a non-trivial value export with its own unit tests"
  - "Option (a) for react-hooks/set-state-in-effect: per-line suppression with inline rationale — refactoring to key-on-id remount pattern would lose in-flight textarea edits during background refetch (v2.1 Phase 6 D-01 contract)"

patterns-established:
  - "React Query hook mock typing: `as Partial<ReturnType<typeof hook>>` — safer than `as any`, drift-free across query library upgrades"
  - "Page module purity: non-component exports live in `*Helpers.ts` siblings, NOT in the page module — preserves Vite HMR"
  - "Intentional sync-from-props effects: per-line `// eslint-disable-next-line react-hooks/set-state-in-effect` with multi-line preceding-comment rationale documenting why the pattern is correct"

requirements-completed: [CLEAN-01]

# Metrics
duration: 8min
completed: 2026-05-21
---

# Phase 16 Plan 01: CLEAN-01 Frontend ESLint Cleanup Summary

**Frontend lint exits 0 (was 15 errors across 4 rule classes: 10× no-explicit-any, 2× react/display-name unbacked-directive, 1× react-hooks/set-state-in-effect, 1× react-refresh/only-export-components) — D-10 regression baseline preserved at 181/181 tests, TypeScript clean.**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-05-21T02:42:00Z (approx — local clock for this executor)
- **Completed:** 2026-05-21T02:47:00Z
- **Tasks:** 1/1 (single CLEAN-01 task per plan shape, mirroring 11-01)
- **Files modified:** 6 (+ 1 created: `perAgentQueueHelpers.ts`)

## Accomplishments

- **Frontend lint clean**: `cd frontend && npm run lint` exits 0 (was: 15 problems / 15 errors / 0 warnings)
- **D-10 regression baseline preserved**: `cd frontend && npm test --silent` reports 181/181 passing across 31 test files (unchanged from baseline)
- **TypeScript still clean**: `cd frontend && npx tsc --noEmit` exits 0 — the type-narrowing fixes for `no-explicit-any` introduced zero TS errors
- **CLEAN-01 acceptance gate satisfied** (REQUIREMENTS.md line 54 — authoritative drift-tolerant tool-exit-code gate)

## Per-Rule-Class Fix Patterns Applied

| Rule | Count | File(s) | Fix pattern |
|------|-------|---------|-------------|
| `@typescript-eslint/no-explicit-any` | 10 | `SummaryFeedPage.test.tsx` (5), `weeklySweeps.test.tsx` (5) | Replaced `as any` with `as Partial<ReturnType<typeof hook>>`. Extracted local `type UseXxxResult = ReturnType<typeof hook>` alias for readability. |
| `react/display-name` (unbacked) | 3 | `summaries.test.tsx`, `SummaryFeedPage.test.tsx`, `weeklySweeps.test.tsx` | Removed the `// eslint-disable-next-line react/display-name` directives — `eslint-plugin-react` is NOT in devDeps, so the directives themselves were the violation (modern flat configs error on unknown rule names in disable comments). |
| `react-hooks/set-state-in-effect` | 1 | `DayCell.tsx:54` | Per-line `// eslint-disable-next-line react-hooks/set-state-in-effect` with multi-line preceding rationale: this is the v2.1 Phase 6 sync-from-props reconciliation pattern; refactoring to key+remount would lose in-flight textarea edits during background refetch. |
| `react-refresh/only-export-components` | 1 | `PerAgentQueuePage.tsx:59` | Moved `parseRunNotes()` to new sibling module `frontend/src/pages/perAgentQueueHelpers.ts`. Page module now exports only React components → Vite HMR fast-refresh works. Test import updated. |

Note: the plan reported only 2× `react/display-name` (in `summaries.test.tsx` + `SummaryFeedPage.test.tsx`). Lint actually showed 3 instances (the third in `weeklySweeps.test.tsx`) — see Deviations.

## Task Commits

1. **Task 1: CLEAN-01 — Frontend ESLint cleanup** — `31ee70b` (fix)

**Plan metadata:** (committed in final step alongside SUMMARY + STATE updates)

## Files Created/Modified

**Created:**
- `frontend/src/pages/perAgentQueueHelpers.ts` — Module housing `parseRunNotes()` extracted from `PerAgentQueuePage.tsx`. Lets the page component file export only React components (Vite HMR contract).

**Modified:**
- `frontend/src/pages/PerAgentQueuePage.tsx` — Dropped inline `parseRunNotes` export and JSDoc; added `import { parseRunNotes } from './perAgentQueueHelpers'`. Behavior unchanged.
- `frontend/src/pages/PerAgentQueuePage.test.tsx` — Updated `parseRunNotes` import path to the new sibling module. All 9 tests in this file remain green.
- `frontend/src/pages/__tests__/SummaryFeedPage.test.tsx` — Removed unbacked `react/display-name` disable; extracted `type UseSummariesResult = ReturnType<typeof summariesApi.useSummaries>` alias; replaced 5× `as any` with `as Partial<UseSummariesResult>` and updated `mockUseSummaries()` parameter type to `Partial<UseSummariesResult>`.
- `frontend/src/__tests__/weeklySweeps.test.tsx` — Same shape as SummaryFeedPage.test.tsx: extracted `type UseWeeklySweepsResult`, removed unbacked `react/display-name` disable, replaced 5× `as any` with `as Partial<UseWeeklySweepsResult>`.
- `frontend/src/api/__tests__/summaries.test.tsx` — Removed unbacked `react/display-name` disable. No other changes.
- `frontend/src/components/calendar/DayCell.tsx` — Added per-line `// eslint-disable-next-line react-hooks/set-state-in-effect` on the `setCurrent(item?.body ?? '')` call inside `useEffect`, with a 4-line preceding rationale comment documenting the v2.1 Phase 6 sync-from-props reconciliation pattern.

ESLint config NOT modified — option (a) for `react/display-name` is "remove the unbacked DIRECTIVES from source files" (because there is no rule entry IN the config to remove; the directives themselves were the unbacked references). The config was already clean.

## Decisions Made

- **Test-mock typing: `as Partial<ReturnType<typeof hook>>` over `as any`** — drift-free across React Query upgrades; preserves narrow type-checking on the partial mock shape; doesn't require maintaining a full ~30-field result-shape mock.
- **Sibling-module extraction for `parseRunNotes` (Step 5 option a)** — cleaner than per-line suppression because `parseRunNotes` is a non-trivial 18-line value export with 5 unit tests in `PerAgentQueuePage.test.tsx`. Extracting to `perAgentQueueHelpers.ts` makes future helper additions natural and keeps the page module pure.
- **Per-line suppression for DayCell sync-from-props effect (Step 4 option a)** — refactoring to key-on-id+remount (option b) is a 30-50 line change that would lose the user's in-flight textarea edits during a background refetch (violates v2.1 Phase 6 D-01 contract: "the day cell IS a textarea"). The synchronous setState IS the intended pattern; the rule is wrong for this specific case.
- **Removed unbacked `react/display-name` directives over installing eslint-plugin-react (Step 3 option a)** — installing the plugin would scope-creep beyond CLEAN-01, add ~3MB of devDeps, and require config wiring for rules that aren't relevant to this codebase (no class components, no `forwardRef` patterns since React 19).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Plan audit-evidence file mapping error: 5× no-explicit-any errors live in `weeklySweeps.test.tsx`, not `PerAgentQueuePage.tsx`**

- **Found during:** Task 1 (after Step 2 attempted to locate the `any` annotations in `PerAgentQueuePage.tsx`)
- **Issue:** Plan's `<audit_evidence>` block listed `PerAgentQueuePage.tsx` lines 52/66/84/96/106 as carrying 5× `Unexpected any` errors. After Steps 2-3 fixed 7 of the 15 errors, the remaining lint output revealed the actual file was `src/__tests__/weeklySweeps.test.tsx` (same line numbers, same column 10, same rule class — an audit-evidence copy-paste error in plan authoring). The plan's `files_modified` frontmatter did not list this file.
- **Fix:** Applied the same test-mock typing pattern (extract `type UseWeeklySweepsResult` alias, replace 5× `as any` with `as Partial<UseWeeklySweepsResult>`, remove unbacked `react/display-name` disable). Same test-file scope, same 4 rule classes already covered by CLEAN-01; fully consistent with the plan's stated intent.
- **Justification:** Plan's authoritative gate is `cd frontend && npm run lint exits 0`, and plan explicitly says "trust the TOOL exit code over any count" and "REQUIREMENTS.md numeric quote". Leaving `weeklySweeps.test.tsx` unfixed would have left lint with 6 errors and failed the gate. Same rule classes, same test-file scope → not scope creep, just following the rules to the actual offending file.
- **Files modified:** `frontend/src/__tests__/weeklySweeps.test.tsx`
- **Verification:** `npm run lint` exits 0; all 5 tests in `WeeklyViralSweeperPage` + 4 tests in `SweeperCard` describe blocks remain green (181/181 total).
- **Committed in:** `31ee70b` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 3 blocking — plan audit-evidence file-mapping correction)
**Impact on plan:** No scope creep (same rule classes, same test-file category, same fix patterns). Plan intent fully honored; closing CLEAN-01 required honoring the lint-tool-exit-code gate over the literal plan file list. Plan's own anti-shallow principle ("trust the TOOL exit code") explicitly authorizes this.

## Issues Encountered

- None. The auto-fix (`npx eslint --fix`) made 0 changes (all 15 errors are semantic, not formatting — as the plan correctly anticipated).

## Known Stubs

None. All fixes are real type-narrowing, real module extraction, real justified suppressions, and real directive removals — no placeholders, no `TODO`/`FIXME`/`coming soon` strings introduced, no `=[]`/`={}`/`=null` flow-to-UI patterns. The one suppression in `DayCell.tsx` is documented as intentional with a 4-line rationale and references the v2.1 Phase 6 D-01 contract.

## Next Phase Readiness

- **CLEAN-01 ready to mark Complete** in `REQUIREMENTS.md` Traceability table — acceptance gate satisfied.
- **v3.1 milestone audit-archive unblock progress:** 1 of 5 audit cleanup items closed by 16-01. Plans 16-02/03/04/05 land in parallel within Wave 1 — orchestrator aggregates final state.
- **No follow-up debt introduced.** The pattern for future React Query hook test-mocks is now established (`as Partial<ReturnType<typeof hook>>` — see commit `31ee70b` for the canonical example).

## Self-Check: PASSED

- `frontend/src/pages/perAgentQueueHelpers.ts` — FOUND
- `frontend/src/pages/__tests__/SummaryFeedPage.test.tsx` — FOUND (modified)
- `frontend/src/pages/PerAgentQueuePage.tsx` — FOUND (modified)
- `frontend/src/pages/PerAgentQueuePage.test.tsx` — FOUND (modified)
- `frontend/src/api/__tests__/summaries.test.tsx` — FOUND (modified)
- `frontend/src/components/calendar/DayCell.tsx` — FOUND (modified)
- `frontend/src/__tests__/weeklySweeps.test.tsx` — FOUND (modified)
- Commit `31ee70b` — FOUND in `git log --oneline -3`
- `cd frontend && npm run lint` exit code — 0 (verified)
- `cd frontend && npx tsc --noEmit` exit code — 0 (verified)
- `cd frontend && npm test --silent` — 181/181 GREEN (verified)

---
*Phase: 16-v3.1-audit-cleanup-bundle*
*Completed: 2026-05-21*
