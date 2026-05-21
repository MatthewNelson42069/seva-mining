---
phase: 16-v3.1-audit-cleanup-bundle
plan: 05
subsystem: ui
tags: [react, tenant-aware-copy, empty-state, juno, cleanup, frontend]

# BINDING for plan-checker / downstream verifier (INFO #2 fix)
clean05_approach: rewrite

# Dependency graph
requires:
  - phase: 10-juno-defence-news-funnel
    provides: "DEF-01..10 production cron (defence-news daily) — semantically established that Phase 10 IS shipped, making 'Coming in Phase 10' dead-text"
  - phase: 12-per-tenant-anthropic-api-key
    provides: "Per-tenant Anthropic key wiring shipped 2026-05-20; Juno cron now production-flipped (JUNO_CRON_ENABLED=true) — confirms cron IS live, not 'not yet enabled'"
provides:
  - "Tenant-aware Juno empty-state copy referencing real cron schedule (08:05/12:05 PT America/Los_Angeles)"
  - "Closure of integration-checker Flow A step 4 PARTIAL finding from v3.1 milestone audit"
  - "Removal of stale Phase-9-era dead-text (`Coming in Phase 10 — Defence-sector ingestion not yet enabled`)"
affects: [v3.1-archive, audit-cleanup, juno-frontend, tenant-empty-states]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Tenant-aware empty-state copy via literal string in companyId branch (not registry lookup — simpler than extending nextCronFireLabelPT() helper for a single line)"
    - "Provenance comment cites plan ID (CLEAN-05) for future audits"

key-files:
  created: []
  modified:
    - "frontend/src/pages/SummaryFeedPage.tsx — lines 63-76: Juno empty-state block rewritten (was: stale 'Coming in Phase 10' copy; now: tenant-aware copy referencing real cron schedule 08:05/12:05 PT)"

key-decisions:
  - "Chose REWRITE approach (default per plan) over DELETE (fallback) — test file does not assert on the stale string, so no test-friction signal forced fallback"
  - "Used literal string for cron times (08:05/12:05 PT) rather than extending nextCronFireLabelPT() helper — the helper is hardcoded to Seva's 08:00/12:00 PT and extending it for one empty-state line was over-engineering"
  - "Kept the companyId === 'juno' branch (preserves tenant-aware UX shape) rather than collapsing both tenants to shared copy"

patterns-established:
  - "When a tenant-specific empty-state references a cron schedule, cite the schedule literally in copy (operator-actionable transparency)"
  - "Stale dead-text from prior milestones is replaced with provenance-commented current-truth, not commented out"

requirements-completed: [CLEAN-05]

# Metrics
duration: 4min
completed: 2026-05-20
---

# Phase 16 Plan 05: CLEAN-05 — Stale Phase-9-era Empty-State Copy Replaced Summary

**Replaced dead-text `Coming in Phase 10 — Defence-sector ingestion not yet enabled` with tenant-aware Juno empty-state copy referencing the real production cron schedule (08:05/12:05 PT America/Los_Angeles)**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-05-20T19:42:30Z
- **Completed:** 2026-05-20T19:45:00Z
- **Tasks:** 1 (single-task plan)
- **Files modified:** 1

## Accomplishments

- Stale Phase-9-era empty-state copy ("Coming in Phase 10 — Defence-sector ingestion not yet enabled") REMOVED from `frontend/src/pages/SummaryFeedPage.tsx` — grep across `frontend/src/` returns 0 for both stale phrases
- Replacement copy is tenant-aware AND operator-actionable, citing the actual cron fire times (Juno: 08:05/12:05 PT America/Los_Angeles) — distinct from Seva's 08:00/12:00 PT slot
- Provenance comment cites Phase 16 (CLEAN-05) for future audit trails — explains WHY the old copy was wrong (Phase 10 shipped 2026-05-19, Phase 12 cron flipped 2026-05-20)
- D-10 regression baseline EXACTLY preserved: frontend test suite 31/31 files, 181/181 tests pass (audit baseline was 181)
- TypeScript clean: `npx tsc --noEmit` exits 0
- Integration-checker Flow A step 4 PARTIAL finding from v3.1 milestone audit CLOSED

## Approach Taken: REWRITE (default)

The plan offered two approved paths:
- **DEFAULT — rewrite tenant-aware (recommended):** preserve the Juno-specific branch, refresh copy to reflect live cron with concrete schedule
- **FALLBACK — delete the block entirely:** collapse to shared `nextCronFireLabelPT()` path; loses Juno-specific cron-time precision

**Chose REWRITE because:**
1. The test file at `frontend/src/pages/__tests__/SummaryFeedPage.test.tsx` does NOT assert on the stale strings ("Coming in Phase 10" / "Defence-sector ingestion") — confirmed via baseline grep before edit and baseline test run (5/5 SummaryFeedPage tests pass pre-edit). No test-friction signal forced the fallback.
2. Tenant-aware UX shape is more thoughtful — Juno's 08:05/12:05 PT cron schedule differs from Seva's 08:00/12:00 PT, so collapsing to the shared `nextCronFireLabelPT()` helper would display a 5-minute-early time for Juno (acceptable but suboptimal).
3. Operator transparency: the new copy tells the user exactly when the next cron will fire — actionable, not vague.

## Verbatim New String

The exact new copy line as it appears in `frontend/src/pages/SummaryFeedPage.tsx` line 72:

```
No defence-industry briefs for this window yet — Juno's daily cron fires at 08:05 and 12:05 PT America/Los_Angeles.
```

Provenance comment (lines 64-68):

```
// v3.1 Phase 16 (CLEAN-05) — Juno daily cron is live (Phase 10 shipped 2026-05-19,
// Phase 12 per-tenant key wiring shipped 2026-05-20). Crons fire at 08:05 PT and
// 12:05 PT America/Los_Angeles. This branch renders when the cron has not yet
// produced a row for the current 60-day window (e.g., first-deploy backfill gap,
// or a stretch where every defence-news fire returned empty-after-classifier).
```

## Stale-String Grep Counts (final state)

| String | Count in `frontend/src/` |
|--------|--------------------------|
| `Coming in Phase 10` | **0** (was: 1) |
| `Defence-sector ingestion not yet enabled` | **0** (was: 1) |
| `No defence-industry briefs for this window yet` | 1 (new copy present) |
| `08:05 and 12:05 PT` | 1 (cron schedule referenced) |
| `CLEAN-05` | 1 (provenance comment present) |

## Frontend Test Pass Count

| Stage | Files | Tests |
|-------|-------|-------|
| Baseline (pre-edit, audit) | 31 | 181 |
| Post-edit (final) | 31 | 181 |

D-10 regression baseline EXACTLY preserved (181 → 181; gate was ≥181).

## TypeScript Clean

`cd /Users/matthewnelson/seva-mining/frontend && npx tsc --noEmit` exits 0 — no new type errors.

## Test File Edits

**None.** The test file `frontend/src/pages/__tests__/SummaryFeedPage.test.tsx` was NOT touched by this plan. Confirmed via baseline read: the file's assertions target only the Seva branch (`/Waiting for first summary\. Next fire at /` and `/Next fire at (08:00|12:00) PT/`), loading state, error state, and SummaryCard rendering. No assertion references "Coming in Phase 10" or "Defence-sector ingestion" or any Juno-specific empty-state string.

Plan 16-01 (CLEAN-01 ESLint cleanup, parallel Wave 1) may have separately touched this test file for mechanical type-narrowing on unrelated lines — that is its scope, not this plan's.

## Task Commits

1. **Task 1: CLEAN-05 — Replace stale Phase-9-era empty-state copy in SummaryFeedPage.tsx** — bundled into commit `5fc45f0` due to parallel-executor git-staging race condition (see Deviations section below)

**Plan metadata commit (this SUMMARY + state files):** pending — will be created as final commit in this plan.

## Decisions Made

- **Approach: rewrite (not delete)** — test file does not assert on stale strings, so no test-friction signal forced the fallback
- **Literal cron times in copy** instead of extending `nextCronFireLabelPT()` helper — over-engineering for a single empty-state line
- **Kept Juno branch** instead of collapsing tenants — preserves tenant-aware UX shape per default approach

## Deviations from Plan

### 1. [Rule 3 - Blocking / Parallel-Execution Race] Frontend edit absorbed into 16-04's commit

- **Found during:** Task 1 commit step
- **Issue:** This plan ran as a parallel Wave 1 executor alongside 16-01/02/03/04 in the same git working tree. My `git add frontend/src/pages/SummaryFeedPage.tsx` staged the file successfully, but before my dedicated `git commit` could complete, Plan 16-04's executor (concurrently working on `scheduler/tests/agents/test_daily_summary_prune.py`) created commit `5fc45f0` which absorbed my already-staged frontend file. Result: my CLEAN-05 frontend edit physically landed in commit `5fc45f0` ("fix(16-04): resolve 4 RuntimeWarnings in test_daily_summary_prune.py (CLEAN-04)"), bundled with 16-04's scheduler-test edit.
- **Fix:** None code-side — the edit IS committed correctly to disk (verified via `git blame -L 60,80 frontend/src/pages/SummaryFeedPage.tsx` showing lines 64-68 and 72 attributed to commit `5fc45f05`). The only loss is commit-message attribution: 16-04's commit message does not mention the SummaryFeedPage change, and there's no separate atomic CLEAN-05 commit. This SUMMARY.md documents the situation for the verifier.
- **Files modified:** `frontend/src/pages/SummaryFeedPage.tsx` (committed as part of `5fc45f0`, alongside the intended `scheduler/tests/agents/test_daily_summary_prune.py`)
- **Verification:** `git blame` confirms CLEAN-05 lines are attributed to commit `5fc45f05`; `git diff HEAD~3 HEAD -- frontend/src/pages/SummaryFeedPage.tsx` shows the expected rewrite diff; working tree is clean for this file (`git status --short frontend/src/pages/SummaryFeedPage.tsx` returns empty).
- **Committed in:** `5fc45f0` (bundled with 16-04's scheduler-test commit due to parallel-executor staging race)

**Total deviations:** 1 (parallel-execution race condition — no semantic impact, commit attribution only)
**Impact on plan:** Zero impact on the code change or verification gates. CLEAN-05 acceptance gates ALL PASS. Only attribution metadata is split across commits — documented here for the verifier and any future archeology.

## Issues Encountered

The parallel-executor commit race (documented in Deviations section above). Resolved by documenting the actual commit hash containing the CLEAN-05 edit (`5fc45f0`) in this SUMMARY so the verifier can trace the change to its true commit.

## Integration-Checker Flow A Step 4 PARTIAL Finding — CLOSED

The v3.1 milestone audit (`.planning/v3.1-MILESTONE-AUDIT.md`) flagged `tech_debt.pre_existing_partial_flow` referencing integration-checker's Flow A step 4 PARTIAL: the Juno empty-state copy at `SummaryFeedPage.tsx:62-74` said "Coming in Phase 10 — Defence-sector ingestion not yet enabled" but Phase 10 had shipped 2026-05-19 and the Phase 12 production cron flipped 2026-05-20, making the copy semantically wrong (dead-text). This plan replaces the copy with current-truth tenant-aware copy. **Finding CLOSED.**

## User Setup Required

None — pure code edit, no external service configuration needed.

## Next Phase Readiness

- CLEAN-05 acceptance gate satisfied (stale copy gone from entire `frontend/src/` tree)
- One of 5 v3.1 audit-cleanup items closed (5/5 Wave 1 plans contribute to phase verifier signoff)
- Frontend regression baseline (181 tests) exactly preserved — no D-10 contract drift
- Phase 16 verifier can now check off CLEAN-05 alongside CLEAN-01/02/03/04 (each landing via parallel executors in this Wave)

---

*Phase: 16-v3.1-audit-cleanup-bundle*
*Plan: 05 (CLEAN-05)*
*Approach: rewrite (BINDING — see frontmatter `clean05_approach: rewrite`)*
*Completed: 2026-05-20*

## Self-Check: PASSED

- [x] `frontend/src/pages/SummaryFeedPage.tsx` exists and contains new copy — verified via grep (`No defence-industry briefs for this window yet` count = 1; `Coming in Phase 10` count = 0)
- [x] Commit `5fc45f0` exists in git log and contains the SummaryFeedPage.tsx edit — verified via `git show 5fc45f0 --stat` (shows `frontend/src/pages/SummaryFeedPage.tsx | 10 ++++++----`)
- [x] All grep gates PASS (stale phrases = 0, new copy present, cron schedule present, provenance comment present)
- [x] Frontend tests GREEN: 31/31 files, 181/181 tests pass — baseline EXACTLY preserved
- [x] TypeScript clean: `npx tsc --noEmit` exits 0
- [x] BINDING frontmatter field present: `clean05_approach: rewrite`
