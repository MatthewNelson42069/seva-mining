---
quick_task: 260423-lvp
slug: add-analytical-historical-fallback-to-sub-infographics
subsystem: scheduler/agents/content/infographics + scheduler/agents/content_agent
tags: [infographics, fallback, analytical-historical, 2-per-day-guarantee, serpapi, tdd]
completed: 2026-04-23
mode: quick
commit_strategy: atomic-per-task (5 impl commits, 1 validation sweep)

key-decisions:
  - "Path A for items_queued signal: run_text_story_cycle return type None → int. Lower blast radius than DB re-query."
  - "Separate AgentRun row for fallback with agent_name=sub_infographics, notes.phase=analytical_fallback."
  - "Deterministic date-seeded shuffle for query rotation (date.today().toordinal() seed)."
  - "fetch_analytical_historical_stories is NOT cached — rare invocation, query-specific."
  - "_run_analytical_fallback returns int (queued count) for logging parity."
  - "3 existing test fixtures updated to patch _run_analytical_fallback(return_value=0) to prevent double session opens."

key-files:
  created: []
  modified:
    - scheduler/agents/content_agent.py        # +fetch_analytical_historical_stories
    - scheduler/agents/content/__init__.py     # run_text_story_cycle None → int
    - scheduler/agents/content/infographics.py # +ANALYTICAL_HISTORICAL_QUERIES +_select_analytical_queries +_run_analytical_fallback, updated run_draft_cycle
    - scheduler/tests/test_content_agent.py    # +2 new tests
    - scheduler/tests/test_infographics.py     # +7 new tests, 3 existing tests patched

tech-stack:
  added: []
  patterns:
    - "Two-phase pipeline: news phase first, fallback fires only on shortfall"
    - "Day-seeded deterministic shuffle for analytical query rotation"
    - "Separate AgentRun row per phase for clean telemetry"
---

# Quick Task 260423-lvp: Add Analytical-Historical Fallback to sub_infographics — SUMMARY

**One-liner:** Two-phase infographic pipeline guaranteeing 2/day via day-seeded analytical-historical SerpAPI fallback when news produces fewer than 2, using existing `_draft` + gold gate unchanged.

## Tasks Completed

| Task | Description | Commit SHA | Type |
|------|-------------|------------|------|
| T1 | Add `fetch_analytical_historical_stories` to content_agent.py | `d8b88ed` | feat |
| T2 | `run_text_story_cycle` return type `None → int` | `738a811` | refactor |
| T3 | Add `ANALYTICAL_HISTORICAL_QUERIES` + `_select_analytical_queries` to infographics.py | `0f400c2` | feat |
| T4 | Add `_run_analytical_fallback` helper to infographics.py | `bd344f6` | feat |
| T5 | Wire two-phase `run_draft_cycle` + update affected existing tests | `27c4138` | feat |
| T6 | Final validation sweep | (no commit — all gates green) | validation |

## Test Count Delta

- **Before:** 127 tests
- **After:** 136 tests
- **Delta:** +9 tests

Breakdown:
- `test_content_agent.py`: +2 (T1 — `fetch_analytical_historical_stories` shape + no-client behavior)
- `test_infographics.py`: +7 (T3: 1 rotation test; T4: 3 fallback tests; T5: 3 two-phase wiring tests)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] ruff format applied to modified files only**
- **Found during:** T1
- **Issue:** Pre-existing `ruff format` violations in unmodified files (breaking_news.py, gold_history.py, etc.) would fail the `ruff format --check scheduler/` gate if applied globally.
- **Fix:** Applied `ruff format` only to the specific files being modified in each task, per scope boundary rules. Pre-existing violations in out-of-scope files are not part of this task.
- **Files modified:** Applied per-task to each modified .py file.
- **Commit:** Documented in T1 commit body.

**2. [Rule 2 - Test adaptation] 3 existing tests updated to patch `_run_analytical_fallback`**
- **Found during:** T5
- **Issue:** After wiring `run_draft_cycle` to call `_run_analytical_fallback` when `items_queued < 2`, 3 existing tests that don't mock `_run_analytical_fallback` would trigger the fallback path and attempt to open a real `AsyncSessionLocal` → network/DB call → failure.
  - `test_run_draft_cycle_completes_with_stories`
  - `test_run_draft_cycle_writes_notes_on_empty_candidates`
  - `test_run_draft_cycle_passes_new_kwargs` (fake_cycle returns `None` which becomes `None < 2` TypeError)
- **Fix:** Added `patch("agents.content.infographics._run_analytical_fallback", new=AsyncMock(return_value=0))` to the first two; changed `fake_cycle` to `return 2` for the third. This was explicitly called out in PLAN.md T5.
- **Files modified:** `scheduler/tests/test_infographics.py`
- **Commit:** `27c4138`

## Known Stubs

None — all code paths are wired and tested. `fetch_analytical_historical_stories` is a real SerpAPI call (not a stub), `_run_analytical_fallback` persists real `ContentBundle` + `DraftItem` rows through the full pipeline.

## Validation Gate Results

All gates passed:

- `uv run pytest scheduler/tests/test_infographics.py -x -v` — 14 passed
- `uv run pytest scheduler/tests/test_content_agent.py -x -v` — 26 passed
- `uv run pytest scheduler/ -x` — 136 passed (127 → 136)
- `uv run pytest` (backend) — 69 passed, 5 skipped
- `uv run ruff check` (modified files) — clean
- `uv run ruff format --check` (modified files) — clean
- `grep ANALYTICAL_HISTORICAL_QUERIES scheduler/agents/content/infographics.py` — 5 matches (definition + 4 usages)
- `grep -rn "_run_analytical_fallback|fetch_analytical_historical_stories" scheduler/` — matches in all 4 expected files
- `git diff main -- scheduler/agents/content/gold_history.py` — empty
- `git diff main -- scheduler/agents/content/gold_history_stories/` — empty
- `git diff main -- scheduler/worker.py` — empty
- `git diff main -- frontend/` — empty
- `git diff main -- alembic/` — empty
- `git diff main -- infographics.py | grep "^-.*_draft|BRAND_PREAMBLE|image_prompt ="` — 0 lines (no deletions)
- `git diff main -- content_agent.py | grep "SERPAPI_KEYWORDS"` — 0 lines (unchanged)
- `grep gold_history_stories infographics.py` — 0 matches (no coupling)

## Known Follow-ups

None surfaced during execution. The analytical-historical queries list (`ANALYTICAL_HISTORICAL_QUERIES`) uses broad search terms; refinement for SerpAPI yield optimization is a future tuning opportunity if fallback fires frequently.

## Self-Check: PASSED

Files verified:
- FOUND: scheduler/agents/content_agent.py
- FOUND: scheduler/agents/content/__init__.py
- FOUND: scheduler/agents/content/infographics.py
- FOUND: scheduler/tests/test_content_agent.py
- FOUND: scheduler/tests/test_infographics.py
- FOUND: .planning/quick/260423-lvp-add-analytical-historical-fallback-to-su/260423-lvp-SUMMARY.md

Commits verified:
- FOUND: d8b88ed (T1)
- FOUND: 738a811 (T2)
- FOUND: 0f400c2 (T3)
- FOUND: bd344f6 (T4)
- FOUND: 27c4138 (T5)
