import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  createCalendarItem,
  deleteCalendarItem,
  updateCalendarItem,
  type CalendarItem,
  type CalendarItemCreate,
  type CalendarItemUpdate,
  type CalendarRangeResponse,
} from '@/api/calendar'
import { queryKeys, type CompanyId } from '@/api/queryKeys'

/**
 * v2.1 Phase 6 / v3.0 Phase 9 — Optimistic mutation hooks for the Content
 * Calendar (CAL-09, TENANT-09).
 *
 * Pitfall P2 defense: every mutation follows the 3-step pattern:
 *   1. onMutate — cancel in-flight queries, snapshot cache, apply optimistic write
 *   2. onError  — restore the snapshot (NOT just invalidate — restoring is the point)
 *   3. onSettled — invalidate ['calendar', companyId, start, end] so the next refetch
 *      is authoritative
 *
 * Failure feedback: sonner toast on any mutation error. Success is silent —
 * the optimistic write IS the feedback.
 *
 * queryKey contract: queryKeys.calendar(companyId, start, end) — must match
 * useCalendar.
 */

interface MutationOptions {
  companyId: CompanyId  // tenant slot (TENANT-09)
  start: string         // 'YYYY-MM-DD' — the current week's Monday
  end: string           // 'YYYY-MM-DD' — the current week's Sunday
}

/** useCreateCalendarItem — POST /api/{company}/calendar with optimistic insert. */
export function useCreateCalendarItem({ companyId, start, end }: MutationOptions) {
  const queryClient = useQueryClient()
  const queryKey = queryKeys.calendar(companyId, start, end)

  return useMutation({
    mutationFn: (payload: CalendarItemCreate) =>
      createCalendarItem(companyId, payload),
    onMutate: async (payload: CalendarItemCreate) => {
      await queryClient.cancelQueries({ queryKey })
      const previous = queryClient.getQueryData<CalendarRangeResponse>(queryKey)
      // Optimistic write — synthetic item with a sentinel id until server replies.
      const optimistic: CalendarItem = {
        id: `optimistic-${Date.now()}`,
        date: payload.date,
        body: payload.body,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      }
      queryClient.setQueryData<CalendarRangeResponse>(queryKey, (old) => {
        if (!old) return { items: [optimistic], total: 1 }
        // Insert preserving date ASC order
        const next = [...old.items, optimistic].sort((a, b) =>
          a.date < b.date ? -1 : a.date > b.date ? 1 : 0,
        )
        return { items: next, total: next.length }
      })
      return { previous }
    },
    onError: (error, _payload, context) => {
      // P2 rollback — restore the pre-mutation snapshot.
      if (context?.previous !== undefined) {
        queryClient.setQueryData<CalendarRangeResponse>(queryKey, context.previous)
      }
      toast.error(`Failed to save: ${error instanceof Error ? error.message : 'unknown error'}`)
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey })
    },
  })
}

/** useUpdateCalendarItem — PATCH /api/{company}/calendar/{id} with optimistic body swap. */
export function useUpdateCalendarItem({ companyId, start, end }: MutationOptions) {
  const queryClient = useQueryClient()
  const queryKey = queryKeys.calendar(companyId, start, end)

  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: CalendarItemUpdate }) =>
      updateCalendarItem(companyId, id, payload),
    onMutate: async ({ id, payload }) => {
      await queryClient.cancelQueries({ queryKey })
      const previous = queryClient.getQueryData<CalendarRangeResponse>(queryKey)
      queryClient.setQueryData<CalendarRangeResponse>(queryKey, (old) => {
        if (!old) return old
        const next = old.items.map((it) =>
          it.id === id ? { ...it, body: payload.body, updated_at: new Date().toISOString() } : it,
        )
        return { items: next, total: next.length }
      })
      return { previous }
    },
    onError: (error, _vars, context) => {
      if (context?.previous !== undefined) {
        queryClient.setQueryData<CalendarRangeResponse>(queryKey, context.previous)
      }
      toast.error(`Failed to save: ${error instanceof Error ? error.message : 'unknown error'}`)
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey })
    },
  })
}

/** useDeleteCalendarItem — DELETE /api/{company}/calendar/{id} with optimistic remove. */
export function useDeleteCalendarItem({ companyId, start, end }: MutationOptions) {
  const queryClient = useQueryClient()
  const queryKey = queryKeys.calendar(companyId, start, end)

  return useMutation({
    mutationFn: (id: string) => deleteCalendarItem(companyId, id),
    onMutate: async (id: string) => {
      await queryClient.cancelQueries({ queryKey })
      const previous = queryClient.getQueryData<CalendarRangeResponse>(queryKey)
      queryClient.setQueryData<CalendarRangeResponse>(queryKey, (old) => {
        if (!old) return old
        const next = old.items.filter((it) => it.id !== id)
        return { items: next, total: next.length }
      })
      return { previous }
    },
    onError: (error, _id, context) => {
      if (context?.previous !== undefined) {
        queryClient.setQueryData<CalendarRangeResponse>(queryKey, context.previous)
      }
      toast.error(`Failed to delete: ${error instanceof Error ? error.message : 'unknown error'}`)
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey })
    },
  })
}
