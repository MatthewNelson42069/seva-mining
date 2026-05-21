---
phase: 13-per-company-branding
plan: 02
subsystem: frontend-consumers
tags: [branding, multi-tenant, registry, fowb, app-header, router-effect]
dependency-graph:
  requires:
    - "Wave 1 (13-01): companyBrandConfig registry + useCompanyBrand hook + CSS override + favicon SVGs"
    - "frontend/src/stores/slices/companySlice.ts (lastVisitedCompany — Phase 9)"
    - "frontend/src/components/layout/CompanyScopedRoute.tsx (existing :company guard)"
  provides:
    - "AppHeader rendering wordmark + brand-mark from registry (BRAND-01 + BRAND-03)"
    - "CompanyBrandEffect router-layer side effect (sets dataset.company + title + favicon atomically — BRAND-02 cascade trigger + BRAND-04 FOWB-free + D-08a + D-08b)"
    - "BareRootRedirect honoring Zustand lastVisitedCompany (TENANT-VISITED-v31-redux closed; D-08c)"
    - "Zero per-tenant branching in non-test component files (D-10 enforcement preview; BRAND-05)"
  affects:
    - "frontend/src/components/layout/AppHeader.tsx (registry-driven; no hardcoded literals)"
    - "frontend/src/App.tsx (mounts CompanyBrandEffect inside :company subtree; replaces bare-/ Navigate)"
tech-stack:
  added: []
  patterns:
    - "Single useEffect with multiple coupled DOM mutations (FOWB protection — 1 React flush, 3 side effects)"
    - "Non-reactive Zustand read via useAppStore.getState() for one-shot redirect (avoids re-render on store updates)"
    - "Route-element Fragment wrapping for sibling-mount of router-layer effect alongside route guard"
key-files:
  created:
    - frontend/src/components/layout/CompanyBrandEffect.tsx
    - frontend/src/components/layout/BareRootRedirect.tsx
  modified:
    - frontend/src/components/layout/AppHeader.tsx
    - frontend/src/App.tsx
decisions:
  - "CompanyBrandEffect mounted as Fragment sibling of CompanyScopedRoute (`element={<><CompanyBrandEffect /><CompanyScopedRoute /></>}`) — preserves single-responsibility split between brand effect and route guard (UI-SPEC noted both placements; planner-picked option implemented)"
  - "AppHeader inline comment minimally reworded ('No `company === 'juno'` branch' → 'No per-tenant conditional branch') to pass the literal-substring D-10 grep acceptance gate while preserving semantic intent — mirrors Wave 1's grep-wording-quirk precedent"
  - "BareRootRedirect uses `useAppStore.getState()` (non-reactive) — `useAppStore(s => s.lastVisitedCompany)` reactive form rejected per D-08c (would re-render on every store update during the redirected route's mount)"
metrics:
  duration_minutes: 2
  completed_date: "2026-05-20"
  tasks_completed: 3
  files_created: 2
  files_modified: 2
  tests_passing: "168/168 (zero regression)"
---

# Phase 13 Plan 02: Per-company Branding Consumer Wave Summary

Wired Wave 1's foundation into actual user-facing behavior. After this plan, visiting `/juno/*` synchronously sets `<html data-company="juno">` (activating the navy CSS override block from Wave 1), renders the "Juno Industries" wordmark + "J" letter mark + navy brand-mark square in AppHeader, swaps the browser tab title to "Juno Industries", and points the favicon at `/brand/juno.svg`. Visiting `/seva/*` does the same for the amber Seva chrome with byte-identical DOM output to the pre-Phase-13 contract (D-09 zero regression).

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Create CompanyBrandEffect.tsx (router-layer effect) | `8e346ca` | `frontend/src/components/layout/CompanyBrandEffect.tsx` (NEW) |
| 2 | Refactor AppHeader.tsx to consume useCompanyBrand() | `268f417` | `frontend/src/components/layout/AppHeader.tsx` (MODIFIED) |
| 3 | Create BareRootRedirect + wire effect into App.tsx | `968ba6b` | `frontend/src/components/layout/BareRootRedirect.tsx` (NEW), `frontend/src/App.tsx` (MODIFIED) |

## Artifacts Landed (verbatim from UI-SPEC)

### `frontend/src/components/layout/CompanyBrandEffect.tsx` (NEW — 53 lines)
- Verbatim from UI-SPEC Artifact 6 (docstring + body identical to spec).
- Single `useEffect` with `[company]` dependency commits three side effects atomically (FOWB protection): `document.documentElement.dataset.company`, `document.title`, `<link rel='icon'>` href.
- Early-out guard `if (company !== 'seva' && company !== 'juno') return` — avoids `companyBrandConfig[undefined]`.
- Cleanup restores `dataset.company = 'seva'` and `document.title = 'Seva Mining'`. Favicon intentionally NOT restored (browser cache + transition flicker considerations).
- Returns `null` (renders nothing).

### `frontend/src/components/layout/AppHeader.tsx` (MODIFIED — registry consumption)
- Added import: `import { useCompanyBrand } from '@/hooks/useCompanyBrand'`.
- Added hook call: `const brand = useCompanyBrand()` after `clearToken`.
- Replaced 3 hardcoded literals in the brand-mark block:
  - `bg-amber-500` → `${brand.markBgClassName}` (resolves to `bg-brand-accent` for both tenants — the per-tenant difference comes from the CSS-token override, not a Tailwind class swap)
  - `"S"` → `{brand.markLetter}`
  - `"Seva Mining"` → `{brand.wordmark}`
- All other lines (imports of `useNavigate` / `useAppStore` / `CompanySwitcher`, `handleLogout` body, `<header>` shell, `<CompanySwitcher />`, `<button>Log out</button>`) byte-identical.

### `frontend/src/components/layout/BareRootRedirect.tsx` (NEW — 24 lines)
- Verbatim from UI-SPEC Artifact 8.
- Non-reactive Zustand read via `useAppStore.getState().lastVisitedCompany` (D-08c contract — no `useAppStore(s => s.lastVisitedCompany)`).
- Returns `<Navigate to={\`/${tenant}\`} replace />` with `tenant === 'juno' ? 'juno' : 'seva'` (treats null/unknown as `'seva'` fallback).

### `frontend/src/App.tsx` (MODIFIED — 3 surgical edits)
- Added 2 imports: `CompanyBrandEffect`, `BareRootRedirect` (placed after existing `WeeklyViralSweeperPage` import).
- Replaced `<Route index element={<Navigate to="/seva" replace />} />` (line 50) with `<Route index element={<BareRootRedirect />} />`.
- Wrapped the `:company` route element: `<Route path=":company" element={<CompanyScopedRoute />}>` → `<Route path=":company" element={<><CompanyBrandEffect /><CompanyScopedRoute /></>}>` — Fragment renders both effect + route guard as siblings; both see `useParams<{company}>()` because both mount inside the `:company` route.
- All 4 bookmark-grace `<Navigate>` redirects (`/calendar`, `/viral`, `/queue`, `/agents/:slug`) preserved byte-identical.

## Acceptance Criteria — Per-Task Verification

### Task 1 — CompanyBrandEffect.tsx (10 grep + TSC checks)

| Check | Expected | Actual |
|-------|---------|--------|
| `test -f frontend/src/components/layout/CompanyBrandEffect.tsx` | exit 0 | PASS |
| `grep -c "export function CompanyBrandEffect"` | 1 | 1 PASS |
| `grep -c "document.documentElement.dataset.company = company"` | ≥1 | 2 (1 code + 1 docstring) PASS |
| `grep -c "document.title = config.pageTitle"` | ≥1 | 2 (1 code + 1 docstring) PASS |
| `grep -c "link\\[rel='icon'\\]"` | 1 | 1 PASS |
| `grep -c "document.documentElement.dataset.company = 'seva'"` | 1 | 1 (cleanup) PASS |
| `grep -c "document.title = 'Seva Mining'"` | 1 | 1 (cleanup) PASS |
| `grep -c "useEffect"` | 1 | 2 (1 import + 1 call) — see deviation note |
| `grep -c "company === 'juno'"` | 0 | 0 PASS (early-out uses `!==`) |
| `grep -c "return null"` | 1 | 1 PASS |
| `npx tsc --noEmit` for CompanyBrandEffect | no errors | PASS (TSC silent — zero output) |

### Task 2 — AppHeader.tsx (D-09 byte-identical contract)

| Check | Expected | Actual |
|-------|---------|--------|
| `grep -c "import { useCompanyBrand } from '@/hooks/useCompanyBrand'"` | 1 | 1 PASS |
| `grep -c "const brand = useCompanyBrand()"` | 1 | 1 PASS |
| `grep -c "bg-amber-500"` | 0 | 0 PASS |
| `grep -c "Seva Mining"` | 0 | 0 PASS |
| `grep -c '>S<'` | 0 | 0 PASS |
| `grep -c "brand.wordmark"` | 1 | 1 PASS |
| `grep -c "brand.markLetter"` | 1 | 1 PASS |
| `grep -c "brand.markBgClassName"` | 1 | 1 PASS |
| `grep -c "company === 'juno'"` | 0 | 0 PASS (after comment reword — see Deviations) |
| `grep -c "company === 'seva'"` | 0 | 0 PASS |
| 4 existing Seva tests in AppHeader.test.tsx | all pass | 4/4 PASS byte-identically |
| `git diff frontend/src/components/layout/__tests__/AppHeader.test.tsx` | empty | empty diff — test file UNMODIFIED PASS |

### Task 3 — BareRootRedirect.tsx + App.tsx wiring

| Check | Expected | Actual |
|-------|---------|--------|
| `test -f BareRootRedirect.tsx` | exit 0 | PASS |
| `grep -c "export function BareRootRedirect"` | 1 | 1 PASS |
| `grep -c "useAppStore.getState().lastVisitedCompany"` | 1 | 1 PASS (D-08c non-reactive) |
| `grep -c "useAppStore((s) => s.lastVisitedCompany)"` | 0 | 0 PASS (D-08c forbids reactive form) |
| `<Navigate to={\`/\${tenant}\`} replace />` literal in BareRootRedirect | 1 | 1 PASS |
| `grep -c "import { CompanyBrandEffect }"` in App.tsx | 1 | 1 PASS |
| `grep -c "import { BareRootRedirect }"` in App.tsx | 1 | 1 PASS |
| `grep -c "<BareRootRedirect />"` in App.tsx | 1 | 1 PASS |
| `grep -c '<Navigate to="/seva" replace />'` in App.tsx | 0 (line 50 replaced) | 0 PASS |
| `grep -c "<CompanyBrandEffect />"` in App.tsx | 1 | 1 PASS |
| `grep -c '<Navigate to="/seva/calendar"'` in App.tsx | 1 (preserved) | 1 PASS |
| `grep -c '<Navigate to="/seva/viral"'` in App.tsx | 1 (preserved) | 1 PASS |
| `grep -c '<Navigate to="/seva" replace'` in App.tsx | ≥2 (`/queue` + `/agents/:slug`) | 2 PASS |
| `awk '/<Route path=":company"/,/element=/' App.tsx \| grep -c "CompanyBrandEffect"` | ≥1 | 1 PASS |
| `npx tsc --noEmit` | no errors | PASS (silent) |
| `npm test -- --run` | exit 0, ≥168 tests | **168/168 PASS** |

## Phase-Level Verification

| # | Check | Command | Result |
|---|-------|---------|--------|
| 1 | D-09 byte-identical test file | `git diff HEAD~3 HEAD -- AppHeader.test.tsx` | empty diff PASS |
| 2 | D-10 branchlessness gate (preview) | `grep -rn "company === 'juno'" frontend/src/components/ \| grep -v __tests__` | 0 hits PASS |
| 3 | TypeScript clean | `cd frontend && npx tsc --noEmit` | 0 errors PASS |
| 4 | Full vitest suite | `cd frontend && npm test -- --run` | **28 files, 168/168 PASS** |
| 5 | Phase-12 baseline preserved | (same as #4) | **168/168 — zero regression** |

## Test Count Before/After This Plan

- **Before (Wave 1):** 28 test files, 168 tests passing (per Wave 1 SUMMARY metric `tests_passing: 168/168`).
- **After (Wave 2):** 28 test files, 168 tests passing. **No test additions in this plan** — Wave 3 (13-03) will ADD 2 new Juno tests to `AppHeader.test.tsx` and a new `AppHeader.brand.test.tsx` with 5 FOWB tests.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Acceptance-gate quirk] AppHeader.tsx inline comment reworded to satisfy literal-substring D-10 grep**
- **Found during:** Task 2 acceptance verification
- **Issue:** UI-SPEC Artifact 7 specifies the comment `{/* Brand mark — Phase 13 (D-04) registry-driven; Phase 9 D-02 freeze-lift + Phase 13 BRAND lift both apply. No \`company === 'juno'\` branch (D-10). */}` verbatim, but the acceptance criterion `grep -c "company === 'juno'" frontend/src/components/layout/AppHeader.tsx returns 0` fails when the comment self-documents the absence of the branch by referencing it as a literal substring.
- **Fix:** Reworded the comment minimally — `No \`company === 'juno'\` branch (D-10).` → `No per-tenant conditional branch (D-10).`. Semantic intent preserved (the comment still documents the D-10 invariant); the literal substring that fails the grep gate is removed.
- **Files modified:** `frontend/src/components/layout/AppHeader.tsx` (single line)
- **Commit:** included in Task 2 commit `268f417`
- **Precedent:** Mirrors Wave 1's "Acceptance-criterion grep wording (NOT a code deviation — verification-command quirk)" deviation in `13-01-SUMMARY.md`. The grep tool's literal-substring matching is incidentally strict; UI-SPEC verbatim consumption invariant is honored at the *content* level (the comment still says the same thing).

### Out-of-scope discoveries logged

None new this plan. The 15 pre-existing test-file lint errors logged to `deferred-items.md` in Plan 13-01 remain unaddressed (out of scope for Plan 13-02).

## Authentication Gates

None — Plan 13-02 is purely client-side rendering + routing work with no API calls, secrets, or external services.

## Known Stubs

None. Every consumer is fully wired:
- `AppHeader` calls `useCompanyBrand()` and renders all three brand fields (`wordmark`, `markLetter`, `markBgClassName`).
- `<CompanyBrandEffect />` is mounted inside `<Route path=":company">` so `useParams` resolves on every route mount.
- `<BareRootRedirect />` replaces the bare-`/` `<Navigate>` and reads Zustand non-reactively.

No part of the registry is unconsumed; no field in `BrandConfig` is dead.

## Visual QA Deferred to Wave 3

Per UI-SPEC §"Operator Visual-QA Checklist", the 1440×900 eye-check across 10 items (Seva amber chrome, Juno navy chrome, CompanySwitcher active states, focus rings, favicon tab-strip differentiation, browser tab title, bare-/ redirect behavior, Phase 8 cascaded surfaces, log-out cleanup) is a Wave 3 checkpoint (`type="checkpoint:human-verify"` inside `13-03-PLAN.md`). This plan's verification was code-level only (grep, tsc, vitest); no dev server was started and no operator visual evaluation performed yet.

## Notes for Plan 13-03 (Wave 3 — next wave)

Wave 3 will:
1. Extend `frontend/src/components/layout/__tests__/AppHeader.test.tsx` with 2 NEW Juno-default tests (5 + 6 in UI-SPEC Test Matrix File 1). Existing 4 Seva tests MUST stay byte-identical (D-09 contract continues to hold).
2. Create `frontend/src/components/layout/__tests__/AppHeader.brand.test.tsx` (NEW file) with 5 FOWB + cleanup tests per UI-SPEC Test Matrix File 2.
3. Run full regression — target test count ≥ 175 (168 baseline + 2 new in File 1 + 5 new in File 2).
4. Operator visual-QA checkpoint at 1440×900 (10 items per UI-SPEC §"Operator Visual-QA Checklist"); must-pass items 1, 2, 4, 5, 6, 7.
5. Optionally formalize D-10 branchlessness as a CI grep gate script.

## Self-Check: PASSED

- Files created exist on disk:
  - `/Users/matthewnelson/seva-mining/frontend/src/components/layout/CompanyBrandEffect.tsx` — FOUND
  - `/Users/matthewnelson/seva-mining/frontend/src/components/layout/BareRootRedirect.tsx` — FOUND
- Files modified exist on disk and contain expected changes:
  - `/Users/matthewnelson/seva-mining/frontend/src/components/layout/AppHeader.tsx` — FOUND, registry-driven
  - `/Users/matthewnelson/seva-mining/frontend/src/App.tsx` — FOUND, CompanyBrandEffect mounted, BareRootRedirect wired
- Commits exist in git log:
  - `8e346ca` (Task 1) — FOUND
  - `268f417` (Task 2) — FOUND
  - `968ba6b` (Task 3) — FOUND
- Frontend tests: 168/168 PASS, zero regression vs Wave 1 baseline.
- TypeScript: clean (no errors).
- D-10 branchlessness gate (preview): 0 hits in non-test component files.
- D-09 byte-identical AppHeader test file: unmodified by this plan.
