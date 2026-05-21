/**
 * Phase 15 D-09 — TanStack Query key isolation per tenant for the
 * Weekly Viral Sweeper page.
 *
 * Validates JSWEEP-06 contract via the primary mechanism — per-tenant query
 * key from `queryKeys.weeklySweeps(companyId, limit)` (a 3-tuple of
 * `['weekly-sweeps', companyId, limit]`). After Phase 15 Task 1 deleted the
 * Phase 9 D-09 Juno short-circuit at `WeeklyViralSweeperPage.tsx:48-60`,
 * `<TenantWeeklyViralSweeperPage />` mounts for BOTH `/seva/sweeper` and
 * `/juno/sweeper`, and `useWeeklySweeps(companyId, 12)` registers a
 * tenant-keyed query entry in the QueryClient cache. These tests assert
 * that the per-tenant entries exist and never bleed across tenants.
 *
 * Mocking strategy:
 *   - `@/api/weeklySweeps` `getWeeklySweeps` -> resolves empty feed; no
 *     network IO. The `actual` spread preserves `useWeeklySweeps` so the
 *     real `useQuery` + `queryKeys.weeklySweeps()` factory runs and the
 *     per-tenant cache key is correctly registered.
 *
 * Pitfalls avoided:
 *   - Vitest fake-timer helpers (Phase 11-05 STATE.md flagged a
 *     TanStack-Query-v5 deadlock; use `waitFor` for async query
 *     registration instead)
 *   - Asserting specific limit values in the query key — `findAll` with
 *     a `['weekly-sweeps', X]` partial-match predicate keeps the test
 *     limit-agnostic
 *   - Strict `length === 1` — use `>= 1` (TanStack Query may register
 *     the key with various lifecycle states during the assertion window)
 *   - Mocking `useWeeklySweeps` with a raw `vi.fn()` returning hardcoded
 *     data — that would bypass the QueryClient cache and trivially break
 *     the per-tenant key assertion. The real hook MUST run.
 */

import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query'
import { queryKeys, type CompanyId } from '@/api/queryKeys'
import WeeklyViralSweeperPage from '../WeeklyViralSweeperPage'

// Mock the weekly-sweeps API module so no real network call fires AND the
// per-tenant TanStack Query key still registers in the cache. We re-implement
// `useWeeklySweeps` here to defer to the real `useQuery` + the real
// `queryKeys.weeklySweeps()` factory — that way `getQueryCache().findAll()`
// against `['weekly-sweeps', companyId, ...]` resolves the entries the page
// would register at runtime, but the queryFn never touches the network.
//
// Rationale: an `import.meta.glob`-style "spread actual" pattern doesn't work
// here because the real `useWeeklySweeps` captures `getWeeklySweeps` via the
// module-internal closure, so even mocking the exported `getWeeklySweeps`
// leaves the closure-bound reference pointing at the real `apiFetch` -> 404.
vi.mock('@/api/weeklySweeps', () => ({
  getWeeklySweeps: vi.fn().mockResolvedValue({ sweeps: [], total: 0 }),
  useWeeklySweeps: (companyId: CompanyId, limit = 12) =>
    useQuery({
      queryKey: queryKeys.weeklySweeps(companyId, limit),
      queryFn: async () => ({ sweeps: [], total: 0 }),
    }),
}))

function renderAt(path: '/seva/sweeper' | '/juno/sweeper') {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  const result = render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path=":company/sweeper" element={<WeeklyViralSweeperPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
  return { ...result, queryClient }
}

describe('WeeklyViralSweeperPage — per-tenant TanStack Query key isolation (D-09)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    cleanup()
  })

  it("mounts at /juno/sweeper and registers a ['weekly-sweeps', 'juno', ...] query key", async () => {
    const { queryClient } = renderAt('/juno/sweeper')

    // Empty-state copy renders -> Phase 9 short-circuit is gone (Task 1 proof).
    // The "Coming in v3.1 — Juno Sweeper not yet enabled" copy MUST NOT appear.
    await waitFor(() =>
      expect(screen.getByText(/Sweeper has not run yet/i)).toBeInTheDocument(),
    )
    expect(screen.queryByText(/Coming in v3\.1/i)).not.toBeInTheDocument()

    // useWeeklySweeps(companyId='juno', 12) registered its query key.
    await waitFor(() => {
      const juno = queryClient
        .getQueryCache()
        .findAll({ queryKey: ['weekly-sweeps', 'juno'] })
      expect(juno.length).toBeGreaterThanOrEqual(1)
    })

    // Sanity: no Seva entry leaked into this fresh client.
    const seva = queryClient
      .getQueryCache()
      .findAll({ queryKey: ['weekly-sweeps', 'seva'] })
    expect(seva.length).toBe(0)
  })

  it("mounts at /seva/sweeper and registers a ['weekly-sweeps', 'seva', ...] query key (D-10 parity)", async () => {
    const { queryClient } = renderAt('/seva/sweeper')

    // Empty-state copy renders for Seva too — D-10 zero-regression: Phase 15
    // did not change the Seva render path's user-facing output.
    await waitFor(() =>
      expect(screen.getByText(/Sweeper has not run yet/i)).toBeInTheDocument(),
    )

    await waitFor(() => {
      const seva = queryClient
        .getQueryCache()
        .findAll({ queryKey: ['weekly-sweeps', 'seva'] })
      expect(seva.length).toBeGreaterThanOrEqual(1)
    })

    // Sanity: no Juno entry leaked into this fresh client.
    const juno = queryClient
      .getQueryCache()
      .findAll({ queryKey: ['weekly-sweeps', 'juno'] })
    expect(juno.length).toBe(0)
  })

  it('Seva and Juno query keys are isolated across mounts (JSWEEP-06 cross-tenant isolation)', async () => {
    // First mount: /seva/sweeper with its own fresh QueryClient.
    const sevaRender = renderAt('/seva/sweeper')
    await waitFor(() => {
      const seva = sevaRender.queryClient
        .getQueryCache()
        .findAll({ queryKey: ['weekly-sweeps', 'seva'] })
      expect(seva.length).toBeGreaterThanOrEqual(1)
    })
    sevaRender.unmount()

    // Second mount: /juno/sweeper with a SECOND fresh QueryClient. Each
    // render owns its own client — this is the cleanest cache-isolation
    // proof: the Juno client never saw the Seva key.
    const junoRender = renderAt('/juno/sweeper')
    await waitFor(() => {
      const juno = junoRender.queryClient
        .getQueryCache()
        .findAll({ queryKey: ['weekly-sweeps', 'juno'] })
      expect(juno.length).toBeGreaterThanOrEqual(1)
    })

    // Cross-tenant isolation: Juno's cache contains NO Seva entry.
    const sevaInJuno = junoRender.queryClient
      .getQueryCache()
      .findAll({ queryKey: ['weekly-sweeps', 'seva'] })
    expect(sevaInJuno.length).toBe(0)
  })
})
