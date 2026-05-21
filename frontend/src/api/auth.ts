const BASE_URL = import.meta.env.VITE_API_URL ?? ''

/**
 * Build the backend token-set URL — cookie-token auth (quick-260521-9ze).
 *
 * Usage: window.location.replace(setTokenFromUrl(token, next))
 *
 * The backend GET /auth/token-set route will:
 *   1. Validate the token against SEVA_DASHBOARD_TOKEN env var
 *   2. Set the seva_auth_token HttpOnly cookie (1 year)
 *   3. 302-redirect to `next`
 *
 * This function only BUILDS the URL — it does not navigate. The caller
 * (main.tsx bootstrap) calls window.location.replace so the token is
 * never visible in browser history after the first visit.
 */
export function setTokenFromUrl(token: string, next: string): string {
  return `${BASE_URL}/auth/token-set?token=${encodeURIComponent(token)}&next=${encodeURIComponent(next)}`
}
