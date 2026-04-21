import { useEffect } from 'react'
import { Navigate, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { format } from 'date-fns'
import type { DraftItemResponse } from '@/api/types'
import { ContentSummaryCard } from '@/components/approval/ContentSummaryCard'
import { EmptyState } from '@/components/shared/EmptyState'
import { useQueue } from '@/hooks/useQueue'
import { useAppStore } from '@/stores/index'
import { Button } from '@/components/ui/button'
import { getAgentRuns } from '@/api/settings'
import type { AgentRunResponse } from '@/api/types'
import { findTabBySlug, CONTENT_AGENT_TABS } from '@/config/agentTabs'

/** Group items under the agent run that produced them.
 *  Each item is assigned to the most recent run whose started_at <= item.created_at.
 *  Items that precede all known runs fall into a catch-all "earlier" group.
 */
function groupByRun(
  items: DraftItemResponse[],
  runs: AgentRunResponse[],
): Array<{ run: AgentRunResponse | null; items: DraftItemResponse[] }> {
  const sorted = [...runs].sort(
    (a, b) => new Date(b.started_at).getTime() - new Date(a.started_at).getTime()
  )

  const groups = new Map<string, { run: AgentRunResponse | null; items: DraftItemResponse[] }>()
  const NO_RUN_KEY = '__no_run__'

  for (const item of items) {
    const itemTime = new Date(item.created_at).getTime()
    const matchedRun = sorted.find(
      (r) => new Date(r.started_at).getTime() <= itemTime
    ) ?? null

    const key = matchedRun ? matchedRun.id.toString() : NO_RUN_KEY
    if (!groups.has(key)) {
      groups.set(key, { run: matchedRun, items: [] })
    }
    groups.get(key)!.items.push(item)
  }

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

/**
 * Per-sub-agent queue page (quick-260421-eoe).
 *
 * Single dynamic route `/agents/:slug` renders one of the 7 sub-agents'
 * queues based on `CONTENT_AGENT_TABS`. Unknown slug redirects to
 * `/agents/breaking-news` (priority-1 default).
 */
export function PerAgentQueuePage() {
  const { slug } = useParams<{ slug: string }>()
  const tab = findTabBySlug(slug)

  // Unknown slug → redirect to priority-1 agent (breaking news).
  // Hooks below MUST still be declared unconditionally; to do that cleanly
  // we return early BEFORE any hook is called only in the unreachable-tab
  // case. Return a separate component render path instead.
  if (!tab) {
    return <Navigate to={`/agents/${CONTENT_AGENT_TABS[0].slug}`} replace />
  }

  return <PerAgentQueueBody tab={tab} />
}

function PerAgentQueueBody({ tab }: { tab: ReturnType<typeof findTabBySlug> & object }) {
  const queue = useQueue('content', tab.contentType)
  const items = queue.data?.pages.flatMap((p) => p.items) ?? []
  const isLoading = queue.isLoading

  const runsQuery = useQuery({
    queryKey: ['agent-runs', tab.agentName],
    queryFn: () => getAgentRuns(tab.agentName, 7),
    enabled: !!tab.agentName,
    staleTime: 60_000,
  })
  const runs = runsQuery.data ?? []

  useEffect(() => {
    return () => {
      useAppStore.getState().clearAllPending()
    }
  }, [])

  const showRunGroups = runs.length > 0

  return (
    <div className="flex flex-col h-full">
      <div className="px-6 py-4 border-b border-border bg-card">
        <h1 className="text-base font-semibold">{tab.label} Queue</h1>
        {!isLoading && (
          <p className="text-xs text-muted-foreground mt-0.5">
            {items.length}{queue.hasNextPage ? '+' : ''} pending
          </p>
        )}
      </div>

      <div className="flex-1 p-6 overflow-auto">
        {isLoading ? (
          <div className="flex items-center justify-center py-16">
            <p className="text-sm text-muted-foreground">Loading...</p>
          </div>
        ) : items.length === 0 ? (
          <EmptyState />
        ) : showRunGroups ? (
          <div className="max-w-2xl space-y-6">
            {groupByRun(items, runs).map((group, gi) => (
              <div key={gi} className="space-y-3">
                <RunHeader run={group.run} />
                {group.items.map((item) => (
                  <ContentSummaryCard key={item.id} item={item} />
                ))}
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
          <div className="max-w-2xl space-y-4">
            {items.map((item) => (
              <ContentSummaryCard key={item.id} item={item} />
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
        )}
      </div>
    </div>
  )
}
