import { describe, it } from 'vitest'

// Wave 0 stub — skip until useContentBundle exists (Plan 05)
describe.skip('useContentBundle (Plan 11-05)', () => {
  it('polls every 5s while rendered_images is empty and bundle is <10min old', () => {})
  it('stops polling once rendered_images has length >= 1', () => {})
  it('stops polling after bundle is older than 10 minutes', () => {})
  it('is disabled when bundleId is null/undefined', () => {})
})
