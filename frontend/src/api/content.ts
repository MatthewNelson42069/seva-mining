import { apiFetch } from './client'
import type {
  ContentBundleResponse,
  ContentBundleDetailResponse,
} from './types'

export async function getTodayContent(): Promise<ContentBundleResponse> {
  return apiFetch<ContentBundleResponse>('/content/today')
}

export async function getContentBundle(
  id: string,
): Promise<ContentBundleDetailResponse> {
  return apiFetch<ContentBundleDetailResponse>(`/content-bundles/${id}`)
}
