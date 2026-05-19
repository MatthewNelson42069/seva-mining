#!/usr/bin/env bash
# scripts/verify-tenant-isolation.sh
# Phase 9 TENANT-03 — CI grep gate enforcing the scoped_*() helper contract.
#
# PASS: every select() against a tenant-scoped Model is INSIDE
#       backend/app/queries/scoped.py (or its __init__.py re-export).
# FAIL: any raw select(DailySummary | CalendarItem | WeeklySweep) elsewhere.
#
# Mirrors v2.1 Phase 8 grep verification scripts
# (scripts/verify-ui-04-hover-transitions.sh pattern).
#
# v3.0 Phase 9 Wave 0 (this commit):
#   Pre-existing raw select() call sites in backend/app/routers/{summaries,
#   calendar,weekly_sweeps}.py + scheduler/agents/{daily_summary,
#   weekly_sweeper}.py are TEMPORARILY whitelisted so the gate exits 0 today.
#   Wave 1 lands backend/app/queries/scoped.py (the only legitimate site).
#   Wave 2 refactors the temporary-whitelist sites to call the scoped helpers
#   and REMOVES those entries from PRE_WAVE_2_WHITELIST below. Mid-Wave-2 the
#   gate WILL fail; phase-close must restore EXIT 0.
set -euo pipefail
cd /Users/matthewnelson/seva-mining

echo "=== TENANT-03 scoped helper grep gate ==="

# Scope: backend/app (router + service code) and scheduler/agents (cron code).
# Tests are excluded — they may legitimately construct ad-hoc selects in
# fixtures using .execution_options(skip_tenant_check=True) for negative
# assertions.
TARGETS=(
  "backend/app"
  "scheduler/agents"
)

# The scoped_*() helpers are the ONLY allowed sites for raw select(Model)
# at phase-close. (Wave 1 creates these files.)
ALLOWED=(
  "backend/app/queries/scoped.py"
  "backend/app/queries/__init__.py"
)

# v3.0 Phase 9 Wave 0 temporary whitelist — Wave 2 REMOVES these entries
# after refactoring each call site to use scoped_summaries / scoped_calendar
# / scoped_weekly_sweeps. See 09-01-SUMMARY.md "Deferred Items / TODO" for
# the full list. Each entry MUST be paired with a Wave 2 task that refactors
# that call site and deletes the entry from this array in the same commit.
PRE_WAVE_2_WHITELIST=(
  # v3.0 Phase 9 Wave 2 (09-03-PLAN.md): all 5 entries removed as routers + scheduler
  # agents now route through the canonical scoped helpers
  # (backend/app/queries/scoped.py + scheduler/queries/scoped.py).
  # Wave 2 Task 1: backend/app/routers/{summaries,calendar,weekly_sweeps}.py — REFACTORED.
  # Wave 2 Task 2: scheduler/agents/{daily_summary,weekly_sweeper}.py raw selects — REFACTORED.
)

# Recommended regex from RESEARCH §Code Example 7 Note:
# tightened with [\)\.] to also catch select(DailySummary.col) column-selects.
PATTERN='select\((DailySummary|CalendarItem|WeeklySweep)[\)\.]'

violations=$(grep -rnE "$PATTERN" "${TARGETS[@]}" 2>/dev/null || true)

# Strip allowed paths (scoped helpers) from the result.
filtered="$violations"
for path in "${ALLOWED[@]}"; do
  filtered=$(echo "$filtered" | grep -v "^$path:" || true)
done

# Strip Wave-0 pre-Wave-2 whitelist entries (TODO refactor sites).
for path in "${PRE_WAVE_2_WHITELIST[@]}"; do
  filtered=$(echo "$filtered" | grep -v "^$path:" || true)
done

# After both strips, any remaining lines are real violations.
# Drop blank lines that may have been left over from the strips.
filtered=$(echo "$filtered" | grep -v '^$' || true)

if [ -n "$filtered" ]; then
  echo "FAIL — raw select() against tenant-scoped Model found outside scoped helpers:"
  echo "$filtered"
  echo ""
  echo "Fix: replace with scoped_summaries(company_id) / scoped_calendar(company_id)"
  echo "     / scoped_weekly_sweeps(company_id) from backend/app/queries/scoped.py"
  exit 1
fi

echo "PASS — all tenant-scoped selects routed through queries/scoped.py"
echo "      (Wave 2 complete: PRE_WAVE_2_WHITELIST emptied; all 5 prior raw"
echo "       select() call sites now use scoped_summaries / scoped_calendar /"
echo "       scoped_weekly_sweeps via backend + scheduler helper modules.)"
exit 0
