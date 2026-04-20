import { Button } from '@/components/ui/button'
import { toast } from 'sonner'

interface InfographicDraft {
  format: 'infographic'
  twitter_caption?: string
  suggested_headline?: string
  data_facts?: string[]
  image_prompt?: string
}

export function InfographicPreview({ draft }: { draft: unknown }) {
  const d = (draft ?? {}) as InfographicDraft
  const headline = typeof d.suggested_headline === 'string' ? d.suggested_headline : ''
  const facts = Array.isArray(d.data_facts) ? d.data_facts.filter((f): f is string => typeof f === 'string') : []
  const imagePrompt = typeof d.image_prompt === 'string' ? d.image_prompt : ''
  const factsClipboard = facts.map(f => `- ${f}`).join('\n')

  // Legacy bundles pre-date this plan — show a minimal placeholder, never crash.
  if (!imagePrompt) {
    return (
      <div className="space-y-3 border rounded-lg p-4">
        <p className="text-sm text-muted-foreground">Legacy format — regenerate this bundle.</p>
      </div>
    )
  }

  return (
    <div className="space-y-3 border rounded-lg p-4">
      <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        INFOGRAPHIC
      </span>

      {/* Block 1: Suggested Headline */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Suggested Headline</p>
          <Button size="sm" variant="ghost" onClick={() => { navigator.clipboard.writeText(headline); toast.success('Headline copied') }}>
            Copy
          </Button>
        </div>
        <div className="bg-muted/40 rounded-lg p-3">
          <p className="text-sm leading-relaxed whitespace-pre-wrap">{headline}</p>
        </div>
      </div>

      {/* Block 2: Key Facts */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Key Facts</p>
          <Button size="sm" variant="ghost" onClick={() => { navigator.clipboard.writeText(factsClipboard); toast.success('Facts copied') }}>
            Copy
          </Button>
        </div>
        <div className="bg-muted/40 rounded-lg p-3">
          <ul className="text-sm leading-relaxed space-y-1">
            {facts.map((f, i) => <li key={i}>- {f}</li>)}
          </ul>
        </div>
      </div>

      {/* Block 3: Image Prompt (claude.ai artifact) */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Image Prompt (paste into claude.ai)</p>
          <Button size="sm" variant="ghost" onClick={() => { navigator.clipboard.writeText(imagePrompt); toast.success('Prompt copied') }}>
            Copy
          </Button>
        </div>
        <div className="bg-muted/40 rounded-lg p-3 max-h-64 overflow-y-auto">
          <pre className="text-xs leading-relaxed whitespace-pre-wrap font-mono">{imagePrompt}</pre>
        </div>
      </div>
    </div>
  )
}
