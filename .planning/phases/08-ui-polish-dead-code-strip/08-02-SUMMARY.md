---
phase: 08-ui-polish-dead-code-strip
plan: 02
subsystem: ui
tags: [tailwind-v4, css-tokens, oklch, shadcn, react, dark-mode, hover-transitions]

# Dependency graph
requires:
  - phase: 08-01
    provides: "Wave 0 RED test scaffolds (src/__tests__/css/index-css.test.ts) and three verify-*.sh grep scripts; provides the failing automation that this wave flips GREEN"
  - phase: 05
    provides: "Frozen AppShell/AppHeader/TabNav baseline that this wave preserves byte-identically (D-06 zinc untouched)"
  - phase: 06
    provides: "DayCell.tsx already shipping `hover:border-zinc-700 transition-colors` (line 89) — verified, not modified"
provides:
  - "3 semantic amber tokens addressable as Tailwind v4 utilities: bg-brand-accent, border-brand-accent, text-brand-accent, ring-brand-accent-subtle (plus hover/subtle variants)"
  - "Uniform UI-04 hover treatment across all 3 card-class components (SummaryCard, SweeperCard, DayCell)"
  - "Wave 2-ready visual baseline: XHandlePill's amber-hover pattern can now reference semantic tokens instead of literal amber-500"
affects: [08-03, 08-04, future X-handle pill, future v2.2 light theme]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Tailwind v4 @theme inline token binding via var() aliasing (--color-NAME: var(--NAME)) — new code prefers `brand-accent` semantic names over literal amber-500"
    - "Brand-prefix namespace (brand-accent) to coexist with shadcn's --color-accent (muted-neutral hover surface) without collision"
    - "Card hover pattern: border baseline + hover:border-zinc-700 + transition-colors uniformly across all card components"

key-files:
  created: []
  modified:
    - "frontend/src/index.css (added 6 lines: 3 in @theme inline, 3 in .dark)"
    - "frontend/src/components/summary/SummaryCard.tsx (1 className edit on outer cn())"
    - "frontend/src/components/viral/SweeperCard.tsx (1 className edit on outer cn())"
    - "frontend/src/__tests__/css/index-css.test.ts (ESM __dirname + node types fix to unblock tsc build)"

key-decisions:
  - "OKLCH values committed verbatim from 08-UI-SPEC §Color: --brand-accent oklch(0.769 0.188 70.08), --brand-accent-hover oklch(0.828 0.189 84.429), --brand-accent-subtle oklch(0.769 0.188 70.08 / 0.05)"
  - "Brand-prefix namespace enforced — shadcn --color-accent (oklch(0.269 0 0)) preserved, never clobbered"
  - "Tokens declared under .dark { ... } ONLY — D-10 explicitly defers light theme to v2.2; no :root binding added"
  - "DayCell.tsx and SectionBlock.tsx verified compliant with no edits (DayCell line 89 shipped hover; SectionBlock h3 = text-sm font-semibold, markdown wrapper = prose-sm)"

patterns-established:
  - "Tailwind v4 semantic-token addition: add `--color-X: var(--X)` inside the SINGLE existing @theme inline block + bind value under .dark — never create a second @theme inline block (Pitfall 1 defense)"
  - "Card hover uniformity: every card-class component uses `border bg-card hover:border-zinc-700 transition-colors` (UI-04 contract)"

requirements-completed: [UI-01, UI-02, UI-03, UI-04]

# Metrics
duration: 2min
completed: 2026-05-19
---

# Phase 8 Plan 02: Wave 1 UI Polish Summary

**3 semantic amber tokens (--color-brand-accent[-hover/-subtle]) added to Tailwind v4 @theme inline + uniform UI-04 hover treatment (`hover:border-zinc-700 transition-colors`) applied to SummaryCard and SweeperCard, making all 3 card-class components visually consistent.**

## Performance

- **Duration:** 2 min
- **Started:** 2026-05-19T17:47:13Z
- **Completed:** 2026-05-19T17:49:44Z
- **Tasks:** 2
- **Files modified:** 4 (index.css, SummaryCard.tsx, SweeperCard.tsx, index-css.test.ts)

## Accomplishments

- **UI-01 (semantic tokens):** Added 3 brand-prefixed tokens inside the existing `@theme inline { ... }` block in `frontend/src/index.css`, with concrete OKLCH values bound under `.dark`. Tailwind v4 now emits `bg-brand-accent`, `border-brand-accent`, `text-brand-accent`, `ring-brand-accent-subtle` (plus hover and subtle variants) as valid utility classes — confirmed in `dist/assets/index-*.css` after build.
- **UI-04 (hover transitions):** Appended `hover:border-zinc-700 transition-colors` to the outer `cn()` className on SummaryCard.tsx and SweeperCard.tsx. All 3 card-class components (SummaryCard, SweeperCard, DayCell) now render with consistent hover behavior.
- **UI-02 + UI-03:** Verified SectionBlock.tsx already meets the contract (`text-sm font-semibold` on h3 = UI-03 weight 600; `prose-sm` on markdown wrapper = UI-02 bullet rhythm). No edits made.
- **Wave 0 gates flipped:** CSS test (`src/__tests__/css/index-css.test.ts`) went from 6 failing assertions to 7/7 passing. `scripts/verify-ui-04-hover-transitions.sh` went from exit 1 to exit 0. Regression scripts (`verify-ui-03-weights.sh`, `verify-spacing-tokens.sh`) stayed GREEN.
- **D-06 invariant preserved:** zinc-* tokens untouched (0 `--color-zinc-*` declarations added/changed); frozen `AppShell.tsx`, `AppHeader.tsx`, `TabNav.tsx` confirmed byte-identical (`git diff --stat HEAD` returned empty for those paths).

## Task Commits

Each task was committed atomically:

1. **Task 1: Add 3 semantic amber tokens to frontend/src/index.css (UI-01)** — `f7e095d` (feat)
2. **Task 2: Apply UI-04 hover transitions to SummaryCard + SweeperCard; verify DayCell + SectionBlock** — `8d4a482` (feat)

## Files Created/Modified

### Modified

- **`frontend/src/index.css`** — Added 6 lines total:
  - Inside the existing `@theme inline { ... }` (after `--radius-4xl`):
    ```css
    --color-brand-accent: var(--brand-accent);
    --color-brand-accent-hover: var(--brand-accent-hover);
    --color-brand-accent-subtle: var(--brand-accent-subtle);
    ```
  - Inside the existing `.dark { ... }` (after `--sidebar-ring`):
    ```css
    --brand-accent: oklch(0.769 0.188 70.08);
    --brand-accent-hover: oklch(0.828 0.189 84.429);
    --brand-accent-subtle: oklch(0.769 0.188 70.08 / 0.05);
    ```
- **`frontend/src/components/summary/SummaryCard.tsx`** — One-line className edit on the outer wrapper:
  - Before: `cn('w-full rounded-lg border bg-card shadow-sm', className)`
  - After:  `cn('w-full rounded-lg border bg-card shadow-sm hover:border-zinc-700 transition-colors', className)`
- **`frontend/src/components/viral/SweeperCard.tsx`** — One-line className edit on the outer wrapper:
  - Before: `cn('w-full rounded-lg border bg-card shadow-sm', className,)`
  - After:  `cn('w-full rounded-lg border bg-card shadow-sm hover:border-zinc-700 transition-colors', className,)`
- **`frontend/src/__tests__/css/index-css.test.ts`** — Deviation fix (see below): added `/// <reference types="node" />` and switched to ESM `fileURLToPath(import.meta.url)` so `tsc -b` resolves `fs`/`path`/`__dirname` without polluting the app-code `types` array.

### Verified (no edit)

- **`frontend/src/components/calendar/DayCell.tsx`** — Line 89 already ships `hover:border-zinc-700 transition-colors` (Phase 6 D-09 baseline). `grep -c "hover:border-zinc-700"` returns 1.
- **`frontend/src/components/summary/SectionBlock.tsx`** — h3 uses `text-sm font-semibold` (UI-03 weight 600); markdown wrapper uses `prose-sm` (UI-02 bullet rhythm). `grep -c "font-semibold"` returns 1; `grep -c "prose-sm"` returns 1.

## Decisions Made

- **OKLCH values committed verbatim from 08-UI-SPEC §Color** — no hex fallback used, no interpolation done. Visual equivalents are amber-500 / amber-400 / amber-500-with-5%-alpha per the design spec.
- **Brand-prefix namespace enforced** — shadcn's `--color-accent` (line 29) remained intact. The CSS test's Dimension D-06 assertion (`expect(stripped.match(/--color-accent\s*:/g)).toBeLessThanOrEqual(1)`) passes.
- **`.dark`-only binding** — Per D-10, light theme deferred to v2.2; no `:root` overrides added.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed pre-existing Wave 0 tsc regression in `index-css.test.ts`**
- **Found during:** Task 1 (Add semantic amber tokens — running `npm run build` per acceptance criterion)
- **Issue:** The Wave 0 test file `frontend/src/__tests__/css/index-css.test.ts` (added in commit `202a170` by Plan 08-01) imports `fs`, `path`, and uses CommonJS `__dirname`. `tsconfig.app.json` sets `"types": ["vite/client"]` (restrictive list — no `node`), and includes `src/` (which now covers the test file). Result: `npm run build` fails with `TS2307: Cannot find module 'fs'` / `TS2304: Cannot find name '__dirname'`. Stash-test confirmed this regression existed at `HEAD` before any 08-02 edit. The plan's Task 1 acceptance criterion explicitly requires `npm run build` to exit 0, so the build had to be unblocked here.
- **Fix:** Added `/// <reference types="node" />` triple-slash at the top of `index-css.test.ts` (scopes Node types to that single file without polluting the app-code `types` array). Replaced CommonJS `__dirname` with ESM-friendly `dirname(fileURLToPath(import.meta.url))` since Vitest defaults to ESM. The CSS test still passes 7/7 after the change.
- **Files modified:** `frontend/src/__tests__/css/index-css.test.ts`
- **Verification:** `cd frontend && npm run build` exits 0; emitted `dist/assets/index-*.css` contains `brand-accent`, `brand-accent-hover`, `brand-accent-subtle` (confirmed by grep). `npm test -- --run` exits 0 (128 passed | 13 skipped — unchanged from pre-08-02 baseline).
- **Committed in:** `f7e095d` (part of Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 3 — pre-existing Wave 0 blocking issue uncovered by Task 1's build acceptance criterion)
**Impact on plan:** Surgical fix to the Wave 0 test file. No scope creep — the test still passes and now `tsc -b` resolves cleanly. The triple-slash directive scopes Node types to that single test file, preserving the original intent of keeping `types: ["vite/client"]` restrictive in app code.

## Issues Encountered

None beyond the deviation above.

## Wave 0 Gate Status Post-Wave 1

| Gate | Pre-08-02 | Post-08-02 |
|------|-----------|------------|
| `src/__tests__/css/index-css.test.ts` | 6 fail / 1 pass | **7 pass / 0 fail** |
| `scripts/verify-ui-04-hover-transitions.sh` | exit 1 (RED — SummaryCard + SweeperCard missing) | **exit 0 (GREEN — all 3 cards pass)** |
| `scripts/verify-ui-03-weights.sh` | exit 0 | **exit 0 (still GREEN)** |
| `scripts/verify-spacing-tokens.sh` | exit 0 | **exit 0 (still GREEN)** |
| `npm test -- --run` (full suite) | 122 pass / 13 skipped / 6 fail (CSS) | **128 pass / 13 skipped / 0 fail** |
| `npm run build` (tsc + vite) | FAIL (TS2307 fs/path/__dirname) | **PASS** |

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- **Wave 2 (08-03) unblocked:** XHandlePill component can now reference `bg-brand-accent-subtle` / `hover:border-brand-accent` / `hover:text-brand-accent-hover` semantic utilities instead of literal `amber-500/40` / `amber-400` / `amber-300` classes. Existing literal usages in SweeperCard status banners and DayCell today-cell stay as-is per D-05.
- **Wave 4 (08-04) unblocked:** The Wave 0 CSS test passing means the human-verify checkpoint has direct automated evidence that the token contract holds; the 1440x900 visual QA pass can focus on rendered output without needing to verify token source.
- **D-06 invariant intact:** Phase 5 frozen layout files render byte-identically. Phase 7 SweeperCard structure preserved (only the outer wrapper className changed; the inner three `<ReactMarkdown>` invocations remain unmodified for Wave 2 to consume).

## Self-Check: PASSED

Verified all claims via filesystem and git:

- `frontend/src/index.css`: FOUND (`grep -c "color-brand-accent"` = 3, `grep -c "^@theme inline"` = 1, `grep -c "^\s*--color-zinc-"` = 0)
- `frontend/src/components/summary/SummaryCard.tsx`: FOUND (`grep -c "hover:border-zinc-700"` = 1)
- `frontend/src/components/viral/SweeperCard.tsx`: FOUND (`grep -c "hover:border-zinc-700"` = 1)
- `frontend/src/components/calendar/DayCell.tsx`: FOUND (`grep -c "hover:border-zinc-700"` = 1) — verified, not modified
- `frontend/src/components/summary/SectionBlock.tsx`: FOUND (font-semibold + prose-sm) — verified, not modified
- Commit `f7e095d`: FOUND (Task 1 — feat(08-02): UI-01 semantic amber tokens)
- Commit `8d4a482`: FOUND (Task 2 — feat(08-02): UI-04 hover transitions on SummaryCard + SweeperCard)
- Frozen layout files: `git diff --stat HEAD~2 -- frontend/src/components/layout/AppHeader.tsx frontend/src/components/layout/AppShell.tsx frontend/src/components/layout/TabNav.tsx` returns empty
- All 4 Wave 0 verification gates: GREEN (CSS test 7/7, hover script exit 0, weights script exit 0, spacing script exit 0)
- Build: `npm run build` exits 0 with brand-accent utilities in emitted CSS

---
*Phase: 08-ui-polish-dead-code-strip*
*Completed: 2026-05-19*
