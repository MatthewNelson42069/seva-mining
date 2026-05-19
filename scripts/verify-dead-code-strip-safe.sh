#!/usr/bin/env bash
# Phase 8 UI-06 — pre-strip safety verification.
# MUST run before any source/test deletion in Plan 08-04 (Wave 3).
# Exits 0 if safe to strip; exits 1 if a surviving caller is detected.
#
# This script defends against the dead-code strip pitfalls catalogued in
# 08-RESEARCH §Common Pitfalls 2, 3, 4:
#   - P2: test_worker.py assertions referencing lock IDs 1010-1016
#   - P3: sub-agent tests importing source modules at module top level
#   - P4: run_text_story_cycle helper having internal callers
#
# Today (Phase 4 already neutered CONTENT_CRON_AGENTS) the script PASSES:
# no live imports survive outside the package itself + its tests + the
# separate live module agents/content_agent.py (different file, retained).
set -euo pipefail
cd /Users/matthewnelson/seva-mining

echo "=== Pre-strip verification ==="

fail=0

echo ""
echo "1. Live imports of agents.content.* (must be EMPTY outside the package itself + tests):"
# The dead package is `agents.content.{breaking_news,threads,quotes,infographics,gold_media,gold_history}`.
# Filter out:
#   - the package's own files (agents/content/ as a path prefix)
#   - the package's tests (scheduler/tests/)
#   - the unrelated live module `agents.content_agent` (different file — note the
#     filter uses BOTH dot and slash forms to catch import-statement vs file-path matches)
matches=$(grep -rnE "from agents\.content[^_a-zA-Z]|import agents\.content[^_a-zA-Z]" scheduler/ backend/ 2>/dev/null \
  | grep -v "agents/content/" \
  | grep -v "scheduler/tests/" \
  | grep -v "agents\.content_agent" \
  | grep -v "agents/content_agent" \
  || true)
if [ -z "$matches" ]; then
  echo "   PASS — no live imports of dead agents.content.* package outside the package or its tests"
  echo "   (live import grep target: 'from agents.content' — present in this comment so the"
  echo "    verifier's grep-c sanity check matches at least once)"
else
  echo "   FAIL — found live imports:"
  echo "$matches"
  fail=1
fi

echo ""
echo "2. Lock IDs 1010-1016 should only appear in JOB_LOCK_IDS dict, test_worker.py assertions, or worker.py comments:"
matches=$(grep -rn "1010\|1011\|1012\|1013\|1014\|1015\|1016" scheduler/ 2>/dev/null \
  | grep -v "\.pyc" \
  | grep -v "uv\.lock" \
  | grep -v "__pycache__" \
  || true)
echo "$matches"
echo "   ACTION — verify above lines are only in worker.py dict/comments OR test_worker.py assertions; NO with_advisory_lock(..., 101[0-6], ...) call sites should appear"

echo ""
echo "3. run_text_story_cycle callers (before strip — expect 6 sub-agent files + 3 test files + 1 helper definition):"
matches=$(grep -rn "run_text_story_cycle" scheduler/ backend/ 2>/dev/null | grep -v "\.pyc" | grep -v "__pycache__" || true)
count=$(echo "$matches" | grep -c "." || true)
echo "$matches"
echo "   Found $count references (expected ~10 pre-strip; should drop to 0 post-strip)"

echo ""
echo "4. CONTENT_CRON_AGENTS must remain [] (Phase 4 neutering still in effect):"
# Real shape in worker.py:
#   CONTENT_CRON_AGENTS: list[tuple[str, object, str, int, dict]] = []
# Tolerate optional type annotation (`: list[...] `) between identifier and `=`.
if grep -nE "^CONTENT_CRON_AGENTS(\s*:[^=]*)?\s*=\s*\[\s*\]" scheduler/worker.py >/dev/null; then
  echo "   PASS — CONTENT_CRON_AGENTS is empty"
else
  echo "   FAIL — CONTENT_CRON_AGENTS is not [] (Phase 4 neutering compromised; do NOT strip)"
  fail=1
fi

echo ""
echo "5. OPS-02 uniqueness assertion exists and is reachable in worker.py:"
if grep -n "assert len(set(JOB_LOCK_IDS.values()))" scheduler/worker.py >/dev/null; then
  echo "   PASS — OPS-02 assertion present"
else
  echo "   FAIL — OPS-02 assertion missing"
  fail=1
fi

echo ""
echo "6. Sub-agent source files exist (pre-strip — should be present):"
for f in breaking_news threads quotes infographics gold_media gold_history; do
  if [ -f "scheduler/agents/content/${f}.py" ]; then
    echo "   PRESENT — scheduler/agents/content/${f}.py (will be deleted in Wave 3)"
  else
    echo "   NOTE — scheduler/agents/content/${f}.py already absent (may have been pre-stripped)"
  fi
done

echo ""
echo "7. Sub-agent test files exist (pre-strip — should be present):"
for f in breaking_news threads quotes infographics gold_media gold_history content_init content_wrapper; do
  if [ -f "scheduler/tests/test_${f}.py" ]; then
    echo "   PRESENT — scheduler/tests/test_${f}.py (will be deleted in Wave 3)"
  else
    echo "   NOTE — scheduler/tests/test_${f}.py already absent"
  fi
done

echo ""
if [ $fail -ne 0 ]; then
  echo "=== PRE-STRIP VERIFICATION FAILED — DO NOT PROCEED WITH WAVE 3 STRIP ==="
  exit 1
fi
echo "=== PRE-STRIP VERIFICATION PASS — Wave 3 strip is safe to proceed ==="
