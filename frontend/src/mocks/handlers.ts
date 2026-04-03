import { http, HttpResponse } from 'msw'
import type {
  DraftItemResponse, QueueListResponse, TokenResponse,
  DailyDigestResponse, WatchlistResponse, KeywordResponse,
  AgentRunResponse, ConfigEntry, QuotaResponse,
} from '@/api/types'

const mockItems: DraftItemResponse[] = [
  {
    id: '11111111-1111-1111-1111-111111111111',
    platform: 'twitter',
    status: 'pending',
    source_url: 'https://x.com/goldwatcher/status/123',
    source_text: 'Gold breaks $2,400 resistance — watch for continuation above 2,420 before loading.',
    source_account: '@goldwatcher',
    follower_count: 45200,
    score: 8.2,
    quality_score: 7.8,
    alternatives: [
      { text: 'The 2,400 break matters because it clears the March 2024 high. Next technical level is 2,450 — the 78.6% Fib retracement from the 2020 low.', type: 'reply', label: 'Draft A' },
      { text: 'Central bank accumulation is doing the heavy lifting here. WGC data shows 1,037 tonnes purchased in 2023 — that bid doesn\'t go away on a daily chart move.', type: 'reply', label: 'Draft B' },
    ],
    rationale: 'High engagement tweet from credible technical account. Breaking key resistance level with specific price targets.',
    urgency: 'high',
    created_at: new Date(Date.now() - 3600000).toISOString(),
  },
  {
    id: '22222222-2222-2222-2222-222222222222',
    platform: 'twitter',
    status: 'pending',
    source_url: 'https://x.com/mininganalyst/status/456',
    source_text: 'Central banks bought 1,037 tonnes of gold in 2023. Pace accelerating in Q1 2024.',
    source_account: '@mininganalyst',
    follower_count: 12800,
    score: 7.5,
    quality_score: 8.1,
    alternatives: [
      { text: 'The demand shift is structural: 1,037t in 2023 vs 450t average 2010-2020. Central banks aren\'t buying as a hedge anymore — they\'re diversifying away from dollar reserves.', type: 'reply', label: 'Draft A' },
      { text: 'Worth noting: Turkey, China, and Poland account for ~40% of that 1,037t. Concentrated demand from nations actively reducing USD exposure.', type: 'reply', label: 'Draft B' },
      { text: 'Q1 2024 pace would imply 1,200t annual run rate if sustained. That\'s the kind of floor demand that makes price dips shallow.', type: 'retweet', label: 'RT Quote' },
    ],
    rationale: 'Macro-level data point with strong engagement. Central bank buying is core narrative for gold sector.',
    urgency: 'medium',
    created_at: new Date(Date.now() - 7200000).toISOString(),
  },
  {
    id: '33333333-3333-3333-3333-333333333333',
    platform: 'twitter',
    status: 'pending',
    source_url: 'https://x.com/juniormines/status/789',
    source_text: 'Kinross Q1 results beat on production. All-in sustaining costs at $1,248/oz — below guidance.',
    source_account: '@juniormines',
    follower_count: 8900,
    score: 6.8,
    quality_score: 7.2,
    alternatives: [
      { text: 'AISC at $1,248 with gold at $2,200+ means $950/oz margin. At current strip ratio that\'s 43% operating margin — the best in Kinross history.', type: 'reply', label: 'Draft A' },
      { text: 'Production beat + cost miss is the typical junior pattern. Kinross executing on both metrics is the story here — puts them in conversation for a premium rating.', type: 'reply', label: 'Draft B' },
    ],
    rationale: 'Q1 earnings beat with AISC detail. Strong engagement from mining community.',
    urgency: 'medium',
    created_at: new Date(Date.now() - 10800000).toISOString(),
  },
  {
    id: '44444444-4444-4444-4444-444444444444',
    platform: 'instagram',
    status: 'pending',
    source_url: 'https://www.instagram.com/p/goldpost1',
    source_text: 'Gold at all-time highs. What does this mean for miners? Our breakdown.',
    source_account: '@goldanalysis_ig',
    follower_count: 87500,
    score: 7.9,
    quality_score: 8.3,
    alternatives: [
      { text: 'The lever that rarely gets discussed: gold miner margins expand exponentially above AISC. At $1,250 AISC and $2,400 gold, a 10% price move = a 67% margin expansion. That\'s operating leverage at work.', type: 'comment', label: 'Draft A' },
      { text: 'All-time high in nominal terms. In real terms (inflation-adjusted), gold peaked in 1980. The rerating case for gold still has substantial room — that\'s the context most coverage skips.', type: 'comment', label: 'Draft B' },
    ],
    rationale: 'High-follower account discussing ATH gold. Educational content angle fits the audience.',
    urgency: 'low',
    created_at: new Date(Date.now() - 14400000).toISOString(),
  },
  {
    id: '55555555-5555-5555-5555-555555555555',
    platform: 'instagram',
    status: 'pending',
    source_url: 'https://www.instagram.com/p/silverpost1',
    source_text: 'Silver-to-gold ratio hits 88:1. Historically extreme. Watch for mean reversion.',
    source_account: '@preciousmetals_daily',
    follower_count: 34200,
    score: 7.1,
    quality_score: 7.4,
    alternatives: [
      { text: '88:1 is 2 standard deviations above the 30-year mean of 67:1. The last three times this ratio reached these levels (2008, 2016, 2020), silver outperformed gold by 40-80% in the following 18 months.', type: 'comment', label: 'Draft A' },
      { text: 'The ratio tells you relative value, not direction. Both metals can fall with the ratio staying wide — or both rally with silver leading. Industrial demand is the swing factor for silver here.', type: 'comment', label: 'Draft B' },
    ],
    rationale: 'Silver-gold ratio discussion from credible PM account. Technical setup with historical context.',
    urgency: 'low',
    created_at: new Date(Date.now() - 18000000).toISOString(),
  },
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

  // Digests
  http.get('/digests/latest', () => {
    const digest: DailyDigestResponse = {
      id: 'aaaaaaaa-0000-0000-0000-000000000001',
      digest_date: '2026-04-02',
      top_stories: [
        { headline: 'Gold hits $2,400', source: 'Kitco', url: 'https://kitco.com/1', score: 8.5 },
        { headline: 'Central banks buy record gold', source: 'WGC', url: 'https://wgc.com/1', score: 8.2 },
        { headline: 'Mining output up 3% in Q1', source: 'Mining.com', url: 'https://mining.com/1', score: 7.9 },
        { headline: 'Silver-gold ratio hits 88:1', source: 'Kitco', url: 'https://kitco.com/2', score: 7.5 },
        { headline: 'Fed hold signals gold strength', source: 'JMN', url: 'https://jmn.com/1', score: 7.2 },
      ],
      queue_snapshot: { twitter: 3, instagram: 2, content: 1 },
      yesterday_approved: { count: 4, items: [] },
      yesterday_rejected: { count: 1, items: [] },
      yesterday_expired: { count: 2, items: [] },
      priority_alert: null,
      created_at: new Date().toISOString(),
    }
    return HttpResponse.json(digest)
  }),

  http.get('/digests/:date', ({ params }) => {
    if (params.date === '1999-01-01') {
      return new HttpResponse(null, { status: 404 })
    }
    const digest: DailyDigestResponse = {
      id: 'aaaaaaaa-0000-0000-0000-000000000002',
      digest_date: params.date as string,
      top_stories: [
        { headline: 'Gold at $2,350', source: 'Kitco', url: 'https://kitco.com/3', score: 7.8 },
      ],
      queue_snapshot: { twitter: 2, instagram: 1, content: 0 },
      yesterday_approved: { count: 2, items: [] },
      yesterday_rejected: { count: 0, items: [] },
      yesterday_expired: { count: 1, items: [] },
      priority_alert: null,
      created_at: new Date().toISOString(),
    }
    return HttpResponse.json(digest)
  }),

  // Content
  http.get('/content/today', () => {
    return HttpResponse.json({
      id: 'bbbbbbbb-0000-0000-0000-000000000001',
      story_headline: 'Gold breaks $2,400 resistance on central bank demand',
      story_url: 'https://kitco.com/news/gold-2400',
      source_name: 'Kitco',
      format_type: 'thread',
      score: 8.5,
      quality_score: 8.2,
      no_story_flag: false,
      deep_research: {
        corroborating_sources: [
          { title: 'Source 1', url: 'https://example.com/1' },
          { title: 'Source 2', url: 'https://example.com/2' },
        ],
      },
      draft_content: { tweets: ['Tweet 1', 'Tweet 2', 'Tweet 3'] },
      compliance_passed: true,
      created_at: new Date().toISOString(),
    })
  }),

  // Watchlists
  http.get('/watchlists', () => {
    const items: WatchlistResponse[] = [
      {
        id: 'cccccccc-0000-0000-0000-000000000001',
        platform: 'twitter',
        account_handle: '@goldwatcher',
        relationship_value: 5,
        follower_threshold: 1000,
        active: true,
        created_at: new Date().toISOString(),
      },
      {
        id: 'cccccccc-0000-0000-0000-000000000002',
        platform: 'instagram',
        account_handle: '@goldanalysis_ig',
        relationship_value: 4,
        active: true,
        created_at: new Date().toISOString(),
      },
    ]
    return HttpResponse.json(items)
  }),

  http.post('/watchlists', async ({ request }) => {
    const body = await request.json() as WatchlistResponse
    return HttpResponse.json(
      { id: 'cccccccc-0000-0000-0000-000000000099', ...body, active: body.active ?? true, created_at: new Date().toISOString() },
      { status: 201 }
    )
  }),

  http.patch('/watchlists/:id', async ({ params, request }) => {
    const body = await request.json() as Partial<WatchlistResponse>
    return HttpResponse.json({
      id: params.id,
      platform: 'twitter',
      account_handle: '@goldwatcher',
      active: true,
      created_at: new Date().toISOString(),
      ...body,
    })
  }),

  http.delete('/watchlists/:id', () => {
    return new HttpResponse(null, { status: 204 })
  }),

  // Keywords
  http.get('/keywords', () => {
    const items: KeywordResponse[] = [
      {
        id: 'dddddddd-0000-0000-0000-000000000001',
        term: 'gold mining',
        platform: 'twitter',
        weight: 1.5,
        active: true,
        created_at: new Date().toISOString(),
      },
      {
        id: 'dddddddd-0000-0000-0000-000000000002',
        term: '$GLD',
        platform: undefined,
        weight: 1.0,
        active: true,
        created_at: new Date().toISOString(),
      },
    ]
    return HttpResponse.json(items)
  }),

  http.post('/keywords', async ({ request }) => {
    const body = await request.json() as KeywordResponse
    return HttpResponse.json(
      { id: 'dddddddd-0000-0000-0000-000000000099', ...body, active: body.active ?? true, created_at: new Date().toISOString() },
      { status: 201 }
    )
  }),

  http.patch('/keywords/:id', async ({ params, request }) => {
    const body = await request.json() as Partial<KeywordResponse>
    return HttpResponse.json({
      id: params.id,
      term: 'gold mining',
      active: true,
      created_at: new Date().toISOString(),
      ...body,
    })
  }),

  http.delete('/keywords/:id', () => {
    return new HttpResponse(null, { status: 204 })
  }),

  // Agent runs
  http.get('/agent-runs', () => {
    const items: AgentRunResponse[] = [
      {
        id: 'eeeeeeee-0000-0000-0000-000000000001',
        agent_name: 'twitter_agent',
        started_at: new Date(Date.now() - 7200000).toISOString(),
        ended_at: new Date(Date.now() - 7100000).toISOString(),
        items_found: 12,
        items_queued: 5,
        items_filtered: 7,
        status: 'completed',
        created_at: new Date(Date.now() - 7200000).toISOString(),
      },
      {
        id: 'eeeeeeee-0000-0000-0000-000000000002',
        agent_name: 'instagram_agent',
        started_at: new Date(Date.now() - 14400000).toISOString(),
        ended_at: new Date(Date.now() - 14300000).toISOString(),
        items_found: 8,
        items_queued: 3,
        items_filtered: 5,
        status: 'completed',
        created_at: new Date(Date.now() - 14400000).toISOString(),
      },
      {
        id: 'eeeeeeee-0000-0000-0000-000000000003',
        agent_name: 'content_agent',
        started_at: new Date(Date.now() - 3600000).toISOString(),
        ended_at: new Date(Date.now() - 3500000).toISOString(),
        items_found: 1,
        items_queued: 1,
        items_filtered: 0,
        status: 'completed',
        created_at: new Date(Date.now() - 3600000).toISOString(),
      },
    ]
    return HttpResponse.json(items)
  }),

  // Config — IMPORTANT: /config/quota must be listed before /config/:key
  http.get('/config/quota', () => {
    const quota: QuotaResponse = {
      monthly_tweet_count: 3400,
      quota_safety_margin: 1500,
      monthly_cap: 10000,
      reset_date: '2026-05-01',
    }
    return HttpResponse.json(quota)
  }),

  http.get('/config', () => {
    const entries: ConfigEntry[] = [
      { key: 'content_relevance_weight', value: '0.4' },
      { key: 'content_recency_weight', value: '0.3' },
      { key: 'content_credibility_weight', value: '0.3' },
      { key: 'content_quality_threshold', value: '7.0' },
    ]
    return HttpResponse.json(entries)
  }),

  http.patch('/config/:key', async ({ params, request }) => {
    const body = await request.json() as { value: string }
    return HttpResponse.json({ key: params.key, value: body.value })
  }),
]
