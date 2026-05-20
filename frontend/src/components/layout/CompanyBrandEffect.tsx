import { useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { companyBrandConfig } from '@/config/companyBrandConfig'

/**
 * Phase 13 D-06 / D-08a / D-08b — Router-layer brand effect.
 *
 * Mounts inside `<Route path=":company">` (sibling of <TabbedDashboard />)
 * so `useParams` resolves to the active tenant synchronously on every route
 * mount. Sets three pieces of global state in a single effect:
 *
 *   1. `document.documentElement.dataset.company = company` — triggers the
 *      `:root.dark[data-company='juno']` CSS override in `index.css`.
 *      Browsers apply the token cascade atomically with the route's first
 *      paint — no FOWB.
 *   2. `document.title = config.pageTitle` — browser tab title (D-08a).
 *   3. `<link rel="icon">` href = `config.faviconHref` — favicon swap (D-08b).
 *
 * Cleanup on unmount reverts dataset.company to 'seva' (the historical
 * default) and document.title to 'Seva Mining' (matches `index.html`'s
 * `<title>` after the planner updates it from the Vite-scaffold "frontend").
 * Favicon is left at the last-visited tenant's icon — see "Why no favicon
 * cleanup" below.
 *
 * Vite is CSR-only — no SSR hydration mismatch concerns.
 *
 * Renders nothing.
 */
export function CompanyBrandEffect() {
  const { company } = useParams<{ company: 'seva' | 'juno' }>()

  useEffect(() => {
    if (company !== 'seva' && company !== 'juno') return
    const config = companyBrandConfig[company]

    document.documentElement.dataset.company = company
    document.title = config.pageTitle
    const iconLink = document.querySelector<HTMLLinkElement>("link[rel='icon']")
    if (iconLink) iconLink.href = config.faviconHref

    return () => {
      document.documentElement.dataset.company = 'seva'
      document.title = 'Seva Mining'
      // Favicon intentionally NOT restored on cleanup — browsers cache
      // favicons aggressively (cross-ref ROADMAP P5) and rapidly toggling
      // <link rel='icon'> href during route transitions causes flicker.
      // The next mount's effect (immediately after this cleanup runs during
      // a /seva ↔ /juno switch) will set the correct favicon synchronously.
    }
  }, [company])

  return null
}
