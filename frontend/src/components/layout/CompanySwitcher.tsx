import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'

/**
 * v3.0 Phase 9 — CompanySwitcher segmented control (TENANT-07, D-07, D-08).
 *
 * Two side-by-side buttons (Seva | Juno). Active state derived from
 * `useParams<{company: string}>()` — URL is canonical (per
 * ARCHITECTURE.md D-03). Switching tenants:
 *   1. queryClient.clear() — defence-in-depth cache invalidation (D-08)
 *   2. navigate(`/${nextCompany}${currentSubPath || '/'}`) — preserves tab
 *
 * Element type is `<button type="button">` (NOT `<NavLink>`) so the cache
 * clear can run BEFORE the navigate atomically inside one onClick handler.
 *
 * Visual contract per 09-UI-SPEC.md §CompanySwitcher canonical contract —
 * all amber tokens are semantic (border-brand-accent / text-brand-accent /
 * bg-brand-accent-subtle), NOT literal amber-*.
 */
const COMPANIES = [
  { id: 'seva' as const, label: 'Seva' },
  { id: 'juno' as const, label: 'Juno' },
]

export function CompanySwitcher() {
  const { company: active } = useParams<{ company: string }>()
  const navigate = useNavigate()
  const location = useLocation()
  const queryClient = useQueryClient()

  function switchTo(next: 'seva' | 'juno') {
    // Already-active click is a no-op (no clear, no navigate).
    if (next === active) return
    // Strip the current tenant prefix; remainder is the sub-path
    // (e.g. /seva/calendar -> /calendar; /seva -> '').
    const subPath = location.pathname.replace(/^\/(seva|juno)/, '')
    queryClient.clear()
    navigate(`/${next}${subPath || '/'}`)
  }

  const baseClasses =
    'px-3 py-1.5 text-sm font-medium rounded-md border transition-colors ' +
    'focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-accent ' +
    'focus-visible:ring-offset-1 focus-visible:ring-offset-zinc-900'

  return (
    <div className="inline-flex gap-1">
      {COMPANIES.map((c) => {
        const isActive = active === c.id
        const stateClasses = isActive
          ? 'border-brand-accent text-brand-accent bg-brand-accent-subtle'
          : 'border-zinc-800 text-zinc-400 hover:border-zinc-700 hover:text-zinc-100'
        return (
          <button
            key={c.id}
            type="button"
            aria-current={isActive ? 'page' : undefined}
            onClick={() => switchTo(c.id)}
            className={`${baseClasses} ${stateClasses}`}
          >
            {c.label}
          </button>
        )
      })}
    </div>
  )
}
