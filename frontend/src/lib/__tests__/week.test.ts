import { describe, it, expect } from 'vitest'
import {
  formatDateISO,
  getWeekDays,
  getWeekEnd,
  getWeekStart,
} from '../week'

/**
 * v2.1 Phase 6 — ISO week (Mon-Sun) helper coverage.
 *
 * Anchored to a known calendar week: 2026-05-18 (Mon) .. 2026-05-24 (Sun).
 * The Wednesday of that week is 2026-05-20. We build Date instances from
 * year/month/day primitives (NEVER `new Date('YYYY-MM-DD')`) to avoid the
 * Pitfall P1 timezone interpretation footgun.
 */
describe('week helpers (ISO, Mon-Sun)', () => {
  // 2026-05-20 is a Wednesday. month index 4 = May.
  const wed = new Date(2026, 4, 20)

  it('getWeekStart returns Monday of the week', () => {
    const monday = getWeekStart(wed)
    expect(monday.getDay()).toBe(1) // 0 = Sunday, 1 = Monday
    expect(monday.getDate()).toBe(18)
  })

  it('getWeekEnd returns Sunday of the week', () => {
    const sunday = getWeekEnd(wed)
    expect(sunday.getDay()).toBe(0)
    expect(sunday.getDate()).toBe(24)
  })

  it('formatDateISO emits YYYY-MM-DD', () => {
    expect(formatDateISO(wed)).toBe('2026-05-20')
    expect(formatDateISO(new Date(2026, 0, 1))).toBe('2026-01-01')
    expect(formatDateISO(new Date(2026, 11, 31))).toBe('2026-12-31')
  })

  it('getWeekDays returns 7 days in Mon-Sun order', () => {
    const days = getWeekDays(wed)
    expect(days).toHaveLength(7)
    expect(days[0].getDay()).toBe(1) // Monday
    expect(days[6].getDay()).toBe(0) // Sunday
    expect(days.map((d) => d.getDate())).toEqual([18, 19, 20, 21, 22, 23, 24])
  })

  it('getWeekStart for a Monday returns the same Monday', () => {
    const mon = new Date(2026, 4, 18)
    expect(getWeekStart(mon).getDate()).toBe(18)
  })

  it('getWeekStart for a Sunday returns the previous Monday', () => {
    const sun = new Date(2026, 4, 24) // Sunday May 24 2026
    const monday = getWeekStart(sun)
    expect(monday.getDate()).toBe(18) // previous Monday May 18
  })
})
