/**
 * Per-tenant brand identity registry — Phase 13 D-04.
 *
 * Mirrors the Phase 9 D-08 `companySectionConfig.ts` pattern: a single
 * `Record<'seva' | 'juno', T>` keyed on `company_id`, consumed by both
 * a React hook (`useCompanyBrand`) AND a router-layer effect
 * (`<CompanyBrandEffect />`) that sets `document.documentElement.dataset.company`
 * for the CSS-token override under `:root[data-company='juno']` (see
 * `frontend/src/index.css` Phase 13 block).
 *
 * Anti-pattern PROHIBITED (CONTEXT D-10):
 *   - Do NOT write `if (company === 'juno') { ... }` inside any file under
 *     `frontend/src/components/`. The registry IS the only allowed branch.
 *   - Adding a 3rd tenant requires (a) extending the `'seva' | 'juno'`
 *     union below, (b) adding a registry entry, and (c) adding a new
 *     `:root[data-company='X']` block to `index.css`. Three edits, three
 *     files. No component edits.
 *
 * The `palette` strings are DOCUMENTATION-ONLY references — actual token
 * values live in `index.css` (single source of truth for CSS values).
 * They exist so a reader of this file can see at a glance which OKLCH
 * triple each tenant resolves to without cross-referencing CSS.
 */

export interface BrandConfig {
  /** Wordmark string rendered in `AppHeader` (e.g., "Seva Mining"). */
  wordmark: string
  /** Single uppercase letter in the brand-mark square (e.g., "S"). */
  markLetter: string
  /** Tailwind class for the brand-mark square background. Always uses the
   *  semantic `bg-brand-accent` token so the override cascades automatically;
   *  this field exists for future flexibility (e.g., a tenant wanting a
   *  square outline instead of fill could change to `border-brand-accent
   *  border-2 bg-transparent` without touching AppHeader). */
  markBgClassName: string
  /** Documentation-only mirror of the CSS-resolved palette. SOURCE OF TRUTH
   *  for the actual token values lives in `frontend/src/index.css`. */
  palette: {
    accent: string        // OKLCH string for --brand-accent
    accentHover: string   // OKLCH string for --brand-accent-hover
    accentSubtle: string  // OKLCH string for --brand-accent-subtle (alpha)
  }
  /** Browser tab title — set by `<CompanyBrandEffect />` on route mount
   *  (CONTEXT D-08a). */
  pageTitle: string
  /** Absolute href for the per-tenant favicon SVG — set by
   *  `<CompanyBrandEffect />` mutating the existing `<link rel='icon'>`
   *  in `frontend/index.html` (CONTEXT D-08b). */
  faviconHref: string
}

export const companyBrandConfig: Record<'seva' | 'juno', BrandConfig> = {
  seva: {
    wordmark: 'Seva Mining',
    markLetter: 'S',
    markBgClassName: 'bg-brand-accent',
    palette: {
      accent: 'oklch(0.769 0.188 70.08)',
      accentHover: 'oklch(0.828 0.189 84.429)',
      accentSubtle: 'oklch(0.769 0.188 70.08 / 0.05)',
    },
    pageTitle: 'Seva Mining',
    faviconHref: '/brand/seva.svg',
  },
  juno: {
    wordmark: 'Juno Industries',
    markLetter: 'J',
    markBgClassName: 'bg-brand-accent',
    palette: {
      accent: 'oklch(0.58 0.14 245)',
      accentHover: 'oklch(0.65 0.14 245)',
      accentSubtle: 'oklch(0.58 0.14 245 / 0.05)',
    },
    pageTitle: 'Juno Industries',
    faviconHref: '/brand/juno.svg',
  },
}
