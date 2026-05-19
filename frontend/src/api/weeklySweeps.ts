import { useQuery } from '@tanstack/react-query'

import { apiFetch } from './client'

/** One weekly sweep card returned by GET /weekly-sweeps.
 *  Mirrors backend/app/schemas/weekly_sweep.py::WeeklySweepCard.
 *
 *  Note: column is named `reddit_top_md` in the backend schema for
 *  Phase 5 migration compatibility, but stores X posts under the
 *  07-CONTEXT.md D-03 pivot. Frontend treats it as "top X posts markdown".
 */
export interface WeeklySweepCard {
  id: string
  generated_at: string // ISO datetime
  week_start: string // YYYY-MM-DD
  week_end: string // YYYY-MM-DD
  reddit_top_md: string | null // stores X posts markdown (pivot)
  story_virality_md: string | null
  content_angles_md: string | null
  status: 'completed' | 'failed' | 'partial'
  error_text: string | null
  agent_run_id: string | null
}

export interface WeeklySweepFeedResponse {
  sweeps: WeeklySweepCard[]
  total: number
}

/** Fetch up to `limit` weekly sweeps (newest first). */
export async function getWeeklySweeps(limit = 12): Promise<WeeklySweepFeedResponse> {
  return apiFetch<WeeklySweepFeedResponse>(`/weekly-sweeps?limit=${limit}`)
}

/** TanStack Query hook for the weekly-sweeps feed.
 *  Refetch behavior mirrors useSummaries (no aggressive polling — sweeper fires
 *  weekly so 5-min refetch interval is more than enough to catch the Sunday fire).
 */
export function useWeeklySweeps(limit = 12) {
  return useQuery({
    queryKey: ['weekly-sweeps', limit],
    queryFn: () => getWeeklySweeps(limit),
    refetchInterval: 5 * 60 * 1000,
    refetchOnWindowFocus: false,
    staleTime: 5 * 60 * 1000,
  })
}
