/** @vitest-environment jsdom */
/**
 * apiFetch client tests — quick-260521-9ze
 * Verifies: credentials:include, 403→/access-denied, no Authorization header, no localStorage.
 */
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'

describe('apiFetch (cookie-token auth model)', () => {
  beforeEach(() => {
    vi.resetModules()
    vi.restoreAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('calls fetch with credentials: include on every request', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ result: 'ok' }),
    })
    vi.stubGlobal('fetch', mockFetch)

    const { apiFetch } = await import('../client')
    await apiFetch('/test-path')

    expect(mockFetch).toHaveBeenCalledOnce()
    const callArg = mockFetch.mock.calls[0][1]
    expect(callArg.credentials).toBe('include')
  })

  it('redirects to /access-denied on 403 response', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      json: async () => ({}),
    })
    vi.stubGlobal('fetch', mockFetch)

    // Capture window.location.href assignment
    const locationMock = { href: '' }
    Object.defineProperty(window, 'location', {
      value: locationMock,
      writable: true,
    })

    const { apiFetch } = await import('../client')
    await expect(apiFetch('/test-path')).rejects.toThrow()
    expect(locationMock.href).toBe('/access-denied')
  })

  it('does NOT attach an Authorization header', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({}),
    })
    vi.stubGlobal('fetch', mockFetch)

    const { apiFetch } = await import('../client')
    await apiFetch('/test-path')

    const callHeaders = mockFetch.mock.calls[0][1]?.headers ?? {}
    const authHeader = Object.keys(callHeaders).find(
      (k) => k.toLowerCase() === 'authorization',
    )
    expect(authHeader).toBeUndefined()
  })

  it('does NOT access localStorage access_token key', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({}),
    })
    vi.stubGlobal('fetch', mockFetch)

    const getItemSpy = vi.spyOn(Storage.prototype, 'getItem')
    const setItemSpy = vi.spyOn(Storage.prototype, 'setItem')
    const removeItemSpy = vi.spyOn(Storage.prototype, 'removeItem')

    const { apiFetch } = await import('../client')
    await apiFetch('/test-path')

    const tokenAccesses = [
      ...getItemSpy.mock.calls,
      ...setItemSpy.mock.calls,
      ...removeItemSpy.mock.calls,
    ].filter(([key]) => key === 'access_token')

    expect(tokenAccesses).toHaveLength(0)
  })
})
