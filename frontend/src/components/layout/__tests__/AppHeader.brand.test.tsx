/**
 * AppHeader brand effect — global side-effect surface tests.
 *
 * Phase 13 D-07 — FOWB (Flash Of Wrong Brand) protection contract.
 *
 * This file is intentionally SEPARATE from `AppHeader.test.tsx` because it
 * mutates global state (`document.documentElement.dataset.company`,
 * `document.title`, `<link rel='icon'>`). Isolating the pollution here keeps
 * the simpler unit tests in `AppHeader.test.tsx` cleanup-free.
 *
 * The 5 tests cover:
 *   1. Initial /seva mount sets data-company="seva" + title "Seva Mining"
 *   2. Initial /juno mount sets data-company="juno" + title "Juno Industries"
 *   3. FOWB route flip /seva → /juno — wordmark + dataset + title flip
 *      SYNCHRONOUSLY in a single act() wrapper. No async waits anywhere in
 *      the assertion path. The synchronous pass IS the FOWB proof: a real
 *      FOWB bug would surface as a render commit with mismatched chrome.
 *   4. Favicon link href updates on route change to /juno.
 *   5. Cleanup on unmount reverts dataset.company to 'seva' and
 *      document.title to 'Seva Mining' — the /login revert safety net
 *      so re-login to /seva doesn't briefly show navy chrome.
 */

import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, act } from '@testing-library/react'
import { MemoryRouter, Routes, Route, useNavigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useEffect } from 'react'

import { AppHeader } from '../AppHeader'
import { CompanyBrandEffect } from '../CompanyBrandEffect'

// Mock useNavigate is NOT needed here — we use the real useNavigate to drive
// the FOWB route flip in test 3. AppHeader's own useNavigate call still gets
// the real implementation (we don't click Log out in this file).

// Mock @/stores — must support both reactive `useAppStore(selector)` form
// (consumed by useCompanyBrand) AND the non-reactive `useAppStore.getState()`
// form (consumed by BareRootRedirect, though that's not under test here).
// Factory is hoisted by vi.mock, so the stub MUST be inlined inside it —
// referencing a top-level const triggers "Cannot access before initialization".
vi.mock('@/stores', () => {
  const stubState = { clearToken: () => {}, lastVisitedCompany: null }
  const useAppStore = ((selector?: (s: typeof stubState) => unknown) => {
    return selector ? selector(stubState) : stubState
  }) as unknown as {
    (selector: (s: typeof stubState) => unknown): unknown
    getState: () => typeof stubState
  }
  useAppStore.getState = () => stubState
  return { useAppStore }
})

function renderAt(path: '/seva' | '/juno') {
  const queryClient = new QueryClient()
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route
            path=":company/*"
            element={
              <>
                <CompanyBrandEffect />
                <AppHeader />
              </>
            }
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

// Navigate-wrapper for FOWB test (test 3). A tiny inner component captures
// react-router's `useNavigate` and exposes it via a ref so the test body
// can flip routes inside a single synchronous act(). This is the spec's
// fallback when `rerender` with a fresh MemoryRouter doesn't actually
// navigate (each MemoryRouter has its own history; rerendering with new
// initialEntries discards prior cache, mounting a new tree).
function renderWithNavigateHandle(initialPath: '/seva' | '/juno'): {
  navigate: (to: string) => void
  unmount: () => void
} {
  const handle: { navigate: (to: string) => void } = {
    navigate: () => {
      throw new Error('Navigate handle not yet wired')
    },
  }

  function NavigateCapture() {
    const navigate = useNavigate()
    useEffect(() => {
      handle.navigate = (to: string) => navigate(to)
    }, [navigate])
    return null
  }

  const queryClient = new QueryClient()
  const { unmount } = render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route
            path=":company/*"
            element={
              <>
                <CompanyBrandEffect />
                <AppHeader />
                <NavigateCapture />
              </>
            }
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )

  return { navigate: handle.navigate, unmount }
}

describe('AppHeader brand effect', () => {
  beforeEach(() => {
    // Reset global state to a clean default before every test.
    document.documentElement.removeAttribute('data-company')
    document.title = 'Seva Mining'
    // Remove any pre-existing favicon link, inject a fresh one mirroring
    // the production index.html shape.
    document.head.querySelectorAll("link[rel='icon']").forEach((el) => el.remove())
    const link = document.createElement('link')
    link.rel = 'icon'
    link.href = '/favicon.svg'
    document.head.appendChild(link)
    vi.clearAllMocks()
  })

  afterEach(() => {
    document.documentElement.removeAttribute('data-company')
    document.title = 'Seva Mining'
    document.head.querySelectorAll("link[rel='icon']").forEach((el) => el.remove())
  })

  it('sets data-company="seva" on documentElement when route is /seva', () => {
    renderAt('/seva')
    expect(document.documentElement.dataset.company).toBe('seva')
    expect(document.title).toBe('Seva Mining')
  })

  it('sets data-company="juno" on documentElement when route is /juno', () => {
    renderAt('/juno')
    expect(document.documentElement.dataset.company).toBe('juno')
    expect(document.title).toBe('Juno Industries')
  })

  it('FOWB: route flip /seva -> /juno updates wordmark + dataset + title atomically in single act()', () => {
    const { navigate } = renderWithNavigateHandle('/seva')

    // Confirm initial Seva state before the flip.
    expect(document.documentElement.dataset.company).toBe('seva')
    expect(screen.getByText('Seva Mining')).toBeInTheDocument()
    expect(document.title).toBe('Seva Mining')

    // Synchronous flip — no async waits anywhere. The act() wrapper
    // batches React's commit; on its return, ALL effects have flushed.
    // A real FOWB bug would surface as a render with Juno dataset but
    // Seva wordmark (or vice versa) — both sides must flip in the same
    // commit.
    act(() => {
      navigate('/juno')
    })

    expect(document.documentElement.dataset.company).toBe('juno')
    expect(screen.getByText('Juno Industries')).toBeInTheDocument()
    expect(screen.getByText('J')).toBeInTheDocument()
    expect(document.title).toBe('Juno Industries')
  })

  it('updates favicon link href on route change to /juno', () => {
    renderAt('/juno')
    const icon = document.head.querySelector<HTMLLinkElement>("link[rel='icon']")
    expect(icon).not.toBeNull()
    expect(icon!.href).toMatch(/\/brand\/juno\.svg$/)
  })

  it('cleanup on unmount reverts data-company to "seva" and title to "Seva Mining"', () => {
    const { unmount } = renderAt('/juno')
    // Pre-unmount state confirmed.
    expect(document.documentElement.dataset.company).toBe('juno')
    expect(document.title).toBe('Juno Industries')
    // Unmount runs the cleanup effect — dataset + title revert.
    unmount()
    expect(document.documentElement.dataset.company).toBe('seva')
    expect(document.title).toBe('Seva Mining')
  })
})
