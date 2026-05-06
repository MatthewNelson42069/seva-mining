import { describe, expect, it, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'

import { getSummaries, useSummaries } from '../summaries'
import * as client from '../client'

function makeWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  // eslint-disable-next-line react/display-name
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  )
}

describe('getSummaries', () => {
  beforeEach(() => vi.restoreAllMocks())

  it('calls /summaries?limit=60 by default', async () => {
    const spy = vi.spyOn(client, 'apiFetch').mockResolvedValue({
      summaries: [], total: 0,
    })
    await getSummaries()
    expect(spy).toHaveBeenCalledWith('/summaries?limit=60')
  })

  it('calls /summaries?limit=30 when limit=30', async () => {
    const spy = vi.spyOn(client, 'apiFetch').mockResolvedValue({
      summaries: [], total: 0,
    })
    await getSummaries(30)
    expect(spy).toHaveBeenCalledWith('/summaries?limit=30')
  })
})

describe('useSummaries', () => {
  beforeEach(() => vi.restoreAllMocks())

  it('returns React-Query result with data after fetch resolves', async () => {
    vi.spyOn(client, 'apiFetch').mockResolvedValue({
      summaries: [{
        id: 'abc', generated_at: '2026-05-05T15:00:00Z', period_label: '08:00 PT',
        gold_news_md: '## hi', ontario_law_md: null, ontario_stats_md: null,
        status: 'completed', error_text: null,
      }],
      total: 1,
    })
    const { result } = renderHook(() => useSummaries(), { wrapper: makeWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.summaries.length).toBe(1)
  })
})
