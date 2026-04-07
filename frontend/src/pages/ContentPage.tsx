import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { TrendingDown } from 'lucide-react'
import { toast } from 'sonner'
import { getTodayContent } from '@/api/content'
import { getQueue, approveItem, rejectItem } from '@/api/queue'
import type { ContentBundleResponse, RejectionCategory } from '@/api/types'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { ScoreBadge } from '@/components/shared/ScoreBadge'
import { InfographicPreview } from '@/components/content/InfographicPreview'

// Helper: determine clipboard text per content_type
function getClipboardText(bundle: ContentBundleResponse): string {
  const draft = bundle.draft_content as Record<string, unknown> | null
  if (!draft) return ''
  switch (bundle.content_type) {
    case 'infographic':
      return (draft.caption_text as string) ?? ''
    case 'long_form':
      return (draft.post as string) ?? ''
    case 'thread': {
      const tweets = (draft.tweets as string[]) ?? []
      return tweets.join('\n\n')
    }
    default:
      return JSON.stringify(draft)
  }
}

interface DeepResearch {
  corroborating_sources?: Array<{ title: string; url: string; domain: string }>
  rationale?: string
}

interface InfographicDraft {
  format: 'infographic'
  headline: string
  key_stats: Array<{ stat: string; source: string; source_url: string }>
  visual_structure: string
  caption_text: string
}

function NoStoryEmptyState({ score }: { score?: number }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="w-12 h-12 rounded-full bg-muted flex items-center justify-center mb-4">
        <TrendingDown className="w-6 h-6 text-muted-foreground" />
      </div>
      <h3 className="text-base font-medium mb-2">No strong story found today</h3>
      <p className="text-sm text-muted-foreground max-w-xs leading-relaxed">
        No story cleared the 7.0/10 threshold. Score: {score?.toFixed(1) ?? '—'}/10.
      </p>
    </div>
  )
}

function ContentEmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <h3 className="text-base font-medium mb-2">No content today</h3>
      <p className="text-sm text-muted-foreground max-w-xs leading-relaxed">
        The Content Agent has not run yet or found no qualifying story.
      </p>
    </div>
  )
}

function DraftContent({ bundle }: { bundle: ContentBundleResponse }) {
  const draft = bundle.draft_content as Record<string, unknown> | null

  if (!draft) return null

  if (bundle.content_type === 'thread') {
    const tweets = (draft.tweets as string[]) ?? []
    return (
      <div className="space-y-2">
        {tweets.map((tweet, i) => (
          <div key={i} className="border rounded-md p-3 text-sm">
            <span className="text-xs text-muted-foreground font-mono mr-2">{i + 1}</span>
            {tweet}
          </div>
        ))}
      </div>
    )
  }

  if (bundle.content_type === 'long_form') {
    const post = (draft.post as string) ?? ''
    return <Textarea readOnly value={post} rows={8} className="resize-none" />
  }

  if (bundle.content_type === 'infographic') {
    return <InfographicPreview draft={draft as unknown as InfographicDraft} />
  }

  return (
    <pre className="text-xs font-mono whitespace-pre-wrap border rounded-md p-3">
      {JSON.stringify(draft, null, 2)}
    </pre>
  )
}

export function ContentPage() {
  const queryClient = useQueryClient()
  const [showRejectPanel, setShowRejectPanel] = useState(false)
  const [rejectReason, setRejectReason] = useState('')

  const bundleQuery = useQuery({
    queryKey: ['content', 'today'],
    queryFn: async () => {
      try {
        return await getTodayContent()
      } catch (e: unknown) {
        if (e instanceof Error && e.message.includes('404')) return null
        throw e
      }
    },
  })

  const draftQuery = useQuery({
    queryKey: ['queue', 'content', 'pending'],
    queryFn: () => getQueue({ platform: 'content', status: 'pending' }),
    enabled: !!bundleQuery.data && !bundleQuery.data.no_story_flag,
  })

  const bundle = bundleQuery.data
  const draftItem = draftQuery.data?.items?.find(i => i.status === 'pending') ?? null

  const approveMutation = useMutation({
    mutationFn: ({ id }: { id: string }) => approveItem(id),
    onSuccess: () => {
      if (bundle) navigator.clipboard.writeText(getClipboardText(bundle))
      toast.success('Approved — copied to clipboard')
      queryClient.invalidateQueries({ queryKey: ['queue', 'content'] })
      queryClient.invalidateQueries({ queryKey: ['content', 'today'] })
    },
  })

  const rejectMutation = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      rejectItem(id, 'low-quality' as RejectionCategory, reason),
    onSuccess: () => {
      toast.success('Rejected')
      setShowRejectPanel(false)
      setRejectReason('')
      queryClient.invalidateQueries({ queryKey: ['queue', 'content'] })
      queryClient.invalidateQueries({ queryKey: ['content', 'today'] })
    },
  })

  const today = new Date().toLocaleDateString('en-US', {
    weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
  })

  // Branch 1: Loading
  if (bundleQuery.isLoading) {
    return (
      <div className="p-8 max-w-3xl">
        <div className="h-8 w-48 bg-muted animate-pulse rounded mb-2" />
        <div className="h-4 w-32 bg-muted animate-pulse rounded mb-8" />
        <div className="h-64 bg-muted animate-pulse rounded" />
      </div>
    )
  }

  // Branch 2: Error (non-404)
  if (bundleQuery.isError) {
    return (
      <div className="p-8 max-w-3xl">
        <h1 className="text-xl font-semibold mb-2">Content Review</h1>
        <p className="text-sm text-muted-foreground mb-4">
          Failed to load content. Check your connection and try again.
        </p>
        <Button variant="outline" onClick={() => bundleQuery.refetch()}>
          Try Again
        </Button>
      </div>
    )
  }

  // Branch 3: No bundle (404 or not yet fetched)
  if (bundle == null) {
    return (
      <div className="p-8 max-w-3xl">
        <h1 className="text-xl font-semibold mb-1">Content Review</h1>
        <p className="text-sm text-muted-foreground mb-8">{today}</p>
        <ContentEmptyState />
      </div>
    )
  }

  // Branch 4: no_story_flag
  if (bundle?.no_story_flag) {
    return (
      <div className="p-8 max-w-3xl">
        <h1 className="text-xl font-semibold mb-1">Content Review</h1>
        <p className="text-sm text-muted-foreground mb-8">{today}</p>
        <NoStoryEmptyState score={bundle.score ?? bundle.quality_score} />
      </div>
    )
  }

  const deepResearch = bundle.deep_research as DeepResearch | null
  const sources = deepResearch?.corroborating_sources ?? []
  const rationale = deepResearch?.rationale ?? ''

  // Branch 5 & 6: Bundle found — with or without pending draft item
  return (
    <div className="p-8 max-w-5xl">
      <h1 className="text-xl font-semibold mb-1">Content Review</h1>
      <p className="text-sm text-muted-foreground mb-6">{today}</p>

      <div className="grid grid-cols-[1fr_300px] gap-6">
        {/* Left column: content */}
        <div className="space-y-6">
          <div>
            <p className="text-base font-semibold mb-2">{bundle.story_headline}</p>
            {bundle.content_type && (
              <Badge variant="outline" className="mb-3">{bundle.content_type}</Badge>
            )}
            <DraftContent bundle={bundle} />
          </div>

          {sources.length > 0 && (
            <div>
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
                Sources
              </p>
              <ul className="space-y-1">
                {sources.map((s, i) => (
                  <li key={i}>
                    <a
                      href={s.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm hover:underline text-blue-600"
                    >
                      {s.domain || s.title}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {rationale && (
            <div>
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
                Rationale
              </p>
              <p className="text-sm text-muted-foreground">{rationale}</p>
            </div>
          )}
        </div>

        {/* Right column: action panel */}
        <div className="space-y-4">
          {bundle.quality_score !== undefined && (
            <div>
              <p className="text-xs text-muted-foreground mb-1">Quality Score</p>
              <ScoreBadge score={bundle.quality_score} />
            </div>
          )}

          {draftItem ? (
            <div className="space-y-2">
              <Button
                className="w-full"
                disabled={approveMutation.isPending}
                onClick={() => approveMutation.mutate({ id: draftItem.id })}
              >
                Approve — Copy to Clipboard
              </Button>
              <Button
                variant="outline"
                className="w-full"
                onClick={() => setShowRejectPanel(v => !v)}
              >
                Reject Draft
              </Button>
              {showRejectPanel && (
                <div className="space-y-2 pt-2">
                  <Textarea
                    placeholder="Reason for rejection..."
                    value={rejectReason}
                    onChange={e => setRejectReason(e.target.value)}
                    rows={3}
                  />
                  <Button
                    variant="destructive"
                    className="w-full"
                    disabled={!rejectReason.trim() || rejectMutation.isPending}
                    onClick={() => rejectMutation.mutate({ id: draftItem.id, reason: rejectReason })}
                  >
                    Confirm Rejection
                  </Button>
                </div>
              )}
            </div>
          ) : (
            <div>
              <p className="text-xs text-muted-foreground mb-2">Status</p>
              <Badge variant="secondary">Reviewed</Badge>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
