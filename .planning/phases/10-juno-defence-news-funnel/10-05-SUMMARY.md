---
phase: 10-juno-defence-news-funnel
plan: 05
subsystem: scheduler-cron-enable + integration-smoke + visual-qa
tags: [juno, defence, cron-enable, juno-cron-enabled, integration-smoke, visual-qa, def-09, def-04, def-05, def-06, def-07, wave-4, phase-close]

# Dependency graph
requires:
  - phase: 10-04-wave-3-summarycard-cron-gate-voice-uat
    provides: "voice_calibration_uat.md APPROVED marker (grep gate prereq for cron-enable) + JUNO_CRON_ENABLED env-var gate in worker.py + SummaryCard per-tenant rendering (the surface the visual QA validates)"
  - phase: 10-03-wave-2-orchestrator-refusal-health
    provides: "_build_juno_defence_news_section + Canadian Procurement synthesis + World Events synthesis + refusal-detector + health-check (the production code path the smoke fire exercises)"
  - phase: 10-02-wave-1-classifier-config
    provides: "DEFENCE_NEWS_SYSTEM_PROMPT + Haiku 4.5 classify_story + 13 Tier-1 RSS feeds + 10 SerpAPI queries"
  - phase: 09-multi-tenant-foundation
    provides: ":company URL routing + scoped helpers + per-company cron registration + bookmark grace + AppHeader CompanySwitcher"
provides:
  - "Production cron enabled (local-dev flip; Railway env-var flip documented for operator)"
  - "First production-shape Juno daily_summaries row written (id=a88271de-8a6e-46f2-8ce6-30e277fe2ed6, status='completed')"
  - "integration_smoke_results.md artifact (Wave 4 Task 2 deliverable)"
  - "visual_qa_results.md artifact (Wave 4 Task 3 deliverable)"
  - "DEF-09 closure (operator-confirmed Juno Tab 2/Tab 3 empty-state intact)"
  - "End-to-end DEF-01..10 closure across all 5 Phase 10 waves"
affects: ["Phase 10 verifier (final regression gate)", "v3.0 milestone close-out"]

# Tech tracking
tech-stack:
  added:
    - "Local-dev JUNO_CRON_ENABLED=true flip in scheduler/.env (gitignored; Railway-equivalent flip documented for production deploy)"
    - "Inline asyncio.run(run_juno_daily_summary()) manual fire path (canonical for one-off production-shape fires outside the cron schedule)"
  patterns:
    - "Smoke-test gate against live DB before declaring a cron production-ready (Phase 9 D-08 precedent extended — Phase 9 caught Juno idempotency bug; Phase 10 confirms first production-shape row shape end-to-end)"
    - "Operator-walked visual QA at 1440×900 against live-DB-backed rendered output (Phase 8 UI-07 + Phase 9 09-05 Task 4 + Phase 10 10-05 Task 3 — third application of the same gate pattern)"
    - "By-design-empty section communicated via diagnostic JSONB markers (procurement_diagnostic.skipped_reason = 'non_morning_fire') + frontend renders SECTION_UNAVAILABLE_COPY fallback — operator sees explicit reason instead of bare-empty card"

key-files:
  modified:
    - scheduler/.env (gitignored — JUNO_CRON_ENABLED=true flip for local dev)
  created:
    - .planning/phases/10-juno-defence-news-funnel/integration_smoke_results.md
    - .planning/phases/10-juno-defence-news-funnel/visual_qa_results.md

key-decisions:
  - "Manual fire used Option A (direct asyncio.run of run_juno_daily_summary) NOT a forced morning-mode invocation — the 12:05 PT slot was the operator's available window. This means Canadian Procurement was empty by design (per RESEARCH §Open Q 1 cost gate). The next 08:05 PT production fire will populate that section against the live substrate. Documented as by-design behaviour in both integration_smoke_results.md Verdict row 6 and visual_qa_results.md Item 1 nuance."
  - "Railway env-var flip (JUNO_CRON_ENABLED=true on the Railway scheduler service) is documented as an operator post-merge action — local-dev flip in scheduler/.env was sufficient to exercise the production code path against the live (Railway-connected) dev DB. Rollback is a single env-var unset on Railway (no redeploy required)."
  - "Visual QA item 1 nuance (Canadian Procurement empty at 12:05 PT) explicitly accepted by operator as by-design behaviour — NOT a regression. The empty section renders SECTION_UNAVAILABLE_COPY fallback string with the procurement_diagnostic.skipped_reason='non_morning_fire' marker visible in agent_runs.notes for operator diagnostic visibility."
  - "DEF-09 closure verified via operator walking the Juno Tab 2 (Calendar) and Tab 3 (Viral Sweeper) empty-state pages — Phase 9 short-circuit guards held under all Phase 10 changes (Wave 3 SummaryCard rewire did NOT regress page-level early-returns)."

metrics:
  task-count: 3
  duration: "~45 min (Tasks 1+2 ~15 min — env flip + manual fire + smoke artifact; Task 3 ~30 min — operator visual QA walkthrough at 1440×900)"
  files-touched: 2  # integration_smoke_results.md + visual_qa_results.md (scheduler/.env is gitignored, doesn't count)
  commits: 2  # 1ca6528 (Task 2 smoke artifact) + final metadata commit (Task 3 visual QA + SUMMARY + state docs)
  test-impact:
    backend: "unchanged (no Phase 10 backend touches — Phase 9 routers already filter by company_id via scoped helpers)"
    scheduler: "unchanged at code level (Wave 3 baseline 328 passed / 1 skipped); live smoke fire exercised production code path against real Anthropic + RSS + DB stack and exited cleanly"
    frontend: "unchanged (Wave 3 baseline 168 tests passing); operator visual QA confirmed render correctness"
    smoke: "1 production-shape fire wrote 1 daily_summaries row (status='completed') + 1 agent_runs row; 37 Anthropic 200 OK responses (35 Haiku + 2 Sonnet); 0 refusals / 0 flagged feeds / 0 exceptions"
  completed: 2026-05-19
---

# Phase 10 Plan 05: Wave 4 — Cron Enable + Integration Smoke + Visual QA Summary

**Production Juno cron enabled (local-dev flip; Railway flip documented for operator); first production-shape `daily_summaries` row written with `status='completed'` and Janes/CSIS voice intact; operator walked the 10-item visual QA at 1440×900 and APPROVED; DEF-09 + all DEF-01..10 closed end-to-end.**

## Performance

- **Duration:** ~45 min (Tasks 1+2 ~15 min execution; Task 3 ~30 min operator walkthrough)
- **Started:** 2026-05-19 (Wave 4 entry)
- **Completed:** 2026-05-19
- **Tasks:** 3 (1 checkpoint:human-action + 1 auto + 1 checkpoint:human-verify, all approved/passing)
- **Files touched:** 2 new artifacts (`integration_smoke_results.md` + `visual_qa_results.md`); 1 gitignored env flip (`scheduler/.env`)
- **Commits:** 2 (Task 2 smoke artifact `1ca6528` + this final metadata commit covering Task 3 visual QA + SUMMARY + state docs)

## Accomplishments

- **Cron enabled** — `JUNO_CRON_ENABLED=true` flipped in local-dev `scheduler/.env`; Railway env-var flip documented as a post-merge operator action with rollback path. `build_scheduler()` registers 4 jobs (daily_summary, daily_summary_prune, weekly_sweeper, juno_daily_summary) when the env var is set.
- **First production-shape Juno row written** — `id=a88271de-8a6e-46f2-8ce6-30e277fe2ed6`, `company_id='juno'`, `status='completed'` (strongest outcome — not partial), `agent_run_id='bc65c4c0-cae3-4793-8433-334a25f378e1'`. Defence News: 2709 chars, Canadian Procurement: 0 chars (BY DESIGN at 12:05 PT), World Events: 3464 chars.
- **integration_smoke_results.md** archived in the phase directory — DB row excerpt + agent_runs.notes diagnostic + section markdown samples + Smoke Verdict: PASS.
- **visual_qa_results.md** archived in the phase directory — 10/10 checklist items PASS with the 12:05 PT Canadian Procurement empty-section nuance explicitly documented. Operator APPROVED.
- **DEF-09 closed** — operator-confirmed Juno Tab 2 (Calendar) + Tab 3 (Viral Sweeper) empty-state Phase 9 copy intact under all Phase 10 changes.
- **All DEF-01..10 closed end-to-end** across all 5 Phase 10 waves (see `visual_qa_results.md` cross-Phase-10 closure table).

## Task Commits

1. **Task 1: Cron-enable flip + Railway documentation** — no git commit (only modifies gitignored `scheduler/.env`); Railway operator-action documented inside `integration_smoke_results.md` Operator Notes section.
2. **Task 2: Manual smoke fire + `integration_smoke_results.md` artifact** — `1ca6528` (docs(10-05): capture Phase 10 integration smoke results — production cron fire PASS).
3. **Task 3: Visual QA at 1440×900 (operator checkpoint)** — APPROVED via operator resume signal; artifact (`visual_qa_results.md`) committed in this final metadata commit.

**Plan metadata commit:** Final commit covers `visual_qa_results.md` + `10-05-SUMMARY.md` + `10-SUMMARY.md` (phase-level) + `STATE.md` + `ROADMAP.md` + `REQUIREMENTS.md`.

## Files Created/Modified

- `.planning/phases/10-juno-defence-news-funnel/integration_smoke_results.md` — manual fire output + DB row excerpt + 11-check verdict table + refusal-detector + health-check + SerpAPI cost + Haiku classifier diagnostic + Smoke Verdict: PASS
- `.planning/phases/10-juno-defence-news-funnel/visual_qa_results.md` — 10-item operator-walked visual QA at 1440×900 + DEF-09 closure note + cross-Phase-10 DEF-01..10 closure table + Final Verdict: APPROVED
- `scheduler/.env` (gitignored, local-dev only) — `JUNO_CRON_ENABLED=true` flipped; Railway env-var flip is the equivalent for production rollout

## Decisions Made

See frontmatter `key-decisions` for the 4 substantive decisions made in Wave 4. Highlights:

1. **Manual fire ran at the 12:05 PT slot** (operator's available window), which means Canadian Procurement was empty by design (per RESEARCH §Open Q 1 morning-only SerpAPI cost gate). Documented as expected behaviour in both Wave 4 artifacts. The next 08:05 PT production fire will populate Canadian Procurement against the live substrate.
2. **Railway env-var flip deferred to operator post-merge action.** Local-dev `scheduler/.env` flip was sufficient to exercise the production code path against the live (Railway-connected) dev DB. Rollback path is a single Railway env-var unset (no redeploy required).
3. **Visual QA item 1 nuance accepted as by-design** — operator explicitly confirmed the 12:05 PT Canadian Procurement empty-section behaviour is the morning-only cost gate working as specified, not a rendering regression.
4. **DEF-09 closed via operator walkthrough** of Juno Tab 2 + Tab 3 empty-state pages (items 7 + 8 in the visual QA checklist).

## Deviations from Plan

None at the Rule-1/2/3 deviation level — the plan executed exactly as written across all 3 tasks. The single non-fatal anomaly was the operator's chosen execution slot (12:05 PT instead of 08:05 PT), which surfaced the by-design morning-only SerpAPI cost gate behaviour — handled per the planner's `<action>` step 4 note that `partial`/by-design-empty outcomes are ACCEPTABLE per D-11/D-12 and are documented in the artifact, not treated as a regression.

## Issues Encountered

None blocking. Two non-fatal observations from the smoke fire (both deferred to v3.0.1+, neither blocks Phase 10 close):

1. **Corpus-bounded section balance (Wave 3 deferred observation, surfaces again here):** Wave 3 voice UAT against the 8-story curated corpus produced 2/2/2 bullets vs the prompt's 3-7/3-5/5-7 floor. Wave 4 smoke against the live RSS+SerpAPI substrate (35 entries → 6 World Events bullets) is in-floor for World Events but Defence News bullet count was not separately counted (rendering confirmed the section is multi-bullet with proper attribution but exact count wasn't tallied). **Recommendation:** add a bullet-count assertion to the integration smoke artifact format for the next 2-3 production fires; if bullet counts consistently drop below the floor against rich substrate, prompt-tuning is warranted.

2. **Skydio Pydantic ValidationError fail-closed (Wave 3 deferred observation):** Did NOT recur in Wave 4 smoke — production volume showed 35 clean Haiku parses with zero ValidationErrors. The Wave 3 issue was specific to the curated UAT corpus. Still recommend the v3.0.1+ unit test for malformed Haiku response handling per Wave 3 SUMMARY.

Both observations carried forward to phase-level `10-SUMMARY.md` Deferred Items section for v3.0.1+ tracking.

## User Setup Required

**Operator post-merge action (single Railway env-var flip):**

Open Railway dashboard → seva-mining project → scheduler service → Variables tab → add:

```
JUNO_CRON_ENABLED=true
```

Railway auto-redeploys (~30-60s rollout). Confirm via scheduler startup log line:

```
juno_daily_summary cron ENABLED via JUNO_CRON_ENABLED=true env var
```

Rollback path: unset `JUNO_CRON_ENABLED` (or set to anything other than `true`). No redeploy required. Lock ID 1020 reservation untouched in either state.

**Operator action (separate, NOT part of this plan):** Rotate the dev-scoped `ANTHROPIC_API_KEY` that was used inline during the Wave 3 voice UAT auth-gate resolution — the chat transcript exposed the key value. Tracked separately from this plan's deliverables.

## Verification

- **Task 1:** Local-dev `scheduler/.env` confirmed via `cd scheduler && uv run pytest tests/test_worker.py::test_scheduler_registers_4_jobs_after_juno_add_when_env_enabled` returning 1 passed in 0.23s. Pre-flip grep gate verified: `grep -c "APPROVED" voice_calibration_uat.md` returned 5 (≥1 required).
- **Task 2:** Smoke fire wrote a fresh row via the production code path with no exceptions. DB row excerpt + 11-check verdict table archived in `integration_smoke_results.md`. Smoke Verdict: PASS.
- **Task 3:** Operator walked the 10-item visual QA at 1440×900 against the live-DB-backed rendered output. All 10 items PASS (item 1 with documented nuance). DEF-09 explicitly closed via items 7 + 8. Artifact `visual_qa_results.md` archived with operator APPROVED marker.
- **Cross-cutting:** `grep -l "APPROVED" .planning/phases/10-juno-defence-news-funnel/*.md` now returns 3 files (`voice_calibration_uat.md` + `integration_smoke_results.md` (PASS) + `visual_qa_results.md` (APPROVED)) satisfying the success-criteria grep gate.

## Next Phase Readiness

**Phase 10 is COMPLETE pending verification.** The orchestrator-spawned phase verifier will:

1. Run final regression gates against backend / scheduler / frontend test suites:
   - Pre-Phase-10 baseline: backend 184 pass / scheduler 269 pass / frontend 165 pass
   - Post-Phase-10 expected: backend 184 (no schema changes) / scheduler ~325+ (+56 net from Wave 1+2 tests) / frontend 168+ (SummaryCard per-tenant + companySectionConfig tests)
2. Verify CI grep gates still pass (CompanyScopedRoute, queryKeys centralization, scoped helpers)
3. Confirm phase-level `10-SUMMARY.md` matches the cross-cutting evidence in this and the 4 prior wave SUMMARY files
4. Ship Phase 10 → close v3.0 milestone

**No blockers.** Production cron is operationally enabled in local-dev; Railway env-var flip is the only remaining operator action before the next 08:05 PT slot fires a real Juno daily summary against the production DB. Two deferred observations (corpus-bounded bullet-count assertion + Skydio ValidationError unit test) are tracked in this SUMMARY + the phase-level SUMMARY for v3.0.1+ work.

**v3.0 milestone close-out:** Phase 10 is the FINAL phase of milestone v3.0. After Phase 10 verifier passes, the v3.0 milestone (TENANT-01..10 + DEF-01..10) ships and the project is ready for the v3.1+ planning cycle (per-tenant branding, Juno Calendar + Sweeper, additional tenants).

## Self-Check: PASSED

**Files exist:**
- FOUND: `.planning/phases/10-juno-defence-news-funnel/integration_smoke_results.md` (Task 2, commit `1ca6528`)
- FOUND: `.planning/phases/10-juno-defence-news-funnel/visual_qa_results.md` (Task 3, this final metadata commit)

**Commits exist:**
- FOUND: `1ca6528` (docs(10-05): capture Phase 10 integration smoke results — production cron fire PASS)

**Grep gates:**
- `grep -c "APPROVED" voice_calibration_uat.md` returns 5 (≥1 required by Wave 4 Task 1 pre-flip gate) — PASSED
- `grep -l "APPROVED" .planning/phases/10-juno-defence-news-funnel/*.md` returns ≥2 files (UAT + visual QA) — PASSED
- `grep -E "Smoke Verdict.*(PASS|PARTIAL)" .planning/phases/10-juno-defence-news-funnel/integration_smoke_results.md` returns 1 match (Smoke Verdict: PASS) — PASSED

**Backing data:**
- Live DB row exists: `id=a88271de-8a6e-46f2-8ce6-30e277fe2ed6`, `company_id='juno'`, `status='completed'` (confirmed by Task 2 SQLAlchemy query stdout archived in `integration_smoke_results.md`)
- `JUNO_CRON_ENABLED=true` set in local-dev `scheduler/.env` (gitignored); Railway flip is operator post-merge action documented in `integration_smoke_results.md` Operator Notes

---

*Phase: 10-juno-defence-news-funnel*
*Plan: 05 (Wave 4)*
*Completed: 2026-05-19*
*Phase 10 close-out — all 5 waves complete*
