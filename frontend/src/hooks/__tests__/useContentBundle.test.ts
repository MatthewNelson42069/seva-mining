import { describe, it, expect, vi, afterEach } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { server } from '@/mocks/node'
import { http, HttpResponse } from 'msw'
import React from 'react'
import { useContentBundle, useRerenderContentBundle } from '../useContentBundle'
import type { ContentBundleDetailResponse } from '@/api/types'

// ---- helpers ----------------------------------------------------------------

function createWrapper(queryClient: QueryClient) {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(QueryClientProvider, { client: queryClient }, children)
  }
}

function makeBundle(overrides: Partial<ContentBundleDetailResponse> = {}): ContentBundleDetailResponse {
  return {
    id: 'abc-123',
    story_headline: 'African central banks gold accumulation',
    content_type: 'infographic',
    no_story_flag: false,
    draft_content: {},
    rendered_images: null,
    created_at: new Date().toISOString(),
    ...overrides,
  }
}

function freshQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  })
}

// ---- refetchInterval logic tests -------------------------------------------
// These tests directly exercise the refetchInterval callback logic by inspecting
// the TanStack Query v5 query object after the hook mounts. This avoids the
// fake-timer/waitFor deadlock while still testing the correct stop conditions.

describe('useContentBundle — polling semantics (refetchInterval logic)', () => {
  it('polls every 5s while rendered_images is null and bundle is <10min old', async () => {
    const bundle = makeBundle({ rendered_images: null })
    server.use(
      http.get('/content-bundles/:id', () => HttpResponse.json(bundle)),
    )

    const queryClient = freshQueryClient()
    const { result } = renderHook(() => useContentBundle('abc-123'), {
      wrapper: createWrapper(queryClient),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    // Extract the live query from the cache and call its computed refetchInterval
    const query = queryClient.getQueryCache().find({ queryKey: ['content-bundle', 'abc-123'] })!
    // The query options on the live query contain refetchInterval as a function
    const interval = (query.options as { refetchInterval?: (q: typeof query) => number | false }).refetchInterval
    expect(typeof interval).toBe('function')
    // Call it with the real query — data has rendered_images: null, bundle is recent
    const result2 = interval!(query)
    expect(result2).toBe(5000)
  })

  it('stops polling once rendered_images has length >= 1', async () => {
    const bundle = makeBundle({
      rendered_images: [
        { role: 'twitter_visual', url: 'https://r2.example.com/img.png', generated_at: new Date().toISOString() },
      ],
    })
    server.use(
      http.get('/content-bundles/:id', () => HttpResponse.json(bundle)),
    )

    const queryClient = freshQueryClient()
    const { result } = renderHook(() => useContentBundle('abc-123'), {
      wrapper: createWrapper(queryClient),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    const query = queryClient.getQueryCache().find({ queryKey: ['content-bundle', 'abc-123'] })!
    const interval = (query.options as { refetchInterval?: (q: typeof query) => number | false }).refetchInterval
    expect(typeof interval).toBe('function')
    // Data has rendered_images with length 1 — should return false
    const result2 = interval!(query)
    expect(result2).toBe(false)
  })

  it('stops polling after bundle is older than 10 minutes', async () => {
    const elevenMinutesAgo = new Date(Date.now() - 11 * 60 * 1000).toISOString()
    const bundle = makeBundle({ rendered_images: null, created_at: elevenMinutesAgo })
    server.use(
      http.get('/content-bundles/:id', () => HttpResponse.json(bundle)),
    )

    const queryClient = freshQueryClient()
    const { result } = renderHook(() => useContentBundle('abc-123'), {
      wrapper: createWrapper(queryClient),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    const query = queryClient.getQueryCache().find({ queryKey: ['content-bundle', 'abc-123'] })!
    const interval = (query.options as { refetchInterval?: (q: typeof query) => number | false }).refetchInterval
    expect(typeof interval).toBe('function')
    // Bundle is 11 min old with null images — age > 10 min ceiling, should return false
    const result2 = interval!(query)
    expect(result2).toBe(false)
  })
})

// ---- disabled states -------------------------------------------------------

describe('useContentBundle — disabled when bundleId is falsy', () => {
  it('is disabled when bundleId is null', () => {
    const queryClient = freshQueryClient()
    const { result } = renderHook(() => useContentBundle(null), {
      wrapper: createWrapper(queryClient),
    })
    expect(result.current.fetchStatus).toBe('idle')
    expect(result.current.data).toBeUndefined()
  })

  it('is disabled when bundleId is undefined', () => {
    const queryClient = freshQueryClient()
    const { result } = renderHook(() => useContentBundle(undefined), {
      wrapper: createWrapper(queryClient),
    })
    expect(result.current.fetchStatus).toBe('idle')
    expect(result.current.data).toBeUndefined()
  })

  it('is disabled when bundleId is empty string', () => {
    const queryClient = freshQueryClient()
    const { result } = renderHook(() => useContentBundle(''), {
      wrapper: createWrapper(queryClient),
    })
    expect(result.current.fetchStatus).toBe('idle')
    expect(result.current.data).toBeUndefined()
  })
})

// ---- useRerenderContentBundle -----------------------------------------------

describe('useRerenderContentBundle', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('fires POST and invalidates the content-bundle query on success', async () => {
    server.use(
      http.post('/content-bundles/:id/rerender', ({ params }) => {
        return HttpResponse.json(
          {
            bundle_id: params.id,
            render_job_id: `rerender_${params.id}_abc`,
            enqueued_at: new Date().toISOString(),
          },
          { status: 202 },
        )
      }),
    )

    const queryClient = freshQueryClient()
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')

    const { result } = renderHook(() => useRerenderContentBundle('abc-123'), {
      wrapper: createWrapper(queryClient),
    })

    await act(async () => {
      result.current.mutate()
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(invalidateSpy).toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: ['content-bundle', 'abc-123'] }),
    )
  })
})
