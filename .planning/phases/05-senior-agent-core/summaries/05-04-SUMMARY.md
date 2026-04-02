---
phase: 05-senior-agent-core
plan: 04
subsystem: scheduler
tags: [expiry-sweep, breaking-news-alert, expiry-alert, engagement-alert, tdd, wave-2, whatsapp]
dependency_graph:
  requires:
    - scheduler/agents/senior_agent.py (SeniorAgent class with process_new_item, _enforce_queue_cap from 05-03)
    - scheduler/services/whatsapp.py (send_whatsapp_template, TEMPLATE_SIDS)
    - scheduler/models/draft_item.py (engagement_snapshot, engagement_alert_level, alerted_expiry_at, score, expires_at)
    - scheduler/models/watchlist.py (Watchlist.account_handle, Watchlist.platform, Watchlist.active)
    - scheduler/models/agent_run.py (AgentRun for sweep run logging)
    - scheduler/database.py (AsyncSessionLocal)
    - scheduler/tests/test_senior_agent.py (9 Wave-2 stubs replaced with real tests)
  provides:
    - SeniorAgent.run_expiry_sweep() — 30-min sweep job entry point
    - SeniorAgent._check_breaking_news_alert() — score >= 8.5 once-per-item WhatsApp alert
    - SeniorAgent._check_expiry_alerts() — score >= 7.0, within 60 min, alerted_expiry_at dedup
    - SeniorAgent._send_engagement_alert() — breaking_news template with composite engagement score
    - SeniorAgent._check_engagement_alerts() — watchlist 2-tier + non-watchlist viral alerts
  affects:
    - scheduler/tests/test_senior_agent.py (9 stubs replaced; 17 passing, 2 morning-digest stubs remain)
tech_stack:
  added: []
  patterns:
    - send_whatsapp_template imported at module level — patch target is agents.senior_agent.send_whatsapp_template
    - Watchlist.account_handle (not username) — lstrip("@").lower() normalisation for handle matching
    - engagement_alert_level dedup — null→watchlist→viral one-way state machine; viral items excluded from candidates query via or_(is_null, =="watchlist")
    - alerted_expiry_at dedup — IS NULL filter in expiry alert query prevents double-send
    - Composite engagement score: likes*1 + retweets*2 + replies*1.5 in template variable {{3}}
    - AgentRun with try/except/finally pattern per EXEC-04 (errors captured, never re-raised)
key_files:
  created: []
  modified:
    - scheduler/agents/senior_agent.py
    - scheduler/tests/test_senior_agent.py
decisions:
  - _check_breaking_news_alert now fully implemented replacing the Plan 03 pass-body stub
  - Engagement alert dedup uses engagement_alert_level column as a one-way state machine (null -> watchlist -> viral); the query explicitly excludes viral items so they never appear as candidates
  - Watchlist handle normalisation strips leading @ and lowercases before set membership test — handles both "@KitcoNews" DB values and "@kitconews" comparisons
  - _send_engagement_alert uses breaking_news template (not a dedicated engagement template) per context decisions
  - run_expiry_sweep does NOT call _check_breaking_news_alert — that method is called by process_new_item at item intake time, not during the sweep
metrics:
  duration: ~20 minutes
  completed: 2026-04-02
  tasks_completed: 1
  tasks_total: 1
  files_created: 0
  files_modified: 2
---

# Phase 5 Plan 4: Expiry Sweep, Breaking News Alerts, Expiry Alerts, Engagement Alerts Summary

**One-liner:** `run_expiry_sweep` with `_check_expiry_alerts` and `_check_engagement_alerts` (watchlist 2-tier + non-watchlist viral); `_check_breaking_news_alert` fully replaces Plan 03 stub; all 9 sweep/alert tests pass via TDD red-green cycle.

## What Was Done

Implemented SENR-05, SENR-09, WHAT-02, WHAT-03, and WHAT-05 as a TDD cycle. Tests were confirmed RED (AttributeError on missing `send_whatsapp_template` attribute), then GREEN after adding all implementations.

### Task 1: TDD — RED then GREEN (0489749)

**RED phase confirmed:** Running the 9 new test implementations against the pre-implementation `senior_agent.py` raised `AttributeError: <module 'agents.senior_agent'> does not have the attribute 'send_whatsapp_template'` — tests were properly failing.

**scheduler/tests/test_senior_agent.py** — 9 stubs replaced with real implementations:

- `test_expiry_sweep_marks_expired`: mocks `AsyncSessionLocal` context + `AgentRun`; calls `run_expiry_sweep()`; asserts `execute()` was called and `run.status == "completed"`.
- `test_breaking_news_alert_fires`: item with `score=9.0`, `rationale="Gold hits all-time high..."`, calls `_check_breaking_news_alert`; asserts `send_whatsapp_template` called with `"breaking_news"` template and correct variables (headline = first sentence, score "9.0", dashboard URL).
- `test_breaking_news_alert_no_fire`: item with `score=7.5`; asserts `send_whatsapp_template` never called.
- `test_expiry_alert_fires`: item with `score=8.0`, `expires_at=now+30min`, `alerted_expiry_at=None`; calls `_check_expiry_alerts`; asserts template called with `"expiry_alert"` and `item.alerted_expiry_at` is now set.
- `test_expiry_alert_no_double_send`: query returns empty list (simulating `alerted_expiry_at IS NULL` filter excluding already-alerted item); asserts no send.
- `test_engagement_alert_watchlist_early`: watchlist item with 60 likes / 6000 views, `engagement_alert_level=None`; asserts `breaking_news` template called; `item.engagement_alert_level == "watchlist"`.
- `test_engagement_alert_watchlist_viral`: watchlist item with 600 likes / 50000 views, current level `"watchlist"`; asserts send and `item.engagement_alert_level == "viral"`.
- `test_engagement_alert_nonwatchlist_viral`: `@RandomUser` (not in watchlist), 600 likes / 50000 views, level `None`; asserts send and `item.engagement_alert_level == "viral"`.
- `test_engagement_alert_no_repeat_viral`: item with `engagement_alert_level="viral"`; candidates query returns empty; asserts no send.

**scheduler/agents/senior_agent.py** — Imports and methods added:

**New imports:**
- `from models.watchlist import Watchlist`
- `from services.whatsapp import send_whatsapp_template`
- `or_` added to `sqlalchemy` import

**Plan 03 stub replaced:**
- `_check_breaking_news_alert(session, item_id)`: reads `senior_breaking_news_threshold` (default `"8.5"`); if `float(item.score) >= threshold`, extracts first sentence of rationale as headline, reads `dashboard_url`, sends `breaking_news` template with `{1: headline, 2: source_account, 3: score_str, 4: dashboard_url}`; wraps in try/except.

**New methods:**
- `_check_expiry_alerts(session)`: reads score threshold (default `"7.0"`) and window (default `"60"` min); queries `pending` items with score >= threshold, `expires_at` within window, `alerted_expiry_at IS NULL`; sends `expiry_alert` template per candidate; sets `item.alerted_expiry_at`.
- `_send_engagement_alert(item, dashboard_url)`: truncates `source_text` to ~100 chars at word boundary; computes composite engagement score; sends `breaking_news` template.
- `_check_engagement_alerts(session)`: loads watchlist handles from `Watchlist.account_handle`; queries pending twitter candidates where `engagement_alert_level` is null or "watchlist"; applies watchlist 2-tier logic (50/5k → watchlist, 500/40k → viral) or non-watchlist 1-tier (500/40k → viral).
- `run_expiry_sweep()`: opens session, creates AgentRun, runs bulk UPDATE to expire stale items, calls `_check_expiry_alerts`, calls `_check_engagement_alerts`, commits; try/except/finally pattern.

**GREEN phase confirmed:** 17 passed, 2 skipped (morning digest stubs remain for Wave 3).

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
tests/test_senior_agent.py::test_morning_digest_assembly SKIPPED (Wave 0 stub...)
tests/test_senior_agent.py::test_morning_digest_whatsapp_send SKIPPED (Wave 0 stub...)
======================== 17 passed, 2 skipped in 0.30s =========================
```

## Known Stubs

- `test_morning_digest_assembly` — Wave 0 stub, implementation in Wave 3 (Plan 05).
- `test_morning_digest_whatsapp_send` — Wave 0 stub, implementation in Wave 3 (Plan 05).

No stubs in `senior_agent.py` itself — all five Plan 04 methods are fully implemented.

## Commits

| Hash | Message |
|------|---------|
| 0489749 | feat(05-04): expiry sweep with breaking news, expiry, and engagement alerts |

## Self-Check: PASSED
