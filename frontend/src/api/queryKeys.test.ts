/** @vitest-environment node */
/**
 * queryKeys factory shape (TENANT-09).
 *
 * Phase 9 Wave 0 RED — production code lands in Wave 3 (09-04-PLAN.md).
 * Factory expected at: frontend/src/api/queryKeys.ts
 *
 * Contract:
 *   queryKeys.summaries('seva', 60)       -> ['summaries', 'seva', 60] as const
 *   queryKeys.calendar('juno', start, end) -> ['calendar', 'juno', start, end] as const
 *   queryKeys.weeklySweeps('seva', 12)    -> ['weekly-sweeps', 'seva', 12] as const
 *
 * Every key MUST include companyId as the SECOND tuple element so
 * queryClient.clear() at tenant switch (D-08) + invalidation on per-company
 * mutations work uniformly.
 *
 * Vitest does NOT support module-level skip equivalent to pytest's
 * `pytest.skip(..., allow_module_level=True)`. Per-test `it.skip()` is the
 * canonical Vitest pattern; Wave 3 removes each `.skip` (already enforced
 * by plan 09-04 Task 2 step 5 grep verification).
 */
import { describe, expect, it } from 'vitest'

// Indirect-path pattern: assigning the module path to a variable prevents
// vite:import-analysis from attempting to statically resolve the missing
// `@/api/queryKeys` module at transform time. Without this indirection, the
// test file fails to TRANSFORM (not just fails the assertion) — defeating
// the purpose of `it.skip()`. Wave 3 lands `@/api/queryKeys` at which point
// the indirection is harmless (vite still resolves the same module).
const queryKeysModulePath = '@/api/queryKeys'

describe('queryKeys factory (TENANT-09)', () => {
  it.skip('summaries factory returns tuple with companyId and limit', async () => {
    // Wave 3 (09-04-PLAN.md) — queryKeys.ts not yet created.
    const { queryKeys } = await import(/* @vite-ignore */ queryKeysModulePath)
    expect(queryKeys.summaries('seva', 60)).toEqual(['summaries', 'seva', 60])
    expect(queryKeys.summaries('juno', 30)).toEqual(['summaries', 'juno', 30])
  })

  it.skip('calendar factory returns tuple with companyId, start, end', async () => {
    const { queryKeys } = await import(/* @vite-ignore */ queryKeysModulePath)
    expect(queryKeys.calendar('juno', '2026-01-01', '2026-12-31')).toEqual([
      'calendar',
      'juno',
      '2026-01-01',
      '2026-12-31',
    ])
  })

  it.skip('weeklySweeps factory returns tuple', async () => {
    const { queryKeys } = await import(/* @vite-ignore */ queryKeysModulePath)
    expect(queryKeys.weeklySweeps('seva', 12)).toEqual([
      'weekly-sweeps',
      'seva',
      12,
    ])
  })

  it.skip('seva and juno produce different cache keys', async () => {
    // Defence-in-depth: switching tenants must NOT collide with cached results
    // for the other tenant. Each factory MUST distinguish on companyId.
    const { queryKeys } = await import(/* @vite-ignore */ queryKeysModulePath)
    expect(queryKeys.summaries('seva', 60)).not.toEqual(
      queryKeys.summaries('juno', 60),
    )
  })
})

// Once Wave 3 ships frontend/src/api/queryKeys.ts, REMOVE the `.skip` on each
// `it.skip(...)` above and the suite should pass GREEN.
