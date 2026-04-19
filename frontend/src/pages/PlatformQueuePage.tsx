import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { format } from 'date-fns'
import type { Platform, DraftItemResponse } from '@/api/types'
import { ApprovalCard } from '@/components/approval/ApprovalCard'
import { ContentSummaryCard } from '@/components/approval/ContentSummaryCard'
import { EmptyState } from '@/components/shared/EmptyState'
import { useQueue } from '@/hooks/useQueue'
import { useAppStore } from '@/stores/index'
import { Button } from '@/components/ui/button'
import { getAgentRuns } from '@/api/settings'
import type { AgentRunResponse } from '@/api/types'

const PLATFORM_LABELS: Record<Platform, string> = {
  twitter: 'Twitter',
  content: 'Content',
}

// Agent name used in the agent_runs table for each platform
const AGENT_NAMES: Partial<Record<Platform, string>> = {
  twitter: 'twitter_agent',
  content: 'content_agent',
}

interface PlatformQueuePageProps {
  platform: Platform
}

/** Group items under the agent run that produced them.
 *  Each item is assigned to the most recent run whose started_at <= item.created_at.
 *  Items that precede all known runs fall into a catch-all "earlier" group.
 */
function groupByRun(
  items: DraftItemResponse[],
  runs: AgentRunResponse[],
): Array<{ run: AgentRunResponse | null; items: DraftItemResponse[] }> {
  // Runs sorted newest-first (already from API, but sort defensively)
  const sorted = [...runs].sort(
    (a, b) => new Date(b.started_at).getTime() - new Date(a.started_at).getTime()
  )

  // Map item → run
  const groups = new Map<string, { run: AgentRunResponse | null; items: DraftItemResponse[] }>()
  const NO_RUN_KEY = '__no_run__'

  for (const item of items) {
    const itemTime = new Date(item.created_at).getTime()
    // Find the most recent run that started before (or at) this item's creation time
    const matchedRun = sorted.find(
      (r) => new Date(r.started_at).getTime() <= itemTime
    ) ?? null

    const key = matchedRun ? matchedRun.id.toString() : NO_RUN_KEY
    if (!groups.has(key)) {
      groups.set(key, { run: matchedRun, items: [] })
    }
    groups.get(key)!.items.push(item)
  }

  // Return groups in order: newest run first, no-run group last
  const result: Array<{ run: AgentRunResponse | null; items: DraftItemResponse[] }> = []
  for (const run of sorted) {
    const key = run.id.toString()
    if (groups.has(key)) {
      result.push(groups.get(key)!)
    }
  }
  if (groups.has(NO_RUN_KEY)) {
    result.push(groups.get(NO_RUN_KEY)!)
  }
  return result
}

function RunHeader({ run }: { run: AgentRunResponse | null }) {
  return (
    <div className="flex items-center gap-3 py-1">
      <span className="text-xs font-medium text-muted-foreground whitespace-nowrap">
        Pulled from agent run {run ? `at ${format(new Date(run.started_at), 'h:mm a')} · ${format(new Date(run.started_at), 'MMM d')}` : '(earlier)'}
      </span>
      <div className="flex-1 border-t border-border" />
      {run?.items_queued != null && (
        <span className="text-xs text-muted-foreground shrink-0">
          {run.items_queued} queued
        </span>
      )}
    </div>
  )
}

export function PlatformQueuePage({ platform }: PlatformQueuePageProps) {
  const queue = useQueue(platform)
  const items = queue.data?.pages.flatMap((p) => p.items) ?? []
  const isLoading = queue.isLoading

  // Fetch agent runs only for platforms that have them mapped
  const agentName = AGENT_NAMES[platform]
  const runsQuery = useQuery({
    queryKey: ['agent-runs', agentName],
    queryFn: () => getAgentRuns(agentName, 7),
    enabled: !!agentName,
    staleTime: 60_000,
  })
  const runs = runsQuery.data ?? []

  // Clear pending timeouts on unmount
  useEffect(() => {
    return () => {
      useAppStore.getState().clearAllPending()
    }
  }, [])

  const showRunGroups = (platform === 'twitter' || platform === 'content') && runs.length > 0

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
        ) : showRunGroups ? (
          // Twitter + Content: grouped by agent run
          <div className="max-w-2xl space-y-6">
            {groupByRun(items, runs).map((group, gi) => (
              <div key={gi} className="space-y-3">
                <RunHeader run={group.run} />
                {group.items.map((item) =>
                  platform === 'content' ? (
                    <ContentSummaryCard key={item.id} item={item} />
                  ) : (
                    <ApprovalCard key={item.id} item={item} platform={platform} />
                  )
                )}
              </div>
            ))}

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
        ) : (
          // Other platforms: flat list
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
