import { useState, useEffect } from 'react'
import type { Platform } from '@/api/types'
import { PlatformTabBar } from '@/components/layout/PlatformTabBar'
import { ApprovalCard } from '@/components/approval/ApprovalCard'
import { ContentSummaryCard } from '@/components/approval/ContentSummaryCard'
import { EmptyState } from '@/components/shared/EmptyState'
import { useQueue } from '@/hooks/useQueue'
import { useAppStore } from '@/stores/index'
import { Button } from '@/components/ui/button'

export function QueuePage() {
  const [activePlatform, setActivePlatform] = useState<Platform>('twitter')

  const twitterQuery = useQueue('twitter')
  const contentQuery = useQueue('content')

  const twitterCount = twitterQuery.data?.pages.flatMap((p) => p.items).length ?? 0
  const contentCount = contentQuery.data?.pages.flatMap((p) => p.items).length ?? 0

  const counts: Record<Platform, number> = {
    twitter: twitterCount,
    content: contentCount,
  }

  const activeQuery = { twitter: twitterQuery, content: contentQuery }[activePlatform]
  const activeItems = activeQuery.data?.pages.flatMap((p) => p.items) ?? []
  const isLoading = activeQuery.isLoading
  const hasNextPage = activeQuery.hasNextPage
  const isFetchingNextPage = activeQuery.isFetchingNextPage
  const fetchNextPage = activeQuery.fetchNextPage

  // Clear pending timeouts on unmount to prevent leaks
  useEffect(() => {
    return () => {
      useAppStore.getState().clearAllPending()
    }
  }, [])

  return (
    <div className="flex flex-col h-full">
      <PlatformTabBar
        activeTab={activePlatform}
        onTabChange={setActivePlatform}
        counts={counts}
      />

      <div className="flex-1 p-6">
        {isLoading ? (
          <div className="flex items-center justify-center py-16">
            <p className="text-sm text-muted-foreground">Loading...</p>
          </div>
        ) : activeItems.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="space-y-4">
            {activeItems.map((item) =>
              activePlatform === 'content' ? (
                <ContentSummaryCard key={item.id} item={item} />
              ) : (
                <ApprovalCard
                  key={item.id}
                  item={item}
                  platform={activePlatform}
                />
              )
            )}

            {hasNextPage && (
              <div className="flex justify-center pt-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => fetchNextPage()}
                  disabled={isFetchingNextPage}
                >
                  {isFetchingNextPage ? 'Loading more...' : 'Load more'}
                </Button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
