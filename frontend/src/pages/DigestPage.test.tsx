import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { server } from '@/mocks/node'
import { http, HttpResponse } from 'msw'
import { DigestPage } from './DigestPage'
import type { DailyDigestResponse } from '@/api/types'

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  }
}

const mockLatestDigest: DailyDigestResponse = {
  id: 'aaaaaaaa-0000-0000-0000-000000000001',
  digest_date: '2026-04-02',
  top_stories: [
    { headline: 'Gold hits $2,400', source: 'Kitco', url: 'https://kitco.com/1', score: 8.5 },
    { headline: 'Central banks add 1,037t in 2023', source: 'WGC', url: 'https://wgc.com/1', score: 8.2 },
    { headline: 'Mining costs stabilise at $1,248/oz AISC', source: 'Mining.com', url: 'https://mining.com/1', score: 7.9 },
    { headline: 'Silver-gold ratio hits 88:1', source: 'Kitco', url: 'https://kitco.com/2', score: 7.4 },
    { headline: 'Gold ETF inflows accelerate in Q1', source: 'JMN', url: 'https://jmn.com/1', score: 7.1 },
  ],
  queue_snapshot: { twitter: 3, instagram: 2, content: 1 },
  yesterday_approved: { count: 4, items: [] },
  yesterday_rejected: { count: 1, items: [] },
  yesterday_expired: { count: 2, items: [] },
  priority_alert: { message: 'Gold approaching $2,500 resistance' },
  created_at: new Date().toISOString(),
}

const mockLatestDigestNoAlert: DailyDigestResponse = {
  ...mockLatestDigest,
  priority_alert: null,
}

describe('DigestPage', () => {
  beforeEach(() => {
    // Mock localStorage — not available in this jsdom environment by default
    vi.stubGlobal('localStorage', {
      getItem: vi.fn().mockReturnValue(null),
      setItem: vi.fn(),
      removeItem: vi.fn(),
      clear: vi.fn(),
    })

    server.use(
      http.get('/digests/latest', () => {
        return HttpResponse.json(mockLatestDigest)
      }),
    )
  })

  it('renders today digest with all sections', async () => {
    render(<DigestPage />, { wrapper: createWrapper() })

    await waitFor(() => {
      expect(screen.getByText('Daily Digest')).toBeInTheDocument()
    })
    // Date displayed
    expect(screen.getByText('Thursday, April 2, 2026')).toBeInTheDocument()
    // Section headings present
    expect(screen.getByText('Top Stories')).toBeInTheDocument()
    expect(screen.getByText('Queue Snapshot')).toBeInTheDocument()
    expect(screen.getByText('Yesterday')).toBeInTheDocument()
  })

  it('shows top stories list', async () => {
    render(<DigestPage />, { wrapper: createWrapper() })

    await waitFor(() => {
      expect(screen.getByText('Gold hits $2,400')).toBeInTheDocument()
    })
    expect(screen.getByText('Central banks add 1,037t in 2023')).toBeInTheDocument()
    expect(screen.getByText('Mining costs stabilise at $1,248/oz AISC')).toBeInTheDocument()
    expect(screen.getByText('Silver-gold ratio hits 88:1')).toBeInTheDocument()
    expect(screen.getByText('Gold ETF inflows accelerate in Q1')).toBeInTheDocument()
  })

  it('shows queue snapshot cards', async () => {
    render(<DigestPage />, { wrapper: createWrapper() })

    await waitFor(() => {
      expect(screen.getByText('Twitter')).toBeInTheDocument()
    })
    expect(screen.getByText('Instagram')).toBeInTheDocument()
    expect(screen.getByText('Content')).toBeInTheDocument()
    // Check counts appear
    expect(screen.getByText('3')).toBeInTheDocument()
    expect(screen.getByText('2')).toBeInTheDocument()
    expect(screen.getByText('1')).toBeInTheDocument()
  })

  it('shows yesterday summary', async () => {
    render(<DigestPage />, { wrapper: createWrapper() })

    await waitFor(() => {
      expect(screen.getByText(/Approved: 4/)).toBeInTheDocument()
    })
    expect(screen.getByText(/Rejected: 1/)).toBeInTheDocument()
    expect(screen.getByText(/Expired: 2/)).toBeInTheDocument()
  })

  it('shows priority alert banner when present', async () => {
    render(<DigestPage />, { wrapper: createWrapper() })

    await waitFor(() => {
      expect(screen.getByText('Priority Alert')).toBeInTheDocument()
    })
    expect(screen.getByText(/Gold approaching \$2,500 resistance/)).toBeInTheDocument()
  })

  it('does not render alert banner when priority_alert is null', async () => {
    server.use(
      http.get('/digests/latest', () => {
        return HttpResponse.json(mockLatestDigestNoAlert)
      }),
    )

    render(<DigestPage />, { wrapper: createWrapper() })

    await waitFor(() => {
      expect(screen.getByText('Daily Digest')).toBeInTheDocument()
    })
    expect(screen.queryByText('Priority Alert')).not.toBeInTheDocument()
  })

  it('prev/next navigation changes date', async () => {
    render(<DigestPage />, { wrapper: createWrapper() })

    // Wait for initial load
    await waitFor(() => {
      expect(screen.getByText('Thursday, April 2, 2026')).toBeInTheDocument()
    })

    // Override handler to return prev date digest
    server.use(
      http.get('/digests/:date', ({ params }) => {
        const prevDigest: DailyDigestResponse = {
          id: 'aaaaaaaa-0000-0000-0000-000000000003',
          digest_date: params.date as string,
          top_stories: [{ headline: 'Prev day story', source: 'Kitco', url: 'https://kitco.com/prev', score: 7.0 }],
          queue_snapshot: { twitter: 1, instagram: 0, content: 0 },
          yesterday_approved: { count: 2, items: [] },
          yesterday_rejected: { count: 0, items: [] },
          yesterday_expired: { count: 1, items: [] },
          priority_alert: null,
          created_at: new Date().toISOString(),
        }
        return HttpResponse.json(prevDigest)
      }),
    )

    // Click prev button
    fireEvent.click(screen.getByRole('button', { name: /Previous digest/ }))

    await waitFor(() => {
      expect(screen.getByText('Wednesday, April 1, 2026')).toBeInTheDocument()
    })
    expect(screen.getByText('Prev day story')).toBeInTheDocument()
  })

  it('next button disabled at latest date', async () => {
    render(<DigestPage />, { wrapper: createWrapper() })

    await waitFor(() => {
      expect(screen.getByText('Thursday, April 2, 2026')).toBeInTheDocument()
    })

    const nextBtn = screen.getByRole('button', { name: /Next digest/ })
    expect(nextBtn).toBeDisabled()
  })

  it('shows empty state for 404', async () => {
    server.use(
      http.get('/digests/latest', () => {
        return new HttpResponse(null, { status: 404 })
      }),
    )

    render(<DigestPage />, { wrapper: createWrapper() })

    await waitFor(() => {
      expect(screen.getByText('No digest available')).toBeInTheDocument()
    })
    expect(screen.getByText(/No digest has been generated for this date/)).toBeInTheDocument()
  })
})
