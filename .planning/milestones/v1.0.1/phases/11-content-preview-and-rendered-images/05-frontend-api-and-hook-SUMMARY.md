---
phase: 11
plan: 05-frontend-api-and-hook
status: completed
wave: 2
autonomous: true
tasks_completed: 2
tasks_total: 2
---

# Plan 05 — Frontend API and Hook — SUMMARY

## Commits

- `16cb730` — feat(11-05): add getContentBundle and rerenderContentBundle API client functions
- `87f100a` — feat(11-05): create useContentBundle hook with 5s polling and 10min ceiling
- `<this-commit>` — docs(11-05): complete frontend-api-and-hook plan

## Files touched

- `frontend/src/api/content.ts` — extended with `getContentBundle(id)` and `rerenderContentBundle(id)`
- `frontend/src/api/__tests__/content-bundle.test.ts` — un-skipped; 4 passing MSW tests (get + rerender + 401 + 404)
- `frontend/src/hooks/useContentBundle.ts` — new file, 35 lines, two exports
- `frontend/src/hooks/__tests__/useContentBundle.test.ts` — un-skipped; 7 passing tests

## Task 1 — API client functions (T1)

- `getContentBundle(id: string): Promise<ContentBundleDetailResponse>` — GET /content-bundles/{id}
- `rerenderContentBundle(id: string): Promise<RerenderResponse>` — POST /content-bundles/{id}/rerender
- Both use the existing `apiFetch` wrapper (JWT Authorization header applied automatically)
- Types imported from `@/api/types` (added in Plan 01)

## Task 2 — Polling hook (T2)

- `POLL_INTERVAL_MS = 5000` (D-12)
- `MAX_POLL_WINDOW_MS = 10 * 60 * 1000` (D-14)
- `useContentBundle(bundleId)` — TanStack Query v5 `useQuery` with `refetchInterval: (query) => …`
  - Stops polling once `rendered_images` has ≥1 entry
  - Stops polling after 10 minutes (age computed from `data.created_at`)
  - `enabled: !!bundleId` — no-op when modal is closed
- `useRerenderContentBundle(bundleId)` — TanStack Query v5 `useMutation` that invalidates the query cache on success so polling resumes with fresh data

### Polling-window implementation decisions

- `created_at` IS present on `ContentBundleDetailResponse` (confirmed from Plan 01's schema additions), so the age check uses `Date.now() - new Date(data.created_at).getTime()` directly — no `useRef` fallback needed.
- Tests 1–3 in `useContentBundle.test.ts` exercise the `refetchInterval` callback directly by pulling the live query out of the query cache and invoking its `refetchInterval` option with the real query object. This avoids a `vi.useFakeTimers()` + React Testing Library `waitFor` deadlock.

## Verification

- `npm run test -- --run src/api/__tests__/content-bundle.test.ts src/hooks/__tests__/useContentBundle.test.ts` → **11 passed**
- `npx tsc --noEmit` → exits 0

## Known pre-existing failures (out of Plan 05 scope)

- `DigestPage.test.tsx` (6 failures) — unrelated, pre-existing
- `ApprovalCard.test.tsx` "renders draft tabs" (1 failure) — unrelated, pre-existing

## Blockers / follow-ups

- None for Plan 05 itself.
- Orchestrator-level follow-up (flagged in Plan 03): `backend/app/routers/content_bundles.py` `_get_render_bundle_job()` falls back to a no-op stub in the backend process because `scheduler/agents/__init__.py` eagerly imports `tweepy`. To be addressed during Plan 07 (checkpoint) via `importlib.util.spec_from_file_location` to bypass the package `__init__.py`.

## Executor note

Plan 05's sub-agent completed the implementation and verified tests/tsc, but lost Bash access before committing. The orchestrator (main session) ran the verifications a second time, confirmed green, and made the two feature commits plus this SUMMARY commit.
