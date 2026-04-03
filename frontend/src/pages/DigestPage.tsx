import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { parse, format, addDays, subDays } from 'date-fns'
import { ChevronLeft, ChevronRight, Calendar } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { getLatestDigest, getDigestByDate } from '@/api/digests'
import type { DailyDigestResponse } from '@/api/types'

interface Story {
  headline: string
  source: string
  url: string
  score?: number
}

interface QueueSnapshot {
  twitter?: number
  instagram?: number
  content?: number
}

interface YesterdayCounts {
  count?: number
}

interface PriorityAlert {
  message?: string
  [key: string]: unknown
}

export function DigestPage() {
  const [currentDate, setCurrentDate] = useState<string | null>(null)
  const [latestDate, setLatestDate] = useState<string | null>(null)

  // Fetch latest digest on mount
  const latestQuery = useQuery({
    queryKey: ['digest', 'latest'],
    queryFn: async () => {
      try {
        return await getLatestDigest()
      } catch (e: unknown) {
        if (e instanceof Error && e.message.includes('404')) return null
        throw e
      }
    },
  })

  // Set current and latest date when data first arrives
  useEffect(() => {
    if (latestQuery.data && latestQuery.data.digest_date && currentDate === null) {
      setCurrentDate(latestQuery.data.digest_date)
      setLatestDate(latestQuery.data.digest_date)
    }
  }, [latestQuery.data, currentDate])

  // Fetch date-specific digest when navigating away from latest
  const isAtLatest = currentDate === latestDate
  const dateQuery = useQuery({
    queryKey: ['digest', currentDate],
    queryFn: async () => {
      try {
        return await getDigestByDate(currentDate!)
      } catch (e: unknown) {
        if (e instanceof Error && e.message.includes('404')) return null
        throw e
      }
    },
    enabled: !!currentDate && !isAtLatest,
  })

  // Determine which digest data to display
  const digest: DailyDigestResponse | null | undefined = isAtLatest || !currentDate
    ? latestQuery.data
    : dateQuery.data

  const isLoading = !currentDate
    ? latestQuery.isLoading
    : isAtLatest
      ? latestQuery.isLoading
      : dateQuery.isLoading

  // Date navigation handlers
  function handlePrev() {
    if (!currentDate) return
    const prevDate = format(
      subDays(parse(currentDate, 'yyyy-MM-dd', new Date()), 1),
      'yyyy-MM-dd'
    )
    setCurrentDate(prevDate)
  }

  function handleNext() {
    if (!currentDate) return
    const nextDate = format(
      addDays(parse(currentDate, 'yyyy-MM-dd', new Date()), 1),
      'yyyy-MM-dd'
    )
    setCurrentDate(nextDate)
  }

  const isNextDisabled = currentDate === latestDate

  // Format date for display
  const displayDate = currentDate
    ? format(parse(currentDate, 'yyyy-MM-dd', new Date()), 'EEEE, MMMM d, yyyy')
    : ''

  // Loading state
  if (isLoading) {
    return (
      <div className="max-w-3xl mx-auto p-8 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <div className="bg-muted animate-pulse rounded h-6 w-32 mb-2" />
            <div className="bg-muted animate-pulse rounded h-4 w-48" />
          </div>
          <div className="flex gap-2">
            <div className="bg-muted animate-pulse rounded h-8 w-8" />
            <div className="bg-muted animate-pulse rounded h-8 w-8" />
          </div>
        </div>
        <div className="bg-muted animate-pulse rounded h-20 w-full" />
        <div className="bg-muted animate-pulse rounded h-40 w-full" />
        <div className="bg-muted animate-pulse rounded h-24 w-full" />
        <div className="bg-muted animate-pulse rounded h-16 w-full" />
      </div>
    )
  }

  // Empty / 404 state — no digest exists for this date
  if (digest === null) {
    return (
      <div className="max-w-3xl mx-auto p-8">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-xl font-semibold">Daily Digest</h1>
            {displayDate && (
              <p className="text-sm text-muted-foreground">{displayDate}</p>
            )}
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="icon"
              aria-label="Previous digest"
              onClick={handlePrev}
            >
              <ChevronLeft className="size-4" />
            </Button>
            <Button
              variant="outline"
              size="icon"
              aria-label="Next digest"
              onClick={handleNext}
              disabled={isNextDisabled}
            >
              <ChevronRight className="size-4" />
            </Button>
          </div>
        </div>
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <div className="w-12 h-12 rounded-full bg-muted flex items-center justify-center mb-4">
            <Calendar className="w-6 h-6 text-muted-foreground" />
          </div>
          <h3 className="text-base font-medium mb-2">No digest available</h3>
          <p className="text-sm text-muted-foreground max-w-xs leading-relaxed">
            No digest has been generated for this date.
          </p>
        </div>
      </div>
    )
  }

  if (!digest) return null

  // Defensive JSONB rendering
  const stories = Array.isArray(digest.top_stories) ? (digest.top_stories as Story[]) : []
  const snapshot = (digest.queue_snapshot as QueueSnapshot) ?? {}
  const approved = (digest.yesterday_approved as YesterdayCounts) ?? {}
  const rejected = (digest.yesterday_rejected as YesterdayCounts) ?? {}
  const expired = (digest.yesterday_expired as YesterdayCounts) ?? {}
  const priorityAlert = digest.priority_alert as PriorityAlert | null

  return (
    <div className="max-w-3xl mx-auto p-8 space-y-6">
      {/* Header row */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Daily Digest</h1>
          <p className="text-sm text-muted-foreground">{displayDate}</p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="icon"
            aria-label="Previous digest"
            onClick={handlePrev}
          >
            <ChevronLeft className="size-4" />
          </Button>
          <Button
            variant="outline"
            size="icon"
            aria-label="Next digest"
            onClick={handleNext}
            disabled={isNextDisabled}
          >
            <ChevronRight className="size-4" />
          </Button>
        </div>
      </div>

      {/* Priority alert banner */}
      {priorityAlert !== null && priorityAlert !== undefined && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 text-amber-800 text-sm">
          <span className="font-semibold">Priority Alert</span>
          {priorityAlert.message && (
            <span className="ml-2">{priorityAlert.message}</span>
          )}
        </div>
      )}

      {/* Top Stories section */}
      <div className="space-y-3">
        <h2 className="text-base font-semibold">Top Stories</h2>
        {stories.length > 0 ? (
          <ol className="space-y-3">
            {stories.map((story, index) => (
              <li key={index} className="flex gap-3">
                <span className="text-sm font-mono text-muted-foreground w-5 shrink-0">
                  {index + 1}.
                </span>
                <div>
                  <p className="text-sm font-medium">{story.headline}</p>
                  {story.url && (
                    <a
                      href={story.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-muted-foreground hover:underline"
                    >
                      {story.source}
                    </a>
                  )}
                </div>
              </li>
            ))}
          </ol>
        ) : (
          <p className="text-sm text-muted-foreground">No stories available.</p>
        )}
      </div>

      {/* Queue Snapshot section */}
      <div className="space-y-3">
        <h2 className="text-base font-semibold">Queue Snapshot</h2>
        <div className="grid grid-cols-3 gap-4">
          <div className="rounded-lg border bg-card p-4">
            <p className="text-xs text-muted-foreground uppercase tracking-wide mb-1">Twitter</p>
            <p className="text-xl font-semibold">{snapshot.twitter ?? 0}</p>
          </div>
          <div className="rounded-lg border bg-card p-4">
            <p className="text-xs text-muted-foreground uppercase tracking-wide mb-1">Instagram</p>
            <p className="text-xl font-semibold">{snapshot.instagram ?? 0}</p>
          </div>
          <div className="rounded-lg border bg-card p-4">
            <p className="text-xs text-muted-foreground uppercase tracking-wide mb-1">Content</p>
            <p className="text-xl font-semibold">{snapshot.content ?? 0}</p>
          </div>
        </div>
      </div>

      {/* Yesterday section */}
      <div className="space-y-2">
        <h2 className="text-base font-semibold">Yesterday</h2>
        <p className="text-sm text-muted-foreground">
          Approved: {approved.count ?? 0} &middot; Rejected: {rejected.count ?? 0} &middot; Expired: {expired.count ?? 0}
        </p>
      </div>
    </div>
  )
}
