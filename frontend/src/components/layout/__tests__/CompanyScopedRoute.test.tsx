/** @vitest-environment jsdom */
/**
 * CompanyScopedRoute — slug validation + redirect (TENANT-05).
 *
 * GREEN as of Wave 3 (09-04 Task 1). Component lives at
 * frontend/src/components/layout/CompanyScopedRoute.tsx.
 *
 * Contract (per D-04, D-05, D-07):
 *   - Invalid slug (not in ACTIVE_COMPANIES) -> <Navigate to="/seva" replace>
 *   - Valid slug ('seva' | 'juno') -> renders <Outlet />
 *   - On mount with valid slug, calls setLastVisitedCompany(slug) so the
 *     Zustand persist middleware captures the last-visited company.
 */
import { describe, expect, it } from 'vitest'

// Indirect-path pattern (see queryKeys.test.ts for rationale): historical
// vite import-analysis workaround. Now harmless — module exists.
const companyScopedRoutePath = '@/components/layout/CompanyScopedRoute'

describe('CompanyScopedRoute (TENANT-05)', () => {
  it('redirects invalid slug to /seva', async () => {
    const { render, screen } = await import('@testing-library/react')
    const { MemoryRouter, Routes, Route, useLocation } = await import(
      'react-router-dom'
    )
    const { CompanyScopedRoute } = await import(
      /* @vite-ignore */ companyScopedRoutePath
    )

    function LocationProbe() {
      const loc = useLocation()
      return <div data-testid="current-path">{loc.pathname}</div>
    }

    render(
      <MemoryRouter initialEntries={['/bogus']}>
        <Routes>
          <Route path=":company" element={<CompanyScopedRoute />}>
            <Route index element={<div>child</div>} />
          </Route>
          <Route path="/seva/*" element={<LocationProbe />} />
        </Routes>
      </MemoryRouter>,
    )

    expect(screen.getByTestId('current-path').textContent).toBe('/seva')
  })

  it('renders Outlet for valid slug (seva)', async () => {
    const { render, screen } = await import('@testing-library/react')
    const { MemoryRouter, Routes, Route } = await import('react-router-dom')
    const { CompanyScopedRoute } = await import(
      /* @vite-ignore */ companyScopedRoutePath
    )

    render(
      <MemoryRouter initialEntries={['/seva']}>
        <Routes>
          <Route path=":company" element={<CompanyScopedRoute />}>
            <Route index element={<div data-testid="seva-child">CHILD</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    )

    expect(screen.getByTestId('seva-child')).toBeInTheDocument()
  })

  it('renders Outlet for valid slug (juno)', async () => {
    const { render, screen } = await import('@testing-library/react')
    const { MemoryRouter, Routes, Route } = await import('react-router-dom')
    const { CompanyScopedRoute } = await import(
      /* @vite-ignore */ companyScopedRoutePath
    )

    render(
      <MemoryRouter initialEntries={['/juno']}>
        <Routes>
          <Route path=":company" element={<CompanyScopedRoute />}>
            <Route index element={<div data-testid="juno-child">CHILD</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    )

    expect(screen.getByTestId('juno-child')).toBeInTheDocument()
  })

  it('calls setLastVisitedCompany on mount with valid slug', async () => {
    const { render } = await import('@testing-library/react')
    const { MemoryRouter, Routes, Route } = await import('react-router-dom')
    const storesPath = '@/stores'
    const { useAppStore } = await import(/* @vite-ignore */ storesPath)
    const { CompanyScopedRoute } = await import(
      /* @vite-ignore */ companyScopedRoutePath
    )

    render(
      <MemoryRouter initialEntries={['/juno']}>
        <Routes>
          <Route path=":company" element={<CompanyScopedRoute />}>
            <Route index element={<div>child</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    )

    expect(useAppStore.getState().lastVisitedCompany).toBe('juno')
  })
})

// Wave 3 ships frontend/src/components/layout/CompanyScopedRoute.tsx and the
// suite is GREEN.
