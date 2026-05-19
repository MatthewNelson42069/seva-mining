import { format } from 'date-fns'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { getWeekEnd, getWeekStart } from '@/lib/week'

interface WeekNavProps {
  weekAnchor: Date
  onPrev: () => void
  onNext: () => void
  onToday: () => void
}

/**
 * v2.1 Phase 6 — Week navigation header (CAL-05 / D-08).
 *
 * Layout: [prev] [Today] [next]   <label>
 * The component is stateless w/r/t which week is showing; the parent
 * (ContentCalendarPage) owns `weekAnchor` state and updates it via the
 * three callbacks. WeeklyGrid renders the matching week independently.
 *
 * Year-boundary label rule: when the visible week spans Dec/Jan, both
 * halves include the year so the operator can disambiguate quickly.
 */
export function WeekNav({ weekAnchor, onPrev, onNext, onToday }: WeekNavProps) {
  const start = getWeekStart(weekAnchor)
  const end = getWeekEnd(weekAnchor)
  const sameYear = start.getFullYear() === end.getFullYear()
  const startLabel = sameYear
    ? format(start, 'MMM d')
    : format(start, 'MMM d, yyyy')
  const endLabel = format(end, 'MMM d, yyyy')

  return (
    <div className="flex items-center justify-between gap-3 mb-4">
      <div className="flex items-center gap-1.5">
        <Button
          variant="outline"
          size="sm"
          onClick={onPrev}
          aria-label="Previous week"
        >
          <ChevronLeft className="h-4 w-4" />
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={onToday}
          aria-label="Jump to today"
        >
          Today
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={onNext}
          aria-label="Next week"
        >
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>
      <span
        className="text-sm text-zinc-400"
        data-testid="week-range-label"
      >
        {startLabel} – {endLabel}
      </span>
    </div>
  )
}
