#!/usr/bin/env bash
# Phase 8 UI-02 — spacing density verification.
# PASS: SummaryCard / SweeperCard contain p-6+ padding and inter-section rhythm
#       (space-y-{4,5,6} or gap-{4,5,6}).
# PASS: SectionBlock has bullet-rhythm signal (prose-sm or space-y-4).
#
# This enforces 08-UI-SPEC §Spacing Scale "Layout-level spacing contract":
#   - Card interior: p-6 + space-y-6
#   - Inter-section in card: space-y-5
#   - Markdown bullets: space-y-4 (via prose-sm)
set -euo pipefail
cd /Users/matthewnelson/seva-mining/frontend/src/components

echo "=== UI-02 spacing token verification ==="
fail=0

for f in summary/SummaryCard.tsx viral/SweeperCard.tsx; do
  if ! grep -qE "p-6|p-8" "$f"; then
    echo "FAIL — $f has no p-6 or p-8 padding"
    fail=1
  else
    echo "PASS — $f uses p-6+ card interior"
  fi
done

for f in summary/SummaryCard.tsx viral/SweeperCard.tsx; do
  if ! grep -qE "space-y-4|space-y-5|space-y-6|gap-4|gap-5|gap-6" "$f"; then
    echo "FAIL — $f missing inter-section vertical rhythm"
    fail=1
  else
    echo "PASS — $f has inter-section rhythm"
  fi
done

if ! grep -qE "space-y-4|prose-sm" summary/SectionBlock.tsx; then
  echo "FAIL — summary/SectionBlock.tsx missing space-y-4 or prose-sm"
  fail=1
else
  echo "PASS — summary/SectionBlock.tsx has bullet rhythm"
fi

[ $fail -ne 0 ] && exit 1
echo ""
echo "=== UI-02 verification PASS ==="
