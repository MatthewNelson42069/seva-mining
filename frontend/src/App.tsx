import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { ProtectedRoute } from '@/components/layout/ProtectedRoute'
import { AppShell } from '@/components/layout/AppShell'
import { LoginPage } from '@/pages/LoginPage'
import { PlatformQueuePage } from '@/pages/PlatformQueuePage'
import { DigestPage } from '@/pages/DigestPage'
import { ContentPage } from '@/pages/ContentPage'
import { SettingsPage } from '@/pages/SettingsPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<ProtectedRoute />}>
          <Route element={<AppShell />}>
            {/* Redirect root to Twitter queue */}
            <Route path="/" element={<Navigate to="/twitter" replace />} />

            {/* Platform queues */}
            <Route path="/twitter" element={<PlatformQueuePage platform="twitter" />} />
            <Route path="/content" element={<PlatformQueuePage platform="content" />} />

            {/* Other pages */}
            <Route path="/digest" element={<DigestPage />} />
            <Route path="/content-review" element={<ContentPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Route>
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
