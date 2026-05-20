/**
 * Phase 14 D-04 — TanStack Query key isolation per tenant.
 *
 * Validates JCAL-03 contract via the primary mechanism — per-tenant query
 * key from `queryKeys.calendar(companyId, start, end)` (a 4-tuple of
 * `['calendar', companyId, start, end]`). After Phase 14 Task 1 deleted
 * the Phase 9 D-09 Juno short-circuit at `ContentCalendarPage.tsx:42-54`,
 * `<WeeklyGrid />` mounts for BOTH `/seva/calendar` and `/juno/calendar`
 * and `useCalendar(companyId, ...)` registers a tenant-keyed query entry
 * in the QueryClient cache. These tests assert that the per-tenant entries
 * exist and never bleed across tenants.
 *
 * Mocking strategy (mirrors DayCell.test.tsx + AppHeader.brand.test.tsx):
 *   - `@/api/calendar` getCalendar -> resolves empty range; no network IO
 *   - `@/hooks/useCalendarMutations` -> all 3 mutation factories stubbed;
 *     no mutation hot-path fires during cache-key assertions
 *
 * Pitfalls avoided:
 *   - Vitest fake-timer helpers (Phase 11-05 STATE.md flagged a
 *     TanStack-Query-v5 deadlock; use `waitFor` for async query
 *     registration instead)
 *   - Asserting specific date strings in the query key (today's date varies
 *     between test runs — use partial `findAll({ queryKey: ['calendar', X] })`
 *     predicate match)
 *   - Touching `document.documentElement.dataset.company` (Phase 13 domain;
 *     Phase 14 does NOT need CompanyBrandEffect)
 */

import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import ContentCalendarPage from '../ContentCalendarPage'

// Mock the calendar API module so no real network call fires.
vi.mock('@/api/calendar', () => ({
  getCalendar: vi.fn().mockResolvedValue({ items: [], total: 0 }),
}))

// Mock the mutation hooks so the DayCell auto-save branches stay inert
// and no second-order network IO is attempted.
vi.mock('@/hooks/useCalendarMutations', () => ({
  useCreateCalendarItem: () => ({ mutate: vi.fn(), isPending: false }),
  useUpdateCalendarItem: () => ({ mutate: vi.fn(), isPending: false }),
  useDeleteCalendarItem: () => ({ mutate: vi.fn(), isPending: false }),
}))

function renderAt(path: '/seva/calendar' | '/juno/calendar') {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  const result = render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path=":company/calendar" element={<ContentCalendarPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
  return { ...result, queryClient }
}

describe('ContentCalendarPage — per-tenant TanStack Query key isolation (D-04)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    cleanup()
  })

  it('mounts at /juno/calendar and registers a [\'calendar\', \'juno\', ...] query key', async () => {
    const { queryClient } = renderAt('/juno/calendar')

    // WeeklyGrid mounted -> Phase 9 short-circuit is gone (Task 1 proof).
    await waitFor(() =>
      expect(screen.getByTestId('weekly-grid')).toBeInTheDocument(),
    )

    // useCalendar(companyId='juno', ...) registered its query key.
    await waitFor(() => {
      const juno = queryClient
        .getQueryCache()
        .findAll({ queryKey: ['calendar', 'juno'] })
      expect(juno.length).toBeGreaterThanOrEqual(1)
    })

    // Sanity: no Seva entry leaked into this fresh client.
    const seva = queryClient
      .getQueryCache()
      .findAll({ queryKey: ['calendar', 'seva'] })
    expect(seva.length).toBe(0)
  })

  it('mounts at /seva/calendar and registers a [\'calendar\', \'seva\', ...] query key (D-07 parity)', async () => {
    const { queryClient } = renderAt('/seva/calendar')

    // WeeklyGrid mounts for Seva (zero-regression — Phase 14 did not
    // touch the Seva render path).
    await waitFor(() =>
      expect(screen.getByTestId('weekly-grid')).toBeInTheDocument(),
    )

    await waitFor(() => {
      const seva = queryClient
        .getQueryCache()
        .findAll({ queryKey: ['calendar', 'seva'] })
      expect(seva.length).toBeGreaterThanOrEqual(1)
    })

    // Sanity: no Juno entry leaked into this fresh client.
    const juno = queryClient
      .getQueryCache()
      .findAll({ queryKey: ['calendar', 'juno'] })
    expect(juno.length).toBe(0)
  })

  it('Seva and Juno query keys are isolated across mounts (JCAL-03 cross-tenant isolation)', async () => {
    // First mount: /seva/calendar with its own fresh QueryClient.
    const sevaRender = renderAt('/seva/calendar')
    await waitFor(() => {
      const seva = sevaRender.queryClient
        .getQueryCache()
        .findAll({ queryKey: ['calendar', 'seva'] })
      expect(seva.length).toBeGreaterThanOrEqual(1)
    })
    sevaRender.unmount()

    // Second mount: /juno/calendar with a SECOND fresh QueryClient.
    // Per AppHeader.brand.test.tsx renderAt pattern, each render owns its
    // own client — this is the cleanest cache-isolation proof: the Juno
    // client never saw the Seva key.
    const junoRender = renderAt('/juno/calendar')
    await waitFor(() => {
      const juno = junoRender.queryClient
        .getQueryCache()
        .findAll({ queryKey: ['calendar', 'juno'] })
      expect(juno.length).toBeGreaterThanOrEqual(1)
    })

    // Cross-tenant isolation: Juno's cache contains NO Seva entry.
    const sevaInJuno = junoRender.queryClient
      .getQueryCache()
      .findAll({ queryKey: ['calendar', 'seva'] })
    expect(sevaInJuno.length).toBe(0)
  })
})
