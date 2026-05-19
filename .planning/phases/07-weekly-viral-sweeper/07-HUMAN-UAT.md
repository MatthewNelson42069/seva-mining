---
status: partial
phase: 07-weekly-viral-sweeper
source: [07-VERIFICATION.md]
started: "2026-05-19T06:16:20Z"
updated: "2026-05-19T06:16:20Z"
---

## Current Test

[awaiting human testing — both items gated on first weekly_sweeps DB row]

## Tests

### 1. Populated SweeperCard renders with real data after first sweep produces a row

expected: After triggering `python -m agents.weekly_sweeper` from a Railway shell (or after the first Sunday 08:00 PT cron fire), reload `/viral`. Title row shows `Weekly Sweep — {start_date} – {end_date}`. No status badge when `status='completed'`. Three react-markdown sections render: `Top X Posts This Week` (10 entries with @handle + engagement), `Most Cross-Referenced Stories` (up to 5), `3 Content Angles` (3 angle blocks OR fallback copy `Insufficient signal this week — angles not generated` if signal was sparse). No console errors. No raw `### Angle 1` markdown leakage. Week-picker dropdown hidden when only 1 row exists. Running the sweeper a second time within 60 min logs `idempotency_skip` and DB row count stays at 1.

result: [pending]

### 2. Status banner colors render correctly for partial and failed rows

expected: Manually `UPDATE weekly_sweeps SET status='partial'` and reload `/viral` → amber banner with copy `Sweeper had partial output — some sections may be empty`. `UPDATE` to `status='failed'` → red banner with copy `Sweeper failed last run — see telemetry`. Reset to `'completed'` when done → no banner rendered. Vitest already asserts the copy strings (3 of 9 spec tests); the human check is purely visual color/layout delivery.

result: [pending]

## Summary

total: 2
passed: 0
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps
