---
phase: 13-per-company-branding
plan: 01
subsystem: frontend-foundation
tags: [branding, multi-tenant, registry, css-tokens, foundation]
dependency-graph:
  requires:
    - "frontend/src/stores (Zustand lastVisitedCompany — Phase 9)"
    - "react-router-dom useParams (existing)"
    - ":company route subtree in App.tsx (Phase 9)"
  provides:
    - "companyBrandConfig: Record<'seva'|'juno', BrandConfig> registry"
    - "useCompanyBrand(): BrandConfig hook with URL → Zustand → 'seva' fallback"
    - "Per-tenant favicon SVGs at /brand/seva.svg + /brand/juno.svg"
    - ":root.dark[data-company='juno'] CSS token override block"
    - "Default <title>Seva Mining</title> for first-paint / unauthenticated views"
  affects:
    - "frontend/src/index.css (additive 11-line block; Phase 8 amber preserved)"
    - "frontend/index.html (title swap; no other tags touched)"
tech-stack:
  added: []
  patterns:
    - "Per-tenant config registry (extends Phase 9 D-08 companySectionConfig.ts shape)"
    - "CSS custom-property override via documentElement data-attribute (D-06)"
    - "OKLCH string-equality cross-file invariant (registry ↔ index.css ↔ favicon SVG)"
key-files:
  created:
    - frontend/src/config/companyBrandConfig.ts
    - frontend/src/hooks/useCompanyBrand.ts
    - frontend/public/brand/seva.svg
    - frontend/public/brand/juno.svg
  modified:
    - frontend/src/index.css
    - frontend/index.html
decisions:
  - "Selector ':root.dark[data-company=juno]' chosen over ':root[data-company=juno]' to mirror Phase 8 .dark scoping (D-06 + UI-SPEC §Why .dark qualifier)"
  - "OKLCH triple finalized at oklch(0.58 0.14 245) / oklch(0.65 0.14 245) / oklch(0.58 0.14 245 / 0.05) — locked from UI-SPEC Color section, NOT D-01 starting point"
  - "Hook fallback chain ordered URL → Zustand → 'seva' (D-05) — handles both ABOVE-':company'-route consumers (AppHeader in AppShell) and INSIDE-':company' consumers"
  - "Registry palette field documented as DOCUMENTATION-ONLY (single source of truth for OKLCH values is index.css)"
metrics:
  duration_minutes: 4
  completed_date: "2026-05-20"
  tasks_completed: 2
  files_created: 4
  files_modified: 2
  tests_passing: "168/168 (zero regression)"
---

# Phase 13 Plan 01: Per-company Branding Foundation Summary

Landed the per-tenant branding foundation: registry of record (`companyBrandConfig.ts`), resolution hook (`useCompanyBrand.ts`), two favicon SVG assets, the `:root.dark[data-company='juno']` CSS override block, and the default browser-tab title fix. No consumer is wired yet — Plan 13-02 (Wave 2) refactors `AppHeader.tsx` and mounts `<CompanyBrandEffect />`.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Create companyBrandConfig registry + useCompanyBrand hook | `b0edf68` | `frontend/src/config/companyBrandConfig.ts`, `frontend/src/hooks/useCompanyBrand.ts` |
| 2 | Create 2 favicon SVGs + add CSS override block + fix index.html title | `406c8b9` | `frontend/public/brand/seva.svg`, `frontend/public/brand/juno.svg`, `frontend/src/index.css`, `frontend/index.html` |

## Artifacts Landed (verbatim from UI-SPEC)

### `frontend/src/config/companyBrandConfig.ts` (NEW)
- `Record<'seva' | 'juno', BrandConfig>` with both entries fully populated (no TODOs).
- Fields: `wordmark`, `markLetter`, `markBgClassName: 'bg-brand-accent'` (both tenants), `palette {accent, accentHover, accentSubtle}`, `pageTitle`, `faviconHref`.
- Seva wordmark `'Seva Mining'`, mark `'S'`, accent `oklch(0.769 0.188 70.08)`, page title `'Seva Mining'`, favicon `/brand/seva.svg`.
- Juno wordmark `'Juno Industries'`, mark `'J'`, accent `oklch(0.58 0.14 245)`, page title `'Juno Industries'`, favicon `/brand/juno.svg`.

### `frontend/src/hooks/useCompanyBrand.ts` (NEW)
- Exports `useCompanyBrand(): BrandConfig`.
- Fallback chain strictly enforced: `useParams<{company}>()` → Zustand `useAppStore((s) => s.lastVisitedCompany)` → `'seva'` hardcoded default.
- Import path `from '@/config/companyBrandConfig'` (verified `@/` alias works via `grep -rn "from '@/stores'"`).

### `frontend/public/brand/seva.svg` (NEW — 292 bytes)
- Single-line SVG with `<rect fill="oklch(0.769 0.188 70.08)"/>` + `<text fill="oklch(0.145 0 0)">S</text>`.
- `viewBox="0 0 32 32"`, no trailing newline (hex tail verified `73 76 67 3e` = `svg>`).

### `frontend/public/brand/juno.svg` (NEW — 288 bytes)
- Single-line SVG with `<rect fill="oklch(0.58 0.14 245)"/>` + `<text fill="oklch(0.145 0 0)">J</text>`.
- Same DOM shape as `seva.svg`, no trailing newline.

### `frontend/src/index.css` (MODIFIED — additive 11-line block)
- Phase 13 block inserted between the existing `.dark { ... }` closing brace (line 127) and `@layer base { ... }` (now at line 141).
- Selector `:root.dark[data-company='juno']` (specificity 0,2,0) beats `.dark` (specificity 0,1,0). The `.dark` qualifier is required because Phase 8 amber tokens live INSIDE `.dark` (lines 124-126).
- Three Juno OKLCH tokens: base `oklch(0.58 0.14 245)`, hover `oklch(0.65 0.14 245)`, subtle `oklch(0.58 0.14 245 / 0.05)`.
- Phase 8 amber tokens at lines 124-126 BYTE-IDENTICAL to pre-Phase-13 state (D-09 zero regression confirmed via `grep -n "0.769 0.188 70.08"` returning lines 124 + 126, with hover `0.828 0.189 84.429` at line 125).

### `frontend/index.html` (MODIFIED — single-line title swap)
- Line 7: `<title>frontend</title>` → `<title>Seva Mining</title>`.
- All other tags (charset, favicon link, viewport meta, root div, script) byte-identical.

## Byte Sizes (must be 200-800 each per acceptance criteria)

| File | Bytes | Pass? |
|------|------:|------:|
| `frontend/public/brand/seva.svg` | 292 | YES |
| `frontend/public/brand/juno.svg` | 288 | YES |

## OKLCH String-Equality Invariant (cross-file)

The Juno accent OKLCH string `oklch(0.58 0.14 245)` appears in exactly 3 files (registry + CSS override + favicon SVG), confirming the visual-consistency contract:

```
$ grep -l 'oklch(0.58 0.14 245)' frontend/src/index.css frontend/public/brand/juno.svg frontend/src/config/companyBrandConfig.ts | wc -l
3
```

The Seva accent OKLCH string `oklch(0.769 0.188 70.08)` also appears in 3 files (the existing pre-Phase-13 `index.css` line 124, the new `seva.svg`, and the new registry). String-equality holds for both tenants.

## D-09 Zero-Regression Verification

Phase 8 amber tokens at `frontend/src/index.css:124-126` byte-identical to pre-Phase-13 state:

```css
124:    --brand-accent: oklch(0.769 0.188 70.08);
125:    --brand-accent-hover: oklch(0.828 0.189 84.429);
126:    --brand-accent-subtle: oklch(0.769 0.188 70.08 / 0.05);
```

Confirmed via `awk '/^\.dark \{/,/^}/' frontend/src/index.css | grep -c "data-company"` returning `0` — the override block is OUTSIDE the `.dark` block, not inside it.

Full frontend test suite: **28 test files, 168 tests, all passing**. Existing `AppHeader.test.tsx` (4 tests) unchanged and green. No consumer was refactored in this plan, so D-09's byte-identical Seva output guarantee holds vacuously at the rendering layer.

## Phase-Level Verification Run

| Check | Command | Result |
|-------|---------|--------|
| 1. TSC clean for new files | `npx tsc --noEmit` filtered for `companyBrandConfig\|useCompanyBrand` | NO ERRORS |
| 2. Full frontend test suite | `npm test -- --run` | 168/168 PASS |
| 3. Cross-file OKLCH equality | `grep -l 'oklch(0.58 0.14 245)' <3 files>` | 3/3 files present |
| 4. Phase 8 amber preserved | `grep -n "0.769 0.188 70.08" frontend/src/index.css` | lines 124 + 126 present |
| 5. Override placement | `awk '/^\.dark \{/,/^}/' frontend/src/index.css \| grep -c "data-company"` | 0 (outside .dark, correct) |
| 6. AppHeader regression | `npm test -- --run AppHeader.test.tsx` | 4/4 PASS |

## Deviations from Plan

### Acceptance-criterion grep wording (NOT a code deviation — verification-command quirk)

The plan's acceptance criterion for Task 2 stated `grep -c "oklch(0.58 0.14 245)" frontend/src/index.css returns at least 2 (base + alpha variant in override block)`. `grep -c` counts MATCHING LINES, not occurrences. The override block has two lines containing `oklch(0.58 0.14 245`:

```
136:    --brand-accent: oklch(0.58 0.14 245);
138:    --brand-accent-subtle: oklch(0.58 0.14 245 / 0.05);
```

But only line 136 contains the exact literal substring `oklch(0.58 0.14 245)` (with the `)` immediately after `245`). Line 138 has `oklch(0.58 0.14 245 / 0.05)` — the `)` is preceded by `0.05` not `245`. Therefore `grep -c "oklch(0.58 0.14 245)" frontend/src/index.css` returns `1`, not `≥ 2`.

**The CONTENT is correct and verbatim per UI-SPEC Artifact 2** (all three Juno OKLCH tokens — base, hover, subtle — are present and match exactly). Verified independently with per-line anchored grep:

```
$ grep -cE "^\s*--brand-accent: oklch\(0\.58 0\.14 245\);" frontend/src/index.css           # → 1
$ grep -cE "^\s*--brand-accent-hover: oklch\(0\.65 0\.14 245\);" frontend/src/index.css     # → 1
$ grep -cE "^\s*--brand-accent-subtle: oklch\(0\.58 0\.14 245 / 0\.05\);" frontend/src/index.css  # → 1
```

This is a documentation-only mismatch between the plan's verification command and the actual UI-SPEC content. No code adjustment needed — UI-SPEC verbatim consumption invariant honored.

### Out-of-scope discoveries logged

Pre-existing lint errors (15 errors in test files, none touching `companyBrandConfig.ts` or `useCompanyBrand.ts`) logged to `.planning/phases/13-per-company-branding/deferred-items.md`. Out of scope for Plan 13-01 (foundation only); a future hygiene phase can address.

## Authentication Gates

None — Plan 13-01 is purely client-side configuration work with no API calls, secrets, or external services.

## Known Stubs

None. Both registry entries (`seva` + `juno`) are fully populated; the hook returns a strictly-typed `BrandConfig` (consumer never sees `undefined`); the CSS override block contains all three Juno OKLCH tokens; both favicon SVGs are complete.

The fact that no consumer is wired yet (AppHeader still renders hardcoded `bg-amber-500` + "S" + "Seva Mining") is NOT a stub — it is the intentional Wave 1 / Wave 2 split per the plan's `<objective>`. Plan 13-02 wires consumption.

## Notes for Plan 13-02 (Wave 2 — next wave)

When Plan 13-02 wires consumers:
- `AppHeader.tsx` line 19 (`bg-amber-500`) becomes `${brand.markBgClassName}` (resolves to `bg-brand-accent` for BOTH tenants — the per-tenant DIFFERENCE comes from the CSS-token override, NOT a Tailwind class swap).
- `AppHeader.tsx` line 20 (`"S"`) becomes `{brand.markLetter}`.
- `AppHeader.tsx` line 22 (`"Seva Mining"`) becomes `{brand.wordmark}`.
- Mount `<CompanyBrandEffect />` inside `<Route path=":company">` (sees `useParams`).
- The dataset effect (`document.documentElement.dataset.company = company`) is what activates the new CSS override block.
- Existing AppHeader test (Seva-default scenario, `<MemoryRouter initialEntries={['/seva']}>`) MUST continue to pass byte-identically.

## Self-Check: PASSED

- Files created exist on disk: `frontend/src/config/companyBrandConfig.ts`, `frontend/src/hooks/useCompanyBrand.ts`, `frontend/public/brand/seva.svg`, `frontend/public/brand/juno.svg` — all FOUND.
- Files modified exist on disk: `frontend/src/index.css`, `frontend/index.html` — both FOUND.
- Commits exist in git log: `b0edf68` (Task 1) + `406c8b9` (Task 2) — both FOUND.
- Frontend tests: 168/168 PASS, zero regression.
- All Task 1 + Task 2 acceptance criteria met (with one cosmetic documentation-only grep-wording quirk explained in Deviations).
