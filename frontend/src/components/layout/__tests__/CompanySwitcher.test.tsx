/** @vitest-environment jsdom */
/**
 * CompanySwitcher — segmented control + queryClient.clear() + navigate
 * (TENANT-07, TENANT-09).
 *
 * GREEN as of Wave 3 (09-04 Task 2). Component lives at
 * frontend/src/components/layout/CompanySwitcher.tsx.
 *
 * Contract (per D-07, D-08, 09-UI-SPEC.md):
 *   - Renders two side-by-side buttons (Seva | Juno).
 *   - Active state derived from useParams<{company: string}>() — URL is the
 *     source of truth, NOT a separate piece of state.
 *   - Active button class: border-brand-accent text-brand-accent (semantic
 *     tokens from Phase 8 D-05). Inactive: border-zinc-800.
 *   - Click on the OTHER button:
 *     1. queryClient.clear()      — defence-in-depth cache invalidation
 *     2. navigate(`/${nextCompany}${currentSubPath}`)
 *     (in that order — clear MUST happen before navigate so the new tenant's
 *      first queries don't render stale rows from the previous tenant.)
 *   - Click on the ALREADY-ACTIVE button is a no-op (no clear, no navigate).
 */
import { describe, expect, it, vi, beforeEach } from 'vitest'

const mockNavigate = vi.fn()
const mockClear = vi.fn()

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>()
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

vi.mock('@tanstack/react-query', async (importOriginal) => {
  const actual =
    await importOriginal<typeof import('@tanstack/react-query')>()
  return {
    ...actual,
    useQueryClient: () => ({ clear: mockClear }),
  }
})

// Indirect-path pattern (see queryKeys.test.ts for rationale): keeps the
// file transformable today even though `@/components/layout/CompanySwitcher`
// doesn't exist yet (lands in Wave 3).
const companySwitcherPath = '@/components/layout/CompanySwitcher'

describe('CompanySwitcher (TENANT-07, TENANT-09)', () => {
  beforeEach(() => {
    mockNavigate.mockReset()
    mockClear.mockReset()
  })

  it('renders Seva and Juno buttons with active class on current tenant', async () => {
    const { render, screen } = await import('@testing-library/react')
    const { MemoryRouter, Routes, Route } = await import('react-router-dom')
    const { CompanySwitcher } = await import(
      /* @vite-ignore */ companySwitcherPath
    )

    render(
      <MemoryRouter initialEntries={['/seva/calendar']}>
        <Routes>
          <Route path=":company/*" element={<CompanySwitcher />} />
        </Routes>
      </MemoryRouter>,
    )

    const sevaBtn = screen.getByRole('button', { name: /seva/i })
    const junoBtn = screen.getByRole('button', { name: /juno/i })

    expect(sevaBtn.className).toMatch(/border-brand-accent/)
    expect(junoBtn.className).not.toMatch(/border-brand-accent/)
  })

  it('clicking Juno calls queryClient.clear() then navigate to /juno/calendar', async () => {
    const { render, screen, fireEvent } = await import('@testing-library/react')
    const { MemoryRouter, Routes, Route } = await import('react-router-dom')
    const { CompanySwitcher } = await import(
      /* @vite-ignore */ companySwitcherPath
    )

    render(
      <MemoryRouter initialEntries={['/seva/calendar']}>
        <Routes>
          <Route path=":company/*" element={<CompanySwitcher />} />
        </Routes>
      </MemoryRouter>,
    )

    fireEvent.click(screen.getByRole('button', { name: /juno/i }))

    expect(mockClear).toHaveBeenCalledOnce()
    expect(mockNavigate).toHaveBeenCalledWith('/juno/calendar')

    // Order-of-operations: clear must precede navigate.
    const clearOrder = mockClear.mock.invocationCallOrder[0]
    const navOrder = mockNavigate.mock.invocationCallOrder[0]
    expect(clearOrder).toBeLessThan(navOrder)
  })

  it('preserves sub-path when switching (e.g. /seva/viral -> /juno/viral)', async () => {
    const { render, screen, fireEvent } = await import('@testing-library/react')
    const { MemoryRouter, Routes, Route } = await import('react-router-dom')
    const { CompanySwitcher } = await import(
      /* @vite-ignore */ companySwitcherPath
    )

    render(
      <MemoryRouter initialEntries={['/seva/viral']}>
        <Routes>
          <Route path=":company/*" element={<CompanySwitcher />} />
        </Routes>
      </MemoryRouter>,
    )

    fireEvent.click(screen.getByRole('button', { name: /juno/i }))
    expect(mockNavigate).toHaveBeenCalledWith('/juno/viral')
  })

  it('switching while at /seva/ goes to /juno/ (empty sub-path)', async () => {
    const { render, screen, fireEvent } = await import('@testing-library/react')
    const { MemoryRouter, Routes, Route } = await import('react-router-dom')
    const { CompanySwitcher } = await import(
      /* @vite-ignore */ companySwitcherPath
    )

    render(
      <MemoryRouter initialEntries={['/seva']}>
        <Routes>
          <Route path=":company/*" element={<CompanySwitcher />} />
        </Routes>
      </MemoryRouter>,
    )

    fireEvent.click(screen.getByRole('button', { name: /juno/i }))
    expect(mockNavigate).toHaveBeenCalledWith('/juno/')
  })

  it('clicking the already-active tenant is a no-op', async () => {
    const { render, screen, fireEvent } = await import('@testing-library/react')
    const { MemoryRouter, Routes, Route } = await import('react-router-dom')
    const { CompanySwitcher } = await import(
      /* @vite-ignore */ companySwitcherPath
    )

    render(
      <MemoryRouter initialEntries={['/seva/calendar']}>
        <Routes>
          <Route path=":company/*" element={<CompanySwitcher />} />
        </Routes>
      </MemoryRouter>,
    )

    fireEvent.click(screen.getByRole('button', { name: /seva/i }))

    expect(mockClear).not.toHaveBeenCalled()
    expect(mockNavigate).not.toHaveBeenCalled()
  })
})

// Wave 3 ships frontend/src/components/layout/CompanySwitcher.tsx and the
// suite is GREEN.
