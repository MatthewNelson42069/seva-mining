/** @vitest-environment node */
/**
 * queryKeys factory shape (TENANT-09).
 *
 * GREEN as of Wave 3 (09-04 Task 1) — production code lives at
 * frontend/src/api/queryKeys.ts.
 *
 * Contract:
 *   queryKeys.summaries('seva', 60)       -> ['summaries', 'seva', 60] as const
 *   queryKeys.calendar('juno', start, end) -> ['calendar', 'juno', start, end] as const
 *   queryKeys.weeklySweeps('seva', 12)    -> ['weekly-sweeps', 'seva', 12] as const
 *
 * Every key MUST include companyId as the SECOND tuple element so
 * queryClient.clear() at tenant switch (D-08) + invalidation on per-company
 * mutations work uniformly.
 */
import { describe, expect, it } from 'vitest'

// Indirect-path pattern: assigning the module path to a variable historically
// prevented vite:import-analysis from failing the whole file at transform time
// when @/api/queryKeys did not yet exist. The module now ships under Wave 3,
// but the indirection is harmless — vite still resolves the same module.
const queryKeysModulePath = '@/api/queryKeys'

describe('queryKeys factory (TENANT-09)', () => {
  it('summaries factory returns tuple with companyId and limit', async () => {
    // GREEN as of Wave 3.
    const { queryKeys } = await import(/* @vite-ignore */ queryKeysModulePath)
    expect(queryKeys.summaries('seva', 60)).toEqual(['summaries', 'seva', 60])
    expect(queryKeys.summaries('juno', 30)).toEqual(['summaries', 'juno', 30])
  })

  it('calendar factory returns tuple with companyId, start, end', async () => {
    // GREEN as of Wave 3.
    const { queryKeys } = await import(/* @vite-ignore */ queryKeysModulePath)
    expect(queryKeys.calendar('juno', '2026-01-01', '2026-12-31')).toEqual([
      'calendar',
      'juno',
      '2026-01-01',
      '2026-12-31',
    ])
  })

  it('weeklySweeps factory returns tuple', async () => {
    // GREEN as of Wave 3.
    const { queryKeys } = await import(/* @vite-ignore */ queryKeysModulePath)
    expect(queryKeys.weeklySweeps('seva', 12)).toEqual([
      'weekly-sweeps',
      'seva',
      12,
    ])
  })

  it('seva and juno produce different cache keys', async () => {
    // Defence-in-depth: switching tenants must NOT collide with cached results
    // for the other tenant. Each factory MUST distinguish on companyId.
    // GREEN as of Wave 3.
    const { queryKeys } = await import(/* @vite-ignore */ queryKeysModulePath)
    expect(queryKeys.summaries('seva', 60)).not.toEqual(
      queryKeys.summaries('juno', 60),
    )
  })
})

// Wave 3 ships frontend/src/api/queryKeys.ts and the suite is GREEN.
