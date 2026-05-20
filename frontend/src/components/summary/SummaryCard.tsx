import { format, parseISO } from 'date-fns'
import { useParams } from 'react-router-dom'

import type { SummaryCard as SummaryCardData } from '@/api/summaries'
import { Badge } from '@/components/ui/badge'
import { companySectionConfig } from '@/config/companySectionConfig'
import { cn } from '@/lib/utils'

import { SectionBlock } from './SectionBlock'

export interface SummaryCardComponentProps {
  summary: SummaryCardData
  className?: string
}

/**
 * One summary card in the feed.
 *
 * Layout (per-tenant via companySectionConfig):
 *   ┌──────────────────────────────────────────────┐
 *   │ Summary as of 08:00 PT — April 27   [badge?] │  ← title row
 *   ├──────────────────────────────────────────────┤
 *   │ {sections[0].title}                          │  ← Seva: "Gold News"
 *   │ <markdown>                                   │     Juno: "Defence News"
 *   │ {sections[1].title}                          │  ← Seva: "Ontario Law"
 *   │ <markdown>                                   │     Juno: "Canadian Procurement"
 *   │ {sections[2].title}                          │  ← Seva: "Ontario Stats"
 *   │ <markdown>                                   │     Juno: "World Events Relevant to Defence"
 *   └──────────────────────────────────────────────┘
 *
 * Status badge: hidden on 'completed'; amber-pill on 'partial'; red on 'failed'.
 * (Locked decision per CONTEXT.md — clean default for the common case.)
 *
 * Per-tenant section configuration via frontend/src/config/companySectionConfig.ts
 * (Phase 10 DEF-08 — Phase 9 D-08 claim was verified-false; SummaryCard was
 * hardcoded with Seva field names + titles until this Wave 3 edit landed. The
 * 3 physical DB columns (gold_news_md / ontario_law_md / ontario_stats_md) are
 * reused semantically per Phase 9 D-08 — Juno's "Defence News" markdown lives
 * in gold_news_md, "Canadian Procurement" in ontario_law_md, "World Events
 * Relevant to Defence" in ontario_stats_md. No Alembic migration; only the
 * per-tenant display titles + empty-fallback copy change.)
 *
 * Note: card.tsx primitive does not exist in this codebase (not installed via shadcn).
 * Using a div wrapper with equivalent styling.
 *
 * Phase 1, Plan 06; per-tenant section config: Phase 10, Plan 04.
 */
export function SummaryCard({ summary, className }: SummaryCardComponentProps) {
  const datePart = format(parseISO(summary.generated_at), 'MMMM d')
  const title = `Summary as of ${summary.period_label} — ${datePart}`

  const { company = 'seva' } = useParams<{ company: 'seva' | 'juno' }>()
  const sections = companySectionConfig[company]

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
          {sections.map((section) => (
            <SectionBlock
              key={section.field}
              title={section.title}
              content={summary[section.field]}
              emptyFallback={section.emptyFallback}
            />
          ))}
        </div>
      </div>
    </div>
  )
}
