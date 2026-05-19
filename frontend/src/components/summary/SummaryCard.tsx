import { format, parseISO } from 'date-fns'

import type { SummaryCard as SummaryCardData } from '@/api/summaries'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

import { SectionBlock } from './SectionBlock'

export interface SummaryCardComponentProps {
  summary: SummaryCardData
  className?: string
}

/**
 * One summary card in the feed.
 *
 * Layout:
 *   ┌──────────────────────────────────────────────┐
 *   │ Summary as of 08:00 PT — April 27   [badge?] │  ← title row
 *   ├──────────────────────────────────────────────┤
 *   │ Gold News                                    │
 *   │ <markdown>                                   │
 *   │ Ontario Law                                  │
 *   │ <markdown>                                   │
 *   │ Ontario Stats                                │
 *   │ <markdown>                                   │
 *   └──────────────────────────────────────────────┘
 *
 * Status badge: hidden on 'completed'; amber-pill on 'partial'; red on 'failed'.
 * (Locked decision per CONTEXT.md — clean default for the common case.)
 *
 * Note: card.tsx primitive does not exist in this codebase (not installed via shadcn).
 * Using a div wrapper with equivalent styling.
 *
 * Phase 1, Plan 06.
 */
export function SummaryCard({ summary, className }: SummaryCardComponentProps) {
  const datePart = format(parseISO(summary.generated_at), 'MMMM d')
  const title = `Summary as of ${summary.period_label} — ${datePart}`

  return (
    <div className={cn('w-full rounded-lg border bg-card shadow-sm hover:border-zinc-700 transition-colors', className)}>
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-base font-semibold text-foreground">{title}</h2>
          {summary.status === 'partial' && (
            <Badge
              variant="outline"
              className="bg-amber-100 text-amber-900 border-amber-300"
            >
              Partial
            </Badge>
          )}
          {summary.status === 'failed' && (
            <Badge variant="destructive">Failed</Badge>
          )}
          {/* status === 'completed' renders no badge — locked decision */}
        </div>

        <div className="space-y-5">
          <SectionBlock
            title="Gold News"
            content={summary.gold_news_md}
            emptyFallback="No major moves in gold for this window."
          />
          <SectionBlock
            title="Ontario Law"
            content={summary.ontario_law_md}
            emptyFallback="No new Ontario mining-related laws today."
          />
          <SectionBlock
            title="Ontario Stats"
            content={summary.ontario_stats_md}
            emptyFallback="No new production statistics released today."
          />
        </div>
      </div>
    </div>
  )
}
