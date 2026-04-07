import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ContentPage } from './ContentPage'
import type { ContentBundleResponse, QueueListResponse, DraftItemResponse } from '@/api/types'

// Mock the API modules so we don't need MSW for page-level tests
vi.mock('@/api/content', () => ({
  getTodayContent: vi.fn(),
}))

vi.mock('@/api/queue', () => ({
  getQueue: vi.fn(),
  approveItem: vi.fn(),
  rejectItem: vi.fn(),
}))

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

import { getTodayContent } from '@/api/content'
import { getQueue, approveItem } from '@/api/queue'

const mockGetTodayContent = vi.mocked(getTodayContent)
const mockGetQueue = vi.mocked(getQueue)
const mockApproveItem = vi.mocked(approveItem)

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  }
}

const mockDraftItem: DraftItemResponse = {
  id: 'draft-001',
  platform: 'content',
  status: 'pending',
  alternatives: [
    { text: 'Draft text', type: 'long_post', label: 'Draft A' },
  ],
  created_at: new Date().toISOString(),
}

const threadBundle: ContentBundleResponse = {
  id: 'bundle-thread',
  story_headline: 'Central banks bought record gold',
  content_type: 'thread',
  no_story_flag: false,
  draft_content: { tweets: ['Tweet 1 about gold', 'Tweet 2 about reserves'] },
  deep_research: {
    corroborating_sources: [
      { title: 'WGC Source', url: 'https://gold.org', domain: 'gold.org' },
    ],
    rationale: 'Strong central bank buying narrative.',
  },
  quality_score: 8.5,
  created_at: new Date().toISOString(),
}

const longFormBundle: ContentBundleResponse = {
  id: 'bundle-longform',
  story_headline: 'Long form article about gold',
  content_type: 'long_form',
  no_story_flag: false,
  draft_content: { post: 'Full article text about gold markets and central banks...' },
  deep_research: { corroborating_sources: [], rationale: 'Good article.' },
  quality_score: 7.9,
  created_at: new Date().toISOString(),
}

const infographicBundle: ContentBundleResponse = {
  id: 'bundle-infographic',
  story_headline: 'Gold infographic story',
  content_type: 'infographic',
  no_story_flag: false,
  draft_content: {
    format: 'infographic',
    headline: 'Central Bank Gold Buying Reaches Record',
    key_stats: [
      { stat: '1,037 tonnes in 2023', source: 'WGC', source_url: 'https://gold.org' },
    ],
    visual_structure: 'bar chart',
    caption_text: 'Record central bank gold buying caption.',
  },
  deep_research: { corroborating_sources: [], rationale: 'Strong data story.' },
  quality_score: 9.0,
  created_at: new Date().toISOString(),
}

const noStoryBundle: ContentBundleResponse = {
  id: 'bundle-nostory',
  story_headline: '',
  no_story_flag: true,
  score: 5.2,
  quality_score: 5.2,
  created_at: new Date().toISOString(),
}

const emptyQueue: QueueListResponse = { items: [] }
const pendingQueue: QueueListResponse = { items: [mockDraftItem] }

describe('ContentPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    Object.assign(navigator, {
      clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
    })
  })

  describe('Thread format', () => {
    it('renders content bundle', async () => {
      mockGetTodayContent.mockResolvedValue(threadBundle)
      mockGetQueue.mockResolvedValue(pendingQueue)
      render(<ContentPage />, { wrapper: createWrapper() })
      await screen.findByText('Central banks bought record gold')
    })

    it('renders numbered tweet blocks for thread format', async () => {
      mockGetTodayContent.mockResolvedValue(threadBundle)
      mockGetQueue.mockResolvedValue(pendingQueue)
      render(<ContentPage />, { wrapper: createWrapper() })
      await screen.findByText('Tweet 1 about gold')
      expect(screen.getByText('Tweet 2 about reserves')).toBeInTheDocument()
    })
  })

  describe('Long form format', () => {
    it('renders textarea with post text', async () => {
      mockGetTodayContent.mockResolvedValue(longFormBundle)
      mockGetQueue.mockResolvedValue(pendingQueue)
      render(<ContentPage />, { wrapper: createWrapper() })
      await screen.findByText('Full article text about gold markets and central banks...')
    })
  })

  describe('Infographic format', () => {
    it('renders InfographicPreview component with INFOGRAPHIC BRIEF text', async () => {
      mockGetTodayContent.mockResolvedValue(infographicBundle)
      mockGetQueue.mockResolvedValue(pendingQueue)
      render(<ContentPage />, { wrapper: createWrapper() })
      await screen.findByText('INFOGRAPHIC BRIEF')
    })
  })

  describe('Sources section', () => {
    it('shows links from deep_research corroborating_sources', async () => {
      mockGetTodayContent.mockResolvedValue(threadBundle)
      mockGetQueue.mockResolvedValue(pendingQueue)
      render(<ContentPage />, { wrapper: createWrapper() })
      await screen.findByText('Sources')
      expect(screen.getByRole('link', { name: /gold\.org/i })).toBeInTheDocument()
    })
  })

  describe('Approve flow', () => {
    it('approve button calls mutation and copies correct clipboard text for thread format', async () => {
      mockGetTodayContent.mockResolvedValue(threadBundle)
      mockGetQueue.mockResolvedValue(pendingQueue)
      mockApproveItem.mockResolvedValue({ ...mockDraftItem, status: 'approved' })
      render(<ContentPage />, { wrapper: createWrapper() })
      const btn = await screen.findByRole('button', { name: /approve/i })
      fireEvent.click(btn)
      await waitFor(() => {
        expect(navigator.clipboard.writeText).toHaveBeenCalledWith('Tweet 1 about gold\n\nTweet 2 about reserves')
      })
    })
  })

  describe('404 / empty state', () => {
    it('shows empty state "No content today" when 404', async () => {
      mockGetTodayContent.mockRejectedValue(new Error('API error 404'))
      render(<ContentPage />, { wrapper: createWrapper() })
      await screen.findByText('No content today')
    })
  })

  describe('No story flag', () => {
    it('shows "No strong story found today" with score when no_story_flag is true', async () => {
      mockGetTodayContent.mockResolvedValue(noStoryBundle)
      mockGetQueue.mockResolvedValue(emptyQueue)
      render(<ContentPage />, { wrapper: createWrapper() })
      await screen.findByText(/No strong story found today/)
      expect(screen.getByText(/5\.2/)).toBeInTheDocument()
    })
  })

  describe('Already actioned', () => {
    it('shows read-only view with status badge when no pending DraftItem', async () => {
      const approvedDraft: DraftItemResponse = { ...mockDraftItem, status: 'approved' }
      mockGetTodayContent.mockResolvedValue(threadBundle)
      mockGetQueue.mockResolvedValue({ items: [approvedDraft] })
      render(<ContentPage />, { wrapper: createWrapper() })
      await screen.findByText('Central banks bought record gold')
      await waitFor(() => {
        expect(screen.queryByRole('button', { name: /approve/i })).not.toBeInTheDocument()
      })
    })
  })
})
