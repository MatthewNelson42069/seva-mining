import { Button } from '@/components/ui/button'
import { toast } from 'sonner'

interface InfographicBrief {
  headline?: string
  visual_structure?: string
}

interface BreakingNewsDraft {
  format: 'breaking_news'
  tweet?: string
  infographic_brief?: InfographicBrief
}

export function BreakingNewsPreview({ draft }: { draft: unknown }) {
  const d = (draft ?? {}) as BreakingNewsDraft
  const tweet = typeof d.tweet === 'string' ? d.tweet : ''
  const brief = d.infographic_brief && typeof d.infographic_brief === 'object' ? d.infographic_brief : null

  if (!tweet) {
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
          BREAKING NEWS
        </span>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => {
            navigator.clipboard.writeText(tweet)
            toast.success('Tweet copied')
          }}
        >
          Copy Tweet
        </Button>
      </div>

      <div className="bg-muted/40 rounded-lg p-3">
        <p className="text-sm leading-relaxed whitespace-pre-wrap">{tweet}</p>
      </div>

      {brief && (
        <div className="space-y-1.5 border-t pt-3">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
            Infographic brief
          </p>
          <div className="bg-muted/20 rounded-lg p-3 space-y-1">
            {brief.headline && (
              <p className="text-sm font-medium">{brief.headline}</p>
            )}
            {brief.visual_structure && (
              <p className="text-xs text-muted-foreground">
                Visual: {brief.visual_structure}
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
