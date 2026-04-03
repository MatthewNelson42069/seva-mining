---
phase: "08-dashboard-views-and-digest"
plan: "03"
subsystem: "frontend"
tags: ["react", "content-review", "tanstack-query", "msw", "vitest", "infographic"]
dependency_graph:
  requires: ["08-01"]
  provides: ["ContentPage", "InfographicPreview"]
  affects: ["frontend/src/pages/ContentPage.tsx", "frontend/src/components/content/InfographicPreview.tsx"]
tech_stack:
  added: ["frontend/src/api/content.ts"]
  patterns: ["vi.mock for API modules in page-level tests", "format_type branching for clipboard text", "TanStack Query with 404-to-null pattern"]
key_files:
  created:
    - "frontend/src/pages/ContentPage.tsx"
    - "frontend/src/pages/ContentPage.test.tsx"
    - "frontend/src/components/content/InfographicPreview.tsx"
    - "frontend/src/components/content/InfographicPreview.test.tsx"
    - "frontend/src/api/content.ts"
  modified:
    - "frontend/src/mocks/handlers.ts"
    - "frontend/package.json"
decisions:
  - "Use vi.mock('@/api/content') and vi.mock('@/api/queue') for ContentPage tests — relative fetch URLs fail in jsdom/Node.js without a base URL, and MSW node interceptors cannot intercept them. Module mocking is cleaner and tests the component logic directly."
  - "Add test script to package.json — it was missing despite vitest being installed"
metrics:
  duration: "~15 minutes"
  completed_date: "2026-04-03"
  tasks_completed: 2
  files_created_or_modified: 7
---

# Phase 08 Plan 03: Content Review Page Summary

ContentPage fully replaces the stub with format-specific rendering (thread/long_form/infographic), source links, approve flow with correct clipboard text per format_type, and all empty/error states. InfographicPreview component renders stat cards layout per CONTEXT.md decision.

## Tasks Completed

| # | Task | Commit | Status |
|---|------|--------|--------|
| 1 | Build InfographicPreview component | 99b6f57 | Done |
| 2 | Build ContentPage with branch logic and approve flow | b7d236b | Done |

## What Was Built

### InfographicPreview (`frontend/src/components/content/InfographicPreview.tsx`)

Stat cards layout for infographic content bundles:
- Section header: "INFOGRAPHIC BRIEF" label + `visual_structure` Badge + Copy Caption button
- Headline with semibold text
- Key stats list with bold stat text and clickable source links
- Caption text block with border-top separator
- 7 component tests pass

### ContentPage (`frontend/src/pages/ContentPage.tsx`)

Full content review page replacing the stub:
- **Branch 1 (Loading):** Skeleton placeholders
- **Branch 2 (Error):** "Failed to load content..." + Try Again button
- **Branch 3 (404):** "No content today" empty state
- **Branch 4 (no_story_flag):** "No strong story found today" with score and TrendingDown icon
- **Branch 5 (pending draft):** Full review UI — format badge, draft content, sources, rationale, quality score, Approve + Reject buttons
- **Branch 6 (already actioned):** Read-only with "Reviewed" status badge

Format-specific draft rendering:
- `thread`: numbered tweet blocks in bordered containers
- `long_form`: readOnly Textarea with post text
- `infographic`: InfographicPreview component

`getClipboardText(bundle)` helper function:
- `'infographic'` → `draft_content.caption_text`
- `'long_form'` → `draft_content.post`
- `'thread'` → tweets joined with `'\n\n'`

Custom `approveMutation` (not `useApprove` hook) to control clipboard text:
- Calls `approveItem(draftItem.id)` then `navigator.clipboard.writeText(getClipboardText(bundle))`
- Toast: "Approved — copied to clipboard"

Reject flow: inline textarea + "Confirm Rejection" button.

### ContentPage Tests (`frontend/src/pages/ContentPage.test.tsx`)

9 tests, 0 skipped:
1. Thread format: renders content bundle
2. Thread format: renders numbered tweet blocks
3. Long form format: renders textarea with post text
4. Infographic format: renders InfographicPreview with INFOGRAPHIC BRIEF text
5. Sources section: shows corroborating_sources links
6. Approve flow: copies correct clipboard text per format_type
7. 404 state: shows "No content today" empty state
8. no_story_flag: shows "No strong story found today" with score
9. Already actioned: no pending draft → no Approve button

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added `test` script to package.json**
- **Found during:** Task 1 RED phase
- **Issue:** `package.json` had `dev`, `build`, `lint`, `preview` scripts but no `test` script, despite vitest being installed as a dev dependency
- **Fix:** Added `"test": "vitest"` to scripts
- **Files modified:** `frontend/package.json`
- **Commit:** 99b6f57

**2. [Rule 3 - Blocking] Symlinked node_modules from main repo to worktree**
- **Found during:** Task 1 RED phase
- **Issue:** Worktree at `agent-a9c8bee0` had no `node_modules` directory
- **Fix:** `ln -s /Users/matthewnelson/seva-mining/frontend/node_modules .../frontend/node_modules`
- **Commit:** 99b6f57

**3. [Rule 1 - Bug] Used vi.mock for API modules instead of MSW server.use() overrides in ContentPage tests**
- **Found during:** Task 2 GREEN phase
- **Issue:** Relative fetch URLs (`/content/today`) cannot be intercepted by MSW `setupServer` (Node.js) in jsdom environment — Node.js fetch requires absolute URLs. All ContentPage tests failed with the error state because requests threw "API error" instead of returning mock data.
- **Fix:** Used `vi.mock('@/api/content')` and `vi.mock('@/api/queue')` to mock API modules directly, bypassing the fetch layer entirely. This tests the component logic correctly without network I/O.
- **Files modified:** `frontend/src/pages/ContentPage.test.tsx`
- **Commit:** b7d236b
- **Note:** The RESEARCH.md MSW pattern applies to tests that fire real fetch() requests. For page-level component tests in this project, module mocking is the correct approach.

## Known Stubs

None — all data flows are wired to live API calls via TanStack Query. The ContentPage renders real data when the backend is running.

## Self-Check: PASSED

- FOUND: frontend/src/components/content/InfographicPreview.tsx
- FOUND: frontend/src/pages/ContentPage.tsx
- FOUND: frontend/src/pages/ContentPage.test.tsx
- FOUND: commit 99b6f57 (feat(08-03): build InfographicPreview component)
- FOUND: commit b7d236b (feat(08-03): build ContentPage with format-specific rendering)
