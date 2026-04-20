import { useState } from 'react'
import { ExternalLink } from 'lucide-react'
import { toast } from 'sonner'

import { useApprove } from '@/hooks/useApprove'
import { useReject } from '@/hooks/useReject'
import { useAppStore } from '@/stores/index'
import { useShallow } from 'zustand/react/shallow'
import { Button } from '@/components/ui/button'
import { ScoreBadge } from '@/components/shared/ScoreBadge'
import { RejectPanel } from './RejectPanel'
import { ContentDetailModal } from './ContentDetailModal'
import type { DraftItemResponse, RejectionCategory } from '@/api/types'

interface ContentSummaryCardProps {
  item: DraftItemResponse
}

const FORMAT_LABELS: Record<string, string> = {
  thread: 'Thread',
  long_post: 'Long Post',
  article: 'Article',
  infographic: 'Infographic',
  reply: 'Reply',
  retweet: 'Retweet',
  comment: 'Comment',
}

export function ContentSummaryCard({ item }: ContentSummaryCardProps) {
  const [isModalOpen, setIsModalOpen] = useState(false)

  const {
    rejectionPanelCardId,
    fadingCardIds,
    setRejectionPanel,
    startFadeOut,
    cancelFadeOut,
  } = useAppStore(
    useShallow((s) => ({
      rejectionPanelCardId: s.rejectionPanelCardId,
      fadingCardIds: s.fadingCardIds,
      setRejectionPanel: s.setRejectionPanel,
      startFadeOut: s.startFadeOut,
      cancelFadeOut: s.cancelFadeOut,
    }))
  )

  const approveMutation = useApprove('content')
  const rejectMutation = useReject('content')

  const isRejectionOpen = rejectionPanelCardId === item.id
  const isFading = fadingCardIds.has(item.id)

  // Extract headline from first line of source_text
  const headline = item.source_text?.split('\n')[0] ?? 'Content item'
  const formatType = item.alternatives[0]?.type

  function handleApprove(e: React.MouseEvent) {
    e.stopPropagation()
    const textToCopy = item.alternatives[0]?.text ?? ''
    navigator.clipboard.writeText(textToCopy).catch(() => {/* non-fatal */})

    const timeoutId = setTimeout(() => {
      approveMutation.mutate({ id: item.id })
    }, 5000)

    startFadeOut(item.id, timeoutId)

    toast.success('Approved — copied to clipboard', {
      action: {
        label: 'Undo',
        onClick: () => { cancelFadeOut(item.id) },
      },
      duration: 5000,
    })
  }

  function handleRejectClick(e: React.MouseEvent) {
    e.stopPropagation()
    setRejectionPanel(isRejectionOpen ? null : item.id)
  }

  function handleRejectConfirm(category: RejectionCategory, notes?: string) {
    const timeoutId = setTimeout(() => {
      rejectMutation.mutate({ id: item.id, category, notes })
    }, 5000)

    startFadeOut(item.id, timeoutId)
    setRejectionPanel(null)

    toast.success('Rejected', {
      action: {
        label: 'Undo',
        onClick: () => { cancelFadeOut(item.id) },
      },
      duration: 5000,
    })
  }

  return (
    <>
      <div
        className={[
          'w-full rounded-xl border bg-background shadow-sm transition-opacity duration-300 cursor-pointer hover:border-gray-300',
          isFading ? 'opacity-0' : 'opacity-100',
        ].join(' ')}
        onClick={() => setIsModalOpen(true)}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') setIsModalOpen(true) }}
      >
        <div className="p-4 space-y-3">
          {/* Header row */}
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1 min-w-0">
              {/* Format badge */}
              {formatType && (
                <div className="mb-1.5">
                  <span className="inline-flex items-center rounded px-2 py-0.5 text-xs font-medium bg-blue-50 text-blue-700 border border-blue-200">
                    {FORMAT_LABELS[formatType] ?? formatType}
                  </span>
                </div>
              )}
              {/* Headline */}
              <p className="text-sm font-medium text-foreground leading-snug line-clamp-2">{headline}</p>
            </div>
            {item.score != null && (
              <div className="shrink-0">
                <ScoreBadge score={item.score} />
              </div>
            )}
          </div>

          {/* Source info */}
          {(item.source_account || item.source_url) && (
            <div className="flex items-center gap-3 text-xs text-muted-foreground">
              {item.source_account && <span>{item.source_account}</span>}
              {item.source_url && (
                <a
                  href={item.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 hover:text-foreground"
                  onClick={(e) => e.stopPropagation()}
                >
                  <ExternalLink className="size-3" />
                  View source
                </a>
              )}
            </div>
          )}

          {/* Alternatives count hint */}
          {item.alternatives.length > 0 && (
            <p className="text-xs text-muted-foreground">
              {item.alternatives.length} draft{item.alternatives.length !== 1 ? 's' : ''} · Click to review
            </p>
          )}

          {/* Action buttons */}
          <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
            <Button
              size="sm"
              onClick={handleApprove}
              className="bg-primary text-primary-foreground"
            >
              Approve
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={handleRejectClick}
            >
              Reject
            </Button>
          </div>

          {/* Reject panel */}
          <div onClick={(e) => e.stopPropagation()}>
            <RejectPanel
              isOpen={isRejectionOpen}
              onConfirm={handleRejectConfirm}
              onCancel={() => setRejectionPanel(null)}
            />
          </div>
        </div>
      </div>

      {/* Detail modal */}
      <ContentDetailModal
        item={item}
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
      />
    </>
  )
}
