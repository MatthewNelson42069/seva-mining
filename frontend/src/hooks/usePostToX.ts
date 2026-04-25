import { useMutation, useQueryClient } from '@tanstack/react-query'
import { postItemToX } from '@/api/queue'
import type { PostToXResponse } from '@/api/types'
import { toast } from 'sonner'

/**
 * Phase B (quick-260424-l0d): approve→post-to-X mutation.
 *
 * Wraps `POST /items/{id}/post-to-x`. The backend atomically transitions the
 * draft's `approval_state` (pending → posted | posted_partial | failed) inside
 * a single FOR-UPDATE transaction, so this hook does not need to coordinate
 * optimistic state — we just toast on each terminal state and invalidate the
 * platform queue so cards re-render with the fresh post-state.
 *
 * Toast behavior per CONTEXT.md D6:
 *   - posted          → success "Posted to X" with action link to tweet
 *   - posted_partial  → warning "Thread posted partially" with first-tweet link
 *   - failed          → error "Failed to post" with the post_error string
 *   - already_posted  → info "Already posted" (no-op idempotent re-call)
 */
export function usePostToX(platform: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id }: { id: string }) => postItemToX(id),
    onSuccess: (data: PostToXResponse) => {
      const tweetId = data.posted_tweet_id
      const tweetUrl = tweetId && !tweetId.startsWith('sim-')
        ? `https://x.com/i/web/status/${tweetId}`
        : undefined

      if (data.already_posted) {
        toast.info('Already posted', {
          ...(tweetUrl && {
            action: { label: 'View on X', onClick: () => window.open(tweetUrl, '_blank', 'noopener,noreferrer') },
          }),
        })
      } else if (data.approval_state === 'posted') {
        toast.success('Posted to X', {
          ...(tweetUrl && {
            action: { label: 'View on X', onClick: () => window.open(tweetUrl, '_blank', 'noopener,noreferrer') },
          }),
        })
      } else if (data.approval_state === 'posted_partial') {
        toast.warning('Thread posted partially — review on X', {
          description: data.post_error ?? undefined,
          ...(tweetUrl && {
            action: { label: 'View on X', onClick: () => window.open(tweetUrl, '_blank', 'noopener,noreferrer') },
          }),
        })
      } else if (data.approval_state === 'failed') {
        toast.error('Failed to post to X', {
          description: data.post_error ?? 'Unknown error',
        })
      }
      queryClient.invalidateQueries({ queryKey: ['queue', platform] })
    },
    onError: (err) => {
      toast.error('Failed to post to X', {
        description: err instanceof Error ? err.message : String(err),
      })
    },
  })
}
