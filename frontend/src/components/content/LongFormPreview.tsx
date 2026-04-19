import { Button } from '@/components/ui/button'
import { toast } from 'sonner'

interface LongFormDraft {
  format: 'long_form'
  post_text?: string
}

export function LongFormPreview({ draft }: { draft: unknown }) {
  const d = (draft ?? {}) as LongFormDraft
  const postText = typeof d.post_text === 'string' ? d.post_text : ''

  if (!postText) {
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
          LONG-FORM POST
        </span>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => {
            navigator.clipboard.writeText(postText)
            toast.success('Post copied')
          }}
        >
          Copy Post
        </Button>
      </div>

      <div className="bg-muted/40 rounded-lg p-3">
        <p className="text-sm leading-relaxed whitespace-pre-wrap">{postText}</p>
      </div>
    </div>
  )
}
