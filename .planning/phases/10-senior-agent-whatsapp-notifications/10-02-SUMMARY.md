---
phase: 10-senior-agent-whatsapp-notifications
plan: "02"
subsystem: scheduler/agents
tags: [whatsapp, notifications, twitter-agent, instagram-agent, content-agent, tdd]
dependency_graph:
  requires:
    - 10-01 (send_whatsapp_message() free-form API)
  provides:
    - All three agents call send_whatsapp_message() after DraftItems committed
    - New-item notifications fire immediately when count > 0
  affects:
    - scheduler/agents/twitter_agent.py
    - scheduler/agents/instagram_agent.py
    - scheduler/agents/content_agent.py
    - scheduler/agents/senior_agent.py
    - scheduler/services/whatsapp.py
tech_stack:
  added: []
  patterns:
    - Lazy import of send_whatsapp_message inside try/except for non-fatal failure isolation
    - sys.modules injection for mocking lazy-imported modules in tests
    - Notification in run() finally block for instagram + content agents (consistent pattern)
    - Notification in _run_pipeline() Step 13 for twitter agent (inline with pipeline steps)
key_files:
  created: []
  modified:
    - scheduler/agents/twitter_agent.py
    - scheduler/agents/instagram_agent.py
    - scheduler/agents/content_agent.py
    - scheduler/agents/senior_agent.py
    - scheduler/services/whatsapp.py
    - scheduler/tests/test_twitter_agent.py
    - scheduler/tests/test_instagram_agent.py
    - scheduler/tests/test_content_agent.py
decisions:
  - "Instagram + Content Agent notification in run() finally block (not _run_pipeline) — enables clean test isolation via mocked _run_pipeline that sets agent_run.items_queued"
  - "Twitter Agent notification at end of _run_pipeline() Step 13 — items_queued is a local variable not accessible from run()"
  - "sys.modules patch for senior_agent lazy import in twitter tests — agents/__init__.py import chain makes direct patch() fail; sys.modules injection is the standard pattern"
metrics:
  duration: "~8 minutes"
  completed_date: "2026-04-07"
  tasks: 3
  files_modified: 8
---

# Phase 10 Plan 02: Agent New-Item WhatsApp Notifications Summary

WhatsApp new-item notification hook added to all three sub-agents (Twitter, Instagram, Content). Every time an agent creates draft items, the operator receives an instant WhatsApp message naming the agent and count.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | Twitter Agent failing tests | 4e4a29b | test_twitter_agent.py, whatsapp.py |
| 1 (GREEN) | Twitter Agent notification hook | 903e6d6 | twitter_agent.py |
| 2 (RED) | Instagram Agent failing tests | 9c61133 | test_instagram_agent.py |
| 2 (GREEN) | Instagram Agent notification + critical fix | 754f773 | instagram_agent.py, test_instagram_agent.py |
| 3 (RED) | Content Agent failing tests | aed9da5 | test_content_agent.py |
| 3 (GREEN) | Content Agent notification + senior_agent fix | ab00d22 | content_agent.py, senior_agent.py |

## What Was Built

### Twitter Agent (Step 13 in `_run_pipeline()`)
After `logger.info("TwitterAgent run complete...")`, Step 13 fires if `items_queued > 0`:
```
🐦 Twitter Agent — 3 new items ready for review
```

### Instagram Agent (finally block in `run()`)
After `session.commit()` in the finally block, notification fires if `items_queued > 0`:
```
📸 Instagram Agent — 2 new items ready for review
```

Also fixed the broken critical failure alert that was calling the removed `send_whatsapp_template("breaking_news", ...)` — replaced with `send_whatsapp_message("⚠️ Instagram scraper failure — ...")`.

### Content Agent (finally block in `run()`)
After `session.commit()` in the finally block, notification fires if `items_queued > 0`:
```
📰 Content Agent — 4 new items ready for review
```

## Test Results

All 8 new WhatsApp tests pass. All pre-existing tests preserved (59 total across 3 files):

```
tests/test_twitter_agent.py::test_twitter_whatsapp_notification_fires_when_items_queued PASSED
tests/test_twitter_agent.py::test_twitter_whatsapp_notification_skipped_when_no_items PASSED
tests/test_twitter_agent.py::test_twitter_whatsapp_failure_is_non_fatal PASSED
tests/test_instagram_agent.py::test_instagram_whatsapp_notification_fires_when_items_queued PASSED
tests/test_instagram_agent.py::test_instagram_whatsapp_notification_skipped_when_no_items PASSED
tests/test_content_agent.py::test_content_agent_whatsapp_fires_when_items_queued PASSED
tests/test_content_agent.py::test_content_agent_whatsapp_skipped_when_no_items PASSED
tests/test_content_agent.py::test_content_agent_whatsapp_failure_is_non_fatal PASSED
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Apply whatsapp.py rewrite from plan 10-01 (parallel execution)**
- **Found during:** Task 1 RED phase
- **Issue:** `services/whatsapp.py` in this worktree still had old `send_whatsapp_template` / `TEMPLATE_SIDS` API. The 10-01 rewrite existed only in another worktree's commits.
- **Fix:** Applied the 10-01 `whatsapp.py` rewrite (free-form `send_whatsapp_message()` API) from commit `78cd162` in the main repo.
- **Files modified:** `scheduler/services/whatsapp.py`
- **Commit:** 4e4a29b (included with RED test commit)

**2. [Rule 1 - Bug] Fix 2 existing instagram tests broken by whatsapp.py change**
- **Found during:** Task 2 GREEN phase — full test run
- **Issue:** `test_critical_failure_alert` and `test_no_duplicate_alert` patched `services.whatsapp.send_whatsapp_template` which no longer exists
- **Fix:** Updated both tests to patch `services.whatsapp.send_whatsapp_message` with updated message assertions
- **Files modified:** `scheduler/tests/test_instagram_agent.py`
- **Commit:** 754f773

**3. [Rule 3 - Blocking] Fix senior_agent.py broken by whatsapp.py change**
- **Found during:** Task 3 GREEN phase — test_content_agent::test_scheduler_wiring failed because worker imports senior_agent which imports `send_whatsapp_template`
- **Issue:** `senior_agent.py` had a top-level `from services.whatsapp import send_whatsapp_template` import that raised `ImportError`
- **Fix:** Applied the 10-03 plan's `send_whatsapp_message` migration to senior_agent.py — replaced all 4 call sites (breaking_news alert, expiry alert, engagement alert, morning digest) with free-form text messages using `send_whatsapp_message()`
- **Files modified:** `scheduler/agents/senior_agent.py`
- **Commit:** ab00d22

**4. [Rule 3 - Deviation] Instagram notification in `run()` instead of `_run_pipeline()`**
- **Found during:** Task 2 test design
- **Issue:** Plan specified notification at end of `_run_pipeline()`, but tests mock `_run_pipeline` entirely. Code inside mocked method never executes — tests would always fail.
- **Fix:** Placed notification in `run()` finally block (identical to Content Agent pattern), where `agent_run.items_queued` is readable after mocked `_run_pipeline` sets it.
- **Impact:** Functionally identical — notification fires after DraftItems committed in both approaches.

## Known Stubs

None. All notification hooks are fully wired.

## Self-Check: PASSED

All 8 files verified present. All 6 commits verified in git log.
