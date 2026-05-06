import ReactMarkdown from 'react-markdown'
import rehypeSanitize from 'rehype-sanitize'

import { cn } from '@/lib/utils'

export interface SectionBlockProps {
  /** Section heading rendered as <h3> (e.g. "Gold News", "Ontario Law", "Ontario Stats"). */
  title: string
  /** Markdown content from one of the daily_summaries.*_md columns. May be null/empty. */
  content: string | null
  /** Fallback line shown when `content` is null or empty. */
  emptyFallback: string
  className?: string
}

/**
 * One labeled section inside a SummaryCard.
 *
 * Renders markdown via react-markdown + rehype-sanitize default schema. The
 * sanitizer strips script/iframe/style/form/event-handlers/javascript: at the
 * AST level BEFORE the DOM is touched — defence-in-depth for LLM output.
 *
 * Phase 1, Plan 06.
 */
export function SectionBlock({ title, content, emptyFallback, className }: SectionBlockProps) {
  const hasContent = content !== null && content.trim().length > 0

  return (
    <section className={cn('space-y-2', className)}>
      <h3 className="text-sm font-semibold text-foreground">{title}</h3>
      {hasContent ? (
        <div className="prose prose-sm max-w-none text-foreground [&_a]:text-primary [&_a]:underline [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5">
          <ReactMarkdown rehypePlugins={[rehypeSanitize]}>{content as string}</ReactMarkdown>
        </div>
      ) : (
        <p className="text-sm italic text-muted-foreground">{emptyFallback}</p>
      )}
    </section>
  )
}
