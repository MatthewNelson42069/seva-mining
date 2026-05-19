/** @vitest-environment jsdom */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import type { ReactNode } from 'react'
import { describe, expect, it, vi, beforeEach } from 'vitest'

import * as weeklySweepsApi from '@/api/weeklySweeps'
import type { WeeklySweepCard } from '@/api/weeklySweeps'
import { SweeperCard } from '@/components/viral/SweeperCard'
import WeeklyViralSweeperPage from '@/pages/WeeklyViralSweeperPage'

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  // eslint-disable-next-line react/display-name
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  )
}

function mockUseWeeklySweeps(value: Partial<ReturnType<typeof weeklySweepsApi.useWeeklySweeps>>) {
  vi.spyOn(weeklySweepsApi, 'useWeeklySweeps').mockReturnValue(
    value as ReturnType<typeof weeklySweepsApi.useWeeklySweeps>,
  )
}

function mkSweep(overrides: Partial<WeeklySweepCard> = {}): WeeklySweepCard {
  return {
    id: 'sweep-1',
    generated_at: '2026-05-17T15:00:00Z',
    week_start: '2026-05-11',
    week_end: '2026-05-17',
    reddit_top_md: '### Top X Posts This Week\n\n* @analyst1: hello',
    story_virality_md: '### Most Cross-Referenced Stories\n\n* Story A',
    content_angles_md: '### 3 Content Angles\n\n#### Angle 1: foo',
    status: 'completed',
    error_text: null,
    agent_run_id: null,
    ...overrides,
  }
}

describe('WeeklyViralSweeperPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('renders empty state when total is 0', () => {
    mockUseWeeklySweeps({
      data: { sweeps: [], total: 0 },
      isLoading: false,
      error: null,
    } as any)
    render(<WeeklyViralSweeperPage />, { wrapper: makeWrapper() })
    expect(screen.getByText(/Sweeper has not run yet/i)).toBeInTheDocument()
    // SWEEP-14 copy includes the PT fire time
    const text = screen.getByText(/Sweeper has not run yet/).textContent ?? ''
    expect(text).toMatch(/08:00 PT/)
  })

  it('renders the latest sweep as the default selection', () => {
    const sweeps = [mkSweep({ id: 'a', week_start: '2026-05-11', week_end: '2026-05-17' })]
    mockUseWeeklySweeps({
      data: { sweeps, total: 1 },
      isLoading: false,
      error: null,
    } as any)
    render(<WeeklyViralSweeperPage />, { wrapper: makeWrapper() })
    // The card title should match the latest sweep
    expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent(/Weekly Sweep/i)
    // No <select> when only 1 sweep
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument()
  })

  it('shows week-picker dropdown when 2+ sweeps exist', () => {
    const sweeps = [
      mkSweep({ id: 'a', week_start: '2026-05-11', week_end: '2026-05-17' }),
      mkSweep({ id: 'b', week_start: '2026-05-04', week_end: '2026-05-10' }),
      mkSweep({ id: 'c', week_start: '2026-04-27', week_end: '2026-05-03' }),
    ]
    mockUseWeeklySweeps({
      data: { sweeps, total: 3 },
      isLoading: false,
      error: null,
    } as any)
    render(<WeeklyViralSweeperPage />, { wrapper: makeWrapper() })
    const select = screen.getByRole('combobox') as HTMLSelectElement
    expect(select).toBeInTheDocument()
    expect(select.options.length).toBe(3)
  })

  it('renders loading state', () => {
    mockUseWeeklySweeps({
      data: undefined,
      isLoading: true,
      error: null,
    } as any)
    render(<WeeklyViralSweeperPage />, { wrapper: makeWrapper() })
    expect(screen.getByText(/Loading/i)).toBeInTheDocument()
  })

  it('renders error state', () => {
    mockUseWeeklySweeps({
      data: undefined,
      isLoading: false,
      error: new Error('boom'),
    } as any)
    render(<WeeklyViralSweeperPage />, { wrapper: makeWrapper() })
    expect(screen.getByText(/Failed to load/i)).toBeInTheDocument()
  })
})

describe('SweeperCard', () => {
  it('hides status badge when status is completed', () => {
    render(<SweeperCard sweep={mkSweep({ status: 'completed' })} />)
    // No banner copy should render for completed sweeps
    expect(screen.queryByText(/Sweeper had partial output/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/Sweeper failed last run/i)).not.toBeInTheDocument()
  })

  it('shows partial banner when status is partial', () => {
    render(<SweeperCard sweep={mkSweep({ status: 'partial' })} />)
    expect(screen.getByText(/Sweeper had partial output/i)).toBeInTheDocument()
  })

  it('shows failed banner when status is failed', () => {
    render(<SweeperCard sweep={mkSweep({ status: 'failed' })} />)
    expect(screen.getByText(/Sweeper failed last run/i)).toBeInTheDocument()
  })

  it('renders all 3 markdown sections when populated', () => {
    const sweep = mkSweep()
    render(<SweeperCard sweep={sweep} />)
    // Each section's markdown heading renders as an h3 — distinct text fragments
    expect(screen.getByText(/Top X Posts This Week/i)).toBeInTheDocument()
    expect(screen.getByText(/Most Cross-Referenced Stories/i)).toBeInTheDocument()
    expect(screen.getByText(/3 Content Angles/i)).toBeInTheDocument()
  })
})
