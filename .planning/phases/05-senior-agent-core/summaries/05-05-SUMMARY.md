---
phase: 05-senior-agent-core
plan: 05
subsystem: scheduler
tags: [morning-digest, daily-digest, whatsapp, tdd, wave-3, senr-06, senr-07, senr-08, what-01, what-05]
dependency_graph:
  requires:
    - scheduler/agents/senior_agent.py (SeniorAgent class with all Wave 1-2 methods from 05-01 through 05-04)
    - scheduler/models/daily_digest.py (DailyDigest model with JSONB columns and whatsapp_sent_at)
    - scheduler/services/whatsapp.py (send_whatsapp_template, morning_digest SID)
    - scheduler/models/draft_item.py (status, decided_at, updated_at, score, rationale, platform, source_account, source_url, expires_at)
    - scheduler/models/agent_run.py (AgentRun for run logging)
    - scheduler/database.py (AsyncSessionLocal)
    - scheduler/tests/test_senior_agent.py (2 Wave-0 morning digest stubs replaced with real tests)
  provides:
    - SeniorAgent._headline_from_rationale() — first-sentence extractor, 100-char truncation
    - SeniorAgent._assemble_digest() — assembles full JSONB digest dict from DB
    - SeniorAgent.run_morning_digest() — job entry point: assembles, writes DailyDigest, sends WhatsApp
  affects:
    - scheduler/tests/test_senior_agent.py (2 stubs replaced; 19 passing, 0 skipped)
tech_stack:
  added:
    - models.daily_digest.DailyDigest (first use in scheduler agent code)
  patterns:
    - from models.daily_digest import DailyDigest — added to senior_agent.py imports
    - from datetime import date — added to distinguish date vs datetime for digest_date and isoformat
    - _headline_from_rationale: split on ". ", take first sentence, ensure trailing period, truncate to 100 chars at word boundary
    - var_2 truncation: join with "; ", truncate at last "; " boundary within 200 chars, append "..."
    - _assemble_digest uses 6 sequential session.execute() calls (approved count, rejected count, expired count, top stories, queue snapshot, priority alert)
    - queue_snapshot["total"] computed as sum of platform values (excluding "total" key itself)
    - AgentRun with try/except/finally pattern per EXEC-04 (errors captured, never re-raised)
key_files:
  created: []
  modified:
    - scheduler/agents/senior_agent.py
    - scheduler/tests/test_senior_agent.py
decisions:
  - _headline_from_rationale split on ". " (period-space) not "." to avoid splitting decimal numbers
  - queue_snapshot total computed in Python after query returns platform rows (not a DB-level SUM)
  - yesterday_approved includes {"items": []} empty list to match DailyDigest JSONB schema comment ("count + top items")
  - var_2 truncation uses rfind("; ") boundary to avoid cutting mid-headline, appends "..." to signal truncation
  - SENR-07 @sevamining own metrics remain deferred (no DailyDigest column exists, X API not live)
metrics:
  duration: ~2 minutes
  completed: 2026-04-02
  tasks_completed: 1
  tasks_total: 1
  files_created: 0
  files_modified: 2
---

# Phase 5 Plan 5: Morning Digest Assembly and WhatsApp Dispatch Summary

**One-liner:** `_assemble_digest` + `run_morning_digest` implement SENR-06/SENR-07/SENR-08/WHAT-01/WHAT-05: queries yesterday's approved/rejected/expired counts, top 5 stories by score, queue snapshot by platform, and priority alert; writes DailyDigest record; sends morning_digest WhatsApp template with 7 variables.

## What Was Done

Implemented the final business logic piece of the Senior Agent as a TDD red-green cycle. The two Wave-0 stub tests (`test_morning_digest_assembly`, `test_morning_digest_whatsapp_send`) were replaced with real implementations, confirmed RED (AttributeError on missing `_assemble_digest`), then GREEN after adding all three methods.

### Task 1: TDD — RED then GREEN (bacb18f)

**RED phase confirmed:** Both new tests raised `AttributeError: 'SeniorAgent' object has no attribute '_assemble_digest'` before implementation.

**scheduler/tests/test_senior_agent.py** — 2 Wave-0 stubs replaced with real implementations:

- `test_morning_digest_assembly`: Mocks 6 sequential `session.execute()` calls (approved count=3, rejected count=1, expired count=2, top stories=[3 items], queue snapshot=[("twitter",3),("instagram",1),("content",1)], priority alert item with score=9.0). Calls `_assemble_digest(session)` directly. Asserts: `top_stories` is a list of 3 items each with `headline/source_account/platform/score/source_url` keys; `queue_snapshot == {"twitter":3,"instagram":1,"content":1,"total":5}`; `yesterday_approved.count==3`, `yesterday_rejected.count==1`, `yesterday_expired.count==2`; `priority_alert` has all required keys and `score==9.0`.

- `test_morning_digest_whatsapp_send`: Patches `_assemble_digest` to return a known digest dict, patches `send_whatsapp_template` as AsyncMock, patches `AsyncSessionLocal`, `AgentRun`, and `_get_config`. Calls `run_morning_digest()`. Asserts: template called once with `"morning_digest"` and 7 variables (`"1"=today_date`, `"2"=headlines_under_200_chars`, `"3"="5"`, `"4"="3"`, `"5"="1"`, `"6"="2"`, `"7"="https://app.sevamining.com"`); a `DailyDigest` object was added to the session; `digest_record.whatsapp_sent_at` is not None.

**scheduler/agents/senior_agent.py** — Imports and methods added:

**New imports:**
- `from datetime import date` (added to existing datetime import line)
- `from models.daily_digest import DailyDigest`

**New static method:**
- `_headline_from_rationale(rationale)`: Splits on `". "`, takes first sentence, ensures trailing period, truncates to 100 chars at word boundary.

**New methods:**
- `_assemble_digest(session)`: Computes yesterday boundaries (UTC midnight). Runs 6 queries: (1) COUNT approved+edited_approved by decided_at range, (2) COUNT rejected by decided_at range, (3) COUNT expired by updated_at range, (4) top 5 DraftItems by score DESC NULLS LAST where created_at >= yesterday_start, (5) platform+count GROUP BY for pending items, (6) highest-scoring pending item. Returns full digest dict with `top_stories`, `queue_snapshot` (including `total`), `yesterday_approved` (with empty `items` list), `yesterday_rejected`, `yesterday_expired`, `priority_alert`.
- `run_morning_digest()`: Opens `AsyncSessionLocal` session, creates `AgentRun(agent_name="morning_digest")`, calls `_assemble_digest`, creates and adds `DailyDigest` record, builds 7 template variables (var_2 truncated to ≤200 chars at "; " boundary), calls `send_whatsapp_template("morning_digest", {...})`, sets `record.whatsapp_sent_at`, commits. try/except/finally error capture pattern per EXEC-04.

**GREEN phase confirmed:** 19 passed, 0 skipped.

## Deviations from Plan

None — plan executed exactly as written.

## Test Results

```
cd /Users/matthewnelson/seva-mining/scheduler && /Users/matthewnelson/.local/bin/uv run pytest tests/test_senior_agent.py -v
tests/test_senior_agent.py::test_jaccard_similarity PASSED
tests/test_senior_agent.py::test_extract_fingerprint_tokens PASSED
tests/test_senior_agent.py::test_dedup_sets_related_id PASSED
tests/test_senior_agent.py::test_dedup_no_match_below_threshold PASSED
tests/test_senior_agent.py::test_queue_cap_accepts_below_cap PASSED
tests/test_senior_agent.py::test_queue_cap_displaces_lowest PASSED
tests/test_senior_agent.py::test_queue_cap_discards_new_item PASSED
tests/test_senior_agent.py::test_queue_cap_tiebreak_expires_at PASSED
tests/test_senior_agent.py::test_expiry_sweep_marks_expired PASSED
tests/test_senior_agent.py::test_breaking_news_alert_fires PASSED
tests/test_senior_agent.py::test_breaking_news_alert_no_fire PASSED
tests/test_senior_agent.py::test_expiry_alert_fires PASSED
tests/test_senior_agent.py::test_expiry_alert_no_double_send PASSED
tests/test_senior_agent.py::test_engagement_alert_watchlist_early PASSED
tests/test_senior_agent.py::test_engagement_alert_watchlist_viral PASSED
tests/test_senior_agent.py::test_engagement_alert_nonwatchlist_viral PASSED
tests/test_senior_agent.py::test_engagement_alert_no_repeat_viral PASSED
tests/test_senior_agent.py::test_morning_digest_assembly PASSED
tests/test_senior_agent.py::test_morning_digest_whatsapp_send PASSED
============================== 19 passed in 0.44s ==============================
```

## Known Stubs

None — all 19 tests are fully implemented and passing. `senior_agent.py` contains no stubs.

## Commits

| Hash | Message |
|------|---------|
| bacb18f | feat(05-05): morning digest assembly and WhatsApp dispatch |
