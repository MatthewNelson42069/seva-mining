# Phase 8: UI Polish + Dead-Code Strip - Context

**Gathered:** 2026-05-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Apply the Linear-style dark/amber-500 design language consistently across the three active tabs (`/`, `/calendar`, `/viral`), refine spacing/typography/borders/hovers per UI-01..04, reframe UI-05 to match the Phase 7 X-API pivot (Reddit dropped), complete a manual visual-QA pass at 1440x900 across the 3 active tabs (UI-07), and strip v1.0 dead-code (`scheduler/agents/content/*.py` retired sub-agent files + their tests + the orphaned `run_text_story_cycle()` helper + lock IDs 1010-1016 + referencing comments) as the final task once nothing references them (UI-06).

**Carrying forward from earlier phases:**
- **Phase 5:** `AppShell.tsx` + `AppHeader.tsx` are structurally byte-frozen — the UI pass must not break their existing `border-zinc-800` / `bg-zinc-900` / `text-zinc-400|100` classes
- **Phase 6 (D-09):** Amber strategy already partially in flight — today-cell uses `ring-2 ring-amber-500 bg-amber-500/5`
- **Phase 7 (D-03):** X API replaces Reddit. UI-05's "subreddit pills" spec is obsolete; X posts have `@handle`, not `r/subreddit`. SWEEP-01/02 are already marked Dropped in REQUIREMENTS.md.
- **Codebase baseline:** `frontend/src/index.css` already has `@custom-variant dark (&:is(.dark *))` (Tailwind v4 class-based dark mode wired) and shadcn-style `--color-*` custom properties — semantic tokens are viable.
- **Codebase baseline:** `scheduler/worker.py:66` already neutered `agents.content.*` imports in Phase 4 Task 4 (`CONTENT_CRON_AGENTS` emptied). The 6 sub-agent files are truly orphaned; `x_ingest.py` only references `gold_media.py` in comments (docstring pattern note), not as a live import.

</domain>

<decisions>
## Implementation Decisions

### UI-05 Reframe — X Pill Treatment (DISCUSSED)
- **D-01:** **Replace UI-05's `r/gold` subreddit pill spec with `@handle` monospace pills**, since Phase 7 dropped Reddit. REQUIREMENTS.md UI-05 needs surgical edit (rephrase, not Drop). Pill class is the same as the original Reddit pill: `font-mono text-xs bg-zinc-800/60 px-2 py-0.5 rounded`.
- **D-02:** **Pill scope: everywhere `@\w+` appears inside react-markdown rendered content** — covers the "Top X Posts" bullets, the "3 Content Angles" section (Sonnet writes `(@author_handle)` references per Phase 7 D-11), and any future surface that renders X-attributed markdown. Implement via a `react-markdown` component override (e.g., `components.text` or a custom rehype plugin that transforms `@\w+` text nodes).
- **D-03:** **Pill behavior: clickable + amber hover.** Pill stays a clickable link opening `https://x.com/{handle}` in a new tab (`target="_blank" rel="noopener noreferrer"`). On hover: `hover:border-amber-500/40 hover:text-amber-300 transition-colors` to match the broader UI-04 hover transition pattern.
- **D-04:** **Existing `[@handle](url)` markdown link** should be transformed to the same pill — when the link points at `x.com` or `twitter.com`, swap the default `<a>` renderer for the pill component. Bare `@handle` text (no link) gets wrapped in a pill that synthesizes the `x.com/{handle}` href.

### Amber Token Strategy (DEFAULT — Claude's Discretion)
- **D-05:** **Semantic CSS tokens added to `frontend/src/index.css`** under the existing `@theme inline` block. Add at minimum: `--color-accent: oklch(...)` (amber-500 equivalent), `--color-accent-hover: oklch(...)` (amber-400 equivalent), `--color-accent-subtle: oklch(...)` (amber-500/5 equivalent for ring backgrounds). Existing literal `amber-500`/`amber-400` usages stay as-is in this phase to avoid a sweeping refactor — new code prefers semantic tokens (`bg-accent`, `border-accent`, `text-accent-hover`). Rationale: ROADMAP Pitfall P2 warns against redefining the zinc scale; semantic tokens layer cleanly without touching zinc.
- **D-06:** **Do NOT redefine zinc-* values.** Only add new semantic tokens; never remap `--color-zinc-900` etc. Phase 5's frozen `AppHeader.tsx` classes (`bg-zinc-900`, `border-zinc-800`, `text-zinc-400`) must continue to render identically after this phase.

### Dead-Code Strip Scope (DEFAULT — Claude's Discretion)
- **D-07:** **Aggressive strip — files + tests + helper + lock IDs + comments.** Specifically:
  - Delete `scheduler/agents/content/{breaking_news,threads,quotes,infographics,gold_media,gold_history}.py` (6 files)
  - Delete `scheduler/tests/test_{breaking_news,threads,quotes,infographics,gold_media,gold_history}.py` + `test_content_init.py` + `test_content_wrapper.py` (matching test files)
  - Delete `scheduler/agents/content/__init__.py`'s `run_text_story_cycle()` helper IF nothing else imports it after the sub-agent files are gone. Verify with `grep -r "run_text_story_cycle\|from .content\|agents.content" scheduler/ backend/` before deleting; if `agents.content_agent` (the separate live library module) is the only surviving reference, the helper goes.
  - Remove lock IDs `1010..1016` from `JOB_LOCK_IDS` in `scheduler/worker.py` (current lines 105-110). Confirm OPS-02 assertion still passes on boot.
  - Remove the comment block at `scheduler/worker.py` lines 138-145 referencing the retired sub-agent files.
  - Update `scheduler/worker.py:27` docstring ("by 7 independent sub-agent crons under agents.content.*") to reflect post-strip topology.
- **D-08:** **DB rows stay.** Historical `agent_runs`, `content_bundles`, `draft_items` rows from the retired sub-agents are preserved (matches the `260420-sn9` and `260423-k8n` precedents in CLAUDE.md — no Alembic migration, no DELETE). Source code disappears; data history persists.
- **D-09:** **Strip runs LAST, as the final task of Phase 8** (UI-06). All UI polish + visual QA must land first so that:
  - The verifier can confirm Phases 5-7 still render correctly with no surviving callers,
  - The dead-code commit is isolated and easily revertable,
  - `pytest scheduler/tests/` continues to pass after the test files are deleted (no surviving fixture or import depends on them).

### Visual QA Depth (DEFAULT — Claude's Discretion)
- **D-10:** **Manual eyeball pass at 1440x900 on the 3 active tabs only** (`/`, `/calendar`, `/viral`). No automated lighthouse/axe-core in this phase — that would expand scope. WCAG AA contrast is checked manually using the macOS DevTools color contrast inspector (or Tailwind's known-safe `zinc-100 on zinc-900` and `amber-500 on zinc-900` pairs). Legacy v2.0 routes (`/digest`, `/settings`) are NOT touched — they're not under TabbedDashboard and out of v2.1 polish scope.
- **D-11:** **QA checklist captured in the plan, executed at human-verify checkpoint.** The planner should generate a 1440x900 visual QA checklist (per tab: amber accent locations, hover transitions on cards, typography weight differentials, no contrast failures, no overflow at min-width). User runs through it after implementation lands.

### Claude's Discretion
- **`oklch` color values for the new semantic tokens.** Picking exact `oklch()` values for `--color-accent` etc. is a planner/researcher task — the goal is "matches Tailwind `amber-500` and `amber-400` visually." Direct hex (`#f59e0b`, `#fbbf24`) is acceptable if `oklch` is awkward in the surrounding token block.
- **Whether to commit the pill component as a standalone file** (`frontend/src/components/markdown/XHandlePill.tsx`) or inline it in the existing react-markdown `components` prop wherever react-markdown is used. Planner picks based on how many surfaces render X content.
- **Whether to extract a shared `<MarkdownContent>` wrapper** that bundles the rehype-sanitize + components-override config used by `SweeperCard` (and possibly `SummaryFeedPage` daily-summary cards). Could collapse duplication but adds an abstraction; planner decides.
- **Exact monospace numerics treatment for UI-03** — wrap engagement counts (♥123 ⟲45 💬12) in `<code>` tags via the same react-markdown component override, or use a simpler regex-replace in `_build_x_posts_md`. Either is fine.

### Folded Todos
None — no pending todos matched Phase 8 scope.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Domain & Design Direction
- `.planning/research/FEATURES.md` §"LINEAR-STYLE UI REDESIGN" — Dark + amber-500 token direction, density target ("Linear/Vercel dashboard")
- `.planning/research/PITFALLS.md` §6 "shadcn Tabs + Linear UI Redesign" — P1 (Tailwind v4 dark mode strategy), P2 (don't redefine zinc-*), P3 (dead-code strip safety)
- `.planning/research/ARCHITECTURE.md` §"Complete File Change Map" — MODIFIED vs UNCHANGED file list; confirms `AppShell.tsx` + `AppHeader.tsx` are structurally frozen

### Phase Inputs (must read)
- `.planning/REQUIREMENTS.md` §UI-01..UI-07 — full requirement text; UI-05 will be surgically rephrased in Wave 1
- `.planning/phases/06-content-calendar/06-CONTEXT.md` §D-09 — today-cell amber treatment (already in-flight)
- `.planning/phases/07-weekly-viral-sweeper/07-CONTEXT.md` §D-03 — X-API pivot rationale + which SWEEP-* requirements were rephrased

### Frontend Surfaces (the polish targets)
- `frontend/src/index.css` — Tailwind v4 `@theme inline` + `@custom-variant dark` already configured; semantic token additions go here
- `frontend/src/components/layout/AppHeader.tsx` — FROZEN, do not edit class names
- `frontend/src/components/layout/AppShell.tsx` — FROZEN
- `frontend/src/components/layout/TabNav.tsx` — `border-amber-500` already on active tab; verify hover transitions
- `frontend/src/components/viral/SweeperCard.tsx` — react-markdown `components` prop is the injection point for D-02 / D-04 pill renderer
- `frontend/src/pages/SummaryFeedPage.tsx` — daily summary cards, may share the markdown component config
- `frontend/src/pages/ContentCalendarPage.tsx` — calendar grid, already uses `ring-2 ring-amber-500 bg-amber-500/5` (Phase 6 D-09)
- `frontend/src/pages/WeeklyViralSweeperPage.tsx` — page wrapper for `SweeperCard`

### Backend / Markdown Producers (for understanding what gets rendered)
- `scheduler/agents/weekly_sweeper.py::_build_x_posts_md` — produces `* **[@handle](x.com/...)** (♥N ⟲N 💬N, score=N): {preview}` bullets
- `scheduler/agents/weekly_sweeper.py::_build_virality_md` — produces source-attributed virality bullets
- Sonnet system prompt section in `scheduler/agents/weekly_sweeper.py` (D-11 of Phase 7) — references `(@author_username)` in angles output

### Dead-Code Strip Targets (UI-06)
- `scheduler/agents/content/breaking_news.py`
- `scheduler/agents/content/threads.py`
- `scheduler/agents/content/quotes.py`
- `scheduler/agents/content/infographics.py`
- `scheduler/agents/content/gold_media.py`
- `scheduler/agents/content/gold_history.py`
- `scheduler/agents/content/__init__.py` — `run_text_story_cycle()` helper, after verifying no survivor
- `scheduler/tests/test_{breaking_news,threads,quotes,infographics,gold_media,gold_history}.py`
- `scheduler/tests/test_content_init.py` + `scheduler/tests/test_content_wrapper.py`
- `scheduler/worker.py:103-110` — `JOB_LOCK_IDS` entries `sub_breaking_news..sub_gold_history` (1010-1016)
- `scheduler/worker.py:27, 66, 138-145` — docstring + comments referencing retired sub-agents

### Historical / CLAUDE.md Context
- `CLAUDE.md` historical notes — `260420-sn9`, `260423-k8n` purges establish the "source out, data history kept" precedent that D-08 follows

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`@custom-variant dark (&:is(.dark *))`** in `index.css` — Tailwind v4 dark mode is class-based; semantic tokens can layer on cleanly without changing the dark mode strategy
- **shadcn `--color-*` custom properties** already in `index.css` `@theme inline` block — adding `--color-accent` family follows the established pattern
- **react-markdown `components` prop** in `SweeperCard.tsx` — the natural injection point for the X-handle pill renderer (D-04). Possibly extract to a shared `<MarkdownContent>` wrapper if the same config is used in `SummaryFeedPage`.
- **shadcn `Badge` component** at `frontend/src/components/ui/badge.tsx` — already used in `SweeperCard` for status badges; could be the base for the X-handle pill if a `variant="x-handle"` is added
- **`cn()` utility** at `frontend/src/lib/utils.ts` — standard for class composition

### Established Patterns
- **`bg-zinc-900` / `border-zinc-800` / `text-zinc-100|400`** is the locked surface palette — UI pass adds amber accents on top, never replaces zinc
- **Geist Variable font** loaded via `@fontsource-variable/geist` import — UI-03 weight differentiation works through `font-weight-{400,500,600}` Tailwind utilities; no font swap needed (and explicitly forbidden by UI-03)
- **react-markdown + `rehype-sanitize`** is the rendering pipeline for all markdown content — any new transform plugin must be sanitize-compatible

### Integration Points
- New semantic tokens land in `index.css` `@theme inline` block (existing structure)
- Pill component injects via react-markdown `components` prop on every surface that renders X-attributed markdown
- Dead-code strip touches `scheduler/worker.py` (lock IDs + comments + docstring) and deletes whole files — no module restructure

</code_context>

<specifics>
## Specific Ideas

- **Pill style is identical to the original UI-05 Reddit spec** — `font-mono text-xs bg-zinc-800/60 px-2 py-0.5 rounded` — just retargeted from `r/gold` to `@handle`. Visual consistency with the original design intent.
- **Amber-on-hover** is the unifying interaction language for accent-eligible surfaces (cards, pills, links) per D-03.

</specifics>

<deferred>
## Deferred Ideas

- **Mobile-responsive UI** — explicitly out of scope (single-user desktop constraint per PROJECT.md).
- **Light theme / theme toggle** — semantic tokens make this easier later, but not in v2.1.
- **Automated WCAG audit (lighthouse / axe-core CI)** — could be a v2.2 quick task; manual QA suffices for v2.1.
- **Sweeping refactor of existing `amber-500`/`amber-400` literal classes to semantic tokens** — D-05 leaves existing literals as-is; a follow-up cleanup phase or quick task could finish the migration if desired.
- **Sharing a `<MarkdownContent>` wrapper across `SweeperCard` + `SummaryFeedPage`** — left to planner's discretion (D in Claude's Discretion); if the planner sees high duplication it's a clean refactor, otherwise scope creep.

### Reviewed Todos (not folded)
None — no pending todos surfaced for Phase 8.

</deferred>

---

*Phase: 08-ui-polish-dead-code-strip*
*Context gathered: 2026-05-19*
