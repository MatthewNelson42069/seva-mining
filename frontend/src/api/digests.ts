import { apiFetch } from './client'
import type { DailyDigestResponse } from './types'

export interface NewsStory {
  headline: string
  source?: string | null
  time?: string | null
  url?: string | null
  score?: number | null
}

export async function getLatestDigest(): Promise<DailyDigestResponse> {
  return apiFetch<DailyDigestResponse>('/digests/latest')
}

export async function getDigestByDate(date: string): Promise<DailyDigestResponse> {
  return apiFetch<DailyDigestResponse>(`/digests/${date}`)
}

export async function getNewsFeed(hours = 24, limit = 15): Promise<NewsStory[]> {
  return apiFetch<NewsStory[]>(`/digests/news-feed?hours=${hours}&limit=${limit}`)
}
