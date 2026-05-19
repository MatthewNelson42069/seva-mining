import { useQuery } from '@tanstack/react-query'
import { getCalendar, type CalendarRangeResponse } from '@/api/calendar'

/**
 * v2.1 Phase 6 — useCalendar query hook (CAL-10).
 *
 * Locked behavior per 06-CONTEXT.md D-11:
 *   - staleTime: 0 — calendar items are user-mutated, no stale tolerance.
 *   - refetchOnWindowFocus: false — but no auto-refetch on tab switching either.
 *
 * queryKey: ['calendar', start, end] — the optimistic-mutation hooks in
 * useCalendarMutations.ts invalidate this EXACT key onSettled, so the
 * tuple shape MUST match.
 */
export function useCalendar(start: string, end: string) {
  return useQuery<CalendarRangeResponse>({
    queryKey: ['calendar', start, end],
    queryFn: () => getCalendar(start, end),
    staleTime: 0,
    refetchOnWindowFocus: false,
  })
}
