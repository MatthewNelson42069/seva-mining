import { addDays, endOfWeek, format, startOfWeek } from 'date-fns'

/**
 * v2.1 Phase 6 — ISO week (Mon-Sun) helpers.
 *
 * All helpers use `weekStartsOn: 1` to align with the ISO 8601 convention
 * and the user's explicit decision (06-CONTEXT.md D-07).
 *
 * Pitfall P1 defense (frontend side): we never `new Date('YYYY-MM-DD')`
 * a string from the backend — that would silently apply local TZ
 * interpretation. Callers should pass Date objects constructed from
 * year/month/day primitives (e.g. new Date(2026, 4, 18) for May 18 2026)
 * when round-tripping with the backend. For "today" use `new Date()`.
 */

/** Return the Monday of the ISO week containing `d` (00:00:00 local). */
export function getWeekStart(d: Date): Date {
  return startOfWeek(d, { weekStartsOn: 1 })
}

/** Return the Sunday of the ISO week containing `d` (23:59:59.999 local). */
export function getWeekEnd(d: Date): Date {
  return endOfWeek(d, { weekStartsOn: 1 })
}

/** Format a Date as 'YYYY-MM-DD' (P1: this is the canonical backend format). */
export function formatDateISO(d: Date): string {
  return format(d, 'yyyy-MM-dd')
}

/** Return 7 Date objects, one per day Mon-Sun, for the week containing `d`. */
export function getWeekDays(d: Date): Date[] {
  const monday = getWeekStart(d)
  return Array.from({ length: 7 }, (_, i) => addDays(monday, i))
}
