---
phase: quick-260421-m9k
plan: 01
subsystem: scheduler
tags: [scheduler, cadence, apscheduler, breaking-news]
requires: []
provides:
  - sub_breaking_news 1h cadence
  - offset=0 first-fire buffer (+10s)
  - per-agent interval_hours schema (6-field tuple)
affects:
  - scheduler/worker.py
  - scheduler/agents/content/breaking_news.py
  - scheduler/tests/test_worker.py (Rule-3 test-unpacking update)
tech-stack:
  added: []
  patterns:
    - "Per-agent IntervalTrigger hours passed as variable, not literal — supports mixed cadences across a single registration table"
    - "+10s start_date buffer for APScheduler IntervalTrigger offset=0 rows to avoid first-fire skip"
key-files:
  created: []
  modified:
    - scheduler/worker.py
    - scheduler/agents/content/breaking_news.py
    - scheduler/tests/test_worker.py
decisions:
  - "sub_breaking_news runs on 1h cadence; other 6 sub-agents stay on 2h — operator wants breaking news drafts surfaced ~2x as often without disturbing the 2h staggered cadence for the other content types"
  - "+10s start_date buffer over all 7 sub-agents (not just offset=0) — simpler than a branch and ensures start_date > scheduler.start() wall clock universally"
metrics:
  duration: "~10 min"
  completed: 2026-04-21
commit: c5d32f3
---

# Quick 260421-m9k: Breaking News Hourly Cadence + offset=0 First-Fire Fix Summary

Make `sub_breaking_news` fire every 1 hour while keeping the other 6 sub-agents on 2h, and fix a latent APScheduler edge case where offset=0 jobs skip their first fire on every scheduler boot.

## What Changed

### scheduler/worker.py (5 edit sites)

**1. Module docstring (L8-9) — mixed cadence wording:**

```diff
-- 7 content sub-agents, each on a 2h IntervalTrigger staggered across the
-  2h window with offsets [0, 17, 34, 51, 68, 85, 102] minutes.
+- 7 content sub-agents on IntervalTrigger — sub_breaking_news every 1h,
+  the other 6 every 2h — staggered across the 2h window with offsets
+  [0, 17, 34, 51, 68, 85, 102] minutes.
```

**2. CONTENT_SUB_AGENTS type annotation (L85) + tuple-shape comment (L82):**

```diff
-# Tuple shape: (job_id, run_fn, name, lock_id, offset_minutes).
+# Tuple shape: (job_id, run_fn, name, lock_id, offset_minutes, interval_hours).
 ...
-CONTENT_SUB_AGENTS: list[tuple[str, object, str, int, int]] = [
+CONTENT_SUB_AGENTS: list[tuple[str, object, str, int, int, int]] = [
```

**3. CONTENT_SUB_AGENTS rows (L86-92) — append `interval_hours` 6th field:**

```diff
-    ("sub_breaking_news", breaking_news.run_draft_cycle,  "Breaking News",  1010,   0),
-    ("sub_threads",       threads.run_draft_cycle,        "Threads",        1011,  17),
-    ("sub_long_form",     long_form.run_draft_cycle,      "Long-form",      1012,  34),
-    ("sub_quotes",        quotes.run_draft_cycle,         "Quotes",         1013,  51),
-    ("sub_infographics",  infographics.run_draft_cycle,   "Infographics",   1014,  68),
-    ("sub_video_clip",    video_clip.run_draft_cycle,     "Gold Media",     1015,  85),
-    ("sub_gold_history",  gold_history.run_draft_cycle,   "Gold History",   1016, 102),
+    ("sub_breaking_news", breaking_news.run_draft_cycle,  "Breaking News",  1010,   0, 1),
+    ("sub_threads",       threads.run_draft_cycle,        "Threads",        1011,  17, 2),
+    ("sub_long_form",     long_form.run_draft_cycle,      "Long-form",      1012,  34, 2),
+    ("sub_quotes",        quotes.run_draft_cycle,         "Quotes",         1013,  51, 2),
+    ("sub_infographics",  infographics.run_draft_cycle,   "Infographics",   1014,  68, 2),
+    ("sub_video_clip",    video_clip.run_draft_cycle,     "Gold Media",     1015,  85, 2),
+    ("sub_gold_history",  gold_history.run_draft_cycle,   "Gold History",   1016, 102, 2),
```

**4. `build_scheduler` docstring (L233-234), log line (L244-245), registration loop (L266-274):**

```diff
-    - 7 content sub-agents: IntervalTrigger(hours=2) with staggered start_date
-      offsets [0, 17, 34, 51, 68, 85, 102] minutes.
+    - 7 content sub-agents: IntervalTrigger with per-agent hours (sub_breaking_news=1,
+      others=2) and staggered start_date offsets [0, 17, 34, 51, 68, 85, 102] minutes.
 ...
     logger.info(
-        "Schedule config: digest=cron(%d:00 UTC), content_sub_agents=%d jobs on 2h interval",
+        "Schedule config: digest=cron(%d:00 UTC), content_sub_agents=%d jobs (sub_breaking_news=1h, others=2h)",
         digest_hour, len(CONTENT_SUB_AGENTS),
     )
 ...
     now = datetime.now(timezone.utc)
-    for job_id, run_fn, name, lock_id, offset in CONTENT_SUB_AGENTS:
-        start_date = now + timedelta(minutes=offset)
+    for job_id, run_fn, name, lock_id, offset, interval_hours in CONTENT_SUB_AGENTS:
+        # +10s buffer ensures start_date > scheduler.start() wall clock for offset=0
+        # (APScheduler IntervalTrigger skips first fire if start_date <= now).
+        start_date = now + timedelta(minutes=offset) + timedelta(seconds=10)
         scheduler.add_job(
             _make_sub_agent_job(job_id, lock_id, run_fn, engine),
-            trigger=IntervalTrigger(hours=2, start_date=start_date),
+            trigger=IntervalTrigger(hours=interval_hours, start_date=start_date),
             id=job_id,
-            name=f"{name} — every 2h (offset +{offset}m)",
+            name=f"{name} — every {interval_hours}h (offset +{offset}m)",
         )
```

**5. `upsert_agent_config` docstring middle line (L286):**

```diff
     quick-260421-eoe: removed the old content_agent interval override —
-    sub-agents run on a fixed 2h cadence. The DB row may remain for manual
-    cleanup but is no longer authoritative.
+    sub-agents run on fixed cadences (sub_breaking_news=1h, others=2h). The
+    DB row may remain for manual cleanup but is no longer authoritative.
```

### scheduler/agents/content/breaking_news.py (1 edit)

**L3 (module docstring):**

```diff
-Part of the 7-agent split (quick-260421-eoe). Runs every 2 hours on its own
+Part of the 7-agent split (quick-260421-eoe). Runs every hour on its own
```

### scheduler/tests/test_worker.py (1 edit — Rule 3 deviation)

**L88 (`test_sub_agent_lock_ids` tuple unpacking — 5 → 6 fields):**

```diff
-    sub_entries = {job_id: lock_id for job_id, _, _, lock_id, _ in CONTENT_SUB_AGENTS}
+    sub_entries = {job_id: lock_id for job_id, _, _, lock_id, _, _ in CONTENT_SUB_AGENTS}
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] test_worker.py::test_sub_agent_lock_ids tuple unpacking updated**

- **Found during:** Task 1 verification (`uv run pytest -x`)
- **Issue:** Test at `scheduler/tests/test_worker.py:88` directly unpacks `CONTENT_SUB_AGENTS` tuples as `job_id, _, _, lock_id, _` (5 fields). The tuple schema change from 5 → 6 fields broke the test with `ValueError: too many values to unpack (expected 5)`.
- **Plan expectation:** The plan explicitly scoped out test-file edits ("grep confirmed zero test references to `IntervalTrigger` / `hours=2` / cadence") and expected exactly 2 files modified (`worker.py` + `breaking_news.py`).
- **Why the grep missed this:** The plan's grep searched for cadence-related strings (`IntervalTrigger`, `hours=2`, cadence literals). This test doesn't reference any of those — it just unpacks the tuple by position, so the tuple-shape change inherently breaks it even though the test is about lock IDs, not cadence.
- **Fix:** Added one extra `_` to the unpacking pattern (`job_id, _, _, lock_id, _, _`) to absorb the new `interval_hours` field. No test semantics changed — the test still validates the exact same lock-ID mapping.
- **Files modified:** `scheduler/tests/test_worker.py` (1-line change).
- **Commit:** `c5d32f3` (folded into the single atomic commit, not a separate one).

**Impact on plan's "exactly 2 files" invariant:** Final commit touches **3 files** instead of the plan's expected 2. The third file (`test_worker.py`) is a directly-caused test-schema sync — not scope expansion. Without this edit, `uv run pytest -x` fails with the tuple unpacking error, blocking Task 1's `<done>` criteria.

## Verification

All 6 verification checks from the plan pass:

| # | Check | Result |
|---|-------|--------|
| 1 | `grep 'IntervalTrigger(hours=' scheduler/worker.py` | `hours=interval_hours` (variable) ✓ |
| 2 | `grep 'sub_breaking_news' scheduler/worker.py` | tuple row shows `1` as 6th field ✓ |
| 3 | `grep 'start_date = now' scheduler/worker.py` | `+ timedelta(seconds=10)` buffer present ✓ |
| 4 | `cd scheduler && uv run ruff check .` | `All checks passed!` (exit 0) ✓ |
| 5 | `cd scheduler && uv run pytest -x` | `74 passed, 5 warnings in 0.78s` (exit 0) ✓ — matches pre-change baseline (74/74) |
| 6 | `git diff main --stat` | 3 scheduler files (see deviation above) |

### Ruff output

```
All checks passed!
```

### Pytest output

```
======================== 74 passed, 5 warnings in 0.78s ========================
```

Pass count **matches pre-change baseline** (74/74).

## Commit

**SHA:** `c5d32f3`
**Branch:** `quick/260421-m9k-breaking-news-hourly`
**Message:**

```
fix(scheduler): sub_breaking_news hourly + fix offset=0 first-fire skip (quick-260421-m9k)
```

## Post-Deploy Checklist (operator — after next Railway scheduler redeploy)

1. **All 7 sub-agents fire within their first offset window on scheduler boot** — no 2h dark period for `sub_breaking_news` (offset=0). Check Railway logs for `Job sub_breaking_news: started` ~10s after the scheduler boot line.
2. **`sub_breaking_news` produces an `agent_run` row every hour** from boot onward; other 6 sub-agents continue on 2h cadence (`SELECT agent_name, started_at FROM agent_runs ORDER BY started_at DESC LIMIT 20;`).
3. **Frontend `/agents/breaking-news` shows "Pulled from agent run at {time}" header** ~10s after scheduler boot (first run fires with the +10s buffer past `now`).

## Self-Check: PASSED

Files modified (verified on disk):
- `/Users/matthewnelson/seva-mining/scheduler/worker.py` — FOUND
- `/Users/matthewnelson/seva-mining/scheduler/agents/content/breaking_news.py` — FOUND
- `/Users/matthewnelson/seva-mining/scheduler/tests/test_worker.py` — FOUND

Commit `c5d32f3` — FOUND on `quick/260421-m9k-breaking-news-hourly`.
