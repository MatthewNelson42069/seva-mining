---
phase: 01-gold-news-card-web-feed
plan: "06"
subsystem: ui
tags: [react, react-markdown, rehype-sanitize, tanstack-query, vitest, xss, route-swap]

# Dependency graph
requires:
  - "01-02 — useSummaries() hook + SummaryCard/SummaryFeedResponse types"
  - "01-04 — GET /summaries endpoint"
provides:
  - "frontend/src/components/summary/SectionBlock.tsx — markdown renderer with XSS sanitizer"
  - "frontend/src/components/summary/SummaryCard.tsx — one summary card (title + badge + 3 sections)"
  - "frontend/src/pages/SummaryFeedPage.tsx — feed page at / with empty/loading/error/populated states"
  - "Route table: / → SummaryFeedPage; /queue + /agents/:slug → Navigate to /"
affects:
  - "Phase 1 milestone — operator can read summary cards at / in the browser"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "react-markdown + rehype-sanitize default schema for XSS defence at AST level"
    - "date-fns format(parseISO()) for PT-aware card title formatting"
    - "Intl.DateTimeFormat with timeZone:'America/Los_Angeles' for next-cron-fire computation"
    - "vi.spyOn(summariesApi, 'useSummaries') for hook-level mocking without MSW"
    - "div with rounded-lg border bg-card as card primitive (card.tsx not installed)"

key-files:
  created:
    - frontend/src/components/summary/SectionBlock.tsx
    - frontend/src/components/summary/SummaryCard.tsx
    - frontend/src/pages/SummaryFeedPage.tsx
    - frontend/src/components/summary/__tests__/SectionBlock.test.tsx
    - frontend/src/components/summary/__tests__/SummaryCard.test.tsx
    - frontend/src/pages/__tests__/SummaryFeedPage.test.tsx
  modified:
    - frontend/src/App.tsx

key-decisions:
  - "card.tsx primitive not installed — used div with rounded-lg border bg-card shadow-sm instead (plan explicitly documented this fallback; tests do not depend on Card primitive)"
  - "react-markdown v10 drops raw HTML blocks entirely (allowDangerousHtml: false default) — MORE conservative than rehype-sanitize alone; iframe test updated to use paragraph + iframe pattern"
  - "SummaryCard.test.tsx: test 7 queries for h2 with textContent='Lead' (not querySelector('h2')) because the card title is also an h2 element"
  - "No /summaries MSW handler added — vi.spyOn at hook level intercepts before any fetch"

requirements-completed:
  - FEED-01
  - FEED-02
  - FEED-03
  - FEED-04

# Metrics
duration: 4min
completed: "2026-05-06"
---

# Phase 1 Plan 06: Frontend Feed Page Summary

**3 components + 19 tests + App.tsx route swap — Instagram-style vertical feed at `/` with rehype-sanitize XSS defence and conditional status badges**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-05-06T16:41:00Z
- **Completed:** 2026-05-06T16:45:00Z
- **Tasks:** 3 (TDD for each)
- **Files created/modified:** 7

## Accomplishments

- `SectionBlock.tsx` renders markdown via ReactMarkdown + rehypeSanitize default schema; strips script/iframe/javascript: URLs at AST level before DOM touch
- `SummaryCard.tsx` renders title ("Summary as of {period_label} — {Month Day}"), conditional status badge (hidden on 'completed', amber on 'partial', destructive red on 'failed'), 3 SectionBlocks
- `SummaryFeedPage.tsx` calls `useSummaries(60)`, handles loading/error/empty/populated states; empty state computes next cron fire (08:00 PT or 12:00 PT) via Intl in America/Los_Angeles
- `App.tsx` route table reshaped: `/` → SummaryFeedPage; `/queue` + `/agents/:slug` → `<Navigate to="/" replace />`; `/login`, `/digest`, `/settings` preserved intact; unused `PerAgentQueuePage` import removed
- 19 tests pass: SectionBlock (7), SummaryCard (7), SummaryFeedPage (5)
- Full test suite: 81 tests, 13 files, 0 failures
- `tsc --noEmit` exits 0; `npm run build` exits 0 (629 kB bundle, no type errors)

## Component Files

| File | Exports | Description |
|------|---------|-------------|
| `frontend/src/components/summary/SectionBlock.tsx` | `SectionBlock`, `SectionBlockProps` | Section heading + ReactMarkdown(rehypeSanitize) or emptyFallback |
| `frontend/src/components/summary/SummaryCard.tsx` | `SummaryCard`, `SummaryCardComponentProps` | Title row + conditional badge + 3 SectionBlocks |
| `frontend/src/pages/SummaryFeedPage.tsx` | `SummaryFeedPage` | Top-level feed page calling useSummaries(60) |

## Test Files

| File | Tests | Description |
|------|-------|-------------|
| `frontend/src/components/summary/__tests__/SectionBlock.test.tsx` | 7 | Heading, markdown, null/empty fallback, script/iframe/javascript: XSS |
| `frontend/src/components/summary/__tests__/SummaryCard.test.tsx` | 7 | Title format, badge visibility x3, 3 sections, empty fallbacks, markdown wiring |
| `frontend/src/pages/__tests__/SummaryFeedPage.test.tsx` | 5 | Empty state, next-fire label, populated (2 cards), loading, error |

## App.tsx Route Changes

| Route | Before | After |
|-------|--------|-------|
| `/` | Navigate to `/agents/breaking-news` | `<SummaryFeedPage />` |
| `/queue` | (not registered) | `<Navigate to="/" replace />` |
| `/agents/:slug` | `<PerAgentQueuePage />` | `<Navigate to="/" replace />` |
| `/login` | Preserved | Preserved |
| `/digest` | Preserved | Preserved |
| `/settings` | Preserved | Preserved |

## Locked Decisions Implemented

- **Badge visibility:** `status === 'completed'` renders NO badge (clean default); `'partial'` renders amber-pill (`bg-amber-100 text-amber-900`); `'failed'` renders `variant="destructive"` red badge
- **Card title format:** `Summary as of {period_label} — {Month Day}` (e.g. "Summary as of 08:00 PT — April 27") — date computed via `format(parseISO(generated_at), 'MMMM d')`
- **Empty state copy:** "Waiting for first summary. Next fire at {HH:MM PT}." — next fire is 08:00 PT (if before 08:00 or after 12:00 PT) or 12:00 PT (if between 08:00 and 12:00 PT)
- **Sanitizer wiring:** `rehypePlugins={[rehypeSanitize]}` on ReactMarkdown — no `allowDangerousHtml`, no custom schema, default schema strips all unsafe elements at AST level
- **useSummaries(60):** Calls with limit=60 per plan spec; 5-min refetch + no focus refetch inherited from Plan 02 hook
- **Dead-code-only retirement:** `PerAgentQueuePage.tsx` source file NOT deleted; only the route and import removed

## Task Commits

1. `f25ea15` — `feat(01-06): SectionBlock component + XSS sanitizer tests`
2. `7f3f30c` — `feat(01-06): SummaryCard component + tests (title, badge, sections)`
3. `0f5f6a7` — `feat(01-06): SummaryFeedPage + App.tsx route swap`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] react-markdown v10 drops raw HTML entirely — iframe test assertion adjusted**
- **Found during:** Task 1 GREEN phase (SectionBlock tests)
- **Issue:** Test 6 expected `container.textContent` to contain `"safe text"` after the `</iframe>` tag. However, react-markdown v10 defaults to `allowDangerousHtml: false`, which drops the entire raw HTML block (including text after the closing tag). The container.textContent was only `"Gold News"` (the h3 heading).
- **Fix:** Adjusted test input to use a markdown paragraph on a separate line followed by the iframe on its own block: `"safe prefix\n\n<iframe ...></iframe>"`. The paragraph renders normally; the iframe block is stripped. This accurately tests that iframe elements cannot appear in the DOM.
- **Note:** react-markdown's default is MORE conservative than rehype-sanitize alone — raw HTML is dropped at parse time before rehype-sanitize even runs. This is defence-in-depth.
- **Files modified:** `frontend/src/components/summary/__tests__/SectionBlock.test.tsx`
- **Commit:** f25ea15

**2. [Rule 2 - Missing] card.tsx primitive absent — div wrapper used**
- **Found during:** Task 2 (SummaryCard implementation)
- **Issue:** Plan references `<Card><CardContent>` from `frontend/src/components/ui/card.tsx` but that file does not exist (shadcn card primitive was never installed). Plan explicitly documented this fallback: "If `frontend/src/components/ui/card.tsx` does NOT exist ... fall back to a `<div className="rounded-lg border bg-card p-6">` wrapper instead".
- **Fix:** Used `<div className="w-full rounded-lg border bg-card shadow-sm">` wrapper with equivalent visual styling. Tests do not depend on the Card primitive.
- **Files modified:** `frontend/src/components/summary/SummaryCard.tsx`
- **Commit:** 7f3f30c

**3. [Rule 1 - Bug] SummaryCard test 7 updated for multiple h2 elements**
- **Found during:** Task 2 (pre-emptive analysis before writing test)
- **Issue:** Plan's test 7 uses `container.querySelector('h2')` to find the react-markdown h2 ("Lead"), but SummaryCard itself renders an h2 for the card title. `querySelector` returns the FIRST h2 (the card title), not the markdown h2.
- **Fix:** Test queries `container.querySelectorAll('h2')` and finds the one with `textContent === 'Lead'` via `Array.from(h2Elements).find(...)`.
- **Files modified:** `frontend/src/components/summary/__tests__/SummaryCard.test.tsx`
- **Commit:** 7f3f30c

## Known Stubs

None — all three components are fully implemented and wired to real data sources. The `ontario_law_md` and `ontario_stats_md` fields render empty-state fallbacks in Phase 1 (by design — Phase 2/3 will populate them), but the SectionBlock components are complete and will render those fields when populated.

## Requirements Closed

- **FEED-01:** Feed page at `/` — `<Route path="/" element={<SummaryFeedPage />} />` in App.tsx
- **FEED-02:** Card structure + status badge — SummaryCard with title row, conditional badge, 3 SectionBlocks
- **FEED-03:** react-markdown + rehype-sanitize — SectionBlock.tsx wires both; 7 sanitizer tests verify XSS defence
- **FEED-04:** Redirect deprecated routes — `/queue` and `/agents/:slug` → Navigate to `/`
