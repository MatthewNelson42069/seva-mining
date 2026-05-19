import { useCallback, useState } from 'react'
import { addDays } from 'date-fns'
import { useParams } from 'react-router-dom'
import { WeekNav } from '@/components/calendar/WeekNav'
import { WeeklyGrid } from '@/components/calendar/WeeklyGrid'
import type { CompanyId } from '@/api/queryKeys'

/**
 * v2.1 Phase 6 — Content Calendar page (CAL-05).
 *
 * State: `weekAnchor` (a Date inside the visible week). Defaults to today,
 * so the first paint shows the current ISO week with today's cell highlighted.
 *
 * Layout (inside TabbedDashboard's outer chrome from Phase 5):
 *   [WeekNav: prev / Today / next  |  May 18 – May 24, 2026]
 *   [WeeklyGrid: 7 Mon-Sun day cells]
 *
 * The page intentionally renders NO tab strip / header / nav — TabbedDashboard
 * already renders <TabNav /> above the <Outlet />. Adding another header here
 * would duplicate that chrome.
 *
 * Prev/Next move the anchor by ±7 days. Today resets the anchor to `new Date()`.
 * WeeklyGrid recomputes its Mon-Sun window from whatever anchor it gets.
 */
export default function ContentCalendarPage() {
  const { company } = useParams<{ company: string }>()
  const companyId = company as CompanyId  // narrowed by CompanyScopedRoute
  const [weekAnchor, setWeekAnchor] = useState<Date>(() => new Date())

  const handlePrev = useCallback(() => {
    setWeekAnchor((d) => addDays(d, -7))
  }, [])

  const handleNext = useCallback(() => {
    setWeekAnchor((d) => addDays(d, 7))
  }, [])

  const handleToday = useCallback(() => {
    setWeekAnchor(new Date())
  }, [])

  // v3.0 Phase 9 — Juno short-circuit per CONTEXT D-09. Render the
  // v3.1 empty-state BEFORE <WeeklyGrid> mounts so neither useCalendar
  // nor any of the mutation hooks fire (avoids a wasted /api/juno/calendar
  // round-trip that would only ever return an empty array in v3.0).
  if (companyId === 'juno') {
    return (
      <div className="max-w-[720px] mx-auto py-8 px-4">
        <p className="text-sm text-muted-foreground">
          Coming in v3.1 — Juno Calendar not yet enabled.
        </p>
      </div>
    )
  }

  return (
    <div className="px-4 py-6">
      <WeekNav
        weekAnchor={weekAnchor}
        onPrev={handlePrev}
        onNext={handleNext}
        onToday={handleToday}
      />
      <WeeklyGrid companyId={companyId} weekAnchor={weekAnchor} />
    </div>
  )
}
