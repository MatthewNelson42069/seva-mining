import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'

import * as summariesApi from '@/api/summaries'
import { SummaryFeedPage } from '../SummaryFeedPage'

type UseSummariesResult = ReturnType<typeof summariesApi.useSummaries>

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  )
}

function mockUseSummaries(value: Partial<UseSummariesResult>) {
  vi.spyOn(summariesApi, 'useSummaries').mockReturnValue(value as UseSummariesResult)
}

describe('SummaryFeedPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('renders the empty state when summaries array is empty', () => {
    mockUseSummaries({ data: { summaries: [], total: 0 }, isLoading: false, error: null } as Partial<UseSummariesResult>)
    render(<SummaryFeedPage />, { wrapper: makeWrapper() })
    expect(screen.getByText(/Waiting for first summary\. Next fire at /)).toBeInTheDocument()
  })

  it('empty state next-fire time is "08:00 PT" or "12:00 PT"', () => {
    mockUseSummaries({ data: { summaries: [], total: 0 }, isLoading: false, error: null } as Partial<UseSummariesResult>)
    render(<SummaryFeedPage />, { wrapper: makeWrapper() })
    const text = screen.getByText(/Waiting for first summary/).textContent ?? ''
    expect(text).toMatch(/Next fire at (08:00|12:00) PT/)
  })

  it('renders one SummaryCard per row in the response', () => {
    mockUseSummaries({
      data: {
        summaries: [
          { id: 'a', generated_at: '2026-04-27T15:00:00Z', period_label: '08:00 PT',
            gold_news_md: null, ontario_law_md: null, ontario_stats_md: null,
            status: 'completed', error_text: null },
          { id: 'b', generated_at: '2026-04-27T19:00:00Z', period_label: '12:00 PT',
            gold_news_md: null, ontario_law_md: null, ontario_stats_md: null,
            status: 'completed', error_text: null },
        ],
        total: 2,
      },
      isLoading: false,
      error: null,
    } as Partial<UseSummariesResult>)
    render(<SummaryFeedPage />, { wrapper: makeWrapper() })
    const titles = screen.getAllByRole('heading', { level: 2 })
    expect(titles.length).toBe(2)
  })

  it('renders the loading state when isLoading is true', () => {
    mockUseSummaries({ data: undefined, isLoading: true, error: null } as Partial<UseSummariesResult>)
    render(<SummaryFeedPage />, { wrapper: makeWrapper() })
    expect(screen.getByText(/Loading/i)).toBeInTheDocument()
  })

  it('renders the error state when error is set', () => {
    mockUseSummaries({ data: undefined, isLoading: false, error: new Error('boom') } as Partial<UseSummariesResult>)
    render(<SummaryFeedPage />, { wrapper: makeWrapper() })
    expect(screen.getByText(/Failed to load summaries/i)).toBeInTheDocument()
  })
})
