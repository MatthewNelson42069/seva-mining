import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import {
  useCreateCalendarItem,
  useUpdateCalendarItem,
  useDeleteCalendarItem,
} from '../useCalendarMutations'
import type { CalendarRangeResponse } from '@/api/calendar'

function makeWrapper(client: QueryClient) {
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  )
}

function makeQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: 0 },
      mutations: { retry: false },
    },
  })
}

const WEEK = { companyId: 'seva' as const, start: '2026-05-18', end: '2026-05-24' }
const QK = ['calendar', WEEK.companyId, WEEK.start, WEEK.end] as const

const SEED: CalendarRangeResponse = {
  items: [
    {
      id: 'item-1',
      date: '2026-05-20',
      body: 'original',
      created_at: '2026-05-18T12:00:00Z',
      updated_at: '2026-05-18T12:00:00Z',
    },
  ],
  total: 1,
}

function mockFetchSuccess(body: unknown, status = 200) {
  vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
    new Response(JSON.stringify(body), {
      status,
      headers: { 'Content-Type': 'application/json' },
    }),
  )
}

function mockFetch500() {
  vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
    new Response('Internal error', { status: 500 }),
  )
}

beforeEach(() => {
  localStorage.setItem('access_token', 'test-token')
})
afterEach(() => {
  vi.restoreAllMocks()
  localStorage.clear()
})

describe('useCreateCalendarItem', () => {
  it('applies optimistic insert on mutate and keeps it on success', async () => {
    const qc = makeQueryClient()
    qc.setQueryData(QK, SEED)
    mockFetchSuccess({
      id: 'item-2',
      date: '2026-05-21',
      body: 'new',
      created_at: '2026-05-18T12:00:01Z',
      updated_at: '2026-05-18T12:00:01Z',
    }, 201)

    const { result } = renderHook(() => useCreateCalendarItem(WEEK), { wrapper: makeWrapper(qc) })
    result.current.mutate({ date: '2026-05-21', body: 'new' })

    // Wait for the optimistic update (sync within onMutate) and success
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    const after = qc.getQueryData<CalendarRangeResponse>(QK)!
    // Optimistic item was inserted (before server reply); after invalidate the
    // refetch would replace it — but our test mock only responds once so the
    // cache still contains the optimistic entry. Assert it's there.
    expect(after.items.some((it) => it.date === '2026-05-21')).toBe(true)
  })

  it('rolls back to snapshot on 500 (P2 defense)', async () => {
    const qc = makeQueryClient()
    qc.setQueryData(QK, SEED)
    mockFetch500()

    const { result } = renderHook(() => useCreateCalendarItem(WEEK), { wrapper: makeWrapper(qc) })
    result.current.mutate({ date: '2026-05-21', body: 'new' })

    await waitFor(() => expect(result.current.isError).toBe(true))
    const after = qc.getQueryData<CalendarRangeResponse>(QK)!
    // Cache restored to the original SEED — the optimistic 2026-05-21 entry is gone.
    expect(after.items.length).toBe(1)
    expect(after.items[0].date).toBe('2026-05-20')
  })
})

describe('useUpdateCalendarItem', () => {
  it('applies optimistic body swap on mutate', async () => {
    const qc = makeQueryClient()
    qc.setQueryData(QK, SEED)
    mockFetchSuccess({
      ...SEED.items[0], body: 'updated', updated_at: '2026-05-18T12:00:02Z',
    })

    const { result } = renderHook(() => useUpdateCalendarItem(WEEK), { wrapper: makeWrapper(qc) })
    result.current.mutate({ id: 'item-1', payload: { body: 'updated' } })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    const after = qc.getQueryData<CalendarRangeResponse>(QK)!
    expect(after.items[0].body).toBe('updated')
  })

  it('rolls back to snapshot on 500 (P2 defense)', async () => {
    const qc = makeQueryClient()
    qc.setQueryData(QK, SEED)
    mockFetch500()

    const { result } = renderHook(() => useUpdateCalendarItem(WEEK), { wrapper: makeWrapper(qc) })
    result.current.mutate({ id: 'item-1', payload: { body: 'updated' } })

    await waitFor(() => expect(result.current.isError).toBe(true))
    const after = qc.getQueryData<CalendarRangeResponse>(QK)!
    expect(after.items[0].body).toBe('original')  // restored from snapshot
  })
})

describe('useDeleteCalendarItem', () => {
  it('applies optimistic remove on mutate', async () => {
    const qc = makeQueryClient()
    qc.setQueryData(QK, SEED)
    // DELETE returns 204 with no body
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
      new Response(null, { status: 204 }),
    )

    const { result } = renderHook(() => useDeleteCalendarItem(WEEK), { wrapper: makeWrapper(qc) })
    result.current.mutate('item-1')

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    const after = qc.getQueryData<CalendarRangeResponse>(QK)!
    expect(after.items.length).toBe(0)
  })

  it('rolls back to snapshot on 500 (P2 defense)', async () => {
    const qc = makeQueryClient()
    qc.setQueryData(QK, SEED)
    mockFetch500()

    const { result } = renderHook(() => useDeleteCalendarItem(WEEK), { wrapper: makeWrapper(qc) })
    result.current.mutate('item-1')

    await waitFor(() => expect(result.current.isError).toBe(true))
    const after = qc.getQueryData<CalendarRangeResponse>(QK)!
    expect(after.items.length).toBe(1)  // item-1 is back
    expect(after.items[0].id).toBe('item-1')
  })
})
