/** @vitest-environment jsdom */
/**
 * App router — bookmark grace redirects + :company nested route (TENANT-05,
 * TENANT-06).
 *
 * Phase 9 Wave 0 RED — production code lands in Wave 3 (09-04-PLAN.md).
 * App.tsx will be updated to:
 *   - Add <Route path=":company"> wrapper around <TabbedDashboard>.
 *   - Add bookmark grace <Navigate> elements:
 *       /            -> /seva     (D-05: bare / redirects to /seva/)
 *       /calendar    -> /seva/calendar  (D-06)
 *       /viral       -> /seva/viral     (D-06)
 *       /queue       -> /seva           (D-06; legacy v2.0)
 *       /agents/:slug -> /seva          (D-06; legacy v2.0)
 *       /digest, /settings, /login      — unchanged (NOT tenant-scoped)
 *
 * Vitest skip idiom: per-test `it.skip()`. Wave 3 removes each `.skip`.
 *
 * Note on testing App.tsx: the real App mounts its own <BrowserRouter>.
 * For these tests we re-define the route tree inside a <MemoryRouter> so
 * we can control initial entries. The Wave 3 implementation should factor
 * the route tree into a testable shape (e.g. export `<AppRoutes />` that
 * the tests can mount inside <MemoryRouter>).
 */
import { describe, expect, it } from 'vitest'

// Indirect-path pattern (see queryKeys.test.ts for rationale): `AppRoutes`
// is NOT yet exported from `@/App` — App.tsx currently exports the default
// `App` only. Wave 3 must factor the route tree into a testable
// `AppRoutes` export. Until then, this indirection keeps vite's
// import-analysis from failing the whole file at transform time.
const appRoutesPath = '@/App'

describe('App router bookmark grace (TENANT-06)', () => {
  it.skip('bare / redirects to /seva', async () => {
    // Wave 3 (09-04-PLAN.md) — bookmark grace redirects not yet wired.
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

  it.skip('/calendar redirects to /seva/calendar', async () => {
    // Wave 3 (09-04-PLAN.md) — bookmark grace redirects not yet wired.
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

  it.skip('/viral redirects to /seva/viral', async () => {
    // Wave 3 (09-04-PLAN.md) — bookmark grace redirects not yet wired.
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

  it.skip('/queue redirects to /seva (legacy v2.0 grace)', async () => {
    // Wave 3 (09-04-PLAN.md) — bookmark grace redirects not yet wired.
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

  it.skip('/agents/breaking_news redirects to /seva (legacy v2.0 grace)', async () => {
    // Wave 3 (09-04-PLAN.md) — bookmark grace redirects not yet wired.
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

  it.skip('/digest stays at /digest (not tenant-scoped — D-06)', async () => {
    // Wave 3 (09-04-PLAN.md) — /digest must NOT be tenant-prefixed.
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

  it.skip(':company route mounts TabbedDashboard with useParams', async () => {
    // Wave 3 (09-04-PLAN.md) — nested :company route not yet wired.
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

// Once Wave 3 ships the nested :company route + bookmark grace <Navigate>
// elements in App.tsx (and exports `AppRoutes` so tests can mount it inside
// <MemoryRouter>), REMOVE the `.skip` on each it.skip(...) above and the
// suite should pass GREEN.
