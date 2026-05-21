# Quick Task 260521-9ze — Cookie-Token Auth Migration Summary

**Completed:** 2026-05-21
**Commits:**
- `094de47` — `feat(auth): replace JWT login with cookie-token bookmark model (backend)`
- `4508e8b` — `feat(auth): remove LoginPage, add AccessDeniedPage + token-bootstrap (frontend)`

---

## What Changed

### Auth model

Replaced the JWT/bcrypt password-login model with a bookmark-token cookie model:

- The operator holds a single long-lived URL: `https://seva-mining-smm.vercel.app/?token=<SEVA_DASHBOARD_TOKEN>`
- On first visit, `bootstrapTokenRedirect()` intercepts `?token=` before React mounts and calls `GET /auth/token-set?token=<value>&next=/`
- The backend validates the token with `secrets.compare_digest()`, sets an `HttpOnly; SameSite=Lax; Secure; Max-Age=31536000` cookie named `seva_auth_token`, then 302-redirects to `/`
- All subsequent requests include the cookie automatically (`credentials: 'include'`); no header, no localStorage
- If the cookie is missing or wrong, the backend returns 403 and the frontend redirects to `/access-denied`
- `/access-denied` shows a tenant-branded page (via `useCompanyBrand()`) with no login form, no inputs

### Backend changes

| File | Change |
|------|--------|
| `app/config.py` | Added `seva_dashboard_token: str` field (maps to `SEVA_DASHBOARD_TOKEN` env var via pydantic-settings case-insensitive binding) |
| `app/dependencies.py` | Replaced `HTTPBearer`/`get_current_user` with `get_current_session_token(request)` — reads `seva_auth_token` cookie, validates with `secrets.compare_digest()` |
| `app/routers/auth.py` | Deleted `POST /auth/login`; added `GET /auth/token-set` (validates token, sets cookie, 302-redirects) |
| `app/auth.py` | Emptied (kept as stub for import stability) |
| `app/schemas/auth.py` | Deleted (`LoginRequest`/`TokenResponse` no longer needed) |
| All 12 router files | Renamed `get_current_user` → `get_current_session_token` in `Depends()` calls |
| `tests/conftest.py` | Auth fixture updated: sets cookie instead of Bearer header |
| `tests/test_auth.py` | 9 new cookie-token tests covering: valid/invalid/missing token, cookie attributes, redirect behaviour, timing-safe comparison |
| All other test files | `Authorization: Bearer` headers → `cookies={"seva_auth_token": ...}` |

`get_current_company` (Phase 9 D-04) is **unchanged**.

### Frontend changes

| File | Change |
|------|--------|
| `src/lib/bootstrap.ts` | NEW — `bootstrapTokenRedirect()` function (extracted for testability) |
| `src/pages/AccessDeniedPage.tsx` | NEW — tenant-branded access-denied page (no form, no inputs) |
| `src/main.tsx` | Calls `bootstrapTokenRedirect()` before `ReactDOM.createRoot`; re-exports function |
| `src/api/client.ts` | Rewritten: `credentials: 'include'`, 403 → `/access-denied`, no Bearer/localStorage |
| `src/api/auth.ts` | Rewritten: `setTokenFromUrl()` builds `/auth/token-set` URL |
| `src/App.tsx` | Removed `ProtectedRoute` wrapper; replaced `/login` with `/access-denied` |
| `src/components/layout/ProtectedRoute.tsx` | DELETED |
| `src/pages/LoginPage.tsx` | DELETED |
| `src/stores/slices/authSlice.ts` | Gutted (empty — cookie is the session) |
| `src/components/layout/AppHeader.tsx` | Removed logout button |
| `src/components/layout/Sidebar.tsx` | Removed logout button |
| `src/api/calendar.ts` | `deleteCalendarItem`: removed Bearer header, added `credentials: 'include'` |
| `src/api/types.ts` | Removed `LoginRequest`, `TokenResponse` |
| `src/mocks/handlers.ts` | Removed `POST /auth/login` handler |

### Tests

All tests green:
- **Backend:** 187 tests pass (`pytest`)
- **Frontend:** 205 tests pass / 35 test files (`vitest --run`)

---

## Railway Setup — Required One-Time Steps

### 1. Generate a fresh token

A fresh token was generated for this migration:

```
VL8_a-YAFywyMNpATMkq3FQyGJP1kixMrvo4FU-Ipy2Gi4MKb-FOZJ2Ve5IbcOCq
```

> **Security note:** This token appears in this summary file in the repo. Generate a replacement using `python3 -c "import secrets; print(secrets.token_urlsafe(48))"` and use that value instead. Do not use the value printed above if this file is in version control.

To generate a fresh replacement:
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

### 2. Set env var in Railway (API service)

In the Railway dashboard → seva-mining API service → Variables:

```
SEVA_DASHBOARD_TOKEN=<your-generated-token>
```

Remove `JWT_SECRET` and `DASHBOARD_PASSWORD` after verifying the new auth works (they are kept as optional fields in `config.py` to avoid a boot crash if they linger, but they are no longer used).

### 3. Remove `JWT_SECRET` and `DASHBOARD_PASSWORD` from Railway (after verification)

Once you have confirmed the cookie-token flow works end-to-end:
- Delete `JWT_SECRET` from Railway env
- Delete `DASHBOARD_PASSWORD` from Railway env

### 4. Create the bookmark URL

```
https://seva-mining-smm.vercel.app/?token=<your-SEVA_DASHBOARD_TOKEN>
```

Save this as a browser bookmark. On first visit it will redirect to the clean dashboard URL and set the HttpOnly cookie. Subsequent visits (to the clean URL, without `?token=`) will use the cookie directly.

The cookie has `Max-Age=31536000` (1 year). To reset access, change `SEVA_DASHBOARD_TOKEN` in Railway — the old cookie becomes invalid immediately.

### 5. Verify the Juno tenant

```
https://seva-mining-smm.vercel.app/juno?token=<your-SEVA_DASHBOARD_TOKEN>
```

This should redirect to `/juno` clean URL. The `/access-denied` page at `/juno/access-denied` will show the "Juno Industries" wordmark (per `useCompanyBrand()` / Phase 13 D-04).

---

## Security Properties

| Property | Value |
|----------|-------|
| Cookie name | `seva_auth_token` |
| HttpOnly | Yes (not readable by JS) |
| SameSite | Lax |
| Secure | Yes (HTTPS only in production) |
| Max-Age | 31536000 (1 year) |
| Token comparison | `secrets.compare_digest()` (timing-safe) |
| Token entropy | 48 bytes = 384 bits via `secrets.token_urlsafe` |
| Auth surface | Single env var + single cookie name |
| Login page | None (no credential-entry UI) |

---

## Deviations from Plan

**[Rule 1 - Bug] Pydantic field name for SEVA_DASHBOARD_TOKEN**
- Found during Task 1 (backend)
- Issue: Initially used `dashboard_token` as the Pydantic field name, which maps to env var `DASHBOARD_TOKEN`, not `SEVA_DASHBOARD_TOKEN`
- Fix: Renamed to `seva_dashboard_token` — pydantic-settings case-insensitive binding maps this to `SEVA_DASHBOARD_TOKEN`
- Files: `backend/app/config.py`

**[Rule 1 - Bug] Cookie attribute assertion case-sensitivity in tests**
- Found during Task 1 testing
- Issue: `"SameSite=lax" in set_cookie.lower()` was comparing mixed case against lowercased string
- Fix: Changed all assertions to all-lowercase: `"samesite=lax" in set_cookie.lower()`
- Files: `backend/tests/test_auth.py`

**[Rule 1 - Bug] Protected route test failing due to missing DB table**
- Found during Task 1 testing
- Issue: `test_protected_route_with_valid_cookie` passed auth but failed when queue route tried to query SQLite (no `draft_items` table in conftest's empty DB)
- Fix: Used `unittest.mock.patch` to mock `get_db` dependency and return early
- Files: `backend/tests/test_auth.py`

**[Rule 3 - Blocking] bootstrapTokenRedirect test triggered ReactDOM.createRoot**
- Found during Task 2 frontend testing
- Issue: Importing `main.tsx` in tests executed top-level `if (!bootstrapTokenRedirect()) { ReactDOM.createRoot(...) }` — no `#root` DOM element in jsdom → crash
- Fix: Extracted `bootstrapTokenRedirect()` to `src/lib/bootstrap.ts`; `main.tsx` imports and re-exports it; test imports from `../lib/bootstrap`
- Files: `frontend/src/lib/bootstrap.ts`, `frontend/src/main.tsx`, `frontend/src/__tests__/main.bootstrap.test.ts`

**[Rule 1 - Bug] ruff lint: unused Depends import in dependencies.py**
- Found during Task 1 (ruff check)
- Fix: Removed `Depends` from `fastapi` import line in `app/dependencies.py`

**[Rule 1 - Bug] ruff lint: unsorted imports across multiple test files**
- Found during Task 1 (ruff check)
- Fix: `uv tool run ruff check . --fix` auto-sorted all affected test files
