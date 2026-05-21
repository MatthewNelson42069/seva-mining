import { setTokenFromUrl } from '@/api/auth'

/**
 * Token bootstrap — cookie-token auth model (quick-260521-9ze).
 *
 * If the URL contains ?token=X, hand off to the backend BEFORE React renders.
 * The backend validates the token, sets the HttpOnly cookie, and 302-redirects
 * to the clean URL (pathname only — no ?token= visible after first visit).
 *
 * This MUST run before React renders so the operator never sees the token
 * in the address bar. Exported for unit testing.
 *
 * Returns true if a redirect was triggered (caller should NOT mount React).
 * Returns false if no token in URL (normal boot).
 */
export function bootstrapTokenRedirect(): boolean {
  const params = new URLSearchParams(window.location.search)
  const token = params.get('token')
  if (token) {
    const next = window.location.pathname // pathname only — strip query string
    window.location.replace(setTokenFromUrl(token, next))
    return true
  }
  return false
}
