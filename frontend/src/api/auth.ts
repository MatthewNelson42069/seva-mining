import { apiFetch } from './client'
import type { TokenResponse } from './types'

export async function login(password: string): Promise<TokenResponse> {
  return apiFetch<TokenResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ password }),
  })
}
