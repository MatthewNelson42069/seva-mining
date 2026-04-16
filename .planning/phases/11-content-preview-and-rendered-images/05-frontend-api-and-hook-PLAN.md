---
phase: 11-content-preview-and-rendered-images
plan: 05
type: execute
wave: 2
depends_on: [11-03]
files_modified:
  - frontend/src/api/content.ts
  - frontend/src/hooks/useContentBundle.ts
  - frontend/src/api/__tests__/content-bundle.test.ts
  - frontend/src/hooks/__tests__/useContentBundle.test.ts
autonomous: true
requirements: [CREV-02, CREV-06, CREV-08, CREV-09]

must_haves:
  truths:
    - "getContentBundle(id) calls GET /content-bundles/:id via apiFetch and returns a ContentBundleDetailResponse"
    - "rerenderContentBundle(id) calls POST /content-bundles/:id/rerender and returns a RerenderResponse"
    - "useContentBundle(bundleId) returns the TanStack Query result for the bundle"
    - "useContentBundle polls every 5000ms while rendered_images is empty AND bundle.created_at is within the last 10 minutes"
    - "useContentBundle stops polling once rendered_images.length >= 1"
    - "useContentBundle stops polling once bundle is older than 10 minutes"
    - "useContentBundle is disabled (no fetch) when bundleId is null, undefined, or empty string"
    - "useRerenderContentBundle is a useMutation hook that calls rerenderContentBundle and invalidates the content-bundle query key on success"
  artifacts:
    - path: "frontend/src/api/content.ts"
      provides: "API client functions for content-bundle detail + rerender"
      contains: "getContentBundle"
    - path: "frontend/src/hooks/useContentBundle.ts"
      provides: "TanStack Query hook with 5s polling and 10min ceiling"
      min_lines: 30
      exports: ["useContentBundle", "useRerenderContentBundle"]
  key_links:
    - from: "frontend/src/hooks/useContentBundle.ts"
      to: "frontend/src/api/content.ts"
      via: "import { getContentBundle, rerenderContentBundle }"
      pattern: "getContentBundle"
    - from: "useContentBundle refetchInterval"
      to: "query.state.data.rendered_images"
      via: "TanStack Query v5 callback signature"
      pattern: "query.state.data"
---

<objective>
Build the frontend data layer for the detail modal: API client functions, the polling hook, and the rerender mutation. The modal (Plan 06) consumes these hooks directly.

Purpose: CREV-02 (fetch full brief), CREV-06 (format-aware data shape available), CREV-08 (polling UX), CREV-09 (regen button mutation backend).

Output: Two new exports (`useContentBundle`, `useRerenderContentBundle`) with TanStack Query v5 semantics, plus real tests filling in the Plan 01 stubs.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/phases/11-content-preview-and-rendered-images/11-CONTEXT.md
@.planning/phases/11-content-preview-and-rendered-images/11-RESEARCH.md
@.planning/phases/11-content-preview-and-rendered-images/11-01-SUMMARY.md
@.planning/phases/11-content-preview-and-rendered-images/11-03-SUMMARY.md

<interfaces>
<!-- frontend/src/api/types.ts (after Plan 01) -->
```typescript
export interface ContentBundleDetailResponse {
  id: string
  story_headline: string
  story_url?: string
  source_name?: string
  content_type?: string
  score?: number
  quality_score?: number
  no_story_flag: boolean
  deep_research?: unknown
  draft_content?: unknown
  compliance_passed?: boolean
  rendered_images?: RenderedImage[] | null
  created_at: string
}

export interface RerenderResponse {
  bundle_id: string
  render_job_id: string
  enqueued_at: string
}

export interface RenderedImage {
  role: 'twitter_visual' | 'instagram_slide_1' | 'instagram_slide_2' | 'instagram_slide_3'
  url: string
  generated_at: string
}
```

<!-- Existing apiFetch pattern -->
```typescript
// frontend/src/api/client.ts
export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T>
```

<!-- TanStack Query v5 callback signature (RESEARCH §Pattern 5, §Pitfall 7) -->
```typescript
refetchInterval: (query) => {
  const data = query.state.data
  if (!data) return false
  // ... return number (ms) or false
}
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: API client — getContentBundle + rerenderContentBundle</name>
  <files>
    frontend/src/api/content.ts,
    frontend/src/api/__tests__/content-bundle.test.ts
  </files>
  <read_first>
    /Users/matthewnelson/seva-mining/frontend/src/api/content.ts,
    /Users/matthewnelson/seva-mining/frontend/src/api/client.ts,
    /Users/matthewnelson/seva-mining/frontend/src/api/__tests__/content-bundle.test.ts,
    /Users/matthewnelson/seva-mining/frontend/src/mocks/handlers.ts,
    /Users/matthewnelson/seva-mining/frontend/src/api/types.ts
  </read_first>
  <behavior>
    - Test 1 (getContentBundle fetches GET /content-bundles/:id): Given MSW handler returning a mock bundle with id="abc-123", await getContentBundle("abc-123") resolves to the mock object; the MSW handler received a GET to /content-bundles/abc-123.
    - Test 2 (getContentBundle throws on 404): When MSW returns 404, getContentBundle rejects with an error (apiFetch throws on non-2xx).
    - Test 3 (rerenderContentBundle posts to rerender path): Given MSW handler returning 202 with {bundle_id, render_job_id, enqueued_at}, await rerenderContentBundle("abc-123") resolves to that object; MSW received POST to /content-bundles/abc-123/rerender.
    - Test 4 (rerenderContentBundle throws on 404): When MSW returns 404, rerenderContentBundle rejects.
  </behavior>
  <action>
    Modify frontend/src/api/content.ts — extend with the two new functions (keep the existing getTodayContent):

      import { apiFetch } from './client'
      import type {
        ContentBundleResponse,
        ContentBundleDetailResponse,
        RerenderResponse,
      } from './types'

      export async function getTodayContent(): Promise<ContentBundleResponse> {
        return apiFetch<ContentBundleResponse>('/content/today')
      }

      export async function getContentBundle(
        id: string,
      ): Promise<ContentBundleDetailResponse> {
        return apiFetch<ContentBundleDetailResponse>(`/content-bundles/${id}`)
      }

      export async function rerenderContentBundle(
        id: string,
      ): Promise<RerenderResponse> {
        return apiFetch<RerenderResponse>(`/content-bundles/${id}/rerender`, {
          method: 'POST',
        })
      }

    Replace the describe.skip block in frontend/src/api/__tests__/content-bundle.test.ts with real tests (Tests 1–4). Use the existing MSW server setup pattern from other api test files — read the project for precedent. Use `server.use(http.get(...))` to override handlers per test where a 404 is needed.

    Each test should import from '../content' and assert on resolved/rejected promises.
  </action>
  <verify>
    <automated>cd /Users/matthewnelson/seva-mining/frontend && npx vitest run src/api/__tests__/content-bundle.test.ts</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "export async function getContentBundle" /Users/matthewnelson/seva-mining/frontend/src/api/content.ts` returns 1
    - `grep -c "export async function rerenderContentBundle" /Users/matthewnelson/seva-mining/frontend/src/api/content.ts` returns 1
    - `grep -c "method: 'POST'" /Users/matthewnelson/seva-mining/frontend/src/api/content.ts` returns 1
    - `grep -c "describe.skip" /Users/matthewnelson/seva-mining/frontend/src/api/__tests__/content-bundle.test.ts` returns 0
    - vitest reports 4 PASSED from content-bundle.test.ts
  </acceptance_criteria>
  <done>
    Two new API functions exported; existing getTodayContent unchanged; 4 tests pass via MSW.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: useContentBundle + useRerenderContentBundle hooks with polling</name>
  <files>
    frontend/src/hooks/useContentBundle.ts,
    frontend/src/hooks/__tests__/useContentBundle.test.ts
  </files>
  <read_first>
    /Users/matthewnelson/seva-mining/frontend/src/hooks/useQueue.ts,
    /Users/matthewnelson/seva-mining/frontend/src/hooks/useApprove.ts,
    /Users/matthewnelson/seva-mining/frontend/src/hooks/__tests__/useContentBundle.test.ts,
    /Users/matthewnelson/seva-mining/.planning/phases/11-content-preview-and-rendered-images/11-RESEARCH.md (§Pattern 5, §Pitfall 7)
  </read_first>
  <behavior>
    - Test 1 (polls every 5s while rendered_images empty and bundle <10min old): Render the hook with a mock bundle whose created_at is "now" and rendered_images=[]; advance vi.fake timers by 5000ms; assert queryFn was called at least twice.
    - Test 2 (stops polling once rendered_images has length >= 1): After bundle mock updates to include 1 image entry, refetchInterval returns false and no further queryFn calls fire after advancing timers.
    - Test 3 (stops polling after bundle is older than 10 minutes): Mock bundle with created_at set to 11 minutes ago; refetchInterval returns false immediately.
    - Test 4 (is disabled when bundleId is null): useContentBundle(null) → query.fetchStatus === 'idle' (enabled: false); queryFn is never called.
    - Test 5 (is disabled when bundleId is undefined): same as Test 4.
    - Test 6 (is disabled when bundleId is empty string): same.
    - Test 7 (useRerenderContentBundle fires POST and invalidates query): Call mutation.mutate("abc-123"); after mutation success, assert queryClient.invalidateQueries was called with queryKey ['content-bundle', 'abc-123'].
  </behavior>
  <action>
    Create frontend/src/hooks/useContentBundle.ts:

      import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
      import { getContentBundle, rerenderContentBundle } from '@/api/content'
      import type { ContentBundleDetailResponse, RerenderResponse } from '@/api/types'

      const POLL_INTERVAL_MS = 5000
      const MAX_POLL_WINDOW_MS = 10 * 60 * 1000 // 10 minutes (D-14)

      export function useContentBundle(bundleId: string | null | undefined) {
        return useQuery<ContentBundleDetailResponse>({
          queryKey: ['content-bundle', bundleId],
          queryFn: () => getContentBundle(bundleId as string),
          enabled: !!bundleId,
          refetchInterval: (query) => {
            const data = query.state.data
            if (!data) return false
            // Stop once at least one image has landed
            if (data.rendered_images && data.rendered_images.length > 0) return false
            // Stop after the 10-minute ceiling
            const age = Date.now() - new Date(data.created_at).getTime()
            if (age > MAX_POLL_WINDOW_MS) return false
            return POLL_INTERVAL_MS
          },
        })
      }

      export function useRerenderContentBundle(bundleId: string) {
        const queryClient = useQueryClient()
        return useMutation<RerenderResponse, Error, void>({
          mutationFn: () => rerenderContentBundle(bundleId),
          onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['content-bundle', bundleId] })
          },
        })
      }

    Replace the describe.skip in frontend/src/hooks/__tests__/useContentBundle.test.ts with real tests (Tests 1–7). Use the `renderHook` utility from `@testing-library/react` and a fresh `QueryClientProvider` wrapper per test. For timer-based tests use `vi.useFakeTimers()` + `vi.advanceTimersByTimeAsync(5000)`. For Test 7, mock the POST via MSW and spy on queryClient.invalidateQueries.

    Boilerplate per test:
      const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
      const wrapper = ({ children }) => <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
      const { result } = renderHook(() => useContentBundle('abc-123'), { wrapper })
  </action>
  <verify>
    <automated>cd /Users/matthewnelson/seva-mining/frontend && npx vitest run src/hooks/__tests__/useContentBundle.test.ts</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "export function useContentBundle" /Users/matthewnelson/seva-mining/frontend/src/hooks/useContentBundle.ts` returns 1
    - `grep -c "export function useRerenderContentBundle" /Users/matthewnelson/seva-mining/frontend/src/hooks/useContentBundle.ts` returns 1
    - `grep -c "query.state.data" /Users/matthewnelson/seva-mining/frontend/src/hooks/useContentBundle.ts` returns ≥ 1 (v5 signature per Pitfall 7)
    - `grep -c "10 \* 60 \* 1000\|MAX_POLL_WINDOW_MS" /Users/matthewnelson/seva-mining/frontend/src/hooks/useContentBundle.ts` returns ≥ 1
    - `grep -c "POLL_INTERVAL_MS\|5000" /Users/matthewnelson/seva-mining/frontend/src/hooks/useContentBundle.ts` returns ≥ 1
    - `grep -c "describe.skip" /Users/matthewnelson/seva-mining/frontend/src/hooks/__tests__/useContentBundle.test.ts` returns 0
    - vitest reports 7 PASSED from useContentBundle.test.ts
    - Full frontend suite: `cd frontend && npm run test -- --run` — no regressions
  </acceptance_criteria>
  <done>
    Hook correctly polls with 5s interval, stops on image arrival, stops on age ceiling, and is disabled for falsy bundleIds. Mutation invalidates the query on success. 7 tests pass.
  </done>
</task>

</tasks>

<verification>
- `cd frontend && npm run test -- --run` — full suite green
- TypeScript: `cd frontend && npx tsc --noEmit` exits 0
</verification>

<success_criteria>
- Two new API client functions work end-to-end with MSW
- useContentBundle has correct polling semantics per D-12 and D-14
- useRerenderContentBundle invalidates the cache on success
- TanStack Query v5 callback signature is used correctly (Pitfall 7 avoided)
</success_criteria>

<output>
Create `.planning/phases/11-content-preview-and-rendered-images/11-05-SUMMARY.md` noting:
- Final signature of both hooks
- Whether any edge cases in refetchInterval semantics were surfaced during testing
- Patterns Plan 06 should follow when wiring these hooks into the modal
</output>
