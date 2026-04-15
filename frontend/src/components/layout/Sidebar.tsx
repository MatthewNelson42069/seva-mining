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
    <aside className="w-[220px] min-h-screen flex flex-col border-r border-zinc-800 bg-zinc-900 py-6">
      {/* Brand */}
      <div className="px-5 mb-8 flex items-center gap-3">
        <div className="w-7 h-7 rounded-md bg-amber-500 flex items-center justify-center shrink-0">
          <span className="text-xs font-bold text-zinc-900">S</span>
        </div>
        <span className="text-sm font-semibold text-white">Seva Mining</span>
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
                  ? 'bg-amber-500/10 text-amber-400'
                  : 'text-zinc-400 hover:bg-white/5 hover:text-zinc-100'
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
          className="flex w-full items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium text-zinc-500 hover:bg-white/5 hover:text-zinc-300 transition-colors"
        >
          <LogOut className="size-4" />
          Log out
        </button>
      </div>
    </aside>
  )
}
