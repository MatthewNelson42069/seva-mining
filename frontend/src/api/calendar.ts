import { apiFetch } from './client'
import type { CompanyId } from './queryKeys'

/**
 * v2.1 Phase 6 — Content Calendar API surface (v3.0 multi-tenant refactor).
 *
 * Pitfall P1 defense: all date fields are `string` in 'YYYY-MM-DD' format.
 * Never construct `Date` objects from these — TZ-naive string-in / string-out
 * is the contract from POST through GET back to the day-cell render.
 *
 * Backend contract reference: backend/app/schemas/calendar.py (Plan 06-01).
 * v3.0 (Phase 9): URLs are tenant-prefixed: /api/{company}/calendar.
 */

/** Single calendar item as returned by GET /calendar and POST /calendar. */
export interface CalendarItem {
  id: string            // UUID
  date: string          // 'YYYY-MM-DD'
  body: string | null
  created_at: string    // ISO datetime
  updated_at: string    // ISO datetime
}

/** Wrapper response for GET /api/{company}/calendar?start=&end=. */
export interface CalendarRangeResponse {
  items: CalendarItem[]
  total: number
}

/** Request body for POST /api/{company}/calendar. */
export interface CalendarItemCreate {
  date: string          // 'YYYY-MM-DD'
  body: string          // non-empty after .trim() — enforced by backend
}

/** Request body for PATCH /api/{company}/calendar/{id}. */
export interface CalendarItemUpdate {
  body: string          // non-empty after .trim()
}

/** GET /api/{company}/calendar?start=YYYY-MM-DD&end=YYYY-MM-DD — date ASC order. */
export async function getCalendar(
  companyId: CompanyId,
  start: string,
  end: string,
): Promise<CalendarRangeResponse> {
  const sp = new URLSearchParams({ start, end })
  return apiFetch<CalendarRangeResponse>(`/api/${companyId}/calendar?${sp}`)
}

/** POST /api/{company}/calendar — creates a new item; 409 if a row already exists for that date. */
export async function createCalendarItem(
  companyId: CompanyId,
  payload: CalendarItemCreate,
): Promise<CalendarItem> {
  return apiFetch<CalendarItem>(`/api/${companyId}/calendar`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

/** PATCH /api/{company}/calendar/{id} — updates body text only. */
export async function updateCalendarItem(
  companyId: CompanyId,
  id: string,
  payload: CalendarItemUpdate,
): Promise<CalendarItem> {
  return apiFetch<CalendarItem>(`/api/${companyId}/calendar/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

/** DELETE /api/{company}/calendar/{id} — returns 204; resolves to void on success. */
export async function deleteCalendarItem(
  companyId: CompanyId,
  id: string,
): Promise<void> {
  // apiFetch always parses res.json(); but the 204 No Content response has
  // no body. We use a thin local fetch here to handle that special case.
  const token = localStorage.getItem('access_token')
  const baseUrl = import.meta.env.VITE_API_URL ?? ''
  const res = await fetch(`${baseUrl}/api/${companyId}/calendar/${id}`, {
    method: 'DELETE',
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  })
  if (res.status === 401) {
    localStorage.removeItem('access_token')
    window.location.href = '/login'
    throw new Error('Unauthorized')
  }
  if (!res.ok) throw new Error(`API error ${res.status}`)
  // 204 No Content — nothing to parse
}
