# Phase 13: Per-company Branding - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `13-CONTEXT.md` — this log preserves the alternatives considered.

**Date:** 2026-05-20
**Phase:** 13-per-company-branding
**Areas discussed:** Juno visual identity, Registry architecture, CSS token resolution + FOWB, Opportunistic polish

---

## Juno Visual Identity

### Q1: Juno color palette — what tone fits a defence-industry intelligence dashboard?

| Option | Description | Selected |
|--------|-------------|----------|
| Navy / midnight blue | (Recommended) Deep institutional blue — RUSI/Naval Postgraduate/defence-prime corporate. Authoritative, sober. OKLCH ~oklch(0.55 0.15 240). | ✓ |
| Desaturated steel-blue / gunmetal | Cooler, more muted; Jane's IHS style. Risk: washed-out next to amber. | |
| Muted bronze / brass | Military insignia / brass-instrument tone. Risk: too similar to Seva amber at small sizes. | |
| Slate gray | Pure achromatic accent. Risk: low contrast against existing zinc backgrounds. | |

**User's choice:** Navy / midnight blue
**Notes:** Decision captured as D-01. Anti-references documented in `<specifics>` section.

### Q2: Juno wordmark text in AppHeader

| Option | Description | Selected |
|--------|-------------|----------|
| Juno Industries | (Recommended) Full two-word name; matches "Seva Mining" shape. | ✓ |
| Juno | Shorter, punchier. Less consistent with two-word pattern. | |
| JUNO INDUSTRIES (all-caps) | Defence-trade-press masthead feel. | |

**User's choice:** Juno Industries
**Notes:** Decision captured as D-02.

### Q3: Juno brand-mark (the small square next to wordmark)

| Option | Description | Selected |
|--------|-------------|----------|
| Letter mark (J in colored square) | (Recommended) Mirrors Seva 'S in amber square' exactly. Zero asset design work. | ✓ |
| Simple geometric SVG | ~30-line inline SVG glyph (shield/compass/etc.). | |
| Letter mark now, SVG later | Ship letter mark in Phase 13; defer SVG upgrade. | |

**User's choice:** Letter mark (J in colored square)
**Notes:** Decision captured as D-03. SVG upgrade documented as deferred (v3.2+).

---

## Registry Architecture

### Q4: Registry file location + schema scope

| Option | Description | Selected |
|--------|-------------|----------|
| Sibling of companySectionConfig (Recommended) | `frontend/src/config/companyBrandConfig.ts` next to existing config. Full schema: wordmark, markLetter, markBgClassName, palette, pageTitle, faviconHref. | ✓ |
| Co-locate with AppHeader | `frontend/src/components/layout/companyBrandConfig.ts`. Weaker pattern. | |
| Minimal registry (palette only) | Keep wordmark + markLetter inline with conditionals. Violates BRAND-05. | |

**User's choice:** Sibling of companySectionConfig
**Notes:** Decision captured as D-04 with full schema.

### Q5: useCompanyBrand() hook — how does AppHeader read the active tenant?

| Option | Description | Selected |
|--------|-------------|----------|
| URL-derived via useParams (Recommended) | Hook reads `:company` from useParams; fallback chain URL → Zustand → 'seva'. | ✓ |
| Zustand-derived | Reads from store only. Risk: drift between URL and store causing FOWB on deep links. | |
| React Context | `<BrandProvider>` wrapper. Heavyweight; doesn't compose with Phase 9 routing. | |

**User's choice:** URL-derived via useParams
**Notes:** Decision captured as D-05 with fallback chain.

---

## CSS Token Resolution + FOWB

### Q6: How should per-tenant palette tokens override the default?

| Option | Description | Selected |
|--------|-------------|----------|
| data-company attribute on <html> (Recommended) | `:root[data-company='juno'] { --brand-accent: ... }` + JS sets dataset.company. FOWB-proof; Tailwind v4 native. | ✓ |
| Body class toggle | `body.juno-theme { ... }` + JS toggles class. Equivalent but harder to query in tests. | |
| Inline-style React Context | `style={{ '--brand-accent': ... }}` on wrapper. Doesn't reach Tailwind's @theme compile. | |
| Per-route CSS files (heavy) | Two stylesheets swap on route. Overkill for 3 token values. | |

**User's choice:** data-company attribute on <html>
**Notes:** Decision captured as D-06.

### Q7: How should FOWB protection be tested?

| Option | Description | Selected |
|--------|-------------|----------|
| RTL unit test on route flip (Recommended) | MemoryRouter + route flip + synchronous assertions in single act(). | ✓ |
| Visual screenshot diff | Playwright route + screenshots + compare. Requires adding Playwright to CI. | |
| Manual operator-eye check + log assertion | Cheapest but not regression-proof. | |

**User's choice:** RTL unit test on route flip
**Notes:** Decision captured as D-07.

---

## Opportunistic Polish

### Q8 (initial, multi-select): Which polish items should fold into Phase 13 scope?

| Option | Description | Selected (initial) |
|--------|-------------|---------------------|
| Browser tab title per tenant | document.title update from registry. ~3 lines. | ✓ |
| Favicon swap per tenant | <link rel='icon'> swap + 2 SVG assets. ~5 lines. | ✓ |
| Bare `/` redirect to last-visited tenant | TENANT-VISITED-v31-redux closure. ~5 lines. | ✓ |
| None — keep Phase 13 minimal | Scope strictly to BRAND-01..05. | ✓ (contradictory) |

**Initial answer was inconsistent** — user selected all 4 options including the contradictory "None". Orchestrator re-asked Q8b for clarification.

### Q8b (single-select clarification): Which polish items actually fold in?

| Option | Description | Selected |
|--------|-------------|----------|
| All 3 polish items | Browser tab title + favicon swap + bare `/` redirect. ~15 lines total. | ✓ |
| Tab title + redirect (skip favicon) | Skip favicon to avoid SVG asset design step. | |
| Bare `/` redirect only | Close TENANT-VISITED-v31-redux gap only. Most conservative. | |
| None — keep Phase 13 minimal | Scope strictly to BRAND-01..05. | |

**User's choice:** All 3 polish items
**Notes:** Decision captured as D-08 (subdivided into D-08a tab title / D-08b favicon / D-08c bare-`/` redirect).

---

## Claude's Discretion

- Exact OKLCH values for `--brand-accent-hover` + `--brand-accent-subtle` — starting points given in D-01 + `<specifics>`, planner refines + visual QA verifies during ui-phase / plan-phase.
- Implementation site for the router-layer `dataset.company` effect — likely `TabbedDashboard.tsx` or a new `<CompanyBrandEffect />` component; planner picks.
- Whether to ship a CI grep script (mirror `verify-anthropic-resolver.sh`) for D-10 component-branchless enforcement, or keep it as a manual code-review gate. Planner picks based on perceived regression risk.
- AppHeader test file structure — extend existing `AppHeader.test.tsx` vs split FOWB test into new `AppHeader.brand.test.tsx`. Planner picks based on test grouping clarity.

## Deferred Ideas

- SVG logo upgrade for Juno — deferred to v3.2+ polish.
- Light theme per-tenant variant — out of scope (no light theme exists).
- Formal WCAG axe-core integration — deferred to future a11y phase.
- Per-tenant fonts — out of scope.
- Mobile-responsive header collapse — desktop-only constraint preserved.
