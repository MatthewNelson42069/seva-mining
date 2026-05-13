---
phase: quick-260506-gmg
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - frontend/src/components/layout/AppShell.tsx
  - frontend/src/components/layout/AppHeader.tsx
  - frontend/src/components/layout/__tests__/AppHeader.test.tsx
  - frontend/src/pages/SummaryFeedPage.tsx
autonomous: false
requirements:
  - GMG-01
  - GMG-02
  - GMG-03
---

<objective>
Replace the v1.0 `<Sidebar />` chrome with a minimal top header on every authenticated page so the v2.0 root feed matches the locked "Instagram feed, very simple UI" CONTEXT.md spec from milestone v2.0.

Purpose: The v2.0 milestone shipped the SummaryFeedPage as the new `/` (Phase 1, Plan 06), but the surrounding `AppShell` still mounts the v1.0 220px Sidebar — leaving the root view looking like the old multi-agent dashboard instead of the locked Instagram-feed aesthetic. This polish PR retires the sidebar from page chrome (file kept as dead code per v2.0 retirement discipline) and replaces it with a small "Seva Mining" brand header + subtle "Log out" link.

Output: One new `AppHeader` component, a slimmer `AppShell` that drops `<Sidebar />` and the `min-w-[1280px]` constraint, a re-widened `SummaryFeedPage` (max-w-2xl → max-w-[720px] per locked spec), one new unit test for `AppHeader`, and a human verification checkpoint.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@frontend/src/components/layout/AppShell.tsx
@frontend/src/components/layout/Sidebar.tsx
@frontend/src/pages/SummaryFeedPage.tsx
@frontend/src/pages/DigestPage.tsx
@frontend/src/pages/SettingsPage.tsx
@frontend/src/stores/slices/authSlice.ts
@frontend/src/pages/__tests__/SummaryFeedPage.test.tsx

<interfaces>
<!-- Key contracts the executor needs. Do not go hunting in the codebase. -->

From frontend/src/stores/slices/authSlice.ts:
```typescript
export interface AuthSlice {
  token: string | null
  isAuthenticated: boolean
  setToken: (token: string) => void
  clearToken: () => void
}
```

Logout pattern (from current Sidebar.tsx — replicate this exact sequence in AppHeader):
```typescript
import { useNavigate } from 'react-router-dom'
import { useAppStore } from '@/stores'

const navigate = useNavigate()
const clearToken = useAppStore((s) => s.clearToken)

function handleLogout() {
  clearToken()
  navigate('/login')
}
```

Brand mark pattern (from current Sidebar.tsx lines 47-52 — preserve the amber "S" + "Seva Mining" wordmark, but downsize for header):
```tsx
<div className="w-7 h-7 rounded-md bg-amber-500 flex items-center justify-center shrink-0">
  <span className="text-xs font-bold text-zinc-900">S</span>
</div>
<span className="text-sm font-semibold text-white">Seva Mining</span>
```

Current AppShell (the surgical edit point):
```tsx
// frontend/src/components/layout/AppShell.tsx
<div className="min-h-screen bg-background flex min-w-[1280px]">
  <Sidebar />
  <main className="flex-1 overflow-auto">
    <Outlet />
  </main>
</div>
```

Existing utility:
```typescript
// frontend/src/lib/utils.ts
export function cn(...inputs: ClassValue[]): string  // standard shadcn cn() helper
```
</interfaces>

**Key facts gathered during planning:**
- `DigestPage.tsx` (line 238) already renders its own `<h1>Daily Digest</h1>` page-title header — the new global header sits ABOVE that, no conflict.
- `SettingsPage.tsx` (line 12) already renders its own `<h1>Settings</h1>` page-title header — same, no conflict.
- `SummaryFeedPage.tsx` is currently `max-w-2xl mx-auto` (672px). Locked spec is **720px** — change to `max-w-[720px]`.
- `min-w-[1280px]` on AppShell's outer div was a v1.0 wide-layout artifact; with the sidebar gone it must be removed or it forces horizontal scroll on a centered 720px column.
- Existing test file `SummaryFeedPage.test.tsx` does NOT assert on layout chrome — its 5 tests will continue to pass after this change. No test edits required there.
- `Sidebar.tsx` source file is left intact on disk per v2.0 retirement discipline (mirrors how Twitter/long_form sub-agent files were handled in `260420-sn9` / `260423-k8n`). Just stop importing it from `AppShell.tsx`.
- React 19 + Tailwind v4 + shadcn — use existing primitives. The Sidebar's logout button used a plain `<button>` with Tailwind classes (no shadcn `<Button>`); the AppHeader's "Log out" should use the same lightweight approach so it reads as a subtle link, not a CTA.

</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Create AppHeader component + retire Sidebar from AppShell + widen feed to 720px</name>
  <files>
    frontend/src/components/layout/AppHeader.tsx (new)
    frontend/src/components/layout/__tests__/AppHeader.test.tsx (new)
    frontend/src/components/layout/AppShell.tsx (edit)
    frontend/src/pages/SummaryFeedPage.tsx (edit)
  </files>
  <behavior>
    AppHeader.test.tsx — write these tests FIRST, watch them fail, then implement:
    - Test 1: Renders the "Seva Mining" wordmark text.
    - Test 2: Renders the amber "S" logo mark (assert by class on the brand container OR by aria-hidden span; pick a stable selector — `getByText('S')` inside the brand block is acceptable).
    - Test 3: Renders a "Log out" control (assert `getByRole('button', { name: /log out/i })` OR `getByText(/log out/i)` — whichever matches the impl).
    - Test 4: Clicking "Log out" calls `clearToken` (mock the zustand store via `vi.mock('@/stores', ...)` returning `{ useAppStore: (selector) => selector({ clearToken: mockFn, ... }) }`) AND triggers navigation to `/login` (mock `useNavigate` from `react-router-dom`).

    Test wrapper must include `<MemoryRouter>` from react-router-dom because the component uses `useNavigate`.
  </behavior>
  <action>
    **STEP A — Write failing tests FIRST (RED):**
    Create `frontend/src/components/layout/__tests__/AppHeader.test.tsx` with the 4 tests described in `<behavior>`. Use vitest + @testing-library/react. Follow the same import/wrapper style used in `frontend/src/pages/__tests__/SummaryFeedPage.test.tsx` for consistency. Run `npm test -- AppHeader` from `frontend/` and confirm tests fail because the component doesn't exist yet.

    **STEP B — Implement AppHeader (GREEN):**
    Create `frontend/src/components/layout/AppHeader.tsx`. Requirements:
    - Default export NOT required; use `export function AppHeader()` (matches Sidebar.tsx convention).
    - Renders a thin sticky/fixed-top bar across the full viewport width with a centered inner row constrained to `max-w-[720px]` so the brand mark and logout control align with the feed column underneath.
    - Outer bar: `border-b border-zinc-800 bg-zinc-900` (matches existing Sidebar palette so it doesn't fight the dark theme — verify against the running app screenshot during checkpoint, swap to `bg-background` + `border-border` if the rest of the app is light-themed).
    - Inner row: `max-w-[720px] mx-auto px-4 py-3 flex items-center justify-between`.
    - Left: brand mark (amber "S" square + "Seva Mining" wordmark) using the exact pattern from `<interfaces>` above. Slightly downsize if it feels heavy in the bar — the Sidebar version uses `w-7 h-7`; keep that or drop to `w-6 h-6`, your call.
    - Right: `<button onClick={handleLogout}>` with classes `text-sm text-zinc-400 hover:text-zinc-100 transition-colors` (subtle, not a CTA — locked spec says "subtle 'Log out' link/button"). No icon (the v1.0 Sidebar used `<LogOut />` from lucide; the locked spec is more minimal — drop the icon).
    - Logout handler: replicate the exact pattern from `<interfaces>` — `clearToken()` then `navigate('/login')`.
    - Do NOT use shadcn `<Button>` here — that's a CTA primitive and would over-style this control. A plain `<button>` with Tailwind matches the "subtle link" intent.

    Run `npm test -- AppHeader` and confirm all 4 tests pass.

    **STEP C — Wire AppHeader into AppShell + retire Sidebar:**
    Edit `frontend/src/components/layout/AppShell.tsx`:
    - Remove the `import { Sidebar } from './Sidebar'` line. (Do NOT delete `Sidebar.tsx` — it stays on disk as dead code per v2.0 retirement discipline; consistent with `260423-k8n` and `260420-sn9` precedent.)
    - Add `import { AppHeader } from './AppHeader'`.
    - Replace the layout body. New structure:
      ```tsx
      <div className="min-h-screen bg-background flex flex-col">
        <AppHeader />
        <main className="flex-1 overflow-auto">
          <Outlet />
        </main>
      </div>
      ```
    - Drop `min-w-[1280px]` (v1.0 wide-layout artifact). Drop `flex` in favor of `flex flex-col` (vertical stack: header on top, main below).

    **STEP D — Widen feed to locked 720px:**
    Edit `frontend/src/pages/SummaryFeedPage.tsx`. In all four return blocks (loading / error / empty / success), change `max-w-2xl` → `max-w-[720px]`. Keep `mx-auto py-8 px-4`. Do NOT touch SummaryCard, SectionBlock, or the empty-state copy ("Waiting for first summary. Next fire at {next_fire}.").

    **STEP E — Verify nothing broke (REFACTOR/VERIFY):**
    From `frontend/`, run `npm test` (full suite). Run `npm run build` (type-check + Vite build) — must succeed without errors. The 5 existing `SummaryFeedPage.test.tsx` tests must still pass (they don't assert on layout chrome).
  </action>
  <verify>
    <automated>cd frontend && npm test -- AppHeader SummaryFeedPage --run && npm run build</automated>
  </verify>
  <done>
    - `AppHeader.tsx` exists and exports `AppHeader`.
    - `AppHeader.test.tsx` exists with 4 passing tests.
    - `AppShell.tsx` no longer imports `Sidebar`; renders `<AppHeader />` above `<Outlet />`; no `min-w-[1280px]`.
    - `SummaryFeedPage.tsx` uses `max-w-[720px]` in all 4 return blocks; empty-state copy unchanged.
    - `Sidebar.tsx` source file untouched on disk (verify with `git status` — Sidebar.tsx should NOT appear in changed files).
    - `npm test` passes for both the new AppHeader tests and the existing SummaryFeedPage tests.
    - `npm run build` succeeds with no TypeScript errors.
  </done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 2: Human verification — visual + functional check</name>
  <what-built>
    - New top-bar `AppHeader` component (amber "S" logo + "Seva Mining" wordmark on left, subtle "Log out" link on right)
    - Sidebar removed from page chrome on `/`, `/digest`, `/settings` (Sidebar.tsx file still on disk)
    - Feed column re-widened from 672px → 720px to match locked spec
    - All existing tests still passing; full TypeScript build succeeds
  </what-built>
  <how-to-verify>
    1. From `frontend/`, run `npm run dev` and open http://localhost:5173
    2. Log in if not already authenticated
    3. **Verify `/` (root feed)**:
       - No 220px sidebar on the left — the page is a single centered column
       - Top of page has a thin bar with: amber "S" + "Seva Mining" on the left, "Log out" on the right
       - Empty state text reads exactly: "Waiting for first summary. Next fire at HH:MM PT." (where HH:MM is 08:00 or 12:00)
       - When summaries exist, the column reads at ~720px wide (slightly wider than before)
       - SummaryCards render unchanged (no styling regressions)
    4. **Verify `/digest`**: Direct-navigate. The new top header appears; below it, the existing "Daily Digest" page renders normally with its own h1, stats grid, and stories list. No sidebar.
    5. **Verify `/settings`**: Direct-navigate. The new top header appears; below it, the existing "Settings" page renders normally with its tab bar (Keywords / Scoring / Notifications / Agent Runs / Schedule). No sidebar.
    6. **Verify logout**: Click "Log out" in the header. Should navigate to `/login` and the form should appear. Re-enter password to confirm full round-trip works.
    7. **Verify retired routes still redirect**: Direct-navigate to `/queue` and `/agents/threads` — both should redirect to `/` (FEED-04 bookmark-grace, unchanged).
    8. Visually confirm: no horizontal scrollbar, no `min-w-[1280px]` artifact forcing wide layout, header bar reads as "subtle" (not a heavy CTA stripe).
  </how-to-verify>
  <resume-signal>Type "approved" to mark complete, or describe any visual/functional issues to fix.</resume-signal>
</task>

</tasks>

<verification>
- `npm test` passes (existing 5 SummaryFeedPage tests + 4 new AppHeader tests, all green)
- `npm run build` succeeds with zero TypeScript errors
- `git status` shows: AppShell.tsx (M), SummaryFeedPage.tsx (M), AppHeader.tsx (??), AppHeader.test.tsx (??). Sidebar.tsx must NOT appear (left intact on disk).
- Visual checkpoint approved by human (Task 2)
</verification>

<success_criteria>
- Root `/` route renders as a single centered 720px column with no sidebar chrome
- Minimal top header (logo + name on left, "Log out" on right) appears across `/`, `/digest`, `/settings`
- Logout button signs the user out and routes to `/login`
- Empty-state copy preserved verbatim: "Waiting for first summary. Next fire at {next_cron_PT}."
- Sidebar.tsx source file retained on disk as dead code
- All existing tests still passing; full TypeScript build green
- Human visual check approved
</success_criteria>

<output>
After completion, create `.planning/quick/260506-gmg-remove-v1-0-sidebar-and-add-minimal-head/260506-gmg-SUMMARY.md` documenting:
- Files changed (with brief reason)
- Files left intentionally unchanged (Sidebar.tsx as dead code; DigestPage and SettingsPage page-titles untouched because they already had their own h1s)
- Verification results (test counts, build status, screenshot reference if captured)
</output>
