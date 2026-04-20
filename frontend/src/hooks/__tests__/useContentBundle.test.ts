import { describe, it, expect } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { server } from '@/mocks/node'
import { http, HttpResponse } from 'msw'
import React from 'react'
import { useContentBundle } from '../useContentBundle'
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

// ---- basic fetch tests -------------------------------------------------------

describe('useContentBundle — basic fetch', () => {
  it('fetches bundle when bundleId is provided', async () => {
    const bundle = makeBundle()
    server.use(
      http.get('/content-bundles/:id', () => HttpResponse.json(bundle)),
    )

    const queryClient = freshQueryClient()
    const { result } = renderHook(() => useContentBundle('abc-123'), {
      wrapper: createWrapper(queryClient),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.id).toBe('abc-123')
    expect(result.current.data?.story_headline).toBe('African central banks gold accumulation')
  })

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
