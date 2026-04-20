import { useQuery } from '@tanstack/react-query'
import { getContentBundle } from '@/api/content'
import type { ContentBundleDetailResponse } from '@/api/types'

export function useContentBundle(bundleId: string | null | undefined) {
  return useQuery<ContentBundleDetailResponse>({
    queryKey: ['content-bundle', bundleId],
    queryFn: () => getContentBundle(bundleId as string),
    enabled: !!bundleId,
  })
}
