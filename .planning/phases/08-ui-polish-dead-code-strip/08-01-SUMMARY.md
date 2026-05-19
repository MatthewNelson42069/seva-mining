---
phase: 08-ui-polish-dead-code-strip
plan: 01
subsystem: testing
tags: [vitest, bash, grep, rehype, react-markdown, validation-scaffolding, nyquist, ui-polish]

# Dependency graph
requires:
  - phase: 04-content-purge
    provides: "CONTENT_CRON_AGENTS already emptied + agents.content.* imports neutered in scheduler/worker.py — required precondition for the Wave 0 pre-strip safety script to PASS today"
  - phase: 05-frontend-baseline
    provides: "Frozen AppHeader.tsx / AppShell.tsx / TabNav.tsx structural baseline — the UI-03 grep script excludes these from weight-constraint scanning"
  - phase: 07-weekly-viral-sweeper
    provides: "X-API pivot rationale (D-03) — markdown stubs assume @handle, not r/subreddit"
provides:
  - "RED vitest test stubs for XHandlePill, MarkdownContent, rehypeHandleMentions (3 files, 13 specs, all describe.skip-gated)"
  - "RED CSS semantic-token test (6 failing assertions today; turns GREEN in Wave 1)"
  - "Executable bash verification scripts for UI-02 (spacing), UI-03 (weights), UI-04 (hover transitions), UI-06 (pre-strip safety)"
  - "Variable-path dynamic-import pattern for vitest stubs that defeats Vite's static import analysis without losing TypeScript types"
  - "FROZEN-file exclusion convention for grep harnesses (UI-03 script excludes AppHeader/AppShell/TabNav/Sidebar/Digest/Settings)"
affects: [08-02-PLAN, 08-03-PLAN, 08-04-PLAN, gsd-ui-checker, nyquist-validator]

# Tech tracking
tech-stack:
  added: []  # Wave 0 adds no runtime deps; uses already-installed vitest 4.1.2 + testing-library + jsdom + bash
  patterns:
    - "Variable-path dynamic import (`await import(/* @vite-ignore */ VAR)`) to defer module resolution under describe.skip"
    - "Bash verification harness with `set -euo pipefail` strict mode + explicit exit codes (0=PASS, 1=FAIL)"
    - "Per-script FROZEN-file exclusion pattern when a constraint applies only to Phase 8 surfaces"

key-files:
  created:
    - "frontend/src/components/markdown/__tests__/XHandlePill.test.tsx (4 specs, describe.skip)"
    - "frontend/src/components/markdown/__tests__/MarkdownContent.test.tsx (5 specs, describe.skip)"
    - "frontend/src/components/markdown/__tests__/rehypeHandleMentions.test.ts (4 specs, describe.skip)"
    - "frontend/src/__tests__/css/index-css.test.ts (7 specs, 6 RED today + 1 negative-assertion PASS)"
    - "scripts/verify-ui-03-weights.sh (PASSES today — regression guard)"
    - "scripts/verify-ui-04-hover-transitions.sh (FAILS today — Wave 1 target)"
    - "scripts/verify-spacing-tokens.sh (PASSES today — regression guard)"
    - "scripts/verify-dead-code-strip-safe.sh (PASSES today — gates Wave 3 strip)"
  modified: []

key-decisions:
  - "CSS test placed at frontend/src/__tests__/css/index-css.test.ts (under src/) because tsconfig.app.json only includes src/ — keeps TypeScript checking active"
  - "Markdown test stubs use variable-path dynamic import to defeat Vite's static analysis (the plan's claim that describe.skip alone defers imports turned out to be false for Vite)"
  - "UI-03 weights script excludes 6 FROZEN files (AppHeader, AppShell, TabNav, Sidebar, DigestPage, SettingsPage) so it PASSES today as the plan requires"
  - "verify-dead-code-strip-safe.sh filter for agents.content_agent uses both slash-form (agents/content_agent for file paths) AND dot-form (agents.content_agent for import statements) to avoid false-positive flagging of the live module"

patterns-established:
  - "Vite import deferral: literal-string import() is statically analyzed; variable-indirection (`const PATH = '../X'; await import(PATH)`) defers resolution to runtime, which never executes under describe.skip"
  - "RED scaffolding contract: describe.skip + REDLINE comment + dynamic import = collection-safe RED stub that flips to active test with a single character edit in Wave 2"
  - "Grep verification scripts use exit code 0 for PASS and 1 for FAIL with explicit `set -euo pipefail`; multi-section scripts accumulate a `fail` counter and exit at the end"

requirements-completed: []  # Plan frontmatter has requirements_addressed: []

# Metrics
duration: 10min
completed: 2026-05-19
---

# Phase 08 Plan 01: Wave 0 Validation Scaffolding Summary

**RED vitest stubs + grep harness landed for UI-01/02/03/04/05/06 so Wave 1+2+3 have automated targets, making Phase 8 the project's first Nyquist-compliant phase.**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-05-19T17:33:13Z
- **Completed:** 2026-05-19T17:42:48Z
- **Tasks:** 3
- **Files created:** 8

## Accomplishments

- 3 vitest spec files under `frontend/src/components/markdown/__tests__/` (13 skipped specs) ready for Wave 2 (Plan 08-03) to flip into active RED-then-GREEN tests by changing `describe.skip` → `describe` and shipping `XHandlePill.tsx`, `MarkdownContent.tsx`, `rehypeHandleMentions.ts`.
- 1 CSS semantic-token test at `frontend/src/__tests__/css/index-css.test.ts` failing today with 6 RED assertions for the three `--color-brand-accent*` tokens that Wave 1 (Plan 08-02) adds to `index.css`.
- 4 executable bash grep scripts under `scripts/` covering UI-02 (spacing), UI-03 (weight constraint), UI-04 (hover transitions), and UI-06 (pre-strip safety). UI-04 is RED today (proves it catches the real Wave 1 gap); the other three PASS today as regression guards.
- Variable-path dynamic-import pattern documented inline in all 3 markdown stubs so the redline diff in Wave 2 is a single character.

## Task Commits

Each task was committed atomically:

1. **Task 1: Markdown test stubs (XHandlePill, MarkdownContent, rehypeHandleMentions)** — `646507b` (test)
2. **Task 2: CSS RED test + UI-02/03/04 grep harness** — `202a170` (test)
3. **Task 3: Pre-strip safety verification script** — `c57206d` (test)

**Plan metadata:** _(to be added in final commit below)_

## Files Created/Modified

### Markdown vitest stubs (Task 1)
- `frontend/src/components/markdown/__tests__/XHandlePill.test.tsx` — 4 specs covering pill rendering, target=_blank/rel=noopener, canonical class string from D-01, and amber hover from D-03
- `frontend/src/components/markdown/__tests__/MarkdownContent.test.tsx` — 5 specs covering markdown-link → pill, bare-text → pill, non-X anchor stays default, sanitize strips `<script>`, code-fence handles stay literal
- `frontend/src/components/markdown/__tests__/rehypeHandleMentions.test.ts` — 4 specs driving the rehype plugin against synthetic hast trees (split single text node, skip inside `<a>`, skip inside `<code>`, multiple handles)

### CSS RED test + grep scripts (Task 2)
- `frontend/src/__tests__/css/index-css.test.ts` — 7 specs (6 RED, 1 PASS) asserting Wave 1's brand-accent token additions
- `scripts/verify-ui-03-weights.sh` — UI-03 reverse-grep with FROZEN-file exclusions (PASSES today)
- `scripts/verify-ui-04-hover-transitions.sh` — UI-04 hover/border/transition coverage on SummaryCard, SweeperCard, DayCell (FAILS today — only DayCell carries the hover; Wave 1 fixes SummaryCard + SweeperCard)
- `scripts/verify-spacing-tokens.sh` — UI-02 spacing density checks on SummaryCard, SweeperCard, SectionBlock (PASSES today)

### Pre-strip safety (Task 3)
- `scripts/verify-dead-code-strip-safe.sh` — 7-section pre-strip gate (PASSES today; Wave 3 must re-run before deleting anything)

## CSS Test Path Choice

Path: `frontend/src/__tests__/css/index-css.test.ts` (under `src/`)

Rationale: `frontend/tsconfig.app.json` declares `"include": ["src"]` — placing the file at `frontend/__tests__/css/` would silently drop it from TypeScript checking. vitest's default include glob (`**/*.{test,spec}.?(c|m)[jt]s?(x)`) picks the file up under `src/` automatically with zero config change. The `resolve(__dirname, '../../index.css')` traversal walks `src/__tests__/css/ → src/__tests__/ → src/index.css` correctly.

## Current PASS/FAIL State of Each Verification Artifact

| Artifact | State today | Wave that flips it | Why it's in this shape |
|----------|------------|--------------------|------------------------|
| `XHandlePill.test.tsx` (describe.skip) | SKIPPED (collects clean) | Wave 2 / Plan 08-03 (flip skip + ship XHandlePill.tsx) | Production module doesn't exist yet |
| `MarkdownContent.test.tsx` (describe.skip) | SKIPPED (collects clean) | Wave 2 / Plan 08-03 | Production module doesn't exist yet |
| `rehypeHandleMentions.test.ts` (describe.skip) | SKIPPED (collects clean) | Wave 2 / Plan 08-03 | Production module doesn't exist yet |
| `frontend/src/__tests__/css/index-css.test.ts` | **6 RED, 1 PASS** | Wave 1 / Plan 08-02 (add 3 brand-accent tokens to index.css) | Tokens don't exist in index.css yet |
| `scripts/verify-ui-03-weights.sh` | **PASS** (exit 0) | n/a — regression guard | No forbidden weights in Phase 8 surfaces today |
| `scripts/verify-ui-04-hover-transitions.sh` | **FAIL** (exit 1) | Wave 1 / Plan 08-02 (add `hover:border-zinc-700 transition-colors` to SummaryCard + SweeperCard) | Only DayCell carries the hover pattern; the other two cards inherit shadcn defaults |
| `scripts/verify-spacing-tokens.sh` | **PASS** (exit 0) | n/a — regression guard | All Phase 8 surfaces already carry p-6+, space-y-{5,6}, prose-sm |
| `scripts/verify-dead-code-strip-safe.sh` | **PASS** (exit 0) | n/a — gates Wave 3 / Plan 08-04 Task 1 | Phase 4 already emptied CONTENT_CRON_AGENTS; no live caller outside the dead package |

Vitest full-suite shape: **6 failed (CSS test RED by design)** | 122 passed | 13 skipped (markdown stubs) = 141 specs across 23 files.

## Decisions Made

- **CSS test location:** `frontend/src/__tests__/css/` instead of `frontend/__tests__/css/` because `tsconfig.app.json` restricts include to `src/`. Placing it outside would skip TypeScript checking and Node's `__dirname`-based path traversal would also need adjustment.
- **Vite import-deferral pattern:** `describe.skip` alone does NOT defer static imports — Vite's import-analysis runs at transform time and hard-fails on missing modules. Use `const PATH = '../X'; await import(/* @vite-ignore */ PATH)` inside `it` bodies so the import literal is non-static AND only executes when the test runs (which it never does under `.skip`). This pattern is documented inline in every stub.
- **UI-03 FROZEN-file exclusion:** AppHeader.tsx and Sidebar.tsx both use `font-bold` on the brand-mark "S" element. Both are FROZEN per 08-UI-SPEC §Component Inventory. The plan's UI-03 reverse-grep would have failed today on those frozen surfaces, contradicting the plan's "likely PASSES today" claim. Script excludes 6 frozen files (the 3 layout primitives, Sidebar, DigestPage, SettingsPage) so UI-03 enforces the constraint on Phase 8 surfaces only.
- **Pre-strip filter dot/slash duality:** The plan's draft filter `grep -v "agents/content_agent"` (slash) missed import statements like `from agents.content_agent import ...` (dot). Filter now matches both forms to keep the live `agents.content_agent` module out of the dead-code report.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `describe.skip` does not defer static imports under Vite**
- **Found during:** Task 1 (vitest verification of markdown stubs)
- **Issue:** The plan's `<interfaces>` section claimed "describe.skip keeps the imports unevaluated at collection time so missing production files do NOT cause errors." That is true for vitest's own collection but false for Vite's import-analysis pass, which runs BEFORE vitest sees the file and hard-fails on missing modules (`Failed to resolve import "../XHandlePill"`). All 3 markdown test files failed to load.
- **Fix:** Replaced static `import { X } from '../X'` with variable-indirection dynamic import inside each `it` body: `const PATH = '../X'; const { X } = await import(/* @vite-ignore */ PATH)`. Vite's static analyzer only inspects literal string arguments to `import()`; a variable forces runtime resolution. Under `describe.skip` the `it` bodies never execute and the dynamic import never runs.
- **Files modified:** All 3 files in `frontend/src/components/markdown/__tests__/`
- **Verification:** `cd frontend && npm test -- --run src/components/markdown/__tests__/` reports "3 skipped (3) | 13 skipped (13)" cleanly; full vitest suite is 122 passed + 13 skipped (excluding the intentionally-RED CSS test).
- **Committed in:** `646507b` (Task 1 commit)

**2. [Rule 1 - Bug] UI-03 weights script flagged frozen AppHeader/Sidebar font-bold usage**
- **Found during:** Task 2 (running `verify-ui-03-weights.sh` after creation)
- **Issue:** Initial script as drafted from the plan would fail today because `font-bold` appears in two frozen files (`AppHeader.tsx` brand-mark, `Sidebar.tsx` brand-mark). Plan acceptance criterion required the script to exit 0 today. Frozen Phase 5 files are explicitly out of UI-03's scope per 08-UI-SPEC §Component Inventory §FROZEN files.
- **Fix:** Added `EXCLUDE_PATTERN` filtering 6 files: components/layout/{AppHeader,AppShell,TabNav,Sidebar}.tsx and pages/{DigestPage,SettingsPage}.tsx. UI-03 now scans Phase 8 + non-frozen v2.1 surfaces only.
- **Files modified:** `scripts/verify-ui-03-weights.sh`
- **Verification:** Script now exits 0; both reverse-grep checks PASS.
- **Committed in:** `202a170` (Task 2 commit)

**3. [Rule 1 - Bug] Pre-strip script filter pattern path-separator mismatch**
- **Found during:** Task 3 (running `verify-dead-code-strip-safe.sh` after creation)
- **Issue:** Section 1 (live-imports check) flagged `scheduler/agents/weekly_sweeper.py:47: from agents.content_agent import deduplicate_stories` and `scheduler/agents/daily_summary.py:33: from agents.content_agent import fetch_stories` as false positives. The plan's draft filter `grep -v "agents/content_agent"` uses path-separator slash, but the actual import statements use module-separator dot. The live module `agents.content_agent` is a separate file that must stay; only the `agents.content.*` package is dead.
- **Fix:** Added both filter forms: `grep -v "agents/content_agent"` AND `grep -v "agents\.content_agent"`. Also tightened the primary grep to `from agents\.content[^_a-zA-Z]|import agents\.content[^_a-zA-Z]` so `agents.content_agent` doesn't satisfy the initial match in the first place.
- **Files modified:** `scripts/verify-dead-code-strip-safe.sh`
- **Verification:** Section 1 now reports "PASS — no live imports of dead agents.content.* package outside the package or its tests".
- **Committed in:** `c57206d` (Task 3 commit)

**4. [Rule 1 - Bug] CONTENT_CRON_AGENTS regex did not tolerate type annotation**
- **Found during:** Task 3 (running `verify-dead-code-strip-safe.sh`)
- **Issue:** Initial regex `^CONTENT_CRON_AGENTS\s*=\s*\[\s*\]` did not match the real declaration `CONTENT_CRON_AGENTS: list[tuple[str, object, str, int, dict]] = []` in `scheduler/worker.py:147` (Python 3.12 PEP 526 variable annotation). Script flagged Section 4 as FAIL, preventing exit 0.
- **Fix:** Regex now tolerates optional type annotation: `^CONTENT_CRON_AGENTS(\s*:[^=]*)?\s*=\s*\[\s*\]`.
- **Files modified:** `scripts/verify-dead-code-strip-safe.sh`
- **Verification:** Section 4 now PASSES; full script exits 0.
- **Committed in:** `c57206d` (Task 3 commit)

---

**Total deviations:** 4 auto-fixed (1 blocking — Rule 3; 3 bugs — Rule 1)
**Impact on plan:** All deviations are local fixes to grep filters and import shapes; no scope change, no architectural movement. The plan's intent (Wave 0 scaffolding that lets Wave 1+2+3 execute against automated targets) is fully delivered.

## Issues Encountered

- **Vitest import deferral semantics:** The Phase 4-7 precedent referenced in the plan (`pytest.skip()` before lazy import) does not translate to Vite/vitest. Vite analyzes ES module imports at transform time regardless of test framework decoration. The variable-path indirection pattern is now documented in all 3 stubs as the project-wide convention for future RED test scaffolding.
- **Plan vs objective tension on test RED-ness:** The objective said "tests MUST be created in a state where they fail. Do NOT add `.skip`." The plan said "wrap in describe.skip so vitest collects without import errors." Resolved by following the plan (per project precedent and acceptance criteria) — markdown stubs use `describe.skip` (technically `skipped` not `failed`), while the CSS test is genuinely RED (failing). Both flip to GREEN in Wave 1+2. The redline edit for the markdown stubs is `s/describe.skip/describe/g` once production modules land.

## Next Wave Readiness

- **Wave 1 / Plan 08-02** can begin immediately. Targets to turn GREEN:
  - `frontend/src/__tests__/css/index-css.test.ts` → add 3 brand-accent token declarations + 3 dark-scope bindings to `frontend/src/index.css` per 08-UI-SPEC §Color §Semantic accent token additions
  - `scripts/verify-ui-04-hover-transitions.sh` → add `hover:border-zinc-700 transition-colors` to `frontend/src/components/summary/SummaryCard.tsx` outer wrapper and `frontend/src/components/viral/SweeperCard.tsx` outer wrapper
- **Wave 2 / Plan 08-03** can begin once Wave 1 is GREEN. Targets:
  - Ship `frontend/src/components/markdown/{XHandlePill.tsx,MarkdownContent.tsx,rehypeHandleMentions.ts}` per 08-RESEARCH §Code Examples §Example 1 + §Pattern 3
  - In each `__tests__/` file: change `describe.skip(...)` → `describe(...)` so the suite runs the assertions
  - Migrate `SweeperCard.tsx` (and `SectionBlock.tsx` if planner chose duplication) to use `<MarkdownContent>` instead of bare `<ReactMarkdown>`
- **Wave 3 / Plan 08-04** Task 1 MUST run `bash scripts/verify-dead-code-strip-safe.sh` and confirm exit 0 BEFORE deleting any sub-agent source/test file. The script is now the gate.

## Self-Check: PASSED

All 8 created files verified present on disk. All 3 task commits verified present in git log (`646507b`, `202a170`, `c57206d`). Plan-level verification confirmed: vitest collects all 4 new test files cleanly; UI-03 / spacing / pre-strip scripts PASS with exit 0; UI-04 / CSS test are RED today as the plan requires.

---
*Phase: 08-ui-polish-dead-code-strip*
*Completed: 2026-05-19*
