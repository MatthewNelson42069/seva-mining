---
must_haves:
  - scheduler/worker.py CONTENT_INTERVAL_AGENTS[0] tuple ends with interval_hours=1 (was 2)
  - scheduler/tests/test_worker.py asserts cadences["sub_breaking_news"] == 1
  - scheduler/agents/content/breaking_news.py header comment updated to reflect kqa revert
  - Narrative comments in worker.py (L9, L108, L329) updated from "every 2h" to "every 1h" for sub_breaking_news
  - sub_threads cadence UNTOUCHED (stays 3h from j5i)
  - uv run pytest -x green
  - uv run ruff check . clean
validation_commands:
  - cd scheduler && uv run pytest tests/test_worker.py -x -v
  - cd scheduler && uv run pytest -x
  - cd scheduler && uv run ruff check .
  - grep -n '"sub_breaking_news"' scheduler/worker.py
  - grep -n '"sub_breaking_news": 1' scheduler/tests/test_worker.py
  - git diff main -- scheduler/agents/content/ scheduler/agents/content_agent.py scheduler/services/whatsapp.py scheduler/agents/senior_agent.py backend/ frontend/ alembic/ scheduler/models/
---

# Quick Task 260424-kqa: Breaking News cadence 2h → 1h — Plan

## T1 — Flip interval + update test + narrative comments (atomic commit)

**Why:** User directive to restore 1h cadence for `sub_breaking_news`. Reverts vxg's 2h bump (which had reverted m9k's original 1h).

**Files + exact diffs:**

### `scheduler/worker.py:116`
Current:
```python
("sub_breaking_news", breaking_news.run_draft_cycle, "Breaking News", 1010, 0, 2),
```
New:
```python
("sub_breaking_news", breaking_news.run_draft_cycle, "Breaking News", 1010, 0, 1),
```

### `scheduler/worker.py:9` (module docstring)
Find "sub_breaking_news every 2h," → replace with "sub_breaking_news every 1h,"

### `scheduler/worker.py:108-111` (CONTENT_INTERVAL_AGENTS narrative comment)
Find "sub_breaking_news every 2h," → replace with "sub_breaking_news every 1h,"

### `scheduler/worker.py:329` (log line in `build_scheduler`)
Find "sub_breaking_news=2h" → replace with "sub_breaking_news=1h"

### `scheduler/tests/test_worker.py:533-535` (test_interval_agents_cadences)
Current:
```python
cadences = {t[0]: t[5] for t in CONTENT_INTERVAL_AGENTS}
assert cadences == {
    "sub_breaking_news": 2,
    "sub_threads": 3,
}
```
New:
```python
cadences = {t[0]: t[5] for t in CONTENT_INTERVAL_AGENTS}
assert cadences == {
    "sub_breaking_news": 1,
    "sub_threads": 3,
}
```
Also update the test docstring if it mentions "BN=2h".

### `scheduler/agents/content/breaking_news.py:4` (module header comment)
Current narrative mentions the m9k→vxg cadence history. Append a note that kqa reverts vxg back to 1h. Exact wording left to executor discretion — keep it short (1 line added).

## T2 — STATE.md update (no code)

Append row to STATE.md "Quick Tasks Completed" table:
- slug: 260424-kqa
- title: Breaking News cadence 2h → 1h
- status: shipped
- commit SHAs: T1 SHA, T2 SHA
- note: restores 1h cadence (reverts vxg's 2h). User directive after observing ~30 min cadence in logs (likely Railway redeploy side-effect, not the interval itself — flagged for future investigation if persistent post-deploy).

## Commit discipline

- T1 commit: `feat(scheduler): restore sub_breaking_news 1h cadence (kqa)` — single atomic commit covering worker.py tuple + narrative comments + test assertion + breaking_news.py header
- T2 commit: `docs(quick-kqa): STATE.md row` — docs-only

Every commit ends with:
```
Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

## Goal-backward check

| Must-have | Task |
|-----------|------|
| Interval tuple = 1 | T1 |
| Test assertion = 1 | T1 |
| Narrative comments updated | T1 |
| Test green, ruff clean | T1 validation |
| STATE.md row | T2 |

No orphans. 2 tasks, 1 code file touched (worker.py), 1 test file touched (test_worker.py), 1 narrative file touched (breaking_news.py header comment), plus STATE.md.
