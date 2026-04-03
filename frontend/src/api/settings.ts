import { apiFetch } from './client'
import type {
  WatchlistResponse, WatchlistCreate, WatchlistUpdate,
  KeywordResponse, KeywordCreate, KeywordUpdate,
  AgentRunResponse, ConfigEntry, QuotaResponse,
} from './types'

export async function getWatchlists(platform?: string): Promise<WatchlistResponse[]> {
  const sp = new URLSearchParams()
  if (platform) sp.set('platform', platform)
  return apiFetch<WatchlistResponse[]>(`/watchlists?${sp}`)
}

export async function createWatchlist(body: WatchlistCreate): Promise<WatchlistResponse> {
  return apiFetch<WatchlistResponse>('/watchlists', {
    method: 'POST', body: JSON.stringify(body),
  })
}

export async function updateWatchlist(id: string, body: WatchlistUpdate): Promise<WatchlistResponse> {
  return apiFetch<WatchlistResponse>(`/watchlists/${id}`, {
    method: 'PATCH', body: JSON.stringify(body),
  })
}

export async function deleteWatchlist(id: string): Promise<void> {
  await apiFetch<void>(`/watchlists/${id}`, { method: 'DELETE' })
}

export async function getKeywords(platform?: string, active?: boolean): Promise<KeywordResponse[]> {
  const sp = new URLSearchParams()
  if (platform) sp.set('platform', platform)
  if (active !== undefined) sp.set('active', String(active))
  return apiFetch<KeywordResponse[]>(`/keywords?${sp}`)
}

export async function createKeyword(body: KeywordCreate): Promise<KeywordResponse> {
  return apiFetch<KeywordResponse>('/keywords', {
    method: 'POST', body: JSON.stringify(body),
  })
}

export async function updateKeyword(id: string, body: KeywordUpdate): Promise<KeywordResponse> {
  return apiFetch<KeywordResponse>(`/keywords/${id}`, {
    method: 'PATCH', body: JSON.stringify(body),
  })
}

export async function deleteKeyword(id: string): Promise<void> {
  await apiFetch<void>(`/keywords/${id}`, { method: 'DELETE' })
}

export async function getAgentRuns(agentName?: string, days?: number): Promise<AgentRunResponse[]> {
  const sp = new URLSearchParams()
  if (agentName) sp.set('agent_name', agentName)
  if (days) sp.set('days', String(days))
  return apiFetch<AgentRunResponse[]>(`/agent-runs?${sp}`)
}

export async function getConfig(): Promise<ConfigEntry[]> {
  return apiFetch<ConfigEntry[]>('/config')
}

export async function updateConfig(key: string, value: string): Promise<ConfigEntry> {
  return apiFetch<ConfigEntry>(`/config/${key}`, {
    method: 'PATCH', body: JSON.stringify({ value }),
  })
}

export async function getQuota(): Promise<QuotaResponse> {
  return apiFetch<QuotaResponse>('/config/quota')
}
