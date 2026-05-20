---
phase: 08-ui-polish-dead-code-strip
plan: 04
subsystem: scheduler
tags: [dead-code-strip, scheduler, advisory-locks, JOB_LOCK_IDS, sub-agent-retirement, OPS-02, D-07, D-08, D-09, UI-06]

# Dependency graph
requires:
  - phase: 08-01
    provides: "Wave 0 RED test stubs + pre-strip safety verification script (scripts/verify-dead-code-strip-safe.sh) — exited 0 before Task 1 started, confirming no surviving callers of agents.content.*"
  - phase: 08-02
    provides: "Wave 1 UI polish landed (UI-01..04 amber tokens + hover transitions) — visual baseline established before strip"
  - phase: 08-03
    provides: "Wave 2 X-handle pill (UI-05) + UI-07 human-verify checkpoint PASS — visual baseline confirmed green at 1440x900 across 3 active tabs before strip"
  - phase: 4 (v2.1 numbering)
    provides: "CONTENT_CRON_AGENTS = [] neutering (Phase 4 Task 4, 2026-04-27) — sub-agent crons were already deregistered; this strip removes the source files + tests + lock IDs"
provides:
  - "scheduler/worker.py JOB_LOCK_IDS shrunk from 10 keys to 4 keys: midday_digest=1005 (D-07-retained dead code), daily_summary=1017, daily_summary_prune=1018, weekly_sweeper=1019"
  - "OPS-02 startup uniqueness assertion preserved verbatim and verified passing post-strip (4 unique values)"
  - "scheduler/agents/content/ directory removed entirely (7 files: 6 sub-agent sources + __init__.py with run_text_story_cycle + _is_already_covered_today helpers)"
  - "8 scheduler test files removed (test_breaking_news, test_threads, test_quotes, test_infographics, test_gold_media, test_gold_history, test_content_init, test_content_wrapper)"
  - "scheduler/worker.py docstring + comment block + build_scheduler docstring + DIGEST_EXCLUDED_CONTENT_TYPES comment + _read_schedule_config docstring + upsert_agent_config docstring all updated to remove dangling sub-agent references and point at CLAUDE.md historical notes"
  - "scheduler/tests/test_worker.py simplified: 7 sub-agent regression-guard functions deleted; test_retired_crons_absent_from_job_lock_ids updated to assert len(JOB_LOCK_IDS) == 4 and 4-key set membership; sub_long_form / content_agent / morning_digest absence guards preserved"
  - "Pre-strip safety script re-run after deletion: run_text_story_cycle callers = 0 in source files (the stale .pytest_cache nodeids hit was cleared)"
  - "DB historical data preserved per D-08 — no Alembic migration created (backend/alembic/versions/ count unchanged at 14)"
  - "Phase 8 closure: UI-01 ✓ UI-02 ✓ UI-03 ✓ UI-04 ✓ UI-05 ✓ UI-06 ✓ UI-07 ✓"
affects: [v2.1-shipping, future-cron-additions]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Dead-code strip protocol (3-task atomic pattern): (1) update assertion-based tests FIRST in their own commit with a 'KNOWN RED STATE' commit message; (2) edit the production dict + docstrings + comment blocks in the immediately-following commit that resolves the RED state; (3) atomic git rm of source/test pairs to defeat pytest collection-time ImportError (Pitfall 3) — establishes the canonical strip order for future v1.x→v2.x retirements"
    - "Pre-strip safety gate pattern: bash scripts/verify-dead-code-strip-safe.sh MUST exit 0 before any deletion — checks live imports, lock-ID call sites, helper-function callers, neutered-list invariant (CONTENT_CRON_AGENTS == []), and OPS-02 reachability; pre-strip + post-strip runs document the delta"
    - "Source-out / data-stays purge pattern (now thrice-applied: 260420-sn9 Twitter+Senior, 260423-k8n sub_long_form, 260519 Phase 8 UI-06 6-sub-agent retirement): historical agent_runs / content_bundles / draft_items rows preserved verbatim — no Alembic migration, no DELETE statements; rationale tracked in CLAUDE.md historical notes"

key-files:
  created: []
  modified:
    - "scheduler/tests/test_worker.py (Task 1: 7 sub-agent regression-guard functions deleted; test_retired_crons_absent_from_job_lock_ids assertion updates — len == 10 → 4, 6-key set → 4-key set; 4 insertions, 95 deletions)"
    - "scheduler/worker.py (Task 2: JOB_LOCK_IDS dict shrunk from 10 keys to 4; OPS-02 assertion preserved; module docstring rewritten to remove '7 independent sub-agent crons under agents.content.*' phrase + 6-cron bullet list; comment block enumerating retired sub-agent source files deleted; build_scheduler docstring + DIGEST_EXCLUDED_CONTENT_TYPES comment + _read_schedule_config + upsert_agent_config docstrings softened to past-tense Phase 8 strip notes; 60 insertions, 87 deletions)"
  deleted:
    - "scheduler/agents/content/__init__.py (Task 3: run_text_story_cycle + _is_already_covered_today helpers — 458 lines)"
    - "scheduler/agents/content/breaking_news.py (Task 3)"
    - "scheduler/agents/content/threads.py (Task 3)"
    - "scheduler/agents/content/quotes.py (Task 3)"
    - "scheduler/agents/content/infographics.py (Task 3)"
    - "scheduler/agents/content/gold_media.py (Task 3)"
    - "scheduler/agents/content/gold_history.py (Task 3)"
    - "scheduler/tests/test_breaking_news.py (Task 3)"
    - "scheduler/tests/test_threads.py (Task 3)"
    - "scheduler/tests/test_quotes.py (Task 3)"
    - "scheduler/tests/test_infographics.py (Task 3)"
    - "scheduler/tests/test_gold_media.py (Task 3)"
    - "scheduler/tests/test_gold_history.py (Task 3)"
    - "scheduler/tests/test_content_init.py (Task 3)"
    - "scheduler/tests/test_content_wrapper.py (Task 3)"
    - "scheduler/agents/content/ (entire directory removed via rmdir after git rm of contents)"

key-decisions:
  - "midday_digest=1005 RETAINED in JOB_LOCK_IDS as dead code per D-07 literal wording (D-07 lists 1010-1016 explicitly, not 1005) — matches RESEARCH §Runtime State recommendation (option b: do not expand strip scope beyond what CONTEXT specifies). Cleaner final state (4 keys) preferred over the 3-key alternative; midday_digest factory + lock ID stay as dead code consistent with how 260423-k8n preserved sub_long_form's lock ID as well."
  - "Task 1 + Task 2 split into TWO commits (not atomic single commit) — plan offered both; the split was chosen to keep the strip protocol pattern legible for future v1.x→v2.x retirements (RED-state commit message is self-documenting). Risk mitigation: Task 1 commit message explicitly warns 'KNOWN RED STATE' and Task 2 follows immediately with no other work intervening."
  - "Line-58 / line-74 with_advisory_lock SCRUB SKIPPED — the literal lock ID 1010 + label 'sub_breaking_news' in test_advisory_lock_prevents_duplicate_run + test_job_exception_does_not_propagate are KEPT verbatim. These are generic locking smoke tests where 1010 is just an integer (the test asserts lock behavior, not dict membership). Plan called the scrub 'RECOMMENDED but not required for correctness' — skipping minimizes churn and preserves the regression-guard symmetry with the older 260423-k8n purge."
  - "Beyond-plan deletions: 3 additional sub-agent regression-guard tests deleted from test_worker.py beyond the 4 the plan called out in Task 1 (test_gold_history_is_every_other_day, test_infographics_is_daily_cron, test_gold_media_is_daily_cron). Plan omitted them but their JOB_LOCK_IDS.get('sub_gold_history') == 1016 assertions would have silently failed once Task 2 dropped those keys (.get() returns None, None != 1016, AssertionError). Tracked below as Deviation [Rule 1]."

# Verification record (specific results)
metrics:
  duration: "~14 minutes"
  completed: "2026-05-19"
  tasks_count: 3
  files_modified: 2
  files_deleted: 15
  pre_strip_test_count: 352
  post_strip_test_count: 265
  post_strip_test_breakdown: "264 passed + 1 skipped"
  test_delta: "-87 tests (8 deleted test files: test_breaking_news.py + test_threads.py + test_quotes.py + test_infographics.py + test_gold_media.py + test_gold_history.py + test_content_init.py + test_content_wrapper.py)"
  job_lock_ids_count: 4
  ops_02_smoke: "PASS, len= 4 keys= ['daily_summary', 'daily_summary_prune', 'midday_digest', 'weekly_sweeper']"
  alembic_versions_count: 14
  frontend_test_count: "141/141 PASS (23 test files) — sanity confirmed strip is scheduler-only"

commits:
  task_1: "89a1f67 test(08-04): update test_worker.py assertions for post-strip JOB_LOCK_IDS shape"
  task_2: "c3ba5b4 feat(08-04): shrink JOB_LOCK_IDS to 4 keys; clean sub-agent references"
  task_3: "9e51f7d chore(08-04): strip v1.0 content sub-agents (UI-06)"
---

# Phase 8 Plan 04: Wave 3 — UI-06 Dead-Code Strip Summary

**One-liner:** Final wave of Phase 8 (UI Polish + Dead-Code Strip) — atomically removed 6 v1.0 content sub-agent source files + 8 paired test files + the `scheduler/agents/content/` package directory + 6 sub_* entries from `JOB_LOCK_IDS` (lock IDs 1010-1016), shrinking the dict to 4 keys (midday_digest=1005 dead code, daily_summary=1017, daily_summary_prune=1018, weekly_sweeper=1019) and verifying OPS-02 uniqueness still holds; DB historical rows preserved per D-08 (no Alembic migration, matching 260420-sn9 + 260423-k8n purge precedents).

## What Was Done

### Pre-strip safety gate (BEFORE Task 1)

Ran `bash /Users/matthewnelson/seva-mining/scripts/verify-dead-code-strip-safe.sh`:
- Check 1 (live imports of `agents.content.*`): PASS — no live imports outside the package itself + its tests
- Check 2 (lock IDs 1010-1016 call sites): only in JOB_LOCK_IDS dict + worker.py comments + test_worker.py assertions; NO `with_advisory_lock(..., 101[0-6], ...)` calls
- Check 3 (run_text_story_cycle callers): 41 references pre-strip (all inside to-be-deleted files), expected to drop to 0 post-strip
- Check 4 (CONTENT_CRON_AGENTS == []): PASS — Phase 4 neutering still in effect
- Check 5 (OPS-02 assertion present): PASS
- Final exit: `=== PRE-STRIP VERIFICATION PASS — Wave 3 strip is safe to proceed ===`

### Task 1 (commit `89a1f67`): test_worker.py assertion update FIRST

Deleted 7 sub-agent regression-guard functions whose hardcoded assertions reference deleted lock IDs:
- `test_sub_agent_lock_ids` (asserted `JOB_LOCK_IDS["sub_breaking_news"] == 1010` etc. — all 6 sub-agents)
- `test_quotes_is_daily_cron`
- `test_breaking_news_is_hourly_cron`
- `test_threads_is_every_three_hours_cron`
- `test_gold_history_is_every_other_day` (beyond-plan delete — see Deviation §Rule 1 below)
- `test_infographics_is_daily_cron` (beyond-plan delete)
- `test_gold_media_is_daily_cron` (beyond-plan delete)

Updated `test_retired_crons_absent_from_job_lock_ids`:
- `assert len(JOB_LOCK_IDS) == 10` → `assert len(JOB_LOCK_IDS) == 4`
- `set(JOB_LOCK_IDS.keys()) == { ... 10 keys ... }` → `{ midday_digest, daily_summary, daily_summary_prune, weekly_sweeper }`

Preserved (verified by grep counts in acceptance check):
- `assert "sub_long_form" not in JOB_LOCK_IDS` (260423-k8n regression guard)
- `assert "content_agent" / "gold_history_agent" / "twitter_agent" / "expiry_sweep" / "morning_digest" not in JOB_LOCK_IDS` (earlier-purge guards)
- `assert JOB_LOCK_IDS["midday_digest"] == 1005` (D-07 retention)
- Line 58 `await with_advisory_lock(mock_conn, 1010, "sub_breaking_news", job_fn)` generic lock smoke (literal int + label only, no dict lookup)
- Line 74 sibling generic lock smoke

Commit message explicitly flagged `KNOWN RED STATE` — test fails on `len(==4)` until Task 2 lands worker.py changes. No other work intervened between Task 1 and Task 2.

### Task 2 (commit `c3ba5b4`): scheduler/worker.py JOB_LOCK_IDS shrink + comment cleanup

Edited `scheduler/worker.py`:
- **JOB_LOCK_IDS dict shrunk 10 → 4 keys**, preserving exact key order (midday_digest, daily_summary, daily_summary_prune, weekly_sweeper). Inline comments re-grouped by purpose (dead code / v2.0 Phase 1 / v2.1 Phase 7).
- **OPS-02 uniqueness assertion preserved verbatim** with an updated explanatory comment pointing at the 260519 strip rationale in CLAUDE.md.
- **Module docstring rewritten** — removed the "by 7 independent sub-agent crons under agents.content.*" phrase (acceptance grep confirms 0 matches post-edit), removed the 6-cron sub-agent bullet list, condensed 5 historical cron-lineage paragraphs (260421-mos, 260422-vxg, 260424-j5i/kqa, 260427-m49) into a single Phase 8 UI-06 note that cross-references CLAUDE.md historical notes.
- **Comment block (formerly 9 lines) enumerating the 6 sub-agent source-file paths + lock IDs DELETED.**
- **build_scheduler docstring** rewritten: "6 cron sub-agents" bullet list removed; replaced with 3-job summary + Phase 8 UI-06 footnote.
- **DIGEST_EXCLUDED_CONTENT_TYPES comment** updated: stale `scheduler/agents/content/__init__.py` firehose reference changed to past-tense, noting the constant is now harmless dead code consumed only by the also-dead-code midday_digest factory.
- **_read_schedule_config + upsert_agent_config docstrings** softened: sub-agent cadence references rewritten in past-tense pointing at the Phase 8 UI-06 strip.
- **Comment about "dead-code-only retirement"** (line 381 area) rewritten: replaced the "do NOT delete v1.0 sub-agent source files" guidance (now contradicted by the strip) with a D-07 reference noting midday_digest stays but v1.0 sub_* lock IDs were removed.

Post-edit test run:
```
cd /Users/matthewnelson/seva-mining/scheduler && uv run pytest tests/test_worker.py -x
================== 33 passed in 0.23s ==================
```

OPS-02 smoke:
```
$ uv run python -c "from worker import JOB_LOCK_IDS; ..."
OPS-02 PASS, len= 4 keys= ['daily_summary', 'daily_summary_prune', 'midday_digest', 'weekly_sweeper']
```

### Task 3 (commit `9e51f7d`): Atomic git rm of 14 source/test files + directory removal

Pre-deletion grep for `run_text_story_cycle | _is_already_covered_today` confirmed all 41 references were inside the deletion list (6 sub-agent sources + 3 test files that import the helpers + the helper definitions themselves in `__init__.py`). Zero references in production code outside the package.

Atomic `git rm` of 15 files in a single staged commit:

| Source files (7) | Test files (8) |
|---|---|
| scheduler/agents/content/__init__.py | scheduler/tests/test_breaking_news.py |
| scheduler/agents/content/breaking_news.py | scheduler/tests/test_threads.py |
| scheduler/agents/content/threads.py | scheduler/tests/test_quotes.py |
| scheduler/agents/content/quotes.py | scheduler/tests/test_infographics.py |
| scheduler/agents/content/infographics.py | scheduler/tests/test_gold_media.py |
| scheduler/agents/content/gold_media.py | scheduler/tests/test_gold_history.py |
| scheduler/agents/content/gold_history.py | scheduler/tests/test_content_init.py |
| | scheduler/tests/test_content_wrapper.py |

Total: **5100 lines deleted**.

Directory cleanup:
```
$ find scheduler -name __pycache__ -type d -exec rm -rf {} +
$ rmdir scheduler/agents/content
# (succeeded — directory removed)
$ test ! -d /Users/matthewnelson/seva-mining/scheduler/agents/content && echo OK
OK
```

Stale `.pytest_cache/v/cache/nodeids` (containing references to deleted test node IDs) was cleared with `rm -rf scheduler/.pytest_cache`. Note: `.pytest_cache/` is already in `.gitignore` so the cache file was never tracked.

## Verification (specific results)

### Acceptance criteria

| Check | Expected | Actual | Status |
|---|---|---|---|
| Pre-strip safety gate (`bash scripts/verify-dead-code-strip-safe.sh`) | exit 0 | exit 0 | PASS |
| Task 1 commit references `len(JOB_LOCK_IDS) == 4` | grep -c returns 1 | 1 | PASS |
| Task 1 commit removes `len(JOB_LOCK_IDS) == 10` | grep -c returns 0 | 0 | PASS |
| Task 1 preserves `"sub_long_form" not in JOB_LOCK_IDS` guard | grep -c returns 1 | 1 | PASS |
| Task 2 commit removes `"sub_breaking_news"` | grep -c returns 0 | 0 | PASS |
| Task 2 commit removes `"sub_threads"` | grep -c returns 0 | 0 | PASS |
| Task 2 commit removes `"sub_quotes"` | grep -c returns 0 | 0 | PASS |
| Task 2 commit removes `"sub_infographics"` | grep -c returns 0 | 0 | PASS |
| Task 2 commit removes `"sub_gold_media"` | grep -c returns 0 | 0 | PASS |
| Task 2 commit removes `"sub_gold_history"` | grep -c returns 0 | 0 | PASS |
| Task 2 preserves `"midday_digest"` | grep -c returns ≥1 | 4 | PASS |
| Task 2 preserves `"daily_summary"` | grep -c returns ≥1 | 4 | PASS |
| Task 2 preserves `"weekly_sweeper"` | grep -c returns ≥1 | 4 | PASS |
| Task 2 removes `"7 independent sub-agent crons under agents.content"` | grep -c returns 0 | 0 | PASS |
| Task 2 removes `"scheduler/agents/content/breaking_news.py"` | grep -c returns 0 | 0 | PASS |
| Task 2: `uv run pytest tests/test_worker.py -x` | exit 0 | 33 passed | PASS |
| Task 2: OPS-02 smoke `len(JOB_LOCK_IDS) == 4 == len(set(...))` | exit 0 | `OPS-02 PASS, len= 4` | PASS |
| Task 3: all 14 file paths absent | exit 0 for `test ! -f ...` | all 14 absent | PASS |
| Task 3: `scheduler/agents/content/` directory absent | exit 0 for `test ! -d ...` | absent | PASS |
| Task 3: `uv run pytest tests/ -x` (full scheduler) | exit 0 | 264 passed, 1 skipped | PASS |
| Task 3: OPS-02 smoke + build_scheduler import | exit 0 | `OPS-02 PASS, len= 4` | PASS |
| Task 3: `run_text_story_cycle` callers in source files | grep returns 0 | 0 | PASS |
| Task 3: No new Alembic migration | versions/ count unchanged | 14 → 14 | PASS |
| Frontend sanity (`npm test -- --run`) | all GREEN | 141/141 pass (23 files) | PASS |

### Pre/post-strip pytest counts

- **Pre-strip baseline:** 352 tests collected (`uv run pytest tests/ --collect-only -q`)
- **Post-strip:** 265 tests collected (264 passed + 1 skipped); delta = **-87 tests** across 8 deleted test files (each carried 10-15 sub-agent assertions)

### OPS-02 final state

```
$ cd /Users/matthewnelson/seva-mining/scheduler && uv run python -c "from worker import JOB_LOCK_IDS, build_scheduler; assert len(set(JOB_LOCK_IDS.values())) == len(JOB_LOCK_IDS); assert len(JOB_LOCK_IDS) == 4; print('OPS-02 PASS, len=', len(JOB_LOCK_IDS), 'keys=', sorted(JOB_LOCK_IDS.keys()))"
OPS-02 PASS, len= 4 keys= ['daily_summary', 'daily_summary_prune', 'midday_digest', 'weekly_sweeper']
```

### Final JOB_LOCK_IDS contents (4 entries)

```python
JOB_LOCK_IDS: dict[str, int] = {
    # midday_digest retained as dead code per Phase 1 Plan 05 (CRIT-1).
    # Registration removed from build_scheduler; factory + dict entry preserved.
    "midday_digest": 1005,

    # v2.0 daily_summary feed (Phase 1, Plan 05).
    "daily_summary": 1017,
    "daily_summary_prune": 1018,

    # v2.1 Phase 7 weekly_sweeper cron (lock reserved Phase 5 Plan 01).
    "weekly_sweeper": 1019,
}
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Plan omitted 3 sub-agent regression-guard tests that would have silently failed after Task 2**

- **Found during:** Task 1
- **Issue:** The plan's Task 1 deletion list named 4 functions (`test_sub_agent_lock_ids`, `test_quotes_is_daily_cron`, `test_breaking_news_is_hourly_cron`, `test_threads_is_every_three_hours_cron`) but omitted 3 functionally identical functions in the same file: `test_gold_history_is_every_other_day`, `test_infographics_is_daily_cron`, `test_gold_media_is_daily_cron`. Each contains `assert JOB_LOCK_IDS.get("sub_gold_history") == 1016` (or the analogous key for the other two). After Task 2 removed the dict keys, `.get()` would return None and `None == 1016` is False — the surviving tests would have failed pytest at Task 2's verify step. The plan classified these as `Rule 1` candidates implicitly (its acceptance criteria for Task 1 require the worker pytest to pass after Task 2 — impossible without these deletions).
- **Fix:** Deleted all 3 functions in the same Task 1 commit (89a1f67) using the same pattern as the 4 plan-named deletions.
- **Files modified:** `scheduler/tests/test_worker.py` (additional 21 lines removed beyond plan)
- **Commit:** `89a1f67` (folded into Task 1 commit)
- **Validation:** Task 2's verify step (`uv run pytest tests/test_worker.py -x`) passed 33/33 — confirms the fix was necessary and sufficient.

**2. [Rule 3 - Blocking] Stale `.pytest_cache/v/cache/nodeids` flagged false positive in post-strip safety re-run**

- **Found during:** Task 3 (post-deletion safety script re-run)
- **Issue:** `bash scripts/verify-dead-code-strip-safe.sh` reported 1 remaining `run_text_story_cycle` reference at `scheduler/.pytest_cache/v/cache/nodeids:284` — a stale pytest cache file from the pre-strip test run. The safety script's grep does not filter `.pytest_cache/` (it filters `__pycache__` and `.pyc`). The acceptance criterion ("grep returns 0") would have falsely failed.
- **Fix:** `rm -rf /Users/matthewnelson/seva-mining/scheduler/.pytest_cache` — cache file is in `.gitignore` already (no tracked-file impact). Re-ran grep manually with `.pytest_cache` filter added; got 0 hits.
- **Files modified:** None tracked (cache file was untracked).
- **Commit:** N/A — no source-file change. Documented here for the verifier.
- **Note for future:** The safety script `scripts/verify-dead-code-strip-safe.sh` could be enhanced in a future quick task to filter `.pytest_cache/` from its grep — out of scope for this plan, so logged informally.

### Skipped Optional Items

- **Line-58 / line-74 with_advisory_lock literal scrub** — plan called this "RECOMMENDED but not required for correctness." Skipped per documented key-decision above: the literal `1010` + `"sub_breaking_news"` are generic locking smoke tests; the test asserts lock behavior, not dict membership; keeping them preserves regression-guard symmetry with the 260423-k8n purge.

## Known Stubs

None — no stub patterns (empty arrays, "coming soon", TODO/FIXME placeholders) introduced by this plan. The plan is a pure code-removal operation; the surviving code paths (3 active crons: daily_summary, daily_summary_prune, weekly_sweeper) all have wired data sources and were verified by the full pytest suite passing post-strip.

## Authentication Gates

None encountered — this is a scheduler-only code strip with no external API or auth interactions.

## Phase 8 closure note

Per D-09, this plan was the FINAL work of Phase 8. With Task 3 committed, all 7 Phase 8 requirements are satisfied:

- **UI-01** ✓ (Plan 08-02 — amber accent tokens applied to active tab, primary CTA, status badges, today-cell, hover states)
- **UI-02** ✓ (Plan 08-02 — spacing tokens p-6/gap-6/space-y-4 refined)
- **UI-03** ✓ (Plan 08-02 — typography weights 400/500/600 via standard Tailwind utilities)
- **UI-04** ✓ (Plan 08-02 — subtle borders + hover states uniformly applied to cards)
- **UI-05** ✓ (Plan 08-03 — X-handle monospace pill via rehypeHandleMentions + MarkdownContent wrapper)
- **UI-06** ✓ (Plan 08-04 — this plan; v1.0 dead-code strip per D-07)
- **UI-07** ✓ (Plan 08-03 — 1440x900 visual QA checklist PASS by operator, documented in 08-UI-07-CHECKLIST-RESULTS.md)

Milestone v2.1 — Three-Tab Content Engine + UI Polish — all 4 phases complete (Phase 5 foundation + Phase 6 calendar + Phase 7 viral sweeper + Phase 8 UI polish + dead-code strip).

## Follow-up records

- **No `unist-util-visit` follow-up needed** — Plan 08-03's Wave 2 strip-protocol research mentioned a potential dependency add; no additional install was needed for this plan (the rehype mention plugin was already shipped + tested in Plan 08-03).
- **No DB migration created** — confirmed by `ls backend/alembic/versions/ | wc -l` returning 14 (unchanged from pre-strip baseline). D-08 invariant preserved; matches 260420-sn9 + 260423-k8n purge precedents.
- **Scheduler 5-second boot smoke skipped** — the OPS-02 smoke + `from worker import build_scheduler` import succeeded, which exercises the same module-import code path as a Railway boot would. The 5-second boot was a belt-and-suspenders check in the plan; the import-success result is equivalent evidence of no ImportError/ModuleNotFoundError/AttributeError on JOB_LOCK_IDS. Skipping the timeout-wrapped boot smoke avoids spurious DATABASE_URL connection errors in the local-dev env where no Postgres is running.

## Self-Check: PASSED

**File existence verification (15 deletions confirmed):**

```
$ for f in breaking_news threads quotes infographics gold_media gold_history __init__; do test ! -f "scheduler/agents/content/${f}.py" && echo "OK"; done
OK x7
$ test ! -d scheduler/agents/content && echo "OK"
OK
$ for f in breaking_news threads quotes infographics gold_media gold_history content_init content_wrapper; do test ! -f "scheduler/tests/test_${f}.py" && echo "OK"; done
OK x8
```

**Commit verification:**

```
$ git log --oneline -3
9e51f7d chore(08-04): strip v1.0 content sub-agents (UI-06)
c3ba5b4 feat(08-04): shrink JOB_LOCK_IDS to 4 keys; clean sub-agent references
89a1f67 test(08-04): update test_worker.py assertions for post-strip JOB_LOCK_IDS shape
```

All 3 task commits (89a1f67, c3ba5b4, 9e51f7d) verified present in git log. All 15 file deletions verified absent from filesystem. Directory `scheduler/agents/content/` verified removed. All claims in this SUMMARY are reproducible.
