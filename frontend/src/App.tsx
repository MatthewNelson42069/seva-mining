import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { ProtectedRoute } from '@/components/layout/ProtectedRoute'
import { AppShell } from '@/components/layout/AppShell'
import { LoginPage } from '@/pages/LoginPage'
import { PerAgentQueuePage } from '@/pages/PerAgentQueuePage'
import { DigestPage } from '@/pages/DigestPage'
import { SettingsPage } from '@/pages/SettingsPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<ProtectedRoute />}>
          <Route element={<AppShell />}>
            {/* Redirect root to Breaking News (priority-1 sub-agent, quick-260421-eoe) */}
            <Route path="/" element={<Navigate to="/agents/breaking-news" replace />} />

            {/* Per-sub-agent queues via single dynamic route (quick-260421-eoe).
                CONTENT_AGENT_TABS drives Sidebar + PerAgentQueuePage slug lookup.
                Unknown slug → redirect back to /agents/breaking-news. */}
            <Route path="/agents/:slug" element={<PerAgentQueuePage />} />

            {/* Other pages. */}
            <Route path="/digest" element={<DigestPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Route>
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
