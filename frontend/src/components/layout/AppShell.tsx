import { Outlet } from 'react-router-dom'
import { AppHeader } from './AppHeader'

export function AppShell() {
  return (
    <div className="min-h-screen bg-background flex flex-col">
      <AppHeader />

      {/* Main content area */}
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}
