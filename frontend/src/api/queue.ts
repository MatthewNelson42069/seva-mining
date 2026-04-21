import { apiFetch } from './client'
import type { DraftItemResponse, QueueListResponse, RejectionCategory } from './types'

export async function getQueue(params: {
  platform?: string; status?: string; contentType?: string; cursor?: string; limit?: number
}): Promise<QueueListResponse> {
  const sp = new URLSearchParams()
  if (params.platform) sp.set('platform', params.platform)
  if (params.status) sp.set('status', params.status)
  // quick-260421-eoe: /queue?content_type= filters drafts via the
  // content_bundles JSONB link. Value must be the DB-native content_type
  // (e.g. "thread", "breaking_news") — not the URL slug.
  if (params.contentType) sp.set('content_type', params.contentType)
  if (params.cursor) sp.set('cursor', params.cursor)
  if (params.limit) sp.set('limit', String(params.limit))
  return apiFetch<QueueListResponse>(`/queue?${sp}`)
}

export async function approveItem(id: string, editedText?: string): Promise<DraftItemResponse> {
  return apiFetch<DraftItemResponse>(`/items/${id}/approve`, {
    method: 'PATCH',
    body: editedText ? JSON.stringify({ edited_text: editedText }) : undefined,
  })
}

export async function rejectItem(id: string, category: RejectionCategory, notes?: string): Promise<DraftItemResponse> {
  return apiFetch<DraftItemResponse>(`/items/${id}/reject`, {
    method: 'PATCH',
    body: JSON.stringify({ category, notes }),
  })
}
