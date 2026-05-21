/**
 * quick-260520-srt: Juno defence-history calendar date dataset.
 *
 * Provides a curated list of Canadian defence/military commemorations for
 * display as subdued informational badges in the Juno Calendar tab.
 *
 * Tenant-scoped: this module is consumed only by DayCell when companyId === 'juno'.
 * The Seva calendar remains byte-identical per v3.0 D-10 invariant.
 *
 * Voice contract (Phase 10 D-01 anti-tactical clause):
 *   Descriptions are sober and commemorative — Janes/CSIS desk register.
 *   No celebratory, sensational, or operational language. Do NOT paraphrase
 *   descriptions — they have been reviewed for tone compliance.
 *
 * Dataset: 29 fixed annual dates + 3 movable feasts + 1 inclusive range.
 * Omitted by operator decision: Air India bombing (Jun 23), Parliament Hill
 * attack (Oct 22).
 *
 * Priority when getDefenceDateBadges returns multiple matches:
 *   fixed > movable > range
 */

export type DefenceCalendarDate = {
  // Exactly ONE of these three should be set per entry:
  fixed?: { month: number; day: number }
  movable?: { month: number; weekday: number; ordinal: 1 | 2 | 3 | 4 }
  range?: { startMonth: number; startDay: number; endMonth: number; endDay: number }

  name: string
  description: string
  significance?: string
}

/**
 * Full dataset of Canadian defence/military commemorations.
 * Order: fixed (calendar-month order), then movables, then range.
 */
export const junoDefenceCalendarDates: DefenceCalendarDate[] = [
  // ── Fixed annual dates (29 entries, calendar-month order) ──────────────────

  {
    fixed: { month: 2, day: 1 },
    name: 'Canadian Armed Forces Unification Day',
    description:
      'Anniversary of the 1968 Canadian Forces Reorganization Act unifying the RCN, Army, and RCAF into one service.',
  },
  {
    fixed: { month: 4, day: 1 },
    name: 'Royal Canadian Air Force Birthday',
    description:
      "Anniversary of the RCAF's 1924 establishment as a permanent component of Canadian defence.",
  },
  {
    fixed: { month: 4, day: 4 },
    name: 'NATO Founding Day',
    description:
      'Canada was one of twelve founding signatories of the 1949 North Atlantic Treaty.',
  },
  {
    fixed: { month: 4, day: 9 },
    name: 'Vimy Ridge Day',
    description:
      'Commemorates the Canadian Corps\' assault on Vimy Ridge, 9–12 April 1917.',
  },
  {
    fixed: { month: 4, day: 22 },
    name: 'Second Battle of Ypres Anniversary',
    description:
      "Canada's 1st Division held against the first large-scale chlorine gas attack on the Western Front, 1915.",
  },
  {
    fixed: { month: 4, day: 24 },
    name: 'Battle of Kapyong Anniversary',
    description:
      '2 PPCLI\'s defensive stand against Chinese forces in the Korean War, 22–25 April 1951.',
  },
  {
    fixed: { month: 5, day: 4 },
    name: 'Royal Canadian Navy Founding',
    description:
      'Anniversary of Royal Assent for the 1910 Naval Service Act establishing Canada\'s navy.',
  },
  {
    fixed: { month: 5, day: 5 },
    name: 'Liberation of the Netherlands',
    description:
      'Marks the German surrender to Lt-Gen Charles Foulkes at Wageningen, 1945.',
  },
  {
    fixed: { month: 5, day: 8 },
    name: 'Victory in Europe (VE) Day',
    description: 'Marks the end of the Second World War in Europe, 1945.',
  },
  {
    fixed: { month: 5, day: 9 },
    name: 'National Day of Honour',
    description:
      "Commemorates the end of Canada's military mission in Afghanistan; informally observed.",
  },
  {
    fixed: { month: 5, day: 12 },
    name: 'NORAD Agreement Anniversary',
    description:
      'Formal 1958 Canada–US agreement establishing the North American Aerospace Defense Command.',
  },
  {
    fixed: { month: 5, day: 28 },
    name: 'Tomb of the Unknown Soldier Interment',
    description:
      "Anniversary of the 2000 interment of Canada's Unknown Soldier at the National War Memorial.",
  },
  {
    fixed: { month: 5, day: 29 },
    name: 'International Day of UN Peacekeepers',
    description: 'UN-designated day honouring peacekeepers worldwide.',
  },
  {
    fixed: { month: 6, day: 6 },
    name: 'D-Day / Juno Beach Anniversary',
    description:
      'Marks the 1944 Allied landings in Normandy; approximately 14,000 Canadians landed on Juno Beach.',
  },
  {
    fixed: { month: 6, day: 25 },
    name: 'Korean War Outbreak Anniversary',
    description:
      'Beginning of the 1950 Korean War; more than 26,000 Canadians served.',
  },
  {
    fixed: { month: 7, day: 1 },
    name: 'Newfoundland & Labrador Memorial Day',
    description:
      'Provincial day of mourning marking the Battle of Beaumont-Hamel, 1 July 1916.',
  },
  {
    fixed: { month: 7, day: 27 },
    name: 'Korean War Veterans Day',
    description: 'National day honouring Korean War veterans; marks the 1953 armistice.',
  },
  {
    fixed: { month: 8, day: 9 },
    name: "National Peacekeepers' Day",
    description:
      'Marks the 1974 loss of nine Canadians when their UN aircraft was shot down over Syria.',
  },
  {
    fixed: { month: 8, day: 13 },
    name: "Canadian Women's Army Corps Anniversary",
    description:
      'Authorization of the CWAC in 1941, the first formal integration of women in the Canadian Army.',
  },
  {
    fixed: { month: 8, day: 15 },
    name: 'End of the Second World War in the Pacific',
    description: "Marks Japan's surrender, 1945; the formal end of the Second World War.",
  },
  {
    fixed: { month: 8, day: 19 },
    name: 'Dieppe Raid Anniversary',
    description:
      "Canada's bloodiest single day of the war, 1942; approximately 3,350 of 5,000 Canadians became casualties.",
  },
  {
    fixed: { month: 8, day: 21 },
    name: 'Closing of the Falaise Pocket',
    description:
      'Marks the 1944 sealing of the Falaise Pocket by Canadian and Polish forces.',
  },
  {
    fixed: { month: 9, day: 3 },
    name: 'Merchant Navy Veterans Day',
    description:
      'Honours Canadian Merchant Navy sailors, particularly in the Battle of the Atlantic.',
  },
  {
    fixed: { month: 10, day: 26 },
    name: 'Canadian Corps at Passchendaele',
    description:
      "Start of the Canadian Corps' assault at Passchendaele, 26 October – 10 November 1917.",
  },
  {
    fixed: { month: 11, day: 8 },
    name: 'Indigenous Veterans Day',
    description:
      'Recognizes First Nations, Inuit, and Métis military service; distinct from Remembrance Day.',
  },
  {
    fixed: { month: 11, day: 11 },
    name: 'Remembrance Day',
    description: 'National day of remembrance marking the 1918 Armistice.',
  },
  {
    fixed: { month: 12, day: 8 },
    name: 'Battle of Hong Kong Anniversary',
    description:
      "Marks the opening of the 1941 Hong Kong battle; Canada's first ground combat of WWII.",
  },
  {
    fixed: { month: 12, day: 20 },
    name: 'Battle of Ortona Begins',
    description:
      "Canadian 1st Division's urban battle in Italy, 20–28 December 1943.",
  },
  {
    fixed: { month: 12, day: 25 },
    name: 'Christmas at Ortona / Fall of Hong Kong',
    description:
      'Two solemn Christmas-day anniversaries in Canadian military memory, 1943 and 1941.',
  },

  // ── Movable feasts (3 entries) ─────────────────────────────────────────────

  {
    movable: { month: 5, weekday: 0, ordinal: 1 },
    name: 'Battle of the Atlantic Sunday',
    description:
      "Commemorates the Second World War's longest campaign, 1939–1945; over 4,600 RCN, RCAF, and Merchant Navy lost.",
  },
  {
    movable: { month: 6, weekday: 0, ordinal: 1 },
    name: 'Canadian Armed Forces Day',
    description:
      'National observance recognizing CAF personnel, heritage, and service; established 2002.',
  },
  {
    movable: { month: 9, weekday: 0, ordinal: 3 },
    name: 'Battle of Britain Sunday',
    description:
      'Commemorates the 1940 air defence of the UK; over 100 Canadian pilots flew in the battle.',
  },

  // ── Range (1 entry) ────────────────────────────────────────────────────────

  {
    // Nov 5–10: Veterans' Week leads up to Remembrance Day (Nov 11).
    // endDay is 10, not 11, so that Nov 11 is covered exclusively by the
    // fixed Remembrance Day entry (priority: fixed > range). This matches
    // the must_haves truth: Nov 11 shows "Remembrance Day" only.
    range: { startMonth: 11, startDay: 5, endMonth: 11, endDay: 10 },
    name: "Veterans' Week",
    description: 'Annual week of remembrance leading to Remembrance Day.',
  },
]

/**
 * Returns all defence/military commemorations matching the given date,
 * ordered by priority: fixed first, then movable, then range.
 *
 * @param year  - Full calendar year (e.g. 2026)
 * @param month - 1-indexed month (1 = January)
 * @param day   - 1-indexed day of month
 * @returns Array of matching DefenceCalendarDate entries (may be empty)
 */
export function getDefenceDateBadges(
  year: number,
  month: number,
  day: number,
): DefenceCalendarDate[] {
  const target = new Date(year, month - 1, day)
  const targetWeekday = target.getDay()
  // Ordinal of this weekday within the month: 1st, 2nd, 3rd, or 4th occurrence.
  // Math.ceil(day / 7) works because the Nth occurrence of any weekday always
  // falls in days [(N-1)*7+1 .. N*7].
  const targetOrdinal = Math.ceil(day / 7)

  const fixedMatches: DefenceCalendarDate[] = []
  const movableMatches: DefenceCalendarDate[] = []
  const rangeMatches: DefenceCalendarDate[] = []

  for (const entry of junoDefenceCalendarDates) {
    if (entry.fixed) {
      if (entry.fixed.month === month && entry.fixed.day === day) {
        fixedMatches.push(entry)
      }
    } else if (entry.movable) {
      if (
        entry.movable.month === month &&
        targetWeekday === entry.movable.weekday &&
        targetOrdinal === entry.movable.ordinal
      ) {
        movableMatches.push(entry)
      }
    } else if (entry.range) {
      const { startMonth, startDay, endMonth, endDay } = entry.range
      if (startMonth === endMonth) {
        // Same-month range (Veterans' Week: Nov 5–11)
        if (month === startMonth && day >= startDay && day <= endDay) {
          rangeMatches.push(entry)
        }
      } else {
        // Cross-month range (not present in current dataset, but handle correctly)
        const afterStart =
          month > startMonth || (month === startMonth && day >= startDay)
        const beforeEnd =
          month < endMonth || (month === endMonth && day <= endDay)
        if (afterStart && beforeEnd) {
          rangeMatches.push(entry)
        }
      }
    }
  }

  return [...fixedMatches, ...movableMatches, ...rangeMatches]
}
