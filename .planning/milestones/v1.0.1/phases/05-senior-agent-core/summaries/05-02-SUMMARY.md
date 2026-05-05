---
phase: 05-senior-agent-core
plan: 02
subsystem: scheduler
tags: [deduplication, jaccard, fingerprint, tdd, wave-1]
dependency_graph:
  requires:
    - scheduler/models/draft_item.py (related_id FK column)
    - scheduler/models/config.py (Config key-value store)
    - scheduler/database.py (AsyncSessionLocal)
    - scheduler/tests/test_senior_agent.py (Wave 0 stubs from 05-01)
  provides:
    - scheduler/agents/senior_agent.py
    - extract_fingerprint_tokens() pure function
    - jaccard_similarity() pure function
    - SeniorAgent._run_deduplication() async method
  affects:
    - scheduler/tests/test_senior_agent.py (4 stubs replaced with real tests)
tech_stack:
  added: []
  patterns:
    - Jaccard similarity for text deduplication (no Claude call, zero API cost)
    - frozenset-based token fingerprinting with cashtag-aware regex
    - pytest mock_get_config with key-dispatch side_effect for multi-key async config helpers
key_files:
  created:
    - scheduler/agents/senior_agent.py
  modified:
    - scheduler/tests/test_senior_agent.py
decisions:
  - STOPWORDS frozenset at module level — covers high-frequency English function words plus
    gold-domain noise words (via, per, just, new, today, following, after, before, over, under,
    about, into); easily extended in future plans
  - re.findall(r'\$[a-z0-9]+|\b\w+\b') — cashtag pattern comes first so $2400 and $gld are
    preserved as single tokens before the generic \w+ match would split them
  - _run_deduplication queries pending items ordered by created_at ASC so the "oldest" matching
    item is the one that wins best_match (related_id points to the original source story)
  - Mock side_effect pattern for _get_config returns key-specific values, avoiding ValueError
    when int() is called on a float-string default
metrics:
  duration: ~18 minutes
  completed: 2026-04-02
  tasks_completed: 1
  tasks_total: 1
  files_created: 1
  files_modified: 1
---

# Phase 5 Plan 2: Story Fingerprint Deduplication Summary

**One-liner:** Jaccard similarity deduplication using cashtag-aware tokenisation and configurable 0.40 threshold, linking same-story items via related_id on the newer DraftItem.

## What Was Done

Implemented SENR-02 story deduplication as a TDD cycle. Both files were confirmed RED (ModuleNotFoundError) before implementation, then GREEN after creating `scheduler/agents/senior_agent.py`.

### Task 1: TDD — RED then GREEN (622c95f)

**RED phase confirmed:** Running the 4 dedup tests against the pre-implementation codebase raised `ModuleNotFoundError: No module named 'agents.senior_agent'` — tests were properly failing.

**scheduler/agents/senior_agent.py** — Created with:

- `STOPWORDS` frozenset (module-level) — 75 high-frequency English words plus gold-domain noise (via, per, just, new, today, following, after, before, over, under, about, into). These words carry no story-identity signal and are filtered from fingerprint tokens.

- `extract_fingerprint_tokens(text: str | None) -> frozenset[str]` — Handles `None` and empty string gracefully. Lowercases and strips the input. Uses `re.findall(r'\$[a-z0-9]+|\b\w+\b', lowered)` — cashtag pattern first to preserve `$gld`, `$2400` as atomic tokens. Filters out stopwords and single-character tokens. Returns `frozenset`.

- `jaccard_similarity(set_a, set_b) -> float` — Returns 0.0 for two empty sets (no divide-by-zero). Returns `len(A & B) / len(A | B)` otherwise.

- `SeniorAgent` class with `__init__` setting `self.settings = get_settings()`.

- `SeniorAgent._get_config(session, key, default)` async helper — `select(Config.value).where(Config.key == key)`, returns `scalar_one_or_none() or default`.

- `SeniorAgent._run_deduplication(session, new_item_id)` async method:
  - Reads `senior_dedup_threshold` (default "0.40") and `senior_dedup_lookback_hours` (default "24") from config
  - Fetches new item via `session.get(DraftItem, new_item_id)` — returns if not found
  - Builds fingerprint from `source_text + " " + rationale`
  - Queries `pending` items created in last N hours, excluding new item, ordered by `created_at ASC`
  - Finds best Jaccard match above threshold
  - Sets `new_item.related_id = best_match.id` if match found

**GREEN phase confirmed:** All 4 tests pass, 15 stubs still skip.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Mock _get_config returned float-string for int() conversion call**
- **Found during:** GREEN phase validation (first run)
- **Issue:** Both DB integration tests patched `_get_config` with `AsyncMock(return_value="0.40")`. This returned "0.40" for both the threshold call (`float(...)`) and the lookback_hours call (`int(...)`), causing `ValueError: invalid literal for int() with base 10: '0.40'`.
- **Fix:** Replaced the blanket `return_value="0.40"` mock with a key-dispatch `async def mock_get_config(session, key, default)` that returns `"0.40"` for `senior_dedup_threshold` and `"24"` for `senior_dedup_lookback_hours`. This matches realistic config behavior and prevents the type coercion error.
- **Files modified:** `scheduler/tests/test_senior_agent.py`
- **Commit:** 622c95f (same commit — tests and implementation staged together)

**2. [TDD protocol note] RED and GREEN committed together**
- The Wave 0 stub plan already committed `test_senior_agent.py`, so only the test *replacements* and the new `senior_agent.py` needed staging. Both files were staged and committed in a single commit (622c95f) rather than separate RED/GREEN commits. Functionally equivalent — RED failure was confirmed interactively before implementation was written.

## Test Results

```
cd /Users/matthewnelson/seva-mining/scheduler && uv run pytest tests/test_senior_agent.py -v
...
tests/test_senior_agent.py::test_jaccard_similarity PASSED
tests/test_senior_agent.py::test_extract_fingerprint_tokens PASSED
tests/test_senior_agent.py::test_dedup_sets_related_id PASSED
tests/test_senior_agent.py::test_dedup_no_match_below_threshold PASSED
tests/test_senior_agent.py::test_queue_cap_accepts_below_cap SKIPPED
... (11 more SKIPPED)
======================== 4 passed, 15 skipped in 0.29s =========================
```

## Known Stubs

None — the 4 dedup tests implemented in this plan are complete. The 15 remaining Wave 1-3 stubs are intentional placeholders for Plans 03-06.

## Commits

| Hash | Message |
|------|---------|
| 622c95f | test(05-02): RED — replace 4 dedup stubs with real test implementations |

## Self-Check: PASSED

- `/Users/matthewnelson/seva-mining/scheduler/agents/senior_agent.py` — FOUND
- `/Users/matthewnelson/seva-mining/scheduler/tests/test_senior_agent.py` — FOUND (modified)
- Commit 622c95f — FOUND in git log
- 4 passed, 15 skipped — CONFIRMED
