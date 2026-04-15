import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { parse, format, addDays, subDays, formatDistanceToNow } from 'date-fns'
import { ChevronLeft, ChevronRight, Calendar, ExternalLink, Newspaper } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { getLatestDigest, getDigestByDate } from '@/api/digests'
import type { DailyDigestResponse } from '@/api/types'

interface Story {
  headline: string
  source?: string
  time?: string | null
  url?: string | null
  score?: number
}

interface QueueSnapshot {
  twitter?: number
  instagram?: number
  content?: number
  total?: number
}

interface YesterdayCounts {
  count?: number
}

interface PriorityAlert {
  headline?: string
  platform?: string
  score?: number
  source_url?: string | null
  [key: string]: unknown
}

// Source → pill color mapping
const SOURCE_COLORS: Record<string, string> = {
  reuters:    'bg-orange-100 text-orange-700',
  bloomberg:  'bg-purple-100 text-purple-700',
  kitco:      'bg-yellow-100 text-yellow-700',
  cnbc:       'bg-blue-100 text-blue-700',
  'world gold council': 'bg-amber-100 text-amber-700',
  ft:         'bg-pink-100 text-pink-700',
  wsj:        'bg-slate-100 text-slate-700',
  marketwatch:'bg-green-100 text-green-700',
  investing:  'bg-teal-100 text-teal-700',
}

function sourceColor(source?: string): string {
  if (!source) return 'bg-zinc-100 text-zinc-600'
  const key = source.toLowerCase()
  for (const [k, v] of Object.entries(SOURCE_COLORS)) {
    if (key.includes(k)) return v
  }
  return 'bg-zinc-100 text-zinc-600'
}

function timeAgo(iso?: string | null): string {
  if (!iso) return ''
  try {
    return formatDistanceToNow(new Date(iso), { addSuffix: true })
  } catch {
    return ''
  }
}

function ScoreDot({ score }: { score?: number }) {
  if (score == null) return null
  const color =
    score >= 8 ? 'bg-emerald-500' :
    score >= 6 ? 'bg-amber-400' :
    'bg-zinc-300'
  return (
    <span
      title={`Score: ${score.toFixed(1)}`}
      className={`inline-block w-2 h-2 rounded-full ${color} shrink-0`}
    />
  )
}

function StoryCard({ story, index }: { story: Story; index: number }) {
  const ago = timeAgo(story.time)
  return (
    <div className="rounded-xl border bg-card shadow-sm p-4 space-y-2">
      {/* Header row: index + source pill + time + score dot */}
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-xs font-mono text-muted-foreground w-5 shrink-0 select-none">
          {index + 1}.
        </span>
        {story.source && (
          <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${sourceColor(story.source)}`}>
            {story.source}
          </span>
        )}
        {ago && (
          <span className="text-xs text-muted-foreground">{ago}</span>
        )}
        <ScoreDot score={story.score} />
      </div>

      {/* Headline */}
      <p className="text-sm font-medium leading-snug pl-7">{story.headline}</p>

      {/* Source link */}
      {story.url && (
        <div className="pl-7">
          <a
            href={story.url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            <ExternalLink className="size-3" />
            View source
          </a>
        </div>
      )}
    </div>
  )
}

export function DigestPage() {
  const [currentDate, setCurrentDate] = useState<string | null>(null)
  const [latestDate, setLatestDate] = useState<string | null>(null)

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

  useEffect(() => {
    if (latestQuery.data && latestQuery.data.digest_date && currentDate === null) {
      setCurrentDate(latestQuery.data.digest_date)
      setLatestDate(latestQuery.data.digest_date)
    }
  }, [latestQuery.data, currentDate])

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

  const digest: DailyDigestResponse | null | undefined =
    isAtLatest || !currentDate ? latestQuery.data : dateQuery.data

  const isLoading = !currentDate
    ? latestQuery.isLoading
    : isAtLatest
      ? latestQuery.isLoading
      : dateQuery.isLoading

  function handlePrev() {
    if (!currentDate) return
    setCurrentDate(
      format(subDays(parse(currentDate, 'yyyy-MM-dd', new Date()), 1), 'yyyy-MM-dd')
    )
  }

  function handleNext() {
    if (!currentDate) return
    setCurrentDate(
      format(addDays(parse(currentDate, 'yyyy-MM-dd', new Date()), 1), 'yyyy-MM-dd')
    )
  }

  const isNextDisabled = currentDate === latestDate

  const displayDate = currentDate
    ? format(parse(currentDate, 'yyyy-MM-dd', new Date()), 'EEEE, MMMM d, yyyy')
    : ''

  // ─── Loading ────────────────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="max-w-3xl mx-auto p-8 space-y-4">
        <div className="flex items-center justify-between mb-6">
          <div>
            <div className="bg-muted animate-pulse rounded h-6 w-32 mb-2" />
            <div className="bg-muted animate-pulse rounded h-4 w-48" />
          </div>
          <div className="flex gap-2">
            <div className="bg-muted animate-pulse rounded h-8 w-8" />
            <div className="bg-muted animate-pulse rounded h-8 w-8" />
          </div>
        </div>
        {[...Array(5)].map((_, i) => (
          <div key={i} className="bg-muted animate-pulse rounded-xl h-20 w-full" />
        ))}
      </div>
    )
  }

  // ─── Empty / 404 ────────────────────────────────────────────────────────────
  if (digest === null) {
    return (
      <div className="max-w-3xl mx-auto p-8">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-xl font-semibold">Daily Digest</h1>
            {displayDate && <p className="text-sm text-muted-foreground">{displayDate}</p>}
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="icon" aria-label="Previous digest" onClick={handlePrev}>
              <ChevronLeft className="size-4" />
            </Button>
            <Button variant="outline" size="icon" aria-label="Next digest" onClick={handleNext} disabled={isNextDisabled}>
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

  // ─── Data extraction ─────────────────────────────────────────────────────────
  const stories = Array.isArray(digest.top_stories) ? (digest.top_stories as Story[]) : []
  const snapshot = (digest.queue_snapshot as QueueSnapshot) ?? {}
  const approved = (digest.yesterday_approved as YesterdayCounts) ?? {}
  const rejected = (digest.yesterday_rejected as YesterdayCounts) ?? {}
  const expired = (digest.yesterday_expired as YesterdayCounts) ?? {}
  const priorityAlert = digest.priority_alert as PriorityAlert | null

  return (
    <div className="max-w-3xl mx-auto p-8 space-y-6">
      {/* ── Header ── */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Daily Digest</h1>
          <p className="text-sm text-muted-foreground">{displayDate}</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="icon" aria-label="Previous digest" onClick={handlePrev}>
            <ChevronLeft className="size-4" />
          </Button>
          <Button variant="outline" size="icon" aria-label="Next digest" onClick={handleNext} disabled={isNextDisabled}>
            <ChevronRight className="size-4" />
          </Button>
        </div>
      </div>

      {/* ── Stats row ── */}
      <div className="grid grid-cols-4 gap-3">
        <div className="rounded-xl border bg-card p-4">
          <p className="text-xs text-muted-foreground uppercase tracking-wide mb-1">Twitter</p>
          <p className="text-xl font-semibold">{snapshot.twitter ?? 0}</p>
        </div>
        <div className="rounded-xl border bg-card p-4">
          <p className="text-xs text-muted-foreground uppercase tracking-wide mb-1">Instagram</p>
          <p className="text-xl font-semibold">{snapshot.instagram ?? 0}</p>
        </div>
        <div className="rounded-xl border bg-card p-4">
          <p className="text-xs text-muted-foreground uppercase tracking-wide mb-1">Content</p>
          <p className="text-xl font-semibold">{snapshot.content ?? 0}</p>
        </div>
        <div className="rounded-xl border bg-card p-4">
          <p className="text-xs text-muted-foreground uppercase tracking-wide mb-1">Yesterday</p>
          <p className="text-xl font-semibold">{approved.count ?? 0}
            <span className="text-xs font-normal text-muted-foreground ml-1">approved</span>
          </p>
          <p className="text-xs text-muted-foreground mt-0.5">
            {rejected.count ?? 0} rejected · {expired.count ?? 0} expired
          </p>
        </div>
      </div>

      {/* ── Priority alert ── */}
      {priorityAlert != null && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 flex items-start gap-3">
          <span className="mt-0.5 w-2 h-2 rounded-full bg-amber-500 shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-amber-900">Priority Alert</p>
            {priorityAlert.headline && (
              <p className="text-sm text-amber-800 mt-0.5">{priorityAlert.headline}</p>
            )}
            {priorityAlert.platform && (
              <Badge variant="outline" className="mt-1 text-xs border-amber-300 text-amber-700">
                {priorityAlert.platform}
              </Badge>
            )}
          </div>
          {priorityAlert.score != null && (
            <span className="text-sm font-semibold text-amber-700 shrink-0">
              {Number(priorityAlert.score).toFixed(1)}
            </span>
          )}
        </div>
      )}

      {/* ── Top Gold News Stories ── */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold">Top Gold News Stories</h2>
          {stories.length > 0 && (
            <span className="text-xs text-muted-foreground">{stories.length} stories</span>
          )}
        </div>

        {stories.length > 0 ? (
          <div className="space-y-2">
            {stories.map((story, index) => (
              <StoryCard key={index} story={story} index={index} />
            ))}
          </div>
        ) : (
          <div className="rounded-xl border bg-card p-8 flex flex-col items-center justify-center text-center">
            <div className="w-10 h-10 rounded-full bg-muted flex items-center justify-center mb-3">
              <Newspaper className="w-5 h-5 text-muted-foreground" />
            </div>
            <p className="text-sm font-medium mb-1">No stories yet</p>
            <p className="text-xs text-muted-foreground max-w-xs">
              Gold news stories will appear here after the content agent runs.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
