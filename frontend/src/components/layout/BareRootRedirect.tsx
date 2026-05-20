import { Navigate } from 'react-router-dom'
import { useAppStore } from '@/stores'

/**
 * Phase 13 D-08c — Bare-`/` redirect honoring the user's last-visited tenant.
 *
 * Closes the v3.0 TENANT-VISITED-v31-redux deferred gap: the Zustand
 * `lastVisitedCompany` field has been populated since Phase 9 as a
 * `<CompanySwitcher />` action byproduct, but no route consumed it. Now
 * the bare-`/` route uses it for the one-shot redirect:
 *
 *   - Returning user who last visited `/juno` → redirected to `/juno`
 *   - First-ever visitor (Zustand null) or unknown value → fallback `/seva`
 *
 * Uses `useAppStore.getState()` — the NON-reactive Zustand read — because
 * this is a one-shot redirect on mount. The reactive form
 * `useAppStore(s => s.lastVisitedCompany)` would re-render this component
 * on every store update (e.g., when CompanySwitcher writes a new value
 * during the redirected route's mount), causing redundant <Navigate>
 * re-evaluations. See D-08c for the rationale.
 */
export function BareRootRedirect() {
  const lastVisited = useAppStore.getState().lastVisitedCompany
  const tenant = lastVisited === 'juno' ? 'juno' : 'seva'
  return <Navigate to={`/${tenant}`} replace />
}
