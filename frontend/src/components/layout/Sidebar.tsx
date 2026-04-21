import { NavLink, useNavigate } from 'react-router-dom'
import { FileText, Newspaper, Settings, LogOut } from 'lucide-react'
import { useAppStore } from '@/stores'
import { useQueueCounts } from '@/hooks/useQueueCounts'
import { CONTENT_AGENT_TABS } from '@/config/agentTabs'
import { cn } from '@/lib/utils'

export function Sidebar() {
  const navigate = useNavigate()
  const clearToken = useAppStore((s) => s.clearToken)
  const counts = useQueueCounts()

  function handleLogout() {
    clearToken()
    navigate('/login')
  }

  function countLabel(n: number, hasMore: boolean) {
    if (n === 0) return null
    return hasMore ? `${n}+` : String(n)
  }

  // 7 sub-agents post quick-260421-eoe (monolithic content_agent split).
  // Rendered in priority order from CONTENT_AGENT_TABS (the single source
  // of truth shared with the /agents/:slug route). Twitter purged in
  // quick-260420-sn9; Instagram purged in quick-260419-lvy.
  const agentItems = [...CONTENT_AGENT_TABS]
    .sort((a, b) => a.priority - b.priority)
    .map((tab) => {
      const entry = counts[tab.contentType]
      return {
        to: `/agents/${tab.slug}`,
        label: tab.label,
        icon: <FileText className="size-4" />,
        badge: countLabel(entry?.count ?? 0, entry?.hasMore ?? false),
      }
    })

  const bottomItems = [
    { to: '/digest', label: 'Digest', icon: <Newspaper className="size-4" /> },
    { to: '/settings', label: 'Settings', icon: <Settings className="size-4" /> },
  ]

  return (
    <aside className="w-[220px] min-h-screen flex flex-col border-r border-zinc-800 bg-zinc-900 py-6">
      {/* Brand */}
      <div className="px-5 mb-8 flex items-center gap-3">
        <div className="w-7 h-7 rounded-md bg-amber-500 flex items-center justify-center shrink-0">
          <span className="text-xs font-bold text-zinc-900">S</span>
        </div>
        <span className="text-sm font-semibold text-white">Seva Mining</span>
      </div>

      <nav className="flex-1 px-3 space-y-0.5">
        {/* Section label */}
        <p className="px-3 pb-1.5 text-[10px] font-semibold uppercase tracking-widest text-zinc-600">
          Agents
        </p>

        {agentItems.map(({ to, label, icon, badge }) => (
          <NavLink
            key={to}
            to={to}
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
            <span className="flex-1">{label}</span>
            {badge && (
              <span className="inline-flex items-center justify-center min-w-[20px] h-5 rounded-full bg-amber-500/20 text-amber-400 text-xs font-medium px-1.5">
                {badge}
              </span>
            )}
          </NavLink>
        ))}

        {/* Divider */}
        <div className="my-3 border-t border-zinc-800" />

        {bottomItems.map(({ to, label, icon }) => (
          <NavLink
            key={to}
            to={to}
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
