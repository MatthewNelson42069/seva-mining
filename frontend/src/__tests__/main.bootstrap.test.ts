/** @vitest-environment jsdom */
/**
 * Frontend bootstrap token-intercept tests — quick-260521-9ze
 * Verifies: ?token= triggers window.location.replace BEFORE React mounts.
 * Note: these tests import and exercise the bootstrap logic directly, not main.tsx.
 * The bootstrap function is exported from main.tsx for testability.
 */
import { describe, expect, it, vi, beforeEach } from 'vitest'

describe('token bootstrap', () => {
  beforeEach(() => {
    vi.resetModules()
    vi.restoreAllMocks()
  })

  it('calls window.location.replace with backend token-set URL when ?token=X is present', async () => {
    const replaceSpy = vi.fn()
    // Stub window.location before importing bootstrap
    Object.defineProperty(window, 'location', {
      value: {
        search: '?token=mytoken123',
        pathname: '/seva',
        replace: replaceSpy,
        href: '',
      },
      writable: true,
      configurable: true,
    })

    // The bootstrap logic lives in lib/bootstrap.ts (extracted from main.tsx for testability)
    const { bootstrapTokenRedirect } = await import('../lib/bootstrap')
    bootstrapTokenRedirect()

    expect(replaceSpy).toHaveBeenCalledOnce()
    const calledUrl = replaceSpy.mock.calls[0][0] as string
    expect(calledUrl).toContain('auth/token-set')
    expect(calledUrl).toContain('token=mytoken123')
    expect(calledUrl).toContain('next=')
  })

  it('does NOT call window.location.replace when no ?token param in URL', async () => {
    const replaceSpy = vi.fn()
    Object.defineProperty(window, 'location', {
      value: {
        search: '',
        pathname: '/seva',
        replace: replaceSpy,
        href: '',
      },
      writable: true,
      configurable: true,
    })

    const { bootstrapTokenRedirect } = await import('../lib/bootstrap')
    bootstrapTokenRedirect()

    expect(replaceSpy).not.toHaveBeenCalled()
  })
})
