import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { ProtectedRoute } from '@/components/layout/ProtectedRoute'
import { AppShell } from '@/components/layout/AppShell'
import { LoginPage } from '@/pages/LoginPage'
import { DigestPage } from '@/pages/DigestPage'
import { SettingsPage } from '@/pages/SettingsPage'
import { SummaryFeedPage } from '@/pages/SummaryFeedPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<ProtectedRoute />}>
          <Route element={<AppShell />}>
            {/* Phase 1, Plan 06 — v2.0 daily summary feed at root (FEED-01) */}
            <Route path="/" element={<SummaryFeedPage />} />

            {/* Bookmark-grace redirects for retired v1.0 routes (FEED-04) */}
            <Route path="/queue" element={<Navigate to="/" replace />} />
            <Route path="/agents/:slug" element={<Navigate to="/" replace />} />

            {/* Retained v1.0 surfaces (out of scope for v2.0 retirement) */}
            <Route path="/digest" element={<DigestPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Route>
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
