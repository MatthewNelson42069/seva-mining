import { useQueries } from '@tanstack/react-query'
import { getQueue } from '@/api/queue'
import { CONTENT_AGENT_TABS } from '@/config/agentTabs'

/**
 * Per-content-type pending-queue counts.
 *
 * Returns a map keyed by each sub-agent's DB `contentType`. quick-260421-eoe:
 * the Sidebar renders one badge per sub-agent, so we parallelise 7 queries
 * via `useQueries` (TanStack Query dedupes concurrent identical keys and the
 * payload is tiny — `limit=100` is an upper-bound probe; if the server
 * reports `next_cursor` we render "100+").
 */
export interface QueueCountEntry {
  count: number
  hasMore: boolean
}
export type QueueCountsMap = Record<string, QueueCountEntry>

export function useQueueCounts(): QueueCountsMap {
  const results = useQueries({
    queries: CONTENT_AGENT_TABS.map((tab) => ({
      queryKey: ['queue-count', 'content', tab.contentType],
      queryFn: () =>
        getQueue({
          platform: 'content',
          status: 'pending',
          contentType: tab.contentType,
          limit: 100,
        }),
      staleTime: 60_000,
    })),
  })

  const map: QueueCountsMap = {}
  CONTENT_AGENT_TABS.forEach((tab, idx) => {
    const data = results[idx]?.data
    map[tab.contentType] = {
      count: data?.items.length ?? 0,
      hasMore: !!data?.next_cursor,
    }
  })
  return map
}
