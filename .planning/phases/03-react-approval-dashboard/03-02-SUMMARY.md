---
phase: 03-react-approval-dashboard
plan: 02
subsystem: ui
tags: [react, zustand, tanstack-query, shadcn, vitest, tailwind]

# Dependency graph
requires:
  - phase: 03-01
    provides: API types, queue/approve/reject client functions, shadcn components (Badge, Button, Tabs, RadioGroup, Textarea), MSW handlers, Vitest setup

provides:
  - Zustand AppStore (useAppStore) combining QueueUiSlice and AuthSlice
  - useQueue hook: TanStack Query infinite query per platform with cursor pagination
  - useApprove hook: mutation with clipboard copy, toast, and query invalidation
  - useReject hook: mutation with toast and query invalidation
  - ApprovalCard component: full approve/edit/reject workflow
  - DraftTabBar, InlineEditor, RejectPanel sub-components
  - PlatformBadge and ScoreBadge shared components
  - 7 passing unit tests covering all DASH-03 requirements

affects:
  - 03-03 (QueuePage will consume ApprovalCard and hooks)
  - 03-04 (LoginPage will use authSlice setToken/clearToken)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Zustand slice pattern: separate createXxxSlice functions combined in stores/index.ts
    - useShallow from zustand/react/shallow for multi-field store subscriptions
    - TanStack Query infinite query with initialPageParam and getNextPageParam
    - 5-second undo window: setTimeout stored in Zustand pendingTimeouts Map, clearTimeout on cancelFadeOut
    - CSS opacity transition for card fade-out via fadingCardIds Set

key-files:
  created:
    - frontend/src/stores/slices/queueUiSlice.ts
    - frontend/src/stores/slices/authSlice.ts
    - frontend/src/stores/index.ts
    - frontend/src/hooks/useQueue.ts
    - frontend/src/hooks/useApprove.ts
    - frontend/src/hooks/useReject.ts
    - frontend/src/components/approval/ApprovalCard.tsx
    - frontend/src/components/approval/DraftTabBar.tsx
    - frontend/src/components/approval/InlineEditor.tsx
    - frontend/src/components/approval/RejectPanel.tsx
    - frontend/src/components/approval/ApprovalCard.test.tsx
    - frontend/src/components/shared/PlatformBadge.tsx
    - frontend/src/components/shared/ScoreBadge.tsx
  modified:
    - frontend/src/stores/slices/authSlice.ts (localStorage guard for test env)

key-decisions:
  - "lucide-react 1.7 does not export Twitter or Instagram icons — used MessageSquare/Camera as substitutes"
  - "Clipboard copy fires immediately on Approve click (before 5s undo timer), not deferred to mutation success"
  - "Zustand store reset in beforeEach via useAppStore.setState to prevent state leaking between tests"
  - "onEditChange callback added to InlineEditor so parent card can track edit value for Edit+Approve flow"

patterns-established:
  - "Slice pattern: createXxxSlice(set) returns plain object, combined via spread in create<AppStore>()()"
  - "localStorage access guarded with try/catch for SSR/test environment safety"
  - "Zustand state reset in test beforeEach to prevent cross-test contamination"

requirements-completed: [DASH-02, DASH-03, DASH-04, DASH-05, DASH-06, DASH-07]

# Metrics
duration: 7min
completed: 2026-03-31
---

# Phase 3 Plan 02: Zustand Store, Query Hooks, and ApprovalCard Summary

**Zustand UI store + TanStack Query hooks + ApprovalCard with draft tabs, inline editor, reject panel, 5-second undo window, and 7 passing tests**

## Performance

- **Duration:** 7 min
- **Started:** 2026-03-31T21:10:59Z
- **Completed:** 2026-03-31T21:17:44Z
- **Tasks:** 2
- **Files modified:** 13

## Accomplishments

- Zustand AppStore combines QueueUiSlice (edit mode, rejection panel, draft tabs, fade-out with undo) and AuthSlice (token persisted to localStorage) into a single typed store exported as `useAppStore`
- Three TanStack Query hooks: `useQueue` infinite query per platform, `useApprove` mutation with clipboard copy + toast, `useReject` mutation with toast
- ApprovalCard component rendering all DASH-03 fields: platform badge, source account + follower count, score, source text, draft alternatives as tabs, inline edit mode, rationale toggle ("Why this post?"), approve/reject actions, card fade-out with 5-second undo window
- 7 unit tests pass covering rendering, rationale toggle, source URL attributes, reject panel categories, inline edit mode, and follower formatting

## Task Commits

1. **Task 1: Create Zustand store and TanStack Query hooks** - `51823db` (feat)
2. **Task 2: Build ApprovalCard with sub-components and tests** - `ddd938d` (feat)

## Files Created/Modified

- `frontend/src/stores/slices/queueUiSlice.ts` - UI state: editingCardId, rejectionPanelCardId, activeDraftTab, fadingCardIds, pendingTimeouts with cancelFadeOut/clearAllPending
- `frontend/src/stores/slices/authSlice.ts` - Auth state synced to localStorage with try/catch guard
- `frontend/src/stores/index.ts` - Combined AppStore via useAppStore
- `frontend/src/hooks/useQueue.ts` - Infinite query hook per platform, always status='pending'
- `frontend/src/hooks/useApprove.ts` - Approve mutation with navigator.clipboard.writeText and invalidateQueries
- `frontend/src/hooks/useReject.ts` - Reject mutation with toast and invalidateQueries
- `frontend/src/components/approval/ApprovalCard.tsx` - Core approval card component (175 lines)
- `frontend/src/components/approval/DraftTabBar.tsx` - shadcn Tabs for draft alternative switching
- `frontend/src/components/approval/InlineEditor.tsx` - Click-to-edit with Textarea + onEditChange callback
- `frontend/src/components/approval/RejectPanel.tsx` - shadcn RadioGroup with 5 rejection categories + notes Textarea
- `frontend/src/components/approval/ApprovalCard.test.tsx` - 7 unit tests using Testing Library + Vitest
- `frontend/src/components/shared/PlatformBadge.tsx` - Platform badge for twitter/instagram/content
- `frontend/src/components/shared/ScoreBadge.tsx` - Score displayed as N.N/10

## Decisions Made

- lucide-react 1.7 does not export Twitter or Instagram social icons — used `MessageSquare` for Twitter and `Camera` for Instagram as visual substitutes. These are generic icons that convey the platform type adequately for an internal tool.
- Clipboard copy fires immediately on Approve click rather than being deferred to after the 5-second undo window, so the user has the text immediately even if they undo the server action.
- The `onEditChange` callback was added to `InlineEditor` so the parent `ApprovalCard` can track the current edited value via `editedTextRef` for the Edit+Approve button flow.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Guard localStorage access for test environment**
- **Found during:** Task 2 (ApprovalCard test run)
- **Issue:** `authSlice.ts` called `localStorage.getItem()` at module evaluation time. In the Vitest/jsdom test environment with `--localstorage-file` warning, this threw `TypeError: localStorage.getItem is not a function`
- **Fix:** Wrapped localStorage access in a `getStoredToken()` helper with try/catch returning null on error
- **Files modified:** `frontend/src/stores/slices/authSlice.ts`
- **Verification:** All 7 tests now pass
- **Committed in:** `ddd938d` (Task 2 commit)

**2. [Rule 1 - Bug] Icon substitution for unavailable lucide social icons**
- **Found during:** Task 2 (initial test run)
- **Issue:** `PlatformBadge` imported `Twitter` and `Instagram` from `lucide-react` 1.7 — these icons don't exist in this version, causing `Element type is invalid: got undefined` error
- **Fix:** Replaced with `MessageSquare` (Twitter) and `Camera` (Instagram) from the same library
- **Files modified:** `frontend/src/components/shared/PlatformBadge.tsx`
- **Verification:** All 7 tests pass, TypeScript clean
- **Committed in:** `ddd938d` (Task 2 commit)

**3. [Rule 2 - Missing Critical] Zustand store reset in test beforeEach**
- **Found during:** Task 2 (test for inline edit mode failed due to reject panel state from prior test)
- **Issue:** Zustand store is a module-level singleton — state from one test leaked into the next, causing the rejection panel (opened in test 5) to remain open during test 6, creating two textareas in the DOM
- **Fix:** Added `useAppStore.setState({...})` in `beforeEach` to reset all UI state fields to their initial values
- **Files modified:** `frontend/src/components/approval/ApprovalCard.test.tsx`
- **Verification:** All 7 tests pass in correct isolation
- **Committed in:** `ddd938d` (Task 2 commit)

---

**Total deviations:** 3 auto-fixed (2 Rule 1 bugs, 1 Rule 2 missing critical)
**Impact on plan:** All fixes necessary for correctness and test reliability. No scope creep.

## Issues Encountered

- npm install was required first as node_modules was absent from the worktree. Installed 576 packages before running TypeScript or Vitest.

## Known Stubs

None — all components receive real data from props, store, and hooks. No hardcoded empty values flow to rendering.

## Next Phase Readiness

- `useAppStore` ready for QueuePage to consume alongside `useQueue` infinite scroll
- `ApprovalCard` ready to be placed in QueuePage's list rendering
- `authSlice` ready for LoginPage to call `setToken` on successful auth
- All TypeScript clean, all tests passing

---
*Phase: 03-react-approval-dashboard*
*Completed: 2026-03-31*
