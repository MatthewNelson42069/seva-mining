import { useQuery } from '@tanstack/react-query'
import { getCalendar, type CalendarRangeResponse } from '@/api/calendar'
import { queryKeys, type CompanyId } from '@/api/queryKeys'

/**
 * v2.1 Phase 6 / v3.0 Phase 9 — useCalendar query hook (CAL-10, TENANT-09).
 *
 * Locked behavior per 06-CONTEXT.md D-11:
 *   - staleTime: 0 — calendar items are user-mutated, no stale tolerance.
 *   - refetchOnWindowFocus: false — but no auto-refetch on tab switching either.
 *
 * queryKey: queryKeys.calendar(companyId, start, end) — tuple shape
 * ['calendar', companyId, start, end]. The optimistic-mutation hooks in
 * useCalendarMutations.ts invalidate this EXACT key onSettled, so the
 * tuple shape MUST match.
 */
export function useCalendar(companyId: CompanyId, start: string, end: string) {
  return useQuery<CalendarRangeResponse>({
    queryKey: queryKeys.calendar(companyId, start, end),
    queryFn: () => getCalendar(companyId, start, end),
    staleTime: 0,
    refetchOnWindowFocus: false,
  })
}
