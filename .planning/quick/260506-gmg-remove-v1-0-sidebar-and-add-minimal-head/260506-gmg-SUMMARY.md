---
phase: quick-260506-gmg
plan: "01"
type: quick-task
subsystem: frontend/layout
tags: [ui, layout, header, sidebar-retirement, v2.0-polish]
dependency_graph:
  requires: []
  provides: [AppHeader, AppShell-v2]
  affects: [SummaryFeedPage, DigestPage, SettingsPage]
tech_stack:
  added: []
  patterns: [React functional component, Zustand selector, react-router useNavigate]
key_files:
  created:
    - frontend/src/components/layout/AppHeader.tsx
    - frontend/src/components/layout/__tests__/AppHeader.test.tsx
  modified:
    - frontend/src/components/layout/AppShell.tsx
    - frontend/src/pages/SummaryFeedPage.tsx
decisions:
  - Used plain <button> (not shadcn Button) for Log out — matches "subtle link" locked spec
  - sticky top-0 z-10 on header so it stays visible when scrolling long feed
  - Sidebar.tsx left on disk as dead code per v2.0 retirement discipline
metrics:
  duration: "~10 minutes"
  completed: "2026-05-06"
  tasks_completed: 1
  files_changed: 4
---

# Quick Task 260506-gmg: Remove v1.0 Sidebar and Add Minimal Header — Summary

**One-liner:** Replaced 220px v1.0 Sidebar chrome with a sticky amber-branded top header (logo + "Log out") across all authenticated routes and re-widened the feed column from 672px to the locked 720px spec.

## Files Changed

| File | Change | Reason |
|------|--------|--------|
| `frontend/src/components/layout/AppHeader.tsx` | Created | New minimal header: amber "S" logo + "Seva Mining" wordmark left, subtle "Log out" button right |
| `frontend/src/components/layout/__tests__/AppHeader.test.tsx` | Created | 4 unit tests: wordmark, logo mark, logout button renders, logout click behavior |
| `frontend/src/components/layout/AppShell.tsx` | Edited | Removed Sidebar import, added AppHeader, dropped min-w-[1280px], changed to flex-col |
| `frontend/src/pages/SummaryFeedPage.tsx` | Edited | max-w-2xl → max-w-[720px] in all 4 return blocks (loading / error / empty / success) |

## Files Left Intentionally Unchanged

| File | Reason |
|------|--------|
| `frontend/src/components/layout/Sidebar.tsx` | Left as dead code per v2.0 retirement discipline — mirrors quick-260423-k8n (sub_long_form) and quick-260420-sn9 (Twitter Agent) precedent |
| `frontend/src/pages/DigestPage.tsx` | Has its own `<h1>Daily Digest</h1>` page-title header — new global AppHeader sits above it with no conflict |
| `frontend/src/pages/SettingsPage.tsx` | Has its own `<h1>Settings</h1>` page-title header — same, no conflict |
| `frontend/src/pages/__tests__/SummaryFeedPage.test.tsx` | Existing 5 tests don't assert on layout chrome — all pass unchanged |

## Verification Results

- npm test (AppHeader suite): 4/4 passing
- npm test (SummaryFeedPage suite): 5/5 passing — all pre-existing tests green
- npm test (combined): 9/9 passing
- npm run build: TypeScript clean, Vite build succeeded (chunk size warning pre-existing, unrelated)
- git status: Sidebar.tsx does NOT appear — left intact on disk

## Task Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1 | 3a8bfbb | feat(quick-260506-gmg-01): retire Sidebar, add AppHeader, widen feed |

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.

## Self-Check: PASSED

- `frontend/src/components/layout/AppHeader.tsx` — FOUND
- `frontend/src/components/layout/__tests__/AppHeader.test.tsx` — FOUND
- `frontend/src/components/layout/AppShell.tsx` — verified no Sidebar import, has AppHeader, has flex-col, no min-w-[1280px]
- `frontend/src/pages/SummaryFeedPage.tsx` — all 4 return blocks use max-w-[720px]
- commit 3a8bfbb — FOUND
- Human visual verification (Task 2): PENDING
