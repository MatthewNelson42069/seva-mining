/**
 * Zustand companySlice — last-visited tenant tracking (TENANT-07).
 *
 * v3.0 Phase 9 (D-05, D-07, D-08): the lastVisitedCompany field is populated
 * by CompanyScopedRoute's useEffect on every :company route mount. The value
 * is persisted under the localStorage key `seva-mining-app-state-v3` via the
 * `persist` middleware wired in `stores/index.ts`.
 *
 * Default is `null` (NOT 'seva') — v3.0 bare `/` redirect is hardcoded to
 * `/seva/` per CONTEXT D-05; the persisted lastVisitedCompany is a byproduct
 * reserved for the v3.1+ "last-visited landing" feature.
 */
export type CompanyId = 'seva' | 'juno'

export interface CompanySlice {
  lastVisitedCompany: CompanyId | null
  setLastVisitedCompany: (c: CompanyId) => void
}

export function createCompanySlice(
  set: (
    fn: (state: CompanySlice) => Partial<CompanySlice>,
    replace?: boolean,
  ) => void,
): CompanySlice {
  return {
    lastVisitedCompany: null,  // D-05 — default null until first :company route mount
    setLastVisitedCompany: (c) => set(() => ({ lastVisitedCompany: c })),
  }
}
