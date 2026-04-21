import { http, HttpResponse } from 'msw'
import type {
  DraftItemResponse, QueueListResponse, TokenResponse,
  WatchlistResponse, KeywordResponse,
} from '@/api/types'

// Mock data updated in quick-260420-sn9 — Twitter agent purged; Instagram was
// purged in quick-260419-lvy. Sevamining is now a single-agent system (content only).
const mockItems: DraftItemResponse[] = [
  {
    id: '66666666-6666-6666-6666-666666666666',
    platform: 'content',
    status: 'pending',
    source_url: 'https://www.kitco.com/news/gold-reserves-2024',
    source_text: 'Global gold reserves hit record as central banks continue buying spree',
    score: 8.7,
    quality_score: 9.1,
    alternatives: [
      { text: 'Central Bank Gold Accumulation: The Structural Shift Reshaping the Gold Market\n\nWhen the WGC reported 1,037 tonnes of central bank gold purchases in 2023, most coverage focused on the headline number. The more important story is the composition and what it signals about the next decade of demand...', type: 'long_post', label: 'Long-form Post' },
      { text: 'Thread: Why central banks buying gold at record pace matters more than the ATH price\n\n1/ The 1,037t purchased in 2023 represents 24% of annual mine supply. That\'s a structural demand floor that didn\'t exist 15 years ago.\n\n2/ The buyers: Turkey, China, Poland, India, Singapore. Notice anything? All reducing USD reserve concentration.\n\n3/ This isn\'t tactical — it\'s generational reserve diversification. The \'we need an alternative to dollar reserves\' conversation has moved from academic to operational.', type: 'thread', label: 'Thread' },
    ],
    rationale: 'Strong Kitco story on central bank buying. High quality score. Thread + long-post alternatives drafted.',
    urgency: 'high',
    created_at: new Date(Date.now() - 21600000).toISOString(),
  },
]

export const handlers = [
  http.get('/queue', ({ request }) => {
    const url = new URL(request.url)
    const platform = url.searchParams.get('platform')
    const status = url.searchParams.get('status')

    let items = mockItems
    if (platform) items = items.filter(i => i.platform === platform)
    if (status) items = items.filter(i => i.status === status)

    const response: QueueListResponse = {
      items,
      next_cursor: undefined,
    }
    return HttpResponse.json(response)
  }),

  http.patch('/items/:id/approve', async ({ params }) => {
    const item = mockItems.find(i => i.id === params.id)
    if (!item) return new HttpResponse(null, { status: 404 })
    return HttpResponse.json({ ...item, status: 'approved' } as DraftItemResponse)
  }),

  http.patch('/items/:id/reject', async ({ params }) => {
    const item = mockItems.find(i => i.id === params.id)
    if (!item) return new HttpResponse(null, { status: 404 })
    return HttpResponse.json({ ...item, status: 'rejected' } as DraftItemResponse)
  }),

  http.post('/auth/login', async ({ request }) => {
    const body = await request.json() as { password: string }
    if (body.password === 'test-password') {
      const response: TokenResponse = {
        access_token: 'mock-jwt-token-for-testing',
        token_type: 'bearer',
      }
      return HttpResponse.json(response)
    }
    return new HttpResponse(null, { status: 401 })
  }),

  http.get('/digests/latest', () => {
    return HttpResponse.json({
      id: 'digest-1',
      digest_date: '2026-04-02',
      top_stories: [
        { headline: 'Gold hits $2,400', source: 'Kitco', url: 'https://kitco.com/1', score: 8.5 },
        { headline: 'Central bank buying accelerates', source: 'Mining.com', url: 'https://mining.com/1', score: 8.2 },
        { headline: 'Silver ratio at extremes', source: 'JMN', url: 'https://jmn.com/1', score: 7.8 },
        { headline: 'Kinross Q1 beats', source: 'WGC', url: 'https://wgc.com/1', score: 7.5 },
        { headline: 'Inflation data boosts gold', source: 'Kitco', url: 'https://kitco.com/2', score: 7.2 },
      ],
      queue_snapshot: { content: 1, total: 1 },
      yesterday_approved: { count: 4, items: [] },
      yesterday_rejected: { count: 1, items: [] },
      yesterday_expired: { count: 2, items: [] },
      priority_alert: null,
      created_at: new Date().toISOString(),
    })
  }),

  http.get('/digests/:date', ({ params }) => {
    if (params.date === '1999-01-01') {
      return new HttpResponse(null, { status: 404 })
    }
    return HttpResponse.json({
      id: 'digest-2',
      digest_date: params.date,
      top_stories: [],
      queue_snapshot: { content: 0, total: 0 },
      yesterday_approved: { count: 0, items: [] },
      yesterday_rejected: { count: 0, items: [] },
      yesterday_expired: { count: 0, items: [] },
      priority_alert: null,
      created_at: new Date().toISOString(),
    })
  }),

  http.get('/content/today', () => {
    return HttpResponse.json({
      id: 'bundle-1',
      story_headline: 'Central Bank Gold Accumulation',
      content_type: 'thread',
      no_story_flag: false,
      draft_content: { tweets: ['Tweet 1', 'Tweet 2', 'Tweet 3'] },
      deep_research: {
        corroborating_sources: [
          { title: 'Source 1', url: 'https://example.com/1' },
          { title: 'Source 2', url: 'https://example.com/2' },
        ],
      },
      created_at: new Date().toISOString(),
    })
  }),

  http.get('/watchlists', ({ request }) => {
    // Watchlists UI tab removed in quick-260420-sn9; endpoint retained for
    // backwards compatibility but returns empty by default in mocks.
    const url = new URL(request.url)
    const platform = url.searchParams.get('platform')
    const allWatchlists: WatchlistResponse[] = []
    const filtered = platform ? allWatchlists.filter(w => w.platform === platform) : allWatchlists
    return HttpResponse.json(filtered)
  }),

  http.post('/watchlists', async ({ request }) => {
    const body = await request.json() as WatchlistResponse
    return HttpResponse.json({ ...body, id: 'wl-new', active: true, created_at: new Date().toISOString() }, { status: 201 })
  }),

  http.patch('/watchlists/:id', async ({ params, request }) => {
    const body = await request.json() as Partial<WatchlistResponse>
    return HttpResponse.json({ id: params.id, platform: 'content', account_handle: '@updated', active: true, created_at: new Date().toISOString(), ...body })
  }),

  http.delete('/watchlists/:id', () => {
    return new HttpResponse(null, { status: 204 })
  }),

  http.get('/keywords', () => {
    const keywords: KeywordResponse[] = [
      {
        id: 'kw-1',
        term: 'gold price',
        platform: 'content',
        weight: 1.0,
        active: true,
        created_at: new Date().toISOString(),
      },
      {
        id: 'kw-2',
        term: 'central bank',
        platform: 'content',
        weight: 0.8,
        active: true,
        created_at: new Date().toISOString(),
      },
    ]
    return HttpResponse.json(keywords)
  }),

  http.post('/keywords', async ({ request }) => {
    const body = await request.json() as KeywordResponse
    return HttpResponse.json({ ...body, id: 'kw-new', active: true, created_at: new Date().toISOString() }, { status: 201 })
  }),

  http.patch('/keywords/:id', async ({ params, request }) => {
    const body = await request.json() as Partial<KeywordResponse>
    return HttpResponse.json({ id: params.id, term: 'gold price', active: true, created_at: new Date().toISOString(), ...body })
  }),

  http.delete('/keywords/:id', () => {
    return new HttpResponse(null, { status: 204 })
  }),

  http.get('/agent-runs', () => {
    return HttpResponse.json([
      { id: 'run-3', agent_name: 'content_agent', started_at: new Date().toISOString(), status: 'error', items_found: 0, items_queued: 0, items_filtered: 0, errors: { message: 'API timeout' }, created_at: new Date().toISOString() },
      { id: 'run-4', agent_name: 'morning_digest', started_at: new Date().toISOString(), status: 'success', items_found: 0, items_queued: 0, items_filtered: 0, created_at: new Date().toISOString() },
    ])
  }),

  http.get('/config', () => {
    return HttpResponse.json([
      { key: 'content_relevance_weight', value: '0.4' },
      { key: 'content_recency_weight', value: '0.3' },
      { key: 'content_credibility_weight', value: '0.3' },
      { key: 'content_quality_threshold', value: '7.0' },
    ])
  }),

  http.patch('/config/:key', async ({ params, request }) => {
    const body = await request.json() as { value: string }
    return HttpResponse.json({ key: params.key, value: body.value })
  }),

  // /config/quota endpoint removed in quick-260420-sn9 (Twitter agent purged — no consumer).

  // mfy pivot — content-bundle detail (no rerender, no rendered_images)
  http.get('/content-bundles/:id', ({ params }) => {
    return HttpResponse.json({
      id: params.id,
      story_headline: 'Mock headline',
      content_type: 'infographic',
      no_story_flag: false,
      draft_content: {},
      created_at: new Date().toISOString(),
    })
  }),
]
