import { useEffect } from 'react'
import { Navigate, Outlet, useParams } from 'react-router-dom'
import { useAppStore } from '@/stores'

/**
 * v3.0 Phase 9 — CompanyScopedRoute (TENANT-05, D-04, D-05, D-07).
 *
 * Wrapper route at `/:company` — validates the param against ACTIVE_COMPANIES,
 * publishes the active tenant to Zustand (for persistence under
 * `seva-mining-app-state-v3` per D-08), and renders <Outlet /> for nested
 * tabs.
 *
 * Pitfall #3 mitigation: this is the SINGLE chokepoint where `company` is
 * narrowed from `string | undefined` to `CompanyId`. Nested pages get a
 * guarantee the param is one of the valid slugs.
 *
 * Invalid slug graceful fallback (D-06): redirect to `/seva` instead of 404.
 */
const ACTIVE_COMPANIES = ['seva', 'juno'] as const
type CompanyId = (typeof ACTIVE_COMPANIES)[number]

function isCompanyId(value: string | undefined): value is CompanyId {
  return value !== undefined && (ACTIVE_COMPANIES as readonly string[]).includes(value)
}

export function CompanyScopedRoute() {
  const { company } = useParams<{ company: string }>()
  const setLastVisitedCompany = useAppStore((s) => s.setLastVisitedCompany)

  useEffect(() => {
    if (isCompanyId(company)) {
      setLastVisitedCompany(company)
    }
  }, [company, setLastVisitedCompany])

  if (!isCompanyId(company)) {
    // Invalid slug — graceful redirect to /seva/ (D-06).
    return <Navigate to="/seva" replace />
  }

  return <Outlet />
}
