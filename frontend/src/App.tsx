import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { ProtectedRoute } from '@/components/layout/ProtectedRoute'
import { AppShell } from '@/components/layout/AppShell'
import { TabbedDashboard } from '@/components/layout/TabbedDashboard'
import { LoginPage } from '@/pages/LoginPage'
import { DigestPage } from '@/pages/DigestPage'
import { SettingsPage } from '@/pages/SettingsPage'
import { SummaryFeedPage } from '@/pages/SummaryFeedPage'
import ContentCalendarPage from '@/pages/ContentCalendarPage'
import WeeklyViralSweeperPage from '@/pages/WeeklyViralSweeperPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<ProtectedRoute />}>
          <Route element={<AppShell />}>

            {/* v2.1 3-tab surface — TabbedDashboard renders TabNav + Outlet */}
            <Route element={<TabbedDashboard />}>
              <Route index element={<SummaryFeedPage />} />
              <Route path="calendar" element={<ContentCalendarPage />} />
              <Route path="viral" element={<WeeklyViralSweeperPage />} />
            </Route>

            {/* v2.0 bookmark-grace redirects — preserved INSIDE ProtectedRoute (P4 prevention) */}
            <Route path="/queue" element={<Navigate to="/" replace />} />
            <Route path="/agents/:slug" element={<Navigate to="/" replace />} />

            {/* v2.0 retained surfaces — NO tabs here (outside TabbedDashboard) */}
            <Route path="/digest" element={<DigestPage />} />
            <Route path="/settings" element={<SettingsPage />} />

          </Route>
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
