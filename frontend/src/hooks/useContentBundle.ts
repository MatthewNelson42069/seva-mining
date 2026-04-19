import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getContentBundle, rerenderContentBundle } from '@/api/content'
import type { ContentBundleDetailResponse, RerenderResponse } from '@/api/types'

const POLL_INTERVAL_MS = 5000
const MAX_POLL_WINDOW_MS = 10 * 60 * 1000 // 10 minutes per D-14

export function useContentBundle(bundleId: string | null | undefined) {
  return useQuery<ContentBundleDetailResponse>({
    queryKey: ['content-bundle', bundleId],
    queryFn: () => getContentBundle(bundleId as string),
    enabled: !!bundleId,
    refetchInterval: (query) => {
      const data = query.state.data
      if (!data) return false
      // Stop once at least one image has landed
      if (data.rendered_images && data.rendered_images.length > 0) return false
      // Stop after the 10-minute ceiling (D-14)
      const age = Date.now() - new Date(data.created_at).getTime()
      if (age > MAX_POLL_WINDOW_MS) return false
      return POLL_INTERVAL_MS
    },
  })
}

export function useRerenderContentBundle(bundleId: string) {
  const queryClient = useQueryClient()
  return useMutation<RerenderResponse, Error, void>({
    mutationFn: () => rerenderContentBundle(bundleId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['content-bundle', bundleId] })
    },
  })
}
