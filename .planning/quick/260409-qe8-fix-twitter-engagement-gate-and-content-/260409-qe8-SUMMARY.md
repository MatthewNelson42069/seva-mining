---
id: 260409-qe8
type: quick
completed: "2026-04-09"
duration: ~5 min
tasks_completed: 2
files_modified: 4
commits:
  - 0979e7e
  - aecc81b
---

# Quick Task 260409-qe8: Fix Twitter Engagement Gate and Content Agent SerpAPI Date Parsing

**One-liner:** Fixed two 0-items bugs — Twitter gate now skips views check when impression_count is None (Basic tier API), and content agent SerpAPI parser handles non-ISO date strings with try/except fallback.

## Tasks Completed

### Task 1: Fix Twitter engagement gate — skip views check when impression_count is None

**Problem:** `passes_engagement_gate` treated `None` impression_count as 0, which always failed the views threshold. Basic tier X API does not return impression_count in public_metrics, so every tweet was blocked.

**Fix:** Replaced `safe_views = effective_views if effective_views is not None else 0` with `views_ok = True` when `effective_views is None`. Views check only applies when a value is actually present.

**Files:**
- `scheduler/agents/twitter_agent.py` — updated gate logic and docstring
- `scheduler/tests/test_twitter_agent.py` — updated `test_engagement_gate_none_views` to assert new behavior (None+sufficient likes passes, None+insufficient likes fails)

**Commit:** `0979e7e`

### Task 2: Fix content agent SerpAPI date parsing — handle non-ISO date strings

**Problem:** `_fetch_serpapi_stories` called `datetime.fromisoformat()` directly, which crashed on date strings like `'04/09/2026, 10:31 AM, +0000 UTC'` returned by SerpAPI. This caused the entire story-gathering pipeline to throw and return nothing.

**Fix:** Wrapped `fromisoformat` in try/except, falling back to `strptime` with `%m/%d/%Y, %I:%M %p, +0000 UTC` format. Secondary fallback to `datetime.now(utc)` if both parsers fail.

**Files:**
- `scheduler/agents/content_agent.py` — updated date parsing block at lines 1127-1136
- `scheduler/tests/test_content_agent.py` — added `test_serpapi_date_parsing_non_iso`

**Commit:** `aecc81b`

## Verification

All 43 tests pass across both test files:
- `tests/test_twitter_agent.py` — 23 passed
- `tests/test_content_agent.py` — 20 passed (including new non-ISO date test)

## Deviations

None — plan executed exactly as written.

## Self-Check: PASSED

- `scheduler/agents/twitter_agent.py` — modified
- `scheduler/agents/content_agent.py` — modified
- `scheduler/tests/test_twitter_agent.py` — modified
- `scheduler/tests/test_content_agent.py` — modified
- Commits `0979e7e` and `aecc81b` exist in git log
