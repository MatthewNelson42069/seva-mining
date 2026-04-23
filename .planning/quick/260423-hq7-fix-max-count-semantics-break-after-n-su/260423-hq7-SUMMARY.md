---
quick_task: 260423-hq7
subsystem: scheduler/agents/content
tags: [bug-fix, max_count, dedup, run_text_story_cycle, tdd]
key_files:
  modified:
    - scheduler/agents/content/__init__.py
    - scheduler/tests/test_content_init.py
    - scheduler/tests/test_infographics.py
decisions:
  - "Removed pre-loop candidate slice (candidates[:max_count]); replaced with post-persist break inside for-loop"
  - "Sort block retained but condition changed from len(candidates) > max_count to len(candidates) > 1 so sort always runs when max_count is set"
  - "test_infographics::test_run_draft_cycle_writes_structured_notes updated to reflect new candidates=3/drafted=3/queued=2 semantics (Rule 1 deviation)"
metrics:
  duration: "~25 minutes"
  completed: "2026-04-23"
  tests_before: 118
  tests_after: 121
  commit: 4b0ee67
---

# Quick Task 260423-hq7: Fix max_count Semantics — Break-after-N-successes Summary

**One-liner:** Rewrote `run_text_story_cycle.max_count` from "trim candidates to top N before dedup loop" to "break out of the for-loop after N compliance-passing persists", unblocking threads/long_form/quotes/infographics when breaking_news drains the fresh-story pool.

## What Changed

### scheduler/agents/content/__init__.py

**Lines changed:** ~L175-193 (sort+trim block) and ~L298-310 (compliance-ok block)

**Before — sort+trim block (L175-193):**
```python
if max_count is not None and len(candidates) > max_count:
    if sort_by == "score":
        candidates.sort(
            key=lambda s: (float(s.get("score", 0.0)), s.get("published_at", "")),
            reverse=True,
        )
    else:
        candidates.sort(key=lambda s: s.get("published_at", ""), reverse=True)
    candidates = candidates[:max_count]   # <-- THE BUG
    logger.info("%s: max_count cap: trimmed to top %d by %s", ...)
```

**After — sort-only block (same region):**
```python
if max_count is not None and len(candidates) > 1:
    if sort_by == "score":
        candidates.sort(
            key=lambda s: (float(s.get("score", 0.0)), s.get("published_at", "")),
            reverse=True,
        )
    else:
        candidates.sort(key=lambda s: s.get("published_at", ""), reverse=True)
    logger.info("%s: sorted %d candidates by %s (max_count=%d, break-after-N)", ...)
```

**After — break added inside the for-loop (compliance-ok block, ~L308-316):**
```python
if compliance_ok:
    item = content_agent.build_draft_item(bundle, rationale)
    session.add(item)
    await session.flush()
    items_queued += 1
    logger.info("%s: queued %s '%s' ...", ...)
    if max_count is not None and items_queued >= max_count:
        logger.info("%s: reached max_count=%d successful drafts — exiting loop", ...)
        break
```

Also updated the `max_count` parameter docstring in `run_text_story_cycle`.

### scheduler/tests/test_content_init.py

Added `_run_with_stories_succeeding()` helper that:
- `draft_fn` returns a real draft dict (activates compliance+persist+items_queued path)
- Mocks `content_agent.review()` → compliance_passed=True
- Mocks `content_agent.build_draft_item()` → sentinel
- Supports `dedup_returns_true_for` and `stories_draft_returns_none` per-story overrides

**Rewritten tests (semantically equivalent for all-succeed case):**
- `test_max_count_caps_candidates` — now uses `_run_with_stories_succeeding`, asserts `items_queued == 2`
- `test_sort_by_score_picks_top_by_score` — same
- `test_sort_by_score_breaks_ties_by_recency` — same
- `test_sort_by_default_is_published_at` — same

**New tests:**
- `test_run_text_story_cycle_max_count_iterates_past_dedup_hits` — top 3 stories dedup-blocked; loop must continue to stories 4+5 and produce items_queued=2. FAILED before fix.
- `test_max_count_exhausts_if_insufficient_successes` — 10 stories, 9 return None from draft_fn; all 10 reached, items_queued=1.
- `test_max_count_none_still_iterates_all` — max_count=None regression guard for breaking_news; all 10 drafted.

## Test Results

| Metric | Value |
|--------|-------|
| Baseline | 118/118 |
| After fix | 121/121 |
| New tests added | 3 (test_content_init.py) |
| Tests rewritten | 4 (test_content_init.py) |
| Test file also updated | test_infographics.py (notes-payload assertion) |

## Commit

Single atomic commit on `main`:
- **SHA:** `4b0ee67`
- **Message:** `fix(content): max_count = break-after-N-successes, not pre-trim (quick-260423-hq7)`
- **Files:** `scheduler/agents/content/__init__.py`, `scheduler/tests/test_content_init.py`, `scheduler/tests/test_infographics.py`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] test_infographics::test_run_draft_cycle_writes_structured_notes updated**
- **Found during:** Step 3 (run full suite after GREEN)
- **Issue:** The test was written assuming the old trim semantics — `candidates: 2` (trimmed from 3), `drafted: 2`, `queued: 1`, with only 2 review mock results. After the fix, all 3 candidates enter the loop; the review iterator raised StopIteration on the 3rd call, producing a RuntimeError.
- **Fix:** Extended review_results to 3 items (True, False, True), updated expected notes payload to `candidates:3, drafted:3, compliance_blocked:1, queued:2` (Top A passes → queued=1; Top B fails → blocked; Trimmed passes → queued=2 → break).
- **Files modified:** `scheduler/tests/test_infographics.py`
- **Commit:** `4b0ee67` (included in single atomic commit per plan's "single atomic commit" instruction; only 2 files were specified in plan but test_infographics.py was required for correctness)

**Note:** The plan specified `git add scheduler/agents/content/__init__.py scheduler/tests/test_content_init.py`. The addition of `scheduler/tests/test_infographics.py` is a Rule 1 deviation — the test was actively failing with a RuntimeError caused by the fix, and leaving it broken would violate the "uv run pytest scheduler/ is green" success criterion.

## Validation Gates (all passed)

```
grep "candidates\[:max_count\]" scheduler/agents/content/__init__.py  → 0 matches
grep "items_queued >= max_count" scheduler/agents/content/__init__.py  → 1 match at L310
git diff (5 caller files)                                               → empty (no changes)
uv run pytest scheduler/ -x                                             → 121 passed
uv run ruff check scheduler/                                            → All checks passed!
```

## Task 2: Human Verification — Post-Deploy Observation

**Status:** Awaiting deploy to Railway.

After deploying `4b0ee67` to the Railway backend/worker service, observe:

1. **Target agents:** sub_threads, sub_long_form, sub_quotes, sub_infographics
2. **Expected:** Each produces `items_queued >= 1` in their first scheduled cycle after deploy (within 1-3 hours of deploy, given 2h staggered crons)
3. **Key signal:** `agent_run.notes` JSON shows `candidates > items_queued` — confirms loop iterated past dedup hits rather than an empty run
4. **Regression check:** sub_breaking_news continues producing drafts (max_count=None path unchanged)
5. **Spend check:** Anthropic dashboard — expect small increase (4 more agents drafting), should stay well within $30-50/mo budget
6. **Error check:** Railway worker logs — zero new errors referencing run_text_story_cycle, items_queued, or candidate sorting

**Resume signal:** Type "approved" once all 4 previously-starved agents have produced at least one draft each post-deploy, OR describe issues observed.

## Self-Check: PASSED

- `/Users/matthewnelson/seva-mining/scheduler/agents/content/__init__.py` — exists, contains `if max_count is not None and items_queued >= max_count` at L310, does NOT contain `candidates[:max_count]`
- `/Users/matthewnelson/seva-mining/scheduler/tests/test_content_init.py` — exists, contains `test_run_text_story_cycle_max_count_iterates_past_dedup_hits`
- Commit `4b0ee67` — confirmed via `git log --oneline -1`
- 121/121 tests pass
- ruff clean
