import { useParams } from 'react-router-dom'
import { useAppStore } from '@/stores'
import { companyBrandConfig, type BrandConfig } from '@/config/companyBrandConfig'

/**
 * Resolves the active tenant's BrandConfig — Phase 13 D-05.
 *
 * Resolution chain (highest priority first):
 *   1. URL `:company` segment via `useParams<{company}>()` — present when the
 *      hook runs inside the `<Route path=":company">` subtree.
 *   2. Zustand `lastVisitedCompany` — populated as a switch-action byproduct
 *      in v3.0 Phase 9 (`CompanySwitcher.tsx`). Used when this hook runs
 *      ABOVE the `:company` route (e.g., `<AppHeader />` mounted in
 *      `<AppShell />` — the AppShell layout itself is outside the
 *      tenant-scoped subtree).
 *   3. `'seva'` hardcoded final fallback — pre-Phase-9 default; covers the
 *      first-ever page load before any switcher click has populated Zustand.
 *
 * Returns a strictly-typed BrandConfig — the consumer never sees `undefined`.
 */
export function useCompanyBrand(): BrandConfig {
  const params = useParams<{ company?: 'seva' | 'juno' }>()
  const lastVisited = useAppStore((s) => s.lastVisitedCompany)

  let resolved: 'seva' | 'juno'
  if (params.company === 'seva' || params.company === 'juno') {
    resolved = params.company
  } else if (lastVisited === 'seva' || lastVisited === 'juno') {
    resolved = lastVisited
  } else {
    resolved = 'seva'
  }

  return companyBrandConfig[resolved]
}
