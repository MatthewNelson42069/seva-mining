/** @vitest-environment jsdom */
/**
 * App router — bookmark grace redirects + :company nested route (TENANT-05,
 * TENANT-06).
 *
 * GREEN as of Wave 3 (09-04 Task 2). App.tsx now exports `AppRoutes` —
 * the route tree extracted from App so tests can mount it inside a
 * <MemoryRouter>:
 *   - Adds <Route path=":company"> wrapper around <TabbedDashboard>.
 *   - Adds bookmark grace <Navigate> elements:
 *       /            -> /seva     (D-05: bare / redirects to /seva/)
 *       /calendar    -> /seva/calendar  (D-06)
 *       /viral       -> /seva/viral     (D-06)
 *       /queue       -> /seva           (D-06; legacy v2.0)
 *       /agents/:slug -> /seva          (D-06; legacy v2.0)
 *       /digest, /settings, /access-denied — unchanged (NOT tenant-scoped)
 */
import { describe, expect, it, beforeEach } from 'vitest'

// Indirect-path pattern (historical — kept for symmetry with the other
// Wave 0 test files). The `AppRoutes` named export is shipped by Wave 3.
const appRoutesPath = '@/App'

// Auth setup: cookie-token auth model (quick-260521-9ze) — no ProtectedRoute.
// All routes are accessible without any auth setup in the router tree.
// apiFetch handles 403 → /access-denied at fetch time, not route time.
// No-op beforeEach kept for test structure symmetry.
beforeEach(async () => {
  // No-op: cookie auth is handled by the browser's HttpOnly cookie.
  // No localStorage setup needed.
})

describe('App router bookmark grace (TENANT-06)', () => {
  it('bare / redirects to /seva', async () => {
    const { render, screen } = await import('@testing-library/react')
    const { MemoryRouter, useLocation } = await import('react-router-dom')
    const { AppRoutes } = await import(/* @vite-ignore */ appRoutesPath)

    function LocationProbe() {
      const loc = useLocation()
      return <div data-testid="current-path">{loc.pathname}</div>
    }

    render(
      <MemoryRouter initialEntries={['/']}>
        <AppRoutes />
        <LocationProbe />
      </MemoryRouter>,
    )

    expect(screen.getByTestId('current-path').textContent).toBe('/seva')
  })

  it('/calendar redirects to /seva/calendar', async () => {
    const { render, screen } = await import('@testing-library/react')
    const { MemoryRouter, useLocation } = await import('react-router-dom')
    const { AppRoutes } = await import(/* @vite-ignore */ appRoutesPath)

    function LocationProbe() {
      const loc = useLocation()
      return <div data-testid="current-path">{loc.pathname}</div>
    }

    render(
      <MemoryRouter initialEntries={['/calendar']}>
        <AppRoutes />
        <LocationProbe />
      </MemoryRouter>,
    )

    expect(screen.getByTestId('current-path').textContent).toBe(
      '/seva/calendar',
    )
  })

  it('/viral redirects to /seva/viral', async () => {
    const { render, screen } = await import('@testing-library/react')
    const { MemoryRouter, useLocation } = await import('react-router-dom')
    const { AppRoutes } = await import(/* @vite-ignore */ appRoutesPath)

    function LocationProbe() {
      const loc = useLocation()
      return <div data-testid="current-path">{loc.pathname}</div>
    }

    render(
      <MemoryRouter initialEntries={['/viral']}>
        <AppRoutes />
        <LocationProbe />
      </MemoryRouter>,
    )

    expect(screen.getByTestId('current-path').textContent).toBe('/seva/viral')
  })

  it('/queue redirects to /seva (legacy v2.0 grace)', async () => {
    const { render, screen } = await import('@testing-library/react')
    const { MemoryRouter, useLocation } = await import('react-router-dom')
    const { AppRoutes } = await import(/* @vite-ignore */ appRoutesPath)

    function LocationProbe() {
      const loc = useLocation()
      return <div data-testid="current-path">{loc.pathname}</div>
    }

    render(
      <MemoryRouter initialEntries={['/queue']}>
        <AppRoutes />
        <LocationProbe />
      </MemoryRouter>,
    )

    expect(screen.getByTestId('current-path').textContent).toBe('/seva')
  })

  it('/agents/breaking_news redirects to /seva (legacy v2.0 grace)', async () => {
    const { render, screen } = await import('@testing-library/react')
    const { MemoryRouter, useLocation } = await import('react-router-dom')
    const { AppRoutes } = await import(/* @vite-ignore */ appRoutesPath)

    function LocationProbe() {
      const loc = useLocation()
      return <div data-testid="current-path">{loc.pathname}</div>
    }

    render(
      <MemoryRouter initialEntries={['/agents/breaking_news']}>
        <AppRoutes />
        <LocationProbe />
      </MemoryRouter>,
    )

    expect(screen.getByTestId('current-path').textContent).toBe('/seva')
  })

  it('/digest stays at /digest (not tenant-scoped — D-06)', async () => {
    const { render, screen } = await import('@testing-library/react')
    const { MemoryRouter, useLocation } = await import('react-router-dom')
    const { AppRoutes } = await import(/* @vite-ignore */ appRoutesPath)

    function LocationProbe() {
      const loc = useLocation()
      return <div data-testid="current-path">{loc.pathname}</div>
    }

    render(
      <MemoryRouter initialEntries={['/digest']}>
        <AppRoutes />
        <LocationProbe />
      </MemoryRouter>,
    )

    expect(screen.getByTestId('current-path').textContent).toBe('/digest')
  })

  it(':company route mounts TabbedDashboard with useParams', async () => {
    const { render, screen } = await import('@testing-library/react')
    const { MemoryRouter } = await import('react-router-dom')
    const { AppRoutes } = await import(/* @vite-ignore */ appRoutesPath)

    render(
      <MemoryRouter initialEntries={['/seva/calendar']}>
        <AppRoutes />
      </MemoryRouter>,
    )

    // TabbedDashboard renders the TabNav with the Calendar tab — assert that
    // text appears (Wave 3 wires useParams().company through to the page).
    expect(screen.getByText(/calendar/i)).toBeInTheDocument()
  })
})

// Wave 3 ships nested :company route + bookmark grace <Navigate> elements
// in App.tsx and the suite is GREEN.
