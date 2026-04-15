import { useState, useRef } from 'react'
import { ExternalLink } from 'lucide-react'
import { toast } from 'sonner'
import { useShallow } from 'zustand/react/shallow'

import { useAppStore } from '@/stores/index'
import { useApprove } from '@/hooks/useApprove'
import { useReject } from '@/hooks/useReject'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { PlatformBadge } from '@/components/shared/PlatformBadge'
import { ScoreBadge } from '@/components/shared/ScoreBadge'
import { DraftTabBar } from './DraftTabBar'
import { InlineEditor } from './InlineEditor'
import { RejectPanel } from './RejectPanel'
import type { DraftItemResponse, Platform, RejectionCategory } from '@/api/types'

interface ApprovalCardProps {
  item: DraftItemResponse
  platform: Platform
}

function formatFollowers(count?: number): string {
  if (!count) return ''
  if (count >= 1_000_000) return `${(count / 1_000_000).toFixed(1)}M`
  if (count >= 1_000) return `${(count / 1_000).toFixed(1)}K`
  return String(count)
}

export function ApprovalCard({ item, platform }: ApprovalCardProps) {
  const [showRationale, setShowRationale] = useState(false)
  const [sourceExpanded, setSourceExpanded] = useState(false)
  // Ref used to trigger the InlineEditor save from Edit+Approve button
  const editedTextRef = useRef<string | null>(null)

  const {
    editingCardId,
    rejectionPanelCardId,
    activeDraftTab,
    fadingCardIds,
    setEditingCard,
    setRejectionPanel,
    setActiveDraftTab,
    startFadeOut,
    cancelFadeOut,
  } = useAppStore(
    useShallow((s) => ({
      editingCardId: s.editingCardId,
      rejectionPanelCardId: s.rejectionPanelCardId,
      activeDraftTab: s.activeDraftTab,
      fadingCardIds: s.fadingCardIds,
      setEditingCard: s.setEditingCard,
      setRejectionPanel: s.setRejectionPanel,
      setActiveDraftTab: s.setActiveDraftTab,
      startFadeOut: s.startFadeOut,
      cancelFadeOut: s.cancelFadeOut,
    }))
  )

  const approveMutation = useApprove(platform)
  const rejectMutation = useReject(platform)

  const isEditing = editingCardId === item.id
  const isRejectionOpen = rejectionPanelCardId === item.id
  const isFading = fadingCardIds.has(item.id)
  const activeTabIndex = activeDraftTab[item.id] ?? 0
  const activeAlternative = item.alternatives[activeTabIndex] ?? item.alternatives[0]

  function handleApprove(editedText?: string) {
    const textToCopy = editedText ?? activeAlternative?.text ?? ''
    // Copy to clipboard immediately on click (not deferred, per D-06)
    navigator.clipboard.writeText(textToCopy).catch(() => {/* non-fatal */})

    const timeoutId = setTimeout(() => {
      approveMutation.mutate({ id: item.id, editedText })
    }, 5000)

    startFadeOut(item.id, timeoutId)
    setEditingCard(null)
    editedTextRef.current = null

    const label = editedText ? 'Edited & approved' : 'Approved'
    toast.success(`${label} — copied to clipboard`, {
      action: {
        label: 'Undo',
        onClick: () => {
          cancelFadeOut(item.id)
        },
      },
      duration: 5000,
    })
  }

  function handleEditApprove() {
    // editedTextRef holds the current edit value updated via InlineEditor's onChange
    const editedText = editedTextRef.current ?? activeAlternative?.text
    handleApprove(editedText ?? undefined)
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
        onClick: () => {
          cancelFadeOut(item.id)
        },
      },
      duration: 5000,
    })
  }

  const sourceLines = item.source_text?.split('\n') ?? []
  const showCollapsedSource = !sourceExpanded && sourceLines.length > 2

  return (
    <div
      className={[
        'w-full rounded-xl border bg-card shadow-sm transition-opacity duration-300',
        isFading ? 'opacity-0' : 'opacity-100',
      ].join(' ')}
    >
      <div className="p-4 space-y-3">
        {/* Header */}
        <div className="flex items-center justify-between gap-2 flex-wrap">
          <div className="flex items-center gap-2 flex-wrap">
            <PlatformBadge platform={platform} />
            {item.source_account && (
              <span className="text-sm font-medium">{item.source_account}</span>
            )}
            {item.follower_count && (
              <span className="text-xs text-muted-foreground">
                {formatFollowers(item.follower_count)} followers
              </span>
            )}
            {item.related_id && (
              <Badge variant="outline" className="text-xs">
                Related draft
              </Badge>
            )}
          </div>
          {item.score != null && <ScoreBadge score={item.score} />}
        </div>

        {/* Source section */}
        {(item.source_text || item.source_url) && (
          <div className="space-y-1">
            {item.source_text && (
              <div>
                <p
                  className={[
                    'text-sm text-muted-foreground leading-relaxed',
                    showCollapsedSource ? 'line-clamp-2' : '',
                  ].join(' ')}
                >
                  {item.source_text}
                </p>
                {sourceLines.length > 2 && (
                  <button
                    type="button"
                    className="text-xs text-muted-foreground hover:text-foreground mt-0.5"
                    onClick={() => setSourceExpanded(!sourceExpanded)}
                  >
                    {sourceExpanded ? 'Show less' : 'Show more'}
                  </button>
                )}
              </div>
            )}
            {item.source_url && (
              <a
                href={item.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
              >
                <ExternalLink className="size-3" />
                View source
              </a>
            )}
          </div>
        )}

        {/* Draft section */}
        <div className="space-y-2">
          <DraftTabBar
            alternatives={item.alternatives}
            activeIndex={activeTabIndex}
            onTabChange={(idx) => {
              setActiveDraftTab(item.id, idx)
              editedTextRef.current = null
            }}
          />
          {activeAlternative && (
            <InlineEditor
              text={activeAlternative.text}
              isEditing={isEditing}
              onStartEdit={() => setEditingCard(item.id)}
              onSave={(text) => handleApprove(text)}
              onCancel={() => {
                setEditingCard(null)
                editedTextRef.current = null
              }}
              onEditChange={(text) => { editedTextRef.current = text }}
            />
          )}
        </div>

        {/* Rationale section */}
        {item.rationale && (
          <div>
            <button
              type="button"
              className="text-xs font-medium text-muted-foreground hover:text-foreground"
              onClick={() => setShowRationale(!showRationale)}
            >
              Why this post? {showRationale ? '▲' : '▼'}
            </button>
            {showRationale && (
              <p className="mt-1 text-sm text-muted-foreground leading-relaxed">
                {item.rationale}
              </p>
            )}
          </div>
        )}

        {/* Action buttons */}
        <div className="flex items-center gap-2">
          {isEditing && (
            <Button
              size="sm"
              onClick={handleEditApprove}
              className="bg-primary text-primary-foreground"
            >
              Edit + Approve
            </Button>
          )}
          {!isEditing && (
            <Button
              size="sm"
              onClick={() => handleApprove(undefined)}
              className="bg-primary text-primary-foreground"
            >
              Approve
            </Button>
          )}
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              setRejectionPanel(isRejectionOpen ? null : item.id)
            }}
          >
            Reject
          </Button>
        </div>

        {/* Reject panel */}
        <RejectPanel
          isOpen={isRejectionOpen}
          onConfirm={handleRejectConfirm}
          onCancel={() => setRejectionPanel(null)}
        />
      </div>
    </div>
  )
}
