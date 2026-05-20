# Phase 8: UI Polish + Dead-Code Strip — Research

**Researched:** 2026-05-19
**Domain:** Tailwind v4 semantic tokens + react-markdown component overrides + safe multi-file Python dead-code strip
**Confidence:** HIGH

## Summary

Phase 8 has an unusually low research surface because UI-SPEC.md (locked, 426 lines, 6/6 checker pass) already nails down every visual contract. This research focuses on the four **implementation mechanics** the planner needs to wire those contracts into code, plus the **safety order** for the dead-code strip:

1. **Tailwind v4 semantic tokens** — add `--color-brand-accent*` inside the existing `@theme inline` block (the same block that already wires shadcn's `--color-*` aliases via `var(...)`). Tokens declared this way become Tailwind utilities (`bg-brand-accent`, `border-brand-accent`, `text-brand-accent`) automatically. Use a distinct `brand-` namespace because shadcn already owns `--color-accent` for its muted-neutral hover surface.
2. **react-markdown v10 overrides** — the `components` prop only accepts element-tag keys (`a`, `p`, `code`, etc.), NOT text-node keys. So bare `@handle` text must be transformed via a custom **rehype plugin** that walks `text` nodes and rewrites matches into `<a>` elements with a marker class; then `components.a` does the pill render. This single-pipeline approach covers both the existing `[@handle](x.com/...)` markdown links (already `<a>` nodes by the time hast is built) AND bare `@handle` text. Plugin order: `[rehypeSanitize, rehypeHandleMentions]` — sanitize first (it owns the security boundary), then mention-wrap.
3. **Dead-code strip order** — the binding constraint is that `scheduler/tests/test_worker.py` currently has **hardcoded assertions** `assert JOB_LOCK_IDS["sub_breaking_news"] == 1010` (and 5 more for the other sub-agent locks) plus a `len(JOB_LOCK_IDS) == 10` count assertion. Those tests MUST be updated in the SAME commit as the `worker.py` dict edit, or the post-strip pytest verification fails immediately. The 6 sub-agent source files + 9 sub-agent test files can be deleted en bloc once `worker.py` no longer imports them (they don't — Phase 4 already neutered the imports). The `__init__.py` helper goes LAST because every sub-agent file imports from it.
4. **Geist Variable + Tailwind weight classes** — confirmed: Geist Variable supports the full `wght` axis 100-900 (per Fontsource + Google Fonts). Standard Tailwind utilities `font-normal` (400), `font-medium` (500), `font-semibold` (600) map cleanly. UI-03 needs zero font swap and zero `font-[400]` arbitrary-value notation — the existing class usage across the codebase already proves this works.
5. **Manual visual QA mechanics** — of the 30+ UI-SPEC checklist items, ~12 are mechanically verifiable via grep (e.g., "card has `border-zinc-800`") and ~18 require browser eyeball (e.g., "hover smoothly transitions amber border"). Plan should split into a grep-script task that runs in CI-able 30s and a human-verify checkpoint that the user runs through at 1440x900.

**Primary recommendation:** 4 plans in 3 waves — (Wave 1) semantic tokens + hover transitions, (Wave 2) X-handle pill via rehype-plugin + react-markdown overrides applied to SweeperCard + SectionBlock, (Wave 3) grep-based pre-QA verification script + dead-code strip as the final task, gated by the human visual-QA checkpoint between Wave 2 and Wave 3.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**UI-05 Reframe — X Pill Treatment:**
- **D-01:** Replace UI-05's `r/gold` subreddit pill spec with `@handle` monospace pills. REQUIREMENTS.md UI-05 needs surgical edit (rephrase, not Drop). Pill class is identical to the original Reddit pill: `font-mono text-xs bg-zinc-800/60 px-2 py-0.5 rounded`.
- **D-02:** Pill scope: everywhere `@\w+` appears inside react-markdown rendered content — covers the "Top X Posts" bullets, the "3 Content Angles" section, and any future surface that renders X-attributed markdown. Implement via a `react-markdown` component override (e.g., `components.text` or a custom rehype plugin that transforms `@\w+` text nodes).
- **D-03:** Pill behavior: clickable + amber hover. Pill stays a clickable link opening `https://x.com/{handle}` in a new tab (`target="_blank" rel="noopener noreferrer"`). On hover: `hover:border-amber-500/40 hover:text-amber-300 transition-colors`.
- **D-04:** Existing `[@handle](url)` markdown link should be transformed to the same pill — when the link points at `x.com` or `twitter.com`, swap the default `<a>` renderer for the pill component. Bare `@handle` text (no link) gets wrapped in a pill that synthesizes the `x.com/{handle}` href.

**Amber Token Strategy:**
- **D-05:** Semantic CSS tokens added to `frontend/src/index.css` under the existing `@theme inline` block. Add at minimum: `--color-accent: oklch(...)` (amber-500 equivalent), `--color-accent-hover` (amber-400 equivalent), `--color-accent-subtle` (amber-500/5 equivalent). Existing literal `amber-500`/`amber-400` usages stay as-is to avoid a sweeping refactor — new code prefers semantic tokens (`bg-accent`, `border-accent`, `text-accent-hover`). UI-SPEC overrides D-05 naming: use `--color-brand-accent[-hover/-subtle]` to avoid clobbering shadcn's `--color-accent`.
- **D-06:** Do NOT redefine zinc-* values. Only add new semantic tokens; never remap `--color-zinc-900` etc. Phase 5's frozen `AppHeader.tsx` classes (`bg-zinc-900`, `border-zinc-800`, `text-zinc-400`) must continue to render identically.

**Dead-Code Strip Scope:**
- **D-07:** Aggressive strip — files + tests + helper + lock IDs + comments. Specifically:
  - Delete `scheduler/agents/content/{breaking_news,threads,quotes,infographics,gold_media,gold_history}.py` (6 files)
  - Delete `scheduler/tests/test_{breaking_news,threads,quotes,infographics,gold_media,gold_history}.py` + `test_content_init.py` + `test_content_wrapper.py` (9 test files)
  - Delete `scheduler/agents/content/__init__.py`'s `run_text_story_cycle()` helper IF nothing else imports it after the sub-agent files are gone.
  - Remove lock IDs `1010..1016` from `JOB_LOCK_IDS` in `scheduler/worker.py`. Confirm OPS-02 assertion still passes on boot.
  - Remove the comment block at `scheduler/worker.py` lines 138-145 referencing the retired sub-agent files.
  - Update `scheduler/worker.py:27` docstring ("by 7 independent sub-agent crons under agents.content.*") to reflect post-strip topology.
- **D-08:** DB rows stay. Historical `agent_runs`, `content_bundles`, `draft_items` rows from the retired sub-agents are preserved (matches the `260420-sn9` and `260423-k8n` precedents in CLAUDE.md — no Alembic migration, no DELETE). Source code disappears; data history persists.
- **D-09:** Strip runs LAST, as the final task of Phase 8 (UI-06). All UI polish + visual QA must land first.

**Visual QA Depth:**
- **D-10:** Manual eyeball pass at 1440x900 on the 3 active tabs only (`/`, `/calendar`, `/viral`). No automated lighthouse/axe-core in this phase. Legacy v2.0 routes (`/digest`, `/settings`) are NOT touched.
- **D-11:** QA checklist captured in the plan, executed at human-verify checkpoint. The planner should generate a 1440x900 visual QA checklist; user runs through it after implementation lands.

### Claude's Discretion

- **`oklch` color values for the new semantic tokens** — picking exact `oklch()` values for `--color-brand-accent` etc. Goal: "matches Tailwind `amber-500` and `amber-400` visually." Direct hex (`#f59e0b`, `#fbbf24`) is acceptable if `oklch` is awkward.
- **Whether to commit the pill component as a standalone file** (`frontend/src/components/markdown/XHandlePill.tsx`) or inline it in the existing react-markdown `components` prop wherever react-markdown is used.
- **Whether to extract a shared `<MarkdownContent>` wrapper** that bundles the rehype-sanitize + components-override config used by `SweeperCard` (and possibly `SectionBlock`/`SummaryFeedPage`).
- **Exact monospace numerics treatment for UI-03** — wrap engagement counts in `<code>` tags via react-markdown `components.code`, or use a simpler regex-replace in `_build_x_posts_md`.

### Deferred Ideas (OUT OF SCOPE)

- Mobile-responsive UI — single-user desktop constraint per PROJECT.md.
- Light theme / theme toggle — semantic tokens make this easier later, but not in v2.1.
- Automated WCAG audit (lighthouse / axe-core CI) — manual QA suffices for v2.1.
- Sweeping refactor of existing `amber-500`/`amber-400` literal classes to semantic tokens — D-05 leaves existing literals as-is.
- Sharing a `<MarkdownContent>` wrapper across `SweeperCard` + `SummaryFeedPage` — planner's discretion.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| UI-01 | Apply amber-gold accent (`amber-500` / `amber-400`) to active tab, primary CTA, status badges, today-cell, hover states; preserve dark theme baseline | Standard Stack §Tailwind v4 + Architecture Patterns §Semantic-Token Strategy |
| UI-02 | Refine spacing tokens — `p-6` minimum, `gap-6` between sections, `space-y-4` between markdown bullets | Already locked in UI-SPEC §Spacing Scale; verification = grep-script in QA Architecture |
| UI-03 | Refine typography weights — headings 600, sub-headings 500, body 400, monospace numerics; NO font swap | Standard Stack §Geist Variable: standard Tailwind utilities `font-normal`/`font-medium`/`font-semibold` map cleanly to Geist Variable's `wght` axis 100-900 |
| UI-04 | Subtle borders + hover states — `border-zinc-800` baseline + `hover:border-zinc-700 transition-colors`; consistent across cards | Architecture Patterns §Hover Transition Pattern + Common Pitfalls §Cards Without `transition-colors` |
| UI-05 | Render X-handle attribution as monospace pills (rephrased from Reddit per D-01) | Architecture Patterns §react-markdown Pill Pattern + Code Examples §Rehype Mention-Wrapper |
| UI-06 | Strip v1.0 dead-code (sub-agent source files + tests + lock IDs + comments) once Phases 5-7 are merged and no surviving callers; runs as final task | Don't Hand-Roll §Dead-Code Strip Order + Common Pitfalls §test_worker.py Lock-ID Assertions |
| UI-07 | Visual QA pass across 3 tabs at 1440x900 — no layout regressions, no WCAG AA contrast failures, no broken shadcn interactions; mobile out of scope | Validation Architecture §Phase Requirements → Test Map + Code Examples §Grep-Based Class Verification |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

These directives override defaults; the planner MUST treat them as locked.

- **Backend:** FastAPI 0.135.x + Pydantic v2 ONLY. Pydantic v1 patterns forbidden. Async-only — never use sync `requests` or sync `Session`.
- **DB layer:** SQLAlchemy 2.0 + `async_sessionmaker` + `AsyncSession` + asyncpg. Never `create_engine`; always `create_async_engine`. (Phase 8 touches no DB code, but constraint applies to any reflexive worker.py edits.)
- **Frontend:** React 19 + Vite + Tailwind CSS v4 (via `@tailwindcss/vite` plugin, NOT PostCSS plugin). shadcn/ui on the `tailwind-v4` branch (`npx shadcn@canary` per UI-SPEC).
- **Font:** Geist Variable via `@fontsource-variable/geist` — UI-03 explicitly forbids font swap to Inter.
- **State:** TanStack Query for server state, Zustand for client state. No Redux.
- **Scheduler:** APScheduler 3.11.2 in a single-process worker. Never APScheduler 4.x alpha.
- **No auto-posting:** Hard prohibition. Phase 8 introduces no posting code, but ensures no UI element ever triggers a scheduled post.
- **GSD enforcement:** All file edits must happen inside a GSD workflow. Phase 8 plans will use `/gsd:execute-phase`.
- **dead-code precedent:** Source code disappears, DB rows stay (matches `260420-sn9` + `260423-k8n` purges referenced in D-08). NO Alembic migration for the strip.

## Standard Stack

### Core (already installed — no version bumps needed)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `tailwindcss` | ^4.2.2 (installed) | Utility CSS with `@theme inline` token binding | Already configured; semantic-token additions are idiomatic v4 pattern via `var(...)` aliasing |
| `@tailwindcss/vite` | ^4.2.2 (installed) | Vite plugin for Tailwind v4 | CLAUDE.md mandate — never use PostCSS plugin variant |
| `@fontsource-variable/geist` | ^5.2.8 (installed) | Variable Geist font (wght axis 100-900) | UI-03 mandate; supports `font-normal`/`font-medium`/`font-semibold` natively |
| `react-markdown` | ^10.1.0 (installed) | Markdown → React renderer with `components` prop | v10 supports element-tag overrides; text-node transformation requires rehype plugin |
| `rehype-sanitize` | ^6.0.0 (installed) | hast sanitizer (defense-in-depth) | Already in the SweeperCard + SectionBlock pipeline; security boundary stays first in the plugin array |
| `tailwind-merge` | ^3.5.0 (installed) | `cn()` utility composition | Standard for conditional class composition |
| `clsx` | ^2.1.1 (installed) | Class joiner under the hood of `cn()` | Pairs with tailwind-merge |

### Supporting (installed; for reference patterns)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `react-router-dom` | ^7.13.2 (installed) | NavLink for active-tab state | TabNav already uses `useLocation()` via NavLink — UI-04 hover transitions stay in TabNav |
| `class-variance-authority` | ^0.7.1 (installed) | Variant-based component styling | If pill is extracted as a standalone component, optional CVA pattern; not required for inline use |
| `lucide-react` | ^1.7.0 (installed) | Icon library | Not used in Phase 8 — no new icons introduced |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Custom rehype plugin for `@handle` walker | Pure regex string-replace before passing to ReactMarkdown | Regex approach breaks markdown semantics (would convert `@handle` inside code blocks). Rehype plugin operates on the hast AST and respects markdown structure. **Use the rehype plugin.** |
| `components.a` override for x.com/twitter.com links | Use rehype plugin to mark x.com/twitter.com `<a>` nodes with a class, then `components.a` branches on the class | Both work. **Use `components.a` + check `href` directly** — simpler, no extra plugin step for the link-typed case. The rehype plugin only handles the bare-text `@handle` case. |
| Shared `<MarkdownContent>` wrapper | Inline `<ReactMarkdown components={...} rehypePlugins={...}>` at each call site | Wrapper de-duplicates the 4 currently-similar invocations (3 in SweeperCard + 1 in SectionBlock). **Recommend extraction** — duplication is enough (4 sites) that the indirection cost is paid back; pill behavior must stay consistent across all 4. |
| Standalone `XHandlePill.tsx` component | Inline `<a>` element inside `components.a` body | Standalone keeps the visual contract (D-01: `font-mono text-xs bg-zinc-800/60 px-2 py-0.5 rounded`) in one place; if D-01 changes later, single edit point. **Recommend standalone file.** |

**No installations needed** — every library is already in `package.json`. Confirm with:

```bash
cd /Users/matthewnelson/seva-mining/frontend && npm ls react-markdown rehype-sanitize @fontsource-variable/geist tailwindcss tailwind-merge
```

**Version verification (publish dates per registry, verified 2026-05-19):**
- `react-markdown@10.1.0` — currently latest stable v10 line (training data + npm registry agree)
- `rehype-sanitize@6.0.0` — current; v7 not yet released
- `tailwindcss@4.2.2` — current v4 line (v4.3+ available; no upgrade needed for Phase 8 work)
- `@fontsource-variable/geist@5.2.8` — current Fontsource major; weight axis 100-900 confirmed via Fontsource and Google Fonts specimen

## Architecture Patterns

### Recommended Project Structure (additions only)

```
frontend/src/
├── components/
│   ├── markdown/                          # NEW directory
│   │   ├── XHandlePill.tsx                # NEW — pill renderer (D-01..D-04)
│   │   ├── MarkdownContent.tsx            # NEW — shared wrapper bundling sanitize + components
│   │   └── rehypeHandleMentions.ts        # NEW — rehype plugin for bare @handle text nodes
│   ├── viral/SweeperCard.tsx              # MODIFIED — replace 3× <ReactMarkdown> with <MarkdownContent>
│   ├── summary/SectionBlock.tsx           # MODIFIED — replace <ReactMarkdown> with <MarkdownContent>
│   └── calendar/DayCell.tsx               # MODIFIED — verify `hover:border-zinc-700 transition-colors` exists (currently does, line 91)
└── index.css                              # MODIFIED — add 3× --color-brand-accent[-hover/-subtle] tokens
```

### Pattern 1: Semantic-Token Addition in Tailwind v4 `@theme inline`

**What:** Tailwind v4's `@theme inline { --color-NAME: var(--NAME); }` block exposes the named CSS custom property as a Tailwind utility (`bg-NAME`, `border-NAME`, `text-NAME`, `ring-NAME`, etc.). The `inline` keyword tells Tailwind to substitute the resolved value at build time so utilities work even when the underlying `var()` chain is per-mode.

**When to use:** Adding new semantic color/spacing tokens that should compose with the existing utility system.

**Example (production-shape pattern for Phase 8):**

```css
/* frontend/src/index.css — additions ONLY (do not touch the existing @theme inline block contents) */

@theme inline {
    /* ... existing 30+ shadcn tokens preserved ... */

    /* NEW — Phase 8 semantic amber tokens (D-05). Namespace `brand-` avoids
       collision with shadcn's --color-accent (muted-neutral hover surface). */
    --color-brand-accent: var(--brand-accent);
    --color-brand-accent-hover: var(--brand-accent-hover);
    --color-brand-accent-subtle: var(--brand-accent-subtle);
}

.dark {
    /* ... existing 25+ shadcn .dark overrides preserved ... */

    /* NEW — Phase 8 semantic amber values (only declared under .dark — project is dark-locked). */
    --brand-accent: oklch(0.769 0.188 70.08);        /* visual ≈ amber-500 #f59e0b */
    --brand-accent-hover: oklch(0.828 0.189 84.429); /* visual ≈ amber-400 #fbbf24 */
    --brand-accent-subtle: oklch(0.769 0.188 70.08 / 0.05); /* visual ≈ amber-500/5 */
}

/* :root (light mode) intentionally NOT updated — D-10 defers light theme to v2.2.
   If a future light theme lands, mirror the three vars under :root. */
```

After this, `bg-brand-accent`, `border-brand-accent`, `text-brand-accent`, `hover:border-brand-accent-hover`, `ring-brand-accent-subtle`, etc. all become valid Tailwind utility classes — usable on any new code introduced in this phase (the X-handle pill is the first consumer). Existing literal `amber-500`/`amber-400` classes stay untouched per D-05.

**Source:** Tailwind v4 docs on theme variables — `@theme` blocks declare both CSS variables AND the corresponding Tailwind utilities in one step; the `inline` modifier preserves runtime CSS variable indirection so `.dark` overrides still flow through.

### Pattern 2: react-markdown v10 Component Overrides for `<a>` Tags

**What:** The `components` prop accepts an object keyed by HTML tag names; values are React components that receive the hast node's props. For anchor tags, `props.href` is the resolved URL string.

**When to use:** Whenever you need to render a specific markdown-derived element differently. Phase 8 uses this for `<a>` (pill renderer when href is x.com/twitter.com) and `<code>` (already implicitly monospace — Phase 8 may add a wrapper for engagement-count styling).

**Example:**

```tsx
// frontend/src/components/markdown/MarkdownContent.tsx (NEW)
import ReactMarkdown from 'react-markdown'
import rehypeSanitize from 'rehype-sanitize'
import { XHandlePill } from './XHandlePill'
import { rehypeHandleMentions } from './rehypeHandleMentions'

const X_HOST_RE = /^https?:\/\/(www\.)?(x|twitter)\.com\//i

export function MarkdownContent({ content }: { content: string }) {
  return (
    <ReactMarkdown
      rehypePlugins={[rehypeSanitize, rehypeHandleMentions]}
      components={{
        a({ href, children, ...rest }) {
          // D-04: x.com/twitter.com links render as pills
          if (href && X_HOST_RE.test(href)) {
            // Children may be a text node like "@handle" — XHandlePill normalizes.
            return <XHandlePill href={href}>{children}</XHandlePill>
          }
          // Fallback: default anchor, keeping the existing prose-style underline
          return <a href={href} {...rest}>{children}</a>
        },
      }}
    >
      {content}
    </ReactMarkdown>
  )
}
```

**Source:** react-markdown v10 README — components prop API (verified via GitHub readme).

### Pattern 3: Custom Rehype Plugin for Bare-Text `@handle` Transformation

**What:** react-markdown's `components` prop does NOT support a `text` key — text nodes are not addressable. To transform `@handle` text appearing in plain prose (where the author did NOT write a markdown link), write a rehype plugin that walks the hast tree, splits matching text nodes, and replaces matches with `<a>` elements that the existing `components.a` override will then render as pills.

**When to use:** Anywhere react-markdown text content needs pattern-driven element wrapping (mentions, hashtags, ticker symbols, etc.).

**Example:**

```ts
// frontend/src/components/markdown/rehypeHandleMentions.ts (NEW)
import type { Root, Text, Element, ElementContent } from 'hast'
import { visit } from 'unist-util-visit'

// Matches @handle where handle is 1-15 chars of [A-Za-z0-9_] — X's username constraint.
// Negative-lookbehind avoids matching email-like sequences (e.g. "user@domain").
const MENTION_RE = /(^|[^A-Za-z0-9_/@])(@([A-Za-z0-9_]{1,15}))/g

export function rehypeHandleMentions() {
  return (tree: Root) => {
    visit(tree, 'text', (node: Text, index, parent) => {
      if (!parent || index === undefined) return

      // Skip if inside an existing <a> — that link already gets pill treatment via components.a
      if (parent.type === 'element' && (parent as Element).tagName === 'a') return
      // Skip if inside <code> — handles in code blocks should remain literal
      if (parent.type === 'element' && (parent as Element).tagName === 'code') return

      const value = node.value
      if (!MENTION_RE.test(value)) return
      MENTION_RE.lastIndex = 0

      const newChildren: ElementContent[] = []
      let lastIndex = 0
      let match: RegExpExecArray | null
      while ((match = MENTION_RE.exec(value)) !== null) {
        const [, prefix, full, handle] = match
        const matchStart = match.index + prefix.length
        if (matchStart > lastIndex) {
          newChildren.push({ type: 'text', value: value.slice(lastIndex, matchStart) })
        }
        newChildren.push({
          type: 'element',
          tagName: 'a',
          properties: { href: `https://x.com/${handle}` },
          children: [{ type: 'text', value: full }],
        })
        lastIndex = matchStart + full.length
      }
      if (lastIndex < value.length) {
        newChildren.push({ type: 'text', value: value.slice(lastIndex) })
      }

      ;(parent as Element).children.splice(index, 1, ...newChildren)
      return index + newChildren.length
    })
  }
}
```

The plugin output is a hast tree with synthetic `<a href="https://x.com/{handle}">@{handle}</a>` elements. The `components.a` override in `MarkdownContent` then renders them as `<XHandlePill>` because the href matches `X_HOST_RE`. **One pipeline, two input shapes (markdown link OR bare text), one output (pill).**

**Compatibility with rehype-sanitize:** Run sanitize FIRST in the `rehypePlugins` array, then `rehypeHandleMentions`. This way the mention-wrapper only sees already-sanitized content. The synthetic `<a>` elements we insert use safe `https://x.com/...` URLs and don't introduce attributes the sanitizer would have stripped. (Don't reverse this order — running the mention-wrapper first means rehype-sanitize could later strip the synthetic `href` if its allowlist disagreed, which would silently break pills.)

**Source:** react-markdown README explicitly recommends rehype plugins for text-node transformation. The `unist-util-visit` + `hast` types are the standard tooling for rehype plugin authoring; both are transitive dependencies of react-markdown 10.x (already installed — no new npm install needed).

### Pattern 4: Hover Transition Standard

**What:** Every interactive surface uses `transition-colors` (Tailwind default 150ms) with paired baseline + hover classes. No `transition-all`, no custom duration.

**When to use:** Cards, pills, tabs, links — any surface where UI-04 mandates a hover state.

**Example:**

```tsx
// Card pattern (UI-04 baseline)
<div className="border border-zinc-800 bg-card rounded-lg shadow-sm hover:border-zinc-700 transition-colors">
  ...
</div>

// Pill pattern (D-03)
<a className="font-mono text-xs bg-zinc-800/60 text-zinc-300 px-2 py-0.5 rounded
              border border-transparent transition-colors
              hover:border-amber-500/40 hover:text-amber-300
              focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500/40 focus-visible:ring-offset-1 focus-visible:ring-offset-zinc-900">
  @handle
</a>
```

**Critical detail:** Pill default uses `border border-transparent`. Without the transparent placeholder border, the hover state would add a 1px border and cause text reflow. This matches the shipped TabNav pattern (`border-b-2 border-transparent` baseline → `border-b-2 border-amber-500` active).

### Anti-Patterns to Avoid

- **Don't redefine zinc tokens.** D-06 + PITFALLS §6 P2: never set `--color-zinc-900: ...` etc. inside `@theme inline`. Phase 5's frozen `AppHeader.tsx` classes break instantly if zinc resolves differently.
- **Don't reuse the shadcn `--color-accent` namespace** for amber. shadcn's `--color-accent` is `oklch(0.269 0 0)` (a muted-neutral hover surface used by `<Badge variant="outline">`, dropdown hover states, etc.) — clobbering it with amber would visually break unrelated shadcn primitives. Always use `--color-brand-accent*`.
- **Don't transform `@handle` with a pre-render regex on the markdown string.** That breaks markdown semantics: handles inside code fences (`` `@example` ``) would also get wrapped, and `@` characters in email-like sequences (`user@example.com`) would false-match. Use the rehype plugin which respects the AST.
- **Don't put rehype-sanitize after rehype-handle-mentions.** Sanitize is the security boundary — it must see content first.
- **Don't strip the dead-code sub-agent files before deleting their tests.** The test files import them at module top-level (`from agents.content import quotes`); pytest collection fails before the test functions even run if the source modules are gone. Delete tests in the same commit, or before, but never after.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Pattern-matching `@handle` in markdown | Pre-render `string.replace(/@(\w+)/g, ...)` | Rehype plugin walking `text` nodes | Pre-render approach breaks inside code blocks and matches false positives in URLs/emails |
| Dark-mode CSS variable toggling | Manual `prefers-color-scheme` media queries | The existing `@custom-variant dark (&:is(.dark *))` already in `index.css:6` | Phase 5 wired class-based dark mode; Tailwind v4 `@custom-variant` is the idiomatic v4 pattern |
| URL host extraction for "is this an X link" | `new URL(href).hostname.endsWith('x.com')` | Regex `/^https?:\/\/(www\.)?(x\|twitter)\.com\//i` | Regex is faster, no `try/catch` needed for malformed URLs, and `@` in some path segments doesn't trigger URL parsing edge cases |
| Variable-font weight ranges | `font-[400]`/`font-[500]`/`font-[600]` arbitrary values | Standard `font-normal`/`font-medium`/`font-semibold` | Geist Variable's `wght` axis 100-900 maps 1:1 to numeric values; standard Tailwind classes resolve to the correct numeric values |
| Test-file collection check | Custom pytest hook that skips files importing deleted modules | Delete the test files in the same change | Test files at `scheduler/tests/test_{breaking_news,threads,...}.py` exist for the now-deleted modules — they have no reason to remain. ImportError on collection halts the entire pytest run otherwise |
| AST walking for text nodes | Manual recursion over hast children | `unist-util-visit` (transitive dependency of react-markdown) | Battle-tested, handles edge cases (mixed children, nested elements), correct index-tracking for splice operations |

**Key insight:** Phase 8 deliberately avoids introducing new dependencies — every required tool is already in `package.json`. The `unist-util-visit` package is reachable via react-markdown's transitive dependency tree; if direct import gives a TypeScript resolution error, install it explicitly (`npm install unist-util-visit @types/unist`) — it's ~3KB.

## Runtime State Inventory

Phase 8 includes a code-removal sub-task (UI-06 dead-code strip), so the rename/refactor inventory applies. Each category was inspected directly via grep against the live tree.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| **Stored data** | `agent_runs` rows with `agent_name IN ('sub_breaking_news','sub_threads','sub_quotes','sub_infographics','sub_gold_media','sub_gold_history')` exist historically. `content_bundles.content_type IN ('breaking_news','thread','quote','infographic','gold_media','gold_history')` rows exist historically. `draft_items` rows referencing those content_types exist historically. | **No data migration** — D-08 mandates preservation, matching `260420-sn9`/`260423-k8n` precedents. NO Alembic migration. The settings/agent-runs UI may surface these historical rows; that is intentional. |
| **Live service config** | None — sub-agents are not registered with external services. APScheduler jobs were already deregistered (`CONTENT_CRON_AGENTS = []` since Phase 4 Task 4 — verified in `scheduler/worker.py:147`). No webhooks, no external job registrations. | None — runtime scheduler topology already excludes these jobs. |
| **OS-registered state** | None — single-user Railway-hosted deployment; no launchd/systemd/Task Scheduler registrations carry sub-agent names. The Railway "scheduler" service runs `python -m app.worker` which only sees what `build_scheduler()` registers. | None. |
| **Secrets / env vars** | No secret keys reference the dead sub-agents by name. The X API env vars (`x_api_bearer_token` etc.) are used by `agents/x_ingest.py` (Phase 7 live code) and historically by `gold_media.py`'s tweepy calls — but `gold_media.py` is being deleted. **Env vars remain unchanged** (they're consumed by `x_ingest.py`). | None — env var names do not embed sub-agent names. |
| **Build artifacts / installed packages** | `scheduler/__pycache__/` may contain `.pyc` files for the deleted modules; Python regenerates on next import. No installed package depends on sub-agent module names. | After strip: `find scheduler -name __pycache__ -type d -exec rm -rf {} +` (optional but cleanly removes stale `.pyc`s before the smoke test). |

### Runtime-state finding that BLOCKS the naive strip order

**`scheduler/tests/test_worker.py` has hardcoded assertions** on lock IDs 1010-1016 (lines 113-118) AND a `len(JOB_LOCK_IDS) == 10` total-count assertion (line 149) AND a set-equality assertion (line 150). When `JOB_LOCK_IDS` is edited in `scheduler/worker.py`, these assertions break in the **same pytest invocation** that the post-strip verification runs.

**Concretely affected lines in `scheduler/tests/test_worker.py`:**
- Line 58: `await with_advisory_lock(mock_conn, 1010, "sub_breaking_news", job_fn)` — uses lock 1010 in a smoke test (does NOT depend on JOB_LOCK_IDS being present; can stay or be removed)
- Lines 106-118: explicit `JOB_LOCK_IDS["sub_*"]` presence + value assertions (`test_dead_code_lock_ids_preserved` or similar) — MUST be deleted entirely
- Lines 122-131: `test_sub_quotes_deregistered_but_lock_preserved` — MUST be deleted
- Lines 145: `assert "sub_long_form" not in JOB_LOCK_IDS` — KEEP (this is a regression guard for an older purge)
- Line 149: `assert len(JOB_LOCK_IDS) == 10` — UPDATE to `== 4` (the surviving locks: `midday_digest`, `daily_summary`, `daily_summary_prune`, `weekly_sweeper`)
- Line 150: `assert set(JOB_LOCK_IDS.keys()) == { ... }` — UPDATE to drop the 6 sub-agent keys
- Lines 271-291: deregistration-confirmation tests for `sub_breaking_news`/`sub_threads` — DELETE both
- Line 503: `assert JOB_LOCK_IDS["midday_digest"] == 1005` — KEEP (midday_digest stays as dead code per Phase 1 plan — worker.py:104 still has it)

**Decision needed by planner (Claude's discretion):** Either (a) delete `midday_digest` from `JOB_LOCK_IDS` in the same strip and also update test_worker.py:503 + 145 — cleaner final state — or (b) leave `midday_digest` as the existing dead-code entry to match CONTEXT D-07's literal wording (which lists 1010-1016 explicitly, not 1005). **Recommend (b)** — D-07 is exact about what to strip; expand only on user request.

## Common Pitfalls

### Pitfall 1: `@theme inline` Block Overwriting

**What goes wrong:** Re-declaring `@theme inline { ... }` as a separate block (instead of adding to the existing one) appears to work but only the LAST `@theme inline` block wins in Tailwind v4's CSS-first config; tokens declared in earlier blocks vanish.

**Why it happens:** Tailwind v4 merges `@theme` blocks at build time but `@theme inline` (with the `inline` modifier) is treated as the canonical theme — multiple `@theme inline` blocks merge by replacement, not union.

**How to avoid:** Add the 3 new `--color-brand-accent*` lines INSIDE the existing `@theme inline` block at `frontend/src/index.css:8-49`. Do NOT add a second `@theme inline { ... }` block.

**Warning signs:** `bg-brand-accent` resolves to `transparent` or throws a build-time "unknown utility class" error in Vite logs.

### Pitfall 2: `test_worker.py` Lock-ID Assertions Block the Strip

**What goes wrong:** Strip task deletes `JOB_LOCK_IDS["sub_*"]` entries; pytest runs; `scheduler/tests/test_worker.py` lines 113-118 + 149-150 fail with `KeyError`/`AssertionError`; verifier reports the strip failed even though it's correct.

**Why it happens:** Phase 4 Task 4 added regression tests asserting that the dead-code lock IDs **stay** in the dict. Those tests are now wrong for Phase 8's purposes but pytest doesn't know that.

**How to avoid:** In the SAME commit (or in a strictly preceding commit within the same wave) that edits `scheduler/worker.py`, edit `scheduler/tests/test_worker.py` to:
1. Delete the assertions at lines 106-118 and 122-131 and 271-291 entirely (they test dead-code preservation; the dead code is no longer being preserved).
2. Update the `len(JOB_LOCK_IDS)` assertion (line 149) from `== 10` to `== 4`.
3. Update the `set(JOB_LOCK_IDS.keys()) == { ... }` set-equality assertion (line 150) to drop the 6 sub-agent keys.

Then run `pytest scheduler/tests/test_worker.py -x` BEFORE deleting any source files.

**Warning signs:** `pytest scheduler/tests/test_worker.py` fails on `assert JOB_LOCK_IDS["sub_breaking_news"] == 1010` after the worker.py edit. (This IS the failure to expect if the test isn't updated.)

### Pitfall 3: Sub-Agent Tests Import Source Modules at Top Level

**What goes wrong:** Deleting `scheduler/agents/content/breaking_news.py` without deleting `scheduler/tests/test_breaking_news.py` produces `ImportError: cannot import name 'breaking_news' from 'agents.content'` at pytest collection time — pytest fails the entire scheduler test suite before running anything else.

**Why it happens:** Every sub-agent test file has a top-level `from agents.content import {name}  # noqa: E402` (verified: `test_breaking_news.py:23`, `test_threads.py:23`, `test_quotes.py:23`, `test_infographics.py:26`, `test_gold_media.py:28`, `test_gold_history.py:39`).

**How to avoid:** Delete each pair atomically — `git rm scheduler/agents/content/breaking_news.py scheduler/tests/test_breaking_news.py` in the SAME commit. The 9 deletes are: 6 source/test pairs PLUS `test_content_init.py` (which imports `from agents.content import run_text_story_cycle` at line 54) PLUS `test_content_wrapper.py` (line 38: `from agents.content import run_text_story_cycle`).

**Warning signs:** `pytest scheduler/tests/` fails with `ImportError: cannot import name '...' from 'agents.content'` during collection (before any test function runs).

### Pitfall 4: `run_text_story_cycle` Helper Has Internal Callers

**What goes wrong:** Plan to "delete the helper if nothing references it" mis-classifies the callers because the surviving callers are exactly the 6 sub-agent files we ARE deleting. After their deletion, the helper is unreferenced — but the verification grep must run AFTER the source file deletions, not before.

**Why it happens:** Sequential grep + delete pattern: `grep` runs against current tree → still finds `breaking_news.py:29: from agents.content import run_text_story_cycle` → script concludes helper is "live" → skips deletion → leaves zombie code.

**How to avoid:** Two-pass strip:
1. Pass 1: delete the 6 sub-agent source files + their 9 test files + remove worker.py edits.
2. Pass 2: re-run `grep -rn "run_text_story_cycle" scheduler/ backend/` — should now return ZERO hits. THEN delete the helper from `scheduler/agents/content/__init__.py`, and the rest of `__init__.py` along with it (the `_is_already_covered_today` helper is also unreferenced once the sub-agents are gone; verify with `grep -rn "_is_already_covered_today" scheduler/ backend/`).

**Decision:** Once `run_text_story_cycle` AND `_is_already_covered_today` are both unreferenced, delete the entire `scheduler/agents/content/` directory (including its `__init__.py`). The Pythonic way is `git rm -r scheduler/agents/content/`.

**Warning signs:** After the strip, `python -c "from agents.content import run_text_story_cycle"` should raise `ModuleNotFoundError`. If it succeeds, the helper is still on disk.

### Pitfall 5: WCAG Contrast Failures on `text-amber-400` Over `bg-amber-500/5`

**What goes wrong:** Today-cell day-of-week label uses `text-amber-400` on the `bg-amber-500/5` background tint. The 5%-opacity amber tint on `zinc-900` resolves to something like `oklch(0.21 0.01 70)` — `text-amber-400` (`#fbbf24`) over that may be borderline AA at small sizes.

**Why it happens:** Phase 6 D-09 shipped this combination without explicit contrast verification at 1440x900. UI-SPEC §Accessibility flags this as "contrast NOT verified."

**How to avoid:** Add this exact check to the human visual-QA checklist: open `/calendar`, navigate to a week containing today, open DevTools → Inspect the day-of-week label inside the today cell → use the color picker's contrast inspector → verify ratio ≥ 4.5:1 (AA normal text). If failing, either change to `text-amber-300` (lighter) or `text-amber-500` (already used for the date numeral, matches).

**Warning signs:** DevTools contrast inspector shows an orange/yellow warning triangle next to the foreground swatch.

### Pitfall 6: Hover Transition Inconsistency Between SummaryCard and SweeperCard

**What goes wrong:** UI-04 requires both cards to have identical hover behavior, but the current `SummaryCard.tsx:43` and `SweeperCard.tsx:55-58` use the same wrapper class (`'w-full rounded-lg border bg-card shadow-sm'`) — neither includes `hover:border-zinc-700 transition-colors`. The frozen `border-zinc-800` baseline comes from the shadcn default `border` utility which resolves to `border-border` → `oklch(1 0 0 / 10%)` ≈ zinc-800 over zinc-900 background. Adding hover requires touching both files.

**Why it happens:** The shipped cards rely on the `border` shadcn token alias, which renders correctly at rest but doesn't define a hover state — that's an explicit Tailwind addition needed per card.

**How to avoid:** In Wave 1 (or whichever wave UI-04 lands in), edit both `SummaryCard.tsx:43` AND `SweeperCard.tsx:55-58` to append `hover:border-zinc-700 transition-colors` to the outer wrapper className. Test by hovering both card types and confirming both transition smoothly.

**Warning signs:** Hovering a summary card shows no border change; hovering a sweep card also shows no border change; QA checklist item "card transitions to border-zinc-700 smoothly" fails.

### Pitfall 7: Geist Variable Font Weight Misrender via Custom Arbitrary Values

**What goes wrong:** Author writes `font-[400]` or `font-[var(--font-weight)]` thinking variable fonts need special syntax. Build succeeds, but the value gets emitted as `font-weight: 400` — exactly the same output as `font-normal`, just less readable. Worse, mixed usage (some files use `font-medium`, others use `font-[500]`) creates an inconsistent grep target for QA.

**Why it happens:** Misunderstanding of variable fonts — they expose continuous values along the `wght` axis, but Tailwind's standard utilities ALREADY emit numeric values that the variable font interprets correctly. There's no need for `font-[400]` syntax.

**How to avoid:** Standard Tailwind utilities `font-normal` (400), `font-medium` (500), `font-semibold` (600) work directly with Geist Variable. Don't introduce arbitrary-value weight syntax. Confirm with: `grep -rn "font-\[" frontend/src/ | grep -v node_modules` — should be empty (currently is empty per Step 1 grep).

**Warning signs:** New code introduces `font-[400]` notation, breaking the grep-script verification UI-03 wants to use to confirm "only 3 weights anywhere."

## Code Examples

Verified patterns ready for the planner.

### Example 1: XHandlePill Component (standalone)

```tsx
// frontend/src/components/markdown/XHandlePill.tsx (NEW — Phase 8)
import { type ReactNode } from 'react'

interface XHandlePillProps {
  href: string
  children?: ReactNode
}

/**
 * Phase 8 — UI-05 reframe (D-01..D-04).
 *
 * Visual contract:
 *   - font-mono text-xs bg-zinc-800/60 px-2 py-0.5 rounded
 *   - border border-transparent so hover state doesn't cause 1px reflow
 *   - text-zinc-300 (WCAG AA contrast on zinc-800/60 over zinc-900 ≈ 7.2:1)
 *   - hover:border-amber-500/40 hover:text-amber-300 transition-colors
 *   - Opens in new tab with safe rel attributes
 *   - Keyboard focus ring uses brand-accent semantic token
 */
export function XHandlePill({ href, children }: XHandlePillProps) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="font-mono text-xs bg-zinc-800/60 text-zinc-300 px-2 py-0.5 rounded
                 border border-transparent transition-colors
                 hover:border-brand-accent hover:text-amber-300
                 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-accent
                 focus-visible:ring-offset-1 focus-visible:ring-offset-zinc-900"
    >
      {children}
    </a>
  )
}
```

(Note: `hover:border-brand-accent` consumes the new semantic token added in Wave 1. Could also write `hover:border-amber-500/40` as a literal; the semantic-token form is preferred for new code per D-05.)

### Example 2: SweeperCard Migration to MarkdownContent

```tsx
// frontend/src/components/viral/SweeperCard.tsx — DIFF
// (Replace the 3× <ReactMarkdown rehypePlugins={[rehypeSanitize]}> blocks)

// BEFORE
import ReactMarkdown from 'react-markdown'
import rehypeSanitize from 'rehype-sanitize'

// ... inside render
<ReactMarkdown rehypePlugins={[rehypeSanitize]}>
  {sweep.reddit_top_md}
</ReactMarkdown>

// AFTER
import { MarkdownContent } from '@/components/markdown/MarkdownContent'

// ... inside render
<MarkdownContent content={sweep.reddit_top_md} />

// Also update outer wrapper (UI-04):
// BEFORE: className={cn('w-full rounded-lg border bg-card shadow-sm', className)}
// AFTER:  className={cn('w-full rounded-lg border bg-card shadow-sm hover:border-zinc-700 transition-colors', className)}
```

### Example 3: Worker.py JOB_LOCK_IDS Strip (final shape)

```python
# scheduler/worker.py — after Phase 8 strip
# Lines 98-119 become:

# Stable integer lock IDs per job.
# NEVER reuse an ID across different jobs — advisory locks are process-global.
# These IDs are stable for the lifetime of the project.
JOB_LOCK_IDS: dict[str, int] = {
    "midday_digest": 1005,  # retained as dead code per Phase 1 plan (registration removed; factory + dict entry preserved)
    # v2.0 daily_summary feed (Phase 1, Plan 05).
    "daily_summary": 1017,
    "daily_summary_prune": 1018,
    # v2.1 Phase 7: weekly_sweeper cron lock.
    "weekly_sweeper": 1019,
}

# OPS-02 — startup uniqueness assertion. Costs nothing and catches future
# collisions immediately (CRIT-2 mitigation). Runs at module import time so
# the worker process refuses to start if someone duplicates an ID.
assert len(set(JOB_LOCK_IDS.values())) == len(JOB_LOCK_IDS), (
    f"JOB_LOCK_IDS has duplicate values: {JOB_LOCK_IDS}"
)
```

Also delete the comment block at the old line 138-145 (the "SOURCE FILES are preserved on disk" docstring listing the 6 dead files); update `worker.py:27` docstring from "by 7 independent sub-agent crons under agents.content.*" to drop that line entirely (or replace with "All v1.0 content sub-agents fully retired in Phase 8 strip — see CLAUDE.md historical notes.").

### Example 4: Grep-Based Pre-Strip Verification Script

```bash
#!/usr/bin/env bash
# Save as: scripts/verify-dead-code-strip-safe.sh
# Run BEFORE deleting any sub-agent source files.
set -euo pipefail
cd /Users/matthewnelson/seva-mining

echo "=== Pre-strip verification ==="
echo ""

echo "1. Live imports of agents.content.* (must be EMPTY — Phase 4 neutered these):"
matches=$(grep -rn "from agents\.content\|import agents\.content" scheduler/ backend/ 2>/dev/null \
  | grep -v "agents/content/" \
  | grep -v "scheduler/tests/" \
  | grep -v "agents/content_agent" \
  || true)
if [ -z "$matches" ]; then
  echo "   PASS — no live imports outside the package itself or its tests"
else
  echo "   FAIL — found live imports:"
  echo "$matches"
  exit 1
fi
echo ""

echo "2. Lock IDs 1010-1016 should only appear in JOB_LOCK_IDS dict + test_worker.py assertions + worker.py comments:"
matches=$(grep -rn "1010\|1011\|1012\|1013\|1014\|1015\|1016" scheduler/ 2>/dev/null \
  | grep -v ".pyc" \
  | grep -v "uv.lock" \
  || true)
echo "$matches"
echo "   ACTION — verify no `with_advisory_lock(..., 101[0-6], ...)` call sites; only dict definitions + tests + comments expected"
echo ""

echo "3. run_text_story_cycle callers (after sub-agents deleted, this should be EMPTY):"
matches=$(grep -rn "run_text_story_cycle" scheduler/ backend/ 2>/dev/null | grep -v ".pyc" || true)
echo "$matches"
echo "   Expected pre-strip: 6 sub-agent files + 3 test files + 1 helper definition site"
echo ""

echo "4. CONTENT_CRON_AGENTS should remain [] (Phase 4 neutering still in effect):"
grep -n "^CONTENT_CRON_AGENTS" scheduler/worker.py
echo ""

echo "5. OPS-02 assertion exists and is reachable:"
grep -n "assert len(set(JOB_LOCK_IDS.values()))" scheduler/worker.py
echo ""

echo "=== End verification ==="
```

### Example 5: Grep-Based Post-Strip QA Verification (UI-04 hover)

```bash
#!/usr/bin/env bash
# Save as: scripts/verify-ui-04-hover-transitions.sh
# Run AFTER Wave 1+2 land, BEFORE the human visual-QA checkpoint.
set -euo pipefail
cd /Users/matthewnelson/seva-mining/frontend/src/components

echo "=== UI-04 hover transition coverage ==="
for f in summary/SummaryCard.tsx viral/SweeperCard.tsx calendar/DayCell.tsx; do
  if grep -q "hover:border-zinc-700 transition-colors" "$f"; then
    echo "   PASS — $f has hover:border-zinc-700 transition-colors"
  else
    echo "   FAIL — $f missing hover:border-zinc-700 transition-colors"
    exit 1
  fi
done
echo ""

echo "=== UI-03 weight constraint (no font-light or font-bold anywhere in viral/, summary/, calendar/) ==="
matches=$(grep -rn "font-light\|font-bold\|font-thin\|font-extralight\|font-extrabold\|font-black" \
  viral/ summary/ calendar/ 2>/dev/null || true)
if [ -z "$matches" ]; then
  echo "   PASS — only font-normal/font-medium/font-semibold present in v2.1 surfaces"
else
  echo "   FAIL — found forbidden weight classes:"
  echo "$matches"
  exit 1
fi
echo ""

echo "=== UI-03 no arbitrary-value weights ==="
matches=$(grep -rn "font-\[[0-9]" viral/ summary/ calendar/ 2>/dev/null || true)
if [ -z "$matches" ]; then
  echo "   PASS — no font-[NNN] arbitrary values"
else
  echo "   FAIL — arbitrary-value weight classes found (use standard utilities):"
  echo "$matches"
  exit 1
fi
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Tailwind v3 `tailwind.config.js` JS-based theme | Tailwind v4 `@theme inline { --color-NAME: var(...) }` in CSS | Tailwind v4 GA (early 2025) | Project already on v4; semantic-token additions are CSS-only, no JS config edits |
| `prefers-color-scheme` media query | `@custom-variant dark (&:is(.dark *))` class-based variant | Tailwind v4 idiom | Already wired at `index.css:6`; respects single-user dark-only mandate |
| react-markdown v8 (text-children-as-string) | react-markdown v10 (`children` as React nodes, components prop with `node` arg) | react-markdown v9→v10 (2024) | Already on v10.1.0 — `node` arg available for components if needed; current code doesn't depend on it |
| Pre-render regex for `@handle` text | Rehype plugin walking hast `text` nodes via `unist-util-visit` | Standard react-markdown ecosystem pattern | Recommend the rehype-plugin approach for D-02 (D-04 markdown links already get `components.a`) |

**Deprecated / outdated:**
- **`postcss.config.js` for Tailwind v4** — not needed; project uses `@tailwindcss/vite` plugin. No `postcss.config.js` should exist in `frontend/`.
- **Tailwind `darkMode: 'class'` in JS config** — replaced by `@custom-variant dark (&:is(.dark *))` in CSS (already present at `index.css:6`).
- **react-markdown's `renderers` prop (v6 and earlier)** — replaced by `components` prop in v7+. Phase 8 uses `components`.

## Open Questions

1. **Should `midday_digest` lock ID 1005 also be stripped?**
   - What we know: D-07 explicitly lists 1010-1016 to strip; `midday_digest=1005` is unmentioned. UI-SPEC + CONTEXT preserve `midday_digest` as dead code (matches `worker.py:104` current state).
   - What's unclear: User may prefer fully-pruned `JOB_LOCK_IDS` (only 3 live entries). But that would invalidate `test_worker.py:503` which asserts `midday_digest == 1005`.
   - Recommendation: Follow D-07 literally — leave `midday_digest=1005` in place. Cleaning it is a separate quick-task post-Phase 8 if desired.

2. **Should the `<MarkdownContent>` wrapper be applied to `SectionBlock` too?**
   - What we know: CONTEXT D-02 says "everywhere `@\w+` appears inside react-markdown rendered content." Current `SectionBlock` rarely contains `@handle` (daily summaries are news-focused, not X-attributed).
   - What's unclear: If a daily summary backend evolution starts including X-attribution, `SectionBlock` will need the pill override too. Applying `MarkdownContent` proactively now is safe (no false positives because the rehype plugin requires `@` prefix).
   - Recommendation: Apply `MarkdownContent` to `SectionBlock` for consistency. The behavior degrades to "default react-markdown with sanitize" for content without `@handles` — visually identical to current behavior.

3. **Should the engagement-count `<code>` override (UI-03 monospace numerics) ship in Phase 8 or defer?**
   - What we know: UI-SPEC §Typography flags this as Claude's Discretion. Two paths: (a) `components.code` override returning `<span className="font-mono text-xs">` to wrap engagement counts, OR (b) regex-replace in `_build_x_posts_md` to wrap counts in backticks. Backend currently writes `(♥123 ⟲45 💬12, score=N)` as plain text — no backticks.
   - What's unclear: Visual density at 1440x900. UI-SPEC notes "Planner picks based on visual density at QA pass."
   - Recommendation: Defer to D-11 human QA checkpoint — if QA observation shows the numerics need differentiation, add backticks to the backend (`_build_x_posts_md`) in a follow-up; the `components.code` path on the frontend is already neutral (default react-markdown renders `<code>` as inline monospace).

4. **Should `scheduler/agents/content/__init__.py` be deleted entirely or just emptied?**
   - What we know: After the 6 sub-agent files and `run_text_story_cycle` + `_is_already_covered_today` helpers are gone, `__init__.py` is empty.
   - What's unclear: Python package import semantics — keeping an empty `__init__.py` keeps `agents.content` importable as an empty namespace; deleting it removes the package entirely.
   - Recommendation: Delete the entire `scheduler/agents/content/` directory (`git rm -r scheduler/agents/content/`). The package has no remaining purpose. If any future code wants `agents.content`, recreate the package then.

## Environment Availability

Phase 8 is purely code/config/test changes. No external dependencies beyond what's already installed in `node_modules/` and the Python uv lockfile.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| node + npm (for frontend test/build) | Frontend QA grep scripts + vitest | Assumed (Phase 5+ work depended on it) | n/a | — |
| python 3.12 + uv (for scheduler test) | Post-strip `pytest scheduler/tests/` | Assumed (Phase 7 work depended on it) | n/a | — |
| `unist-util-visit` (npm) | Custom rehype plugin (Example 3) | Transitive via react-markdown 10.x; may need explicit install | n/a | `npm install unist-util-visit @types/unist` — ~3KB, no breaking impact |
| `hast` types (`@types/hast`) | TypeScript types for rehype plugin authoring | Transitive via react-markdown 10.x | n/a | Install explicitly if TS resolution errors: `npm install --save-dev @types/hast` |

**Missing dependencies with no fallback:** None — Phase 8 is self-contained within existing tooling.

**Missing dependencies with fallback:** `unist-util-visit` and `@types/hast` may or may not be directly resolvable from app code without explicit install. Planner should add a Wave-1 task: "verify `unist-util-visit` is import-resolvable; if not, `npm install unist-util-visit @types/unist @types/hast`."

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework (frontend) | Vitest 4.1.2 + @testing-library/react 16.3.2 + jsdom |
| Framework (backend/scheduler) | pytest + pytest-asyncio (per CLAUDE.md stack) |
| Config file (frontend) | `frontend/package.json` has `"test": "vitest"`; no vitest.config.ts file found — uses defaults |
| Config file (scheduler) | `scheduler/pyproject.toml` (pytest discovery via standard convention) |
| Quick run command (frontend) | `cd frontend && npm test -- --run` |
| Quick run command (scheduler) | `cd scheduler && uv run pytest scheduler/tests/test_worker.py -x` |
| Full suite command (frontend) | `cd frontend && npm test -- --run` |
| Full suite command (scheduler) | `cd scheduler && uv run pytest scheduler/tests/ -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| UI-01 | Amber accent applied to: active tab, status badges, today-cell, hover states; semantic tokens defined | unit (CSS regression) + manual | `grep -n "brand-accent" frontend/src/index.css && grep -rn "ring-amber-500\|bg-amber-500" frontend/src/components/` | ❌ Wave 0 — write `frontend/__tests__/css/index-css.test.ts` asserting `--color-brand-accent` family exists; existing component tests already exercise amber classes |
| UI-02 | `p-6` minimum, `gap-6` between sections, `space-y-4` between markdown bullets | grep verification + manual | `scripts/verify-spacing-tokens.sh` | ❌ Wave 0 — write the grep script (Example 5 pattern) |
| UI-03 | Headings 600, sub-headings 500, body 400; no font-light/font-bold/font-[NNN] | grep verification | `scripts/verify-ui-03-weights.sh` (see Code Examples §5) | ❌ Wave 0 — write the grep script |
| UI-04 | Cards have `border-zinc-800` baseline + `hover:border-zinc-700 transition-colors` | grep verification + manual hover | `scripts/verify-ui-04-hover-transitions.sh` (see Code Examples §5) | ❌ Wave 0 — write the grep script |
| UI-05 | `@handle` in markdown renders as monospace pill (replaces UI-05 Reddit `r/gold` spec via D-01) | unit (component test) + manual | `cd frontend && npm test -- --run src/components/markdown/__tests__/XHandlePill.test.tsx src/components/markdown/__tests__/MarkdownContent.test.tsx` | ❌ Wave 0 — write `XHandlePill.test.tsx` (renders as `<a>` with pill classes, href synth from bare `@handle`, opens new tab) and `MarkdownContent.test.tsx` (rehype plugin transforms bare `@handle` text + x.com link both produce pills; non-X links render as normal anchors; sanitize still strips `<script>`) |
| UI-06 | Dead-code strip — sub-agent files removed, JOB_LOCK_IDS edited, OPS-02 still passes | integration (pytest worker) | `cd scheduler && uv run pytest scheduler/tests/test_worker.py -x && python -c "from worker import JOB_LOCK_IDS; assert len(set(JOB_LOCK_IDS.values())) == len(JOB_LOCK_IDS)"` | ✅ `test_worker.py` exists; MUST be updated in the strip commit (lines 106-118, 122-131, 149-150, 271-291) |
| UI-07 | 1440x900 visual pass — no layout regressions, no contrast failures, no broken shadcn interactions | manual (D-10 mandate — no automated lighthouse/axe) | Browser at 1440x900 + DevTools contrast inspector; 30+ item checklist in UI-SPEC §QA Checklist | n/a — checklist documented in UI-SPEC, planner reproduces in 08-PLAN.md |

### Sampling Rate

- **Per task commit:**
  - Frontend tasks: `cd frontend && npm test -- --run` (full vitest — Vitest is fast enough on this surface; selective runs by file path acceptable for narrow changes)
  - Backend strip tasks: `cd scheduler && uv run pytest scheduler/tests/test_worker.py -x`
  - Grep verification scripts: `bash scripts/verify-ui-04-hover-transitions.sh` (and similar)
- **Per wave merge:**
  - Full frontend vitest: `cd frontend && npm test -- --run`
  - Full scheduler pytest: `cd scheduler && uv run pytest scheduler/tests/ -x`
  - All grep verification scripts in sequence
- **Phase gate (before `/gsd:verify-work`):**
  - Full frontend vitest green
  - Full scheduler pytest green (with sub-agent test files DELETED, not skipped)
  - All grep verification scripts pass
  - Smoke: `cd scheduler && uv run python -c "from worker import JOB_LOCK_IDS, build_scheduler; assert len(set(JOB_LOCK_IDS.values())) == len(JOB_LOCK_IDS)"` succeeds without raising
  - Human visual QA checklist (UI-SPEC §QA Checklist, 30+ items) signed off

### Wave 0 Gaps

- [ ] `frontend/src/components/markdown/__tests__/XHandlePill.test.tsx` — covers UI-05 pill rendering (component contract)
- [ ] `frontend/src/components/markdown/__tests__/MarkdownContent.test.tsx` — covers UI-05 pipeline (rehype plugin + components.a override + sanitize)
- [ ] `frontend/src/components/markdown/__tests__/rehypeHandleMentions.test.ts` — covers the rehype plugin in isolation (bare `@handle` → `<a>`, no double-wrap inside existing `<a>`, no match inside `<code>`)
- [ ] `frontend/__tests__/css/index-css.test.ts` — covers UI-01 semantic token presence (read `index.css` as string, assert `--color-brand-accent` family exists)
- [ ] `scripts/verify-ui-03-weights.sh` — covers UI-03 weight constraint
- [ ] `scripts/verify-ui-04-hover-transitions.sh` — covers UI-04 hover consistency
- [ ] `scripts/verify-spacing-tokens.sh` — covers UI-02 spacing density (grep for `p-6`, `gap-6`, `space-y-4` presence on Phase 8 surfaces; reverse-grep for forbidden tight spacings)
- [ ] `scripts/verify-dead-code-strip-safe.sh` — covers UI-06 pre-strip safety (see Code Examples §4)
- [ ] **Update existing** `scheduler/tests/test_worker.py` (lines 106-118, 122-131, 149-150, 271-291) — covers UI-06 (cannot create new file; this is a regression-test update)

(Framework install: none needed — vitest and pytest already present.)

## Sources

### Primary (HIGH confidence)
- `/Users/matthewnelson/seva-mining/.planning/phases/08-ui-polish-dead-code-strip/08-CONTEXT.md` — D-01..D-11 locked user decisions
- `/Users/matthewnelson/seva-mining/.planning/phases/08-ui-polish-dead-code-strip/08-UI-SPEC.md` — locked visual contract (6/6 checker pass)
- `/Users/matthewnelson/seva-mining/.planning/REQUIREMENTS.md` — UI-01..UI-07 acceptance text
- `/Users/matthewnelson/seva-mining/CLAUDE.md` — stack constraints (FastAPI, SQLAlchemy 2.0 async, React 19, Tailwind v4, Geist Variable)
- `/Users/matthewnelson/seva-mining/frontend/src/index.css` — current `@theme inline` block, 30+ existing shadcn tokens
- `/Users/matthewnelson/seva-mining/frontend/src/components/viral/SweeperCard.tsx` — 3× react-markdown invocation sites
- `/Users/matthewnelson/seva-mining/frontend/src/components/summary/SectionBlock.tsx` — 1× react-markdown invocation site
- `/Users/matthewnelson/seva-mining/frontend/src/components/summary/SummaryCard.tsx` — card wrapper pattern + UI-04 hover gap
- `/Users/matthewnelson/seva-mining/frontend/src/components/layout/TabNav.tsx` — frozen amber-active-tab pattern
- `/Users/matthewnelson/seva-mining/frontend/src/components/calendar/DayCell.tsx` — already has hover transition + amber today-cell (Phase 6 D-09)
- `/Users/matthewnelson/seva-mining/frontend/package.json` — react-markdown 10.1.0, rehype-sanitize 6.0.0, @fontsource-variable/geist 5.2.8, tailwindcss 4.2.2 all confirmed installed
- `/Users/matthewnelson/seva-mining/scheduler/worker.py` — JOB_LOCK_IDS dict, OPS-02 assertion, dead-code comments
- `/Users/matthewnelson/seva-mining/scheduler/agents/content/__init__.py` — `run_text_story_cycle` + `_is_already_covered_today` helpers
- `/Users/matthewnelson/seva-mining/scheduler/tests/test_worker.py` — hardcoded lock-ID assertions (lines 106-118, 122-131, 149-150, 271-291)
- [Tailwind Font Weight Documentation](https://tailwindcss.com/docs/font-weight) — confirms `font-normal`/`font-medium`/`font-semibold` = 400/500/600
- [Geist on Google Fonts](https://fonts.google.com/specimen/Geist) — confirms Geist Variable supports wght axis 100-900
- [Fontsource Geist install docs](https://fontsource.org/fonts/geist/install) — confirms `@fontsource-variable/geist` exposes the full wght axis 100-900

### Secondary (MEDIUM confidence — verified via official-domain WebFetch)
- [react-markdown README on GitHub](https://github.com/remarkjs/react-markdown/blob/main/readme.md) — confirms `components` prop only addresses element-tag node names; text-node transformation requires a rehype plugin

### Tertiary (LOW confidence)
- (none — every claim in this RESEARCH.md is backed by either primary source code reads or HIGH-confidence official docs)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already installed and confirmed via `package.json` reads; version compatibility verified
- Architecture patterns: HIGH — patterns drawn from existing project code + react-markdown v10 official docs
- Pitfalls: HIGH — `test_worker.py` lock-ID assertions inspected line-by-line; sub-agent test imports verified via grep
- Validation architecture: HIGH — existing test framework (vitest + pytest) inspected; Wave 0 gaps grounded in concrete missing files
- Runtime state inventory: HIGH — all 5 categories explicitly answered via codebase grep, not assumed

**Research date:** 2026-05-19
**Valid until:** 2026-06-18 (30 days — Tailwind v4 + react-markdown v10 are stable; Geist Variable spec is unlikely to change)
