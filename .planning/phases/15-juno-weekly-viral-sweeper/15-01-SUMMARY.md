---
phase: 15-juno-weekly-viral-sweeper
plan: 01
subsystem: scheduler
tags: [juno, daily-summary, raw-sources-jsonb, defence-news, virality-substrate, d-03a, phase-15]

# Dependency graph
requires:
  - phase: 10-juno-defence-news-funnel
    provides: "_build_juno_defence_news_section / _build_juno_canadian_procurement_section / _build_juno_world_events_section + run_juno_daily_summary orchestrator + raw_sources_jsonb diagnostic payload"
provides:
  - "Three top-level keys (defence_news / canadian_procurement / world_events) persisted in every NEW Juno daily_summaries.raw_sources_jsonb as story-entry arrays"
  - "Extended return tuple shape (md, diag, entries) on all three Juno section builders — orchestrator threads entries into notes_dict"
  - "D-03b backfill-window guarantee: keys EXIST as [] even on refusal/no-substrate paths so sweeper raw.get(k, []) reads are unambiguous"
affects: [15-05-juno-weekly-sweeper-orchestrator, phase-15-virality-compute-substrate]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Section-builder return-tuple extension pattern: (md, diag) → (md, diag, entries) — preserves Phase 10 refusal-guard contract while adding substrate persistence as a sibling output"
    - "Outer-scope entries-list initialization pattern: defence_news_entries / procurement_entries / world_entries init to [] so per-section try/except leaves raw_sources_jsonb keys as empty lists (NOT undefined)"

key-files:
  created: []
  modified:
    - scheduler/agents/daily_summary.py
    - scheduler/tests/agents/test_juno_daily_summary.py

key-decisions:
  - "D-03a Option 1 applied: extend Phase 10 section builders to persist story entries alongside (md, diag); do NOT add a separate ingest pass. Single source of truth for the substrate, no duplicate ingest of feeds."
  - "Entry caps mirror prompt-input caps verbatim: defence entries[:30], procurement flat[:20], world survived[:25] — what gets persisted == what gets fed to Sonnet (no separate retention policy)."
  - "Procurement + world entries normalized to the same {source_name, title, summary, link, published} shape used by defence section so the sweeper's virality compute can treat the 3-sub-array union uniformly. World entries additionally retain {category, confidence} from the Haiku classifier output."
  - "Empty-entry sentinels: skipped-no-serpapi-client returns ('', diag, 0, []); no-world-ingest returns ('', diag, []); no-survivors returns ('', diag, []). All three keys ALWAYS present in raw_sources_jsonb after orchestrator runs (D-03b precondition)."

patterns-established:
  - "Section-builder entries lifting: any future _build_juno_* function that needs to feed downstream substrate reads should return entries as part of its tuple rather than mutating a sidecar — keeps orchestrator notes_dict assembly localized and testable."
  - "D-03a contract guard via inspect.getsource: regression test inspects function source for 'list[dict]' annotation AND notes_dict key writes — protects against future refactors that might silently drop the entries position."

requirements-completed: [JSWEEP-02]

# Metrics
duration: ~12min
completed: 2026-05-21
---

# Phase 15 Plan 01: Juno Substrate Writer Extension Summary

**Extended Phase 10's three `_build_juno_*_section` writers to persist Defence News + Canadian Procurement + World Events story entries into `raw_sources_jsonb` as three new top-level keys — unblocks Plan 15-05's sweeper virality compute substrate read.**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-05-21T00:30:00Z
- **Completed:** 2026-05-21T00:43:43Z
- **Tasks:** 2 (both executed in order)
- **Files modified:** 2 (1 production, 1 test)

## Accomplishments

- Three `_build_juno_*_section` functions in `scheduler/agents/daily_summary.py` extended to return `(md, diag, entries)` (defence/world) or `(md, diag, serpapi_count, entries)` (procurement) — entries are the post-filter story dicts that the sweeper's virality compute will consume.
- `run_juno_daily_summary` orchestrator updated at three callsites to unpack the new tuple shape; three entry-list variables initialized to `[]` at outer scope so a per-section exception leaves the key as `[]` (not undefined) in the persisted row.
- `notes_dict` assembly extended with three new top-level keys (`defence_news`, `canadian_procurement`, `world_events`) — each list of normalized story dicts (`source_name`, `title`, `summary`, `link`, `published`; world entries additionally retain `category` + `confidence` from the Haiku classifier).
- 3 new tests in `scheduler/tests/agents/test_juno_daily_summary.py` guard the contract: happy-path persistence, empty-substrate backfill-window behavior, and a source-introspection regression guard against future refactors.

## Task Commits

Each task was committed atomically with `--no-verify` (parallel-execution protocol per orchestrator instructions):

1. **Task 1: Extend three `_build_juno_*_section` signatures + rewire `run_juno_daily_summary` callsites + `notes_dict`** — `e06e570` (feat)
2. **Task 2: Add Juno daily_summary tests asserting `raw_sources_jsonb` persists the three story-array keys** — `8346318` (test)

_Note: Task 2 was a TDD task but production code was already in place from Task 1, so the TDD flow collapsed to a single GREEN commit (tests passed on first run against the post-Task-1 code) — the regression-guard intent of the TDD shape is preserved by the `test_section_builder_return_tuple_lengths` source-introspection assertion that would fail loudly if Task 1 was ever reverted._

## Files Created/Modified

- `scheduler/agents/daily_summary.py` — three Juno section builder functions extended (return entries alongside md+diag); `run_juno_daily_summary` notes_dict assembly persists three new top-level keys (`defence_news` / `canadian_procurement` / `world_events`).
- `scheduler/tests/agents/test_juno_daily_summary.py` — 3 new tests appended (substrate persistence happy-path, empty-substrate backfill, source-introspection regression guard); `inspect` module added to imports.

## Decisions Made

- **D-03a implementation path (Option 1 picked):** extended Phase 10's writers in-place rather than (a) adding a separate ingest pass that re-fetches feeds outside the section builders or (b) deferring the substrate fix into Plan 15-05 itself. Option 1 has the smallest blast radius — single source of truth for what's persisted, no risk of feed double-ingest, and Plan 15-05's sweeper module can stay narrowly scoped to the virality compute + Sonnet synthesis without also owning daily-summary writer mechanics.
- **Entry-shape normalization (planner discretion):** procurement (SerpAPI `flat` hits) + world (`survived` tuple list) entries are normalized to the defence-section's `{source_name, title, summary, link, published}` shape at write time, not at read time. This means the sweeper's virality compute can union the three sub-arrays and dedupe by URL without per-source-type field-name handling. World entries get two bonus fields (`category`, `confidence`) preserved from the Haiku classifier — sweeper can use these for downstream weighting if needed, or ignore them.
- **Cap-mirroring (deliberate):** entry caps match prompt-input caps exactly (defence 30, procurement 20, world 25). This means "what gets persisted == what gets fed to Sonnet" — simpler mental model than two-tier retention; raw_sources_jsonb size stays bounded; reproducibility of "which stories drove the markdown" stays clean.

## Deviations from Plan

None - plan executed exactly as written.

The plan's grep gates used single-quote string keys (`'defence_news':`) but the production file convention uses double-quote keys (`"defence_news":`); functionally identical, just a documentation typo in the plan. The acceptance-criteria grep was verified with `grep -cE "[\"']defence_news[\"']:"` returning `1` for each key — gate semantically passes.

**Total deviations:** 0
**Impact on plan:** Plan executed verbatim; D-03a contract satisfied; D-10 zero-regression contract preserved.

## Issues Encountered

- **Pre-existing ruff lint warning (out of scope, logged):** `scheduler/agents/daily_summary.py` line 57 has an unused import `HAIKU_MODEL` from `agents.juno_relevance`. Verified pre-existing via `git stash` round-trip — the warning predates this plan and was NOT introduced by the substrate extension. Not fixed (out-of-scope per execute-plan scope boundary). Will be picked up by a future cleanup pass or whichever plan touches that import block.

## D-10 Zero-Regression Evidence

**Seva files NOT touched by this plan:**

- `scheduler/agents/weekly_sweeper.py` — Seva sweeper module (untouched)
- `scheduler/agents/x_ingest.py` — shared X ingest (untouched)
- `scheduler/agents/juno_refusal_detector.py` — Phase 10 module reused verbatim (untouched)
- `scheduler/anthropic_client.py` — Phase 12 resolver consumed as-is (untouched)
- `scheduler/companies/seva/*` — N/A (Seva config lives in non-company-prefixed modules)
- `scheduler/tests/agents/test_daily_summary.py` — Seva daily-summary tests (untouched)
- `run_daily_summary` function (Seva orchestrator at line ~219+) — UNTOUCHED
- All `_assemble_*` Seva helpers — UNTOUCHED
- `DEFENCE_NEWS_SYSTEM_PROMPT` in `scheduler/companies/juno/prompts.py` — UNTOUCHED (this is a substrate-write change, NOT a prompt change)

**Grep evidence:**

```bash
$ git diff HEAD~2 HEAD scheduler/agents/daily_summary.py | grep -cE "^[+-].*_build_seva"
0   # Zero Seva-helper edits across both Task 1 + Task 2 commits

$ git status --porcelain scheduler/tests/agents/test_daily_summary.py
    # Empty output — test_daily_summary.py byte-identical (D-10 contract held)

$ cd scheduler && uv run pytest tests/agents/test_daily_summary.py -x | tail -3
54 passed in 1.85s   # Full Seva daily-summary suite passes byte-identically
```

**Full scheduler suite regression:**

```bash
$ cd scheduler && uv run pytest -q | tail -3
342 passed, 1 skipped, 4 warnings in 7.85s
```

342 passed (Phase 14 baseline was 323 + this plan adds 3 substrate tests + parallel agents 15-02 add 16 prompts/x_queries tests = ~342 total). All GREEN.

## D-03b Backfill Window Expectation

Existing Juno `daily_summaries` rows written between Phase 10 production go-live (2026-05-19 12:05 PT first fire after Phase 11 `JUNO_CRON_ENABLED=true` flip) and Phase 15 Plan 15-01 deploy will have NO `defence_news` / `canadian_procurement` / `world_events` keys in their `raw_sources_jsonb` — those rows only carry the Phase 10 diagnostic-counts payload.

After this plan ships to Railway scheduler service, NEW Juno daily-summary rows will start carrying the populated story arrays. The first Plan-15-05 Sunday-08:00-PT sweep that fires after deploy will see a thin substrate (only post-deploy rows have arrays) until ~7 days of new-schema rows accumulate. **Acceptable per CONTEXT D-03b:** sweeper will produce `status='partial'` with diagnostic note "substrate accumulating from new schema" for the first 0-2 sweeps post-deploy.

No data backfill required — old Juno rows stay untouched and the sweeper's `raw.get('defence_news', []) + raw.get('canadian_procurement', []) + raw.get('world_events', [])` read is defensive (empty list for missing keys).

## Outstanding Concerns

None expected — this plan is the dependency-of-record for Plan 15-05's virality compute substrate. Plan 15-05 can proceed knowing:

1. New Juno `daily_summaries` rows persist the three story-array keys (guarded by `test_run_juno_daily_summary_persists_defence_news_entries_in_raw_sources`).
2. Even on refusal / no-substrate paths, the keys exist as `[]` (guarded by `test_run_juno_daily_summary_persists_three_keys_even_on_empty_substrate`).
3. Future refactors that drop the entries position will fail loudly (guarded by `test_section_builder_return_tuple_lengths`).

The D-10 byte-identical contract for Seva is held — `test_daily_summary.py` unmodified, Seva daily-summary suite passes byte-identically.

## User Setup Required

None — no external service configuration required. The substrate-write change is transparent to operators; the existing Juno daily-summary cron (08:05 / 12:05 PT) will automatically start writing the extended payload on the next scheduler redeploy.

## Next Phase Readiness

- **Plan 15-05 (Wave 2) UNBLOCKED:** `juno_weekly_sweeper.py` orchestrator can now read `raw.get('defence_news', []) + raw.get('canadian_procurement', []) + raw.get('world_events', [])` and trust the result against post-deploy Juno rows.
- **No blockers** for the rest of Phase 15's Wave 1 (15-02 prompts/x_queries already merged in parallel; 15-03 frontend + 15-04 backend tests running in parallel — file-disjoint per orchestrator parallel-execution mandate).

## Self-Check: PASSED

- `scheduler/agents/daily_summary.py` modified — FOUND
- `scheduler/tests/agents/test_juno_daily_summary.py` modified — FOUND
- Commit `e06e570` — FOUND (Task 1)
- Commit `8346318` — FOUND (Task 2)
- Three top-level keys in notes_dict — VERIFIED (grep returns 1 for each)
- D-10 contract held — VERIFIED (`_build_seva` edit count = 0; `test_daily_summary.py` byte-identical)
- Full scheduler suite GREEN — VERIFIED (342 passed, 1 skipped)
- Lint clean on new test file — VERIFIED (ruff: All checks passed!)

---
*Phase: 15-juno-weekly-viral-sweeper*
*Completed: 2026-05-21*
