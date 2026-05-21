import { CompanySwitcher } from './CompanySwitcher'
import { useCompanyBrand } from '@/hooks/useCompanyBrand'

/**
 * Application header — cookie-token auth model (quick-260521-9ze).
 *
 * Logout button REMOVED: with cookie-token auth, there is no client-side
 * logout action (the HttpOnly cookie cannot be cleared from JS). Token
 * rotation is operator-controlled via Railway env var (see SUMMARY.md).
 * Per v3.0 Phase 9 freeze-lift: surgical edit — only the Logout button
 * and its handler are removed; brand mark + CompanySwitcher unchanged.
 */
export function AppHeader() {
  const brand = useCompanyBrand()

  return (
    <header className="border-b border-zinc-800 bg-zinc-900 sticky top-0 z-10">
      <div className="max-w-[720px] mx-auto px-4 py-3 flex items-center justify-between">
        {/* Brand mark — Phase 13 (D-04) registry-driven; Phase 9 D-02 freeze-lift +
            Phase 13 BRAND lift both apply. No per-tenant conditional branch (D-10). */}
        <div className="flex items-center gap-3">
          <div className={`w-7 h-7 rounded-md ${brand.markBgClassName} flex items-center justify-center shrink-0`}>
            <span className="text-xs font-bold text-zinc-900">{brand.markLetter}</span>
          </div>
          <span className="text-sm font-semibold text-white">{brand.wordmark}</span>
        </div>

        {/* v3.0 freeze-lift (Phase 9) — see 09-CONTEXT.md D-02 */}
        <CompanySwitcher />
      </div>
    </header>
  )
}
