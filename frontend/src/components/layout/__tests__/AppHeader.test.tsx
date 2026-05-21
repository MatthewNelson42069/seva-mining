import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import { AppHeader } from '../AppHeader'

// Mock useAppStore — AppHeader no longer uses any auth selectors after
// cookie-token migration (quick-260521-9ze). Mock with an empty store
// to satisfy any remaining imports via useCompanyBrand's Zustand path.
vi.mock('@/stores', () => ({
  useAppStore: (selector: (state: { lastVisitedCompany: string | null }) => unknown) =>
    selector({ lastVisitedCompany: null }),
}))

function renderHeader() {
  // v3.0 Phase 9 — AppHeader now embeds <CompanySwitcher /> which calls
  // useQueryClient + useParams. Wrap in a QueryClientProvider AND mount
  // inside a /:company route so useParams resolves to a valid tenant.
  const queryClient = new QueryClient()
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/seva']}>
        <Routes>
          <Route path=":company/*" element={<AppHeader />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

// Phase 13 (BRAND-01, BRAND-03) — Juno-default helper. Mirrors renderHeader()
// exactly except `initialEntries={['/juno']}` — useCompanyBrand() then
// resolves to companyBrandConfig.juno via the URL useParams path of its
// fallback chain (Zustand mock returns undefined → URL wins).
function renderHeaderJuno() {
  const queryClient = new QueryClient()
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/juno']}>
        <Routes>
          <Route path=":company/*" element={<AppHeader />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('AppHeader', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the "Seva Mining" wordmark text', () => {
    renderHeader()
    expect(screen.getByText('Seva Mining')).toBeInTheDocument()
  })

  it('renders the amber "S" logo mark', () => {
    renderHeader()
    expect(screen.getByText('S')).toBeInTheDocument()
  })

  it('does NOT render a "Log out" button (cookie-token auth — quick-260521-9ze)', () => {
    renderHeader()
    expect(screen.queryByRole('button', { name: /log out/i })).not.toBeInTheDocument()
  })

  // Phase 13 (BRAND-01, BRAND-03) — Juno-default scenario.
  // Tests above are the byte-identical Seva-default contract per D-09.
  // Tests below assert registry-driven rendering at /juno.

  it('renders the "Juno Industries" wordmark and "J" mark when route is /juno', () => {
    renderHeaderJuno()
    expect(screen.getByText('Juno Industries')).toBeInTheDocument()
    expect(screen.getByText('J')).toBeInTheDocument()
  })

  it('does NOT render the "Seva Mining" wordmark or "S" mark when route is /juno', () => {
    renderHeaderJuno()
    expect(screen.queryByText('Seva Mining')).not.toBeInTheDocument()
    expect(screen.queryByText('S')).not.toBeInTheDocument()
  })
})
