import { useEffect, useRef, useState } from 'react'
import { format } from 'date-fns'
import { cn } from '@/lib/utils'
import { formatDateISO } from '@/lib/week'
import type { CalendarItem } from '@/api/calendar'
import type { CompanyId } from '@/api/queryKeys'
import {
  useCreateCalendarItem,
  useDeleteCalendarItem,
  useUpdateCalendarItem,
} from '@/hooks/useCalendarMutations'

interface DayCellProps {
  companyId: CompanyId
  date: Date
  item: CalendarItem | null
  weekRange: { start: string; end: string }
  isToday: boolean
}

/**
 * v2.1 Phase 6 — single day cell of the WeeklyGrid (CAL-05..CAL-08).
 *
 *   D-01: the day cell IS a textarea. No dialog, no popover.
 *   D-03: auto-save on blur (silent success, sonner error toast via mutation hooks).
 *   D-05: clearing the textarea deletes the row.
 *   D-09: today cell highlighted with `ring-2 ring-amber-500 bg-amber-500/5`.
 *   CAL-06: persisted text rendered with `whitespace-pre-wrap` so line breaks
 *           survive the textarea -> render round-trip.
 *   CAL-07: clicking the cell focuses the textarea — implemented by making the
 *           textarea fill the cell area and adding `cursor-text` to the outer
 *           wrapper, plus a manual onClick fallback that focuses the ref.
 *
 * IMPORTANT: this component uses a NATIVE textarea rather than the shadcn
 * Textarea primitive (frontend/src/components/ui/textarea.tsx). The shadcn
 * version is a plain function component — it does NOT forwardRef — so
 * attaching `ref={textareaRef}` to it would not work. CAL-07 requires the
 * outer cell's onClick to call `textareaRef.current?.focus()`, which only
 * works against a real DOM textarea ref. Inlining the textarea here keeps
 * the focus contract obvious and avoids reaching into the shadcn primitive.
 */
export function DayCell({ companyId, date, item, weekRange, isToday }: DayCellProps) {
  const [current, setCurrent] = useState<string>(item?.body ?? '')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const mutationOpts = { companyId, ...weekRange }
  const createMutation = useCreateCalendarItem(mutationOpts)
  const updateMutation = useUpdateCalendarItem(mutationOpts)
  const deleteMutation = useDeleteCalendarItem(mutationOpts)

  // Reconcile local state when the persisted item changes (e.g. after
  // optimistic invalidation refetch, week navigation, or another tab's edit).
  // v2.1 Phase 6 pattern: sync local textarea state when the server-side row
  // changes. Refactoring to a derive-from-props key+remount pattern would lose
  // the user's in-flight edits during a background refetch — this synchronous
  // setState IS the intended reconciliation, not a cascade-render bug.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setCurrent(item?.body ?? '')
  }, [item?.id, item?.body])

  function handleBlur() {
    const trimmed = current.trim()
    const persisted = item?.body ?? ''

    // Branch 1: empty AND no row -> noop (don't fire a request).
    if (trimmed === '' && item == null) return

    // Branch 2: empty AND row exists -> DELETE (D-05).
    if (trimmed === '' && item != null) {
      deleteMutation.mutate(item.id)
      return
    }

    // Branch 3: non-empty AND no row -> POST (first save).
    if (trimmed !== '' && item == null) {
      createMutation.mutate({
        date: formatDateISO(date),
        body: current,
      })
      return
    }

    // Branch 4 & 5: non-empty AND row exists -> PATCH only if changed (idle guard).
    if (trimmed !== '' && item != null) {
      if (current === persisted) return // idle save guard
      updateMutation.mutate({ id: item.id, payload: { body: current } })
    }
  }

  const dayLabel = format(date, 'EEE') // 'Mon', 'Tue', ...
  const dayNumber = format(date, 'd') // '18', '19', ...

  return (
    <div
      className={cn(
        'flex flex-col rounded-lg border border-zinc-800 bg-zinc-900/30 p-2 min-h-32 max-h-64 overflow-y-auto cursor-text transition-colors hover:border-zinc-700',
        isToday && 'ring-2 ring-amber-500 bg-amber-500/5',
      )}
      onClick={() => textareaRef.current?.focus()}
      data-testid={`day-cell-${formatDateISO(date)}`}
    >
      <div className="flex items-baseline justify-between mb-1.5">
        <span
          className={cn(
            'text-xs uppercase tracking-wide text-zinc-500',
            isToday && 'text-amber-500',
          )}
        >
          {dayLabel}
        </span>
        <span
          className={cn(
            'text-sm font-medium text-zinc-300',
            isToday && 'text-amber-400',
          )}
        >
          {dayNumber}
        </span>
      </div>
      <textarea
        ref={textareaRef}
        value={current}
        onChange={(e) => setCurrent(e.target.value)}
        onBlur={handleBlur}
        placeholder="—"
        className="flex-1 w-full bg-transparent border-none outline-none focus:outline-none focus:ring-0 resize-none p-1 text-sm placeholder:text-zinc-500 whitespace-pre-wrap"
        aria-label={`Plan for ${formatDateISO(date)}`}
      />
    </div>
  )
}
