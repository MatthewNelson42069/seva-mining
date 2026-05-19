// Phase 8 — Plan 08-01 (Wave 0) RED-tests-first scaffolding for UI-05 / D-01..D-04.
//
// These tests describe the canonical X-handle pill rendering contract:
//   - Renders as <a> with href="https://x.com/{handle}"
//   - Opens in a new tab via target="_blank" rel="noopener noreferrer"
//   - Carries the locked pill class string from 08-UI-SPEC §Component Inventory
//   - Hover state introduces amber accent classes (D-03)
//
// IMPORT STRATEGY: Vite's import-analysis runs at transform time and fails on
// missing modules EVEN IF the consuming describe block is `.skip`. To keep the
// suite GREEN at Wave 0 while leaving a real import target for Wave 2, we use
// dynamic `await import('../XHandlePill')` inside each `it` body. Under
// `describe.skip` the `it` bodies never execute, so the dynamic import never
// runs. Wave 2's redline: flip `describe.skip` -> `describe` AND ship
// `frontend/src/components/markdown/XHandlePill.tsx`.
import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type XHandlePillModule = { XHandlePill: (props: { href: string; children?: any }) => any }

// Variable-path indirection defeats Vite's static import analysis. The plugin
// only inspects literal string arguments to `import()`; a variable forces
// runtime resolution. Under `describe.skip` the `it` bodies never execute, so
// this resolution never runs at collection time.
const XHANDLEPILL_MODULE_PATH = '../XHandlePill'

describe('XHandlePill', () => {
  it('renders an <a> with href="https://x.com/{handle}" when given a handle URL', async () => {
    const { XHandlePill } = (await import(/* @vite-ignore */ XHANDLEPILL_MODULE_PATH)) as XHandlePillModule
    const { getByRole } = render(
      <XHandlePill href="https://x.com/jpow">@jpow</XHandlePill>,
    )
    const link = getByRole('link') as HTMLAnchorElement
    expect(link.getAttribute('href')).toBe('https://x.com/jpow')
    expect(link.textContent).toBe('@jpow')
  })

  it('opens in a new tab with safe rel attribute', async () => {
    const { XHandlePill } = (await import(/* @vite-ignore */ XHANDLEPILL_MODULE_PATH)) as XHandlePillModule
    const { getByRole } = render(
      <XHandlePill href="https://x.com/jpow">@jpow</XHandlePill>,
    )
    const link = getByRole('link') as HTMLAnchorElement
    expect(link.getAttribute('target')).toBe('_blank')
    expect(link.getAttribute('rel')).toBe('noopener noreferrer')
  })

  it('renders the canonical pill classes from D-01 (08-UI-SPEC §Interaction States)', async () => {
    const { XHandlePill } = (await import(/* @vite-ignore */ XHANDLEPILL_MODULE_PATH)) as XHandlePillModule
    const { getByRole } = render(
      <XHandlePill href="https://x.com/jpow">@jpow</XHandlePill>,
    )
    const link = getByRole('link') as HTMLAnchorElement
    const cls = link.className
    expect(cls).toContain('font-mono')
    expect(cls).toContain('text-xs')
    expect(cls).toContain('bg-zinc-800/60')
    expect(cls).toContain('px-2')
    expect(cls).toContain('py-0.5')
    expect(cls).toContain('rounded')
    expect(cls).toContain('border')
    expect(cls).toContain('border-transparent')
    expect(cls).toContain('transition-colors')
  })

  it('renders the hover classes from D-03 (amber-500/40 border + amber-300 text)', async () => {
    const { XHandlePill } = (await import(/* @vite-ignore */ XHANDLEPILL_MODULE_PATH)) as XHandlePillModule
    const { getByRole } = render(
      <XHandlePill href="https://x.com/jpow">@jpow</XHandlePill>,
    )
    const link = getByRole('link') as HTMLAnchorElement
    const cls = link.className
    // Either literal amber-500/40 OR semantic brand-accent token form per D-05.
    const borderOk =
      cls.includes('hover:border-amber-500/40') ||
      cls.includes('hover:border-brand-accent')
    expect(borderOk).toBe(true)
    expect(cls).toContain('hover:text-amber-300')
  })
})
