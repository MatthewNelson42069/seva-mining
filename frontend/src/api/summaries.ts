import { useQuery } from '@tanstack/react-query'
import { apiFetch } from './client'
import { queryKeys, type CompanyId } from './queryKeys'

/** One summary card returned by GET /api/{company}/summaries.
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

/** Fetch up to `limit` summaries (newest first) for the given tenant. */
export async function getSummaries(
  companyId: CompanyId,
  limit = 60,
): Promise<SummaryFeedResponse> {
  return apiFetch<SummaryFeedResponse>(`/api/${companyId}/summaries?limit=${limit}`)
}

/** TanStack Query hook with locked refetch behaviour:
 *  - refetchInterval: 5 min (FEED-06 — per-fire freshness without manual reload)
 *  - refetchOnWindowFocus: false (locked CONTEXT decision — read-only intelligence,
 *    no need for hyperactive freshness)
 *  - companyId is part of the query key via queryKeys.summaries (TENANT-09, D-08).
 */
export function useSummaries(companyId: CompanyId, limit = 60) {
  return useQuery({
    queryKey: queryKeys.summaries(companyId, limit),
    queryFn: () => getSummaries(companyId, limit),
    refetchInterval: 5 * 60 * 1000,  // 5 minutes — FEED-06
    refetchOnWindowFocus: false,     // locked CONTEXT decision
    staleTime: 5 * 60 * 1000,
  })
}
