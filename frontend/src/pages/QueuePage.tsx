import { useState } from 'react'
import type { Platform } from '@/api/types'
import { PlatformTabBar } from '@/components/layout/PlatformTabBar'
import { useQueue } from '@/hooks/useQueue'

export function QueuePage() {
  const [activePlatform, setActivePlatform] = useState<Platform>('twitter')

  const twitterQuery = useQueue('twitter')
  const instagramQuery = useQueue('instagram')
  const contentQuery = useQueue('content')

  const twitterCount = twitterQuery.data?.pages.flatMap((p) => p.items).length ?? 0
  const instagramCount = instagramQuery.data?.pages.flatMap((p) => p.items).length ?? 0
  const contentCount = contentQuery.data?.pages.flatMap((p) => p.items).length ?? 0

  const counts: Record<Platform, number> = {
    twitter: twitterCount,
    instagram: instagramCount,
    content: contentCount,
  }

  const activeQuery = { twitter: twitterQuery, instagram: instagramQuery, content: contentQuery }[activePlatform]
  const activeItems = activeQuery.data?.pages.flatMap((p) => p.items) ?? []
  const isLoading = activeQuery.isLoading

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
            <p className="text-sm text-gray-400">Loading...</p>
          </div>
        ) : activeItems.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <div className="w-10 h-10 rounded-full bg-green-50 flex items-center justify-center mb-4">
              <svg className="w-5 h-5 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <h3 className="text-sm font-medium text-gray-900 mb-1">Queue is clear</h3>
            <p className="text-sm text-gray-500 max-w-xs">
              The system is monitoring and working. New items will appear here when agents find content worth reviewing.
            </p>
          </div>
        ) : (
          <div>
            {/* Approval cards will be rendered here in Plan 04 */}
            <div className="space-y-4">
              {activeItems.map((item) => (
                <div key={item.id} className="border border-gray-100 rounded-xl p-4 text-sm text-gray-700">
                  {item.source_text ?? item.id}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
