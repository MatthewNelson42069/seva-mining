import { format, parseISO } from 'date-fns'

import type { WeeklySweepCard as WeeklySweepCardData } from '@/api/weeklySweeps'
import { MarkdownContent } from '@/components/markdown/MarkdownContent'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

export interface SweeperCardProps {
  sweep: WeeklySweepCardData
  className?: string
}

/**
 * One weekly viral sweeper card.
 *
 * Layout:
 *   ┌──────────────────────────────────────────────────┐
 *   │ Weekly Sweep — May 11 – May 17, 2026     [badge?] │
 *   │ [status banner if non-completed]                  │
 *   │                                                   │
 *   │ ### Top X Posts This Week (column: reddit_top_md) │
 *   │ <markdown>                                        │
 *   │                                                   │
 *   │ ### Most Cross-Referenced Stories                 │
 *   │ <markdown>                                        │
 *   │                                                   │
 *   │ ### 3 Content Angles                              │
 *   │ <markdown>                                        │
 *   └──────────────────────────────────────────────────┘
 *
 * Status banner (SWEEP-14):
 *   - 'completed': no banner, no badge
 *   - 'partial':   amber banner "Sweeper had partial output — some sections may be empty"
 *   - 'failed':    red banner "Sweeper failed last run — see telemetry"
 *
 * Phase 7, Plan 06.
 */
export function SweeperCard({ sweep, className }: SweeperCardProps) {
  const weekStartDate = format(parseISO(sweep.week_start), 'MMM d')
  const weekEndDate = format(parseISO(sweep.week_end), 'MMM d, yyyy')
  const title = `Weekly Sweep — ${weekStartDate} – ${weekEndDate}`

  const showStatusBadge = sweep.status !== 'completed'

  const bannerCopy =
    sweep.status === 'failed'
      ? 'Sweeper failed last run — see telemetry'
      : sweep.status === 'partial'
        ? 'Sweeper had partial output — some sections may be empty'
        : null

  return (
    <div
      className={cn(
        'w-full rounded-lg border bg-card shadow-sm hover:border-zinc-700 transition-colors',
        className,
      )}
    >
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-base font-semibold text-foreground">{title}</h2>
          {showStatusBadge && sweep.status === 'failed' && (
            <Badge variant="destructive">Failed</Badge>
          )}
          {showStatusBadge && sweep.status === 'partial' && (
            <Badge
              variant="outline"
              className="bg-amber-100 text-amber-900 border-amber-300"
            >
              Partial
            </Badge>
          )}
        </div>

        {bannerCopy && (
          <div
            className={cn(
              'rounded border px-4 py-2 text-sm',
              sweep.status === 'failed'
                ? 'border-red-800 bg-red-950/40 text-red-200'
                : 'border-amber-800 bg-amber-950/40 text-amber-200',
            )}
            role="status"
          >
            {bannerCopy}
          </div>
        )}

        <div className="space-y-5">
          {/* Section 1: Top X Posts This Week (column: reddit_top_md) */}
          {sweep.reddit_top_md && (
            <section className="prose prose-sm max-w-none text-foreground [&_a]:text-primary [&_a]:underline [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5">
              <MarkdownContent content={sweep.reddit_top_md} />
            </section>
          )}

          {/* Section 2: Most Cross-Referenced Stories */}
          {sweep.story_virality_md && (
            <section className="prose prose-sm max-w-none text-foreground [&_a]:text-primary [&_a]:underline [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5">
              <MarkdownContent content={sweep.story_virality_md} />
            </section>
          )}

          {/* Section 3: 3 Content Angles */}
          {sweep.content_angles_md && (
            <section className="prose prose-sm max-w-none text-foreground [&_a]:text-primary [&_a]:underline [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5">
              <MarkdownContent content={sweep.content_angles_md} />
            </section>
          )}
        </div>
      </div>
    </div>
  )
}
