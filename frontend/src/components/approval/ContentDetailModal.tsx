import { useState } from 'react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import type { DraftItemResponse, DraftAlternative } from '@/api/types'

interface ContentDetailModalProps {
  item: DraftItemResponse
  isOpen: boolean
  onClose: () => void
}

const FORMAT_LABELS: Record<string, string> = {
  thread: 'Thread',
  long_post: 'Long Post',
  article: 'Article',
  infographic: 'Infographic Brief',
}

export function ContentDetailModal({ item, isOpen, onClose }: ContentDetailModalProps) {
  const [activeTab, setActiveTab] = useState(0)
  const activeAlternative: DraftAlternative | undefined = item.alternatives[activeTab]

  // Extract headline from source_text first line
  const headline = item.source_text?.split('\n')[0] ?? 'Content Review'

  return (
    <Dialog open={isOpen} onOpenChange={(open) => { if (!open) onClose() }}>
      <DialogContent className="sm:max-w-2xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="text-base leading-snug pr-8">{headline}</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          {/* Format badge */}
          {item.alternatives[0]?.type && (
            <div className="flex items-center gap-2">
              <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Format</span>
              <span className="inline-flex items-center rounded px-2 py-0.5 text-xs font-medium bg-blue-50 text-blue-700 border border-blue-200">
                {FORMAT_LABELS[item.alternatives[0].type] ?? item.alternatives[0].type}
              </span>
            </div>
          )}

          {/* Source info */}
          {(item.source_account || item.source_url) && (
            <div className="text-xs text-muted-foreground space-y-0.5">
              {item.source_account && <p>Source: {item.source_account}</p>}
              {item.source_url && (
                <a
                  href={item.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="underline hover:text-foreground"
                >
                  View original
                </a>
              )}
            </div>
          )}

          {/* Full source text */}
          {item.source_text && (
            <div className="bg-muted/40 rounded-lg p-3">
              <p className="text-xs font-medium text-muted-foreground mb-1.5 uppercase tracking-wide">Story summary</p>
              <p className="text-sm leading-relaxed text-foreground">{item.source_text}</p>
            </div>
          )}

          {/* Draft alternatives tabs */}
          {item.alternatives.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Draft alternatives</p>

              {/* Tab bar */}
              <div className="flex gap-1 border-b border-border">
                {item.alternatives.map((alt, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => setActiveTab(idx)}
                    className={[
                      'px-3 py-1.5 text-xs font-medium transition-colors border-b-2 -mb-px',
                      activeTab === idx
                        ? 'border-blue-600 text-blue-600'
                        : 'border-transparent text-muted-foreground hover:text-foreground',
                    ].join(' ')}
                  >
                    {alt.label}
                  </button>
                ))}
              </div>

              {/* Active draft content */}
              {activeAlternative && (
                <div className="bg-background border border-border rounded-lg p-4">
                  <p className="text-sm leading-relaxed whitespace-pre-wrap">{activeAlternative.text}</p>
                </div>
              )}
            </div>
          )}

          {/* Why this format */}
          {item.rationale && (
            <div className="space-y-1.5">
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Why this format?</p>
              <p className="text-sm leading-relaxed text-muted-foreground">{item.rationale}</p>
            </div>
          )}

          {/* Score */}
          {item.score != null && (
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground">Quality score:</span>
              <span className="text-sm font-medium">{item.score.toFixed(1)}/10</span>
            </div>
          )}
        </div>

        <DialogFooter showCloseButton />
      </DialogContent>
    </Dialog>
  )
}
