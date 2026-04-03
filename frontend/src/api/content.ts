import { apiFetch } from './client'
import type { ContentBundleResponse } from './types'

export async function getTodayContent(): Promise<ContentBundleResponse> {
  return apiFetch<ContentBundleResponse>('/content/today')
}
