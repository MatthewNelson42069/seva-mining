---
phase: 01-gold-news-card-web-feed
plan: "03"
subsystem: scheduler/whatsapp
tags: [whatsapp, delivery, config, simulate-mode, WHA-01, WHA-02, WHA-03, HIGH-5, MOD-6]
dependency_graph:
  requires:
    - scheduler/services/whatsapp.py (existing send_whatsapp_message)
    - scheduler/config.py (existing Settings class)
    - backend/app/config.py (existing Settings class)
  provides:
    - build_summary_teaser(period_label, lead, feed_url) -> str
    - build_summary_failure_alert(period_label, failed_sections, agent_run_id) -> str
    - deliver_summary_teaser(period_label, lead) -> str | None
    - deliver_summary_failure_alert(period_label, failed_sections, agent_run_id) -> None
    - WHATSAPP_DELIVERY_ENABLED env var gate (both configs)
    - FEED_BASE_URL env var (both configs)
  affects:
    - Plan 05 (scheduler agent imports deliver_summary_teaser + deliver_summary_failure_alert)
    - Plan 04 (backend router inherits env-var parity from backend/app/config.py)
tech_stack:
  added: []
  patterns:
    - simulate-mode env gate (mirrors X_POSTING_ENABLED pattern from quick-260424-l0d)
    - char-budget assert at write time (WHA-03)
    - isolated try/except for failure-alert path (MOD-6)
key_files:
  created: []
  modified:
    - scheduler/config.py
    - backend/app/config.py
    - scheduler/services/whatsapp.py
    - scheduler/tests/test_whatsapp.py
decisions:
  - WHATSAPP_DELIVERY_ENABLED defaults to false (safe first-deploy posture)
  - FEED_BASE_URL defaults to https://seva-mining-smm.vercel.app (no env needed in dev)
  - deliver_summary_failure_alert ALWAYS attempts send, independent of gate (WHA-02)
  - MOD-6 catch-all wraps failure-alert send so Twilio outage cannot cascade
  - HIGH-5: build_chunks() never called in daily_summary path (teaser-only pattern)
metrics:
  duration_seconds: 183
  completed_date: "2026-05-06"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 4
---

# Phase 1 Plan 03: WhatsApp Daily Summary Delivery Surface Summary

**One-liner:** WhatsApp teaser + failure-alert helpers with 400-char budget enforcement and simulate-mode gate wired to dual-config env vars.

## What Was Built

### Env Vars Added (WHA-01 — dual-config parity)

Both `scheduler/config.py` AND `backend/app/config.py` now declare:

```python
whatsapp_delivery_enabled: bool = False
feed_base_url: str = "https://seva-mining-smm.vercel.app"
```

Identical declarations in both files as required by the parity constraint. Existing fields (database_url, twilio_*, x_posting_enabled) untouched.

### 4 New Helpers in scheduler/services/whatsapp.py

**`build_summary_teaser(period_label, lead, feed_url) -> str`** (WHA-03)
- Format: `📊 Summary {period_label}: {lead}. Read full → {feed_url}`
- Lead is truncated to fit within 400-char budget with "…" ellipsis
- `assert len(teaser) < SUMMARY_TEASER_MAX_CHARS` fires at write time — regression guard

**`build_summary_failure_alert(period_label, failed_sections, agent_run_id) -> str`** (WHA-02)
- Format: `⚠️ Summary {period_label} FAILED: section(s) {sections}. agent_run_id: {short_id}`
- `agent_run_id` truncated to 8 chars; empty `failed_sections` falls back to `"all"`
- Defensive truncation + assert if section list is abnormally long

**`deliver_summary_teaser(period_label, lead) -> str | None`** (WHA-01 gate)
- Checks `settings.whatsapp_delivery_enabled`
- When False: logs teaser body + length at INFO, returns None (simulate mode)
- When True: calls `send_whatsapp_message(teaser)`, returns SID
- NEVER calls `build_chunks()` (HIGH-5 mitigation)

**`deliver_summary_failure_alert(period_label, failed_sections, agent_run_id) -> None`** (WHA-02 + MOD-6)
- Ignores `whatsapp_delivery_enabled` — failure alerts are critical signal, always sent
- Entire send wrapped in `except Exception as alert_exc` that NEVER re-raises
- Twilio outage during cron failure logs the secondary failure without cascading

### Tests (8 new, 204 total)

All in `scheduler/tests/test_whatsapp.py`:

1. `test_build_summary_teaser_basic_format` — format + char budget
2. `test_build_summary_teaser_truncates_long_lead` — WHA-03 500-char overflow
3. `test_build_summary_failure_alert_basic_format` — emoji + FAILED + truncated ID
4. `test_build_summary_failure_alert_empty_sections_says_all` — empty sections fallback
5. `test_deliver_summary_teaser_simulate_off_does_not_call_twilio` — gate=false → no Twilio call
6. `test_deliver_summary_teaser_enabled_calls_twilio` — gate=true → send_whatsapp_message called once
7. `test_deliver_summary_failure_alert_always_calls_send` — gate=false still sends alert
8. `test_deliver_summary_failure_alert_swallows_twilio_exception` — MOD-6 no re-raise

## Implementation Locations

| Requirement | File | Implementation |
|-------------|------|----------------|
| WHA-01 (env gate) | scheduler/config.py + backend/app/config.py | `whatsapp_delivery_enabled: bool = False` |
| WHA-02 (failure alert) | scheduler/services/whatsapp.py | `deliver_summary_failure_alert()` with own try/except |
| WHA-03 (char budget) | scheduler/services/whatsapp.py | `SUMMARY_TEASER_MAX_CHARS = 400` + `assert len(teaser) < ...` |
| HIGH-5 mitigation | scheduler/services/whatsapp.py | No `build_chunks()` call in any deliver_summary_* function |
| MOD-6 mitigation | scheduler/services/whatsapp.py | `except Exception as alert_exc: # noqa: BLE001 — MOD-6: NEVER re-raise` |

## Deviations from Plan

**1. [Rule 1 - Bug] Ruff E402 — mid-file imports in test block**
- **Found during:** Task 2 post-commit ruff check
- **Issue:** The plan's provided test snippet included `import pytest` and `from unittest.mock import AsyncMock, patch` mid-file, causing ruff E402 (module-level import not at top) and F811 (redefinition of `patch`)
- **Fix:** Moved `AsyncMock` into the existing top-of-file import on line 21; moved `from services.whatsapp import (...)` block to after env setup at the top of the test file; removed the duplicate mid-file import block
- **Files modified:** scheduler/tests/test_whatsapp.py
- **Result:** `ruff check .` passes clean; all 20 tests still pass

## Known Stubs

None — all 4 helpers are fully functional. `deliver_summary_teaser` and `deliver_summary_failure_alert` are ready for Plan 05 (scheduler agent) to import and call.

## Self-Check: PASSED

Files created/modified exist:
- scheduler/config.py: FOUND
- backend/app/config.py: FOUND
- scheduler/services/whatsapp.py: FOUND
- scheduler/tests/test_whatsapp.py: FOUND

Commits exist:
- 4e12489: feat(01-03): add WHATSAPP_DELIVERY_ENABLED + FEED_BASE_URL to both config.py files
- c73d2f9: feat(01-03): add 4 daily_summary helpers to whatsapp.py + 8 tests
