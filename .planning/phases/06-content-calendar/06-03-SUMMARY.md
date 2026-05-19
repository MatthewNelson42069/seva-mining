---
phase: 06-content-calendar
plan: 03
subsystem: frontend-data-layer
tags: [frontend, tanstack-query, optimistic-mutations, calendar, content-calendar, msw, vitest]
requirements: [CAL-09, CAL-10]
requirements_addressed: [CAL-09, CAL-10]
dependency_graph:
  requires:
    - "Plan 06-01 (backend schemas + migration 0013 — UNIQUE(date) + nullable title)"
    - "Plan 06-02 (backend full CRUD calendar router; live JSON contract — `body` field, YYYY-MM-DD dates)"
    - "frontend/src/api/client.ts (apiFetch + JWT Bearer pattern)"
    - "@tanstack/react-query ^5.96 (useQuery, useMutation, queryClient)"
    - "sonner ^2.0 (error toast surface)"
  provides:
    - "frontend/src/api/calendar.ts — typed CRUD verbs against /calendar"
    - "frontend/src/hooks/useCalendar.ts — useQuery hook with staleTime:0 + refetchOnWindowFocus:false (CAL-10)"
    - "frontend/src/hooks/useCalendarMutations.ts — useCreateCalendarItem, useUpdateCalendarItem, useDeleteCalendarItem with full optimistic + rollback pattern (CAL-09 / P2 defense)"
  affects:
    - "Plans 06-04 (Calendar grid UI — consumes useCalendar)"
    - "Plan 06-05 (Day-cell textarea — consumes the 3 mutation hooks)"
tech-stack:
  added: []
  patterns:
    - "TanStack Query v5 optimistic mutation triplet: onMutate (cancel + snapshot + write) / onError (restore snapshot) / onSettled (invalidate)"
    - "queryKey contract: ['calendar', start, end] — shared between useCalendar and all 3 mutation hooks"
    - "Vitest + @testing-library/react renderHook + fresh QueryClientProvider per test"
    - "fetch mock via vi.spyOn(global, 'fetch') with mockResolvedValueOnce for ordered responses"
key-files:
  created:
    - "frontend/src/api/calendar.ts"
    - "frontend/src/hooks/useCalendar.ts"
    - "frontend/src/hooks/useCalendarMutations.ts"
    - "frontend/src/hooks/__tests__/useCalendarMutations.test.tsx"
  modified: []
decisions:
  - "queryKey shape locked to ['calendar', start, end] (3-tuple) — both the query hook and all 3 mutation hooks reference this exact tuple"
  - "DELETE /calendar/{id} bypasses apiFetch and uses a thin local fetch — apiFetch always parses res.json() but DELETE returns 204 No Content with no body"
  - "Optimistic create uses sentinel id `optimistic-${Date.now()}` until server replies; onSettled invalidate will refetch the authoritative row"
  - "Failure surface: sonner toast on mutation error; success is silent (the optimistic write IS the feedback)"
metrics:
  duration_seconds: 144
  duration_minutes: 2
  tasks_completed: 3
  files_created: 4
  files_modified: 0
  lines_of_code: 402
  tests_added: 6
  tests_passing: "95/95 frontend suite (no regression)"
  completed_date: "2026-05-19"
---

# Phase 06 Plan 03: Frontend Calendar Data Layer Summary

Typed API module + `useCalendar` query hook + three optimistic-mutation hooks (create/update/delete) for the v2.1 Content Calendar — built decoupled from any UI and proven against mocked 500s in Vitest so the P2 rollback path is contractually demonstrated before Plans 06-04 / 06-05 wire the day-cell UI.

## What Was Built

### 1. `frontend/src/api/calendar.ts` (80 LOC)

Typed CRUD surface for the `/calendar` endpoints:

- `interface CalendarItem` — `{ id, date: string, body: string|null, created_at, updated_at }`. **Date is `string` end-to-end (P1 defense — no `Date` objects on the frontend).**
- `interface CalendarRangeResponse` — `{ items, total }`.
- `interface CalendarItemCreate` — `{ date, body }`. No `tag` (rescoped contract).
- `interface CalendarItemUpdate` — `{ body }`. No `tag`, no `date` (rescheduling deferred).
- `getCalendar(start, end)` — `GET /calendar?start=&end=` via `apiFetch`.
- `createCalendarItem(payload)` — `POST /calendar` via `apiFetch`.
- `updateCalendarItem(id, payload)` — `PATCH /calendar/{id}` via `apiFetch`.
- `deleteCalendarItem(id)` — `DELETE /calendar/{id}` using a thin local fetch (`apiFetch` always parses JSON; DELETE returns 204 No Content with no body, so we mirror the JWT+401 handling locally and skip parsing).

### 2. `frontend/src/hooks/useCalendar.ts` (22 LOC) — CAL-10

```typescript
useQuery({
  queryKey: ['calendar', start, end],
  queryFn: () => getCalendar(start, end),
  staleTime: 0,                  // CAL-10 / D-11
  refetchOnWindowFocus: false,   // CAL-10 / D-11
})
```

Grep evidence (CAL-10 contract):

```
$ grep -q "staleTime: 0" frontend/src/hooks/useCalendar.ts && echo OK
OK
$ grep -q "refetchOnWindowFocus: false" frontend/src/hooks/useCalendar.ts && echo OK
OK
```

### 3. `frontend/src/hooks/useCalendarMutations.ts` (134 LOC) — CAL-09 / P2 defense

Three hooks, each following the locked triplet:

| Step       | What it does                                                                |
| ---------- | --------------------------------------------------------------------------- |
| onMutate   | `cancelQueries` → `getQueryData` snapshot → `setQueryData` optimistic write |
| onError    | `setQueryData(queryKey, context.previous)` — restore snapshot               |
| onSettled  | `invalidateQueries({ queryKey })` — refetch is authoritative                |

queryKey tuple (locked, matches `useCalendar`):

```typescript
type CalendarQueryKey = ['calendar', string, string]
```

P2 rollback grep evidence (one per hook):

```
$ grep -n "context?.previous" frontend/src/hooks/useCalendarMutations.ts
64:      if (context?.previous !== undefined) {        # useCreateCalendarItem
96:      if (context?.previous !== undefined) {        # useUpdateCalendarItem
125:      if (context?.previous !== undefined) {       # useDeleteCalendarItem
```

### 4. `frontend/src/hooks/__tests__/useCalendarMutations.test.tsx` (166 LOC) — 6 tests

| # | Test | Proves                                                                            |
| - | ---- | --------------------------------------------------------------------------------- |
| 1 | useCreateCalendarItem > applies optimistic insert on mutate and keeps it on success | Optimistic insert lands in the cache before the server reply and survives `isSuccess` |
| 2 | useCreateCalendarItem > rolls back to snapshot on 500 (P2 defense)                  | On fetch 500, the optimistic new-date entry is removed and cache returns to SEED |
| 3 | useUpdateCalendarItem > applies optimistic body swap on mutate                      | `body` field updates in cache immediately on mutate; survives `isSuccess` |
| 4 | useUpdateCalendarItem > rolls back to snapshot on 500 (P2 defense)                  | On 500, `body` reverts from `'updated'` back to `'original'` |
| 5 | useDeleteCalendarItem > applies optimistic remove on mutate                         | item filtered out of cache; survives 204 No Content response |
| 6 | useDeleteCalendarItem > rolls back to snapshot on 500 (P2 defense)                  | On 500, item-1 is re-inserted into the cache from the snapshot |

Test run:

```
Test Files  1 passed (1)
Tests  6 passed (6)
```

Full-suite regression:

```
Test Files  15 passed (15)
Tests  95 passed (95)
```

## Decisions Made

1. **queryKey shape:** `['calendar', start, end]` (3-tuple). The mutation hooks invalidate this EXACT tuple, so the query hook and the mutation hooks must agree.
2. **DELETE 204 handling:** `apiFetch` always calls `res.json()`, which would throw on a 204 No Content body. `deleteCalendarItem` uses a thin local fetch that mirrors `apiFetch`'s 401-redirect + bearer-token behavior but skips JSON parsing.
3. **Optimistic create sentinel id:** `optimistic-${Date.now()}` — the `onSettled` invalidate triggers a refetch that replaces the optimistic row with the server-authoritative one (with the real UUID + timestamps).
4. **Failure surface:** sonner `toast.error(...)` on any mutation error; success is silent because the optimistic write IS the success feedback (D-03 silent-on-success principle).
5. **Date field type:** every date is `string` in `'YYYY-MM-DD'` format — no `Date` objects anywhere in the data layer (Pitfall P1 frontend-side defense).

## Verification Summary

| Check                                                                       | Result |
| --------------------------------------------------------------------------- | ------ |
| `cd frontend && npx tsc --noEmit`                                           | PASS (0 errors) |
| `cd frontend && npx vitest run src/hooks/__tests__/useCalendarMutations.test.tsx` | PASS (6/6) |
| `cd frontend && npx vitest run` (full suite)                                 | PASS (95/95) |
| `grep -q "staleTime: 0" frontend/src/hooks/useCalendar.ts`                   | PASS |
| `grep -q "refetchOnWindowFocus: false" frontend/src/hooks/useCalendar.ts`    | PASS |
| `grep -c "onMutate" frontend/src/hooks/useCalendarMutations.ts` (>= 3)        | 4 |
| `grep -c "onError" frontend/src/hooks/useCalendarMutations.ts` (>= 3)         | 4 |
| `grep -c "onSettled" frontend/src/hooks/useCalendarMutations.ts` (>= 3)       | 4 |
| `grep -c "context?.previous" frontend/src/hooks/useCalendarMutations.ts` (>= 3) | 3 |
| `grep -c "queryClient.cancelQueries" frontend/src/hooks/useCalendarMutations.ts` (>= 3) | 3 |
| `grep -c "queryClient.invalidateQueries" frontend/src/hooks/useCalendarMutations.ts` (>= 3) | 3 |
| `grep -c "rolls back" frontend/src/hooks/__tests__/useCalendarMutations.test.tsx` (>= 3) | 3 |
| `! grep -q "tag" frontend/src/api/calendar.ts`                               | PASS (no tag field) |
| `! grep -q ": Date" frontend/src/api/calendar.ts`                            | PASS (no Date objects) |

(`onMutate`/`onError`/`onSettled` count 4 because the doc-comment header references each step name once in addition to the 3 hook implementations — implementation count is exactly 3 per term, matching the spec.)

## Commits

| Task | Phase | Commit  | Message                                                      |
| ---- | ----- | ------- | ------------------------------------------------------------ |
| 1    | feat  | 06e819d | feat(06-03): add typed calendar.ts API module with CRUD verbs |
| 2    | feat  | e0e3a6d | feat(06-03): add useCalendar query hook with locked refetch behavior |
| 3a   | test  | 6ba2d10 | test(06-03): add failing tests for calendar mutation hooks (RED) |
| 3b   | feat  | 35c5f59 | feat(06-03): add optimistic calendar mutation hooks (GREEN)  |

## Deviations from Plan

None — plan executed exactly as written. The plan's `<action>` blocks were transcribed verbatim into the three implementation files and the test file; all acceptance criteria pass on the first run; no Rule 1/2/3 auto-fixes were required; no Rule 4 architectural questions surfaced.

## Known Stubs

None. This plan delivers the data layer only — the UI components that consume these hooks (Plans 06-04 / 06-05) are still to be built, but that is the deliberate phase split, not a stub. The data layer is fully exercised by the 6 Vitest tests in this plan.

## Self-Check: PASSED

All claims verified:

- `frontend/src/api/calendar.ts` — FOUND
- `frontend/src/hooks/useCalendar.ts` — FOUND
- `frontend/src/hooks/useCalendarMutations.ts` — FOUND
- `frontend/src/hooks/__tests__/useCalendarMutations.test.tsx` — FOUND
- Commit `06e819d` — FOUND
- Commit `e0e3a6d` — FOUND
- Commit `6ba2d10` — FOUND
- Commit `35c5f59` — FOUND
