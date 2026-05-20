# Phase 13 — Deferred items (out of scope for current plan)

## Discovered during 13-01 execution

### Pre-existing lint errors (NOT introduced by Plan 13-01)

`npm run lint` in `frontend/` reports 15 pre-existing errors across these test files (none touched by Plan 13-01):

- `frontend/src/pages/__tests__/SummaryFeedPage.test.tsx` — 6 errors (`react/display-name`, `@typescript-eslint/no-explicit-any` x5)
- Other test files — 9 additional errors (display-name + explicit-any + react-refresh)
- Script exit code is 0, so they do not block CI.
- None of the errors reference `companyBrandConfig.ts` or `useCompanyBrand.ts` (the only files Plan 13-01 added).

These are not regressions; they predate Plan 13-01. Cleanup is out of scope for Plan 13-01 (scope: foundation files only). A future hygiene phase can address them.
