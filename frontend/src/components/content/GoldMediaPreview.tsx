import { Button } from '@/components/ui/button'
import { toast } from 'sonner'

interface GoldMediaDraft {
  format: 'gold_media'
  twitter_caption?: string
  video_url?: string
}

export function GoldMediaPreview({ draft }: { draft: unknown }) {
  const d = (draft ?? {}) as GoldMediaDraft
  const twitterCaption = typeof d.twitter_caption === 'string' ? d.twitter_caption : ''
  const videoUrl = typeof d.video_url === 'string' ? d.video_url : ''

  if (!twitterCaption) {
    return (
      <div className="space-y-3 border rounded-lg p-4">
        <p className="text-sm text-muted-foreground">No draft content available.</p>
      </div>
    )
  }

  return (
    <div className="space-y-3 border rounded-lg p-4">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          GOLD MEDIA
        </span>
        {videoUrl && (
          <Button
            size="sm"
            variant="outline"
            onClick={() => window.open(videoUrl, '_blank', 'noopener,noreferrer')}
          >
            Watch clip
          </Button>
        )}
      </div>

      <div className="space-y-1.5">
        <div className="flex items-center justify-between">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
            Twitter / X caption
          </p>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              navigator.clipboard.writeText(twitterCaption)
              toast.success('Twitter caption copied')
            }}
          >
            Copy
          </Button>
        </div>
        <div className="bg-muted/40 rounded-lg p-3">
          <p className="text-sm leading-relaxed whitespace-pre-wrap">{twitterCaption}</p>
        </div>
      </div>
    </div>
  )
}
