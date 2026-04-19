import { describe, it, expect } from 'vitest'
import { server } from '@/mocks/node'
import { http, HttpResponse } from 'msw'
import { getContentBundle, rerenderContentBundle } from '../content'
import type { ContentBundleDetailResponse, RerenderResponse } from '../types'

const mockBundle: ContentBundleDetailResponse = {
  id: 'abc-123',
  story_headline: 'African central banks gold accumulation',
  content_type: 'infographic',
  no_story_flag: false,
  draft_content: { headline: 'Gold reserves surge' },
  rendered_images: null,
  created_at: new Date().toISOString(),
}

const mockRerenderResponse: RerenderResponse = {
  bundle_id: 'abc-123',
  render_job_id: 'rerender_abc-123_1234567890',
  enqueued_at: new Date().toISOString(),
}

describe('content-bundle api', () => {
  it('getContentBundle fetches GET /content-bundles/:id', async () => {
    server.use(
      http.get('/content-bundles/:id', ({ params }) => {
        expect(params.id).toBe('abc-123')
        return HttpResponse.json(mockBundle)
      }),
    )

    const result = await getContentBundle('abc-123')
    expect(result.id).toBe('abc-123')
    expect(result.story_headline).toBe('African central banks gold accumulation')
    expect(result.content_type).toBe('infographic')
  })

  it('getContentBundle throws on 404', async () => {
    server.use(
      http.get('/content-bundles/:id', () => {
        return new HttpResponse(null, { status: 404 })
      }),
    )

    await expect(getContentBundle('not-found')).rejects.toThrow('API error 404')
  })

  it('rerenderContentBundle posts to /content-bundles/:id/rerender', async () => {
    server.use(
      http.post('/content-bundles/:id/rerender', ({ params }) => {
        expect(params.id).toBe('abc-123')
        return HttpResponse.json(mockRerenderResponse, { status: 202 })
      }),
    )

    const result = await rerenderContentBundle('abc-123')
    expect(result.bundle_id).toBe('abc-123')
    expect(result.render_job_id).toBe('rerender_abc-123_1234567890')
    expect(result.enqueued_at).toBeDefined()
  })

  it('rerenderContentBundle throws on 404', async () => {
    server.use(
      http.post('/content-bundles/:id/rerender', () => {
        return new HttpResponse(null, { status: 404 })
      }),
    )

    await expect(rerenderContentBundle('not-found')).rejects.toThrow('API error 404')
  })
})
