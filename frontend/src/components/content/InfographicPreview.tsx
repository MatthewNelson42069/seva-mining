import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { toast } from 'sonner'

interface InfographicDraft {
  format: 'infographic'
  headline: string
  key_stats: Array<{ stat: string; source: string; source_url: string }>
  visual_structure: string
  caption_text: string
}

export function InfographicPreview({ draft }: { draft: InfographicDraft }) {
  const keyStats = draft.key_stats ?? []
  const visualStructure = draft.visual_structure ?? ''
  const captionText = draft.caption_text ?? ''
  const headline = draft.headline ?? ''

  return (
    <div className="space-y-3 border rounded-lg p-4">
      <div className="flex items-center gap-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          INFOGRAPHIC BRIEF
        </span>
        {visualStructure && <Badge variant="outline">{visualStructure}</Badge>}
        {captionText && (
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              navigator.clipboard.writeText(captionText)
              toast.success('Caption copied')
            }}
          >
            Copy Caption
          </Button>
        )}
      </div>
      {headline && <p className="font-semibold text-sm">{headline}</p>}
      {keyStats.length > 0 && (
        <ul className="space-y-3">
          {keyStats.map((s, i) => (
            <li key={i} className="text-sm">
              <span className="font-medium">{s.stat}</span>
              {s.source_url ? (
                <a
                  href={s.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block text-xs text-muted-foreground hover:underline"
                >
                  {s.source}
                </a>
              ) : (
                <span className="block text-xs text-muted-foreground">{s.source}</span>
              )}
            </li>
          ))}
        </ul>
      )}
      {captionText && (
        <p className="text-sm text-muted-foreground border-t pt-3 mt-3">{captionText}</p>
      )}
    </div>
  )
}
