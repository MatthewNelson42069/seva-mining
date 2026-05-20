---
phase: 09-multi-tenant-foundation
plan: 05
subsystem: testing-multitenant-isolation-smoke-visualqa
tags: [tenant-isolation, parametrized-tests, idempotency, smoke-test, visual-qa, juno-idempotency-fix, freeze-lift]

# Dependency graph
requires:
  - phase: 09-multi-tenant-foundation
    plan: 04
    provides: frontend routing + CompanySwitcher + AppHeader freeze-lift + queryKeys factory + Juno empty-state pages
  - phase: 09-multi-tenant-foundation
    plan: 03
    provides: per-company cron + /api/{company} routers + scoped helpers
provides:
  - backend/tests/test_multitenant_isolation.py — fully-populated parametrized cross-tenant leak detection (19 tests, all GREEN)
  - .planning/PROJECT.md — Key Decisions entry recording the v3.0 AppHeader freeze-lift (3rd of 3 D-02 documentation locations)
  - .planning/phases/09-multi-tenant-foundation/09-VISUAL-QA-RESULTS.md — both blocking checkpoints approved by operator
  - .planning/phases/09-multi-tenant-foundation/09-SUMMARY.md — phase-level summary with Decisions section recording the AppHeader freeze-lift (1st of 3 D-02 documentation locations)
  - Critical pre-prod bug fix: Juno idempotency filter extended to include 'partial' (commit 261b8fa) — without this, every cron fire would have produced duplicate Juno rows in production
affects: [10-juno-defence-news-funnel]

# Tech tracking
tech-stack:
  added: []  # no new deps — pytest + pytest-asyncio + httpx.AsyncClient + existing fixtures only
  patterns:
    - "Parametrized cross-tenant leak detection matrix: 3 endpoints × 2 tenants = 6 tuples + 5 standalone tests = 11 distinct contracts. Walk-the-JSON assertion catches cross-tenant company_id leaks anywhere in the response payload."
    - "Idempotency inclusion-list semantics differ per tenant: Seva idempotency-skips ONLY {running, completed} (allowing partial/failed retry); Juno idempotency-skips {running, completed, PARTIAL} because partial is the v3.0 steady-state for Juno until Phase 10 fills real content. The asymmetry is intentional + documented in 261b8fa commit message."
    - "Blocking checkpoint pair pattern: smoke-test (DB row contracts) BEFORE visual-QA (UI render contracts) — operator verifies DB-level correctness FIRST, then walks the visual checklist with confidence the underlying data layer is sound. Replaces the prior Iteration 1 path-a auto-task that conflated the two."
    - "Visual QA at 1440x900 in Chrome with DevTools Device Toolbar — locked viewport matches Phase 8 D-11 baseline. Same gate, same dimensions, re-baselined for v3.0 with formal freeze-lift recorded."

key-files:
  created:
    - .planning/phases/09-multi-tenant-foundation/09-VISUAL-QA-RESULTS.md
    - .planning/phases/09-multi-tenant-foundation/09-SUMMARY.md
  modified:
    - backend/tests/test_multitenant_isolation.py  # Wave 0 scaffold → fully populated; was status='skip', now 19 tests GREEN
    - scheduler/agents/daily_summary.py            # Juno idempotency filter extended to include 'partial' (Rule 1 bug fix)
    - .planning/PROJECT.md                         # Key Decisions row for v3.0 AppHeader freeze-lift (D-02 3rd documentation location)

key-decisions:
  - "Juno idempotency filter status inclusion-list extended to include 'partial' (Rule 1 bug fix during Task 2 smoke run). Seva idempotency stays at {running, completed} only. The asymmetry is correct: Juno's steady-state in v3.0 is 'partial' (Phase 10 fills real content); Seva's 'partial' represents a flaky attempt that should be retried. Documented verbatim in commit 261b8fa."
  - "Task 2 deliberately persisted /tmp/seva-09-05-smoke.log for the Task 3 checkpoint to inspect — DB row counts are the single source of truth for the smoke contract, NOT Task 2's automated verify gate. Iteration 2 Blocker 3 fix: row counts move to a dedicated human-confirm checkpoint instead of a fragile shell assertion."
  - "Smoke-test rows NOT cleaned up after Task 3 approval — operator chose to leave the 2 rows (1 seva-partial + 1 juno-partial) in the dev DB as harmless clutter that surfaces during Task 4 visual QA at /juno/ (confirms end-to-end render path). The cleanup SQL stays documented in 09-05-PLAN Task 3 step 4 for future similar checkpoints."
  - "Phase-level 09-SUMMARY.md grep gate (verifies 'freeze-lift' OR 'AppHeader freeze' substring appears in the Decisions section) is satisfied — the gate ensures D-02 first documentation location is in place, complementing the inline comment in AppHeader.tsx (b) and the PROJECT.md Key Decisions entry (c)."

requirements-completed: [TENANT-10]

# Metrics
metrics:
  duration: 45  # minutes wall-clock (Tasks 1+2 execution + Tasks 3+4 human checkpoints)
  completed_date: 2026-05-19
  tasks_completed: 4
  task_count: 4
  files_modified: 5  # 2 production source + 1 PROJECT.md + 2 phase docs (this SUMMARY + VISUAL-QA-RESULTS) + phase-level 09-SUMMARY.md
  tests_added_backend: 19  # test_multitenant_isolation.py — was 0 (Wave 0 scaffold skipped), now 19 GREEN
  tests_passed_backend: 184  # was 165 pre-Wave 4
  tests_passed_scheduler: 269  # unchanged from Wave 3
  tests_passed_frontend: 165  # unchanged from Wave 3
  ci_grep_gate: pass
  smoke_test_checkpoint: approved
  visual_qa_checkpoint: approved
---

# Phase 09 Plan 05: Wave 4 — TENANT-10 Cross-Tenant Isolation Tests + Smoke + Visual QA Summary

**One-liner:** TENANT-10 closed — populated `test_multitenant_isolation.py` from Wave 0 scaffold into a 19-test parametrized cross-tenant leak detection matrix (all GREEN); ran the live-DB smoke heredoc which surfaced and auto-fixed a critical Juno idempotency bug that would have written duplicate rows every cron fire in production; operator approved both blocking checkpoints (smoke-test row contracts + 50+ item visual QA checklist at 1440x900) closing Phase 9's atomic-deploy contract.

## Performance

- **Duration:** ~45 min (Tasks 1+2 ~10 min execution; Tasks 3+4 human checkpoints + interleaved bug fix)
- **Started:** 2026-05-19T16:40:00-07:00
- **Completed:** 2026-05-19T17:30:00-07:00
- **Tasks:** 4 of 4 complete (2 auto + 2 blocking checkpoints — both APPROVED)
- **Files modified:** 5 (2 production source + 1 PROJECT.md + 2 phase docs)

## Accomplishments

- **TENANT-10 closed** — `backend/tests/test_multitenant_isolation.py` populated from Wave 0 skip-scaffold into 19 cross-tenant leak detection tests, all GREEN. Matrix: 6 parametrized (3 endpoints × 2 tenants) + 3 invalid-company 404 + 5 invalid-uppercase 422 + 3 unprefixed-legacy 404 + POST-persists-company_id + PATCH-cannot-cross-tenant = 19 distinct contracts.
- **Juno idempotency bug auto-fixed pre-prod (Rule 1 deviation)** — smoke-test surfaced that `run_juno_daily_summary`'s idempotency filter was `status.in_(['running', 'completed'])` but Juno ALWAYS writes `'partial'` in v3.0. Without the catch, every cron fire would have produced a duplicate Juno row. Fix extended the filter to include `'partial'` for the Juno path; Seva semantics remain opposite (retry partial/failed). Critical pre-prod catch — exactly the failure mode the smoke checkpoint exists for.
- **Blocking checkpoint pair both APPROVED** — Task 3 smoke-test (`"approved"`) + Task 4 visual QA (`"approved"`) — recorded in `09-VISUAL-QA-RESULTS.md` with verbatim contracts + per-section PASS marks. The atomic-deploy contract is satisfied.
- **D-02 third documentation location landed** — `.planning/PROJECT.md` Key Decisions table now has the v3.0 AppHeader freeze-lift entry, completing the 3-location D-02 contract (a = phase-level 09-SUMMARY.md Decisions, b = inline AppHeader.tsx comment, c = PROJECT.md).
- **Phase-level 09-SUMMARY.md created** with substantive Decisions section + per-wave summaries + handoff to Phase 10 — the first D-02 documentation location, satisfied by the plan-level grep gate.

## Task Commits

Each task was committed atomically:

1. **Task 1: Populate test_multitenant_isolation.py (TENANT-10)** — `1966645` (`test(09-05): populate cross-tenant isolation test matrix (TENANT-10)`)
2. **Task 2: Smoke heredoc + PROJECT.md D-02 entry + Juno idempotency Rule 1 fix** — `261b8fa` (`fix(09-05): include 'partial' in Juno idempotency filter + document v3.0 D-02 in PROJECT.md`)
3. **Task 3: checkpoint:smoke-test (gate=blocking)** — APPROVED by operator at 2026-05-19; resume signal `"approved"`. No file commit (verification-only checkpoint per plan contract).
4. **Task 4: checkpoint:human-verify visual QA at 1440x900 (gate=blocking)** — APPROVED by operator at 2026-05-19; resume signal `"approved"`. No file commit (visual-only checkpoint per plan contract).

**Plan metadata + finalization:** committed alongside SUMMARY + STATE + ROADMAP + REQUIREMENTS update in the final docs commit.

## Files Created/Modified

- `backend/tests/test_multitenant_isolation.py` — Wave 0 scaffold replaced with 19-test parametrized matrix (TENANT-10 closure)
- `scheduler/agents/daily_summary.py` — Rule 1 bug fix: Juno idempotency filter extended to include 'partial' status
- `.planning/PROJECT.md` — Key Decisions table appended with v3.0 Phase 9 AppHeader freeze-lift entry (D-02 third documentation location)
- `.planning/phases/09-multi-tenant-foundation/09-05-SUMMARY.md` — this file (plan-level summary)
- `.planning/phases/09-multi-tenant-foundation/09-SUMMARY.md` — phase-level summary with Decisions section (D-02 first documentation location)
- `.planning/phases/09-multi-tenant-foundation/09-VISUAL-QA-RESULTS.md` — checkpoint approval record for Tasks 3 + 4
- `/tmp/seva-09-05-smoke.log` — smoke-test stdout (311 lines; persisted for Task 3 inspection)

## Smoke-Test Output Excerpt

```
=== daily_summaries (last 5 min) ===
daily_summaries: company=juno status=partial agent_run_id=ff9e9a6e-30b0-4e7d-84e2-06a3ec47aa5a
daily_summaries: company=seva status=partial agent_run_id=914ed479-53f4-4518-89a5-3bbdc359cedd
=== agent_runs (last 5 min) ===
agent_runs: agent=daily_summary status=partial notes={"candidates_gold": 20, "candidates_gold_rss": 116, "candidates_gold_serpapi": 0
agent_runs: agent=juno_daily_summary status=completed notes={"company_id": "juno", "phase_10_pending": true}
```

All 4 row-count contracts confirmed: exactly 2 daily_summaries rows (1 seva + 1 juno, distinct agent_run_ids), exactly 2 agent_runs rows (`daily_summary` + `juno_daily_summary`), idempotency proof holds (3rd `run_juno_daily_summary()` call wrote no new row), Juno `notes` contain `company_id` + `juno` markers.

Note on Seva `status='partial'`: acceptable per smoke contract (`{completed, partial}` both valid for Seva); the smoke contract only requires Juno=partial. Seva degraded due to dev SerpAPI key unset + an unrelated Anthropic relevance-scoring TypeError that engaged the keyword fallback — neither is a Phase 9 concern.

## Task 3 Checkpoint Result

`"approved"` — all 4 row-count contracts PASS. Detail recorded in `09-VISUAL-QA-RESULTS.md` §Task 3.

## Task 4 Checkpoint Result

`"approved"` — all 50+ items across 9 sections (AppHeader, CompanySwitcher visual states, tab preservation, Juno empty-states, Seva preservation, browser navigation, bookmark grace, accessibility, performance, persistence, production-equivalence) PASS at 1440x900 in Chrome. Detail recorded in `09-VISUAL-QA-RESULTS.md` §Task 4.

## Final Test Counts Across All 3 Layers

| Layer | Pre-Wave 4 | Post-Wave 4 | Net |
|-------|------------|-------------|-----|
| Backend | 165 pass / 6 skip | 184 pass / 6 skip | +19 (test_multitenant_isolation.py populated) |
| Scheduler | 269 pass | 269 pass | 0 (Task 2 fix is in production source, no test additions) |
| Frontend | 165 pass / 0 skip | 165 pass / 0 skip | 0 (no frontend changes in Wave 4) |
| **Total** | **599 pass / 6 skip** | **618 pass / 6 skip** | **+19 net** |

CI grep gate (`scripts/verify-tenant-isolation.sh`) exits 0 with no temporary whitelists.

## Decisions Made

- **Juno idempotency asymmetry (Rule 1 fix):** Juno includes `'partial'` in the skip-list because partial IS the v3.0 steady-state; Seva excludes it because partial signals a flaky attempt worth retrying. The asymmetry is correct + documented in commit `261b8fa`.
- **Visual QA checklist verbatim from UI-SPEC:** the 50+ item list reproduced inline in Task 4 `<how-to-verify>` matches 09-UI-SPEC.md §Manual Visual QA Checklist character-for-character. No paraphrase — same precedent as 08-UI-07-CHECKLIST-RESULTS.md.
- **Smoke-test rows NOT cleaned up:** operator chose to leave the 2 rows in dev DB as visible-during-visual-QA reassurance. Cleanup SQL remains documented in PLAN Task 3 step 4.
- **Phase-level 09-SUMMARY.md created at plan close:** the grep gate (`grep -c "freeze-lift\|AppHeader freeze" .planning/phases/09-multi-tenant-foundation/09-SUMMARY.md` >= 1) enforces D-02 first documentation location lands in this plan's deliverable. Satisfied.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Juno idempotency filter missing 'partial' status**
- **Found during:** Task 2 (smoke-test execution)
- **Issue:** `scheduler/agents/daily_summary.py::run_juno_daily_summary` idempotency check filtered `status.in_(['running', 'completed'])` — but Juno ALWAYS writes `'partial'` in v3.0 (Phase 10 fills real content). Two back-to-back `run_juno_daily_summary()` calls within the IDEMPOTENCY_WINDOW_MIN window produced 3 `daily_summaries` rows instead of 2 — every cron fire in production would have written a duplicate Juno row.
- **Fix:** Extended the Juno-side status filter to include `'partial'`. Seva-side `_idempotency_skip` is left UNCHANGED because Seva's `'partial'` / `'failed'` rows represent flaky attempts that should be retried — the asymmetry is correct + intentional.
- **Files modified:** `scheduler/agents/daily_summary.py`
- **Verification:** Re-ran the smoke heredoc; saw 1 seva + 1 juno daily_summaries row (idempotency proof: 3rd call writes no new row); all 4 Task 3 contracts now PASS. Critical pre-prod catch — this is exactly what the smoke-test gate exists for.
- **Committed in:** `261b8fa` (Task 2 commit, alongside PROJECT.md D-02 entry)

---

**Total deviations:** 1 auto-fixed (1 bug — pre-prod catch via smoke-test gate)
**Impact on plan:** The fix is essential for correctness. Without it, Phase 9 ships immediately broken (duplicate Juno rows every cron fire). The smoke-test gate caught it BEFORE Task 4 visual QA, validating the gate's existence. No scope creep — the fix is within the same 09-05-PLAN Task 2 scope (smoke-test execution + auto-fix path under Rule 1).

## Issues Encountered

None beyond the Juno idempotency bug auto-fixed during Task 2. The plan executed as designed; Tasks 1+2 ran in ~10 min; Tasks 3+4 took ~30 min of human walkthrough including the bug-fix iteration.

## User Setup Required

None — Phase 9 is config-and-code only. No new env vars, no new external services. Phase 10 will require Anthropic API key already set in Railway env.

## Next Phase Readiness

- **Phase 10 (Juno Defence News Funnel) ready to start.** Phase 9 ships the infrastructure (per-company cron, `/api/{company}/*` routers, queryKeys factory, CompanySwitcher, `:company` routing, `scheduler/companies/juno/` package skeleton with stub `feeds.py`/`prompts.py`/`serpapi.py`). Phase 10 is config-only: populate those 3 stub files with Tier-1 defence RSS + SerpAPI fallback + defence Sonnet 4.6 prompt + Haiku 4.5 relevance classifier; no schema changes, no routing changes, no scheduler changes.
- **Atomic-deploy contract satisfied.** All 10 TENANT-01..10 requirements verified in code AND tests AND human eyeball. `test_multitenant_isolation.py` is GREEN with 19 tests covering every list endpoint × tenant. The CI grep gate runs clean with no temporary whitelists. The blocking checkpoint pair both PASSED at the human-verification level.
- **Outstanding follow-ups (none Phase-9-critical):**
  - Seva content quality (Anthropic relevance-scoring TypeError + SerpAPI dev key) is a Phase 8 / Phase 10 concern, not Phase 9. Production Seva runs will pick up the real API keys via Railway env.
  - Smoke-test cleanup SQL stays documented in PLAN Task 3 step 4 for future similar gates; 2 dev rows remain harmlessly in the DB.

---

## Self-Check: PASSED

- [x] FOUND: `.planning/phases/09-multi-tenant-foundation/09-VISUAL-QA-RESULTS.md` (154 lines)
- [x] FOUND: `.planning/phases/09-multi-tenant-foundation/09-SUMMARY.md` (phase-level, 184 lines, D-02 grep gate matches: 10)
- [x] FOUND: `.planning/phases/09-multi-tenant-foundation/09-05-SUMMARY.md` (this file)
- [x] FOUND: commit `1966645` — `test(09-05): populate cross-tenant isolation test matrix (TENANT-10)`
- [x] FOUND: commit `261b8fa` — `fix(09-05): include 'partial' in Juno idempotency filter + document v3.0 D-02 in PROJECT.md`
- [x] PASSED: D-02 grep gate `grep -c "freeze-lift\|AppHeader freeze" .planning/phases/09-multi-tenant-foundation/09-SUMMARY.md` returns 10 (>= 1 required)
- [x] STATE.md updated: 5/5 plans complete; status "Phase 9 complete — pending verification"; progress 25/25 (100%)
- [x] ROADMAP.md updated: Phase 9 row shows `5/5 | Complete pending verification | 2026-05-19`; Phase 9 milestone bullet checked
- [x] REQUIREMENTS.md updated: TENANT-10 checkbox marked + traceability table row reflects 09-05 completion; TENANT-01..09 traceability also updated to Complete

---

*Phase: 09-multi-tenant-foundation*
*Completed: 2026-05-19*
