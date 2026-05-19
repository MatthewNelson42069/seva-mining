---
phase: 06-content-calendar
plan: 04
subsystem: frontend-content-calendar-grid
tags: [calendar, frontend, react, weekly-grid, auto-save, tdd]
requires:
  - 06-03 (useCalendar query hook + 3 optimistic mutation hooks)
  - 06-02 (calendar router GET range / POST / PATCH / DELETE)
  - 06-01 (calendar_items schema + Pydantic contract)
provides:
  - frontend/src/lib/week.ts (ISO Mon-Sun helpers)
  - frontend/src/components/calendar/DayCell.tsx (textarea + auto-save branch)
  - frontend/src/components/calendar/WeeklyGrid.tsx (7-column coordinator)
affects:
  - Phase 06 Plan 05 (page-level navigation will mount WeeklyGrid)
tech-stack:
  added: []
  patterns:
    - "Native textarea over shadcn primitive when ref forwarding is required"
    - "useEffect reconcile on [item?.id, item?.body] to absorb optimistic invalidations"
    - "vi.mock of mutation hooks for spy-based branch coverage"
key-files:
  created:
    - frontend/src/lib/week.ts
    - frontend/src/lib/__tests__/week.test.ts
    - frontend/src/components/calendar/DayCell.tsx
    - frontend/src/components/calendar/__tests__/DayCell.test.tsx
    - frontend/src/components/calendar/WeeklyGrid.tsx
  modified: []
decisions:
  - "Native <textarea> (not shadcn <Textarea>): shadcn primitive doesn't forwardRef so CAL-07 click-to-focus via ref would silently fail"
  - "Idle-save guard inside Branch 4: skip PATCH when current === item.body to avoid hot-path noise from focus/blur with no edit"
  - "Day cell sizing: min-h-32 max-h-64 overflow-y-auto (per CONTEXT.md Claude's Discretion) — keeps grid visually balanced while not truncating long plans"
  - "Empty-state placeholder is the em-dash '—' (per CONTEXT.md Claude's Discretion)"
  - "WeeklyGrid is stateless w/r/t which week is shown — page-level (Plan 06-05) owns prev/next/Today"
metrics:
  duration_minutes: 3
  completed_date: "2026-05-19"
  task_count: 3
  files_created: 5
  files_modified: 0
  tests_added: 13
  tests_passing_total: 108
requirements_addressed: [CAL-05, CAL-06, CAL-07, CAL-08]
---

# Phase 06 Plan 04: Weekly Grid + Day Cell Auto-Save Summary

7-cell Mon-Sun weekly calendar grid where each cell is a native textarea that auto-saves on blur via a 4-way branch (POST | PATCH | DELETE | noop), with today's cell highlighted in amber-500.

## What Shipped

Three React modules + one date utility module, fully TDD-covered:

| File | LOC | Purpose |
|---|---|---|
| `frontend/src/lib/week.ts` | 35 | ISO Mon-Sun helpers (`getWeekStart`, `getWeekEnd`, `formatDateISO`, `getWeekDays`) |
| `frontend/src/lib/__tests__/week.test.ts` | 57 | 6 assertions: Mon anchor, Sun anchor, ISO format, Mon-Sun ordering, Monday-input identity, Sunday-input previous-Monday |
| `frontend/src/components/calendar/DayCell.tsx` | 124 | Native textarea + 4-way auto-save branch + today highlight + line-break-preserving render |
| `frontend/src/components/calendar/__tests__/DayCell.test.tsx` | 147 | 7 assertions: noop, POST, PATCH, DELETE, idle-save-guard, today=true, today=false |
| `frontend/src/components/calendar/WeeklyGrid.tsx` | 82 | grid-cols-7 coordinator consuming `useCalendar` + composing 7 `<DayCell>` instances |

## Auto-Save Decision Table (DayCell `handleBlur`)

The five branches the textarea evaluates on blur:

| `current.trim()` | `item` (persisted row) | `current === item.body` | Action |
|---|---|---|---|
| `''` | `null` | n/a | **noop** — no row to delete, nothing to save |
| `''` | exists | n/a | **DELETE** `item.id` (D-05: clearing deletes the row) |
| non-empty | `null` | n/a | **POST** `{date, body: current}` (first save) |
| non-empty | exists | `false` | **PATCH** `{id, payload: {body: current}}` (edit) |
| non-empty | exists | `true` | **noop** — idle save guard (focus/blur with no edit) |

The idle save guard matters because the cell auto-saves on blur, not on Enter or button click. Without the guard, simply tabbing through cells would PATCH every populated row to its current value on every focus traversal.

## Tests → Requirement Mapping

| Test | File | Verifies |
|---|---|---|
| `getWeekStart returns Monday` | week.test.ts | CAL-05 (Mon-Sun grid root) |
| `getWeekEnd returns Sunday` | week.test.ts | CAL-05 |
| `formatDateISO emits YYYY-MM-DD` | week.test.ts | P1 defense (TZ-naive backend contract) |
| `getWeekDays returns 7 days in Mon-Sun order` | week.test.ts | CAL-05 |
| `getWeekStart for a Monday returns same Monday` | week.test.ts | CAL-05 (idempotence) |
| `getWeekStart for a Sunday returns previous Monday` | week.test.ts | CAL-05 (ISO edge case) |
| `noop: empty textarea + no row` | DayCell.test.tsx | CAL-08 (Branch 1 — no spurious requests) |
| `POST: text typed + no row` | DayCell.test.tsx | CAL-08 (Branch 2 — first save) |
| `PATCH: text changed + row exists` | DayCell.test.tsx | CAL-08 (Branch 3 — edit) |
| `DELETE: cleared textarea + row exists` | DayCell.test.tsx | CAL-08 + D-05 (clear-deletes) |
| `idle save guard: text unchanged + row exists` | DayCell.test.tsx | CAL-08 (Branch 5 — idle guard) |
| `today highlight: isToday=true adds ring-amber-500` | DayCell.test.tsx | CAL-05 / D-09 |
| `today highlight: isToday=false does NOT add ring-amber-500` | DayCell.test.tsx | CAL-05 / D-09 (class-conditional, not structural) |

CAL-06 (whitespace-pre-wrap) and CAL-07 (click-to-focus) are verified by static grep acceptance criteria in the plan rather than dedicated unit tests — both are pure className/structural contracts whose unit-test value would be tautological.

## Decision Log

### 1. Native `<textarea>` over shadcn `<Textarea>`

The shadcn `Textarea` primitive at `frontend/src/components/ui/textarea.tsx` is a plain function component — it does NOT call `React.forwardRef`. CAL-07 requires the outer cell's `onClick` to call `textareaRef.current?.focus()`, which requires a real DOM ref. Two options were available:

- **Modify the shadcn primitive** to forward refs — touches a shared file, risks regressions elsewhere.
- **Inline a native textarea** in DayCell with the shadcn baseline className inlined (`bg-transparent`, no border, no focus ring) — keeps the focus contract obvious and the change surface tight.

Plan locked option B. Acceptance criteria enforce `! grep -q "<Textarea"` and `! grep -q "from '@/components/ui/textarea'"` to prevent regression. Both pass.

### 2. Idle save guard inside Branch 4

Without the `current === persisted` guard, every focus traversal of a populated cell would PATCH it back to its current value. With auto-save on blur as the only save trigger, this would create silent request fan-out during normal keyboard navigation. The guard is cheap (string equality) and catches the case at the right layer.

### 3. Day-cell height: `min-h-32 max-h-64 overflow-y-auto`

Per CONTEXT.md Claude's Discretion. `min-h-32` keeps the grid visually balanced when cells are empty; `max-h-64` plus `overflow-y-auto` prevents one verbose day from blowing out the grid row height; internal scroll preserves the full content.

### 4. Empty-state placeholder: `—`

Per CONTEXT.md Claude's Discretion. The em-dash is visually faint, communicates "intentionally empty" without dictating tone, and disappears immediately when the user types.

### 5. WeeklyGrid is week-stateless

The grid takes `weekAnchor: Date` and renders exactly that week. Prev/next/Today buttons + week-state management live in Plan 06-05 at the page level. Keeping WeeklyGrid stateless means it composes cleanly inside whatever shell Plan 06-05 builds — and unit-testing it later won't require mocking week navigation.

## Verification Gates Passed

- `cd frontend && npx vitest run` — 17 test files, 108 tests passing (95 preexisting + 13 new)
- `cd frontend && npx tsc --noEmit` — clean
- CAL-05: `grid-cols-7` in WeeklyGrid + `weekStartsOn: 1` in week.ts
- CAL-06: `whitespace-pre-wrap` in DayCell
- CAL-07: `textareaRef.current?.focus` in DayCell
- CAL-08: All 5 auto-save branches covered in DayCell.test.tsx

## Deviations from Plan

None — plan executed exactly as written. One micro-edit was made to a JSDoc comment in DayCell.tsx to avoid the literal substring `<Textarea` appearing in the file (the plan's acceptance criteria use a strict `! grep -q "<Textarea"` check that doesn't distinguish comments from code). The substantive guidance in the comment is preserved.

## Known Stubs

None. All produced components are wired to the live data layer from Plan 06-03 (`useCalendar`, `useCreateCalendarItem`, `useUpdateCalendarItem`, `useDeleteCalendarItem`). The Wave 4 work (Plan 06-05) will mount `WeeklyGrid` into `ContentCalendarPage` and add the prev/next/Today shell — the current stub at `frontend/src/pages/ContentCalendarPage.tsx` remains in place by design and is owned by 06-05.

## Commits

| Hash | Subject |
|---|---|
| `cb42270` | feat(06-04): add ISO week (Mon-Sun) helpers with vitest coverage |
| `5d4e3e1` | feat(06-04): add DayCell with auto-save 4-way branch on blur |
| `7f40d53` | feat(06-04): add WeeklyGrid 7-column Mon-Sun coordinator (CAL-05) |

## Self-Check: PASSED

- All 5 created files verified on disk
- All 3 per-task commits verified in git log
- Full vitest suite 108/108 passing
- TypeScript clean (`npx tsc --noEmit` exits 0)
