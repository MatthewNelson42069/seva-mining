import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import type { DraftItemResponse, DraftAlternative } from '@/api/types'
import { useContentBundle } from '@/hooks/useContentBundle'
import { InfographicPreview } from '@/components/content/InfographicPreview'
import { ThreadPreview } from '@/components/content/ThreadPreview'
import { BreakingNewsPreview } from '@/components/content/BreakingNewsPreview'
import { QuotePreview } from '@/components/content/QuotePreview'
import { GoldMediaPreview } from '@/components/content/GoldMediaPreview'

interface ContentDetailModalProps {
  item: DraftItemResponse
  isOpen: boolean
  onClose: () => void
}

// Formats that have a structured preview renderer
const FORMAT_RENDERERS: Record<string, true> = {
  infographic: true,
  thread: true,
  breaking_news: true,
  quote: true,
  gold_media: true,
}

export function ContentDetailModal({ item, isOpen, onClose }: ContentDetailModalProps) {
  // Pull content_bundle_id from engagement_snapshot (populated by Plan 01 schema change)
  const bundleId =
    (item.engagement_snapshot as Record<string, unknown> | undefined)?.content_bundle_id as
      | string
      | undefined

  const { data: bundle, isError, isLoading } = useContentBundle(bundleId ?? null)

  const headline =
    bundle?.story_headline ?? item.source_text?.split('\n')[0] ?? 'Content Review'

  const contentType = bundle?.content_type ?? ''
  // Fallback path: no bundle id, fetch failed, or unknown format → flat text (D-24)
  const showFallback = !bundleId || isError || !FORMAT_RENDERERS[contentType]

  return (
    <Dialog open={isOpen} onOpenChange={(open) => { if (!open) onClose() }}>
      <DialogContent className="sm:max-w-3xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="text-base leading-snug pr-8">{headline}</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          {/* Source metadata */}
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

          {/* Loading state — brief skeleton while bundle is fetching */}
          {isLoading && bundleId && (
            <div className="space-y-2" aria-label="Loading content bundle">
              <div className="h-4 bg-muted/40 rounded animate-pulse w-3/4" />
              <div className="h-4 bg-muted/40 rounded animate-pulse w-1/2" />
              <div className="h-4 bg-muted/40 rounded animate-pulse w-2/3" />
            </div>
          )}

          {/* Brief renders immediately (D-13) */}
          {!isLoading && (
            showFallback ? (
              <FlatTextFallback item={item} />
            ) : (
              bundle && renderForFormat(contentType, bundle)
            )
          )}

          {/* Rationale */}
          {item.rationale && (
            <div className="space-y-1.5">
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                Why this format?
              </p>
              <p className="text-sm leading-relaxed text-muted-foreground">{item.rationale}</p>
            </div>
          )}

          {/* Quality score */}
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

type BundleData = NonNullable<ReturnType<typeof useContentBundle>['data']>

function renderForFormat(contentType: string, bundle: BundleData) {
  const draft = bundle.draft_content as unknown
  switch (contentType) {
    case 'infographic':
      return <InfographicPreview draft={draft} />
    case 'thread':
      return <ThreadPreview draft={draft} />
    case 'breaking_news':
      return <BreakingNewsPreview draft={draft} />
    case 'quote':
      return <QuotePreview draft={draft} />
    case 'gold_media':
      return <GoldMediaPreview draft={draft} />
    default:
      return null
  }
}

function FlatTextFallback({ item }: { item: DraftItemResponse }) {
  // Preserve the pre-Phase-11 behavior: render draft alternatives as plain text (D-24)
  const alt: DraftAlternative | undefined = item.alternatives[0]
  if (!alt) {
    return <p className="text-sm text-muted-foreground">No draft content available.</p>
  }
  return (
    <div className="bg-background border border-border rounded-lg p-4">
      <p className="text-sm leading-relaxed whitespace-pre-wrap">{alt.text}</p>
    </div>
  )
}
