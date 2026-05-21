/**
 * Auth slice — deprecated (quick-260521-9ze).
 *
 * Cookie-token auth model replaces JWT/localStorage auth.
 * The auth slice is now empty — no token, no isAuthenticated, no setToken.
 * Auth is handled transparently by the HttpOnly cookie set during
 * ?token= bootstrap. The backend returns 403 on missing/invalid cookie;
 * apiFetch redirects to /access-denied automatically.
 *
 * The AuthSlice interface and createAuthSlice factory remain exported
 * so the combined store type in index.ts does not break existing
 * component imports (e.g. Sidebar.tsx references) until a full cleanup.
 */

// eslint-disable-next-line @typescript-eslint/no-empty-object-type
export interface AuthSlice {}

export function createAuthSlice(
  _set: unknown,
): AuthSlice {
  return {}
}
