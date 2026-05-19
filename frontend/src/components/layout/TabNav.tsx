import { NavLink, useParams } from 'react-router-dom'

/**
 * v2.1 Phase 5 / v3.0 Phase 9 — TabNav (3 tabs: News Funnel / Calendar / Viral).
 *
 * Tab `to` hrefs are tenant-prefixed in v3.0: `/seva/`, `/seva/calendar`,
 * `/seva/viral` (or `/juno/...`). The `:company` slug is read from
 * useParams — it's narrowed upstream by <CompanyScopedRoute>.
 */
export function TabNav() {
  const { company } = useParams<{ company: string }>()
  const tabs = [
    { to: `/${company}`,          end: true,  label: 'News Funnel' },
    { to: `/${company}/calendar`, end: false, label: 'Content Calendar' },
    { to: `/${company}/viral`,    end: false, label: 'Weekly Viral' },
  ] as const

  return (
    <nav className="border-b border-zinc-800 bg-zinc-900">
      <div className="max-w-[720px] mx-auto px-4 flex gap-1">
        {tabs.map(({ to, end, label }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
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
