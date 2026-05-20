# Phase 14: Juno Content Calendar (Tab 2) - Context

**Gathered:** 2026-05-20
**Status:** Ready for planning (UI design contract may or may not be needed — see "Domain" below)

<domain>
## Phase Boundary

Make `/juno/calendar` functional by removing the deliberate Phase 9 D-09 short-circuit at `frontend/src/pages/ContentCalendarPage.tsx:42-54` that gates the page behind a "Coming in v3.1" placeholder. After this phase: Juno users see the same weekly Mon-Sun paper-planner grid Seva users see; CRUD against `/api/{company}/calendar/*` works with row-level `company_id='juno'` enforcement; cross-tenant isolation is verified via a frontend RTL test + a backend pytest. Phase 14 makes ZERO Seva-side changes — D-09 byte-identical zero-regression contract from v3.0 carries forward unchanged.

**Critical scope insight discovered during discuss-phase codebase scout:** The vast majority of Phase 14's claimed work is ALREADY DONE by v2.1 Phase 6 + v3.0 Phase 9. The frontend `useCalendar` + `useCalendarMutations` hooks already accept `companyId: CompanyId`, key TanStack queries on `queryKeys.calendar(companyId, ...)`, and route to `/api/{company}/calendar/*`. The backend router at `backend/app/routers/calendar.py` already uses `Depends(get_current_company)` on every endpoint + has row-level defence-in-depth (UNIQUE(company_id, date) from Alembic 0013 + `company_id` injected from URL). The only thing blocking `/juno/calendar` from working is the deliberate Phase 9 placeholder. Phase 14 lifts that gate + verifies the existing scaffolding actually works end-to-end for Juno.

**In scope (~30-50 lines of code + 2 new test files):**
- Delete the 13-line short-circuit block at `ContentCalendarPage.tsx:42-54` (lines 42-54 verbatim; the `if (companyId === 'juno') { return <placeholder /> }` block)
- New frontend test: `frontend/src/pages/__tests__/ContentCalendarPage.test.tsx` (RTL + TanStack Query key isolation assertion)
- New backend test: `backend/tests/test_calendar_cross_tenant.py` (POST as Seva, attempt PATCH via /api/juno/, assert 404)
- Update JCAL-01 wording in REQUIREMENTS.md (during planning) to reflect "matches Seva em-dash placeholder pattern" instead of the literal "No content planned..." banner copy (which would create asymmetry)

**Out of scope:**
- **LLM-assist drafting** — no "Suggest content" button or any Sonnet/Haiku call from the calendar page. Defence-aware drafting prompts mentioned in ROADMAP as optional → deferred entirely. Preserves paper-planner-only pattern from v2.1 Phase 6 (Seva-parity).
- **Page-level empty-state banner** — JCAL-01 copy ("No content planned...") not added. Em-dash per-cell placeholder is the empty-state pattern.
- **Any Seva-side changes** — D-09 byte-identical contract. AppHeader, WeeklyGrid, DayCell, WeekNav, useCalendar, useCalendarMutations, backend router — all untouched in this phase. Only ContentCalendarPage.tsx is modified.
- **Backend schema changes** — Alembic 0013 + 0014 already established the multi-tenant constraint. No new migrations.
- **API client changes** — `frontend/src/api/calendar.ts` already accepts companyId and routes to `/api/{company}/calendar/*`. No client changes.
- **TENANT-VISITED-v31-redux** — already closed in Phase 13 D-08c.
- **Mobile-responsive treatment** — desktop-only constraint preserved.

</domain>

<decisions>
## Implementation Decisions

### Short-Circuit Removal (BRAND-05-adjacent, JCAL-01..04)

- **D-01 Delete short-circuit block verbatim.** Lines 42-54 of `frontend/src/pages/ContentCalendarPage.tsx` (the `if (companyId === 'juno') { return <placeholder> }` block including the surrounding comment) are removed entirely. Existing `<WeeklyGrid companyId={companyId} weekAnchor={weekAnchor} />` at line 64 takes over — it already accepts companyId and routes to `/api/juno/calendar/*` via the existing hooks. NOT replaced with an `<EmptyWeekState />` wrapper or `if (false)` dead-code marker.
- **D-07 No Seva-side changes.** D-09 byte-identical regression contract from v3.0 Phase 9 carries forward. Existing AppHeader / WeeklyGrid / DayCell / WeekNav / useCalendar / useCalendarMutations / backend router untouched. Phase 14's only modified production file is `ContentCalendarPage.tsx`.

### LLM-Assist (JCAL deferred)

- **D-02 No LLM-assist drafting in Phase 14.** ROADMAP mentioned "defence-aware drafting prompts (Janes/CSIS voice + anti-tactical clause)" as an *optional* feature; the deliberate scope decision is to defer it entirely. Rationale: (a) Seva calendar has been paper-planner-only since v2.1 Phase 6 — introducing Juno-only LLM-assist creates tenant asymmetry, (b) if LLM-assist becomes desirable later, it's a separate phase shared by both tenants (or one tenant first as A/B test), (c) Phase 14 stays narrow → faster ship + lower risk. If a future operator request surfaces LLM-assist desire, that's its own phase with separate UI-SPEC + discuss-phase.

### Empty-State Pattern (JCAL-01)

- **D-03 Match Seva em-dash placeholder pattern. No page-level banner.** Each empty `DayCell` already shows `placeholder="—"` (em-dash) inside its textarea (see `DayCell.tsx:121`). The Mon/Tue/Wed/... grid IS the visible UI; em-dashes signal "empty cell, click to type." JCAL-01's literal banner copy ("No content planned for this week — start typing in any day to plan ahead.") would either (a) add a tenant-asymmetric banner to Juno only, or (b) change Seva's visible behavior (D-09 regression). Both bad. Pragmatic resolution: the em-dash pattern satisfies the SPIRIT of JCAL-01 (user understands the calendar is empty + knows how to start) without touching Seva or creating asymmetry.
- **D-06 Update JCAL-01 wording during planning.** The literal "Empty state copy: 'No content planned for this week...'" in REQUIREMENTS.md JCAL-01 is relaxed to: "User opens `/juno/calendar` and sees the same weekly Mon-Sun paper-planner grid Seva users see — direct-edit textarea per day with em-dash placeholder when empty, current-week highlighted." Planner edits REQUIREMENTS.md as part of Phase 14's task list with a `(D-06)` annotation.

### Test Coverage (JCAL-03, JCAL-05)

- **D-04 Frontend isolation test.** New file `frontend/src/pages/__tests__/ContentCalendarPage.test.tsx` (or extend existing `__tests__/` pattern). Test mounts the page at `/juno/calendar`, queries the QueryClient cache, asserts key `['calendar', 'juno', <start>, <end>]` exists and is keyed separately from any Seva-side key. Then re-mounts at `/seva/calendar` and asserts the Seva key exists with no Juno data bleeding through. Behaviorally tests JCAL-03's cross-tenant isolation contract via the TanStack Query primary mechanism (per-tenant query key).
- **D-05 Backend isolation test.** New file `backend/tests/test_calendar_cross_tenant.py` (or extend the existing calendar-test module). Test creates a calendar_items row via `POST /api/seva/calendar` with date D, captures the returned UUID, then attempts `PATCH /api/juno/calendar/{seva_uuid}` with body `{notes_md: "stolen"}`. Asserts response status 404 (per JCAL-05 "tenant existence isolation"). Also tests the inverse (Juno UUID via /api/seva/ → 404). Validates the row-level defence-in-depth at `routers/calendar.py:135` works end-to-end.

### Folded Todos
None — no pending todos matched Phase 14 scope at cross-reference time.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents (planner, executor) MUST read these before planning or implementing.**

### Phase 14 Roadmap Source
- `.planning/ROADMAP.md` §"Phase 14: Juno Content Calendar (Tab 2)" (lines ~225-290 in current state — full phase block with goal, depends-on, inputs, outputs, success criteria, complexity, hard parts P1..P5)
- `.planning/REQUIREMENTS.md` §"Juno Content Calendar (JCAL)" — atomic acceptance criteria for JCAL-01..05. NOTE: JCAL-01 wording will be relaxed during planning per D-06.

### Project-Level Constraints
- `.planning/PROJECT.md` §"Current Milestone: v3.1" §"Hard parts the roadmap addresses" item 1 ("Juno Calendar port without breaking Seva Calendar")
- `CLAUDE.md` — no direct calendar guidelines; multi-tenant patterns governed by v3.0 D-03 + v3.0 Phase 9 + v3.1 Phase 13 D-10

### v2.1 / v3.0 Patterns This Phase Relies On
- `.planning/milestones/v2.0-phases/` (or wherever v2.1 Phase 6 archive lives) — v2.1 Phase 6 CONTEXT for the original Seva Calendar implementation; reference for what `WeeklyGrid`/`DayCell`/`WeekNav`/`useCalendar` were designed to do
- `.planning/milestones/v3.0-phases/09-multi-tenant-foundation/09-CONTEXT.md` D-09 — the explicit Phase 9 short-circuit decision Phase 14 is lifting; comment at `ContentCalendarPage.tsx:42` references "CONTEXT D-09" inline
- `.planning/milestones/v3.0-phases/09-multi-tenant-foundation/09-CONTEXT.md` D-02 — AppHeader freeze-lift (mentioned for context only; not relevant to Phase 14's surface)

### Code-Level References (current state for the planner)
- `frontend/src/pages/ContentCalendarPage.tsx:42-54` — the short-circuit block to delete. Surrounding comment block (lines 42-45) explains the Phase 9 D-09 rationale; delete the comment + the `if` block together as one atomic edit.
- `frontend/src/pages/ContentCalendarPage.tsx:64` — `<WeeklyGrid companyId={companyId} weekAnchor={weekAnchor} />` takes over once the short-circuit is removed. No change needed at this line.
- `frontend/src/hooks/useCalendar.ts` — already multi-tenant (`companyId: CompanyId` parameter; `queryKeys.calendar(companyId, start, end)` key). No change.
- `frontend/src/hooks/useCalendarMutations.ts` — all 3 mutation hooks (create/update/delete) already multi-tenant. No change.
- `frontend/src/api/calendar.ts` — already routes `companyId` to `/api/{company}/calendar/*`. No change.
- `frontend/src/api/queryKeys.ts` — `queryKeys.calendar(companyId, start, end)` factory already keyed correctly. No change.
- `frontend/src/components/calendar/WeeklyGrid.tsx` — accepts `companyId` prop; renders 7 DayCells. No change.
- `frontend/src/components/calendar/DayCell.tsx:121` — `placeholder="—"` is Seva's em-dash empty-state. Phase 14 inherits this for Juno via WeeklyGrid → DayCell. No change.
- `backend/app/routers/calendar.py` — fully multi-tenant via `Depends(get_current_company)` on every endpoint + row-level defence-in-depth at line 135 (mutate-by-UUID against wrong tenant → 404). No change.
- `backend/app/queries/scoped.py` — `scoped_calendar_*()` helpers + CI grep gate (`scripts/verify-tenant-isolation.sh`) already enforce row-level scoping. No change.

### New Files Phase 14 Creates (for the planner's task list)
- `frontend/src/pages/__tests__/ContentCalendarPage.test.tsx` — NEW (D-04)
- `backend/tests/test_calendar_cross_tenant.py` — NEW (D-05)

### Files Phase 14 Modifies
- `frontend/src/pages/ContentCalendarPage.tsx` — delete short-circuit (D-01)
- `.planning/REQUIREMENTS.md` — relax JCAL-01 wording per D-06

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets (heavy reuse — Phase 14 leverages prior work extensively)
- **`WeeklyGrid` + `DayCell` + `WeekNav` components** — Already render correctly for Seva at `/seva/calendar`. Identical render path will work for `/juno/calendar` once the short-circuit is removed.
- **`useCalendar(companyId, start, end)` hook** — Already calls `getCalendar(companyId, start, end)` from `@/api/calendar` and keys on `queryKeys.calendar(companyId, start, end)`. Multi-tenant-ready.
- **`useCreateCalendarItem` / `useUpdateCalendarItem` / `useDeleteCalendarItem` hooks** — All 3 already accept `companyId` and route to `/api/{company}/calendar/*` with proper optimistic mutation + rollback semantics.
- **`backend/app/routers/calendar.py`** — All CRUD endpoints already use `Depends(get_current_company)` to inject `company_id` from URL prefix. Row-level scoping enforced via `UNIQUE(company_id, date)` from Alembic 0013.
- **`backend/app/queries/scoped.py`** — `scoped_calendar_*()` helpers ensure no raw `select(CalendarItem)` outside the helpers; CI grep gate from `scripts/verify-tenant-isolation.sh` already in place.

### Established Patterns
- **Per-tenant TanStack Query keying** — `queryKeys.calendar(companyId, start, end)` returns `['calendar', companyId, start, end]` 4-tuple. Cache isolation between tenants is automatic.
- **Backend row-level defence-in-depth** — Mutate-by-UUID with wrong tenant URL prefix returns 404, NOT 403 (per Phase 9 + Phase 14 D-05 contract — tenant existence isolation, NOT permission isolation).
- **`CompanyScopedRoute.tsx`** validates `:company` segment is in ACTIVE_COMPANIES (`'seva' | 'juno'`). Phase 14 inherits this validation for free; no extra guard needed in ContentCalendarPage.
- **Em-dash placeholder for empty DayCell** — established Seva pattern; Phase 14 inherits via WeeklyGrid (no per-Juno override).

### Integration Points
- **Wave-1 / single-task structure likely** — Phase 14's actual change surface is so small (one ~13-line deletion + 2 new test files) that it may not need multiple plans. Planner picks: single plan with 3 tasks vs 2 plans (one for the deletion+frontend-test, one for backend-test). No strong preference.
- **No new dependencies, no new env vars, no DB migration, no new routes** — Phase 14 is a "lift-the-gate" phase. The gate was deliberate (Phase 9 D-09) and the work it gated has since landed (multi-tenant scaffolding from Phase 9; defence-aware Juno daily summary from Phase 10; per-tenant Anthropic key from Phase 12; per-company branding from Phase 13).
- **UI design contract probably NOT needed** — Phase 14 doesn't introduce new visual surfaces. The visible UI is already designed (Seva's calendar at v2.1 Phase 6 + per-tenant branding from Phase 13's CSS-token cascade — Juno's navy palette will automatically apply to any `--color-brand-accent*`-using surface inside the calendar). The UI-SPEC researcher would mostly produce "use existing patterns" output. Planner can skip `/gsd:ui-phase 14` and go directly to plan-phase. (Documented for orchestrator visibility; final call is the operator's.)

</code_context>

<specifics>
## Specific Ideas

- **Exact deletion target** — `frontend/src/pages/ContentCalendarPage.tsx`, lines 42-54 inclusive (the comment block + the `if (companyId === 'juno')` block + its return + the closing brace). Verified by Read tool inspection during discuss-phase. The line right after (`return (` at line 56) opens the main render path that handles both tenants.
- **TanStack Query key assertion shape** — Test uses `queryClient.getQueryCache().findAll({ queryKey: ['calendar', 'juno'] })` (or `findAll({ predicate })`) to assert exactly one matching entry per tenant after navigation. Inverse assertion catches accidental cache poisoning.
- **Backend 404 assertion shape** — Test creates Seva row via `client.post('/api/seva/calendar', json={...})`, captures UUID, then `client.patch(f'/api/juno/calendar/{uuid}', json={...})` and `assert response.status_code == 404`. NOT 403; defence-in-depth treats wrong tenant as "row doesn't exist for this tenant." Same test inverts (Juno UUID via /api/seva/ → 404).
- **No banner copy in JCAL-01 means no companyBrandConfig schema extension** — Phase 13's `BrandConfig` interface stays unchanged. Empty-state copy is NOT a brand attribute; it lives in `DayCell.tsx` as a static `placeholder` prop. If a future banner is added, that would be the right time to extend the registry.

</specifics>

<deferred>
## Deferred Ideas

- **LLM-assist drafting** — Defence-aware "Suggest content for this day" button using Sonnet 4.6 + Janes/CSIS voice + anti-tactical clause. Out of scope per D-02. Could become its own phase shared by both tenants if operator surfaces interest after v3.1 ships. Not a v3.1 milestone deliverable.
- **Page-level empty-state banner** — JCAL-01's literal "No content planned..." banner copy. Out of scope per D-03. If reconsidered, would apply to both tenants (no asymmetry) and would need its own discuss-phase round (planner needs to know whether banner is per-week or per-no-rows-in-any-week, what triggers visibility, etc.).
- **Calendar virality compute** — Cross-pollination between calendar items + weekly viral sweeper (Phase 15) — e.g., "this thread you planned for Monday matches a viral story from last week's sweep." Interesting but firmly out of scope; future enhancement.
- **Per-week notes / weekly theme field** — Add a tenant-scoped weekly summary or theme field above the 7 day cells. Out of scope; Phase 14 is strictly "lift the gate."
- **Mobile-responsive header collapse** — Desktop-only constraint preserved.
- **Reviewed Todos (not folded)** — None reviewed; cross-reference returned 0 matches.

</deferred>

---

*Phase: 14-juno-content-calendar*
*Context gathered: 2026-05-20*
