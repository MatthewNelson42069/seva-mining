import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { PerAgentQueuePage } from './PerAgentQueuePage'
import type { QueueListResponse, AgentRunResponse, DraftItemResponse } from '@/api/types'

vi.mock('@/api/queue', () => ({
  getQueue: vi.fn(),
  approveItem: vi.fn(),
  rejectItem: vi.fn(),
}))

vi.mock('@/api/settings', () => ({
  getAgentRuns: vi.fn().mockResolvedValue([]),
}))

import { getQueue } from '@/api/queue'
import { getAgentRuns } from '@/api/settings'
const mockGetQueue = vi.mocked(getQueue)
const mockGetAgentRuns = vi.mocked(getAgentRuns)

function makeRun(overrides: Partial<AgentRunResponse> = {}): AgentRunResponse {
  return {
    id: overrides.id ?? 'run-1',
    agent_name: overrides.agent_name ?? 'sub_gold_media',
    started_at: overrides.started_at ?? '2026-04-22T19:00:00Z',
    items_found: overrides.items_found,
    items_queued: overrides.items_queued ?? 0,
    notes: overrides.notes ?? undefined,
    status: overrides.status ?? 'completed',
    created_at: overrides.created_at ?? '2026-04-22T19:00:00Z',
  }
}

function makeItem(overrides: Partial<DraftItemResponse> = {}): DraftItemResponse {
  return {
    id: overrides.id ?? 'item-1',
    platform: 'content',
    status: overrides.status ?? 'pending',
    created_at: overrides.created_at ?? '2026-04-22T19:05:00Z',
    alternatives: overrides.alternatives ?? [],
  }
}

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
    mockGetAgentRuns.mockResolvedValue([])
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

  it('renders the Gold Media tab (slug gold-media) and queries with contentType=gold_media', async () => {
    renderAt('/agents/gold-media')
    await screen.findByText('Gold Media Queue')
    await waitFor(() => {
      expect(mockGetQueue).toHaveBeenCalledWith(
        expect.objectContaining({ platform: 'content', contentType: 'gold_media' })
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

  // D-01: Zero-item run renders "No content found" with RunHeader intact
  it('renders "No content found" for a zero-item run and still shows the RunHeader', async () => {
    const run = makeRun({ id: 'run-zero', items_queued: 0 })
    mockGetAgentRuns.mockResolvedValueOnce([run])
    mockGetQueue.mockResolvedValue(emptyQueue)
    renderAt('/agents/gold-media')
    await waitFor(() => {
      expect(screen.getByText('No content found')).toBeInTheDocument()
    })
    expect(screen.getByText(/Pulled from agent run at/)).toBeInTheDocument()
  })

  // D-03: Timeline interleaves zero and non-zero runs in chronological order (newest first)
  it('interleaves zero and non-zero runs in chronological order', async () => {
    const runA = makeRun({ id: 'run-a', started_at: '2026-04-22T01:00:00Z', items_queued: 2 })
    const runB = makeRun({ id: 'run-b', started_at: '2026-04-22T03:00:00Z', items_queued: 0 })
    mockGetAgentRuns.mockResolvedValueOnce([runA, runB])
    // 2 items created between runA and runB start times — attach to runA
    const item1 = makeItem({ id: 'item-1', created_at: '2026-04-22T01:05:00Z' })
    const item2 = makeItem({ id: 'item-2', created_at: '2026-04-22T01:10:00Z' })
    mockGetQueue.mockResolvedValue({ items: [item1, item2] })
    const { container } = renderAt('/agents/gold-media')
    await waitFor(() => {
      expect(screen.getByText('No content found')).toBeInTheDocument()
    })
    // runB (newer, zero-item) should appear BEFORE runA (older, has items) in the DOM
    const allHeaders = screen.getAllByText(/Pulled from agent run at/)
    expect(allHeaders).toHaveLength(2)
    // Check DOM ordering: the first RunHeader group should contain "No content found"
    // and the second should not (it has items). Use container textContent positions.
    const content = container.textContent ?? ''
    const posNoContent = content.indexOf('No content found')
    // Both headers are present; "No content found" should appear before the second group
    // We verify by checking that posNoContent is less than the position of second header text.
    // The first occurrence of "Pulled from agent run at" should be in runB's group (newer = first).
    const firstHeaderPos = content.indexOf('Pulled from agent run at')
    const secondHeaderPos = content.indexOf('Pulled from agent run at', firstHeaderPos + 1)
    expect(firstHeaderPos).toBeGreaterThanOrEqual(0)
    expect(secondHeaderPos).toBeGreaterThan(firstHeaderPos)
    // "No content found" must appear after the first header but before the second header
    expect(posNoContent).toBeGreaterThan(firstHeaderPos)
    expect(posNoContent).toBeLessThan(secondHeaderPos)
  })

  // D-02: Notes telemetry subtitle — three sub-cases
  it('renders notes telemetry subtitle when present; omits when null or malformed', async () => {
    // Sub-case (a): all fields present, compliance_blocked=0 suppressed
    const runWithNotes = makeRun({
      id: 'run-notes',
      items_queued: 3,
      notes: '{"x_candidates":12,"llm_accepted":3,"compliance_blocked":0,"queued":2}',
    })
    mockGetAgentRuns.mockResolvedValueOnce([runWithNotes])
    const item = makeItem({ id: 'item-notes', created_at: '2026-04-22T19:05:00Z' })
    mockGetQueue.mockResolvedValue({ items: [item] })
    const { unmount } = renderAt('/agents/gold-media')
    await waitFor(() => {
      expect(screen.getByText('12 candidates · 3 accepted · 2 queued')).toBeInTheDocument()
    })
    expect(screen.queryByText(/blocked/)).not.toBeInTheDocument()
    unmount()

    // Sub-case (b): compliance_blocked > 0 IS shown
    const runWithBlocked = makeRun({
      id: 'run-blocked',
      items_queued: 3,
      notes: '{"x_candidates":12,"llm_accepted":3,"compliance_blocked":4,"queued":2}',
    })
    mockGetAgentRuns.mockResolvedValueOnce([runWithBlocked])
    mockGetQueue.mockResolvedValue({ items: [item] })
    const { unmount: unmount2 } = renderAt('/agents/gold-media')
    await waitFor(() => {
      expect(screen.getByText('12 candidates · 3 accepted · 4 blocked · 2 queued')).toBeInTheDocument()
    })
    unmount2()

    // Sub-case (c): notes=null → no telemetry line (candidates/accepted/queued text absent)
    const runNullNotes = makeRun({ id: 'run-null', items_queued: 1, notes: undefined })
    mockGetAgentRuns.mockResolvedValueOnce([runNullNotes])
    mockGetQueue.mockResolvedValue({ items: [item] })
    const { unmount: unmount3 } = renderAt('/agents/gold-media')
    await waitFor(() => {
      expect(screen.getByText(/Pulled from agent run at/)).toBeInTheDocument()
    })
    expect(screen.queryByText(/candidates/)).not.toBeInTheDocument()
    expect(screen.queryByText(/accepted/)).not.toBeInTheDocument()
    unmount3()

    // Sub-case (d): malformed JSON → no telemetry line, no crash
    const runMalformed = makeRun({ id: 'run-malformed', items_queued: 0, notes: 'not-valid-json{' })
    mockGetAgentRuns.mockResolvedValueOnce([runMalformed])
    mockGetQueue.mockResolvedValue(emptyQueue)
    renderAt('/agents/gold-media')
    await waitFor(() => {
      expect(screen.getByText('No content found')).toBeInTheDocument()
    })
    expect(screen.queryByText(/candidates/)).not.toBeInTheDocument()
  })

  // D-04 inverse: items.length === 0 AND runs.length > 0 → timeline, NOT EmptyState
  it('renders timeline (not EmptyState) when items=0 but runs exist', async () => {
    const run = makeRun({ id: 'run-empty-items', items_queued: 0 })
    mockGetAgentRuns.mockResolvedValueOnce([run])
    mockGetQueue.mockResolvedValue(emptyQueue)
    renderAt('/agents/gold-media')
    await waitFor(() => {
      expect(screen.getByText('No content found')).toBeInTheDocument()
    })
    expect(screen.queryByText('Queue is clear')).not.toBeInTheDocument()
  })
})
