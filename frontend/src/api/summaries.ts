import { useQuery } from '@tanstack/react-query'
import { apiFetch } from './client'

/** One summary card returned by GET /summaries.
 *  Mirrors backend/app/schemas/daily_summary.py::SummaryCardResponse. */
export interface SummaryCard {
  id: string
  generated_at: string  // ISO datetime
  period_label: string  // '08:00 PT' | '12:00 PT'
  gold_news_md: string | null
  ontario_law_md: string | null
  ontario_stats_md: string | null
  status: 'completed' | 'failed' | 'partial'
  error_text: string | null
}

export interface SummaryFeedResponse {
  summaries: SummaryCard[]
  total: number
}

/** Fetch up to `limit` summaries (newest first). */
export async function getSummaries(limit = 60): Promise<SummaryFeedResponse> {
  return apiFetch<SummaryFeedResponse>(`/summaries?limit=${limit}`)
}

/** TanStack Query hook with locked refetch behaviour:
 *  - refetchInterval: 5 min (FEED-06 — per-fire freshness without manual reload)
 *  - refetchOnWindowFocus: false (locked CONTEXT decision — read-only intelligence,
 *    no need for hyperactive freshness)
 */
export function useSummaries(limit = 60) {
  return useQuery({
    queryKey: ['summaries', limit],
    queryFn: () => getSummaries(limit),
    refetchInterval: 5 * 60 * 1000,  // 5 minutes — FEED-06
    refetchOnWindowFocus: false,     // locked CONTEXT decision
    staleTime: 5 * 60 * 1000,
  })
}
