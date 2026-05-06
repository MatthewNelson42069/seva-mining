import { useSummaries } from '@/api/summaries'
import { SummaryCard } from '@/components/summary/SummaryCard'

/**
 * Compute the next 08:00 PT or 12:00 PT cron fire time from the current
 * America/Los_Angeles wall clock. Used by the empty-state copy.
 *
 * Returns a string of the form "HH:MM PT" (24h, zero-padded minutes).
 */
function nextCronFireLabelPT(now: Date = new Date()): string {
  // Render the current PT hour using Intl (avoids zoneinfo math by hand).
  const ptHourStr = now.toLocaleString('en-US', {
    timeZone: 'America/Los_Angeles',
    hour: '2-digit',
    hour12: false,
  })
  const ptHour = parseInt(ptHourStr, 10)
  // Crons fire at 08:00 PT and 12:00 PT.
  // - Before 08: next fire is 08:00 PT today
  // - 08-11:    next fire is 12:00 PT today
  // - 12+:      next fire is 08:00 PT tomorrow (shown as 08:00 PT — no "tomorrow" label)
  if (ptHour < 8) return '08:00 PT'
  if (ptHour < 12) return '12:00 PT'
  return '08:00 PT'
}

/**
 * Top-level v2.0 web feed page (Phase 1, Plan 06).
 *
 * Layout: single-column, full-width vertical scroll, max-w-2xl. Instagram-feed
 * style per locked CONTEXT decision.
 *
 * Empty state: "Waiting for first summary. Next fire at {next_cron_PT}."
 * Loading state: spinner / "Loading…" text.
 * Error state: simple message; no retry UI in v2.0.
 */
export function SummaryFeedPage() {
  const { data, isLoading, error } = useSummaries(60)

  if (isLoading) {
    return (
      <div className="max-w-2xl mx-auto py-8 px-4">
        <p className="text-sm text-muted-foreground">Loading…</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="max-w-2xl mx-auto py-8 px-4">
        <p className="text-sm text-destructive">Failed to load summaries.</p>
      </div>
    )
  }

  const summaries = data?.summaries ?? []

  if (summaries.length === 0) {
    const nextFire = nextCronFireLabelPT()
    return (
      <div className="max-w-2xl mx-auto py-8 px-4">
        <p className="text-sm text-muted-foreground">
          Waiting for first summary. Next fire at {nextFire}.
        </p>
      </div>
    )
  }

  return (
    <div className="max-w-2xl mx-auto py-8 px-4 space-y-6">
      {summaries.map((s) => (
        <SummaryCard key={s.id} summary={s} />
      ))}
    </div>
  )
}
