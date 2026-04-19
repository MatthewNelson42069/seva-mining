import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { toast } from 'sonner'

interface ThreadDraft {
  format: 'thread'
  tweets?: string[]
  long_form_post?: string
}

export function ThreadPreview({ draft }: { draft: unknown }) {
  const d = (draft ?? {}) as ThreadDraft
  const tweets = Array.isArray(d.tweets) ? d.tweets : []
  const longFormPost = typeof d.long_form_post === 'string' ? d.long_form_post : ''

  if (tweets.length === 0 && !longFormPost) {
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
          THREAD
        </span>
        {tweets.length > 0 && (
          <Badge variant="outline">{tweets.length} tweets</Badge>
        )}
        {tweets.length > 0 && (
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              const text = tweets.join('\n\n')
              navigator.clipboard.writeText(text)
              toast.success('Thread copied')
            }}
          >
            Copy Thread
          </Button>
        )}
      </div>

      {tweets.length > 0 && (
        <ol className="space-y-2">
          {tweets.map((tweet, idx) => (
            <li key={idx} className="flex gap-2">
              <span className="shrink-0 text-xs font-medium text-muted-foreground mt-1 w-5 text-right">
                {idx + 1}.
              </span>
              <div className="flex-1 bg-muted/40 rounded-lg p-3">
                <p className="text-sm leading-relaxed whitespace-pre-wrap">{tweet}</p>
              </div>
            </li>
          ))}
        </ol>
      )}

      {longFormPost && (
        <div className="space-y-1.5 border-t pt-3">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
            Long-form version
          </p>
          <div className="bg-muted/40 rounded-lg p-3">
            <p className="text-sm leading-relaxed whitespace-pre-wrap">{longFormPost}</p>
          </div>
        </div>
      )}
    </div>
  )
}
