#!/usr/bin/env bash
# Phase 8 UI-04 — hover transition coverage.
# PASS: every card-class component has border baseline + hover:border-zinc-700 + transition-colors.
#
# Targets are the three card-class components in v2.1:
#   - summary/SummaryCard.tsx
#   - viral/SweeperCard.tsx
#   - calendar/DayCell.tsx
#
# Expected state at Wave 0 commit: FAIL — SummaryCard.tsx + SweeperCard.tsx do
# not yet carry `hover:border-zinc-700 transition-colors` (only DayCell.tsx does).
# Wave 1 makes this script PASS by adding those classes.
set -euo pipefail
cd /Users/matthewnelson/seva-mining/frontend/src/components

echo "=== UI-04 hover transition coverage ==="

targets=(
  "summary/SummaryCard.tsx"
  "viral/SweeperCard.tsx"
  "calendar/DayCell.tsx"
)

fail=0
for f in "${targets[@]}"; do
  missing=""
  grep -q "hover:border-zinc-700" "$f" || missing="$missing hover:border-zinc-700"
  grep -q "transition-colors" "$f"    || missing="$missing transition-colors"
  grep -qE "border-zinc-800|'border'|\"border\"|border\b" "$f" || missing="$missing border-baseline"
  if [ -n "$missing" ]; then
    echo "FAIL — $f missing:$missing"
    fail=1
  else
    echo "PASS — $f has border baseline + hover:border-zinc-700 + transition-colors"
  fi
done

[ $fail -ne 0 ] && exit 1
echo ""
echo "=== UI-04 verification PASS ==="
