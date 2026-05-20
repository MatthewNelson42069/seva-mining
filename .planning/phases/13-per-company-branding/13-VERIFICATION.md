---
phase: 13-per-company-branding
verified: 2026-05-20T14:40:00Z
status: passed
score: 12/12 invariants verified, 5/5 requirements satisfied
mode: initial
---

# Phase 13: Per-Company Branding — Verification Report

**Phase Goal:** Replace hardcoded Seva visual identity in `AppHeader` + `index.css` with a per-tenant registry (`companyBrandConfig.ts`). After this phase: `/juno/*` routes render "Juno Industries" wordmark + "J" letter mark in navy square + navy-toned color palette resolved through CSS tokens; `/seva/*` continues to render Seva's amber identity unchanged. Brand resolution is config-driven (no `if company === 'juno'` branches inside components) and FOWB-proof. Three opportunistic polish items folded in: per-tenant browser tab title, per-tenant favicon, and bare-`/` redirect to last-visited tenant.

**Verified:** 2026-05-20T14:40:00Z
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

Goal-backward question: **Does the codebase deliver what the phase promised?** YES.

The phase delivered a complete per-tenant brand resolution layer. Visiting `/juno/*` synchronously commits navy chrome (wordmark, mark letter, color palette, document title, favicon) via a single `useEffect` inside `<CompanyBrandEffect />`, with cleanup that reverts to Seva default on unmount. Visiting `/seva/*` continues to render byte-identical chrome to the v3.0 pre-Phase-13 state (4 existing AppHeader tests pass unchanged). No component file in `frontend/src/components/` contains `company === 'juno' | 'seva'` branching — the registry IS the only allowed branch.

---

## Per-Requirement Verdict (BRAND-01 .. BRAND-05)

| ID       | Verdict | Evidence (file:line)                                                                                                                                                                                                                                                              |
| -------- | ------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| BRAND-01 | PASS    | `frontend/src/config/companyBrandConfig.ts:66` (`wordmark: 'Juno Industries'`) + `frontend/src/components/layout/AppHeader.tsx:25` (`{brand.wordmark}`) + `__tests__/AppHeader.test.tsx:90-94` (Juno wordmark test) + `__tests__/AppHeader.test.tsx:63-66` (Seva regression test) |
| BRAND-02 | PASS    | `frontend/src/index.css:135-138` (`:root.dark[data-company='juno']` override with `--brand-accent: oklch(0.58 0.14 245)`) + `frontend/src/components/layout/CompanyBrandEffect.tsx:36` (sets `dataset.company` to trigger CSS cascade)                                             |
| BRAND-03 | PASS    | `frontend/public/brand/juno.svg` exists (288 bytes; `fill="oklch(0.58 0.14 245)"`); `frontend/src/components/layout/AppHeader.tsx:21-24` renders `brand.markLetter` ("J") in `brand.markBgClassName` square; favicon swap via `CompanyBrandEffect.tsx:38-39`                       |
| BRAND-04 | PASS    | `frontend/src/components/layout/CompanyBrandEffect.tsx:32-50` — single `useEffect` commits dataset+title+favicon atomically; `__tests__/AppHeader.brand.test.tsx:155-176` FOWB test verifies synchronous flip with zero `await waitFor` / `act(async)` calls                       |
| BRAND-05 | PASS    | D-10 Gate A (components, no tests): `grep -rn "company === '(juno\|seva)'" frontend/src/components/ \| grep -v __tests__` returns 0 hits. D-10 Gate B (broader sweep) returns 1 hit at `useCompanyBrand.ts:26` — the registry resolution hook itself (planner-flagged deviation)   |

**Score:** 5/5 requirements satisfied.

---

## Per-Invariant Verdict (12 invariants)

| #   | Invariant                                                | Verdict | Evidence                                                                                                                                                                                                                                                |
| --- | -------------------------------------------------------- | ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Registry exists + complete (seva + juno)                 | PASS    | `frontend/src/config/companyBrandConfig.ts:52` declares `Record<'seva' \| 'juno', BrandConfig>`; both keys populated with all 6 schema fields (`wordmark`, `markLetter`, `markBgClassName`, `palette`, `pageTitle`, `faviconHref`). File = 3260 bytes.   |
| 2   | Hook exists with URL → Zustand → 'seva' fallback chain   | PASS    | `frontend/src/hooks/useCompanyBrand.ts:21-35`: `useParams` first, then `useAppStore((s) => s.lastVisitedCompany)`, then `'seva'` final fallback. Returns strictly-typed `BrandConfig`.                                                                   |
| 3   | AppHeader branchlessness (D-10 Gate A)                   | PASS    | `grep -rn "company === '(juno\|seva)'" frontend/src/components/ \| grep -v __tests__` = **0 hits**. AppHeader.tsx contains zero `company ===` checks.                                                                                                    |
| 4   | No hardcoded `bg-amber-500` in AppHeader                 | PASS    | `grep "bg-amber-500" frontend/src/components/layout/AppHeader.tsx` = **0 hits**. Replaced by `${brand.markBgClassName}` (resolves to `bg-brand-accent` via registry, which cascades through CSS token).                                                  |
| 5   | CSS override block at `:root.dark[data-company='juno']`  | PASS    | `frontend/src/index.css:135` — exactly `:root.dark[data-company='juno']` (NOT bare `:root[data-company='juno']`). `.dark` qualifier preserved per D-09 / D-06 specificity contract.                                                                      |
| 6   | OKLCH triple for Juno tokens correct                     | PASS    | `frontend/src/index.css:136-138`: `--brand-accent: oklch(0.58 0.14 245)`; `--brand-accent-hover: oklch(0.65 0.14 245)`; `--brand-accent-subtle: oklch(0.58 0.14 245 / 0.05)`.                                                                            |
| 7   | Favicon OKLCH string-equality with CSS tokens            | PASS    | `frontend/public/brand/juno.svg`: `fill="oklch(0.58 0.14 245)"` byte-equal to CSS `--brand-accent` under `[data-company='juno']`. `frontend/public/brand/seva.svg`: `fill="oklch(0.769 0.188 70.08)"` byte-equal to CSS default Seva accent.             |
| 8   | CompanyBrandEffect single useEffect                      | PASS    | `frontend/src/components/layout/CompanyBrandEffect.tsx:32-50` — exactly ONE `useEffect` block with `[company]` dependency commits all three mutations (`dataset.company`, `document.title`, favicon `<link href>`). Not three separate effects.          |
| 9   | BareRootRedirect non-reactive Zustand read               | PASS    | `frontend/src/components/layout/BareRootRedirect.tsx:23` uses `useAppStore.getState().lastVisitedCompany` (non-reactive). `grep "useAppStore((s)" frontend/src/components/layout/BareRootRedirect.tsx` = 0 hits. D-08c contract honored.                  |
| 10  | App.tsx wiring (CompanyBrandEffect + BareRootRedirect)   | PASS    | `frontend/src/App.tsx:14-15` imports both. Line 52: `<Route index element={<BareRootRedirect />} />` replaces bare `Navigate to="/seva"`. Line 62: `<Route path=":company" element={<><CompanyBrandEffect /><CompanyScopedRoute /></>}>` — effect inside `:company` subtree.                            |
| 11  | D-09 zero-regression — existing 4 Seva tests byte-pass   | PASS    | `frontend/src/components/layout/__tests__/AppHeader.test.tsx:63-84` — original 4 test names unchanged (`renders the "Seva Mining" wordmark text`, `renders the amber "S" logo mark`, `renders a "Log out" button`, `clicking "Log out" calls clearToken and navigates to /login`). Local test run: 6/6 pass. |
| 12  | New FOWB test file with 5+ tests, zero async waits       | PASS    | `frontend/src/components/layout/__tests__/AppHeader.brand.test.tsx` — 5 `it(...)` blocks (dataset×2, FOWB, favicon, cleanup). `grep -E "await waitFor\|act\(async" AppHeader.brand.test.tsx` = **0 hits**. Local test run: 5/5 pass.                       |

**Score:** 12/12 invariants verified.

---

## Behavioral Spot-Check (Step 7b)

| Behavior                            | Command                                                                                                          | Result            | Status |
| ----------------------------------- | ---------------------------------------------------------------------------------------------------------------- | ----------------- | ------ |
| AppHeader + FOWB suite green        | `cd frontend && npm test -- --run src/components/layout/__tests__/AppHeader.test.tsx ...AppHeader.brand.test.tsx` | 11/11 passed      | PASS   |
| All 11 commits present on `main`    | `for sha in b0edf68 406c8b9 1198a36 8e346ca 268f417 968ba6b 157d322 9b3b24e 76a1903 412e272 1a665aa; do git cat-file -e $sha; done` | All 11 OK         | PASS   |
| index.html title corrected          | `grep "<title>" frontend/index.html`                                                                              | `<title>Seva Mining</title>` | PASS   |

Full regression baseline (orchestrator-confirmed, not re-run here):
- Frontend: 175 passed (29 files) — Phase 12 baseline 168 + 7 new
- Scheduler: 323 passed, 1 skipped
- Backend: 184 passed, 5 skipped

---

## Operator Visual QA Ledger (1440×900) — APPROVED

Sign-off recorded in commit `412e272` and documented in `13-03-SUMMARY.md:128`. Operator (Matt) reply: **"approved"** — blanket approval covering all 10 items.

### MUST-PASS (6/6 confirmed)

| # | Item                                                                            | Result |
| - | ------------------------------------------------------------------------------- | ------ |
| 1 | `/seva/` shows amber square + "S" + "Seva Mining" — D-09 zero regression visual | PASS   |
| 2 | `/juno/` shows navy square + "J" + "Juno Industries" — institutional read       | PASS   |
| 4 | Seva → Juno transition — no flash of wrong brand (FOWB)                         | PASS   |
| 5 | Browser tab title flips live (Seva Mining ↔ Juno Industries)                    | PASS   |
| 6 | Favicon swap at 14-16px — amber-S ↔ navy-J distinguishable                      | PASS   |
| 7 | Bare-`/` redirect → last-visited tenant (Juno after visit; Seva on first visit) | PASS   |

### SHOULD-PASS (4/4 confirmed; non-blocking)

| #  | Item                                                                                  | Result |
| -- | ------------------------------------------------------------------------------------- | ------ |
| 3  | CompanySwitcher active "Juno" navy outline + navy text + faint navy fill              | PASS   |
| 8  | Phase 8 surfaces (SectionBlock / SweeperCard accents) auto-cascade navy at /juno      | PASS   |
| 9  | Keyboard focus rings — navy at /juno; amber at /seva                                  | PASS   |
| 10 | Logout from /juno → /login — title reverts to "Seva Mining"; no flash on re-login     | PASS   |

---

## Anticipated Deviations (planner-flagged; NOT failures)

These were pre-validated by the orchestrator and do not affect the PASS verdict:

1. **D-10 Gate B 1 hit at `useCompanyBrand.ts:26`** — `if (params.company === 'seva' || params.company === 'juno')` is the URL-param type-narrowing guard inside the registry resolution hook itself. The hook IS the registry's only allowed branch infrastructure. Semantic intent of D-10 preserved (no per-tenant branching inside `frontend/src/components/`).
2. **AppHeader.tsx inline comment minimally reworded** — "No `company === 'juno'` branch" → "No per-tenant conditional branch" (line 20) to satisfy literal-substring D-10 grep acceptance gate. Semantic intent preserved; comment still documents the D-10 contract.
3. **vi.mock hoist-init bug auto-fixed in Plan 13-03 Task 2 (Rule 1 inline fix)** — the brand test file inlines the `stubState` literal inside the `vi.mock` factory rather than referencing a top-level const (avoids `Cannot access before initialization` at hoist time). See `AppHeader.brand.test.tsx:42-52`.

---

## D-08c (TENANT-VISITED-v31-redux) Closure

The v3.0-deferred polish item is CLOSED as opportunistic Phase 13 work:

- `BareRootRedirect.tsx` consumes Zustand `useAppStore.getState().lastVisitedCompany` (non-reactive)
- Operator visual QA item 7 confirmed redirect behaves correctly (returns to /juno after visiting Juno; falls back to /seva on first visit / cleared localStorage)
- Documented in `13-03-SUMMARY.md:193` and `13-02-SUMMARY.md` (Wave 2 plan delivered the file; Wave 3 plan's operator QA confirmed)

---

## Goal-Backward Summary

**The codebase delivers what the phase promised — without qualification.**

- The hardcoded Seva visual identity in `AppHeader` has been completely replaced with registry-driven resolution. The wordmark, mark letter, and mark background all flow from `useCompanyBrand()` → `companyBrandConfig[resolved]`. Adding a 3rd tenant requires only (a) extending the `'seva' | 'juno'` union, (b) adding a registry entry, and (c) adding a `:root.dark[data-company='X']` CSS block. Zero component edits.
- The CSS-token cascade fires because `<CompanyBrandEffect />` mounts inside `<Route path=":company">` and writes `dataset.company` on the documentElement in the same `useEffect` that writes `document.title` and the favicon `<link href>`. React commits all three mutations atomically — the FOWB unit test proves this synchronously (no `waitFor`, no `act(async)`), and the operator visually confirmed the transition shows no flash.
- The opportunistic polish items (per-tenant tab title, per-tenant favicon, bare-`/` redirect) are all live in the production bundle. `index.html` title corrected from Vite-scaffold `frontend` to `Seva Mining` (the default that `<CompanyBrandEffect />` cleanup restores). Two SVG favicons exist under `frontend/public/brand/` with OKLCH string-equal fills to their CSS counterparts.
- D-09 zero-regression contract holds byte-identically: the 4 original Seva AppHeader tests (`renders the "Seva Mining" wordmark text`, `renders the amber "S" logo mark`, `renders a "Log out" button`, `clicking "Log out" calls clearToken and navigates to /login`) pass with their original names and bodies. The Wave 3 plan's extension to that file is purely additive.

---

## Final Phase Verdict

**PASS** — All 5 BRAND requirements satisfied. All 12 invariants verified. Operator visual QA approved 10/10. D-08c (TENANT-VISITED-v31-redux) closed as opportunistic polish. Phase 13 ships ready.

---

_Verified: 2026-05-20T14:40:00Z_
_Verifier: Claude (gsd-verifier)_
