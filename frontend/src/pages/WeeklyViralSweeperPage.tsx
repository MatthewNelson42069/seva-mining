import { useState } from 'react'
import { addDays, format, parseISO, startOfWeek } from 'date-fns'

import { useWeeklySweeps } from '@/api/weeklySweeps'
import { SweeperCard } from '@/components/viral/SweeperCard'

/**
 * Compute the next Sunday date label for the empty-state copy (SWEEP-14).
 *
 * Returns "May 24, 2026" style string. Boundary handling: if today is Sunday
 * before 08:00 PT, returns today; otherwise returns the next Sunday.
 *
 * The boundary case (Sunday before 08:00 PT) is intentionally imperfect — the
 * empty state ONLY renders when total: 0, so this edge case only matters until
 * the first cron fire ever. Once there's any row, the empty state never
 * renders again.
 */
function nextSundayLabel(now: Date = new Date()): string {
  const sundayThisWeek = startOfWeek(now, { weekStartsOn: 0 })
  const isPastThisWeeksFire =
    sundayThisWeek.getTime() < now.getTime() &&
    (now.getDay() !== 0 || now.getHours() >= 8)
  const target = isPastThisWeeksFire ? addDays(sundayThisWeek, 7) : sundayThisWeek
  return format(target, 'MMM d, yyyy')
}

/**
 * Top-level Weekly Viral Sweeper page (Phase 7, Plan 06).
 *
 * Layout: max-w-[720px] single-column, matching SummaryFeedPage (D-19).
 * - Default view: latest sweep (sweeps[0])
 * - History dropdown: select prior weeks for browsing (SWEEP-13, D-20)
 * - Empty state (total: 0): SWEEP-14 copy
 *   "Sweeper has not run yet — first fire scheduled for Sunday {next_sunday} 08:00 PT."
 */
export default function WeeklyViralSweeperPage() {
  const { data, isLoading, error } = useWeeklySweeps(12)
  const [selectedId, setSelectedId] = useState<string | null>(null)

  if (isLoading) {
    return (
      <div className="max-w-[720px] mx-auto py-8 px-4">
        <p className="text-sm text-muted-foreground">Loading…</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="max-w-[720px] mx-auto py-8 px-4">
        <p className="text-sm text-destructive">Failed to load weekly sweeps.</p>
      </div>
    )
  }

  const sweeps = data?.sweeps ?? []

  if (sweeps.length === 0) {
    const nextFire = nextSundayLabel()
    return (
      <div className="max-w-[720px] mx-auto py-8 px-4">
        <p className="text-sm text-muted-foreground">
          Sweeper has not run yet — first fire scheduled for Sunday {nextFire} 08:00 PT.
        </p>
      </div>
    )
  }

  const selected =
    (selectedId ? sweeps.find((s) => s.id === selectedId) : sweeps[0]) ?? sweeps[0]

  return (
    <div className="max-w-[720px] mx-auto py-8 px-4 space-y-6">
      {sweeps.length > 1 && (
        <div className="flex items-center gap-2">
          <label htmlFor="week-picker" className="text-sm text-muted-foreground">
            Week:
          </label>
          <select
            id="week-picker"
            value={selected.id}
            onChange={(e) => setSelectedId(e.target.value)}
            className="rounded border bg-background px-3 py-1.5 text-sm text-foreground"
          >
            {sweeps.map((s) => {
              const startLbl = format(parseISO(s.week_start), 'MMM d')
              const endLbl = format(parseISO(s.week_end), 'MMM d, yyyy')
              return (
                <option key={s.id} value={s.id}>
                  {startLbl} – {endLbl} ({s.status})
                </option>
              )
            })}
          </select>
        </div>
      )}

      <SweeperCard sweep={selected} />
    </div>
  )
}
