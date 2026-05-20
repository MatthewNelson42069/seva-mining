#!/usr/bin/env bash
# scripts/verify-anthropic-resolver.sh
# v3.1 Phase 12 KEY-03 — CI grep gate enforcing the per-tenant Anthropic
# resolver contract.
#
# PASS: every AsyncAnthropic(api_key=...) instantiation lives INSIDE
#       scheduler/anthropic_client.py (the resolver) or scheduler/tests/
#       (test files may construct mock instances directly).
# FAIL: any raw AsyncAnthropic(api_key=...) or Anthropic(api_key=...)
#       elsewhere in scheduler/ or backend/.
#
# Mirrors v3.0 Phase 9 scripts/verify-tenant-isolation.sh pattern (TARGETS +
# ALLOWED + grep-strip-empty-line idiom).
#
# Inline-comment exemption escape hatch (D-08):
#   Lines containing the marker '# anthropic-resolver: exempt'
#   are stripped from violations. Use sparingly with a justification
#   comment, e.g.
#       # anthropic-resolver: exempt — pinned to test SDK shim
#
# Comment-line filter:
#   The grep pattern requires the match to be in non-commented code
#   (no leading '#' before the AsyncAnthropic( token on the same line),
#   so historical docstring/comment mentions (e.g. weekly_sweeper.py:24
#   "P6 (Sonnet timeout missing) — AsyncAnthropic(timeout=60.0)") do NOT
#   trip the gate.
set -euo pipefail
cd /Users/matthewnelson/seva-mining

echo "=== KEY-03 Anthropic resolver grep gate ==="

# Scope: scheduler/ (where all current production Anthropic calls live)
# plus backend/ (defensive — backend has zero Anthropic calls today but
# may grow one in the future; the gate prevents accidental drift).
TARGETS=(
  "scheduler"
  "backend"
)

# The resolver module is the ONE allowed production site. Test files
# (scheduler/tests/**) are also exempted because tests legitimately
# construct mock AsyncAnthropic instances for unit testing — including
# tests for the resolver itself (test_anthropic_client.py).
ALLOWED_PREFIXES=(
  "scheduler/anthropic_client.py"
  "scheduler/tests/"
)

# Pattern: match raw AsyncAnthropic( or Anthropic(api_key= instantiation
# syntax, but require non-commented lines (no leading '#' before the
# token on the same line). The '[^#]*' anchor catches lines that start
# with whitespace + production code; the explicit '^[^#]*' rejects lines
# whose first non-whitespace character is '#'.
#
# Anchor walkthrough:
#   ^                start of line
#   [^#]*            zero or more non-'#' chars (so the line is not
#                    a pure comment)
#   (AsyncAnthropic\(|Anthropic\(api_key=)
#                    one of the two raw-instantiation tokens
#
# Lines like '    anthropic_client = AsyncAnthropic(api_key=...)' MATCH.
# Lines like '#   AsyncAnthropic(api_key=...) historical note'         do NOT MATCH.
# Lines like '    # AsyncAnthropic(api_key=...) — see context'         do NOT MATCH
# (because '#' precedes 'AsyncAnthropic' on the same line, and our
# anchor requires zero '#' chars BEFORE the token).
PATTERN='^[^#]*(AsyncAnthropic\(|Anthropic\(api_key=)'

# Scope filters:
#   --include='*.py'        only scan Python source (skip binary .pyc cache
#                           files which would otherwise be matched as binary)
#   --exclude-dir=__pycache__   skip compiled bytecode dirs (defense-in-depth)
#   --exclude-dir=.venv         skip vendored SDK source — anthropic's own
#                               _client.py declares `class AsyncAnthropic(...)`
#                               at line 293 and would otherwise trip the gate
#   --exclude-dir=node_modules  defensive; backend/ has none today
violations=$(grep -rnE \
  --include='*.py' \
  --exclude-dir='__pycache__' \
  --exclude-dir='.venv' \
  --exclude-dir='node_modules' \
  "$PATTERN" "${TARGETS[@]}" 2>/dev/null || true)

# Strip allowed paths (resolver + test files).
filtered="$violations"
for prefix in "${ALLOWED_PREFIXES[@]}"; do
  filtered=$(echo "$filtered" | grep -v "^$prefix" || true)
done

# Strip inline-comment exemption marker lines (D-08 escape hatch).
filtered=$(echo "$filtered" | grep -v 'anthropic-resolver: exempt' || true)

# Drop blank lines left over from the strips.
filtered=$(echo "$filtered" | grep -v '^$' || true)

if [ -n "$filtered" ]; then
  echo ""
  echo "FAIL — raw AsyncAnthropic(...) / Anthropic(api_key=...) found"
  echo "       outside scheduler/anthropic_client.py + scheduler/tests/:"
  echo ""
  echo "$filtered"
  echo ""
  echo "Fix: route the call through scheduler/anthropic_client.py:"
  echo "     from anthropic_client import get_anthropic_client"
  echo "     client = get_anthropic_client('seva', timeout=60.0)   # or 'juno'"
  echo ""
  echo "If this site genuinely cannot route through the resolver (rare),"
  echo "add an inline marker on the same line:"
  echo "     client = AsyncAnthropic(api_key=...)  # anthropic-resolver: exempt — <reason>"
  exit 1
fi

echo "PASS — all Anthropic client instantiations routed through"
echo "       scheduler/anthropic_client.py (per v3.1 Phase 12 KEY-03)."
exit 0
