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
  return (
    <div className="space-y-3 border rounded-lg p-4">
      <div className="flex items-center gap-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          INFOGRAPHIC BRIEF
        </span>
        <Badge variant="outline">{draft.visual_structure}</Badge>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => {
            navigator.clipboard.writeText(draft.caption_text)
            toast.success('Caption copied')
          }}
        >
          Copy Caption
        </Button>
      </div>
      <p className="font-semibold text-sm">{draft.headline}</p>
      <ul className="space-y-3">
        {draft.key_stats.map((s, i) => (
          <li key={i} className="text-sm">
            <span className="font-medium">{s.stat}</span>
            <a
              href={s.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="block text-xs text-muted-foreground hover:underline"
            >
              {s.source}
            </a>
          </li>
        ))}
      </ul>
      <p className="text-sm text-muted-foreground border-t pt-3 mt-3">{draft.caption_text}</p>
    </div>
  )
}
