---
phase: quick-260420-p8h
plan: 01
subsystem: scheduler
tags: [env-validation, logging, market-data, startup-diagnostics]
dependency_graph:
  requires: [quick-260420-oa1]
  provides: [OPS-ENV-STATUS]
  affects: [scheduler/worker.py]
tech_stack:
  added: []
  patterns: [WARNING-level degraded-but-functional logging category]
key_files:
  created: []
  modified:
    - scheduler/worker.py
decisions:
  - "market_data uses WARNING (not INFO) for missing keys — INFO would be misleading since absence degrades drafter output (falls back to [UNAVAILABLE] language); ERROR would imply worker is broken; WARNING correctly signals degraded-but-functional state"
  - "New category (not extending optional) — existing optional loop logs at INFO with '(optional)' suffix which would misrepresent the market data keys whose absence has visible content quality impact"
metrics:
  duration: "< 5 min"
  completed: "2026-04-20"
  tasks: 1
  files: 1
---

# Quick Task 260420-p8h Summary

**One-liner:** Added `market_data` env-key status block to `_validate_env()` — FRED + METALPRICEAPI log INFO (SET) or WARNING (MISSING) at scheduler startup so Railway logs confirm key provisioning.

## What Was Done

Extended `scheduler/worker.py::_validate_env()` with a third env key category (`market_data`) appended after the existing `optional` block. At startup the scheduler now logs one status line per market API key:

- `INFO  ENV FRED_API_KEY: SET ✓` when key is present
- `WARNING ENV FRED_API_KEY: MISSING — drafter will fall back to [UNAVAILABLE] for this source` when absent
- Same shape for `METALPRICEAPI_API_KEY`

This gives the operator immediate Railway log confirmation that both keys provisioned in quick-260420-oa1 are wired correctly, without having to wait for a content-agent cron run and check draft output.

## Verification Results

```
ruff check scheduler/worker.py  →  All checks passed!

_validate_env() output (local — keys absent from local .env as expected):
  ERROR  ENV ANTHROPIC_API_KEY: MISSING — agents will fail without this key
  INFO   ENV X_API_BEARER_TOKEN: SET ✓
  INFO   ENV DATABASE_URL: SET ✓
  INFO   ENV SERPAPI_API_KEY: not set (optional)
  INFO   ENV TWILIO_ACCOUNT_SID: not set (optional)
  WARNING ENV FRED_API_KEY: MISSING — drafter will fall back to [UNAVAILABLE] for this source
  WARNING ENV METALPRICEAPI_API_KEY: MISSING — drafter will fall back to [UNAVAILABLE] for this source
```

All 5 pre-existing ENV lines are unchanged. Both new lines appear at WARNING level with the correct message.

On Railway (where keys are provisioned), the two lines will appear as INFO `SET ✓`.

## Commit

| Hash | Message |
|------|---------|
| `352b2d4` | feat(quick-260420-p8h): add FRED + METALPRICEAPI env key status to _validate_env() |

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.

## Self-Check: PASSED

- `scheduler/worker.py` modified — confirmed present
- Commit `352b2d4` exists on main branch
- ruff clean — confirmed
- Both new ENV log lines output — confirmed
