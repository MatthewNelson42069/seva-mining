# Phase 3: React Approval Dashboard - Research

**Researched:** 2026-03-31
**Domain:** React 19 + Vite 6 + Tailwind v4 + shadcn/ui — greenfield frontend approval dashboard
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Card Layout**
- D-01: Full-width stack layout — one card per row, full width, everything visible without clicking. Linear issues / Notion database style.
- D-02: Draft alternatives displayed as tabs within each card (Draft A / Draft B / RT Quote). One visible at a time, click to switch. Keeps card height consistent.
- D-03: Urgency communicated by sort order only — most urgent cards at top. No color-coded borders, countdown badges, or background tints.
- D-04: Original post excerpt shows first 2 lines (~140 chars), click to expand for full text.
- D-05: Rationale collapsed by default — small "Why this post?" toggle. Expand when curious.
- D-06: Score displayed as numeric badge (8.7/10) in card header. Clean number, no color coding.
- D-07: Related cards (DASH-08) use a badge approach — "Also on Instagram" or "Also on Twitter" badge. Clicking navigates to the related card. Doesn't break urgency sorting.
- D-08: Content tab uses summary card + expand modal — headline, format choice, credibility score on the card. Click to open focused reading modal with full draft and all sources.

**Interaction Flow**
- D-09: Approve/reject triggers fade-out animation (300ms) + toast confirmation ("Approved — copied to clipboard" or "Rejected"). Undo available for 5 seconds.
- D-10: Inline editing — click draft text to enter edit mode (textarea expands, border highlights). Read-only by default. "Edit + Approve" saves edit and approves in one action.
- D-11: Rejection UX — click Reject opens inline dropdown with 5 category radio buttons (off-topic, low-quality, bad-timing, tone-wrong, duplicate) + optional notes textarea + Confirm Reject button.

**Visual Identity**
- D-12: Light mode only — clean white background, dark text. No dark mode toggle.
- D-13: Blue accent color (Linear-style) for buttons, active tabs, highlights. Classic SaaS blue, neutral, professional.
- D-14: Login page — Claude's discretion.

**Dashboard Chrome**
- D-15: Top tabs + sidebar combo — platform tabs (Twitter/Instagram/Content with badge counts) at top for the queue, sidebar for other pages (Digest, Content Review, Settings).
- D-16: Empty state shows "Queue is clear" with agent last run time and next run countdown.

**Mock Data**
- D-17: Pre-seed the database with 10-15 realistic gold sector draft items across all platforms.

**Stack (locked)**
- React 19 + Vite 6 + Tailwind v4 + shadcn/ui (tailwind-v4 branch / `npx shadcn@latest init`)
- TanStack Query v5 for server state
- Zustand v5 for UI state
- Vitest for testing

### Claude's Discretion
- Login page design (D-14): simplest approach matching overall aesthetic, single password field, no username
- Sidebar layout details and page routing
- Animation easing and timing details
- Typography scale and spacing
- Card border, shadow, and spacing within the Linear/Notion aesthetic
- Toast positioning and styling
- Modal design for content review

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.

</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DASH-01 | Separate tabs for Twitter, Instagram, and Content | TanStack Query per-tab query keys; shadcn/ui Tabs component; badge counts from `GET /queue?platform=X&status=pending` counts |
| DASH-02 | Feed/timeline layout sorted by urgency within each tab | Backend sorts by `created_at` DESC already (most recent = highest urgency); `useInfiniteQuery` cursor pagination |
| DASH-03 | Each card shows platform badge, source excerpt, account info, all draft alternatives, rationale, urgency, final score | `DraftItemResponse` schema has all fields; `alternatives` is JSONB array; inner-card tab pattern for Draft A/B/RT |
| DASH-04 | Three action buttons per card: Approve, Edit + Approve, Reject | `PATCH /items/{id}/approve` (with optional `edited_text`) and `PATCH /items/{id}/reject` (with `category`); `useMutation` per action |
| DASH-05 | Inline editing of draft text directly on the card | Click-to-edit textarea pattern in Zustand UI state; `edited_text` passed to approve endpoint |
| DASH-06 | One-click copy to clipboard of approved/edited draft text with toast confirmation | `navigator.clipboard.writeText()`; Sonner toast "Approved — copied to clipboard"; triggered on approve success |
| DASH-07 | Direct link to original post opens in new tab | `source_url` field on `DraftItemResponse`; `<a target="_blank" rel="noopener noreferrer">` |
| DASH-08 | Related cards (same story across platforms) visually linked | `related_id` field on `DraftItemResponse`; badge linking to sibling card in the same queue via scroll/navigation |
| DASH-09 | Desktop-only layout (no mobile responsiveness required) | Fixed min-width layout (~1280px); no responsive breakpoints needed |
| DASH-10 | Clean minimal design — Linear/Notion aesthetic, content-focused, lots of white space | shadcn/ui + Tailwind v4 tokens; light mode only (D-12); blue accent (D-13) |

</phase_requirements>

---

## Summary

Phase 3 builds a greenfield React dashboard — the first frontend in this project. There is no existing React code to extend; everything starts from `npm create vite@latest`. The backend is fully operational (Phase 2 complete) with 13 JWT-authenticated endpoints ready to consume. All data shapes are defined in Pydantic schemas. The frontend's only job is to make those endpoints feel good to use.

The stack is locked: React 19, Vite 6, Tailwind v4, shadcn/ui (current CLI, which targets v4 by default), TanStack Query v5, and Zustand v5. The key research finding is that **shadcn/ui's main CLI (`npx shadcn@latest init`) now defaults to Tailwind v4 + React 19** — the old "tailwind-v4 branch" caveat from CLAUDE.md is no longer a separate concern. The `toast` component is deprecated; use **Sonner** instead. The `new-york` style is the new default.

The approval workflow has two critical state management layers: (1) TanStack Query manages server state — queue items fetched per platform, optimistic removal on approve/reject; (2) Zustand manages UI state — which card is in edit mode, which draft alternative tab is active, rejection panel open/closed. These never mix: Zustand never stores server data.

**Primary recommendation:** Bootstrap with `npm create vite@latest frontend -- --template react-ts`, configure Tailwind v4 via the `@tailwindcss/vite` plugin, run `npx shadcn@latest init` (new-york style), then build the approval card as the core component from which everything else derives.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| React | 19.2.4 | UI framework | Locked decision; removes `forwardRef` need; concurrent rendering |
| Vite | 8.0.3 (vite pkg) | Build tool + dev server | Locked; SWC transformer, HMR, first-class ESM |
| TypeScript | 5.x (via vite template) | Type safety | Standard for React 19 projects; catches schema mismatches at compile time |
| Tailwind CSS | 4.2.2 | Utility CSS | Locked; Vite plugin, no PostCSS config, CSS-native variables |
| @tailwindcss/vite | 4.2.2 | Tailwind v4 Vite integration | Replaces PostCSS pipeline; add as `plugins: [tailwindcss()]` in vite.config.ts |
| shadcn/ui | latest (via CLI) | Copy-paste component library | Locked; Radix UI primitives, fully composable with Tailwind v4 |
| TanStack Query | 5.96.0 | Server state management | Locked; caching, background refetch, optimistic updates, cursor pagination |
| Zustand | 5.0.12 | UI/client state | Locked; active tab, edit mode, inline panels |
| react-router-dom | 7.13.2 | Client-side routing | Standard SPA routing; v7 is non-breaking upgrade from v6 patterns |
| date-fns | 4.1.0 | Date/time formatting | Locked in CLAUDE.md; recency display, timestamp formatting |
| sonner | (via shadcn `npx shadcn@latest add sonner`) | Toast notifications | Replaces deprecated shadcn `toast`; handles "Approved — copied to clipboard" |
| lucide-react | 1.7.0 | Icon set | Ships with shadcn/ui; consistent icon library |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| @tanstack/react-query-devtools | 5.x | Query cache inspector | Dev only; wrap `<QueryClientProvider>` with it |
| tw-animate-css | latest | CSS animations | Replaces `tailwindcss-animate`; ships with new shadcn installs |
| @types/node | latest | Node types for vite.config.ts | Required for `path.resolve(__dirname, ...)` in alias setup |
| zustand/react/shallow | (bundled) | Shallow comparison for selectors | Prevents unnecessary re-renders when selecting multiple state keys |
| msw | 2.12.14 | API mock for tests | Node.js `setupServer` for Vitest; intercepts fetch calls |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| sonner (toast) | shadcn `toast` component | `toast` is deprecated in shadcn v4; sonner is the replacement |
| react-router-dom v7 | TanStack Router | TanStack Router adds complexity; React Router v7 is battle-tested and sufficient for this app's simple routing needs |
| Zustand slices pattern | Multiple separate Zustand stores | Slices keep one combined store; better for this app's interconnected UI state (active card edit affects multiple components) |
| Vitest | Jest | Vitest is native to Vite; no transform config needed; Jest requires additional setup for ESM |

**Installation (bootstrap sequence):**

```bash
# 1. Create project
npm create vite@latest frontend -- --template react-ts
cd frontend && npm install

# 2. Tailwind v4
npm install -D tailwindcss @tailwindcss/vite @types/node

# 3. shadcn/ui (new-york style, Tailwind v4 default)
npx shadcn@latest init

# 4. Core runtime dependencies
npm install @tanstack/react-query zustand react-router-dom date-fns

# 5. Dev tooling
npm install -D vitest @testing-library/react @testing-library/user-event @testing-library/jest-dom jsdom msw @tanstack/react-query-devtools

# 6. shadcn components needed for this phase
npx shadcn@latest add button badge tabs dialog sonner separator
npx shadcn@latest add radio-group textarea
```

**Version verification (confirmed 2026-03-31 via npm registry):**

| Package | Verified Version |
|---------|-----------------|
| react | 19.2.4 |
| vite | 8.0.3 |
| tailwindcss | 4.2.2 |
| @tailwindcss/vite | 4.2.2 |
| @tanstack/react-query | 5.96.0 |
| zustand | 5.0.12 |
| react-router-dom | 7.13.2 |
| date-fns | 4.1.0 |
| vitest | 4.1.2 |
| msw | 2.12.14 |

---

## Architecture Patterns

### Recommended Project Structure

```
frontend/
├── src/
│   ├── api/                  # API client functions (typed, one file per resource)
│   │   ├── client.ts         # axios/fetch base + JWT header injection
│   │   ├── queue.ts          # getQueue, approveItem, rejectItem
│   │   ├── auth.ts           # login
│   │   └── digests.ts        # getLatestDigest, getDigestByDate
│   ├── components/
│   │   ├── ui/               # shadcn copy-paste components (DO NOT EDIT)
│   │   ├── approval/         # ApprovalCard, DraftTabBar, InlineEditor, RejectPanel
│   │   ├── layout/           # AppShell, Sidebar, PlatformTabBar
│   │   └── shared/           # ScoreBadge, PlatformBadge, RelatedCardBadge
│   ├── pages/
│   │   ├── LoginPage.tsx
│   │   ├── QueuePage.tsx     # main approval queue
│   │   ├── DigestPage.tsx
│   │   ├── ContentPage.tsx
│   │   └── SettingsPage.tsx  # stub for Phase 8
│   ├── stores/
│   │   ├── index.ts          # combined Zustand store
│   │   └── slices/
│   │       ├── queueUiSlice.ts    # activeEditCardId, activeDraftTab per card
│   │       └── authSlice.ts       # token, isAuthenticated
│   ├── hooks/
│   │   ├── useQueue.ts       # useInfiniteQuery wrapper per platform
│   │   ├── useApprove.ts     # useMutation for approve
│   │   └── useReject.ts      # useMutation for reject
│   ├── lib/
│   │   └── utils.ts          # shadcn cn() utility
│   ├── mocks/
│   │   ├── handlers.ts       # MSW request handlers
│   │   └── node.ts           # MSW server for Vitest
│   ├── seed/
│   │   └── seedData.ts       # 10-15 gold sector mock DraftItem objects + seed script
│   ├── main.tsx
│   └── App.tsx
├── index.html
├── vite.config.ts            # tailwindcss() plugin + path alias @/*
├── tsconfig.json             # baseUrl + paths for @/* alias
├── tsconfig.app.json         # same alias config (Vite splits TS config)
└── components.json           # shadcn config (new-york, tailwind v4)
```

### Pattern 1: TanStack Query Per-Platform Queue Fetching

**What:** Each platform tab (Twitter, Instagram, Content) gets its own `useInfiniteQuery` with a distinct query key. Items are removed from cache optimistically on approve/reject, then invalidated to refetch.

**When to use:** Any time the queue needs to be fetched, displayed, or mutated.

```typescript
// Source: TanStack Query v5 docs — https://tanstack.com/query/v5/docs/react/guides/infinite-queries
import { useInfiniteQuery } from '@tanstack/react-query'
import { getQueue } from '@/api/queue'

export function useQueue(platform: 'twitter' | 'instagram' | 'content') {
  return useInfiniteQuery({
    queryKey: ['queue', platform],
    queryFn: ({ pageParam }) => getQueue({ platform, cursor: pageParam }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
  })
}
```

### Pattern 2: Zustand UI State — Never Store Server Data

**What:** Zustand holds only ephemeral UI state. Server data (queue items) lives in TanStack Query cache only.

**When to use:** Edit mode per card, active draft tab per card, rejection panel visibility, auth token.

```typescript
// Source: Zustand v5 slices pattern
import { create } from 'zustand'
import { useShallow } from 'zustand/react/shallow'

interface QueueUiState {
  editingCardId: string | null
  rejectionPanelCardId: string | null
  activeDraftTab: Record<string, number>  // cardId -> tab index
  setEditingCard: (id: string | null) => void
  setRejectionPanel: (id: string | null) => void
  setActiveDraftTab: (cardId: string, tabIndex: number) => void
}

// Usage with shallow to avoid full-store re-renders:
const { editingCardId, setEditingCard } = useQueueUiStore(
  useShallow((s) => ({ editingCardId: s.editingCardId, setEditingCard: s.setEditingCard }))
)
```

### Pattern 3: Optimistic Card Removal on Approve/Reject

**What:** When the operator clicks Approve or Reject, the card visually fades out immediately (CSS transition 300ms). The TanStack Query cache is then invalidated after the mutation completes.

**When to use:** Approve and Reject mutations.

```typescript
// Source: TanStack Query v5 optimistic updates — https://tanstack.com/query/latest/docs/framework/react/guides/optimistic-updates
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { approveItem } from '@/api/queue'

export function useApprove(platform: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, editedText }: { id: string; editedText?: string }) =>
      approveItem(id, editedText),
    onSuccess: (data, variables) => {
      // Copy approved text to clipboard (DASH-06)
      navigator.clipboard.writeText(variables.editedText ?? data.alternatives[0] ?? '')
      // Invalidate to remove card from queue
      queryClient.invalidateQueries({ queryKey: ['queue', platform] })
    },
  })
}
```

### Pattern 4: Undo Window via setTimeout + Toast

**What:** On approve/reject, show a Sonner toast with an undo action. A 5-second `setTimeout` actually submits to the API. If the user clicks Undo, the timeout is cleared and the card fades back in.

**When to use:** D-09 — fade-out + 5s undo.

```typescript
// Pattern: staged approval with undo
const [pendingApproval, setPendingApproval] = useState<{
  id: string; timeoutId: ReturnType<typeof setTimeout>
} | null>(null)

function handleApprove(id: string) {
  // Start fade animation immediately (CSS class)
  setFadingCardId(id)
  const timeoutId = setTimeout(() => {
    approveMutation.mutate({ id })
    setPendingApproval(null)
  }, 5000)
  setPendingApproval({ id, timeoutId })
  toast('Approved — copied to clipboard', {
    action: { label: 'Undo', onClick: () => {
      clearTimeout(timeoutId)
      setFadingCardId(null)
      setPendingApproval(null)
    }}
  })
}
```

### Pattern 5: Protected Routes with localStorage JWT

**What:** JWT is stored in `localStorage` after login. An `AuthProvider` context reads it on mount. Protected routes redirect to `/login` if token is absent or expired.

**When to use:** All routes except `/login`.

```typescript
// react-router-dom v7 pattern — https://reactrouter.com/
import { Navigate, Outlet } from 'react-router-dom'

function ProtectedRoute() {
  const token = localStorage.getItem('access_token')
  return token ? <Outlet /> : <Navigate to="/login" replace />
}
```

### Pattern 6: shadcn/ui Vite + Tailwind v4 Config

**What:** Tailwind v4 uses `@tailwindcss/vite` plugin — no `tailwind.config.js`, no PostCSS, no three-directive imports.

**When to use:** Project bootstrap only.

```typescript
// vite.config.ts — Source: https://ui.shadcn.com/docs/installation/vite
import path from 'path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
  },
})
```

```css
/* src/index.css — Tailwind v4 import (replaces three-directive setup) */
@import "tailwindcss";
```

### Pattern 7: API Client with JWT Injection

**What:** A single `client.ts` wraps `fetch` (or a thin axios instance) and injects the Bearer token on every request. All API functions import from this client.

```typescript
// src/api/client.ts
const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem('access_token')
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  })
  if (res.status === 401) {
    localStorage.removeItem('access_token')
    window.location.href = '/login'
    throw new Error('Unauthorized')
  }
  if (!res.ok) throw new Error(`API error ${res.status}`)
  return res.json() as Promise<T>
}
```

### Anti-Patterns to Avoid

- **Storing queue items in Zustand:** Any server data in Zustand will go stale when TanStack Query refetches. Keep them separate.
- **Calling `tailwindcss` as PostCSS plugin with Tailwind v4:** v4 uses the Vite plugin. Do not install `postcss` or create `postcss.config.js`.
- **Using shadcn `toast` component:** It is deprecated. Use `sonner` only.
- **Installing both `tailwindcss-animate` and `tw-animate-css`:** shadcn now uses `tw-animate-css`. Remove `tailwindcss-animate` if it appears in devDependencies.
- **Mixing v1-style shadcn init (old `tailwind-v4` branch flag):** The current `npx shadcn@latest init` handles Tailwind v4 automatically. No branch selection needed.
- **Dark mode setup:** D-12 says light mode only. Do not configure dark mode variants in Tailwind or shadcn. Remove `class` dark mode strategy.
- **Putting the `test` block in `vite.config.ts` without `/// <reference types="vitest" />`:** Without the triple-slash reference, TypeScript won't recognize the `test` property.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Accessible tabs (inner-card draft tabs, top platform tabs) | Custom div+click tabs | `shadcn/ui Tabs` (Radix UI `@radix-ui/react-tabs`) | Keyboard nav, ARIA roles, focus management — complex to get right |
| Toast notifications with undo action | Custom toast stack | `sonner` via shadcn | Handles stacking, auto-dismiss, action callbacks, a11y |
| Clipboard copy | Custom execCommand | `navigator.clipboard.writeText()` | `execCommand` is deprecated; Clipboard API is standard |
| Modal/dialog for content review (D-08) | Custom overlay | `shadcn/ui Dialog` (Radix `@radix-ui/react-dialog`) | Focus trap, scroll lock, keyboard dismiss |
| Radio group for rejection categories (D-11) | Custom radio buttons | `shadcn/ui RadioGroup` (Radix) | Correct ARIA grouping, keyboard navigation |
| Cursor pagination with refetch | Custom cursor tracking | `useInfiniteQuery` (TanStack Query v5) | Handles `getNextPageParam`, stale-while-revalidate, background refetch |
| Optimistic card removal | Manual array splice + re-render | TanStack Query `invalidateQueries` after mutation | Cache invalidation race conditions are subtle; let Query handle it |
| Protected route redirect | Session check in every component | React Router v7 `<ProtectedRoute>` wrapping `<Outlet>` | Single source of truth for auth gating |
| Icon set | Custom SVGs | `lucide-react` (ships with shadcn) | Already in the dependency graph; consistent stroke weights |

**Key insight:** The hardest UI problem in this phase is the undo/fade pattern (D-09). The natural instinct is to track this in TanStack Query's optimistic update system, but the 5-second delay before actually calling the API makes that awkward. Keep the undo state in Zustand (a `fadingCardIds: Set<string>` and a `pendingTimeouts: Map<string, timeoutId>`) and only fire the API call when the timeout expires.

---

## Common Pitfalls

### Pitfall 1: shadcn CLI init recreates globals.css / index.css

**What goes wrong:** Running `npx shadcn@latest init` after manually configuring Tailwind v4 will overwrite `src/index.css` with its own version that may not match what you had.

**Why it happens:** shadcn init writes its own CSS variable definitions into the global stylesheet.

**How to avoid:** Run `npx shadcn@latest init` before writing custom CSS. Let shadcn generate the base CSS, then add project-specific overrides below the generated content. Never run init again after setup.

**Warning signs:** Colors or font sizes reset unexpectedly after running an `npx shadcn@latest add` command (add commands don't touch CSS, but init does).

### Pitfall 2: `tsconfig.json` vs `tsconfig.app.json` path alias split

**What goes wrong:** Path alias `@/*` works in app code but TypeScript reports errors, or vice versa.

**Why it happens:** Vite 6 scaffolds two TS config files. The `paths` entry must appear in `tsconfig.app.json` (which the language server reads) AND `tsconfig.json` (which Vite reads for the project reference). Missing either breaks something.

**How to avoid:** Add `"baseUrl": "."` and `"paths": { "@/*": ["./src/*"] }` to `compilerOptions` in BOTH files.

**Warning signs:** VS Code shows red underlines on `@/` imports even though the dev server works fine.

### Pitfall 3: `alternatives` JSONB shape is unknown — must be typed

**What goes wrong:** `DraftItemResponse.alternatives` is typed as `list` (Python) / `unknown[]` (TypeScript inferred). Rendering `alternatives[0]` throws if the JSONB objects don't match expected shape.

**Why it happens:** The backend `alternatives` column is raw JSONB — no enforced schema. Mock data must define the shape, and the frontend must assert the type.

**How to avoid:** Define a TypeScript interface for the alternatives structure (e.g., `{ text: string; type: 'reply' | 'retweet' | 'comment' }`), and write a type guard or Zod schema to validate the JSONB at runtime. Mock data must use the same shape consistently.

**Warning signs:** Card renders blank draft text; console shows `undefined` when accessing `alt.text`.

### Pitfall 4: Undo timeout leak on fast approve/reject

**What goes wrong:** Operator approves a card, immediately approves another, unmounts the component — leftover `setTimeout` callbacks fire after unmount and call the API anyway (or trigger React state updates on unmounted components).

**Why it happens:** `setTimeout` callbacks are not automatically cleaned up on React unmount.

**How to avoid:** Store all pending timeout IDs in Zustand (not component `useState`). On unmount of `QueuePage` (or in a `useEffect` cleanup), call `clearTimeout` on all entries in the pending map. Better yet: always fire the API call from Zustand action, not from a component effect.

**Warning signs:** "Can't perform a React state update on an unmounted component" warnings in test output.

### Pitfall 5: Cursor pagination query key must include cursor

**What goes wrong:** Loading more items from the next page overwrites the first page in the TanStack Query cache instead of appending.

**Why it happens:** If cursor is included in the query key, each page has its own cache entry. `useInfiniteQuery` handles this correctly, but hand-rolled `useQuery` with cursor in the key will not combine pages.

**How to avoid:** Always use `useInfiniteQuery` (not `useQuery`) for the queue. Never manually include the cursor in the `queryKey` — TanStack manages page params internally.

**Warning signs:** Scrolling "Load More" replaces existing items rather than appending.

### Pitfall 6: CORS in local dev — backend must allow Vite dev server origin

**What goes wrong:** API calls from the Vite dev server (`http://localhost:5173`) are blocked by the browser CORS policy because the FastAPI backend only allows its Railway origin.

**Why it happens:** FastAPI's `CORSMiddleware` defaults to blocking all origins not in `allow_origins`.

**How to avoid:** Confirm the backend already allows `http://localhost:5173` as a CORS origin (check `backend/app/main.py` or a `cors.py` module). If not, add it before frontend integration testing. Alternatively, use Vite's proxy config to route `/api/*` through the dev server.

**Warning signs:** Browser console shows `Access to fetch at '...' from origin 'http://localhost:5173' has been blocked by CORS policy`.

### Pitfall 7: Related card badge links to card on a different platform tab

**What goes wrong:** An Instagram card has `related_id` pointing to a Twitter card. Clicking the "Also on Twitter" badge needs to switch the active platform tab to Twitter AND scroll to that card — but the Twitter items may not be loaded yet.

**Why it happens:** Platform tabs use separate query instances. The related card lives in a different query.

**How to avoid:** On related badge click: (1) set active tab to the related platform via Zustand, (2) ensure the target platform query is active, (3) use a URL hash or a Zustand `highlightCardId` that the queue list watches to scroll-into-view the target card once it renders. Simple approach: scroll to top + highlight; don't attempt cross-tab deep linking.

**Warning signs:** Clicking "Also on Twitter" does nothing, or navigates but the card is not visible.

---

## Code Examples

### DraftItem TypeScript Interface (from backend schema)

```typescript
// Source: backend/app/schemas/draft_item.py + backend/app/models/draft_item.py
export type DraftStatus = 'pending' | 'approved' | 'edited_approved' | 'rejected' | 'expired'

export interface DraftAlternative {
  text: string
  type: 'reply' | 'retweet' | 'comment' | 'thread' | 'long_post'
  label?: string  // e.g., "Draft A", "Draft B", "RT Quote"
}

export interface DraftItemResponse {
  id: string                     // UUID
  platform: 'twitter' | 'instagram' | 'content'
  status: DraftStatus
  source_url?: string
  source_text?: string
  source_account?: string
  follower_count?: number
  score?: number                 // 8.7 — displayed as "8.7/10"
  quality_score?: number
  alternatives: DraftAlternative[]  // JSONB array — shape must be consistent
  rationale?: string
  urgency?: string
  related_id?: string            // UUID of sibling card in another platform
  rejection_reason?: string
  edit_delta?: string
  expires_at?: string
  decided_at?: string
  created_at: string
  updated_at?: string
}

export interface QueueListResponse {
  items: DraftItemResponse[]
  next_cursor?: string           // base64 encoded created_at:id
}
```

### API Queue Call

```typescript
// Source: backend/app/routers/queue.py — GET /queue
export async function getQueue(params: {
  platform?: string
  status?: string
  cursor?: string
  limit?: number
}): Promise<QueueListResponse> {
  const searchParams = new URLSearchParams()
  if (params.platform) searchParams.set('platform', params.platform)
  if (params.status) searchParams.set('status', params.status ?? 'pending')
  if (params.cursor) searchParams.set('cursor', params.cursor)
  if (params.limit) searchParams.set('limit', String(params.limit))
  return apiFetch<QueueListResponse>(`/queue?${searchParams}`)
}
```

### Approve Mutation

```typescript
// Source: backend/app/routers/queue.py — PATCH /items/{id}/approve
export async function approveItem(id: string, editedText?: string): Promise<DraftItemResponse> {
  return apiFetch<DraftItemResponse>(`/items/${id}/approve`, {
    method: 'PATCH',
    body: editedText ? JSON.stringify({ edited_text: editedText }) : undefined,
  })
}
```

### Reject Mutation

```typescript
// Source: backend/app/routers/queue.py — PATCH /items/{id}/reject
export const REJECTION_CATEGORIES = [
  'off-topic', 'low-quality', 'bad-timing', 'tone-wrong', 'duplicate'
] as const
export type RejectionCategory = typeof REJECTION_CATEGORIES[number]

export async function rejectItem(
  id: string,
  category: RejectionCategory,
  notes?: string
): Promise<DraftItemResponse> {
  return apiFetch<DraftItemResponse>(`/items/${id}/reject`, {
    method: 'PATCH',
    body: JSON.stringify({ category, notes }),
  })
}
```

### Sonner Toast Setup

```typescript
// Source: https://ui.shadcn.com/docs/components/sonner
// src/main.tsx
import { Toaster } from '@/components/ui/sonner'

root.render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
      <Toaster position="bottom-right" richColors />
    </QueryClientProvider>
  </React.StrictMode>
)
```

### Mock Data Shape (seed pattern)

```typescript
// src/seed/seedData.ts
import type { DraftItemResponse } from '@/api/types'

export const mockTwitterItems: DraftItemResponse[] = [
  {
    id: 'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
    platform: 'twitter',
    status: 'pending',
    source_url: 'https://x.com/GoldmanSachs/status/...',
    source_text: 'Central banks bought 1,037 tonnes of gold in 2023, the second highest on record. #Gold #CentralBanks',
    source_account: '@GoldmanSachs',
    follower_count: 2800000,
    score: 8.7,
    quality_score: 9.1,
    alternatives: [
      {
        text: 'Central banks are voting with their reserves. 1,037 tonnes in 2023 — that\'s not a blip, that\'s a structural shift in monetary strategy.',
        type: 'reply',
        label: 'Draft A'
      },
      {
        text: 'The data is consistent: when institutional confidence in fiat wavers, gold allocation goes up. Second highest CB buying year on record.',
        type: 'reply',
        label: 'Draft B'
      }
    ],
    rationale: 'Goldman Sachs is a tier-1 financial authority. Central bank accumulation data is evergreen signal content for gold sector. High engagement likely from institutional followers.',
    urgency: 'high',
    created_at: new Date(Date.now() - 1000 * 60 * 30).toISOString(),  // 30 min ago
    expires_at: new Date(Date.now() + 1000 * 60 * 60 * 5.5).toISOString(),
  },
  // ... 9-14 more items covering twitter (5-6), instagram (4-5), content (1-2)
]
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| shadcn `tailwind-v4` branch install flag | `npx shadcn@latest init` (default is now v4) | Feb 2025 | No branch flag needed; CLAUDE.md note is now addressed by default behavior |
| shadcn `toast` component | `sonner` via shadcn | Feb 2025 | Must use Sonner, not the old toast component |
| `tailwindcss-animate` | `tw-animate-css` | Feb 2025 | shadcn new installs use `tw-animate-css`; don't install both |
| Tailwind three-directive import (`@tailwind base/components/utilities`) | `@import "tailwindcss"` | Tailwind v4.0 | Single import in CSS; no tailwind.config.js required |
| `forwardRef` on React components | Direct prop passing (React 19 removes need) | React 19 | shadcn components updated; no manual forwardRef wrappers needed |
| HSL color values in CSS variables | OKLCH color values | shadcn Feb 2025 | Better color accessibility; new-york style uses OKLCH |
| `useQuery` with manual cursor tracking | `useInfiniteQuery` with `initialPageParam` (required in v5) | TanStack Query v5 | `initialPageParam` is now required; v4 pattern breaks |

**Deprecated/outdated:**
- `react-query` package name: replaced by `@tanstack/react-query` (has been for a while, but worth noting)
- `zustand/shallow` import: replaced by `zustand/react/shallow` for the `useShallow` hook

---

## Open Questions

1. **`alternatives` JSONB structure — exact field names**
   - What we know: `alternatives` is a JSONB array on `draft_items`; mock data will define the shape for this phase
   - What's unclear: Whether agents (Phases 4-7) will use exactly the same shape the frontend defines now, or if the schema will drift
   - Recommendation: Define the TypeScript interface in Phase 3's `src/api/types.ts` as the authoritative shape, then document it in CLAUDE.md conventions. Agents in later phases must produce this shape.

2. **Backend CORS configuration**
   - What we know: The backend exists; CORS is likely configured for Railway's production URL
   - What's unclear: Whether `http://localhost:5173` is in the allowed origins list
   - Recommendation: Wave 0 task should verify CORS config in `backend/app/main.py` and add the Vite dev server origin if missing.

3. **Database seeding mechanism**
   - What we know: D-17 requires 10-15 items pre-seeded; backend has Alembic for schema migrations
   - What's unclear: Whether to seed via a Python script that calls the DB directly, or via the API using a seed script
   - Recommendation: Create a Python seed script (`backend/scripts/seed_mock_data.py`) that inserts directly via SQLAlchemy — same pattern as existing migration tooling, no auth needed, repeatable.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Node.js | Vite build, npm | Yes | v25.8.2 | — |
| npm | Package installation | Yes | 11.11.1 | — |
| Python 3.x (backend seed script) | Mock data seeding | Assumed present (backend runs) | — | API-based seed script via `curl` |
| Backend API (Railway or local) | Integration testing | Available locally (Phase 2 complete) | — | MSW mocks for unit tests |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:**
- Live backend for integration tests: MSW handlers cover unit/component tests; integration tests need the backend running locally.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Vitest 4.1.2 |
| Config file | Embedded in `vite.config.ts` under `test:` key |
| Quick run command | `npx vitest run --reporter=verbose` |
| Full suite command | `npx vitest run --coverage` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DASH-01 | Platform tabs render with badge counts | unit | `npx vitest run src/components/layout/PlatformTabBar.test.tsx` | Wave 0 |
| DASH-02 | Queue items sorted by created_at DESC | unit | `npx vitest run src/hooks/useQueue.test.ts` | Wave 0 |
| DASH-03 | ApprovalCard renders all required fields | unit | `npx vitest run src/components/approval/ApprovalCard.test.tsx` | Wave 0 |
| DASH-04 | Approve/reject buttons trigger correct mutations | unit | `npx vitest run src/components/approval/ApprovalCard.test.tsx` | Wave 0 |
| DASH-05 | Click on draft text activates edit mode | unit | `npx vitest run src/components/approval/InlineEditor.test.tsx` | Wave 0 |
| DASH-06 | Approve copies text to clipboard | unit | `npx vitest run src/hooks/useApprove.test.ts` | Wave 0 |
| DASH-07 | Source URL link has correct href + target=_blank | unit | `npx vitest run src/components/approval/ApprovalCard.test.tsx` | Wave 0 |
| DASH-08 | Related badge navigates to sibling card | unit | `npx vitest run src/components/shared/RelatedCardBadge.test.tsx` | Wave 0 |
| DASH-09 | No mobile breakpoints in layout | unit | `npx vitest run src/components/layout/AppShell.test.tsx` | Wave 0 |
| DASH-10 | Visual snapshot (optional) | manual | visual review | N/A |

### Sampling Rate

- **Per task commit:** `npx vitest run --reporter=dot`
- **Per wave merge:** `npx vitest run --coverage`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `src/test/setup.ts` — jest-dom matchers + MSW server lifecycle
- [ ] `src/mocks/handlers.ts` — MSW handlers for `/queue`, `/items/{id}/approve`, `/items/{id}/reject`, `/auth/login`
- [ ] `src/mocks/node.ts` — MSW `setupServer`
- [ ] All test files listed in the table above — created alongside their corresponding implementation files

---

## Project Constraints (from CLAUDE.md)

All directives the planner must verify compliance with:

| Directive | Applies To |
|-----------|------------|
| React 19, Vite 6, Tailwind v4, shadcn/ui (now via `npx shadcn@latest init`), TanStack Query v5, Zustand v5 | All frontend tasks |
| shadcn/ui tailwind-v4 branch — now means current CLI, not a separate branch flag | Setup task |
| `date-fns 3.x` for date formatting (CLAUDE.md specifies 3.x; registry shows 4.1.0 is current) | Date display tasks |
| Single-user internal tool — no multi-tenancy, no mobile responsive design | Architecture |
| JWT in localStorage, `Authorization: Bearer` header | API client |
| FastAPI backend on Railway — CORS must allow frontend origin | Integration |
| Desktop-only layout (DASH-09, REQUIREMENTS.md "Out of Scope") | All layout tasks |
| No auto-posting under any circumstances | Not applicable to this phase, but must not add clipboard triggers beyond D-06 |
| GSD workflow enforcement — all file edits through `/gsd:execute-phase` | Process |

> Note on `date-fns`: CLAUDE.md says `3.x` but the current npm version is `4.1.0`. The 4.x release is a major update. For a greenfield project starting now, use `date-fns@4` unless the project's Python backend stack or other frontend deps have a hard `3.x` constraint. Recommend planner task verifies this before locking the install command.

---

## Sources

### Primary (HIGH confidence)

- Official npm registry (verified 2026-03-31) — all package versions
- `backend/app/schemas/draft_item.py` — exact `DraftItemResponse` schema
- `backend/app/routers/queue.py` — queue endpoints, state machine, pagination
- `backend/app/routers/auth.py` — login endpoint shape
- `backend/app/models/draft_item.py` — JSONB `alternatives` column, full field list
- `backend/app/main.py` — all registered routers

### Secondary (MEDIUM confidence)

- [shadcn/ui Tailwind v4 docs](https://ui.shadcn.com/docs/tailwind-v4) — setup, deprecations (Sonner, tw-animate-css)
- [shadcn/ui Vite installation](https://ui.shadcn.com/docs/installation/vite) — bootstrap sequence
- [TanStack Query v5 infinite queries](https://tanstack.com/query/v5/docs/react/guides/infinite-queries) — `useInfiniteQuery` with `initialPageParam`
- [TanStack Query v5 optimistic updates](https://tanstack.com/query/latest/docs/framework/react/guides/optimistic-updates) — mutation patterns
- [Zustand v5 slices pattern](https://github.com/pmndrs/zustand) — `useShallow`, slice composition
- [React Router v7 protected routes](https://www.robinwieruch.de/react-router-private-routes/) — `ProtectedRoute` with `Outlet`
- [MSW quick start](https://mswjs.io/docs/quick-start/) — `setupServer` for Vitest

### Tertiary (LOW confidence)

- Various Medium/DEV community posts on React 19 + Vite + Tailwind v4 setup — used for cross-verification only, not as primary guidance

---

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — all versions verified via npm registry 2026-03-31
- Architecture: HIGH — derived directly from backend schemas and locked decisions in CONTEXT.md
- Pitfalls: MEDIUM — based on known React/shadcn/TanStack patterns; some project-specific (JSONB shape) are flagged as open questions
- Mock data: HIGH — `DraftItemResponse` schema is fully known from backend

**Research date:** 2026-03-31
**Valid until:** 2026-05-01 (shadcn/ui and TanStack Query ship frequently; re-verify if > 30 days pass)
