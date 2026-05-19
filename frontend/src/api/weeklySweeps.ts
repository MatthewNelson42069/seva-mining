import { useQuery } from '@tanstack/react-query'

import { apiFetch } from './client'
import { queryKeys, type CompanyId } from './queryKeys'

/** One weekly sweep card returned by GET /api/{company}/weekly-sweeps.
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

/** Fetch up to `limit` weekly sweeps (newest first) for the given tenant. */
export async function getWeeklySweeps(
  companyId: CompanyId,
  limit = 12,
): Promise<WeeklySweepFeedResponse> {
  return apiFetch<WeeklySweepFeedResponse>(
    `/api/${companyId}/weekly-sweeps?limit=${limit}`,
  )
}

/** TanStack Query hook for the weekly-sweeps feed.
 *  Refetch behavior mirrors useSummaries (no aggressive polling — sweeper fires
 *  weekly so 5-min refetch interval is more than enough to catch the Sunday fire).
 *  companyId is part of the query key (TENANT-09, D-08).
 */
export function useWeeklySweeps(companyId: CompanyId, limit = 12) {
  return useQuery({
    queryKey: queryKeys.weeklySweeps(companyId, limit),
    queryFn: () => getWeeklySweeps(companyId, limit),
    refetchInterval: 5 * 60 * 1000,
    refetchOnWindowFocus: false,
    staleTime: 5 * 60 * 1000,
  })
}
