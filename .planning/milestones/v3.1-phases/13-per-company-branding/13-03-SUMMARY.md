---
phase: 13-per-company-branding
plan: 03
subsystem: frontend-tests-and-visual-qa
tags: [branding, multi-tenant, tests, fowb, visual-qa, regression-gate, d10-branchlessness]
dependency-graph:
  requires:
    - "Wave 1 (13-01): companyBrandConfig registry + useCompanyBrand hook + favicon SVGs + CSS override + index.html title"
    - "Wave 2 (13-02): CompanyBrandEffect + AppHeader refactor + BareRootRedirect + App.tsx wiring"
    - "Phase 12 baseline test count (168/168) — Plan 13-03 regression target"
  provides:
    - "AppHeader.test.tsx extended with 2 Juno-default tests (Test File 1 rows 5+6)"
    - "AppHeader.brand.test.tsx (NEW) with 5 FOWB / dataset / title / favicon / cleanup tests (Test File 2)"
    - "D-10 branchlessness regression gate (2 grep commands, both 0 hits in non-test component files)"
    - "Operator visual QA sign-off ledger at 1440×900 — 10/10 items PASS"
    - "BRAND-04 (FOWB-free transition) closure — last BRAND requirement pending for Phase 13"
  affects:
    - "frontend/src/components/layout/__tests__/AppHeader.test.tsx (4 byte-identical Seva tests preserved + 2 new Juno tests appended)"
    - "frontend/src/components/layout/__tests__/AppHeader.brand.test.tsx (NEW — global side-effect surface tested in isolation)"
tech-stack:
  added: []
  patterns:
    - "Test isolation via separate file when global state mutated (dataset.company / document.title / link[rel=icon] pollute jsdom — isolating in AppHeader.brand.test.tsx keeps the simpler AppHeader.test.tsx clean)"
    - "Synchronous FOWB assertion: rerender() inside a single act() block with NO waitFor / NO act(async) — proves the brand flip is committed in one React render pass"
    - "Zustand mock supporting BOTH reactive useAppStore((s) => ...) AND non-reactive useAppStore.getState() call forms via Object.assign(fn, { getState: () => stub }) (required because useCompanyBrand uses reactive form and BareRootRedirect uses non-reactive form)"
    - "D-10 branchlessness grep gate as code-review contract (not yet CI-scripted — deferred per CONTEXT D-10; manual grep at code-review is the v3.1 contract)"
key-files:
  created:
    - frontend/src/components/layout/__tests__/AppHeader.brand.test.tsx
  modified:
    - frontend/src/components/layout/__tests__/AppHeader.test.tsx
decisions:
  - "Operator approved Phase 13 visual QA 2026-05-20 — Juno navy palette (oklch(0.58 0.14 245)) reads institutional defence; FOWB-free transitions verified manually at 1440×900 (all 6 MUST-PASS + all 4 SHOULD-PASS items confirmed)"
  - "vi.mock hoist-init bug auto-fixed inline during Task 2 — moving local helper above vi.mock factory reference (Rule 1 auto-fix; standard vitest hoisting quirk, not a plan deviation)"
  - "D-10 Gate B 1-hit quirk documented as registry-internal grep wording (frontend/src/hooks/useCompanyBrand.ts:26 — the resolution hook itself; semantic intent preserved like Wave 1/2 grep-wording-quirk precedent)"
  - "Phase 13 closure: 13-03 was the LAST plan in Phase 13. BRAND-01..05 all satisfied + TENANT-VISITED-v31-redux closed as D-08c opportunistic polish. Phase 13 ready for phase-level verifier."
metrics:
  duration_minutes: 35
  completed_date: "2026-05-20"
  tasks_completed: 4
  files_created: 1
  files_modified: 1
  tests_passing: "175/175 (Phase 12 baseline 168 + 7 new = 175 across 29 test files)"
---

# Phase 13 Plan 03: Per-company Branding Tests + Visual QA Summary

Locked in Phase 13's brand-resolution contract with three layers of verification: (1) unit tests — extended `AppHeader.test.tsx` with 2 Juno-default tests (preserving the 4 existing Seva tests byte-identically per D-09) and created `AppHeader.brand.test.tsx` with 5 FOWB / dataset / title / favicon / cleanup tests; (2) D-10 branchlessness grep gates plus full vitest regression and Vite production build; (3) operator visual QA at 1440×900 across the 10-item UI-SPEC checklist — operator approved all 6 MUST-PASS items plus all 4 SHOULD-PASS items. Phase 13 closes complete.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Extend AppHeader.test.tsx with 2 Juno-default tests (preserve 4 existing Seva tests byte-identically) | `9b3b24e` | `frontend/src/components/layout/__tests__/AppHeader.test.tsx` (MODIFIED — 2 tests appended; 4 existing tests unchanged) |
| 2 | Create AppHeader.brand.test.tsx with 5 FOWB / dataset / title / favicon / cleanup tests | `76a1903` | `frontend/src/components/layout/__tests__/AppHeader.brand.test.tsx` (NEW) |
| 3 | D-10 branchlessness grep gates + full vitest regression + Vite production build | verification-only (no commit) | (no file modifications) |
| 4 | Operator visual QA at 1440×900 (10-item checklist) — APPROVED | `412e272` (sign-off; no code change) | (no file modifications — operator sign-off recorded in commit message) |

## Test Additions (UI-SPEC Test Matrix)

### File 1: `AppHeader.test.tsx` — 4 byte-identical Seva tests + 2 new Juno tests

| # | Test name | Status |
|---|-----------|--------|
| 1 | `renders the "Seva Mining" wordmark text` | PASS (byte-identical — D-09) |
| 2 | `renders the amber "S" logo mark` | PASS (byte-identical — D-09) |
| 3 | `renders a "Log out" button` | PASS (byte-identical — D-09) |
| 4 | `clicking "Log out" calls clearToken and navigates to /login` | PASS (byte-identical — D-09) |
| 5 | `renders the "Juno Industries" wordmark and "J" mark when route is /juno` | NEW — PASS |
| 6 | `does NOT render the "Seva Mining" wordmark or "S" mark when route is /juno` | NEW — PASS |

### File 2: `AppHeader.brand.test.tsx` — 5 NEW global-side-effect tests

| # | Test name | Status |
|---|-----------|--------|
| 1 | `sets data-company="seva" on documentElement when route is /seva` | NEW — PASS |
| 2 | `sets data-company="juno" on documentElement when route is /juno` | NEW — PASS |
| 3 | `FOWB: route flip /seva -> /juno updates wordmark + dataset + title atomically in single act()` | NEW — PASS |
| 4 | `updates favicon link href on route change to /juno` | NEW — PASS |
| 5 | `cleanup on unmount reverts data-company to "seva" and title to "Seva Mining"` | NEW — PASS |

**FOWB test shape invariant honored:** `grep -E "await waitFor|act\(async" AppHeader.brand.test.tsx` returns 0 hits — proves the dataset + wordmark + mark + title flip in a single synchronous render commit.

## D-09 Byte-Identical Verification

The 4 original Seva tests in `AppHeader.test.tsx` (test names + bodies + `renderHeader()` helper + `mockNavigate` setup + `mockClearToken` setup + `vi.mock('react-router-dom', ...)` block + `vi.mock('@/stores', ...)` block + `beforeEach(() => { vi.clearAllMocks() })`) remained byte-identical pre/post Task 1. Only acceptable change was APPENDING the new `renderHeaderJuno()` helper + 2 new `it(...)` calls + a comment line marking the Phase 13 (BRAND-01, BRAND-03) section. D-09 zero-regression contract held.

## D-10 Branchlessness Grep Gate Results

**Gate A** (registry IS the only allowed branch — non-test files in `frontend/src/components/`):

```
grep -rEn "company === '(juno|seva)'" frontend/src/components/ --include="*.tsx" --include="*.ts" | grep -vE "(__tests__|\.test\.|\.spec\.)" | wc -l
```

Result: **0 hits** — PASS.

**Gate B** (broader sweep across `frontend/src`, excluding registry files):

```
grep -rEn "company === '(juno|seva)'" frontend/src --include="*.tsx" --include="*.ts" | grep -vE "(__tests__|\.test\.|\.spec\.|companyBrandConfig|companySectionConfig)" | wc -l
```

Result: **1 hit** at `frontend/src/hooks/useCompanyBrand.ts:26` — documented quirk, semantic intent preserved (see Deviations).

## Full Verification Run

| Check | Command | Result |
|-------|---------|--------|
| 1. Full vitest suite | `cd frontend && npm test -- --run` | **175/175 PASS** across 29 test files (Phase 12 baseline 168 + 7 new) |
| 2. AppHeader.test.tsx isolated | `cd frontend && npm test -- --run AppHeader.test.tsx` | 6/6 PASS (4 existing Seva + 2 new Juno) |
| 3. AppHeader.brand.test.tsx isolated | `cd frontend && npm test -- --run AppHeader.brand.test.tsx` | 5/5 PASS |
| 4. D-10 Gate A | `grep -rEn ... frontend/src/components/` filtered | 0 hits PASS |
| 5. D-10 Gate B | `grep -rEn ... frontend/src` filtered | 1 documented hit (Deviations) |
| 6. TypeScript clean | `cd frontend && npx tsc --noEmit` | exit 0 — no errors |
| 7. Vite production build | `cd frontend && npm run build` | exit 0 — clean |
| 8. Build assets present | `ls frontend/dist/brand/` | `seva.svg` + `juno.svg` both present |
| 9. Build HTML title | `grep '<title>Seva Mining</title>' frontend/dist/index.html` | present (1 hit) |

## Test Count Delta

- **Phase 12 baseline:** 28 test files, 168 tests passing (per Wave 2 SUMMARY metric)
- **Wave 3 additions:** +2 tests in `AppHeader.test.tsx` (Juno extension) + 5 tests in new `AppHeader.brand.test.tsx` = **+7 tests**
- **Post-Wave 3:** 29 test files, **175/175 tests passing** — zero regression, expected count hit exactly

## Operator Visual QA Ledger (1440×900) — APPROVED

Operator (Matt) reply at checkpoint: **"approved"** — blanket approval covering all 6 MUST-PASS items plus all 4 SHOULD-PASS items.

### MUST-PASS items (block release if any fail)

| # | Item | Result |
|---|------|--------|
| 1 | At `/seva/` — AppHeader shows amber square + "S" + "Seva Mining". Identical to v3.0 visual (D-09 zero regression). | PASS |
| 2 | At `/juno/` — AppHeader shows navy square + "J" + "Juno Industries". Navy reads as institutional (NOT bright royal, NOT cyan, NOT slate-grey). | PASS |
| 4 | Navigate `/seva/calendar` → click "Juno" in `CompanySwitcher`. NO flash of amber under Juno route during transition. Wordmark + brand-mark + switcher accent flip simultaneously. (BRAND-04 FOWB) | PASS |
| 5 | Browser tab title updates: `/seva/` → "Seva Mining"; `/juno/` → "Juno Industries". OS tab strip updates live. | PASS |
| 6 | Browser tab favicon updates: `/seva/` → amber-S; `/juno/` → navy-J. Distinguishable at 14-16px. | PASS |
| 7 | Bare `/` after visiting Juno last → redirects to `/juno`. After clearing localStorage → redirects to `/seva`. (TENANT-VISITED-v31-redux + BareRootRedirect default fallback) | PASS |

### SHOULD-PASS items (cosmetic; non-blocking)

| # | Item | Result |
|---|------|--------|
| 3 | At `/juno/` — `CompanySwitcher`'s active "Juno" button has navy outline + navy text + faint navy fill. Inactive "Seva" button has zinc-800 border + zinc-400 text. | PASS |
| 8 | At `/juno/calendar` (or `/juno/viral`) — v2.1 Phase 8 surfaces using `--color-brand-accent*` (`SectionBlock`, `SweeperCard` accents, etc.) render in navy AUTOMATICALLY via the CSS-var cascade. No file changes were made to those components. | PASS |
| 9 | At `/juno/` — keyboard-tab into `CompanySwitcher`. Focus ring is navy (not amber). Inverse check at `/seva/` — focus ring is amber. | PASS |
| 10 | Log out from `/juno/` to `/login`. Login page title is "Seva Mining" (default cleanup), not "Juno Industries". Re-login as Seva — no flash of navy on `/seva/` first paint. | PASS |

**Net:** 10/10 items confirmed PASS. No fix cycle needed. Phase 13 visual aesthetic + FOWB-free behavior locked in.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] vi.mock hoist-init bug auto-fixed inline in Task 2**

- **Found during:** Task 2 initial test run
- **Issue:** `vi.mock()` is hoisted by vitest to the top of the module before any `import` or `const` declarations execute. Initial draft of `AppHeader.brand.test.tsx` defined the Zustand mock state stub as a local const above the `vi.mock('@/stores', ...)` call expecting normal top-to-bottom evaluation; vitest's hoist-init pass evaluated the mock factory before the local const was defined, causing a `ReferenceError` on first test run.
- **Fix:** Inlined the state stub directly inside the `vi.mock('@/stores', ...)` factory closure (the standard vitest hoisting workaround). Mock factory is self-contained; no out-of-scope references.
- **Files modified:** `frontend/src/components/layout/__tests__/AppHeader.brand.test.tsx` (single file, single mock block)
- **Commit:** included in Task 2 commit `76a1903`
- **Type:** Standard vitest hoisting quirk, not a plan-content issue. Recorded for Rule-1 documentation hygiene.

### Verification-command quirks (NOT code deviations)

**2. [Wave 1/2 precedent — grep-wording-quirk] D-10 Gate B reports 1 hit in `useCompanyBrand.ts:26`**

- **Found during:** Task 3 D-10 grep gate run
- **Detail:** The broader sweep (Gate B) catches `company === '...'` literals INSIDE the registry-resolution hook (`frontend/src/hooks/useCompanyBrand.ts:26`). This is the hook that PROVIDES branchlessness to consumers — its internal logic must validate the URL `:company` segment is one of the known tenants before indexing the registry, which inherently uses `company === 'seva' || company === 'juno'` shape.
- **Why allowed:** The D-10 contract per CONTEXT D-10 is "no `company === 'juno'` branches in `frontend/src/components/`" — Gate A (the production-relevant gate) covers `frontend/src/components/` and returns 0 hits. Gate B's broader sweep was specified with `--exclude` for registry files (`companyBrandConfig|companySectionConfig`) but did not exclude the resolution hook because the hook's job IS to be the single internal branch site that consumers depend on.
- **Precedent:** Mirrors Wave 1 SUMMARY's "Acceptance-criterion grep wording" deviation and Wave 2 SUMMARY's "[Rule 3 — Acceptance-gate quirk] AppHeader.tsx inline comment reworded" deviation. The grep tool's literal-substring scope is incidentally broader than the D-10 contract; the contract is honored at the *semantic* level (no per-tenant branching inside consumer components).
- **No code adjustment needed.** Future refinement: planner can extend the Gate B exclude pattern to include `useCompanyBrand` (1-token addition) when formalizing the gate as a CI script in a future phase.

### Out-of-scope discoveries logged

None new this plan. The 15 pre-existing test-file lint errors logged to `deferred-items.md` in Plan 13-01 remain unaddressed (out of scope for Plan 13-03; a future hygiene phase can address).

## Authentication Gates

None — Plan 13-03 is purely test additions, grep gates, and operator visual evaluation. No API calls, secrets, or external services.

## Known Stubs

None. Both new tests are fully populated:
- All 6 tests in `AppHeader.test.tsx` (4 existing + 2 new Juno) render real components mounted in real `<MemoryRouter>` + `<QueryClientProvider>` and assert on real DOM text matches.
- All 5 tests in `AppHeader.brand.test.tsx` mount real `<CompanyBrandEffect />` + `<AppHeader />` and assert on real jsdom global state (`document.documentElement.dataset.company`, `document.title`, `link[rel='icon']` href) — no placeholder assertions, no `it.todo`, no skipped tests.

## Phase 13 Closure Note

**13-03 was the LAST plan in Phase 13.** All 5 BRAND requirements (BRAND-01 wordmark, BRAND-02 color, BRAND-03 mark + favicon, BRAND-04 FOWB-free transition, BRAND-05 branchlessness contract) are satisfied — BRAND-01/02/03/05 were already complete after Wave 2 + operator-modified REQUIREMENTS.md; BRAND-04 (FOWB-free transition) is closed by this plan's operator visual QA confirmation of item 4 (Seva → Juno transition with no flash) PLUS the synchronous FOWB unit test in `AppHeader.brand.test.tsx` test 3.

Additionally, **TENANT-VISITED-v31-redux** (the v3.0 carry-over "last-visited tenant for bare `/` redirect") closed as **D-08c opportunistic polish** during Plan 13-02 via `BareRootRedirect.tsx` consuming `useAppStore.getState().lastVisitedCompany`, confirmed by operator visual QA item 7.

Phase 13 is ready for the phase-level verifier:
- 5/5 BRAND requirements satisfied
- 1/1 opportunistic polish item (TENANT-VISITED-v31-redux) closed
- 175/175 frontend tests passing (zero regression from Phase 12 baseline of 168)
- TypeScript + Vite build clean
- Operator visual QA 10/10 PASS at 1440×900
- D-10 grep Gate A: 0 hits in production components
- D-09 byte-identical Seva contract preserved

## Self-Check: PASSED

- File created exists on disk: `/Users/matthewnelson/seva-mining/frontend/src/components/layout/__tests__/AppHeader.brand.test.tsx` — FOUND.
- File modified exists on disk: `/Users/matthewnelson/seva-mining/frontend/src/components/layout/__tests__/AppHeader.test.tsx` — FOUND.
- Commits exist in git log:
  - `9b3b24e` (Task 1) — FOUND
  - `76a1903` (Task 2) — FOUND
  - `412e272` (Task 4 sign-off) — FOUND
- Frontend tests: 175/175 PASS (29 test files; Phase 12 baseline 168 + 7 new).
- TypeScript: clean.
- Vite build: clean; `dist/brand/seva.svg` + `dist/brand/juno.svg` present; `dist/index.html` `<title>Seva Mining</title>` present.
- D-10 Gate A: 0 hits in `frontend/src/components/`.
- D-10 Gate B: 1 documented quirk in `useCompanyBrand.ts:26` (registry resolution hook itself — semantic intent preserved per Wave 1/2 precedent).
- Operator visual QA: all 6 MUST-PASS + all 4 SHOULD-PASS confirmed via blanket "approved" reply.
- BRAND-04 (last pending BRAND requirement) closed. Phase 13 ready for phase-level verifier.
