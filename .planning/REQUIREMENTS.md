# Requirements: Seva Mining v3.0.1

**Defined:** 2026-05-19
**Core Value:** Every piece of intelligence the dashboard surfaces must be genuinely valuable to the analyst for that company — gold-sector intelligence for Seva, defence-industry + world-events-relevant-to-defence intelligence for Juno. For v3.0.1, the operator's directive ("Juno should do the brief at 8am + 12pm PT every day") makes Canadian Procurement signal a both-fires deliverable rather than a morning-only artifact. Remaining four cleanups close documentation drift + dead code + observability gaps the v3.0 audit filed as non-blocking but worth landing before any v3.1 expansion work begins.

## v3.0.1 Requirements

Five cleanup items closing v3.0 audit follow-ups. Each requirement maps to exactly one phase (Phase 11 — single cleanup phase).

### v3.0 Audit Cleanup (CLEANUP)

Five small follow-ups from the v3.0 milestone audit (`milestones/v3.0-MILESTONE-AUDIT.md`). Independent of each other; can be batched in a single phase with parallel-where-possible waves.

- [x] **CLEANUP-01**: System removes the morning-only SerpAPI cost gate inside `scheduler/agents/daily_summary.py::_build_juno_canadian_procurement_section` (currently returns `("", {"skipped_reason": "non_morning_fire"}, 0)` when `is_morning_fire=False`). After change: BOTH daily Juno fires (08:05 PT + 12:05 PT) execute the 7 Canadian-procurement SerpAPI queries from `scheduler/companies/juno/serpapi.py::JUNO_SERPAPI_QUERIES`. Tests in `scheduler/tests/agents/test_juno_daily_summary.py` that assert noon-fire-skip-procurement MUST be updated in the same commit. Operator-facing UX: at 12:05 PT, the `/juno/` SummaryCard renders the full 3-section brief instead of the generic "No new Canadian defence procurement signals today" emptyFallback. Budget delta: Juno SerpAPI cost ~$5.25/mo → ~$8-9/mo (210 → ~420 calls/month, still inside $50/mo SerpAPI cap with ~$41 headroom).

- [x] **CLEANUP-02**: System refreshes the archived `milestones/v3.0-REQUIREMENTS.md` traceability table — rows DEF-01 through DEF-07 currently say "Scaffolded (Wave 0 / 10-01 — RED tests + ...; production lands Wave 1/Wave 2)" but Phase 10 VERIFICATION.md status: passed and the bullet checkboxes are correctly `[x]`. Update the descriptive text to "Complete (2026-05-19, plan 10-02 / 10-03 — <evidence>)" matching the format used for DEF-08..10. Pure documentation edit; no code touched.

- [x] **CLEANUP-03**: System removes the dead `run_juno_daily_summary` stub block at `scheduler/agents/daily_summary.py:762` (Phase 9 stub shadowed by Phase 10 live implementation at line 1150 via Python's last-wins semantics). Pre-removal: grep confirms no module imports the line-762 definition specifically (Python imports always resolve to last definition in a module). Post-removal: full scheduler pytest suite still GREEN; `scheduler/worker.py` `lazy import` of `run_juno_daily_summary` continues to resolve to the Phase 10 implementation. Reduces `daily_summary.py` line count by ~110 lines.

- [x] **CLEANUP-04**: System updates the frontmatter of both archived VALIDATION.md files in `milestones/v3.0-phases/`: `09-multi-tenant-foundation/09-VALIDATION.md` and `10-juno-defence-news-funnel/10-VALIDATION.md`. Flip `nyquist_compliant: false` → `true` and `wave_0_complete: false` → `true`. All Wave 0 RED tests across both phases flipped GREEN at consumer wave time (Phase 9 added 59 net passing scheduler tests; Phase 10 added 27 net passing frontend tests). The flags weren't updated at phase close — pure documentation drift. Two single-line edits per file.

- [x] **CLEANUP-05**: System adds structured logging to the Haiku 4.5 classifier in `scheduler/agents/juno_relevance.py` when `pydantic.ValidationError` is raised on the structured-output `messages.parse(output_format=DefenceRelevance)` call. Current behavior: `try/except` fail-closed (item excluded from synthesis — dual-use exclusion goal satisfied behaviorally). NEW behavior: same fail-closed contract + a log entry written to `agent_runs.notes` shape `{"haiku_validation_errors": [{"input_excerpt": "<first 200 chars of news item>", "error_type": "<exc class name>", "error_msg": "<first 200 chars of exc str>"}]}`. Logging is observability-only — fail-closed contract MUST be preserved. Optional: tune Haiku `temperature` parameter (currently default ~1.0) to reduce schema-mismatch frequency; planner picks whether this lands in this requirement or defers.

## v3.1+ Requirements

Deferred to future v3.x release. Tracked but NOT in v3.0.1 roadmap.

### Juno Expansion
- **JUNO-CAL-v31**: Juno Content Calendar (Tab 2) — same paper-planner UI as Seva, scoped to Juno's calendar_items rows
- **JUNO-SWEEP-v31**: Juno Weekly Viral Sweeper (Tab 3) — defence-sector X API queries + virality compute; lock slot `juno_weekly_sweeper=1021` already reserved in Phase 9
- **TENANT-BRAND-v31**: Per-company branding (logos, color palettes, wordmarks) — Juno currently shows "Seva Mining" wordmark on `/juno/*` pages
- **TENANT-VISITED-v31**: Last-visited tenant for bare `/` redirect — Zustand `lastVisitedCompany` already populated as switch-action byproduct in Phase 9
- **TENANT-KEY-v31**: Per-tenant Anthropic API key — currently single shared key

### Defence Sector Hardening
- **DEF-TIER2-v31**: Tier-2 defence RSS feeds (Defense Daily, Inside Defense, National Defense Magazine, Defense Industry Daily, Shephard, Defense One) — if Tier-1 signal proves insufficient after first 2-4 weeks of production fires

### v3.2+ Scaling
- **TENANT-N-v32**: `companies` DB table replacing hardcoded `CHECK company_id IN ('seva','juno')` constraint — when scaling beyond N=2 tenants

## Out of Scope

Explicitly excluded from v3.0.1. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Any new Juno features beyond the 5 audit cleanups | This is a patch release; new features go in v3.1 |
| Per-company branding / Juno wordmark | TENANT-BRAND-v31 — deferred to v3.1 |
| Juno Calendar / Juno Sweeper | JUNO-CAL-v31 / JUNO-SWEEP-v31 — deferred to v3.1 |
| Tier-2 defence RSS feeds | DEF-TIER2-v31 — wait for Tier-1 production signal data first |
| Companies DB table | TENANT-N-v32 — deferred to v3.2+ scaling milestone |
| Per-tenant Anthropic API key | TENANT-KEY-v31 — deferred to v3.1 |
| Operational/tactical intelligence in Juno briefs | Hard prohibition — Anthropic content-policy boundary preserved from v3.0 |
| Equity/financial signals on defence primes | Explicit anti-feature carried forward from v3.0 |
| Mobile-responsive UI | Single-user desktop constraint preserved from v1.0 |
| Autoposting to X/IG/LinkedIn | Hard prohibition per CLAUDE.md |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| CLEANUP-01 | Phase 11 | Complete |
| CLEANUP-02 | Phase 11 | Complete |
| CLEANUP-03 | Phase 11 | Complete |
| CLEANUP-04 | Phase 11 | Complete |
| CLEANUP-05 | Phase 11 | Complete |

**Coverage:**
- v3.0.1 requirements: 5 total (5 CLEANUP)
- Mapped to phases: 5 (all → Phase 11)
- Unmapped: 0 ✓

---
*Requirements defined: 2026-05-19*
*Last updated: 2026-05-20 — Phase 11 complete; all 5 CLEANUP requirements satisfied (verifier 5/5 PASS)*
