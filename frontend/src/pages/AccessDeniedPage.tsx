import { useCompanyBrand } from '@/hooks/useCompanyBrand'

/**
 * Shown when the browser has no valid seva_auth_token cookie.
 * Cookie-token auth model — quick-260521-9ze.
 *
 * NO inputs. NO forms. NO buttons. NO "log in" CTA.
 * The only affordance is the bookmark link — shared out-of-band.
 * Per-tenant wordmark is sourced from useCompanyBrand() (D-08, D-10).
 */
export function AccessDeniedPage() {
  const brand = useCompanyBrand()
  return (
    <div className="min-h-screen bg-white flex items-center justify-center">
      <div className="w-full max-w-sm px-8 py-10 text-center">
        <h1 className="text-2xl font-semibold text-gray-900 tracking-tight">
          {brand.wordmark}
        </h1>
        <h2 className="text-base font-medium text-gray-800 mt-8">
          Access required
        </h2>
        <p className="text-sm text-gray-500 mt-2">
          This dashboard is accessed via a private bookmark link.
          Contact the operator if you don&apos;t have one.
        </p>
      </div>
    </div>
  )
}
