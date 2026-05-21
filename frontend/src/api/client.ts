const BASE_URL = import.meta.env.VITE_API_URL ?? ''

/**
 * Authenticated API fetch — cookie-token model (quick-260521-9ze).
 *
 * Sends credentials: 'include' on every request so the browser
 * automatically includes the HttpOnly seva_auth_token cookie.
 * NO Authorization header, NO localStorage usage.
 *
 * On 403: redirects to /access-denied (cookie missing or invalid).
 * On other non-OK: throws an error with the status code.
 */
export async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  })
  if (res.status === 403) {
    window.location.href = '/access-denied'
    throw new Error('Access required')
  }
  if (!res.ok) throw new Error(`API error ${res.status}`)
  return res.json() as Promise<T>
}
