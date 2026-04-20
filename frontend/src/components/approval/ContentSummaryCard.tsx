import { useState } from 'react'
import { ExternalLink, Download } from 'lucide-react'
import { toast } from 'sonner'

import { useApprove } from '@/hooks/useApprove'
import { useReject } from '@/hooks/useReject'
import { useAppStore } from '@/stores/index'
import { useShallow } from 'zustand/react/shallow'
import { Button } from '@/components/ui/button'
import { ScoreBadge } from '@/components/shared/ScoreBadge'
import { RejectPanel } from './RejectPanel'
import { ContentDetailModal } from './ContentDetailModal'
import { Dialog, DialogContent, DialogTrigger } from '@/components/ui/dialog'
import { useContentBundle } from '@/hooks/useContentBundle'
import type { DraftItemResponse, RejectionCategory, RenderedImage } from '@/api/types'

interface ContentSummaryCardProps {
  item: DraftItemResponse
}

const ROLE_LABELS: Record<string, string> = {
  twitter_visual: 'Twitter / X',
}

const FORMAT_LABELS: Record<string, string> = {
  thread: 'Thread',
  long_post: 'Long Post',
  article: 'Article',
  infographic: 'Infographic Brief',
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

  // Extract bundle ID for rendered images
  const bundleId =
    (item.engagement_snapshot as Record<string, unknown> | undefined)
      ?.content_bundle_id as string | undefined

  const { data: bundle } = useContentBundle(bundleId ?? null)
  const renderedImages = bundle?.rendered_images ?? []

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

  async function handleDownload(img: RenderedImage, e: React.MouseEvent) {
    e.stopPropagation()
    try {
      const response = await fetch(img.url)
      const blob = await response.blob()
      const objectUrl = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = objectUrl
      anchor.download = `${bundleId ?? 'image'}-${img.role}.png`
      anchor.click()
      URL.revokeObjectURL(objectUrl)
    } catch {
      // CORS fallback: direct anchor download
      const anchor = document.createElement('a')
      anchor.href = img.url
      anchor.download = `${bundleId ?? 'image'}-${img.role}.png`
      anchor.target = '_blank'
      anchor.click()
    }
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

          {/* Inline rendered images gallery */}
          {renderedImages.length > 0 && (
            <InlineImagesGallery
              images={renderedImages}
              bundleId={bundleId ?? ''}
              onDownload={handleDownload}
            />
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

interface InlineImagesGalleryProps {
  images: RenderedImage[]
  bundleId: string
  onDownload: (img: RenderedImage, e: React.MouseEvent) => void
}

function InlineImagesGallery({ images, bundleId: _bundleId, onDownload }: InlineImagesGalleryProps) {
  if (images.length === 0) return null
  return (
    <div className="flex flex-wrap gap-3 pt-1" onClick={(e) => e.stopPropagation()}>
      {images.map((img) => (
        <div key={img.role} className="flex flex-col items-center gap-1">
          <p className="text-xs text-muted-foreground">
            {ROLE_LABELS[img.role] ?? img.role}
          </p>
          <Dialog>
            <DialogTrigger asChild>
              <button
                type="button"
                className="block rounded border overflow-hidden hover:opacity-80 transition-opacity focus-visible:outline-none focus-visible:ring-2"
                aria-label={`Preview ${ROLE_LABELS[img.role] ?? img.role} image`}
              >
                <img
                  src={img.url}
                  alt={ROLE_LABELS[img.role] ?? img.role}
                  className="max-w-[180px] h-auto object-contain"
                  loading="lazy"
                />
              </button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-2xl p-2">
              <img
                src={img.url}
                alt={ROLE_LABELS[img.role] ?? img.role}
                className="w-full h-auto rounded"
              />
            </DialogContent>
          </Dialog>
          <Button
            size="sm"
            variant="ghost"
            className="h-6 px-2 text-xs"
            onClick={(e) => onDownload(img, e)}
          >
            <Download className="size-3 mr-1" />
            Download
          </Button>
        </div>
      ))}
    </div>
  )
}
