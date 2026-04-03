import { apiFetch } from './client'
import type { DailyDigestResponse } from './types'

export async function getLatestDigest(): Promise<DailyDigestResponse> {
  return apiFetch<DailyDigestResponse>('/digests/latest')
}

export async function getDigestByDate(date: string): Promise<DailyDigestResponse> {
  return apiFetch<DailyDigestResponse>(`/digests/${date}`)
}
