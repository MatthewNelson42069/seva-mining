import { NavLink } from 'react-router-dom'

const tabs = [
  { to: '/',         label: 'News Funnel' },
  { to: '/calendar', label: 'Content Calendar' },
  { to: '/viral',    label: 'Weekly Viral' },
] as const

export function TabNav() {
  return (
    <nav className="border-b border-zinc-800 bg-zinc-900">
      <div className="max-w-[720px] mx-auto px-4 flex gap-1">
        {tabs.map(({ to, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `px-3 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ` +
              (isActive
                ? 'border-amber-500 text-white'
                : 'border-transparent text-zinc-400 hover:text-zinc-100')
            }
          >
            {label}
          </NavLink>
        ))}
      </div>
    </nav>
  )
}
