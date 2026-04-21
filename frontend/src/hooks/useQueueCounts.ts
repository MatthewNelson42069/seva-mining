import { useQuery } from '@tanstack/react-query'
import { getQueue } from '@/api/queue'

interface QueueCounts {
  content: number
  contentHasMore: boolean
}

// Single-agent system post quick-260420-sn9 (Twitter purged) — content-only counts.
export function useQueueCounts(): QueueCounts {
  const co = useQuery({
    queryKey: ['queue-count', 'content'],
    queryFn: () => getQueue({ platform: 'content', status: 'pending', limit: 100 }),
    staleTime: 60_000,
  })

  return {
    content: co.data?.items.length ?? 0,
    contentHasMore: !!co.data?.next_cursor,
  }
}
