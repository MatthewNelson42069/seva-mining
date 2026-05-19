/**
 * Centralized TanStack Query key factory (TENANT-09).
 *
 * Every multi-tenant query MUST go through these helpers so the cache
 * never accidentally serves Juno data to a Seva-tab observer (or vice
 * versa). Defence-in-depth on top of company-prefixed URLs (D-08).
 *
 * The `as const` makes the tuple literal so TanStack's structural key
 * equality is sound.
 */
export type CompanyId = 'seva' | 'juno'

export const queryKeys = {
  summaries: (companyId: CompanyId, limit: number) =>
    ['summaries', companyId, limit] as const,

  calendar: (companyId: CompanyId, start: string, end: string) =>
    ['calendar', companyId, start, end] as const,

  weeklySweeps: (companyId: CompanyId, limit: number) =>
    ['weekly-sweeps', companyId, limit] as const,
}
