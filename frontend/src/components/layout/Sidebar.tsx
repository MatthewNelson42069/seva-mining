import { NavLink, useNavigate } from 'react-router-dom'
import { LayoutList, Newspaper, FileText, Settings, LogOut } from 'lucide-react'
import { useAppStore } from '@/stores'
import { cn } from '@/lib/utils'

interface NavItem {
  to: string
  label: string
  icon: React.ReactNode
}

const navItems: NavItem[] = [
  { to: '/', label: 'Queue', icon: <LayoutList className="size-4" /> },
  { to: '/digest', label: 'Digest', icon: <Newspaper className="size-4" /> },
  { to: '/content', label: 'Content Review', icon: <FileText className="size-4" /> },
  { to: '/settings', label: 'Settings', icon: <Settings className="size-4" /> },
]

export function Sidebar() {
  const navigate = useNavigate()
  const clearToken = useAppStore((s) => s.clearToken)

  function handleLogout() {
    clearToken()
    navigate('/login')
  }

  return (
    <aside className="w-[220px] min-h-screen flex flex-col border-r border-gray-100 bg-white py-6">
      {/* Brand */}
      <div className="px-5 mb-8">
        <span className="text-sm font-semibold text-gray-900">Seva Mining</span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 space-y-0.5">
        {navItems.map(({ to, label, icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                isActive
                  ? 'bg-blue-50 text-blue-700'
                  : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
              )
            }
          >
            {icon}
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Footer: logout */}
      <div className="px-3 mt-4">
        <button
          onClick={handleLogout}
          className="flex w-full items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium text-gray-500 hover:bg-gray-50 hover:text-gray-900 transition-colors"
        >
          <LogOut className="size-4" />
          Log out
        </button>
      </div>
    </aside>
  )
}
