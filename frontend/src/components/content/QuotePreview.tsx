import { Button } from '@/components/ui/button'
import { toast } from 'sonner'

interface QuoteDraft {
  format: 'quote'
  speaker?: string
  speaker_title?: string
  attributed_to?: string
  twitter_post?: string
  source_url?: string
  suggested_headline?: string
  data_facts?: string[]
  image_prompt?: string
}

export function QuotePreview({ draft }: { draft: unknown }) {
  const d = (draft ?? {}) as QuoteDraft
  const twitterPost = typeof d.twitter_post === 'string' ? d.twitter_post : ''
  const speaker = typeof d.speaker === 'string' ? d.speaker : (typeof d.attributed_to === 'string' ? d.attributed_to : '')
  const sourceUrl = typeof d.source_url === 'string' ? d.source_url : ''
  const headline = typeof d.suggested_headline === 'string' ? d.suggested_headline : ''
  const facts = Array.isArray(d.data_facts) ? d.data_facts.filter((f): f is string => typeof f === 'string') : []
  const imagePrompt = typeof d.image_prompt === 'string' ? d.image_prompt : ''
  const factsClipboard = facts.map(f => `- ${f}`).join('\n')

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
        {speaker && (
          <span className="text-xs text-muted-foreground">— {speaker}</span>
        )}
      </div>

      {/* Tweet block (always present) */}
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

      {/* Three new fields — only if image_prompt present (new-shape bundles) */}
      {imagePrompt && (
        <>
          {/* Suggested Headline */}
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

          {/* Key Facts */}
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

          {/* Image Prompt */}
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
        </>
      )}

      {/* Footer: attribution + source */}
      {(speaker || sourceUrl) && (
        <div className="border-t pt-3 flex items-center gap-3 text-xs text-muted-foreground">
          {speaker && <span>— {speaker}</span>}
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
