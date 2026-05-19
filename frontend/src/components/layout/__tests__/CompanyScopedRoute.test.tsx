/** @vitest-environment jsdom */
/**
 * CompanyScopedRoute — slug validation + redirect (TENANT-05).
 *
 * Phase 9 Wave 0 RED — production code lands in Wave 3 (09-04-PLAN.md).
 * Component expected at: frontend/src/components/layout/CompanyScopedRoute.tsx
 *
 * Contract (per D-04, D-05, D-07):
 *   - Invalid slug (not in ACTIVE_COMPANIES) -> <Navigate to="/seva" replace>
 *   - Valid slug ('seva' | 'juno') -> renders <Outlet />
 *   - On mount with valid slug, calls setLastVisitedCompany(slug) so the
 *     Zustand persist middleware captures the last-visited company.
 *
 * Vitest skip idiom: per-test `it.skip()`. Wave 3 removes each `.skip`.
 */
import { describe, expect, it } from 'vitest'

// Indirect-path pattern (see queryKeys.test.ts for rationale): vite's
// import-analysis runs at transform time and fails the whole file if it
// can't resolve `@/components/layout/CompanyScopedRoute` — even inside
// `it.skip()` blocks. Storing the path in a variable defers resolution to
// runtime, so the module-not-found error happens AT TEST RUN (inside the
// skipped test) rather than at TRANSFORM (which kills the whole file).
const companyScopedRoutePath = '@/components/layout/CompanyScopedRoute'

describe('CompanyScopedRoute (TENANT-05)', () => {
  it.skip('redirects invalid slug to /seva', async () => {
    // Wave 3 (09-04-PLAN.md) — CompanyScopedRoute component not yet created.
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

  it.skip('renders Outlet for valid slug (seva)', async () => {
    // Wave 3 (09-04-PLAN.md) — CompanyScopedRoute not yet created.
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

  it.skip('renders Outlet for valid slug (juno)', async () => {
    // Wave 3 (09-04-PLAN.md) — CompanyScopedRoute not yet created.
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

  it.skip('calls setLastVisitedCompany on mount with valid slug', async () => {
    // Wave 3 (09-04-PLAN.md) — CompanyScopedRoute + companySlice not yet created.
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

// Once Wave 3 ships frontend/src/components/layout/CompanyScopedRoute.tsx,
// REMOVE the `.skip` on each it.skip(...) above and the suite should pass
// GREEN.
