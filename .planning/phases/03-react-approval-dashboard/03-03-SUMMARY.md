---
phase: 03-react-approval-dashboard
plan: "03"
subsystem: frontend
tags: [react, routing, auth, layout, shadcn, zustand]
dependency_graph:
  requires: ["03-01", "03-02"]
  provides: ["app-shell", "routing", "login-flow", "platform-tabs", "sidebar"]
  affects: ["03-04"]
tech_stack:
  added: [react-router-dom]
  patterns:
    - BrowserRouter with nested protected routes via Outlet
    - ProtectedRoute checks Zustand isAuthenticated
    - PlatformTabBar driven by props (activeTab, onTabChange, counts)
    - NavLink with end={true} for root route active detection
key_files:
  created:
    - frontend/src/pages/LoginPage.tsx
    - frontend/src/components/layout/ProtectedRoute.tsx
    - frontend/src/components/layout/AppShell.tsx
    - frontend/src/components/layout/Sidebar.tsx
    - frontend/src/components/layout/PlatformTabBar.tsx
    - frontend/src/components/layout/PlatformTabBar.test.tsx
    - frontend/src/pages/QueuePage.tsx
    - frontend/src/pages/DigestPage.tsx
    - frontend/src/pages/ContentPage.tsx
    - frontend/src/pages/SettingsPage.tsx
  modified:
    - frontend/src/App.tsx
decisions:
  - "QueuePage uses useQueue for all 3 platforms simultaneously to populate badge counts — queries run in parallel"
  - "PlatformTabBar is prop-driven (no internal state) for testability — QueuePage owns the active tab state"
  - "Sidebar uses NavLink end={true} only for root '/' to avoid matching /settings as Queue-active"
  - "LoginPage catches error status to show 'Incorrect password' on 401/403, generic message otherwise"
metrics:
  duration_seconds: 191
  completed_date: "2026-03-31"
  tasks_completed: 2
  files_created: 10
  files_modified: 1
---

# Phase 3 Plan 03: Application Shell, Routing, and Login Summary

**One-liner:** React router setup with password login, JWT auth gate, sidebar navigation, and platform tabs with badge counts in a 1280px-minimum desktop shell.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Build login page and auth flow | 3f4c1a5 | LoginPage.tsx, ProtectedRoute.tsx |
| 2 | Build AppShell, Sidebar, PlatformTabBar, routing, page stubs | 571d926 | App.tsx + 9 new files |

## What Was Built

### Task 1: Login Page and Auth Flow
- `LoginPage.tsx`: Centered card layout, password-only field, calls `login()` API, stores JWT via `setToken`, navigates to `/` on success. Shows "Incorrect password" on 401/403. Redirects already-authenticated users immediately.
- `ProtectedRoute.tsx`: Checks `isAuthenticated` from Zustand store. Renders `<Outlet />` for authenticated users, `<Navigate to="/login" replace />` otherwise.

### Task 2: AppShell, Sidebar, PlatformTabBar, Routing, Page Stubs
- `App.tsx`: BrowserRouter with Routes — `/login` is public, all others are nested inside ProtectedRoute → AppShell.
- `AppShell.tsx`: `min-w-[1280px]` desktop-only flex layout — Sidebar (220px) + main content Outlet.
- `Sidebar.tsx`: NavLink navigation for Queue/Digest/Content/Settings with lucide-react icons. Active state uses blue-50 background per D-13. Logout button calls `clearToken()` and navigates to `/login`.
- `PlatformTabBar.tsx`: Prop-driven tabs for twitter/instagram/content using shadcn Tabs. Badge counts shown as blue pills when count > 0.
- `QueuePage.tsx`: Runs all 3 platform queries in parallel for badge counts. Shows empty state "Queue is clear" when no items for active platform.
- Stub pages (DigestPage, ContentPage, SettingsPage): Heading + "Coming in Phase 8" placeholder.

## Verification

- TypeScript: zero errors (`tsc --noEmit`)
- Vitest: 12/12 tests pass (4 new PlatformTabBar tests + 8 existing)

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

| File | Stub | Reason |
|------|------|--------|
| frontend/src/pages/QueuePage.tsx | `<div>` placeholder for approval card list | Plan 04 wires ApprovalCard components — intentional per plan |
| frontend/src/pages/DigestPage.tsx | "Coming in Phase 8" | Intentional — not in Phase 3 scope |
| frontend/src/pages/ContentPage.tsx | "Coming in Phase 8" | Intentional — not in Phase 3 scope |
| frontend/src/pages/SettingsPage.tsx | "Coming in Phase 8" | Intentional — not in Phase 3 scope |

These stubs do not prevent Plan 03's goal: the shell, routing, login, and platform tabs all function. Plan 04 will wire the approval cards into QueuePage.

## Self-Check: PASSED

Files exist:
- frontend/src/pages/LoginPage.tsx: FOUND
- frontend/src/components/layout/ProtectedRoute.tsx: FOUND
- frontend/src/components/layout/AppShell.tsx: FOUND
- frontend/src/components/layout/Sidebar.tsx: FOUND
- frontend/src/components/layout/PlatformTabBar.tsx: FOUND
- frontend/src/components/layout/PlatformTabBar.test.tsx: FOUND
- frontend/src/pages/QueuePage.tsx: FOUND
- frontend/src/pages/DigestPage.tsx: FOUND
- frontend/src/pages/ContentPage.tsx: FOUND
- frontend/src/pages/SettingsPage.tsx: FOUND

Commits:
- 3f4c1a5: feat(03-03): build login page and auth gate
- 571d926: feat(03-03): build AppShell, Sidebar, PlatformTabBar, routing, and page stubs
