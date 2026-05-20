---
phase: 08
slug: ui-polish-dead-code-strip
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-19
---

# Phase 08 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `08-RESEARCH.md` §Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework (frontend)** | Vitest 4.1.2 + @testing-library/react 16.3.2 + jsdom |
| **Framework (backend/scheduler)** | pytest + pytest-asyncio |
| **Config file (frontend)** | `frontend/package.json` (`"test": "vitest"`) — no vitest.config.ts; defaults |
| **Config file (scheduler)** | `scheduler/pyproject.toml` (pytest discovery via convention) |
| **Quick run command (frontend)** | `cd frontend && npm test -- --run` |
| **Quick run command (scheduler)** | `cd scheduler && uv run pytest scheduler/tests/test_worker.py -x` |
| **Full suite command (frontend)** | `cd frontend && npm test -- --run` |
| **Full suite command (scheduler)** | `cd scheduler && uv run pytest scheduler/tests/ -x` |
| **Estimated runtime (frontend full)** | ~5-8 seconds (121 tests today + Phase 8 additions) |
| **Estimated runtime (scheduler full)** | ~5 seconds (351 tests today, shrinks after strip) |

---

## Sampling Rate

- **After every task commit:**
  - Frontend: `cd frontend && npm test -- --run`
  - Backend strip: `cd scheduler && uv run pytest scheduler/tests/test_worker.py -x`
  - Grep verification scripts (per requirement): `bash scripts/verify-ui-04-hover-transitions.sh` etc.
- **After every plan wave:**
  - Full frontend vitest + full scheduler pytest + all grep scripts
- **Before `/gsd:verify-work`:**
  - Full frontend vitest green
  - Full scheduler pytest green (sub-agent test files DELETED, not skipped)
  - All grep verification scripts pass
  - Smoke: `cd scheduler && uv run python -c "from worker import JOB_LOCK_IDS, build_scheduler; assert len(set(JOB_LOCK_IDS.values())) == len(JOB_LOCK_IDS)"` succeeds
  - Human visual QA checklist (UI-SPEC §QA Checklist, 30+ items) signed off
- **Max feedback latency:** ~10 seconds (vitest full + grep scripts)

---

## Per-Task Verification Map

Plan-task IDs will be assigned by the planner. The req→test mapping below shows what evidence each requirement needs at execution time.

| Req ID | Behavior | Test Type | Automated Command | File Exists |
|--------|----------|-----------|-------------------|-------------|
| UI-01 | Semantic amber tokens + amber accent on active tab, status badges, today-cell, hover states | unit (CSS) + manual | `grep -n "brand-accent" frontend/src/index.css && grep -rn "ring-amber-500\|bg-amber-500" frontend/src/components/` | ❌ W0 — `frontend/__tests__/css/index-css.test.ts` |
| UI-02 | `p-6` minimum, `gap-6` between sections, `space-y-4` between markdown bullets | grep + manual | `bash scripts/verify-spacing-tokens.sh` | ❌ W0 — write the grep script |
| UI-03 | Headings 600, sub-headings 500, body 400; no font-light/font-bold/font-[NNN] | grep | `bash scripts/verify-ui-03-weights.sh` | ❌ W0 — write the grep script |
| UI-04 | Cards have `border-zinc-800` baseline + `hover:border-zinc-700 transition-colors` | grep + manual hover | `bash scripts/verify-ui-04-hover-transitions.sh` | ❌ W0 — write the grep script |
| UI-05 | `@handle` in markdown renders as monospace pill (replaces Reddit `r/gold` spec per D-01) | unit (component) + manual | `cd frontend && npm test -- --run src/components/markdown/__tests__/` | ❌ W0 — write `XHandlePill.test.tsx`, `MarkdownContent.test.tsx`, `rehypeHandleMentions.test.ts` |
| UI-06 | Dead-code strip — files removed, `JOB_LOCK_IDS` edited, OPS-02 still passes | integration (pytest) | `cd scheduler && uv run pytest scheduler/tests/test_worker.py -x && python -c "from worker import JOB_LOCK_IDS; assert len(set(JOB_LOCK_IDS.values())) == len(JOB_LOCK_IDS)"` | ✅ `test_worker.py` exists; MUST be updated in the strip commit (lines 106-118, 122-131, 149-150, 271-291) |
| UI-07 | 1440x900 visual pass — no layout regressions, no contrast failures, no broken shadcn interactions | manual (D-10) | Browser at 1440x900 + DevTools contrast inspector; UI-SPEC §QA Checklist (30+ items) | n/a — checklist documented in UI-SPEC, reproduced in 08-PLAN.md |

*Status legend: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky — populated by executor.*

---

## Wave 0 Requirements

- [ ] `frontend/src/components/markdown/__tests__/XHandlePill.test.tsx` — UI-05 pill rendering (renders as `<a>` with pill classes; href synth from bare `@handle`; opens new tab; `rel="noopener noreferrer"`)
- [ ] `frontend/src/components/markdown/__tests__/MarkdownContent.test.tsx` — UI-05 pipeline (rehype plugin transforms bare `@handle` text + `x.com`/`twitter.com` link both produce pills; non-X links render as normal anchors; sanitize still strips `<script>`)
- [ ] `frontend/src/components/markdown/__tests__/rehypeHandleMentions.test.ts` — rehype plugin in isolation (bare `@handle` → `<a>`, no double-wrap inside existing `<a>`, no match inside `<code>`)
- [ ] `frontend/__tests__/css/index-css.test.ts` — UI-01 semantic token presence (read `index.css` as string, assert `--color-brand-accent`, `--color-brand-accent-hover`, `--color-brand-accent-subtle` exist)
- [ ] `scripts/verify-ui-03-weights.sh` — UI-03 weight constraint (grep that only `font-normal`/`font-medium`/`font-semibold` appear in `frontend/src/**/*.tsx`; reverse-grep `font-light|font-bold|font-extrabold|font-\\[` returns 0)
- [ ] `scripts/verify-ui-04-hover-transitions.sh` — UI-04 hover consistency (grep that all card-class components have both `border-zinc-800` baseline AND `hover:border-zinc-700` AND `transition-colors`)
- [ ] `scripts/verify-spacing-tokens.sh` — UI-02 spacing density (grep for `p-6`, `gap-6`, `space-y-4` presence on Phase 8 surfaces; reverse-grep for `p-2|p-3|gap-2|gap-3` on card containers)
- [ ] `scripts/verify-dead-code-strip-safe.sh` — UI-06 pre-strip safety (grep `from agents.content`, `agents.content\\.`, `run_text_story_cycle`, lock IDs 1010-1016 across `scheduler/` and `backend/`; all must return zero non-self matches before strip proceeds)
- [ ] **Update existing** `scheduler/tests/test_worker.py` (lines 106-118, 122-131, 149-150, 271-291) — UI-06 regression-test update; not a new file but a Wave 0 dependency for the strip wave

**Framework install:** none needed — vitest 4.1.2 + pytest already in place.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Visual QA pass at 1440x900 across `/`, `/calendar`, `/viral` | UI-07 | Per D-10 — manual eyeball is mandated (no lighthouse/axe-core automation) | Open all 3 tabs at 1440x900 in browser; verify UI-SPEC §QA Checklist (30+ items); use DevTools contrast inspector on `text-amber-400` over `bg-amber-500/5`, all `text-zinc-*` over `bg-zinc-*` pairs. Sign off in the human-verify checkpoint (UI-07) |
| Pill hover renders amber accent | UI-05 / D-03 | TanStack + react-markdown render path needs browser to verify CSS pseudo-class transitions | Hover an `@handle` pill in the Top X Posts section of `/viral` → confirm `border-amber-500/40` + `text-amber-300` transition. Confirm click opens `x.com/{handle}` in new tab |
| No layout overflow / no broken shadcn interactions | UI-07 | Interaction quality not testable via Vitest jsdom (no real layout engine) | Open Dialog, Tabs, Dropdown, Select, RadioGroup primitives across all 3 tabs at 1440x900; no clipped corners, no broken keyboard nav, no z-index regressions |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (9 items above)
- [ ] No watch-mode flags (`--watch`, `--no-cov`-style flags forbidden)
- [ ] Feedback latency < 15s (vitest + grep verification)
- [ ] `nyquist_compliant: true` set in frontmatter at plan close

**Approval:** pending
