#!/usr/bin/env bash
# Phase 8 UI-03 — typography weight grep verification.
# PASS: only font-normal / font-medium / font-semibold appear in v2.1 surfaces.
# FAIL: any font-light / font-thin / font-extralight / font-bold / font-extrabold / font-black
#       OR arbitrary-value font-[NNN] notation.
#
# This script enforces 08-UI-SPEC §Typography weight differentiation rule:
#   - Card titles + section headings: weight 600 (font-semibold)
#   - Tab/button labels + <strong>:   weight 500 (font-medium)
#   - Body + lists + muted text:      weight 400 (no class)
#
# Run today: should PASS (no forbidden weights currently shipped).
# Wave 1 / Wave 2 land new code: this script stays the regression guard.
set -euo pipefail
cd /Users/matthewnelson/seva-mining/frontend/src

echo "=== UI-03 weight constraint ==="

# FROZEN-FILE EXCLUSIONS — UI-03 only applies to Phase 8 surfaces. The
# following files are FROZEN per 08-UI-SPEC §Component Inventory §FROZEN files:
#   - components/layout/AppHeader.tsx   (Phase 5 baseline; brand-mark 'S' uses font-bold by design)
#   - components/layout/AppShell.tsx    (Phase 5 baseline)
#   - components/layout/TabNav.tsx      (Phase 5 baseline)
#   - components/layout/Sidebar.tsx     (legacy v2.0; not under TabbedDashboard; D-10 out of v2.1 scope)
#   - pages/DigestPage.tsx              (legacy v2.0; D-10 out of scope)
#   - pages/SettingsPage.tsx            (legacy v2.0; D-10 out of scope)
# These files predate Phase 8 and must NOT be touched in this phase. UI-03 is
# enforced on NEW + MODIFIED Phase 8 surfaces only.
EXCLUDE_PATTERN='components/layout/AppHeader\.tsx|components/layout/AppShell\.tsx|components/layout/TabNav\.tsx|components/layout/Sidebar\.tsx|pages/DigestPage\.tsx|pages/SettingsPage\.tsx'

forbidden=$(grep -rn "font-light\|font-bold\|font-thin\|font-extralight\|font-extrabold\|font-black" \
  components/ pages/ 2>/dev/null \
  | grep -v "__tests__" \
  | grep -v "\.test\." \
  | grep -Ev "$EXCLUDE_PATTERN" \
  || true)
if [ -n "$forbidden" ]; then
  echo "FAIL — forbidden weight utilities found (in non-frozen files):"
  echo "$forbidden"
  exit 1
fi
echo "PASS — no forbidden weight utilities in Phase 8 surfaces"

arbitrary=$(grep -rn "font-\[[0-9]" components/ pages/ 2>/dev/null \
  | grep -v "__tests__" \
  | grep -v "\.test\." \
  | grep -Ev "$EXCLUDE_PATTERN" \
  || true)
if [ -n "$arbitrary" ]; then
  echo "FAIL — arbitrary-value weight classes found (in non-frozen files):"
  echo "$arbitrary"
  exit 1
fi
echo "PASS — no arbitrary-value font-[NNN] notation"
echo ""
echo "=== UI-03 verification PASS ==="
