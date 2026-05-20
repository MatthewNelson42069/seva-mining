# Phase 14: Juno Content Calendar (Tab 2) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `14-CONTEXT.md` — this log preserves the alternatives considered.

**Date:** 2026-05-20
**Phase:** 14-juno-content-calendar
**Areas discussed:** Short-circuit removal scope, LLM-assist drafting, Empty-state + copy, Cross-tenant isolation test scope

---

## Short-Circuit Removal Scope

### Q1: How should we remove the Juno short-circuit at ContentCalendarPage.tsx:42-54?

| Option | Description | Selected |
|--------|-------------|----------|
| Delete the block entirely | (Recommended) Remove lines 42-54 verbatim. The if-block was Phase 9 D-09 scaffolding; its job is done. WeeklyGrid + hooks already handle Juno via existing companyId plumbing. | ✓ |
| Replace with shared empty-state component | Replace 4-line block with reusable `<EmptyWeekState />`. Scope creep risk; Seva's empty-state lives at DayCell level, not page level. | |
| Keep block, flip condition to always-false | Comment out / `if (false)`. Worst of both worlds. | |

**User's choice:** Delete the block entirely
**Notes:** Decision captured as D-01. Includes deletion of the explanatory comment block at lines 42-45 (Phase 9 D-09 rationale no longer needed once the gate is lifted).

---

## LLM-Assist Drafting

### Q2: Should Phase 14 wire LLM-assist drafting into the Juno (or Seva) calendar?

| Option | Description | Selected |
|--------|-------------|----------|
| No — defer entirely | (Recommended) Scope to short-circuit removal + tests only. Seva calendar has been paper-planner-only since v2.1 Phase 6; introducing Juno-only LLM-assist creates tenant asymmetry. | ✓ |
| Yes — Juno-only LLM-assist | "Suggest content" button per day cell calling Sonnet 4.6 with Janes/CSIS voice. Significant scope expansion; creates asymmetry. | |
| Yes — both tenants get LLM-assist | Suggest button for both with tenant-aware prompts. Largest scope expansion; would justify own phase. | |

**User's choice:** No — defer entirely
**Notes:** Decision captured as D-02. Documented as deferred polish; can become its own phase shared by both tenants if operator interest emerges post-v3.1.

---

## Empty-State + Copy

### Q3: Empty-state pattern for Juno calendar (and Seva, if symmetric)

| Option | Description | Selected |
|--------|-------------|----------|
| Match Seva — em-dash placeholder only | (Recommended) No page-level banner. Each empty DayCell shows '—' placeholder (existing Seva behavior). Zero asymmetry; zero Seva regression. JCAL-01 spirit satisfied (user sees the calendar grid + em-dash signals "type here"). | ✓ |
| Add banner to both tenants | Banner above WeeklyGrid when week has zero rows. Same copy both tenants. Changes Seva visible behavior — minor regression risk. | |
| Tenant-aware: Juno gets banner, Seva keeps em-dash | Only Juno shows banner. Creates per-tenant asymmetry; violates v3.0 D-08 single-component-many-configs principle slightly. | |

**User's choice:** Match Seva — em-dash placeholder only
**Notes:** Decision captured as D-03. Implication captured as D-06 — JCAL-01 wording relaxed during planning from "No content planned for this week..." banner copy to "matches Seva em-dash placeholder pattern."

---

## Cross-Tenant Isolation Test Scope

### Q4a: Frontend isolation test coverage

| Option | Description | Selected |
|--------|-------------|----------|
| RTL + TanStack Query key assertion | (Recommended) New ContentCalendarPage.test.tsx mounts at /juno/calendar then /seva/calendar; asserts separate query keys (['calendar', 'juno', ...] vs ['calendar', 'seva', ...]); per-tenant data doesn't bleed via QueryClient inspection. | ✓ |
| Lightweight render-test only | Just assert /juno/calendar renders WeeklyGrid (no short-circuit). Doesn't deeply test query-key isolation. | |
| Skip frontend isolation test | Trust existing useCalendar/useCalendarMutations Phase 9 tests. | |

**User's choice:** RTL + TanStack Query key assertion
**Notes:** Decision captured as D-04. New file: `frontend/src/pages/__tests__/ContentCalendarPage.test.tsx`.

### Q4b: Backend isolation test coverage (JCAL-05 — 404 on cross-tenant mutate)

| Option | Description | Selected |
|--------|-------------|----------|
| Pytest with both tenants | (Recommended) New test_calendar_cross_tenant.py — create Seva row via /api/seva/calendar, attempt PATCH /api/juno/calendar/{seva_uuid}, assert 404 (NOT 403). Per JCAL-05 "tenant existence isolation" contract. | ✓ |
| Trust existing v3.0 Phase 9 isolation tests | Phase 9 added cross-tenant isolation for summaries. Trust pattern applies to calendar. | |

**User's choice:** Pytest with both tenants
**Notes:** Decision captured as D-05. New file: `backend/tests/test_calendar_cross_tenant.py`. Tests both directions (Seva UUID via /api/juno/ → 404; Juno UUID via /api/seva/ → 404).

---

## Claude's Discretion

- Exact file location for the new frontend test — `__tests__/ContentCalendarPage.test.tsx` is the standard pattern; planner picks if it should sit in `pages/__tests__/` or `__tests__/pages/`.
- Backend test file naming — `test_calendar_cross_tenant.py` vs extending `test_calendar.py`. Planner picks based on existing module organization.
- Whether to ship a single plan with 3 tasks (delete + FE test + BE test) or 2 plans (delete + FE test ; BE test). Phase 14's tiny scope makes single-plan likely cleaner; planner decides.
- Whether `/gsd:ui-phase 14` is run at all. Phase 14 introduces no new visual surfaces (Phase 13's CSS-token cascade automatically applies Juno navy to any `--color-brand-accent*` consumer inside the calendar). UI-SPEC would mostly say "use existing patterns." Operator may skip ui-phase and go directly to plan-phase. Documented in CONTEXT `<code_context>` Integration Points.

## Deferred Ideas

- LLM-assist drafting (Janes/CSIS voice on a "Suggest content" button) — could become its own phase shared by both tenants.
- Page-level empty-state banner — would need its own discuss-phase round if reconsidered.
- Calendar ↔ Sweeper cross-pollination (e.g., "this Monday thread matches a viral story") — interesting future feature.
- Per-week notes / weekly theme field above the 7 day cells.
- Mobile-responsive header collapse — desktop-only constraint preserved.
