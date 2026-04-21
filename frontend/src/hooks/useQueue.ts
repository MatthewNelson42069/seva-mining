import { useInfiniteQuery } from '@tanstack/react-query'
import { getQueue } from '@/api/queue'
import type { Platform } from '@/api/types'

/**
 * Queue hook.
 *
 * `contentType` is optional (quick-260421-eoe): when provided, the backend
 * filters draft_items via the content_bundles JSONB link so each per-agent
 * queue page shows only its own drafts. queryKey includes contentType so
 * TanStack Query dedupes per-tab.
 */
export function useQueue(platform: Platform, contentType?: string) {
  return useInfiniteQuery({
    queryKey: ['queue', platform, contentType ?? null],
    queryFn: ({ pageParam }) =>
      getQueue({ platform, status: 'pending', contentType, cursor: pageParam }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
  })
}
