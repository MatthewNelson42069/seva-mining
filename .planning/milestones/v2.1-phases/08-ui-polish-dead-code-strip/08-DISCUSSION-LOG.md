# Phase 8: UI Polish + Dead-Code Strip - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-19
**Phase:** 08-ui-polish-dead-code-strip
**Areas discussed:** UI-05 reframe (X-API pivot)
**Areas captured as defaults:** Amber token strategy, Dead-code strip scope, Visual QA depth

---

## Gray Area Selection

User was offered 4 gray areas and selected 1 for discussion. The other 3 were captured as Claude's Discretion defaults in CONTEXT.md.

| Gray Area | Description | Selected |
|-----------|-------------|----------|
| UI-05 reframe (X-API pivot) | UI-05 still specs `r/gold` subreddit pills, but Phase 7 dropped Reddit. What replaces it for X posts? | ✓ |
| Amber token strategy | Semantic CSS tokens vs inline Tailwind classes; tradeoff between long-term theme-ability and faster execution. | |
| Dead-code strip scope | How aggressive — files only, files + tests, or full sweep including lock IDs + helper + comments. | |
| Visual QA depth + scope | Manual 1440x900 only, or also automated lighthouse/axe-core, or also touch legacy v2.0 routes. | |

---

## UI-05 Reframe — Pill Treatment

| Option | Description | Selected |
|--------|-------------|----------|
| Style @handles as monospace pills | Override react-markdown's link renderer so any `x.com` link gets wrapped in `<code className="font-mono text-xs bg-zinc-800/60 px-2 py-0.5 rounded">@handle</code>`. Closest 1:1 swap of the original `r/gold` pill aesthetic onto the X equivalent. | ✓ |
| Style engagement counts as pills | Reframe UI-05 around the metadata numerics (♥ ⟲ 💬, score). Dovetails with UI-03 ("monospace numerics for upvote/source counts"). | |
| Drop UI-05 entirely | The X-post bullet's `**[@handle](url)**` bold link already provides natural attribution — no pill needed. | |
| Style source_name attribution in virality bullets | Apply pills to source_names in "Most Cross-Referenced Stories" (`Reuters`, `Kitco`). Leaves X bullets untouched. | |

**User's choice:** Style @handles as monospace pills
**Notes:** Preserves the original UI-05 design intent (monospace attribution pill), just retargeted from Reddit's `r/subreddit` to X's `@handle`. REQUIREMENTS.md UI-05 will be surgically rephrased (not Dropped).

---

## UI-05 Reframe — Pill Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Everywhere @handle appears | Apply the monospace pill to any text matching `@\w+` inside react-markdown rendered content — covers Top X Posts bullets AND any @handle Sonnet drops into the 3 Content Angles section. | ✓ |
| Only the Top X Posts section | Pill applies only to the `[@handle](x.com/...)` link pattern in Top X Posts. Sonnet's angles section keeps plain text @handle references. | |
| Only when wrapped in a markdown link | Pill applies to any markdown link whose href contains `x.com` or `twitter.com`. Bare `@handle` text without a link stays plain. | |

**User's choice:** Everywhere @handle appears
**Notes:** Prevents the eye from seeing two different attribution styles in one card. Sonnet's angles section (Phase 7 D-11) writes `(@author_username)` references which now get the same treatment as the Top X Posts bullets.

---

## UI-05 Reframe — Click + Hover Behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Clickable + amber hover | Pill stays a clickable link opening `x.com/handle` in a new tab. On hover: `hover:border-amber-500/40 hover:text-amber-300` to match the broader UI-04 hover transition. | ✓ |
| Clickable, no hover accent | Pill remains a clickable link but keeps a neutral hover (just `hover:bg-zinc-700/60`). Quieter visual; safer if amber-on-hover feels too noisy with 10 pills stacked. | |
| Non-clickable styling only | Render the pill as plain styled text, not a link. | |

**User's choice:** Clickable + amber hover
**Notes:** Ties the pill into the broader amber accent system (UI-04 hover transitions) — gives a consistent interaction language across cards, pills, and links.

---

## Wrap-Up

| Option | Description | Selected |
|--------|-------------|----------|
| Capture defaults, move to context | Write CONTEXT.md with the UI-05 decisions locked + sensible defaults for the other three gray areas. | ✓ |
| Explore amber token strategy | | |
| Explore dead-code strip scope | | |
| Explore visual QA depth | | |

**User's choice:** Capture defaults, move to context
**Notes:** UI-01..04, UI-06, UI-07 are well-specced in ROADMAP. Defaults captured in CONTEXT.md §"Implementation Decisions" — semantic amber tokens (D-05), aggressive strip incl. tests + lock IDs + helper (D-07), manual 1440x900 QA on 3 active tabs only (D-10). Planner may deviate but has clear starting points.

## Claude's Discretion

Captured in CONTEXT.md §"Implementation Decisions / Claude's Discretion":
- `oklch` vs hex for new semantic tokens
- Whether the pill component is a standalone file or inline in react-markdown `components` prop
- Whether to extract a shared `<MarkdownContent>` wrapper
- Exact monospace numerics treatment for UI-03

## Deferred Ideas

Captured in CONTEXT.md §"Deferred Ideas":
- Mobile-responsive UI (single-user desktop constraint, v2.2+)
- Light theme / theme toggle
- Automated WCAG audit (lighthouse / axe-core CI)
- Sweeping refactor of existing `amber-500` literals to semantic tokens
- Shared `<MarkdownContent>` wrapper across `SweeperCard` + `SummaryFeedPage`
