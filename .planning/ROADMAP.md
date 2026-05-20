# Roadmap: Seva Mining

## Milestones

- ✅ **v1.0.1 — Approval Dashboard (deprecated by v2.0 pivot)** — Phases 1-11, shipped 2026-04-25 → archive: [`milestones/v1.0.1/ROADMAP.md`](milestones/v1.0.1/ROADMAP.md)
- ✅ **v2.0 — Daily Summary Feed** — Phases 1-4 (reset numbering), shipped 2026-05-06 → archive: [`milestones/v2.0-ROADMAP.md`](milestones/v2.0-ROADMAP.md)
- ✅ **v2.1 — Three-Tab Content Engine + UI Polish** — Phases 5-8 (project-wide counter continues), shipped 2026-05-19 → archive in [`milestones/v3.0-ROADMAP.md`](milestones/v3.0-ROADMAP.md) (snapshot at v3.0 close includes v2.1 phase details — v2.1 was never archived separately before v3.0 started)
- ✅ **v3.0 — Multi-Tenant Dashboards (Juno Industries Onboarding)** — Phases 9-10, shipped 2026-05-19 → archive: [`milestones/v3.0-ROADMAP.md`](milestones/v3.0-ROADMAP.md) (audit: [`milestones/v3.0-MILESTONE-AUDIT.md`](milestones/v3.0-MILESTONE-AUDIT.md))
- 🚧 **v3.0.1 — v3.0 Audit Cleanup Bundle** — Phase 11 (in progress)

## Phases

<details>
<summary>✅ v2.0 Daily Summary Feed (Phases 1-4) — SHIPPED 2026-05-06</summary>

- [x] Phase 1: Gold News Card + Web Feed (6/6 plans) — completed 2026-05-06
- [x] Phase 2: Ontario Law Ingestion (1/1 plan) — completed 2026-05-06
- [x] Phase 3: Ontario Stats Ingestion (1/1 plan) — completed 2026-05-06
- [x] Phase 4: Prune Cron + Operations Hardening (1/1 plan, 4 tasks) — completed 2026-05-06

Phase artifacts archived to `milestones/v2.0-phases/`. Full roadmap detail: `milestones/v2.0-ROADMAP.md`.

</details>

<details>
<summary>✅ v1.0.1 Approval Dashboard (Phases 1-11) — DEPRECATED by v2.0 pivot</summary>

11 phases shipped between 2026-03-30 and 2026-04-25 covering FastAPI backend, React approval dashboard, Twitter Agent (later deprecated), Senior Agent (later deprecated), Instagram Agent (later deprecated), Content Agent + 6 sub-agents, dashboard views + WhatsApp digest, agent execution polish, and content preview / rendered images. Source files retained as dead code per v2.0 retirement intent. Full archive: `milestones/v1.0.1/ROADMAP.md`.

</details>

<details>
<summary>✅ v2.1 Three-Tab Content Engine + UI Polish (Phases 5-8) — SHIPPED 2026-05-19</summary>

- [x] Phase 5: Foundation — Tabs + DB + Backend Stubs (5/5 plans) — completed 2026-05-19
- [x] Phase 6: Content Calendar (5/5 plans) — completed 2026-05-19
- [x] Phase 7: Weekly Viral Sweeper (6/6 plans) — completed 2026-05-19 (X-API pivot from Reddit per 07-CONTEXT.md D-03)
- [x] Phase 8: UI Polish + Dead-Code Strip (4/4 plans) — completed 2026-05-19

Full roadmap detail snapshot in `milestones/v3.0-ROADMAP.md` (v2.1 phases were never archived separately — captured in the v3.0 close snapshot).

</details>

<details>
<summary>✅ v3.0 Multi-Tenant Dashboards — Juno Industries Onboarding (Phases 9-10) — SHIPPED 2026-05-19</summary>

- [x] Phase 9: Multi-Tenant Foundation (5/5 plans, verifier 10/10 PASS) — completed 2026-05-19
- [x] Phase 10: Juno Defence News Funnel (5/5 plans, verifier 10/10 PASS, voice UAT + visual QA APPROVED) — completed 2026-05-19

Full roadmap detail: `milestones/v3.0-ROADMAP.md`. Audit verdict `tech_debt` (20/20 reqs satisfied; 8 non-blocking follow-ups for v3.0.1/v3.1+).

</details>

---

### v3.0.1 — v3.0 Audit Cleanup Bundle

**Milestone goal:** Close the 5 non-blocking follow-ups filed by the v3.0 milestone audit (`milestones/v3.0-MILESTONE-AUDIT.md`) — resolve the 12:05 PT Canadian Procurement UX, tighten documentation drift (traceability table + VALIDATION.md frontmatter), remove the `run_juno_daily_summary` double-definition dead code, and harden the Haiku classifier ValidationError observability path. Ships v3.0 cleanly closed before any v3.1 expansion work begins. Single phase (Phase 11) because all 5 items are small audit follow-ups sharing v3.0 context; bundling them avoids ceremony overhead.

- [ ] **Phase 11: v3.0 Audit Cleanup Bundle** — Close CLEANUP-01..05 (12:05 PT Canadian Procurement enablement + traceability refresh + dead-code removal + VALIDATION frontmatter flips + Haiku ValidationError logging)

### Phase 11: v3.0 Audit Cleanup Bundle

**Goal:** All 5 v3.0 audit follow-ups land in one small bundle. After this phase: the 12:05 PT Juno cron writes a full 3-section brief (Defence News + Canadian Procurement + World Events) instead of skipping procurement queries by design; `milestones/v3.0-REQUIREMENTS.md` traceability table reflects production reality (Complete, not Scaffolded) for DEF-01..07; `scheduler/agents/daily_summary.py` has exactly one `run_juno_daily_summary` definition; both v3.0 phase VALIDATION.md frontmatters show `nyquist_compliant: true` + `wave_0_complete: true`; and the Haiku 4.5 relevance classifier's silent `ValidationError` fail-closed path now emits structured logs to `agent_runs.notes` while preserving the existing fail-closed contract (item excluded from synthesis on schema mismatch).

**Depends on:** v3.0 milestone shipped (✓ 2026-05-19) — production cron operational (`JUNO_CRON_ENABLED=true` post-Railway-flip); audit verdict `tech_debt` recorded in `milestones/v3.0-MILESTONE-AUDIT.md`

**Requirements:** CLEANUP-01, CLEANUP-02, CLEANUP-03, CLEANUP-04, CLEANUP-05

**Inputs:**
- v3.0 codebase as shipped (commit `89f5047` post-Phase-10) — `scheduler/agents/daily_summary.py` at ~1370 lines with double-defined `run_juno_daily_summary` (Phase 9 stub at line 762 + Phase 10 live impl at line 1150); `scheduler/agents/juno_relevance.py` with silent `try/except ValidationError` pass-closed
- `milestones/v3.0-MILESTONE-AUDIT.md` — source of all 5 cleanup items with line-level references and operator-stated preferences
- `milestones/v3.0-REQUIREMENTS.md` traceability table — DEF-01..DEF-07 rows say "Scaffolded (Wave 0 / 10-01 — RED tests + ...; production lands Wave 1/Wave 2)" but verification status is `passed` and checkboxes are `[x]`
- `milestones/v3.0-phases/09-multi-tenant-foundation/09-VALIDATION.md` + `milestones/v3.0-phases/10-juno-defence-news-funnel/10-VALIDATION.md` frontmatter with stale `nyquist_compliant: false` + `wave_0_complete: false` flags
- `milestones/v3.0-phases/10-juno-defence-news-funnel/integration_smoke_results.md` — documents the 12:05 PT empty-Canadian-Procurement-by-design behavior that CLEANUP-01 changes (row `a88271de-...` `canadian_procurement_md=""`)
- `scheduler/tests/agents/test_juno_daily_summary.py` — Wave 2 (10-03) tests assert noon-fire-skip-procurement; MUST be updated in the same commit as the CLEANUP-01 production code change
- Operator-stated preference (this session): both daily Juno fires (08:05 PT + 12:05 PT) should produce a full 3-section brief; budget impact accepted at ~$5.25/mo → ~$8-9/mo Juno SerpAPI (still inside $50/mo cap with ~$41 headroom)
- v3.0 audit "Recommendation" line 217: "Land the 4 v3.0.1 quick-fix items (traceability table refresh + VALIDATION frontmatter flags + double-definition cleanup) as a single small bundle" — this phase implements that recommendation plus CLEANUP-01 (operator decision item) and CLEANUP-05 (logging observability)

**Outputs:**
- `scheduler/agents/daily_summary.py` MODIFIED — `_build_juno_canadian_procurement_section()` no longer returns the early `("", {"skipped_reason": "non_morning_fire"}, 0)` short-circuit when `is_morning_fire=False`; both 08:05 PT and 12:05 PT fires execute the 7 Canadian-procurement SerpAPI queries from `scheduler/companies/juno/serpapi.py::JUNO_SERPAPI_QUERIES`
- `scheduler/agents/daily_summary.py` MODIFIED — Phase 9 stub `run_juno_daily_summary` block at line ~762 deleted; only the Phase 10 live implementation at line ~1150 remains; file shrinks by ~110 lines; `scheduler/worker.py` lazy import continues to resolve correctly
- `scheduler/tests/agents/test_juno_daily_summary.py` MODIFIED — Wave 2 tests that assert noon-fire-skips-procurement updated to assert noon-fire-runs-procurement (or removed if redundant with morning-fire test); all scheduler tests stay GREEN
- `scheduler/agents/juno_relevance.py` MODIFIED — `except pydantic.ValidationError as exc:` branch now appends to `agent_runs.notes` JSONB under `haiku_validation_errors` key with shape `{"input_excerpt": "<first 200 chars>", "error_type": "<exc class>", "error_msg": "<first 200 chars of str(exc)>"}`; fail-closed contract preserved (item still excluded from synthesis); optional Haiku `temperature` tune if planner picks
- `milestones/v3.0-REQUIREMENTS.md` MODIFIED — traceability rows DEF-01 through DEF-07 update descriptive text from "Scaffolded (Wave 0 / 10-01 — ...)" to "Complete (2026-05-19, plan 10-02 / 10-03 — <evidence>)" matching the format used for DEF-08..10
- `milestones/v3.0-phases/09-multi-tenant-foundation/09-VALIDATION.md` MODIFIED — frontmatter `nyquist_compliant: false` → `true` and `wave_0_complete: false` → `true`
- `milestones/v3.0-phases/10-juno-defence-news-funnel/10-VALIDATION.md` MODIFIED — frontmatter `nyquist_compliant: false` → `true` and `wave_0_complete: false` → `true`

**Success Criteria** (what must be TRUE when this phase completes):
1. 12:05 PT Juno cron fire writes a `daily_summaries` row with all 3 sections populated (Defence News + Canadian Procurement + World Events Relevant to Defence); `canadian_procurement_md` column is non-empty for both 08:05 PT and 12:05 PT rows in the same day; `agent_runs.notes` for the 12:05 PT fire shows the 7 Canadian-procurement SerpAPI queries executed (not `skipped_reason: non_morning_fire`)
2. `grep -c 'Scaffolded' milestones/v3.0-REQUIREMENTS.md` returns 0 — all 7 DEF-01..DEF-07 traceability rows now read "Complete (2026-05-19, plan 10-02 / 10-03 — <evidence>)" matching the format already used for DEF-08..10
3. `scheduler/agents/daily_summary.py` line count is reduced by ~110 lines; `grep -c 'def run_juno_daily_summary' scheduler/agents/daily_summary.py` returns 1 (not 2); full scheduler pytest suite stays GREEN (328+ pass); `scheduler/worker.py` lazy import of `run_juno_daily_summary` continues to resolve to the Phase 10 implementation (verified by manual scheduler boot)
4. Both `09-VALIDATION.md` + `10-VALIDATION.md` frontmatter show `nyquist_compliant: true` and `wave_0_complete: true`; no other frontmatter fields disturbed
5. When a synthetic schema-violating payload is fed to `juno_relevance.py`, the Haiku `ValidationError` is now logged to `agent_runs.notes` under the `haiku_validation_errors` key with `input_excerpt` + `error_type` + `error_msg` populated; behavioral fail-closed contract preserved — the offending item is still excluded from Sonnet synthesis (NO change to the dual-use exclusion goal); `test_juno_relevance_classifier.py` regression test continues to pass

**Plans:** TBD — likely 5 (one per CLEANUP requirement). Provisional sequencing for `/gsd:plan-phase` to confirm:
- Wave 1 (parallel, different files): 11-01 (CLEANUP-01 — `daily_summary.py` cost-gate removal + Wave 2 test update) + 11-02 (CLEANUP-02 — `milestones/v3.0-REQUIREMENTS.md` docs) + 11-04 (CLEANUP-04 — two VALIDATION.md frontmatter edits)
- Wave 2 (serialize after 11-01 since same file): 11-03 (CLEANUP-03 — `daily_summary.py` line-762 dead-code removal) + 11-05 (CLEANUP-05 — `juno_relevance.py` ValidationError logging)

**UI hint**: no

**Complexity:** S (pure cleanup, no new features, no schema changes, no new dependencies)
**Estimated duration:** 1-2 hours (5 small tasks; 4 of 5 are documentation/dead-code; only CLEANUP-01 + CLEANUP-05 touch production code)

**Dependencies:**
- v3.0 milestone shipped (✓ done 2026-05-19) — production cron operational
- No external blockers; no operator UAT required (CLEANUP-01 budget delta already operator-approved this session)
- CLEANUP-01 code change + CLEANUP-01 test update MUST land in the same commit (Wave 2 noon-fire-skip assertion goes RED the moment the cost gate is removed)
- CLEANUP-03 dead-code removal serialized after CLEANUP-01 because both edit `scheduler/agents/daily_summary.py`

**Hard parts (cross-ref PROJECT.md "Hard parts" + v3.0 audit):**

| # | Pitfall | Severity | Prevention |
|---|---------|----------|-----------|
| P1 | 12:05 PT test update drift — removing the `is_morning_fire` cost gate in `_build_juno_canadian_procurement_section` leaves Wave 2 (10-03) tests in `scheduler/tests/agents/test_juno_daily_summary.py` asserting the old skip-procurement behavior; CI goes RED on first push unless the test change ships in the same commit | HIGH | Update production code + tests as a single atomic edit (one plan, one commit); plan 11-01 explicitly owns both files; pre-merge `pytest scheduler/tests/agents/test_juno_daily_summary.py -v` must show GREEN for both 08:05 PT and 12:05 PT cases |
| P2 | Dead-code removal safety — `run_juno_daily_summary` at line 762 is dead per Python last-wins semantics, but a hypothetical `from scheduler.agents.daily_summary import run_juno_daily_summary` that ran at module import time before line 1150 was reached would still see the Phase 9 stub | LOW | `grep -rn 'run_juno_daily_summary' scheduler/ backend/ frontend/` returns only the two definitions in `daily_summary.py` + the one lazy import in `scheduler/worker.py` (resolves at call time, not import time, so post-deletion the only definition is the Phase 10 impl); confirm with full scheduler pytest re-run + manual `python -c 'from scheduler.agents.daily_summary import run_juno_daily_summary; print(run_juno_daily_summary.__module__, run_juno_daily_summary.__qualname__)'` smoke |
| P3 | Haiku `ValidationError` logging without breaking fail-closed contract — the audit explicitly flagged "silent fail-open at application layer"; the current behavior (item EXCLUDED from synthesis on schema mismatch — dual-use exclusion goal satisfied behaviorally) MUST be preserved; logging is observability-only | HIGH | Add logging INSIDE the existing `except pydantic.ValidationError as exc:` branch — do NOT change control flow; do NOT add a fallback synthesis path; regression: feed `juno_relevance.classify()` a synthetic payload that triggers `ValidationError` and assert (a) the item is still excluded from the relevance-positive return list AND (b) `agent_runs.notes['haiku_validation_errors']` now contains the logged entry; test lives in `backend/tests/test_juno_relevance_classifier.py` |

**Architecture reference:**
- `milestones/v3.0-MILESTONE-AUDIT.md` — source of all 5 cleanup items with line-level references and triage by target version (v3.0.1 = items 1-5)
- `milestones/v3.0-phases/10-juno-defence-news-funnel/integration_smoke_results.md` — documents the 12:05 PT `canadian_procurement_md=""` behavior that CLEANUP-01 changes (row `a88271de-...`)
- `scheduler/agents/daily_summary.py` — production code edit target for CLEANUP-01 (line ~ inside `_build_juno_canadian_procurement_section`) + CLEANUP-03 (line ~762 dead-code block deletion)
- `scheduler/agents/juno_relevance.py` — Haiku 4.5 classifier edit target for CLEANUP-05 (extend existing `try/except pydantic.ValidationError` branch with structured `agent_runs.notes` logging)

**Feature reference:**
- v3.0 PROJECT.md "Current Milestone: v3.0.1" section — target features list + hard-parts enumeration + budget delta accepted
- v3.0.1 REQUIREMENTS.md CLEANUP-01..05 — observable acceptance criteria per requirement
- v3.0 milestone audit "Tech Debt Aggregate → v3.0.1 (recommended within 1-2 weeks)" list — items 1-5

---

## Progress

| Phase | Milestone | Plans | Status | Completed |
|-------|-----------|-------|--------|-----------|
| 1. Gold News Card + Web Feed | v2.0 | 6/6 | Complete | 2026-05-06 |
| 2. Ontario Law Ingestion | v2.0 | 1/1 | Complete | 2026-05-06 |
| 3. Ontario Stats Ingestion | v2.0 | 1/1 | Complete | 2026-05-06 |
| 4. Prune Cron + Ops Hardening | v2.0 | 1/1 | Complete | 2026-05-06 |
| 5. Foundation — Tabs + DB + Backend Stubs | v2.1 | 5/5 | Complete | 2026-05-19 |
| 6. Content Calendar | v2.1 | 5/5 | Complete | 2026-05-19 |
| 7. Weekly Viral Sweeper | v2.1 | 6/6 | Complete | 2026-05-19 |
| 8. UI Polish + Dead-Code Strip | v2.1 | 4/4 | Complete | 2026-05-19 |
| 9. Multi-Tenant Foundation | v3.0 | 5/5 | Complete | 2026-05-19 |
| 10. Juno Defence News Funnel | v3.0 | 5/5 | Complete | 2026-05-19 |
| 11. v3.0 Audit Cleanup Bundle | v3.0.1 | 0/? | Not started | - |

---

## Next Milestone

Not yet scoped beyond v3.0.1. After v3.0.1 ships, run `/gsd:new-milestone` to start v3.1 (questioning → research → requirements → roadmap).

Candidate v3.1+ features (deferred from v3.0 audit):

- Juno Content Calendar (Tab 2) — JUNO-CAL-v31
- Juno Weekly Viral Sweeper (Tab 3) — JUNO-SWEEP-v31; lock slot `juno_weekly_sweeper=1021` already reserved
- Per-company branding — TENANT-BRAND-v31 (Juno currently shows "Seva Mining" wordmark)
- Last-visited tenant for bare `/` redirect — Zustand `lastVisitedCompany` already populated as switch-action byproduct
- Per-tenant Anthropic API key
- Tier-2 defence RSS feeds — if Tier-1 signal insufficient after 2-4 weeks production

Candidate v3.2+ (scaling beyond N=2 tenants):

- `companies` DB table — TENANT-N-v32
