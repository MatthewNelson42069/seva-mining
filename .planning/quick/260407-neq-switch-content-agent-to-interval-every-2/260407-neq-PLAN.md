---
phase: quick
plan: 260407-neq
type: execute
wave: 1
depends_on: []
files_modified:
  - scheduler/worker.py
  - scheduler/seed_content_data.py
  - scheduler/tests/test_worker.py
autonomous: true
requirements: []

must_haves:
  truths:
    - "Content agent runs on interval trigger every 2 hours (same pattern as Twitter agent)"
    - "content_agent_midday job is fully removed from scheduler, JOB_LOCK_IDS, and _make_job"
    - "Tests pass: job count is 5, content_agent_midday is absent from job IDs"
  artifacts:
    - path: "scheduler/worker.py"
      provides: "Single interval-based content_agent job, no content_agent_midday anywhere"
    - path: "scheduler/seed_content_data.py"
      provides: "content_agent_interval_hours key replacing removed cron keys"
    - path: "scheduler/tests/test_worker.py"
      provides: "Updated test expecting 5 jobs and no content_agent_midday"
  key_links:
    - from: "scheduler/worker.py _read_schedule_config defaults"
      to: "build_scheduler content_agent add_job call"
      via: "cfg['content_agent_interval_hours']"
      pattern: "content_agent_interval_hours"
---

<objective>
Switch the content agent from two cron jobs (morning + midday) to a single interval-based job
firing every 2 hours, matching the existing Twitter agent pattern exactly.

Purpose: More frequent, evenly-spaced content drafts without manual cron time management.
Output: worker.py with 5 jobs total; seed_content_data.py with updated config key; tests green.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/PROJECT.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Rewrite worker.py — remove midday job, add content_agent interval trigger</name>
  <files>scheduler/worker.py</files>
  <action>
Make the following surgical changes to scheduler/worker.py:

1. **JOB_LOCK_IDS** — remove the `"content_agent_midday": 1008` entry. Keep all other entries.

2. **_make_job()** — remove the `elif job_name == "content_agent_midday":` branch (lines 153-160).
   The existing `content_agent` branch already instantiates ContentAgent and calls agent.run — that branch is unchanged.

3. **_read_schedule_config() defaults dict** — make these changes:
   - Remove `"content_agent_schedule_hour": "14"`
   - Remove `"content_agent_midday_hour": "20"`
   - Add `"content_agent_interval_hours": "2"`
   The `defaults` dict should end up with keys:
   `twitter_interval_hours`, `instagram_interval_hours`, `content_agent_interval_hours`,
   `morning_digest_schedule_hour`, `gold_history_hour`

4. **build_scheduler()** — replace the two content-agent-related lines and the midday job block:
   - Remove: `content_hour = int(cfg["content_agent_schedule_hour"])`
   - Remove: `midday_hour = int(cfg["content_agent_midday_hour"])`
   - Add: `content_hours = int(cfg["content_agent_interval_hours"])`
   - Update the logger.info call to replace `content=cron(%d:00)` and `midday=cron(%d:00)`
     with `content=%dh` and remove midday from the format string and args.
   - Replace the existing `scheduler.add_job(... "content_agent" ... trigger="cron" ...)` block with:
     ```python
     scheduler.add_job(
         _make_job("content_agent", engine),
         trigger="interval",
         hours=content_hours,
         id="content_agent",
         name=f"Content Agent — every {content_hours} hours",
     )
     ```
   - Delete the entire `scheduler.add_job(... "content_agent_midday" ...)` block.

5. **Module docstring** — update the job count in the docstring from "5 jobs" to "5 jobs"
   (it already says 5 but was inaccurate at 6 — verify and correct to match actual post-change count of 5).
   Also update the docstring description line that mentions the job list if needed.

Result: build_scheduler registers exactly 5 jobs:
`content_agent`, `twitter_agent`, `instagram_agent`, `morning_digest`, `gold_history_agent`
  </action>
  <verify>
    <automated>cd /Users/matthewnelson/seva-mining/scheduler && python -c "
import ast, sys
with open('worker.py') as f:
    src = f.read()
assert 'content_agent_midday' not in src, 'content_agent_midday still present'
assert 'content_agent_interval_hours' in src, 'new config key missing'
assert 'content_agent_schedule_hour' not in src, 'old cron hour key still present'
assert 'trigger=\"interval\"' in src.replace(\"trigger='interval'\", 'trigger=\"interval\"'), 'interval trigger missing'
print('worker.py assertions pass')
"</automated>
  </verify>
  <done>
    worker.py has 5 jobs in build_scheduler, content_agent uses interval trigger, no midday
    references remain anywhere in the file.
  </done>
</task>

<task type="auto">
  <name>Task 2: Update seed_content_data.py and tests; provide DB migration SQL</name>
  <files>scheduler/seed_content_data.py, scheduler/tests/test_worker.py</files>
  <action>
**A. seed_content_data.py — update CONFIG_DEFAULTS:**

In the `CONFIG_DEFAULTS` list:
- Remove the line: `("content_agent_schedule_hour",       "14"),`
- Remove the line: `("content_agent_midday_hour",         "20"),`
- Add in their place (near the other schedule keys, after instagram config or before morning_digest):
  `("content_agent_interval_hours",       "2"),`

The seed script is idempotent on insert — it skips existing rows. Old rows already in DB
will NOT be cleaned up by the seed script; use the SQL below for that.

**B. DB migration SQL (output to console during plan execution for operator to run):**

Print or log this SQL block so the operator can run it against the Neon DB:

```sql
-- Remove old content agent cron config keys
DELETE FROM config WHERE key IN ('content_agent_schedule_hour', 'content_agent_midday_hour');

-- Insert new interval config key (skip if already seeded by updated seed script)
INSERT INTO config (key, value) VALUES ('content_agent_interval_hours', '2')
ON CONFLICT (key) DO NOTHING;
```

Include this SQL block as a comment at the top of seed_content_data.py under the module docstring,
clearly labeled as "DB migration — run once against production DB to remove old keys".

**C. scheduler/tests/test_worker.py — update three tests:**

1. **test_all_five_jobs_registered** (line 88):
   - Update docstring: change "6 jobs" to "5 jobs"
   - Update `expected_ids` set: remove `"content_agent_midday"` from the set
   - The set should be: `{"content_agent", "twitter_agent", "instagram_agent", "morning_digest", "gold_history_agent"}`

2. **test_build_scheduler_has_6_jobs_no_expiry_sweep** (line 118):
   - Update function name to `test_build_scheduler_has_5_jobs_no_expiry_sweep`
   - Update docstring: "returns 5 jobs"
   - Change: `assert len(job_ids) == 6` to `assert len(job_ids) == 5`
   - Add assertion: `assert "content_agent_midday" not in job_ids`

3. **test_read_schedule_config_defaults_no_expiry_sweep** (line 147):
   - Add one more assertion after the existing one:
     `assert "content_agent_midday_hour" not in source`
   - Add: `assert "content_agent_interval_hours" in source`
  </action>
  <verify>
    <automated>cd /Users/matthewnelson/seva-mining/scheduler && python -m pytest tests/test_worker.py -x -q 2>&1 | tail -20</automated>
  </verify>
  <done>
    All test_worker.py tests pass. seed_content_data.py no longer seeds removed keys.
    DB migration SQL is documented in the seed file comment block.
  </done>
</task>

</tasks>

<verification>
Full test suite passes with no regressions:
```
cd /Users/matthewnelson/seva-mining/scheduler && python -m pytest tests/test_worker.py -v
```
Expected: 5 jobs registered, content_agent_midday absent everywhere, content_agent uses interval trigger.
</verification>

<success_criteria>
- worker.py: exactly 5 jobs, content_agent trigger="interval" hours=content_hours, zero midday references
- seed_content_data.py: content_agent_interval_hours="2" present, two old keys removed, DB SQL documented
- test_worker.py: all tests pass, job count assertions updated to 5
</success_criteria>

<output>
After completion, create `.planning/quick/260407-neq-switch-content-agent-to-interval-every-2/260407-neq-SUMMARY.md`
</output>
