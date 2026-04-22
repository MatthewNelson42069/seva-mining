import { render, screen, cleanup } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import React from 'react'
import { ContentDetailModal } from '../ContentDetailModal'
import type { DraftItemResponse, ContentBundleDetailResponse } from '@/api/types'

// ---------------------------------------------------------------------------
// Mock useContentBundle so each test can control query state
// ---------------------------------------------------------------------------
vi.mock('@/hooks/useContentBundle', () => ({
  useContentBundle: vi.fn(),
}))

import { useContentBundle } from '@/hooks/useContentBundle'
const mockUseContentBundle = vi.mocked(useContentBundle)

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  })
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(QueryClientProvider, { client: queryClient }, children)
  }
}

function makeItem(overrides: Partial<DraftItemResponse> = {}): DraftItemResponse {
  return {
    id: 'item-001',
    platform: 'content',
    status: 'pending',
    source_text: 'African central banks are accumulating gold\nSecond line',
    source_account: '@goldanalyst',
    score: 8.5,
    alternatives: [
      { text: 'Draft text for fallback', type: 'long_post', label: 'Draft A' },
    ],
    engagement_snapshot: { content_bundle_id: 'bundle-abc' },
    created_at: new Date().toISOString(),
    ...overrides,
  }
}

function makeBundle(overrides: Partial<ContentBundleDetailResponse> = {}): ContentBundleDetailResponse {
  return {
    id: 'bundle-abc',
    story_headline: 'African Central Banks Accumulate Gold',
    content_type: 'infographic',
    no_story_flag: false,
    draft_content: {
      format: 'infographic',
      suggested_headline: 'Gold Reserves Surge',
      data_facts: ['1,037 tonnes purchased Q1'],
      image_prompt: 'You are building a Seva Mining asset...',
    },
    created_at: new Date().toISOString(),
    ...overrides,
  }
}

function renderModal(item: DraftItemResponse = makeItem()) {
  return render(
    <ContentDetailModal item={item} isOpen={true} onClose={() => {}} />,
    { wrapper: createWrapper() },
  )
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------
describe('ContentDetailModal format-aware (mfy pivot)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
      configurable: true,
    })
  })

  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  // Test 1 — infographic dispatches to InfographicPreview (three-field shape)
  it('renders InfographicPreview with three text blocks when bundle.content_type === "infographic"', () => {
    const bundle = makeBundle({ content_type: 'infographic' })
    mockUseContentBundle.mockReturnValue({
      data: bundle,
      isError: false,
      isLoading: false,
    } as ReturnType<typeof useContentBundle>)

    renderModal()

    // InfographicPreview renders "INFOGRAPHIC" label
    expect(screen.getByText(/INFOGRAPHIC/i)).toBeInTheDocument()
    // Suggested Headline block
    expect(screen.getByText(/Suggested Headline/i)).toBeInTheDocument()
    // Key Facts block
    expect(screen.getByText(/Key Facts/i)).toBeInTheDocument()
    // Image Prompt block
    expect(screen.getByText(/Image Prompt/i)).toBeInTheDocument()
    // No RenderedImagesGallery / Regenerate images button
    expect(screen.queryByRole('button', { name: /Regenerate images/i })).not.toBeInTheDocument()
  })

  // Test C: no RenderedImagesGallery for any format
  it('does not render RenderedImagesGallery for infographic bundles', () => {
    const bundle = makeBundle({ content_type: 'infographic' })
    mockUseContentBundle.mockReturnValue({
      data: bundle,
      isError: false,
      isLoading: false,
    } as ReturnType<typeof useContentBundle>)

    renderModal()

    expect(screen.queryByText(/Rendered images/i)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Regenerate images/i })).not.toBeInTheDocument()
  })

  // Test 2 — thread format dispatches to ThreadPreview; no gallery
  it('renders ThreadPreview when bundle.content_type === "thread"', () => {
    const bundle = makeBundle({
      content_type: 'thread',
      draft_content: {
        format: 'thread',
        tweets: ['Tweet one about gold.', 'Tweet two with stats.'],
        long_form_post: 'Long form version here.',
      },
    })
    mockUseContentBundle.mockReturnValue({
      data: bundle,
      isError: false,
      isLoading: false,
    } as ReturnType<typeof useContentBundle>)

    renderModal()

    const threadLabels = screen.getAllByText(/THREAD/i)
    expect(threadLabels.length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('Tweet one about gold.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Regenerate images/i })).not.toBeInTheDocument()
  })

  // Test 3 — long_form
  it('renders LongFormPreview when bundle.content_type === "long_form"', () => {
    const bundle = makeBundle({
      content_type: 'long_form',
      draft_content: {
        format: 'long_form',
        post: 'A detailed long-form post about gold markets.',
      },
    })
    mockUseContentBundle.mockReturnValue({
      data: bundle,
      isError: false,
      isLoading: false,
    } as ReturnType<typeof useContentBundle>)

    renderModal()

    const labels = screen.getAllByText(/LONG-FORM POST/i)
    expect(labels.length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('A detailed long-form post about gold markets.')).toBeInTheDocument()
  })

  // Test 4 — breaking_news
  it('renders BreakingNewsPreview when bundle.content_type === "breaking_news"', () => {
    const bundle = makeBundle({
      content_type: 'breaking_news',
      draft_content: {
        format: 'breaking_news',
        tweet: 'BREAKING: Gold surpasses $3,000/oz for the first time.',
      },
    })
    mockUseContentBundle.mockReturnValue({
      data: bundle,
      isError: false,
      isLoading: false,
    } as ReturnType<typeof useContentBundle>)

    renderModal()

    expect(screen.getByText(/BREAKING NEWS/i)).toBeInTheDocument()
    expect(screen.getByText('BREAKING: Gold surpasses $3,000/oz for the first time.')).toBeInTheDocument()
  })

  // Test 5 — quote renders QuotePreview (no RenderedImagesGallery)
  it('renders QuotePreview when bundle.content_type === "quote" and no RenderedImagesGallery', () => {
    const bundle = makeBundle({
      content_type: 'quote',
      draft_content: {
        format: 'quote',
        twitter_post: 'Gold never lies.',
        speaker: 'Warren Buffett',
        source_url: 'https://berkshire.com',
      },
      created_at: new Date().toISOString(),
    })
    mockUseContentBundle.mockReturnValue({
      data: bundle,
      isError: false,
      isLoading: false,
    } as ReturnType<typeof useContentBundle>)

    renderModal()

    expect(screen.getByText(/QUOTE/i)).toBeInTheDocument()
    expect(screen.getByText('Gold never lies.')).toBeInTheDocument()
    // No Regenerate images button — rendering is gone
    expect(screen.queryByRole('button', { name: /Regenerate images/i })).not.toBeInTheDocument()
  })

  // Test D: no <img> tags for infographic or quote
  it('does not render any <img> elements for infographic format', () => {
    const bundle = makeBundle({ content_type: 'infographic' })
    mockUseContentBundle.mockReturnValue({
      data: bundle,
      isError: false,
      isLoading: false,
    } as ReturnType<typeof useContentBundle>)

    const { container } = renderModal()
    expect(container.querySelector('img')).toBeNull()
  })

  // Test 6 — gold_media; no gallery
  it('renders GoldMediaPreview when bundle.content_type === "gold_media" and no gallery', () => {
    const bundle = makeBundle({
      content_type: 'gold_media',
      draft_content: {
        format: 'gold_media',
        twitter_caption: 'Watch the gold market analysis clip.',
        video_url: 'https://youtube.com/watch?v=abc',
      },
    })
    mockUseContentBundle.mockReturnValue({
      data: bundle,
      isError: false,
      isLoading: false,
    } as ReturnType<typeof useContentBundle>)

    renderModal()

    expect(screen.getByText(/GOLD MEDIA/i)).toBeInTheDocument()
    expect(screen.getByText('Watch the gold market analysis clip.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Regenerate images/i })).not.toBeInTheDocument()
  })

  // Test 7 — fallback to flat text on bundle fetch error (D-24)
  it('falls back to flat DraftAlternative.text when bundle fetch fails (D-24)', () => {
    mockUseContentBundle.mockReturnValue({
      data: undefined,
      isError: true,
      isLoading: false,
    } as ReturnType<typeof useContentBundle>)

    const item = makeItem()
    renderModal(item)

    expect(screen.getByText('Draft text for fallback')).toBeInTheDocument()
    expect(screen.queryByText(/INFOGRAPHIC/i)).not.toBeInTheDocument()
  })

  // Test 8 — fallback for unknown content_type
  it('falls back to flat text when bundle.content_type is unknown', () => {
    const bundle = makeBundle({ content_type: 'unknown_format' })
    mockUseContentBundle.mockReturnValue({
      data: bundle,
      isError: false,
      isLoading: false,
    } as ReturnType<typeof useContentBundle>)

    renderModal()

    expect(screen.getByText('Draft text for fallback')).toBeInTheDocument()
  })

  // Test 9 — headline from bundle.story_headline
  it('shows bundle.story_headline in dialog title', () => {
    const bundle = makeBundle({ content_type: 'infographic' })
    mockUseContentBundle.mockReturnValue({
      data: bundle,
      isError: false,
      isLoading: false,
    } as ReturnType<typeof useContentBundle>)

    renderModal()

    expect(screen.getByText('African Central Banks Accumulate Gold')).toBeInTheDocument()
  })
})
