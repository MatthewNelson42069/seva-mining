---
phase: 260520-srt-add-canadian-defence-history-date-badges
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - frontend/src/data/junoDefenceCalendarDates.ts
  - frontend/src/data/__tests__/junoDefenceCalendarDates.test.ts
  - frontend/src/components/calendar/DayCell.tsx
  - frontend/src/components/calendar/__tests__/DayCell.test.tsx
autonomous: true
requirements:
  - QUICK-260520-SRT
must_haves:
  truths:
    - "Operator viewing /juno/calendar sees a subdued badge above the date cell content on days matching a curated Canadian defence/military commemoration"
    - "/seva/calendar shows no such badges (D-10 byte-identical contract preserved)"
    - "Nov 8 shows 'Indigenous Veterans Day' (fixed wins over Veterans' Week range); Nov 11 shows 'Remembrance Day'; Nov 5/6/7/9/10 show 'Veterans' Week'"
    - "Movable feasts resolve correctly (Battle of the Atlantic Sunday on 1st Sunday of May, Canadian Armed Forces Day on 1st Sunday of June, Battle of Britain Sunday on 3rd Sunday of September)"
    - "Air India bombing (Jun 23) and Parliament Hill Attack (Oct 22) produce no badge — confirmed omitted per operator decision"
    - "Badge text never competes with operator's drafted content (subdued muted token, not Juno brand accent)"
    - "Dataset descriptions are sober/commemorative tone — no celebratory, sensational, or operational language (Phase 10 D-01 anti-tactical clause)"
  artifacts:
    - path: "frontend/src/data/junoDefenceCalendarDates.ts"
      provides: "Dataset (29 fixed + 3 movable + 1 range) and getDefenceDateBadges(year, month, day) lookup"
      exports: ["DefenceCalendarDate", "junoDefenceCalendarDates", "getDefenceDateBadges"]
    - path: "frontend/src/data/__tests__/junoDefenceCalendarDates.test.ts"
      provides: "Unit tests for fixed lookup, movable-feast computation, range overlap, omitted dates, no-match"
    - path: "frontend/src/components/calendar/DayCell.tsx"
      provides: "Badge slot above textarea, tenant-gated to companyId === 'juno', priority-aware (fixed > movable > range)"
    - path: "frontend/src/components/calendar/__tests__/DayCell.test.tsx"
      provides: "Cross-tenant isolation tests + render/no-render assertions"
  key_links:
    - from: "frontend/src/components/calendar/DayCell.tsx"
      to: "frontend/src/data/junoDefenceCalendarDates.ts"
      via: "import { getDefenceDateBadges } from '@/data/junoDefenceCalendarDates'"
      pattern: "getDefenceDateBadges\\("
    - from: "DayCell render"
      to: "tenant gating"
      via: "conditional on companyId prop"
      pattern: "companyId === 'juno'"
---

<objective>
Add Canadian defence-history date badges to the Juno Calendar tab (`/juno/calendar`).
Days matching curated Canadian defence/military commemorations display a small
subdued static badge above the date cell content (above the existing textarea
inside DayCell), showing the event name. Seva calendar untouched per v3.0 D-10
byte-identical contract.

Purpose: Help the operator be aware of significant Canadian defence dates when
planning Juno content. Brand voice is Janes/CSIS desk — sober, sourced; the
dataset descriptions must NEVER be celebratory, sensational, or operational
(Phase 10 D-01 anti-tactical clause).

Output:
  - `frontend/src/data/junoDefenceCalendarDates.ts` (dataset + lookup)
  - `frontend/src/data/__tests__/junoDefenceCalendarDates.test.ts` (unit tests)
  - Badge slot added to `DayCell.tsx` (tenant-gated by companyId prop)
  - DayCell tests extended for tenant isolation + badge render
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@CLAUDE.md
@frontend/src/components/calendar/DayCell.tsx
@frontend/src/components/calendar/__tests__/DayCell.test.tsx
@frontend/src/hooks/useCompanyBrand.ts
@frontend/src/config/companyBrandConfig.ts

<interfaces>
<!-- Key types and contracts already in the codebase. Use these directly. -->

DayCell already receives `companyId: CompanyId` as a prop — gate the badge
render with `companyId === 'juno'` directly. Do NOT introduce useCompanyBrand
inside DayCell (the prop is the established pattern; WeeklyGrid passes it down).

From frontend/src/components/calendar/DayCell.tsx:
```typescript
import type { CompanyId } from '@/api/queryKeys'

interface DayCellProps {
  companyId: CompanyId        // 'seva' | 'juno'
  date: Date
  item: CalendarItem | null
  weekRange: { start: string; end: string }
  isToday: boolean
}
```

Existing styling reference (subdued muted token already used elsewhere in
DayCell): `text-zinc-500`, `text-zinc-300`. Use `text-zinc-500` family for
the badge — NOT `bg-brand-accent` (informational, not branded).

Existing render structure inside the outer cell `<div>`:
  1. Header row (day label + day number) — `<div className="flex items-baseline justify-between mb-1.5">`
  2. Textarea — `<textarea>`

Insert the badge slot BETWEEN (1) and (2). When `companyId !== 'juno'` OR
when there are no matches, render NOTHING (not an empty `<div>`).
</interfaces>

<dataset_summary>
29 fixed annual dates + 3 movable feasts + 1 inclusive range (Nov 5–11
Veterans' Week). Full table is in the task action below; do NOT paraphrase
descriptions — copy them verbatim from this plan. Omit Jun 23 (Air India)
and Oct 22 (Parliament Hill) per operator decision.

Priority when multiple entries match the same day:
  fixed > movable > range

This makes Nov 8 show "Indigenous Veterans Day" and Nov 11 show
"Remembrance Day"; Nov 5/6/7/9/10 fall back to "Veterans' Week".
</dataset_summary>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Create dataset module + lookup with tests</name>
  <files>
    frontend/src/data/junoDefenceCalendarDates.ts
    frontend/src/data/__tests__/junoDefenceCalendarDates.test.ts
  </files>
  <behavior>
    Unit tests (write FIRST, expect RED, then implement to GREEN):

    1. `getDefenceDateBadges(2026, 11, 11)` returns array of length 1 containing
       the Remembrance Day entry (`name === 'Remembrance Day'`).
    2. `getDefenceDateBadges(2026, 11, 8)` returns array of length 2: BOTH the
       Indigenous Veterans Day fixed entry AND the Veterans' Week range entry.
       The fixed entry MUST appear before the range entry (priority ordering:
       fixed > movable > range).
    3. `getDefenceDateBadges(2026, 11, 7)` returns array of length 1 containing
       ONLY the Veterans' Week range entry (in range, no fixed match).
    4. `getDefenceDateBadges(2026, 5, 3)` returns Battle of the Atlantic Sunday
       (first Sunday of May 2026 = May 3 — verifies movable-feast computation).
    5. `getDefenceDateBadges(2026, 6, 7)` returns Canadian Armed Forces Day
       (first Sunday of June 2026 = June 7).
    6. `getDefenceDateBadges(2026, 9, 20)` returns Battle of Britain Sunday
       (3rd Sunday of September 2026 = Sep 20).
    7. `getDefenceDateBadges(2026, 3, 15)` returns empty array (non-matching).
    8. `getDefenceDateBadges(2026, 6, 23)` returns empty array (Air India OMITTED
       — operator decision; this test enforces the omission).
    9. `getDefenceDateBadges(2026, 10, 22)` returns empty array (Parliament Hill
       OMITTED — operator decision; this test enforces the omission).

    Cross-year sanity check (one assertion is enough — these are annual fixed
    dates, year is only used for movable/range weekday math):
    10. `getDefenceDateBadges(2027, 11, 11)` ALSO returns Remembrance Day
        (verifies fixed dates aren't year-pinned).
  </behavior>
  <action>
    Per the operator's locked decision (storage = hardcoded TS data file,
    registry-pattern precedent from Phase 13 `companyBrandConfig.ts`):

    **Step A — Write the test file FIRST** (`frontend/src/data/__tests__/junoDefenceCalendarDates.test.ts`).
    Use Vitest. Cover all 10 cases above. Run `npm test -- junoDefenceCalendarDates` —
    expect RED (module does not exist yet). Commit RED state? No — keep it
    in-flight; this is a single atomic commit at end of executor pass per the
    operator's commit_strategy.

    **Step B — Implement the dataset module** (`frontend/src/data/junoDefenceCalendarDates.ts`):

    1. Export the type EXACTLY as specified in the planning context:

    ```typescript
    export type DefenceCalendarDate = {
      // Exactly ONE of these three should be set per entry:
      fixed?: { month: number; day: number }
      movable?: { month: number; weekday: number; ordinal: 1 | 2 | 3 | 4 }
      range?: { startMonth: number; startDay: number; endMonth: number; endDay: number }

      name: string
      description: string
      significance?: string
    }
    ```

    2. Export `junoDefenceCalendarDates: DefenceCalendarDate[]` containing all
       29 fixed entries + 3 movable entries + 1 range entry, in this exact order
       (calendar-month order for fixed; movables and range appended at end).

       Copy the `name` and `description` fields VERBATIM from the planning
       context's dataset_to_implement table. Do NOT rewrite or paraphrase —
       the operator has reviewed these for tone compliance (Phase 10 D-01
       anti-tactical clause). Sober, commemorative, no celebratory language.

       Fixed dates (29 entries) — month/day pairs:
       (2,1), (4,1), (4,4), (4,9), (4,22), (4,24), (5,4), (5,5), (5,8), (5,9),
       (5,12), (5,28), (5,29), (6,6), (6,25), (7,1), (7,27), (8,9), (8,13),
       (8,15), (8,19), (8,21), (9,3), (10,26), (11,8), (11,11), (12,8),
       (12,20), (12,25).

       Movable feasts (3 entries) — weekday 0 = Sunday:
       - { month: 5, weekday: 0, ordinal: 1 } → "Battle of the Atlantic Sunday"
       - { month: 6, weekday: 0, ordinal: 1 } → "Canadian Armed Forces Day"
       - { month: 9, weekday: 0, ordinal: 3 } → "Battle of Britain Sunday"

       Range (1 entry):
       - { startMonth: 11, startDay: 5, endMonth: 11, endDay: 11 } → "Veterans' Week"

       Descriptions (use these verbatim):
       - Feb 1: "Anniversary of the 1968 Canadian Forces Reorganization Act unifying the RCN, Army, and RCAF into one service."
       - Apr 1: "Anniversary of the RCAF's 1924 establishment as a permanent component of Canadian defence."
       - Apr 4: "Canada was one of twelve founding signatories of the 1949 North Atlantic Treaty."
       - Apr 9: "Commemorates the Canadian Corps' assault on Vimy Ridge, 9–12 April 1917."
       - Apr 22: "Canada's 1st Division held against the first large-scale chlorine gas attack on the Western Front, 1915."
       - Apr 24: "2 PPCLI's defensive stand against Chinese forces in the Korean War, 22–25 April 1951."
       - May 4: "Anniversary of Royal Assent for the 1910 Naval Service Act establishing Canada's navy."
       - May 5: "Marks the German surrender to Lt-Gen Charles Foulkes at Wageningen, 1945."
       - May 8: "Marks the end of the Second World War in Europe, 1945."
       - May 9: "Commemorates the end of Canada's military mission in Afghanistan; informally observed."
       - May 12: "Formal 1958 Canada–US agreement establishing the North American Aerospace Defense Command."
       - May 28: "Anniversary of the 2000 interment of Canada's Unknown Soldier at the National War Memorial."
       - May 29: "UN-designated day honouring peacekeepers worldwide."
       - Jun 6: "Marks the 1944 Allied landings in Normandy; approximately 14,000 Canadians landed on Juno Beach."
       - Jun 25: "Beginning of the 1950 Korean War; more than 26,000 Canadians served."
       - Jul 1: "Provincial day of mourning marking the Battle of Beaumont-Hamel, 1 July 1916."
       - Jul 27: "National day honouring Korean War veterans; marks the 1953 armistice."
       - Aug 9: "Marks the 1974 loss of nine Canadians when their UN aircraft was shot down over Syria."
       - Aug 13: "Authorization of the CWAC in 1941, the first formal integration of women in the Canadian Army."
       - Aug 15: "Marks Japan's surrender, 1945; the formal end of the Second World War."
       - Aug 19: "Canada's bloodiest single day of the war, 1942; approximately 3,350 of 5,000 Canadians became casualties."
       - Aug 21: "Marks the 1944 sealing of the Falaise Pocket by Canadian and Polish forces."
       - Sep 3: "Honours Canadian Merchant Navy sailors, particularly in the Battle of the Atlantic."
       - Oct 26: "Start of the Canadian Corps' assault at Passchendaele, 26 October – 10 November 1917."
       - Nov 8: "Recognizes First Nations, Inuit, and Métis military service; distinct from Remembrance Day."
       - Nov 11: "National day of remembrance marking the 1918 Armistice."
       - Dec 8: "Marks the opening of the 1941 Hong Kong battle; Canada's first ground combat of WWII."
       - Dec 20: "Canadian 1st Division's urban battle in Italy, 20–28 December 1943."
       - Dec 25: "Two solemn Christmas-day anniversaries in Canadian military memory, 1943 and 1941."
       Movables:
       - Battle of the Atlantic Sunday: "Commemorates the Second World War's longest campaign, 1939–1945; over 4,600 RCN, RCAF, and Merchant Navy lost."
       - Canadian Armed Forces Day: "National observance recognizing CAF personnel, heritage, and service; established 2002."
       - Battle of Britain Sunday: "Commemorates the 1940 air defence of the UK; over 100 Canadian pilots flew in the battle."
       Range:
       - Veterans' Week: "Annual week of remembrance leading to Remembrance Day."

       Names (verbatim from table): Canadian Armed Forces Unification Day,
       Royal Canadian Air Force Birthday, NATO Founding Day, Vimy Ridge Day,
       Second Battle of Ypres Anniversary, Battle of Kapyong Anniversary,
       Royal Canadian Navy Founding, Liberation of the Netherlands,
       Victory in Europe (VE) Day, National Day of Honour, NORAD Agreement Anniversary,
       Tomb of the Unknown Soldier Interment, International Day of UN Peacekeepers,
       D-Day / Juno Beach Anniversary, Korean War Outbreak Anniversary,
       Newfoundland & Labrador Memorial Day, Korean War Veterans Day,
       National Peacekeepers' Day, Canadian Women's Army Corps Anniversary,
       End of the Second World War in the Pacific, Dieppe Raid Anniversary,
       Closing of the Falaise Pocket, Merchant Navy Veterans Day,
       Canadian Corps at Passchendaele, Indigenous Veterans Day, Remembrance Day,
       Battle of Hong Kong Anniversary, Battle of Ortona Begins,
       Christmas at Ortona / Fall of Hong Kong.

       Movables: Battle of the Atlantic Sunday, Canadian Armed Forces Day,
       Battle of Britain Sunday.

       Range: Veterans' Week.

    3. Implement and export `getDefenceDateBadges(year: number, month: number, day: number): DefenceCalendarDate[]`:

       - `month` and `day` are 1-indexed (1 = January, 1 = first day).
       - Construct `const target = new Date(year, month - 1, day)` for weekday math.
       - Iterate `junoDefenceCalendarDates`, collecting matches into three buckets
         (fixedMatches, movableMatches, rangeMatches), then return
         `[...fixedMatches, ...movableMatches, ...rangeMatches]` so priority
         ordering is preserved for the caller.
       - Fixed match: `entry.fixed?.month === month && entry.fixed?.day === day`.
       - Movable match: `entry.movable?.month === month` AND `target.getDay() === entry.movable.weekday`
         AND the Nth occurrence of that weekday in the month equals `entry.movable.ordinal`.
         Implementation hint: `const ordinal = Math.ceil(day / 7)` — works because
         the Nth occurrence of weekday W in a month always falls in days
         `[(N-1)*7 + 1 .. N*7]` exactly when that weekday matches. Pair the
         weekday check with this ordinal computation.
       - Range match: handle same-month ranges (`startMonth === endMonth`) with
         `month === startMonth && day >= startDay && day <= endDay`. (The data
         shape supports cross-month ranges but we have none; either implement
         the cross-month case correctly or assert `startMonth === endMonth` for
         the Veterans' Week entry — pick the cleaner of the two.)

    **Step C — Run tests, expect GREEN.** Iterate until all 10 cases pass.

    **Tone enforcement note for code reviewer:** No description should contain
    words like "heroic", "glorious", "smashed", "annihilated", "crushed",
    "victorious", "epic", or any operational/tactical framing ("how to",
    "lessons learned", "tactics", "doctrine"). The descriptions ARE the
    Janes/CSIS-desk voice contract for this file. If you find yourself
    rewriting one, stop — copy the verbatim text from this plan.
  </action>
  <verify>
    <automated>cd frontend && npm test -- junoDefenceCalendarDates --run</automated>
  </verify>
  <done>
    - `frontend/src/data/junoDefenceCalendarDates.ts` exists with type,
      dataset (29 + 3 + 1 = 33 entries), and `getDefenceDateBadges` export.
    - All 10 unit test cases pass.
    - Descriptions match verbatim text in this plan (no paraphrasing).
    - Air India (Jun 23) and Parliament Hill (Oct 22) are absent from the dataset.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Render badge in DayCell + cross-tenant isolation tests</name>
  <files>
    frontend/src/components/calendar/DayCell.tsx
    frontend/src/components/calendar/__tests__/DayCell.test.tsx
  </files>
  <behavior>
    New component-level tests added to existing `DayCell.test.tsx` (do NOT
    delete or modify the 7 existing tests — they all must still pass):

    1. **Juno + matching date → badge renders.** Pass `companyId: 'juno'`,
       `date: new Date(2026, 10, 11)` (Nov 11). Expect a DOM node with text
       content "Remembrance Day". It should use a muted token class
       (assert `text-zinc-500` substring is present on the badge element OR
       its container — pick whichever matches your implementation).

    2. **Seva + matching date → badge does NOT render** (D-10 invariant).
       Same date (Nov 11 2026), `companyId: 'seva'`. Query for "Remembrance Day"
       text using `screen.queryByText` — expect `null`.

    3. **Juno + non-matching date → badge slot is absent** (not an empty div).
       Pass `companyId: 'juno'`, `date: new Date(2026, 2, 15)` (Mar 15, no
       defence date). Assert no element with `data-testid="defence-badge"`
       (or equivalent stable selector you add) exists.

    4. **Priority ordering — Nov 8 shows the fixed entry, not the range.**
       Pass `companyId: 'juno'`, `date: new Date(2026, 10, 8)` (Nov 8). The
       rendered badge text should be "Indigenous Veterans Day", NOT "Veterans' Week".
       Use `screen.queryByText('Indigenous Veterans Day')` truthy AND
       `screen.queryByText('Veterans' Week')` null.
  </behavior>
  <action>
    **Step A — Extend the test file FIRST.** Add the 4 new tests to
    `frontend/src/components/calendar/__tests__/DayCell.test.tsx` inside the
    existing `describe('DayCell auto-save branches', ...)` block (or a new
    nested `describe('DayCell defence badge', ...)` — your call; keep file
    cohesive). Run `npm test -- DayCell --run` — expect RED on the new tests.

    **Step B — Modify `DayCell.tsx`** (per integration_points: gate via the
    `companyId` prop, which DayCell already receives; do NOT introduce
    `useCompanyBrand` here — the prop pattern is the established Phase 6
    contract and avoids unnecessary hook coupling):

    1. Add an import at the top:
       ```typescript
       import { getDefenceDateBadges } from '@/data/junoDefenceCalendarDates'
       ```

    2. Inside the component body (after `const dayLabel = ...` / `const dayNumber = ...`,
       before the `return`), compute the badge:

       ```typescript
       // Phase-13 + quick-260520-srt: defence-history badge slot.
       // Tenant-gated to Juno via the existing companyId prop (NOT useCompanyBrand
       // — DayCell receives companyId from WeeklyGrid, matching the Phase 6
       // prop-passing contract). Seva calendar must render byte-identically
       // to its pre-quick-260520-srt output (v3.0 D-10 invariant).
       const defenceBadges = companyId === 'juno'
         ? getDefenceDateBadges(date.getFullYear(), date.getMonth() + 1, date.getDate())
         : []
       const defenceBadge = defenceBadges[0] ?? null  // priority: fixed > movable > range (already ordered by lookup)
       ```

    3. Insert the badge slot in the JSX **between** the day-header `<div>` and
       the `<textarea>`. When `defenceBadge === null`, render NOTHING (use
       short-circuit, not an empty `<div>`):

       ```tsx
       {defenceBadge && (
         <div
           data-testid="defence-badge"
           className="mb-1 text-[10px] uppercase tracking-wide text-zinc-500 truncate"
           title={defenceBadge.description}
         >
           {defenceBadge.name}
         </div>
       )}
       ```

       Notes on classes:
       - `text-zinc-500` matches the existing day-label muted token used 6 lines above.
       - `text-[10px]` keeps the badge smaller than the day label (`text-xs` = 12px) so it doesn't compete.
       - `uppercase tracking-wide` matches the day-label visual rhythm.
       - `truncate` prevents long names ("Canadian Women's Army Corps Anniversary") from breaking the cell layout.
       - `mb-1` adds breathing room before the textarea.
       - **Do NOT use `bg-brand-accent` or any Juno-blue color** — informational, not branded (operator decision).
       - The `title={description}` is a native browser tooltip — costs ~0 bytes and gives the operator hover context. Tooltips are listed as out of scope for a *styled* tooltip component, but a native `title` attribute is acceptable since it's a free byproduct of the data shape already including `description`. If the operator prefers strict scope adherence, remove the `title` attribute — verify in checkpoint.

    4. **Crucial:** Do NOT modify any other behavior in DayCell. The 7 existing
       tests (auto-save branches + today highlight) must continue to pass
       unchanged. Specifically:
       - Do NOT change `companyId` typing or prop position.
       - Do NOT alter the textarea's `aria-label`, `placeholder`, or className.
       - Do NOT change the outer wrapper's `data-testid` format.
       - Do NOT change the today-highlight ring/bg classes.

    **Step C — Run all DayCell tests, expect GREEN.**
    ```
    cd frontend && npm test -- DayCell --run
    ```
    Confirm: 7 existing + 4 new = 11 passing.

    **Step D — Run the full frontend suite for regression confirmation:**
    ```
    cd frontend && npm test -- --run
    ```
    Expect: 181 existing + 10 new (Task 1) + 4 new (Task 2) = 195 passing.
    (Or however the count lands — the key invariant is "no existing test
    regresses, all new tests pass".)

    **Verbal cross-tenant isolation re-check** (D-10 audit):
    `git diff frontend/src/` should show ZERO modifications under any path
    that the Seva-only calendar reaches. The only edits should be:
    - `frontend/src/data/junoDefenceCalendarDates.ts` (NEW — Juno-named, Juno-scoped)
    - `frontend/src/data/__tests__/junoDefenceCalendarDates.test.ts` (NEW)
    - `frontend/src/components/calendar/DayCell.tsx` (MODIFIED — shared component, but the new logic is gated `companyId === 'juno'` so Seva path is logically identical)
    - `frontend/src/components/calendar/__tests__/DayCell.test.tsx` (MODIFIED — new tests appended, existing unchanged)

    DayCell is a SHARED component (Phase 9 D-08 single-component precedent —
    confirmed in DayCell's docstring at line 21–40). The "byte-identical Seva"
    invariant is preserved by the runtime gate, not by file-touch avoidance.
    This is exactly the Phase 9 contract.
  </action>
  <verify>
    <automated>cd frontend && npm test -- --run</automated>
  </verify>
  <done>
    - `DayCell.tsx` renders the badge above the textarea when `companyId === 'juno'` AND a match exists.
    - Seva path renders no badge for any date (cross-tenant isolation test green).
    - Priority ordering enforced at the renderer level (`defenceBadges[0]`) — Nov 8 shows Indigenous Veterans Day, not Veterans' Week.
    - All 7 existing DayCell tests still pass.
    - All 4 new DayCell tests pass.
    - Full frontend suite green (no regression).
    - Badge styling uses muted `text-zinc-500` (not `bg-brand-accent`).
  </done>
</task>

</tasks>

<verification>
**Phase-level checks (executor confirms all):**

1. `cd frontend && npm test -- --run` — all tests pass (181 prior + 10 + 4 = ~195).
2. `cd frontend && npm run build` — production build succeeds with no TS errors.
3. **Manual smoke test (executor performs in dev server):**
   - Start dev server, navigate to `/juno/calendar`, navigate to a week containing Nov 11 2026 — confirm "REMEMBRANCE DAY" badge renders above the textarea on Nov 11.
   - Navigate to a week containing Nov 8 2026 — confirm "INDIGENOUS VETERANS DAY" (NOT "Veterans' Week") renders. Then Nov 7 — confirm "VETERANS' WEEK" renders (fallback).
   - Switch to `/seva/calendar` on the same week — confirm NO badges render anywhere.
4. **Tone audit (executor scans the dataset file before commit):**
   ```
   grep -iE "(heroic|glorious|smashed|annihilated|crushed|epic|brutal|how to|tactical|operational|doctrine)" frontend/src/data/junoDefenceCalendarDates.ts
   ```
   Expected: ZERO matches. If any match found, the description has drifted
   from the verbatim text in this plan — restore from the plan.
5. **Omission audit:**
   ```
   grep -iE "(air india|parliament hill|cirillo|nathan)" frontend/src/data/junoDefenceCalendarDates.ts
   ```
   Expected: ZERO matches.
</verification>

<success_criteria>
- Operator opens `/juno/calendar` on any week containing one of the 33 commemorations and sees a subdued muted badge above the day cell content showing the event name.
- Operator opens `/seva/calendar` on the same week and sees no badges (D-10 byte-identical contract intact).
- On Nov 8, the badge reads "Indigenous Veterans Day" (fixed wins over range).
- On Nov 5/6/7/9/10, the badge reads "Veterans' Week" (range fallback).
- Dataset descriptions remain sober/commemorative — no celebratory or operational language (Phase 10 D-01 anti-tactical clause preserved).
- All existing 181 frontend tests still pass; ~14 new tests added and passing.
- Single atomic commit per the operator's commit_strategy (executor will craft the message from the suggested template in the planning context).
</success_criteria>

<output>
After completion, create `.planning/quick/260520-srt-add-canadian-defence-history-date-badges/260520-srt-SUMMARY.md`
summarizing: files added/modified, tests added, any deviations from the plan,
and a confirmation that both the tone audit and omission audit greps returned empty.
</output>
