import { describe, it, expect } from 'vitest'
import { getDefenceDateBadges } from '../junoDefenceCalendarDates'

/**
 * Unit tests for the Juno defence-history calendar badge dataset.
 * quick-260520-srt: Canadian defence/military commemoration badge lookup.
 *
 * Tests cover:
 *  - Fixed date lookup (Remembrance Day Nov 11)
 *  - Priority ordering: fixed > movable > range (Nov 8: Indigenous Veterans Day wins over Veterans' Week)
 *  - Range-only match (Veterans' Week, Nov 7)
 *  - Movable feast computation for all three entries
 *  - Non-matching date returns empty array
 *  - Omitted dates (Air India Jun 23, Parliament Hill Oct 22) return empty array
 *  - Cross-year invariance for fixed dates
 */
describe('getDefenceDateBadges', () => {
  it('case 1: Nov 11 2026 returns Remembrance Day', () => {
    const result = getDefenceDateBadges(2026, 11, 11)
    expect(result).toHaveLength(1)
    expect(result[0].name).toBe('Remembrance Day')
  })

  it('case 2: Nov 8 2026 returns both Indigenous Veterans Day (fixed) and Veterans\' Week (range), fixed first', () => {
    const result = getDefenceDateBadges(2026, 11, 8)
    expect(result).toHaveLength(2)
    expect(result[0].name).toBe('Indigenous Veterans Day')
    expect(result[1].name).toBe("Veterans' Week")
  })

  it('case 3: Nov 7 2026 returns only Veterans\' Week (range only)', () => {
    const result = getDefenceDateBadges(2026, 11, 7)
    expect(result).toHaveLength(1)
    expect(result[0].name).toBe("Veterans' Week")
  })

  it('case 4: May 3 2026 returns Battle of the Atlantic Sunday (1st Sunday of May 2026)', () => {
    // 1st Sunday of May 2026: May 3 (May 1 is Friday, May 2 is Saturday, May 3 is Sunday)
    const result = getDefenceDateBadges(2026, 5, 3)
    expect(result.some(e => e.name === 'Battle of the Atlantic Sunday')).toBe(true)
  })

  it('case 5: Jun 7 2026 returns Canadian Armed Forces Day (1st Sunday of June 2026)', () => {
    // 1st Sunday of June 2026: June 7 (June 1 is Monday ... June 7 is Sunday)
    const result = getDefenceDateBadges(2026, 6, 7)
    expect(result.some(e => e.name === 'Canadian Armed Forces Day')).toBe(true)
  })

  it('case 6: Sep 20 2026 returns Battle of Britain Sunday (3rd Sunday of September 2026)', () => {
    // 3rd Sunday of Sep 2026: Sep 6=Sun, Sep 13=Sun, Sep 20=Sun
    const result = getDefenceDateBadges(2026, 9, 20)
    expect(result.some(e => e.name === 'Battle of Britain Sunday')).toBe(true)
  })

  it('case 7: Mar 15 2026 returns empty array (no defence date)', () => {
    const result = getDefenceDateBadges(2026, 3, 15)
    expect(result).toHaveLength(0)
  })

  it('case 8: Jun 23 2026 returns empty array (Air India omitted per operator decision)', () => {
    const result = getDefenceDateBadges(2026, 6, 23)
    expect(result).toHaveLength(0)
  })

  it('case 9: Oct 22 2026 returns empty array (Parliament Hill omitted per operator decision)', () => {
    const result = getDefenceDateBadges(2026, 10, 22)
    expect(result).toHaveLength(0)
  })

  it('case 10: Nov 11 2027 also returns Remembrance Day (fixed dates are not year-pinned)', () => {
    const result = getDefenceDateBadges(2027, 11, 11)
    expect(result.some(e => e.name === 'Remembrance Day')).toBe(true)
  })
})
