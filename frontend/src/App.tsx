import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useMemo } from 'react'
import { AppShell } from '@/components/layout/AppShell'
import { TabbedDashboard } from '@/components/layout/TabbedDashboard'
import { CompanyScopedRoute } from '@/components/layout/CompanyScopedRoute'
import { AccessDeniedPage } from '@/pages/AccessDeniedPage'
import { DigestPage } from '@/pages/DigestPage'
import { SettingsPage } from '@/pages/SettingsPage'
import { SummaryFeedPage } from '@/pages/SummaryFeedPage'
import ContentCalendarPage from '@/pages/ContentCalendarPage'
import WeeklyViralSweeperPage from '@/pages/WeeklyViralSweeperPage'
import { CompanyBrandEffect } from '@/components/layout/CompanyBrandEffect'
import { BareRootRedirect } from '@/components/layout/BareRootRedirect'

/**
 * v3.0 Phase 9 — `AppRoutes` is the route tree extracted from App so tests
 * can mount it inside a <MemoryRouter>. App still owns the <BrowserRouter>
 * for production. (See frontend/src/__tests__/App.test.tsx for mounting
 * pattern.)
 *
 * Includes its own <QueryClientProvider> so tests don't have to set one up.
 * In production main.tsx ALSO wraps App in a QueryClientProvider — TanStack
 * Query allows nested providers; the innermost wins, which is fine here.
 *
 * Route structure (per CONTEXT D-04, D-05, D-06; auth updated quick-260521-9ze):
 *   - /access-denied               — shown when cookie missing/invalid
 *   - /                            — bookmark grace → /seva (D-05)
 *   - /calendar, /viral            — bookmark grace → /seva/calendar etc. (D-06)
 *   - /queue, /agents/:slug        — legacy v2.0 grace → /seva (D-06)
 *   - /digest, /settings           — non-tenanted (apiFetch 403 → /access-denied)
 *   - /:company/                   — tenant-scoped 3-tab surface
 *   - /:company/calendar           —
 *   - /:company/viral              —
 *
 * Auth model: cookie-based (quick-260521-9ze). No ProtectedRoute needed —
 * apiFetch handles 403 → redirect to /access-denied automatically.
 */
export function AppRoutes() {
  // useMemo so each AppRoutes mount (e.g. multiple tests in one file) gets
  // an isolated client without re-creating per render.
  const queryClient = useMemo(() => new QueryClient(), [])
  return (
    <QueryClientProvider client={queryClient}>
      <Routes>
        <Route path="/access-denied" element={<AccessDeniedPage />} />

        {/* Bookmark grace redirects (D-05, D-06) */}
        <Route index element={<BareRootRedirect />} />
        <Route path="/calendar" element={<Navigate to="/seva/calendar" replace />} />
        <Route path="/viral" element={<Navigate to="/seva/viral" replace />} />
        <Route path="/queue" element={<Navigate to="/seva" replace />} />
        <Route path="/agents/:slug" element={<Navigate to="/seva" replace />} />

        <Route element={<AppShell />}>

          {/* v3.0 tenant-scoped 3-tab surface (TENANT-05) */}
          <Route path=":company" element={<><CompanyBrandEffect /><CompanyScopedRoute /></>}>
            <Route element={<TabbedDashboard />}>
              <Route index element={<SummaryFeedPage />} />
              <Route path="calendar" element={<ContentCalendarPage />} />
              <Route path="viral" element={<WeeklyViralSweeperPage />} />
            </Route>
          </Route>

          {/* Non-tenanted retained surfaces (D-06): stay at root */}
          <Route path="/digest" element={<DigestPage />} />
          <Route path="/settings" element={<SettingsPage />} />

        </Route>
      </Routes>
    </QueryClientProvider>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  )
}
