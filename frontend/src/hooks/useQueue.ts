import { useInfiniteQuery } from '@tanstack/react-query'
import { getQueue } from '@/api/queue'
import type { Platform } from '@/api/types'

export function useQueue(platform: Platform) {
  return useInfiniteQuery({
    queryKey: ['queue', platform],
    queryFn: ({ pageParam }) => getQueue({ platform, status: 'pending', cursor: pageParam }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
  })
}
