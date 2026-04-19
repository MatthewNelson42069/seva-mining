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
  useRerenderContentBundle: vi.fn(() => ({
    mutate: vi.fn(),
    isPending: false,
  })),
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
      headline: 'Gold Reserves Surge',
      key_stats: [{ stat: '1,037 tonnes', source: 'WGC', source_url: 'https://gold.org' }],
      visual_structure: 'bar chart',
      caption_text: 'Central banks reshaping demand.',
    },
    rendered_images: null,
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
describe('ContentDetailModal format-aware (Plan 11-06)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  // Test 1 — infographic dispatches to InfographicPreview + RenderedImagesGallery
  it('renders InfographicPreview when bundle.content_type === "infographic"', () => {
    const bundle = makeBundle({ content_type: 'infographic' })
    mockUseContentBundle.mockReturnValue({
      data: bundle,
      isError: false,
      isLoading: false,
    } as ReturnType<typeof useContentBundle>)

    renderModal()

    // InfographicPreview renders the "INFOGRAPHIC BRIEF" label
    expect(screen.getByText(/INFOGRAPHIC BRIEF/i)).toBeInTheDocument()
    // headline from bundle
    expect(screen.getByText('Gold Reserves Surge')).toBeInTheDocument()
  })

  // Test 2 — thread format dispatches to ThreadPreview; no gallery
  it('renders ThreadPreview when bundle.content_type === "thread" and no RenderedImagesGallery', () => {
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

    // ThreadPreview renders "THREAD" label (multiple matches due to "Copy Thread" button is fine — use getAllByText)
    const threadLabels = screen.getAllByText(/THREAD/i)
    expect(threadLabels.length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('Tweet one about gold.')).toBeInTheDocument()
    // No "Regenerate images" button for text-only formats
    expect(screen.queryByRole('button', { name: /Regenerate images/i })).not.toBeInTheDocument()
  })

  // Test 3 — long_form
  it('renders LongFormPreview when bundle.content_type === "long_form"', () => {
    const bundle = makeBundle({
      content_type: 'long_form',
      draft_content: {
        format: 'long_form',
        post_text: 'A detailed long-form post about gold markets.',
      },
    })
    mockUseContentBundle.mockReturnValue({
      data: bundle,
      isError: false,
      isLoading: false,
    } as ReturnType<typeof useContentBundle>)

    renderModal()

    // "LONG-FORM POST" appears in header span AND in "Copy Post" button text — use getAllByText
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

  // Test 5 — quote renders QuotePreview AND RenderedImagesGallery (expectedCount=2)
  it('renders QuotePreview and RenderedImagesGallery when bundle.content_type === "quote"', () => {
    const bundle = makeBundle({
      content_type: 'quote',
      draft_content: {
        format: 'quote',
        twitter_post: 'Gold never lies.',
        instagram_post: 'Gold never lies. #gold',
        attributed_to: 'Warren Buffett',
        source_url: 'https://berkshire.com',
      },
      rendered_images: [],
      // fresh bundle — triggers polling skeleton
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
    // RenderedImagesGallery appears for quote (expectedCount=2)
    expect(screen.getByRole('button', { name: /Regenerate images/i })).toBeInTheDocument()
  })

  // Test 6 — video_clip; no gallery
  it('renders VideoClipPreview when bundle.content_type === "video_clip" and no gallery', () => {
    const bundle = makeBundle({
      content_type: 'video_clip',
      draft_content: {
        format: 'video_clip',
        twitter_caption: 'Watch the gold market analysis clip.',
        instagram_caption: 'Gold market analysis. #gold #mining',
        video_url: 'https://youtube.com/watch?v=abc',
      },
    })
    mockUseContentBundle.mockReturnValue({
      data: bundle,
      isError: false,
      isLoading: false,
    } as ReturnType<typeof useContentBundle>)

    renderModal()

    expect(screen.getByText(/VIDEO CLIP/i)).toBeInTheDocument()
    expect(screen.getByText('Watch the gold market analysis clip.')).toBeInTheDocument()
    // No gallery for video_clip
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

    // Should show the flat alternative text
    expect(screen.getByText('Draft text for fallback')).toBeInTheDocument()
    // Should NOT show any format preview label
    expect(screen.queryByText(/INFOGRAPHIC BRIEF/i)).not.toBeInTheDocument()
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

  // Test 9 — skeleton + "Rendering images…" for fresh infographic with no images
  it('shows skeleton placeholders + "Rendering images…" for fresh infographic with no images', () => {
    const bundle = makeBundle({
      content_type: 'infographic',
      rendered_images: [],
      created_at: new Date().toISOString(), // fresh — age < 10 min
    })
    mockUseContentBundle.mockReturnValue({
      data: bundle,
      isError: false,
      isLoading: false,
    } as ReturnType<typeof useContentBundle>)

    renderModal()

    // RenderedImagesGallery should show "Rendering images…" text
    expect(screen.getByText(/Rendering images/i)).toBeInTheDocument()
    // Should show skeleton loading divs
    const loadingElements = screen.getAllByLabelText('Loading image')
    expect(loadingElements.length).toBe(4) // infographic = 4 expected
  })

  // Test 10 — hides skeletons after 10 minutes with no images
  it('hides image slots gracefully when bundle is >10min old and no rendered_images', () => {
    const oldDate = new Date(Date.now() - 15 * 60 * 1000).toISOString() // 15 min ago
    const bundle = makeBundle({
      content_type: 'infographic',
      rendered_images: [],
      created_at: oldDate,
    })
    mockUseContentBundle.mockReturnValue({
      data: bundle,
      isError: false,
      isLoading: false,
    } as ReturnType<typeof useContentBundle>)

    renderModal()

    // Should NOT show skeleton placeholders or "Rendering images…"
    expect(screen.queryByText(/Rendering images/i)).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Loading image')).not.toBeInTheDocument()
    // But regen button should still be present
    expect(screen.getByRole('button', { name: /Regenerate images/i })).toBeInTheDocument()
  })

  // Test 11 — regen button disabled while polling (fresh bundle, no images)
  it('Regenerate images button is disabled while isPolling is true', () => {
    const bundle = makeBundle({
      content_type: 'infographic',
      rendered_images: [],
      created_at: new Date().toISOString(), // fresh — triggers polling
    })
    mockUseContentBundle.mockReturnValue({
      data: bundle,
      isError: false,
      isLoading: false,
    } as ReturnType<typeof useContentBundle>)

    renderModal()

    const regenButton = screen.getByRole('button', { name: /Regenerate images/i })
    // Button should be disabled while polling (isPolling = true for fresh bundle with no images)
    expect(regenButton).toBeDisabled()
  })

  // Test 12 — structured brief renders immediately even if images still loading (D-13)
  it('renders structured brief content immediately alongside skeleton gallery (D-13)', () => {
    const bundle = makeBundle({
      content_type: 'infographic',
      draft_content: {
        format: 'infographic',
        headline: 'Gold Accumulation Brief',
        key_stats: [{ stat: '1,037 tonnes', source: 'WGC', source_url: 'https://gold.org' }],
        visual_structure: 'bar chart',
        caption_text: 'Caption text here.',
      },
      rendered_images: [],
      created_at: new Date().toISOString(), // fresh — skeleton state
    })
    mockUseContentBundle.mockReturnValue({
      data: bundle,
      isError: false,
      isLoading: false,
    } as ReturnType<typeof useContentBundle>)

    renderModal()

    // Brief should be visible
    expect(screen.getByText('Gold Accumulation Brief')).toBeInTheDocument()
    expect(screen.getByText(/INFOGRAPHIC BRIEF/i)).toBeInTheDocument()
    // Gallery skeleton should ALSO be visible at the same time
    expect(screen.getByText(/Rendering images/i)).toBeInTheDocument()
  })
})
