import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { PerAgentQueuePage } from './PerAgentQueuePage'
import type { QueueListResponse } from '@/api/types'

vi.mock('@/api/queue', () => ({
  getQueue: vi.fn(),
  approveItem: vi.fn(),
  rejectItem: vi.fn(),
}))

vi.mock('@/api/settings', () => ({
  getAgentRuns: vi.fn().mockResolvedValue([]),
}))

import { getQueue } from '@/api/queue'
const mockGetQueue = vi.mocked(getQueue)

function renderAt(path: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/agents/:slug" element={<PerAgentQueuePage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

const emptyQueue: QueueListResponse = { items: [] }

describe('PerAgentQueuePage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetQueue.mockResolvedValue(emptyQueue)
  })

  it('renders the Breaking News tab and queries with contentType=breaking_news', async () => {
    renderAt('/agents/breaking-news')
    await screen.findByText('Breaking News Queue')
    await waitFor(() => {
      expect(mockGetQueue).toHaveBeenCalledWith(
        expect.objectContaining({ platform: 'content', contentType: 'breaking_news' })
      )
    })
  })

  it('renders the Threads tab and queries with contentType=thread (DB value, not slug)', async () => {
    renderAt('/agents/threads')
    await screen.findByText('Threads Queue')
    await waitFor(() => {
      expect(mockGetQueue).toHaveBeenCalledWith(
        expect.objectContaining({ platform: 'content', contentType: 'thread' })
      )
    })
  })

  it('renders the Long-form tab and queries with contentType=long_form', async () => {
    renderAt('/agents/long-form')
    await screen.findByText('Long-form Queue')
    await waitFor(() => {
      expect(mockGetQueue).toHaveBeenCalledWith(
        expect.objectContaining({ platform: 'content', contentType: 'long_form' })
      )
    })
  })

  it('renders the Gold Media tab (slug gold-media) and queries with contentType=video_clip', async () => {
    renderAt('/agents/gold-media')
    await screen.findByText('Gold Media Queue')
    await waitFor(() => {
      expect(mockGetQueue).toHaveBeenCalledWith(
        expect.objectContaining({ platform: 'content', contentType: 'video_clip' })
      )
    })
  })

  it('redirects unknown slug to /agents/breaking-news', async () => {
    renderAt('/agents/foobar-nonsense')
    // After redirect the Breaking News page should render.
    await screen.findByText('Breaking News Queue')
    await waitFor(() => {
      expect(mockGetQueue).toHaveBeenCalledWith(
        expect.objectContaining({ contentType: 'breaking_news' })
      )
    })
  })
})
