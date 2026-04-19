import { useQuery } from '@tanstack/react-query'
import { getQueue } from '@/api/queue'

interface QueueCounts {
  twitter: number
  twitterHasMore: boolean
  content: number
  contentHasMore: boolean
}

export function useQueueCounts(): QueueCounts {
  const tw = useQuery({
    queryKey: ['queue-count', 'twitter'],
    queryFn: () => getQueue({ platform: 'twitter', status: 'pending', limit: 100 }),
    staleTime: 60_000,
  })
  const co = useQuery({
    queryKey: ['queue-count', 'content'],
    queryFn: () => getQueue({ platform: 'content', status: 'pending', limit: 100 }),
    staleTime: 60_000,
  })

  return {
    twitter: tw.data?.items.length ?? 0,
    twitterHasMore: !!tw.data?.next_cursor,
    content: co.data?.items.length ?? 0,
    contentHasMore: !!co.data?.next_cursor,
  }
}
