# Phase 13: Per-company Branding - Context

**Gathered:** 2026-05-20
**Status:** Ready for planning (UI design contract recommended before plan-phase)

<domain>
## Phase Boundary

Replace hardcoded Seva visual identity in `AppHeader` + `index.css` with a per-tenant registry (`companyBrandConfig.ts`). After this phase: `/juno/*` routes render the "Juno Industries" wordmark + a "J" letter mark in a navy square + a navy-toned color palette resolved through CSS tokens; `/seva/*` continues to render "Seva Mining" + amber-S + amber palette with zero regression. Brand resolution is config-driven (no `if company === 'juno'` branches inside components) and FOWB-proof (no flash of wrong brand on Seva ↔ Juno route switch). Three opportunistic polish items fold in: per-tenant browser tab title, per-tenant favicon, and bare-`/` redirect to last-visited tenant (TENANT-VISITED-v31-redux).

**In scope:**
- New `frontend/src/config/companyBrandConfig.ts` registry (mirrors `companySectionConfig.ts` pattern)
- New `frontend/src/hooks/useCompanyBrand.ts` hook (URL-derived via `useParams`, fallback chain `URL → Zustand lastVisitedCompany → 'seva'`)
- Refactor `AppHeader.tsx` to consume registry (no inline literals, no conditional branches)
- `index.css` — add `:root[data-company='juno'] { --brand-accent: ...navy...; }` override block; preserve existing default amber as `:root { ... }`
- Router-layer effect setting `document.documentElement.dataset.company` on route change (FOWB protection)
- `frontend/public/brand/` directory + 2 SVG favicons (`seva.svg` + `juno.svg`)
- `document.title` per-tenant update effect
- Bare-`/` route — `<Navigate to={`/${lastVisitedCompany || 'seva'}/`} replace />` (TENANT-VISITED-v31-redux closure)
- RTL unit test for FOWB: MemoryRouter route flip + synchronous dataset + wordmark assertions in single `act()` wrapper
- AppHeader test refactor — existing tests at `frontend/src/components/layout/__tests__/AppHeader.test.tsx` must continue to pass (Seva-default case) + new Juno case added

**Out of scope:**
- Adding a 3rd tenant or extending the `Record<'seva'|'juno', ...>` typing (TENANT-N-v32 → v3.2+)
- Light theme (`@layer base` light variant) — current setup is dark-only per Phase 8; light theme deferred to v2.2+ unchanged
- Changing Seva's amber palette values, wordmark, or letter mark — Phase 13 is purely additive for Juno + register-the-existing for Seva (zero regression contract)
- SVG logo upgrade for Juno (deferred to v3.2+ polish — Phase 13 ships letter-mark parity per D-03)
- Mobile-responsive header treatment — desktop-only constraint preserved
- WCAG contrast audit beyond visual eye-check at 1440×900 (formal WCAG verification deferred)

</domain>

<decisions>
## Implementation Decisions

### Visual Identity (BRAND-01..03)

- **D-01 Juno palette family:** Navy / midnight blue — institutional defence-industry tone (RUSI / Naval Postgraduate / defence-prime corporate sites; NOT bright/cyan/tech-startup blue). Starting OKLCH value: `oklch(0.55 0.15 240)` for `--brand-accent`. Planner derives hover (`accentHover`) + subtle (`accentSubtle`) by mirroring Seva's relationship: hover = +~0.06 lightness same chroma + hue, subtle = base + ` / 0.05` alpha. Final values reviewed during plan-phase + visual QA. Eye-check at 1440×900 must show clear distinction from Seva amber on side-by-side toggle.

- **D-02 Juno wordmark text:** `"Juno Industries"` — full two-word company name. Matches Seva Mining's two-word shape for typographic consistency between tenants. Identical font weight + size as existing Seva wordmark (`text-sm font-semibold text-white` per current AppHeader.tsx:22).

- **D-03 Juno brand-mark:** Letter "J" in navy square — mirrors Seva's existing "S in amber square" exactly. Same DOM shape (`<div className="w-7 h-7 rounded-md {markBgClassName}"><span className="text-xs font-bold text-zinc-900">{markLetter}</span></div>`), just different `markLetter` + `markBgClassName` per tenant. Zero asset design work. SVG logo upgrade is explicitly deferred (Out of Scope above).

### Registry Architecture (BRAND-05)

- **D-04 Registry location + schema:** `frontend/src/config/companyBrandConfig.ts` (sibling of existing `companySectionConfig.ts`). Schema:
  ```ts
  export interface BrandConfig {
    wordmark: string                 // e.g., "Seva Mining" / "Juno Industries"
    markLetter: string               // e.g., "S" / "J"
    markBgClassName: string          // e.g., "bg-brand-accent" — Tailwind class consuming CSS token
    palette: {
      accent: string                 // OKLCH string for --brand-accent
      accentHover: string            // OKLCH string for --brand-accent-hover
      accentSubtle: string           // OKLCH string for --brand-accent-subtle (with alpha)
    }
    pageTitle: string                // e.g., "Seva Mining" / "Juno Industries" — for document.title
    faviconHref: string              // e.g., "/brand/seva.svg" / "/brand/juno.svg"
  }
  export const companyBrandConfig: Record<'seva' | 'juno', BrandConfig> = { ... }
  ```
  `palette` strings are documentation-only — actual token values live in `index.css` (single source of truth). Adding a 3rd tenant requires (a) extending `'seva' | 'juno'` union (b) adding registry entry (c) adding new `:root[data-company='X']` block in CSS. Pattern matches v3.0 Phase 9 D-08 exactly.

- **D-05 useCompanyBrand() hook resolution chain:** New file `frontend/src/hooks/useCompanyBrand.ts`. Reads URL via `useParams<{company?: 'seva' | 'juno'}>()`. Fallback chain:
  1. URL `:company` segment if present + valid
  2. Zustand `lastVisitedCompany` (already populated in v3.0)
  3. `'seva'` hardcoded default
  Returns `companyBrandConfig[resolved]`. Designed to work for components ABOVE the `:company` route (e.g., `AppHeader.tsx` which renders in `AppShell` outside the company-scoped subtree).

### CSS Token Resolution + FOWB (BRAND-04)

- **D-06 Token override mechanism:** `:root[data-company='juno'] { --brand-accent: ...navy...; --brand-accent-hover: ...; --brand-accent-subtle: ...; }` CSS block added to `index.css` immediately after the existing `:root { ... }` block at lines 117-127. Router-layer effect at top of `<TabbedDashboard>` (or analogous component scoped to `:company` route) calls `document.documentElement.dataset.company = company` whenever `useParams<{company}>()` resolves. Removal effect (cleanup) sets dataset back to `'seva'` default on unmount. Browser applies token override atomically with route paint cycle — zero flash. Tailwind v4 `@theme inline` mapping (`--color-brand-accent: var(--brand-accent)`) cascades automatically.

- **D-07 FOWB test approach:** New test file `frontend/src/components/layout/__tests__/AppHeader.brand.test.tsx` (or extend existing `AppHeader.test.tsx`). Uses `<MemoryRouter initialEntries={['/seva/']}>` wrapper + RTL `render()`. Assertions:
  - After initial render: `document.documentElement.dataset.company === 'seva'`, AppHeader wordmark text === `'Seva Mining'`, markLetter === `'S'`
  - Programmatically navigate to `/juno/` (via test history or rerender with new initialEntries)
  - Synchronously: `dataset.company === 'juno'`, wordmark === `'Juno Industries'`, markLetter === `'J'` — assert in same `act()` wrapper (no async wait — proves no intermediate render with mismatched state)
  - No Playwright dependency added; runs under Vitest in existing CI lane.

### Opportunistic Polish (D-08 — three items folded in)

- **D-08a Browser tab title per tenant:** Same router-layer effect as D-06 also sets `document.title = companyBrandConfig[company].pageTitle`. Cleanup on tenant-context teardown restores generic `"Seva Mining"` default (matches `index.html` `<title>` tag). ~3 lines.

- **D-08b Favicon swap per tenant:** Same effect also updates `<link rel='icon' href={faviconHref}>`. New assets at `frontend/public/brand/seva.svg` (extracted from existing favicon if any, else inline SVG of amber S) and `frontend/public/brand/juno.svg` (inline SVG of navy J). Both SVGs use `<svg viewBox="0 0 32 32">` with a colored `<rect>` + `<text>` (mirrors the DOM-level brand-mark shape) — kept under 1KB each.

- **D-08c Bare-`/` redirect (TENANT-VISITED-v31-redux):** Replace existing `<Route path='/'>` redirect (if any, or add fresh) in `frontend/src/router.tsx` (or App.tsx — wherever routes are declared) with `<Route path='/' element={<BareRootRedirect />}>` where `BareRootRedirect` is a 4-line component reading `useAppStore.getState().lastVisitedCompany` + returning `<Navigate to={`/${lastVisited || 'seva'}/`} replace />`. The existing Zustand `lastVisitedCompany` (populated as switch-action byproduct in v3.0 Phase 9) is the source. ~5 lines.

### Test + Refactor Boundaries

- **D-09 AppHeader test stability:** Existing `frontend/src/components/layout/__tests__/AppHeader.test.tsx` (Seva-default scenario) must continue to pass with zero modification to its assertion text. Phase 13 changes the IMPLEMENTATION (consumes registry) but the OUTPUT for the Seva default case must be byte-identical: same wordmark `'Seva Mining'`, same `'S'` letter, same amber background. Verifies the zero-regression contract.

- **D-10 No `company === 'juno'` branches inside `frontend/src/components/`:** Grep gate verification (manual or scripted) — `grep -rn "company === 'juno'" frontend/src/components/` returns 0 hits in any file matching `**/AppHeader*.tsx`, `**/Brand*.tsx`, `**/TabbedDashboard*.tsx`. The registry consumption pattern is the only allowed shape. Plan-phase decides whether to ship a CI script (mirror `verify-anthropic-resolver.sh`) or keep this as a manual code-review gate. Registry IS branched logic — by design, internal to the config module only.

### Folded Todos
None — no pending todos matched Phase 13 scope at cross-reference time.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents (researcher, planner, executor, UI researcher if /gsd:ui-phase runs) MUST read these before planning or implementing.**

### Phase 13 Roadmap Source
- `.planning/ROADMAP.md` §"Phase 13: Per-company Branding" (lines ~155-220 — full phase block with goal, depends-on, inputs, outputs, success criteria, complexity, hard parts)
- `.planning/REQUIREMENTS.md` §"Per-company Branding (BRAND)" — atomic acceptance criteria for BRAND-01..05

### Project-Level Constraints
- `.planning/PROJECT.md` §"Current Milestone: v3.1" §"Hard parts the roadmap addresses" item 3 ("Branding without per-tenant code forks")
- `CLAUDE.md` — no direct branding guidelines; UI/UX patterns governed by v2.1 Phase 8 amber-500 + semantic-token precedent

### v3.0 / v2.1 Patterns This Phase Extends
- `.planning/milestones/v3.0-phases/09-multi-tenant-foundation/09-CONTEXT.md` D-08 — single-component + per-tenant config registry idiom (`companySectionConfig.ts`)
- `.planning/milestones/v3.0-phases/09-multi-tenant-foundation/09-CONTEXT.md` D-02 — AppHeader freeze-lift rationale (formally lifted; edits permitted with documented rationale; Phase 13 IS that rationale)
- `.planning/phases/12-per-tenant-anthropic-api-key/12-CONTEXT.md` D-07 — Hardcoded literal pattern at instantiation/consumption sites (mirrors `useCompanyBrand()` consuming via `useParams`)
- v2.1 Phase 8 — semantic `--color-brand-accent[-hover/-subtle]` CSS tokens via Tailwind `@theme inline` (UI-01..04)

### Code-Level References (current state for the planner)
- `frontend/src/components/layout/AppHeader.tsx` — primary refactor target. Hardcoded literals at lines 19 (`bg-amber-500`), 20 (`"S"` letter), 22 (`"Seva Mining"` text). Phase 9 D-02 freeze-lift comment already at line 25.
- `frontend/src/index.css:51-53` — Tailwind `@theme inline` `--color-brand-accent*` mappings (no change in Phase 13)
- `frontend/src/index.css:124-126` — current `:root` amber OKLCH values (Seva default; Phase 13 PRESERVES these verbatim and adds a sibling `:root[data-company='juno']` block)
- `frontend/src/config/companySectionConfig.ts` — reference pattern shape that `companyBrandConfig.ts` mirrors
- `frontend/src/components/layout/CompanySwitcher.tsx` — already consumes Zustand for `lastVisitedCompany`; Phase 13's `BareRootRedirect` uses the same hook/selector
- `frontend/src/components/layout/__tests__/AppHeader.test.tsx` — existing tests must continue to pass with Seva-default scenario unchanged
- `frontend/src/router.tsx` (or App.tsx, wherever `<Routes>` is declared) — location for the bare-`/` redirect
- `frontend/public/` — current favicon location; Phase 13 adds `frontend/public/brand/` subdirectory + 2 SVG files

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`companySectionConfig.ts` pattern** — Direct shape template. `Record<'seva' | 'juno', SectionConfig[]>` becomes `Record<'seva' | 'juno', BrandConfig>`. Same import surface, same consumer ergonomics.
- **Tailwind v4 `@theme inline` + CSS-var mapping** (`index.css:51-53`) — already set up correctly. Phase 13 just adds the per-tenant override block; no Tailwind config changes.
- **Zustand `lastVisitedCompany`** (already populated in v3.0 Phase 9) — drives both `useCompanyBrand()` fallback (D-05) AND `BareRootRedirect` (D-08c). Single source.
- **`useParams<{company}>()` pattern** — established in v3.0 Phase 9 multi-tenant routing. `useCompanyBrand()` reuses it identically.

### Established Patterns
- **Per-tenant config registry, no component branches** (v3.0 Phase 9 D-08) — `companyBrandConfig.ts` extends this exactly.
- **`:where(.dark)` / OKLCH color values** (v2.1 Phase 8 UI-01..04) — Phase 13 adds parallel OKLCH values for Juno navy under the same `@layer base` block.
- **Test isolation via MemoryRouter + RTL** — already used in `__tests__/AppHeader.test.tsx`. FOWB test reuses the same setup.
- **`document.documentElement.dataset.*` mutation** — Tailwind v4 dark-mode toggle pattern (if used) is identical mechanism; CSS reads `[data-theme='dark']` selector. Phase 13 adds `[data-company='juno']` alongside.

### Integration Points
- **`AppShell.tsx`** — top-level wrapper. AppHeader renders here OUTSIDE the `:company` route subtree. Router-layer effect needs to set `dataset.company` from a component that DOES see the `:company` param. Best location: `TabbedDashboard.tsx` or a new `<CompanyBrandEffect />` component that lives inside the `<Route path=":company">` element prop.
- **Router declaration site** — `frontend/src/router.tsx` (most likely; planner verifies). Bare-`/` `<Route path='/'>` element needs to be either added or replaced.
- **Index.html `<title>` tag** — current static value. The per-tenant effect overrides it dynamically; ensure HTML default matches Seva (zero-regression for unauthenticated `/login` or page loads outside tenant context).

</code_context>

<specifics>
## Specific Ideas

- **OKLCH navy starting values** (planner refines, visual QA verifies):
  - `--brand-accent: oklch(0.55 0.15 240)` — base navy (mid-saturation, hue ≈ 240° = blue)
  - `--brand-accent-hover: oklch(0.62 0.16 240)` — +0.07 lightness for hover lift (mirror Seva's +0.06 amber bump)
  - `--brand-accent-subtle: oklch(0.55 0.15 240 / 0.05)` — base + alpha (mirrors Seva pattern exactly)
- **Anti-references for Juno palette:** NOT bright royal blue (#1E40AF range), NOT cyan/teal, NOT navy-so-dark-it-reads-black. Target sits between Naval Postgraduate School deep institutional + RUSI publication header tones.
- **Favicon SVG inline shape** (each ~500 bytes):
  - `seva.svg`: `<svg viewBox="0 0 32 32" xmlns="..."><rect width="32" height="32" rx="6" fill="oklch(0.769 0.188 70.08)"/><text x="16" y="22" font-family="system-ui" font-size="20" font-weight="700" text-anchor="middle" fill="oklch(0.145 0 0)">S</text></svg>`
  - `juno.svg`: same shape, swap fill colors + letter to navy + "J"
- **Inline `companyBrandConfig` schema annotation:** Header docstring should explicitly cite "Phase 13 D-04" + "Phase 9 D-08 pattern" so future maintainers see the lineage.

</specifics>

<deferred>
## Deferred Ideas

- **SVG logo upgrade for Juno** — Phase 13 ships letter-mark parity per D-03. A future polish phase (v3.2 / v4.0) could design a real Juno glyph (shield, compass, etc.) once we know the brand has staying power. Letter mark is the pragmatic ship.
- **Light theme support** — Current setup is dark-only per Phase 8. If light theme is ever revived, the per-tenant tokens would need light-variants under `:root:not(.dark)`. Out of scope for v3.1 (no design intent for light theme exists).
- **WCAG contrast audit** — Eye-check at 1440×900 only in Phase 13. Formal axe-core / playwright-accessibility-checker integration deferred to a future a11y phase.
- **Per-tenant fonts** — All tenants currently share Geist Variable (Phase 8 lock). If a future tenant wants different typography, schema extension required. Out of scope.
- **Mobile-responsive header collapsing wordmark to logo-only** — Desktop-only constraint preserved. Not a v3.1 concern.
- **Reviewed Todos (not folded)** — None reviewed; cross-reference returned 0 matches.

</deferred>

---

*Phase: 13-per-company-branding*
*Context gathered: 2026-05-20*
