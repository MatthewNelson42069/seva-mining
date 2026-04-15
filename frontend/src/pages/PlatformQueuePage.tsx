import { useEffect } from 'react'
import type { Platform } from '@/api/types'
import { ApprovalCard } from '@/components/approval/ApprovalCard'
import { ContentSummaryCard } from '@/components/approval/ContentSummaryCard'
import { EmptyState } from '@/components/shared/EmptyState'
import { useQueue } from '@/hooks/useQueue'
import { useAppStore } from '@/stores/index'
import { Button } from '@/components/ui/button'

const PLATFORM_LABELS: Record<Platform, string> = {
  twitter: 'Twitter',
  instagram: 'Instagram',
  content: 'Content',
}

interface PlatformQueuePageProps {
  platform: Platform
}

export function PlatformQueuePage({ platform }: PlatformQueuePageProps) {
  const queue = useQueue(platform)
  const items = queue.data?.pages.flatMap((p) => p.items) ?? []
  const isLoading = queue.isLoading

  // Clear pending timeouts on unmount to prevent leaks
  useEffect(() => {
    return () => {
      useAppStore.getState().clearAllPending()
    }
  }, [])

  return (
    <div className="flex flex-col h-full">
      {/* Page header */}
      <div className="px-6 py-4 border-b border-border bg-card">
        <h1 className="text-base font-semibold">{PLATFORM_LABELS[platform]} Queue</h1>
        {!isLoading && (
          <p className="text-xs text-muted-foreground mt-0.5">
            {items.length}{queue.hasNextPage ? '+' : ''} pending
          </p>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 p-6 overflow-auto">
        {isLoading ? (
          <div className="flex items-center justify-center py-16">
            <p className="text-sm text-muted-foreground">Loading...</p>
          </div>
        ) : items.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="max-w-2xl space-y-4">
            {items.map((item) =>
              platform === 'content' ? (
                <ContentSummaryCard key={item.id} item={item} />
              ) : (
                <ApprovalCard key={item.id} item={item} platform={platform} />
              )
            )}

            {queue.hasNextPage && (
              <div className="flex justify-center pt-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => queue.fetchNextPage()}
                  disabled={queue.isFetchingNextPage}
                >
                  {queue.isFetchingNextPage ? 'Loading more…' : 'Load more'}
                </Button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
