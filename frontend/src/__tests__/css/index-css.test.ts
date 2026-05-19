// Phase 8 — Plan 08-01 (Wave 0) RED test for UI-01 / D-05 semantic-token presence.
//
// LOCATION RATIONALE: this file lives under `frontend/src/__tests__/css/`
// rather than `frontend/__tests__/css/` because `tsconfig.app.json` only
// includes `src/` — placing it outside `src/` would silently skip TypeScript
// checking. vitest's default include glob (**/*.{test,spec}.?(c|m)[jt]s?(x))
// picks it up automatically regardless.
//
// This test asserts the three semantic amber tokens added by Wave 1
// (Plan 08-02) in `frontend/src/index.css` per 08-UI-SPEC §Color §Semantic
// accent token additions. The naming uses the `brand-` namespace (NOT `accent`)
// to avoid colliding with shadcn's existing `--color-accent` (D-06).
//
// EXPECTED STATE: this test FAILS at Wave 0 (the tokens do not exist yet) and
// turns GREEN after Wave 1 adds them. This is the entire point of the Wave 0
// scaffolding contract: provide a real automated target for the executor of
// Plan 08-02 to verify against.
/// <reference types="node" />
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'

describe('index.css — Phase 8 semantic amber tokens (UI-01 / D-05)', () => {
  // ESM-friendly __dirname replacement (Vitest runs ESM by default).
  // Phase 8 Wave 1 (08-02) fix: original Wave 0 stub assumed CommonJS __dirname
  // which broke `tsc -b` under the `tsconfig.app.json` `types: ["vite/client"]`
  // restriction. The triple-slash above unlocks Node types for this single file.
  const __filename = fileURLToPath(import.meta.url)
  const __dirname = dirname(__filename)
  const cssPath = resolve(__dirname, '../../index.css')
  const css = readFileSync(cssPath, 'utf-8')

  it('declares --color-brand-accent inside @theme inline', () => {
    expect(css).toMatch(/--color-brand-accent:\s*var\(--brand-accent\)/)
  })

  it('declares --color-brand-accent-hover inside @theme inline', () => {
    expect(css).toMatch(/--color-brand-accent-hover:\s*var\(--brand-accent-hover\)/)
  })

  it('declares --color-brand-accent-subtle inside @theme inline', () => {
    expect(css).toMatch(/--color-brand-accent-subtle:\s*var\(--brand-accent-subtle\)/)
  })

  it('binds --brand-accent under .dark (visual amber-500)', () => {
    expect(css).toMatch(/--brand-accent:\s*(oklch\([^)]+\)|#f59e0b)/i)
  })

  it('binds --brand-accent-hover under .dark (visual amber-400)', () => {
    expect(css).toMatch(/--brand-accent-hover:\s*(oklch\([^)]+\)|#fbbf24)/i)
  })

  it('binds --brand-accent-subtle under .dark (5% alpha)', () => {
    expect(css).toMatch(/--brand-accent-subtle:\s*(oklch\([^)]+\/\s*0?\.0?5\)|#f59e0b0d)/i)
  })

  it('does NOT clobber the shadcn --color-accent token (D-06)', () => {
    // Strip the brand-prefixed declarations and check that --color-accent
    // (the shadcn neutral hover surface) appears at most once.
    const stripped = css.replace(/--color-brand-accent[-a-z]*:/g, '')
    const accentLines = stripped.match(/--color-accent\s*:/g) ?? []
    expect(accentLines.length).toBeLessThanOrEqual(1)
  })
})
