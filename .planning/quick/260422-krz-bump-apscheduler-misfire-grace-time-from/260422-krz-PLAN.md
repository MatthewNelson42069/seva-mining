---
phase: quick-260422-krz
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - scheduler/worker.py
autonomous: true
requirements:
  - KRZ-01
must_haves:
  truths:
    - "APScheduler's misfire_grace_time job default is 1800 seconds (30 minutes)"
    - "Noon-PT cron jobs that were dropped today survive a 3-7 minute Railway deploy window going forward"
    - "Scheduler test suite still passes 98/98 (no regression introduced)"
    - "scheduler/worker.py still compiles cleanly as valid Python"
  artifacts:
    - path: "scheduler/worker.py"
      provides: "Scheduler build with widened misfire_grace_time"
      contains: 'misfire_grace_time": 1800'
  key_links:
    - from: "scheduler/worker.py (AsyncIOScheduler job_defaults)"
      to: "All 8 scheduled jobs (morning_digest + 7 sub-agents)"
      via: "APScheduler job_defaults inheritance"
      pattern: 'misfire_grace_time":\s*1800'
---

<objective>
Bump APScheduler `misfire_grace_time` from 300s (5 min) to 1800s (30 min) in `scheduler/worker.py` so scheduled jobs survive Railway auto-redeploy windows (3-7 min typical) without being coalesced and dropped.

Purpose: Today (2026-04-22), noon-PT crons for quotes, infographics, and video_clip sub-agents were dropped because two Railway redeploys (10:48 PT and 13:30 PT) interrupted the scheduler during the 5-minute misfire grace window. APScheduler coalesced those jobs and never fired them. A 30-minute grace is comfortably larger than any observed Railway deploy duration, restoring reliability without changing any other scheduling behavior.

Output: One-line edit to `scheduler/worker.py`, test suite green, single atomic commit on `main`.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@scheduler/worker.py
@scheduler/pyproject.toml

<interfaces>
<!-- Exact state of the config block before the edit. L278-285 of scheduler/worker.py. -->

```python
scheduler = AsyncIOScheduler(
    job_defaults={
        "coalesce": True,
        "max_instances": 1,
        "misfire_grace_time": 300,
    },
    timezone="UTC",
)
```

After edit:

```python
scheduler = AsyncIOScheduler(
    job_defaults={
        "coalesce": True,
        "max_instances": 1,
        "misfire_grace_time": 1800,
    },
    timezone="UTC",
)
```

Test runner (from `scheduler/pyproject.toml`):
- `pytest` with `asyncio_mode = "auto"`, `testpaths = ["tests"]`
- Run from `scheduler/` directory: `cd scheduler && pytest tests/ -x`
- Baseline from recent STATE.md entry (260422-zid): 98/98 pass
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Bump misfire_grace_time 300 -> 1800 in scheduler/worker.py</name>
  <files>scheduler/worker.py</files>
  <action>
    Open `scheduler/worker.py` and change the single line at L282 inside the `AsyncIOScheduler(job_defaults=...)` block.

    Exact edit:
    - Find: `            "misfire_grace_time": 300,`
    - Replace with: `            "misfire_grace_time": 1800,`

    Do NOT touch any other line. Do NOT reformat the block. Do NOT add/remove imports. Do NOT change `coalesce`, `max_instances`, or `timezone`. Do NOT adjust per-job overrides (there are none in this block, and there should still be none after the edit).

    Rationale (for commit message context): 300s = 5 min was insufficient to survive a Railway auto-redeploy window. Railway build + container startup typically takes 3-7 minutes; when a deploy was mid-flight during a cron fire time, APScheduler coalesced the missed fire and dropped the job. 1800s = 30 min gives comfortable headroom over any observed Railway deploy duration while still being short enough that jobs delayed beyond 30 min are genuinely stale and should not run. This setting is inherited by all 8 scheduled jobs via `job_defaults` (morning_digest + 7 sub-agents: sub_breaking_news, sub_threads, sub_long_form, sub_quotes, sub_infographics, sub_video_clip, sub_gold_history).
  </action>
  <verify>
    <automated>cd /Users/matthewnelson/seva-mining && grep -c 'misfire_grace_time.*1800' scheduler/worker.py | grep -qx 1 && grep -c 'misfire_grace_time.*300,' scheduler/worker.py | grep -qx 0 && python -m py_compile scheduler/worker.py && cd scheduler && pytest tests/ -x</automated>
  </verify>
  <done>
    - `grep -c 'misfire_grace_time.*1800' scheduler/worker.py` returns exactly 1
    - `grep -c 'misfire_grace_time.*300,' scheduler/worker.py` returns exactly 0
    - `python -m py_compile scheduler/worker.py` exits 0 (valid Python)
    - `cd scheduler && pytest tests/ -x` returns 98/98 passed, 0 failed (matches baseline from 260422-zid)
    - No other lines in `scheduler/worker.py` changed (diff should be a clean 1-line swap)
  </done>
</task>

</tasks>

<verification>
Overall quick-task checks:

1. Diff scope — `git diff scheduler/worker.py` shows exactly one line changed (the `misfire_grace_time` value). No unrelated edits.
2. No other files modified — `git status` shows only `scheduler/worker.py` as modified.
3. Syntax — `python -m py_compile scheduler/worker.py` exits 0.
4. Regression — `cd scheduler && pytest tests/ -x` reports 98 passed.
5. Branch — still on `main` (per orchestrator constraint: init returned `branch_name=null`, quick task stays on main).
6. Commit — single atomic commit on `main`. Do NOT push.
</verification>

<success_criteria>
- `scheduler/worker.py` L282 reads `"misfire_grace_time": 1800,`
- `scheduler/worker.py` contains no occurrence of `"misfire_grace_time": 300,`
- `python -m py_compile scheduler/worker.py` exits 0
- `cd scheduler && pytest tests/ -x` = 98/98 passed
- Exactly one line of `scheduler/worker.py` changed (verified via `git diff --stat`)
- Single atomic commit created on `main`; not pushed
- Next noon-PT cron fire (or any fire occurring during a Railway redeploy up to 30 min long) will execute when the scheduler resumes rather than being coalesced-and-dropped
</success_criteria>

<output>
After completion, create `.planning/quick/260422-krz-bump-apscheduler-misfire-grace-time-from/260422-krz-SUMMARY.md` documenting:
- One-line change made (with before/after value)
- Test result (98/98 pass confirmation)
- Commit SHA
- Confirmation that branch is still `main` and no push was performed
- Operational note: next Railway redeploy will validate the fix in production; if a cron fires during the 30-min grace window post-deploy, APScheduler will execute it rather than coalesce-drop it
</output>
