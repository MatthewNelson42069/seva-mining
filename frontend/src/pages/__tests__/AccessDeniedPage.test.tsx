/** @vitest-environment jsdom */
/**
 * AccessDeniedPage tests — quick-260521-9ze
 * Verifies: per-tenant wordmark, no inputs/forms, correct copy.
 */
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

// We mock useCompanyBrand to control the wordmark without needing full router state.
vi.mock('@/hooks/useCompanyBrand', () => ({
  useCompanyBrand: vi.fn(() => ({
    wordmark: 'Seva Mining',
    markLetter: 'S',
    markBgClassName: 'bg-brand-accent',
    palette: { accent: '', accentHover: '', accentSubtle: '' },
    pageTitle: 'Seva Mining',
    faviconHref: '/brand/seva.svg',
  })),
}))

describe('AccessDeniedPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('renders an "Access required" heading', async () => {
    const { AccessDeniedPage } = await import('../AccessDeniedPage')
    render(
      <MemoryRouter initialEntries={['/access-denied']}>
        <AccessDeniedPage />
      </MemoryRouter>,
    )
    expect(
      screen.getByRole('heading', { name: /access required/i }),
    ).toBeInTheDocument()
  })

  it('renders the Juno wordmark when useCompanyBrand returns Juno config', async () => {
    const { useCompanyBrand } = await import('@/hooks/useCompanyBrand')
    vi.mocked(useCompanyBrand).mockReturnValue({
      wordmark: 'Juno Industries',
      markLetter: 'J',
      markBgClassName: 'bg-brand-accent',
      palette: { accent: '', accentHover: '', accentSubtle: '' },
      pageTitle: 'Juno Industries',
      faviconHref: '/brand/juno.svg',
    })
    const { AccessDeniedPage } = await import('../AccessDeniedPage')
    render(
      <MemoryRouter initialEntries={['/juno/access-denied']}>
        <AccessDeniedPage />
      </MemoryRouter>,
    )
    expect(screen.getByText('Juno Industries')).toBeInTheDocument()
  })

  it('renders the Seva wordmark when useCompanyBrand returns Seva config', async () => {
    const { useCompanyBrand } = await import('@/hooks/useCompanyBrand')
    vi.mocked(useCompanyBrand).mockReturnValue({
      wordmark: 'Seva Mining',
      markLetter: 'S',
      markBgClassName: 'bg-brand-accent',
      palette: { accent: '', accentHover: '', accentSubtle: '' },
      pageTitle: 'Seva Mining',
      faviconHref: '/brand/seva.svg',
    })
    const { AccessDeniedPage } = await import('../AccessDeniedPage')
    render(
      <MemoryRouter initialEntries={['/seva/access-denied']}>
        <AccessDeniedPage />
      </MemoryRouter>,
    )
    expect(screen.getByText('Seva Mining')).toBeInTheDocument()
  })

  it('does NOT render any <input> element', async () => {
    const { AccessDeniedPage } = await import('../AccessDeniedPage')
    const { container } = render(
      <MemoryRouter initialEntries={['/access-denied']}>
        <AccessDeniedPage />
      </MemoryRouter>,
    )
    expect(container.querySelectorAll('input')).toHaveLength(0)
  })

  it('does NOT render any <form> element', async () => {
    const { AccessDeniedPage } = await import('../AccessDeniedPage')
    const { container } = render(
      <MemoryRouter initialEntries={['/access-denied']}>
        <AccessDeniedPage />
      </MemoryRouter>,
    )
    expect(container.querySelectorAll('form')).toHaveLength(0)
  })
})
