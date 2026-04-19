import { Button } from '@/components/ui/button'
import { toast } from 'sonner'

interface QuoteDraft {
  format: 'quote'
  twitter_post?: string
  attributed_to?: string
  source_url?: string
}

export function QuotePreview({ draft }: { draft: unknown }) {
  const d = (draft ?? {}) as QuoteDraft
  const twitterPost = typeof d.twitter_post === 'string' ? d.twitter_post : ''
  const attributedTo = typeof d.attributed_to === 'string' ? d.attributed_to : ''
  const sourceUrl = typeof d.source_url === 'string' ? d.source_url : ''

  if (!twitterPost) {
    return (
      <div className="space-y-3 border rounded-lg p-4">
        <p className="text-sm text-muted-foreground">No draft content available.</p>
      </div>
    )
  }

  return (
    <div className="space-y-3 border rounded-lg p-4">
      <div className="flex items-center gap-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          QUOTE
        </span>
        {attributedTo && (
          <span className="text-xs text-muted-foreground">— {attributedTo}</span>
        )}
      </div>

      <div className="space-y-1.5">
        <div className="flex items-center justify-between">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
            Twitter / X
          </p>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              navigator.clipboard.writeText(twitterPost)
              toast.success('Twitter post copied')
            }}
          >
            Copy
          </Button>
        </div>
        <div className="bg-muted/40 rounded-lg p-3">
          <p className="text-sm leading-relaxed whitespace-pre-wrap">{twitterPost}</p>
        </div>
      </div>

      {(attributedTo || sourceUrl) && (
        <div className="border-t pt-3 flex items-center gap-3 text-xs text-muted-foreground">
          {attributedTo && <span>— {attributedTo}</span>}
          {sourceUrl && (
            <a
              href={sourceUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="underline hover:text-foreground"
            >
              Source
            </a>
          )}
        </div>
      )}
    </div>
  )
}
