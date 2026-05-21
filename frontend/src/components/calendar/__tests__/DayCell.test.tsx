import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, fireEvent, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { DayCell } from '../DayCell'

/**
 * v2.1 Phase 6 — DayCell auto-save branch coverage (CAL-08 + D-05).
 *
 * The 5 branches under test:
 *   1. empty textarea + no row  -> noop          (avoid hot-path noise)
 *   2. text typed  + no row     -> POST          (first save)
 *   3. text changed + row exists -> PATCH        (edit)
 *   4. cleared text + row exists -> DELETE       (D-05: clear deletes)
 *   5. unchanged text + row exists -> noop       (idle save guard)
 *
 * Plus 2 today-highlight class assertions (D-09 ring-amber-500 conditional).
 *
 * The mutation hooks are vi.mock'd so we can spy on .mutate() without any
 * real network IO. The QueryClientProvider is still present because some
 * downstream hooks may reach for queryClient internally even when the
 * mutation factory itself is mocked.
 */

const createMutate = vi.fn()
const updateMutate = vi.fn()
const deleteMutate = vi.fn()

vi.mock('@/hooks/useCalendarMutations', () => ({
  useCreateCalendarItem: () => ({ mutate: createMutate, isPending: false }),
  useUpdateCalendarItem: () => ({ mutate: updateMutate, isPending: false }),
  useDeleteCalendarItem: () => ({ mutate: deleteMutate, isPending: false }),
}))

function renderCell(props: Parameters<typeof DayCell>[0]) {
  const qc = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  return render(
    <QueryClientProvider client={qc}>
      <DayCell {...props} />
    </QueryClientProvider>,
  )
}

const WEEK = { start: '2026-05-18', end: '2026-05-24' }
const TUE = new Date(2026, 4, 19) // May 19 2026 — a Tuesday

beforeEach(() => {
  createMutate.mockClear()
  updateMutate.mockClear()
  deleteMutate.mockClear()
})

describe('DayCell auto-save branches', () => {
  it('noop: empty textarea + no row -> no mutation fired', () => {
    renderCell({ companyId: 'seva', date: TUE, item: null, weekRange: WEEK, isToday: false })
    const ta = screen.getByLabelText(/Plan for 2026-05-19/i) as HTMLTextAreaElement
    ta.focus()
    ta.blur()
    expect(createMutate).not.toHaveBeenCalled()
    expect(updateMutate).not.toHaveBeenCalled()
    expect(deleteMutate).not.toHaveBeenCalled()
  })

  it('POST: text typed + no row -> create fires with {date, body}', async () => {
    const user = userEvent.setup()
    renderCell({ companyId: 'seva', date: TUE, item: null, weekRange: WEEK, isToday: false })
    const ta = screen.getByLabelText(/Plan for 2026-05-19/i) as HTMLTextAreaElement
    await user.click(ta)
    await user.type(ta, 'new plan')
    fireEvent.blur(ta)
    expect(createMutate).toHaveBeenCalledWith({ date: '2026-05-19', body: 'new plan' })
    expect(updateMutate).not.toHaveBeenCalled()
    expect(deleteMutate).not.toHaveBeenCalled()
  })

  it('PATCH: text changed + row exists -> update fires with {id, payload: {body}}', async () => {
    const user = userEvent.setup()
    const item = {
      id: 'item-1',
      date: '2026-05-19',
      body: 'old',
      created_at: 'x',
      updated_at: 'x',
    }
    renderCell({ companyId: 'seva', date: TUE, item, weekRange: WEEK, isToday: false })
    const ta = screen.getByLabelText(/Plan for 2026-05-19/i) as HTMLTextAreaElement
    await user.clear(ta)
    await user.type(ta, 'new')
    fireEvent.blur(ta)
    expect(updateMutate).toHaveBeenCalledWith({ id: 'item-1', payload: { body: 'new' } })
    expect(createMutate).not.toHaveBeenCalled()
    expect(deleteMutate).not.toHaveBeenCalled()
  })

  it('DELETE: cleared textarea + row exists -> delete fires with id', async () => {
    const user = userEvent.setup()
    const item = {
      id: 'item-1',
      date: '2026-05-19',
      body: 'old',
      created_at: 'x',
      updated_at: 'x',
    }
    renderCell({ companyId: 'seva', date: TUE, item, weekRange: WEEK, isToday: false })
    const ta = screen.getByLabelText(/Plan for 2026-05-19/i) as HTMLTextAreaElement
    await user.clear(ta)
    fireEvent.blur(ta)
    expect(deleteMutate).toHaveBeenCalledWith('item-1')
    expect(createMutate).not.toHaveBeenCalled()
    expect(updateMutate).not.toHaveBeenCalled()
  })

  it('idle save guard: text unchanged + row exists -> no mutation fired', () => {
    const item = {
      id: 'item-1',
      date: '2026-05-19',
      body: 'old',
      created_at: 'x',
      updated_at: 'x',
    }
    renderCell({ companyId: 'seva', date: TUE, item, weekRange: WEEK, isToday: false })
    const ta = screen.getByLabelText(/Plan for 2026-05-19/i) as HTMLTextAreaElement
    ta.focus()
    fireEvent.blur(ta) // no edit between focus and blur
    expect(createMutate).not.toHaveBeenCalled()
    expect(updateMutate).not.toHaveBeenCalled()
    expect(deleteMutate).not.toHaveBeenCalled()
  })

  it('today highlight: isToday=true adds ring-amber-500', () => {
    renderCell({ companyId: 'seva', date: TUE, item: null, weekRange: WEEK, isToday: true })
    const cell = screen.getByTestId('day-cell-2026-05-19')
    expect(cell.className).toContain('ring-amber-500')
    expect(cell.className).toContain('bg-amber-500/5')
  })

  it('today highlight: isToday=false does NOT add ring-amber-500', () => {
    renderCell({ companyId: 'seva', date: TUE, item: null, weekRange: WEEK, isToday: false })
    const cell = screen.getByTestId('day-cell-2026-05-19')
    expect(cell.className).not.toContain('ring-amber-500')
  })
})

describe('DayCell defence badge (quick-260520-srt)', () => {
  /**
   * Cross-tenant isolation tests + badge render/no-render assertions.
   *
   * D-10 invariant: Seva calendar must remain byte-identical — no defence
   * badges ever render for companyId === 'seva'.
   *
   * Priority check: Nov 8 has both a fixed entry (Indigenous Veterans Day)
   * and falls within Veterans' Week range. The badge should display the
   * fixed entry first (companyId === 'juno' renders defenceBadges[0]).
   */

  it('juno + matching date → badge renders with Remembrance Day', () => {
    // Nov 11 2026
    renderCell({
      companyId: 'juno',
      date: new Date(2026, 10, 11),
      item: null,
      weekRange: { start: '2026-11-09', end: '2026-11-15' },
      isToday: false,
    })
    const badge = screen.getByTestId('defence-badge')
    expect(badge).toBeTruthy()
    expect(badge.textContent).toBe('Remembrance Day')
    // Verify muted token (text-zinc-500) is present on the badge element
    expect(badge.className).toContain('text-zinc-500')
  })

  it('seva + matching date → badge does NOT render (D-10 invariant)', () => {
    // Same date (Nov 11 2026), companyId: 'seva'
    renderCell({
      companyId: 'seva',
      date: new Date(2026, 10, 11),
      item: null,
      weekRange: { start: '2026-11-09', end: '2026-11-15' },
      isToday: false,
    })
    const badge = screen.queryByText('Remembrance Day')
    expect(badge).toBeNull()
  })

  it('juno + non-matching date → defence-badge slot is absent', () => {
    // Mar 15 2026 — no defence date
    renderCell({
      companyId: 'juno',
      date: new Date(2026, 2, 15),
      item: null,
      weekRange: { start: '2026-03-09', end: '2026-03-15' },
      isToday: false,
    })
    const badge = screen.queryByTestId('defence-badge')
    expect(badge).toBeNull()
  })

  it('priority ordering — Nov 8 shows Indigenous Veterans Day (fixed), not Veterans\' Week (range)', () => {
    // Nov 8 2026: fixed entry (Indigenous Veterans Day) wins in position 0
    renderCell({
      companyId: 'juno',
      date: new Date(2026, 10, 8),
      item: null,
      weekRange: { start: '2026-11-02', end: '2026-11-08' },
      isToday: false,
    })
    expect(screen.queryByText('Indigenous Veterans Day')).toBeTruthy()
    expect(screen.queryByText("Veterans' Week")).toBeNull()
  })
})
