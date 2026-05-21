---
phase: 260520-srt-add-canadian-defence-history-date-badges
plan: 01
subsystem: frontend/calendar
tags: [juno, calendar, defence-history, badge, tenant-isolation]
dependency_graph:
  requires: []
  provides: [defence-history-badge-juno-calendar]
  affects: [frontend/src/components/calendar/DayCell.tsx]
tech_stack:
  added: []
  patterns: [companyId-prop-gate, fixed-movable-range-dataset, priority-bucket-sort]
key_files:
  created:
    - frontend/src/data/junoDefenceCalendarDates.ts
    - frontend/src/data/__tests__/junoDefenceCalendarDates.test.ts
  modified:
    - frontend/src/components/calendar/DayCell.tsx
    - frontend/src/components/calendar/__tests__/DayCell.test.tsx
decisions:
  - "Veterans' Week range uses endDay:10 (not endDay:11) — Nov 11 must map exclusively to Remembrance Day fixed entry per must_haves truth"
  - "native title= tooltip included for operator hover context (zero-cost byproduct of description field already present)"
metrics:
  duration: ~5 minutes
  completed: 2026-05-21
  tasks_completed: 2
  tasks_total: 2
  files_created: 2
  files_modified: 2
---

# Quick Task 260520-srt: Add Canadian Defence-History Date Badges to Juno Calendar

**One-liner:** Hardcoded dataset of 29 fixed + 3 movable + 1 range Canadian defence commemorations surfaces as subdued informational badges above DayCell content on `/juno/calendar` only, tenant-gated via existing `companyId` prop.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Dataset module + lookup + tests | `81dfcbf` | `frontend/src/data/junoDefenceCalendarDates.ts` (new), `frontend/src/data/__tests__/junoDefenceCalendarDates.test.ts` (new) |
| 2 | DayCell badge render + cross-tenant isolation tests | `d14afea` | `frontend/src/components/calendar/DayCell.tsx` (modified), `frontend/src/components/calendar/__tests__/DayCell.test.tsx` (modified) |

## Test Counts

| Suite | Before | After | Delta |
|-------|--------|-------|-------|
| Frontend total | 181 | 195 | +14 |
| Dataset unit tests (new) | 0 | 10 | +10 |
| DayCell tests (existing + new) | 7 | 11 | +4 |

All 32 test files pass. Zero regressions.

## Files Added / Modified

### frontend/src/data/junoDefenceCalendarDates.ts (NEW)
- Exports `DefenceCalendarDate` type with `fixed | movable | range` discriminated shape
- Exports `junoDefenceCalendarDates` array (29 fixed + 3 movable + 1 range = 33 entries)
- Exports `getDefenceDateBadges(year, month, day)` returning matches in priority order
- Priority buckets: fixedMatches → movableMatches → rangeMatches (spread-concat return)
- Movable feast ordinal: `Math.ceil(day / 7)` paired with `target.getDay()` weekday check
- Omitted: Air India (Jun 23), Parliament Hill (Oct 22) — operator decision

### frontend/src/data/__tests__/junoDefenceCalendarDates.test.ts (NEW)
10 unit test cases:
1. Nov 11 → Remembrance Day (fixed, length 1)
2. Nov 8 → Indigenous Veterans Day + Veterans' Week (fixed+range, length 2, fixed first)
3. Nov 7 → Veterans' Week only (range, length 1)
4. May 3 2026 → Battle of the Atlantic Sunday (1st Sunday of May)
5. Jun 7 2026 → Canadian Armed Forces Day (1st Sunday of June)
6. Sep 20 2026 → Battle of Britain Sunday (3rd Sunday of September)
7. Mar 15 → empty array (no match)
8. Jun 23 → empty array (Air India omission enforced)
9. Oct 22 → empty array (Parliament Hill omission enforced)
10. Nov 11 2027 → Remembrance Day (cross-year, not year-pinned)

### frontend/src/components/calendar/DayCell.tsx (MODIFIED)
- Added `import { getDefenceDateBadges } from '@/data/junoDefenceCalendarDates'`
- Computes `defenceBadges` and `defenceBadge` after existing dayLabel/dayNumber vars
- Gate: `companyId === 'juno'` — Seva path evaluates to `[]`, renders nothing
- JSX: `{defenceBadge && <div data-testid="defence-badge" ...>{defenceBadge.name}</div>}`
- Styling: `text-zinc-500 text-[10px] uppercase tracking-wide truncate mb-1`
- `title={defenceBadge.description}` native browser tooltip
- Badge inserted between day-header `<div>` and `<textarea>`

### frontend/src/components/calendar/__tests__/DayCell.test.tsx (MODIFIED)
4 new tests in new `describe('DayCell defence badge')` block:
1. juno + Nov 11 → badge renders "Remembrance Day" with text-zinc-500
2. seva + Nov 11 → badge absent (D-10 invariant)
3. juno + Mar 15 → no `[data-testid="defence-badge"]` element
4. juno + Nov 8 → "Indigenous Veterans Day" visible, "Veterans' Week" absent (priority)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Veterans' Week range endDay corrected from 11 to 10**
- **Found during:** Task 1 (test case 1 failure on first run)
- **Issue:** Plan simultaneously states `endDay: 11` in the data spec and `must_haves` truth that Nov 11 returns only Remembrance Day (length 1). These are contradictory — with `endDay: 11`, Veterans' Week matches Nov 11 and the function returns length 2.
- **Fix:** Changed `endDay: 11` to `endDay: 10`. Veterans' Week spans Nov 5–10 (leading up to Remembrance Day); Nov 11 is covered exclusively by the fixed Remembrance Day entry. Consistent with must_haves: "Nov 5/6/7/9/10 show 'Veterans' Week'" (Nov 11 not listed).
- **Files modified:** `frontend/src/data/junoDefenceCalendarDates.ts`
- **Commit:** `81dfcbf`

## Tone Audit (Phase 10 D-01 Anti-Tactical Clause)

```
grep -iE "(heroic|glorious|smashed|annihilated|crushed|epic|brutal|how to|tactical|operational|doctrine)" frontend/src/data/junoDefenceCalendarDates.ts | grep -v "^\s*\*"
```
Result: **ZERO matches** — all descriptions are sober and commemorative.

## Omission Audit

```
grep -iE "(air india|parliament hill|cirillo|nathan)" frontend/src/data/junoDefenceCalendarDates.ts | grep -v "^\s*\*"
```
Result: **ZERO matches** — Air India (Jun 23) and Parliament Hill (Oct 22) are absent from the dataset per operator decision.

## Cross-Tenant Isolation Audit (D-10)

Files touched outside Juno-scoped paths:
- `DayCell.tsx` — shared component, but new logic is gated `companyId === 'juno'` so Seva path is logically unchanged. This matches the Phase 9 D-08 single-component precedent.
- No Seva-only routes, pages, or hooks modified.

The Seva calendar renders byte-identically (the gate evaluates `defenceBadges = []` for seva, `defenceBadge = null`, and the `{defenceBadge && (...)}` short-circuit renders nothing).

## Known Stubs

None — all data is wired and rendering correctly for `/juno/calendar`.

## Self-Check: PASSED

All 4 expected files found. Both commits (81dfcbf, d14afea) confirmed in git log. Full test suite 195/195.
