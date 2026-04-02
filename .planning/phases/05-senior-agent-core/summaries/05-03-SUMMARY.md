---
phase: 05-senior-agent-core
plan: 03
subsystem: scheduler
tags: [queue-cap, tdd, wave-1, displacement, tiebreaking, process_new_item]
dependency_graph:
  requires:
    - scheduler/agents/senior_agent.py (SeniorAgent class, _run_deduplication from 05-02)
    - scheduler/models/draft_item.py (DraftItem.score, DraftItem.expires_at)
    - scheduler/models/config.py (Config key-value store, senior_queue_cap)
    - scheduler/models/agent_run.py (AgentRun for intake run logging)
    - scheduler/database.py (AsyncSessionLocal)
    - scheduler/tests/test_senior_agent.py (4 queue cap stubs from 05-01)
  provides:
    - SeniorAgent._enforce_queue_cap() async method
    - SeniorAgent._check_breaking_news_alert() stub
    - SeniorAgent.process_new_item() entry point
    - process_new_items() module-level convenience function
  affects:
    - scheduler/tests/test_senior_agent.py (4 stubs replaced with real tests)
tech_stack:
  added: []
  patterns:
    - ORDER BY score ASC, expires_at ASC tiebreaking — soonest-expiring item displaced when scores tie
    - with_for_update(skip_locked=True) on lowest-item SELECT for concurrent-safe displacement
    - Module-level async function for sub-agent call site to avoid circular imports
    - AgentRun with try/except/finally pattern per EXEC-04 (errors captured, never re-raised)
key_files:
  created: []
  modified:
    - scheduler/agents/senior_agent.py
    - scheduler/tests/test_senior_agent.py
decisions:
  - ORDER BY score ASC, expires_at ASC — a single compound sort makes tiebreaking implicit; no
    special-case branch needed for tied scores. The test mock mimics this by returning the
    soonest-expiring item as the result of `.scalar_one_or_none()`.
  - with_for_update(skip_locked=True) on the lowest-item fetch — guards against a race where two
    sub-agents call process_new_item concurrently; a locked row is skipped rather than waited on,
    preventing deadlock at the cost of occasionally missing a displacement candidate.
  - _check_breaking_news_alert added as a pass-body stub now so process_new_item has its full
    three-stage pipeline shape from day one; Plan 04 will replace the stub with real logic.
  - process_new_items (module-level) instantiates SeniorAgent lazily inside the function body,
    matching the plan spec's intent to avoid circular imports when TwitterAgent calls it.
metrics:
  duration: ~15 minutes
  completed: 2026-04-02
  tasks_completed: 1
  tasks_total: 1
  files_created: 0
  files_modified: 2
---

# Phase 5 Plan 3: Queue Cap Enforcement Summary

**One-liner:** 15-item hard cap via `_enforce_queue_cap` with `ORDER BY score ASC, expires_at ASC` tiebreaking; `process_new_item` wires dedup + cap + alert stub into a single AgentRun-logged entry point.

## What Was Done

Implemented SENR-01, SENR-03, and SENR-04 queue cap logic as a TDD cycle. Tests were confirmed RED (AttributeError on missing method), then GREEN after adding the implementation.

### Task 1: TDD — RED then GREEN (d3b3a97)

**RED phase confirmed:** The 4 queue cap tests in `test_senior_agent.py` were updated from `pytest.skip()` stubs to full implementations using `AsyncMock` / `MagicMock`. Running against the pre-implementation `senior_agent.py` raised `AttributeError: 'SeniorAgent' object has no attribute '_enforce_queue_cap'` — tests were properly failing.

**scheduler/tests/test_senior_agent.py** — 4 stubs replaced with real implementations:

- `test_queue_cap_accepts_below_cap`: mocks `execute()` to return count=10; asserts `session.delete()` is never called.
- `test_queue_cap_displaces_lowest`: mocks count=15, lowest item with score=1.0; new item score=9.0; asserts `session.delete()` is called once with the lowest item's id.
- `test_queue_cap_discards_new_item`: mocks count=15, lowest item with score=5.0; new item score=3.0; asserts `session.delete()` is called once with the new item's id.
- `test_queue_cap_tiebreak_expires_at`: mocks count=15; `scalar_one_or_none()` returns the item with the earlier `expires_at` (simulating `ORDER BY score ASC, expires_at ASC`); new item score=9.0; asserts the soon-expiring item is deleted.

All 4 tests use `asyncio.run()` directly (no pytest-asyncio fixture) to match the established dedup test pattern.

**scheduler/agents/senior_agent.py** — Three methods added to `SeniorAgent`:

- `_enforce_queue_cap(session, new_item_id)`:
  - Reads `senior_queue_cap` config (default `"15"`)
  - Counts pending items excluding `new_item_id` via `select(func.count()).select_from(DraftItem).where(...)`
  - Returns early if `existing_count < cap`
  - Fetches `new_item` via `session.get(DraftItem, new_item_id)`
  - Fetches lowest via `select(DraftItem).order_by(DraftItem.score.asc(), DraftItem.expires_at.asc()).limit(1).with_for_update(skip_locked=True)`
  - Deletes `lowest` if `new_score > low_score`, otherwise deletes `new_item`

- `_check_breaking_news_alert(session, item_id)`: stub with `pass` body and docstring, full implementation in Plan 04.

- `process_new_item(item_id)`:
  - Opens `AsyncSessionLocal()` context
  - Creates `AgentRun(agent_name="senior_agent_intake", status="running")`
  - Calls `_run_deduplication`, `_enforce_queue_cap`, `_check_breaking_news_alert` in sequence
  - On success: `run.status = "completed"`, commits
  - On exception: `run.status = "failed"`, `run.errors = [str(exc)]`, commits (or rolls back if commit fails); never re-raises

**Module-level function:**

- `process_new_items(item_ids: list[uuid.UUID])`: creates `SeniorAgent()` lazily and calls `process_new_item` for each id in sequence.

**GREEN phase confirmed:** All 4 queue cap tests pass. All 4 dedup tests from Plan 02 still pass. 8 total passing, 11 skipped.

## Deviations from Plan

None — plan executed exactly as written.

## Test Results

```
cd /Users/matthewnelson/seva-mining/scheduler && /Users/matthewnelson/.local/bin/uv run pytest tests/test_senior_agent.py -v
tests/test_senior_agent.py::test_jaccard_similarity PASSED
tests/test_senior_agent.py::test_extract_fingerprint_tokens PASSED
tests/test_senior_agent.py::test_dedup_sets_related_id PASSED
tests/test_senior_agent.py::test_dedup_no_match_below_threshold PASSED
tests/test_senior_agent.py::test_queue_cap_accepts_below_cap PASSED
tests/test_senior_agent.py::test_queue_cap_displaces_lowest PASSED
tests/test_senior_agent.py::test_queue_cap_discards_new_item PASSED
tests/test_senior_agent.py::test_queue_cap_tiebreak_expires_at PASSED
tests/test_senior_agent.py::test_expiry_sweep_marks_expired SKIPPED
... (9 more SKIPPED)
======================== 8 passed, 11 skipped in 0.29s =========================
```

## Known Stubs

- `SeniorAgent._check_breaking_news_alert` — pass body, docstring only. Intentional placeholder for Plan 04 (Wave 2). Does not affect Plan 03's goal (queue cap); the stub is unreachable in normal test paths because it is called after `_enforce_queue_cap` inside `process_new_item`, and none of the 4 queue cap tests exercise `process_new_item` directly.

## Commits

| Hash | Message |
|------|---------|
| d3b3a97 | feat(05-03): queue cap enforcement with priority tiebreaking (SENR-01, SENR-03, SENR-04) |

## Self-Check: PASSED
