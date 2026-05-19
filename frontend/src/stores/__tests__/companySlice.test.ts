/** @vitest-environment jsdom */
/**
 * Zustand companySlice — lastVisitedCompany + persist (TENANT-07).
 *
 * GREEN as of Wave 3 (09-04 Task 1). Slice lives at
 * frontend/src/stores/slices/companySlice.ts and is wired into useAppStore
 * via persist middleware (D-08) under the existing localStorage key
 * `seva-mining-app-state-v3`.
 *
 * Contract:
 *   - setLastVisitedCompany('juno') updates state to 'juno'.
 *   - The lastVisitedCompany value persists to localStorage under
 *     `seva-mining-app-state-v3` (Zustand persist's default JSON shape:
 *      `{ state: { lastVisitedCompany: 'juno' }, version: ... }`).
 *   - partialize EXCLUDES queueUi + auth state from persistence — ONLY
 *     lastVisitedCompany is persisted.
 */
import { beforeEach, describe, expect, it } from 'vitest'

const PERSIST_KEY = 'seva-mining-app-state-v3'

// Indirect-path pattern (see queryKeys.test.ts for rationale): keeps the
// test file transformable today even though `@/stores` does not yet export
// the companySlice fields under test. The existing `@/stores` module DOES
// exist (Phase 8) — only the new slice methods + persistence wiring land
// in Wave 3 — but using the same pattern across all Wave 0 files keeps the
// idiom consistent and avoids future breakage if the export surface changes.
const storesModulePath = '@/stores'

describe('companySlice (TENANT-07)', () => {
  beforeEach(async () => {
    localStorage.clear()
    // Reset in-memory Zustand state — the store is a module-level singleton
    // shared across tests; without this the previous test's set() leaks.
    const { useAppStore } = await import(/* @vite-ignore */ storesModulePath)
    useAppStore.setState({ lastVisitedCompany: null })
  })

  it('setLastVisitedCompany updates state to juno', async () => {
    // GREEN as of Wave 3.
    const { useAppStore } = await import(/* @vite-ignore */ storesModulePath)
    useAppStore.getState().setLastVisitedCompany('juno')
    expect(useAppStore.getState().lastVisitedCompany).toBe('juno')
  })

  it('persists lastVisitedCompany to localStorage under seva-mining-app-state-v3 key', async () => {
    // GREEN as of Wave 3.
    const { useAppStore } = await import(/* @vite-ignore */ storesModulePath)
    useAppStore.getState().setLastVisitedCompany('juno')
    const raw = localStorage.getItem(PERSIST_KEY)
    expect(raw).not.toBeNull()
    const parsed = JSON.parse(raw as string)
    expect(parsed.state.lastVisitedCompany).toBe('juno')
  })

  it('partialize excludes queueUi and auth state from persistence', async () => {
    // GREEN as of Wave 3.
    const { useAppStore } = await import(/* @vite-ignore */ storesModulePath)
    useAppStore.getState().setLastVisitedCompany('juno')
    const raw = localStorage.getItem(PERSIST_KEY)
    expect(raw).not.toBeNull()
    const parsed = JSON.parse(raw as string)
    // Only lastVisitedCompany should appear in persisted state.
    const persistedKeys = Object.keys(parsed.state)
    expect(persistedKeys).toEqual(['lastVisitedCompany'])
  })

  it('default lastVisitedCompany is null until a switch occurs (D-05)', async () => {
    // D-05: bare `/` redirects to `/seva/` (hardcoded, NOT last-visited in v3.0).
    // GREEN as of Wave 3.
    const { useAppStore } = await import(/* @vite-ignore */ storesModulePath)
    expect(useAppStore.getState().lastVisitedCompany).toBeNull()
  })
})

// Wave 3 ships frontend/src/stores/slices/companySlice.ts and the suite is GREEN.
