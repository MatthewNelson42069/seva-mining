---
phase: 03-react-approval-dashboard
plan: 01
subsystem: frontend
tags: [react, vite, tailwind, shadcn, typescript, msw, vitest, cors]
dependency_graph:
  requires: []
  provides: [frontend-scaffold, typescript-types, api-client, msw-mocks, backend-cors]
  affects: [03-02, 03-03, 03-04, 03-05]
tech_stack:
  added:
    - React 19 + Vite 6 (react-ts template)
    - Tailwind CSS v4 (@tailwindcss/vite plugin)
    - shadcn/ui (new-york style, Tailwind v4 auto-detected)
    - "@tanstack/react-query v5"
    - zustand v5
    - react-router-dom v7
    - date-fns v4
    - vitest v4 + @testing-library/react + jsdom
    - msw v2 (Mock Service Worker)
  patterns:
    - Vite proxy /api -> localhost:8000 for dev
    - Path alias @/ -> ./src/
    - QueryClientProvider + Toaster wrapping App in main.tsx
    - MSW server lifecycle in vitest setup.ts (beforeAll/afterEach/afterAll)
    - apiFetch wraps all API calls with JWT Bearer injection + 401 redirect
key_files:
  created:
    - frontend/package.json
    - frontend/vite.config.ts
    - frontend/tsconfig.json
    - frontend/tsconfig.app.json
    - frontend/index.html
    - frontend/src/main.tsx
    - frontend/src/App.tsx
    - frontend/src/index.css
    - frontend/components.json
    - frontend/src/lib/utils.ts
    - frontend/src/api/types.ts
    - frontend/src/api/client.ts
    - frontend/src/api/queue.ts
    - frontend/src/api/auth.ts
    - frontend/src/test/setup.ts
    - frontend/src/test/smoke.test.ts
    - frontend/src/mocks/handlers.ts
    - frontend/src/mocks/node.ts
    - frontend/src/components/ui/ (button, badge, tabs, dialog, sonner, separator, radio-group, textarea)
  modified:
    - backend/app/main.py (added CORSMiddleware)
decisions:
  - "MSW onUnhandledRequest: error enforces strict handler coverage in tests — any unmocked API call fails loudly"
  - "VITE_API_URL defaults to empty string so Vite proxy handles routing in dev; production sets explicit Railway URL"
  - "smoke.test.ts added to verify MSW server infrastructure initializes — will be removed or expanded in later plans"
metrics:
  duration_minutes: 6
  tasks_completed: 2
  files_created: 27
  files_modified: 1
  completed_date: "2026-03-31"
requirements_satisfied: [DASH-09, DASH-10]
---

# Phase 3 Plan 1: Frontend Foundation + API Layer Summary

React 19 + Vite 6 + Tailwind v4 + shadcn/ui project bootstrapped with typed API client, MSW test mocks, and CORS-enabled backend.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Bootstrap Vite + React 19 + Tailwind v4 + shadcn/ui | cfd265a | 29 files created in frontend/ |
| 2 | TypeScript types, API client, MSW mocks, backend CORS | 0505df2 | 9 files created/modified |

## Decisions Made

1. **MSW strict mode**: `onUnhandledRequest: 'error'` in test setup — any unmocked API call throws immediately, catching missing handler coverage early.

2. **VITE_API_URL defaults empty**: `BASE_URL = import.meta.env.VITE_API_URL ?? ''` means Vite's `/api` proxy handles dev routing without any env var. Production sets explicit Railway backend URL.

3. **smoke.test.ts**: Minimal test added to verify MSW setup infrastructure runs clean. Subsequent plans will add real tests for components.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] shadcn init required pre-configured tsconfig alias and Tailwind import**
- **Found during:** Task 1
- **Issue:** Running `npx shadcn@latest init --defaults` failed because shadcn requires the `@/*` path alias to already exist in tsconfig AND an `@import "tailwindcss"` line in index.css before it can validate
- **Fix:** Updated vite.config.ts (added tailwindcss plugin + @/ alias), tsconfig.app.json (added paths), and wrote minimal index.css with `@import "tailwindcss"` before running shadcn init. shadcn then overwrote index.css with its full CSS variables — which is the expected behavior per plan.
- **Files modified:** frontend/vite.config.ts, frontend/tsconfig.app.json, frontend/src/index.css, frontend/tsconfig.json
- **Commit:** cfd265a

**2. [Rule 3 - Blocking] npm create vite@latest created nested .git repository**
- **Found during:** Task 1 commit
- **Issue:** Vite template scaffolding creates its own `.git` directory, which git detected as an embedded repo and staged it as a submodule rather than tracking the files
- **Fix:** Used `git rm --cached -f frontend` to remove the submodule entry, then deleted `frontend/.git`, then re-added frontend/ as regular files
- **Commit:** cfd265a (same commit, resolved before staging)

## Known Stubs

None. All API files export real implementations. Mock data in handlers.ts is intentional test infrastructure, not production stubs.

## Self-Check: PASSED

Files verified present:
- frontend/package.json: FOUND
- frontend/vite.config.ts: FOUND (contains tailwindcss(), vitest config)
- frontend/tsconfig.app.json: FOUND (contains @/* path alias)
- frontend/src/main.tsx: FOUND (contains QueryClientProvider and Toaster)
- frontend/src/index.css: FOUND (contains @import "tailwindcss")
- frontend/components.json: FOUND
- frontend/src/components/ui/button.tsx: FOUND
- frontend/src/components/ui/sonner.tsx: FOUND
- frontend/src/api/types.ts: FOUND
- frontend/src/api/client.ts: FOUND (contains Authorization Bearer)
- frontend/src/api/queue.ts: FOUND
- frontend/src/api/auth.ts: FOUND
- frontend/src/mocks/handlers.ts: FOUND
- frontend/src/mocks/node.ts: FOUND
- frontend/src/test/setup.ts: FOUND (contains server.listen)
- backend/app/main.py: FOUND (contains CORSMiddleware + localhost:5173)

TypeScript: `npx tsc --noEmit` — PASSED (0 errors)
Vitest: `npx vitest run` — PASSED (1 test, MSW server initializes)
