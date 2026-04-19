import { apiFetch } from './client'
import type {
  ContentBundleResponse,
  ContentBundleDetailResponse,
  RerenderResponse,
} from './types'

export async function getTodayContent(): Promise<ContentBundleResponse> {
  return apiFetch<ContentBundleResponse>('/content/today')
}

export async function getContentBundle(
  id: string,
): Promise<ContentBundleDetailResponse> {
  return apiFetch<ContentBundleDetailResponse>(`/content-bundles/${id}`)
}

export async function rerenderContentBundle(
  id: string,
): Promise<RerenderResponse> {
  return apiFetch<RerenderResponse>(`/content-bundles/${id}/rerender`, {
    method: 'POST',
  })
}
