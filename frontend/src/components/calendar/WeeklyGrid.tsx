import { useMemo } from 'react'
import { isSameDay } from 'date-fns'
import { DayCell } from './DayCell'
import { formatDateISO, getWeekDays, getWeekEnd, getWeekStart } from '@/lib/week'
import { useCalendar } from '@/hooks/useCalendar'
import type { CompanyId } from '@/api/queryKeys'

interface WeeklyGridProps {
  /** Tenant slot (TENANT-09) — threaded into useCalendar + mutation hooks. */
  companyId: CompanyId
  /** Any date within the week to render. The grid computes Mon-Sun from this. */
  weekAnchor: Date
}

/**
 * v2.1 Phase 6 — 7-column Mon-Sun weekly grid (CAL-05).
 *
 * Composition: WeeklyGrid owns the data fetch (useCalendar) and the
 * day-to-item mapping; DayCell owns the per-cell editing state and
 * auto-save branching. This split lets the WeeklyGrid stay a thin
 * coordinator while DayCell handles all of CAL-06/07/08.
 *
 * Notes for the page-level orchestration (Plan 06-05):
 *   - Prev/next/Today navigation lives at the page, not here. WeeklyGrid
 *     is stateless w/r/t which week it shows; it just renders the week
 *     containing `weekAnchor`.
 *   - Query error is surfaced inline; mutation errors are toasted from
 *     useCalendarMutations. We deliberately do NOT also toast query errors
 *     here — the inline message is enough and avoids double-surfacing.
 */
export function WeeklyGrid({ companyId, weekAnchor }: WeeklyGridProps) {
  // `today` is captured once per render of this component instance.
  // Page-level reloads / week navigation will re-mount or re-evaluate
  // naturally; we don't need ticking precision here (the today highlight
  // only matters at day granularity).
  const today = useMemo(() => new Date(), [])

  const weekRange = useMemo(
    () => ({
      start: formatDateISO(getWeekStart(weekAnchor)),
      end: formatDateISO(getWeekEnd(weekAnchor)),
    }),
    [weekAnchor],
  )

  const days = useMemo(() => getWeekDays(weekAnchor), [weekAnchor])

  const { data, isLoading, isError, error } = useCalendar(
    companyId,
    weekRange.start,
    weekRange.end,
  )

  if (isError) {
    return (
      <div className="rounded-lg border border-red-900/40 bg-red-950/20 p-4 text-sm text-red-300">
        Failed to load calendar:{' '}
        {error instanceof Error ? error.message : 'unknown error'}
      </div>
    )
  }

  const items = data?.items ?? []

  return (
    <div
      className="grid grid-cols-7 gap-2"
      aria-busy={isLoading || undefined}
      data-testid="weekly-grid"
    >
      {days.map((d) => {
        const iso = formatDateISO(d)
        const item = items.find((it) => it.date === iso) ?? null
        return (
          <DayCell
            key={iso}
            companyId={companyId}
            date={d}
            item={item}
            weekRange={weekRange}
            isToday={isSameDay(d, today)}
          />
        )
      })}
    </div>
  )
}
