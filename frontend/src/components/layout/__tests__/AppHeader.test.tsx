import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import { AppHeader } from '../AppHeader'

// Mock useNavigate from react-router-dom
const mockNavigate = vi.fn()
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>()
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

// Mock the zustand store
const mockClearToken = vi.fn()
vi.mock('@/stores', () => ({
  useAppStore: (selector: (state: { clearToken: () => void }) => unknown) =>
    selector({ clearToken: mockClearToken }),
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

  it('renders a "Log out" button', () => {
    renderHeader()
    expect(screen.getByRole('button', { name: /log out/i })).toBeInTheDocument()
  })

  it('clicking "Log out" calls clearToken and navigates to /login', () => {
    renderHeader()
    const logoutBtn = screen.getByRole('button', { name: /log out/i })
    fireEvent.click(logoutBtn)
    expect(mockClearToken).toHaveBeenCalledOnce()
    expect(mockNavigate).toHaveBeenCalledWith('/login')
  })
})
