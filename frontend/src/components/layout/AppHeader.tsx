import { useNavigate } from 'react-router-dom'
import { useAppStore } from '@/stores'
import { CompanySwitcher } from './CompanySwitcher'

export function AppHeader() {
  const navigate = useNavigate()
  const clearToken = useAppStore((s) => s.clearToken)

  function handleLogout() {
    clearToken()
    navigate('/login')
  }

  return (
    <header className="border-b border-zinc-800 bg-zinc-900 sticky top-0 z-10">
      <div className="max-w-[720px] mx-auto px-4 py-3 flex items-center justify-between">
        {/* Brand mark */}
        <div className="flex items-center gap-3">
          <div className="w-7 h-7 rounded-md bg-amber-500 flex items-center justify-center shrink-0">
            <span className="text-xs font-bold text-zinc-900">S</span>
          </div>
          <span className="text-sm font-semibold text-white">Seva Mining</span>
        </div>

        {/* v3.0 freeze-lift (Phase 9) — see 09-CONTEXT.md D-02 */}
        <CompanySwitcher />

        {/* Logout */}
        <button
          onClick={handleLogout}
          className="text-sm text-zinc-400 hover:text-zinc-100 transition-colors"
        >
          Log out
        </button>
      </div>
    </header>
  )
}
