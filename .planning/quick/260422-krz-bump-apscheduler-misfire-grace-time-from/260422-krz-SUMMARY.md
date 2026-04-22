---
phase: quick-260422-krz
plan: "01"
subsystem: scheduler
tags: [apscheduler, reliability, railway, quick-fix]
dependency_graph:
  requires: []
  provides: [widened-misfire-grace-window]
  affects: [all-8-scheduled-jobs]
tech_stack:
  added: []
  patterns: []
key_files:
  created: []
  modified:
    - scheduler/worker.py
decisions:
  - "Bumped misfire_grace_time from 300s to 1800s — 30 min comfortably exceeds Railway's 3-7 min deploy window"
metrics:
  duration: "< 5 minutes"
  completed: "2026-04-22T22:02:35Z"
  tasks_completed: 1
  tasks_total: 1
  files_changed: 1
---

# Quick Task 260422-krz: Bump APScheduler misfire_grace_time 300s → 1800s

**One-liner:** Widened APScheduler `misfire_grace_time` from 5 min to 30 min in `scheduler/worker.py` so all 8 scheduled jobs survive Railway auto-redeploy windows without being coalesced and dropped.

## Change Made

**File:** `scheduler/worker.py` — line 282 inside `AsyncIOScheduler(job_defaults={...})`

**Before:**
```python
"misfire_grace_time": 300,
```

**After:**
```python
"misfire_grace_time": 1800,
```

This is the only line changed. The `coalesce`, `max_instances`, and `timezone` settings are untouched.

## Root Cause

On 2026-04-22, two Railway auto-redeploys (10:48 PT and 13:30 PT) interrupted the scheduler during noon-PT cron fire windows for `sub_quotes`, `sub_infographics`, and `sub_video_clip`. APScheduler's 5-minute misfire grace time was shorter than the Railway deploy duration (3-7 min typical), so APScheduler coalesced the missed fires and never re-executed them. Those jobs were silently dropped.

## Scope

`job_defaults` is inherited by all 8 scheduled jobs:
- `morning_digest` (daily cron)
- `sub_breaking_news`, `sub_threads`, `sub_long_form`, `sub_quotes`, `sub_infographics`, `sub_video_clip`, `sub_gold_history` (7 sub-agents, each on a staggered 2h interval)

No per-job `misfire_grace_time` overrides exist — all 8 jobs inherit from `job_defaults`.

## Test Result

98/98 passed (matches baseline from 260422-zid), 0 failed, 17 pre-existing RuntimeWarnings (unrelated to this change).

```
============================= test session starts ==============================
collected 98 items
...
======================= 98 passed, 17 warnings in 4.23s ========================
```

## Commit

- **SHA:** `9d03381`
- **Message:** `fix(scheduler): bump misfire_grace_time 300→1800s (quick-260422-krz)`
- **Branch:** worktree-agent-a044810a (merge target: main)
- **Push:** NOT performed (per constraints)

## Verification

- `grep -c 'misfire_grace_time.*1800' scheduler/worker.py` → `1`
- `grep -c 'misfire_grace_time.*300,' scheduler/worker.py` → `0`
- `python3 -m py_compile scheduler/worker.py` → exits 0
- `uv run pytest tests/ -x` → 98/98 passed
- `git diff --stat` → `1 file changed, 1 insertion(+), 1 deletion(-)`

## Operational Note

The next Railway redeploy will validate this fix in production. Any cron that fires during a Railway deploy lasting up to 30 minutes will now execute when the scheduler resumes rather than being coalesced-dropped. Jobs delayed beyond 30 min remain intentionally discarded (stale content).

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- File modified: `scheduler/worker.py` — confirmed present and contains `misfire_grace_time": 1800`
- Commit `9d03381` exists: confirmed via `git log`
- 98/98 tests passed: confirmed
- Diff is exactly 1 line: confirmed via `git diff --stat`
