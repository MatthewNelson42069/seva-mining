---
phase: 15
slug: juno-weekly-viral-sweeper
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-20
source: 15-RESEARCH.md §5 Validation Architecture (Nyquist Dimension 8)
---

# Phase 15 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Crystallized from `15-RESEARCH.md` §5. Updated mid-execution as tests land.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Backend framework** | `pytest` + `pytest-asyncio` (existing — used by `backend/tests/` + `scheduler/tests/`) |
| **Frontend framework** | `Vitest` + React Testing Library (existing — used by `frontend/src/pages/__tests__/`) |
| **Config files** | `scheduler/tests/conftest.py`, `backend/tests/conftest.py`, `frontend/vitest.config.ts` — all exist |
| **Quick run command (scheduler)** | `cd scheduler && uv run pytest tests/agents/test_juno_weekly_sweeper.py -x` |
| **Quick run command (backend)** | `cd backend && uv run pytest tests/test_weekly_sweeps_cross_tenant.py -x` |
| **Quick run command (frontend)** | `cd frontend && npm test -- WeeklyViralSweeperPage.test.tsx` |
| **Full suite command** | `cd scheduler && uv run pytest -q && cd ../backend && uv run pytest -q && cd ../frontend && npm test` |
| **Estimated runtime** | ~30-45 seconds (full suite) |

---

## Sampling Rate

- **After every task commit:** Run the quick run command for the file/area changed (scheduler / backend / frontend)
- **After every plan wave:** Run the full suite — all three test suites must be GREEN
- **Before `/gsd:verify-work`:** Full suite GREEN + `scripts/verify-tenant-isolation.sh` exit 0 + `scripts/verify-anthropic-resolver.sh` exit 0
- **Max feedback latency:** ~45 seconds (full suite)

---

## Per-Requirement Verification Map

| Req ID | Behavior to Verify | Test Type | Automated Command | New File? | Plan |
|--------|--------------------|-----------|-------------------|-----------|------|
| **JSWEEP-01** | When `JUNO_SWEEPER_CRON_ENABLED` unset/false, `build_scheduler()` registers no `juno_weekly_sweeper` job. When `=true`, exactly one is registered at lock 1021 with Sunday 08:00 PT trigger. | unit (worker scheduler) | `pytest scheduler/tests/test_worker.py::test_juno_sweeper_cron_disabled_by_default` + `::test_juno_sweeper_cron_enabled_registers_job` | extends existing | 15-06 |
| **JSWEEP-02 (a)** | `JUNO_SWEEPER_X_QUERY` constant is non-empty string ≤512 chars containing `from:` operators + `-is:retweet lang:en` filter | unit | `pytest scheduler/tests/companies/test_juno_x_queries.py::test_query_constant_valid` + `::test_query_length_within_basic_tier_cap` | NEW | 15-02 |
| **JSWEEP-02 (b)** | `run_juno_weekly_sweeper()` happy-path: X ingest → virality compute (3-sub-array union, deduped by canonical URL) → Sonnet call | unit | `pytest scheduler/tests/agents/test_juno_weekly_sweeper.py::test_run_happy_path` + `::test_virality_compute_three_sub_array_union` + `::test_virality_compute_dedupes_by_canonical_url` | NEW | 15-05 |
| **JSWEEP-03 (a)** | Idempotency filter includes `'partial'`: when recent Juno sweep with `status='partial'` exists, second invocation skips without writing duplicate row | unit | `pytest scheduler/tests/agents/test_juno_weekly_sweeper.py::test_idempotency_skip_when_partial_exists` + `::test_idempotency_skip_when_completed_exists` + `::test_idempotency_skip_when_running_exists` | NEW | 15-05 |
| **JSWEEP-03 (b)** | `weekly_sweeps` row written with `company_id='juno'` only | unit | `pytest scheduler/tests/agents/test_juno_weekly_sweeper.py::test_persisted_row_has_company_id_juno` | NEW | 15-05 |
| **JSWEEP-04 (a)** | Sonnet call uses `get_anthropic_client('juno', ...)` hardcoded literal (Phase 12 D-07) | unit | `pytest scheduler/tests/agents/test_juno_weekly_sweeper.py::test_anthropic_client_called_with_juno_literal` | NEW | 15-05 |
| **JSWEEP-04 (b)** | `JUNO_SWEEPER_SYSTEM_PROMPT` contains verbatim anti-tactical clause (string-equality contract with Phase 10's `DEFENCE_NEWS_SYSTEM_PROMPT`) | unit (property) | `pytest scheduler/tests/companies/test_juno_prompts.py::test_anti_tactical_clause_in_sweeper_prompt_verbatim` | NEW | 15-02 |
| **JSWEEP-04 (c)** | Refusal-detector: first refusal → retry-with-nudge; second refusal → `status='partial'` (Phase 10 D-05 pattern reused verbatim) | unit | `pytest scheduler/tests/agents/test_juno_weekly_sweeper.py::test_refusal_first_attempt_retries` + `::test_refusal_second_attempt_sets_partial` | NEW | 15-05 |
| **JSWEEP-05** | After D-08 short-circuit removal, `<WeeklyViralSweeperPage />` at `/juno/sweeper` renders the same component path as `/seva/sweeper`. Empty-state copy renders when no sweeps. | unit (React) | `npm test -- WeeklyViralSweeperPage.test.tsx --testNamePattern "renders for juno"` | NEW | 15-03 |
| **JSWEEP-06 (a)** | Frontend cross-tenant isolation: TanStack Query keys differ between `/juno/sweeper` and `/seva/sweeper`; cache for one company does not bleed into the other | RTL | `npm test -- WeeklyViralSweeperPage.test.tsx --testNamePattern "tenant isolation"` | NEW | 15-03 |
| **JSWEEP-06 (b)** | Backend tenant existence isolation: GET `/api/juno/weekly-sweeps/{seva_uuid}` returns 404 (NOT 403). Cross-tenant access via list endpoint returns empty for the wrong tenant. | integration | `pytest backend/tests/test_weekly_sweeps_cross_tenant.py -x` (all tests) | NEW | 15-04 |

---

## Plan → Test Mapping

| Plan | New Test Files | Existing Files Extended | Estimated Tests |
|------|----------------|--------------------------|------------------|
| 15-01 | `scheduler/tests/agents/test_juno_daily_summary.py` (extend) | — | +3-4 tests (substrate-keys persistence) |
| 15-02 | `scheduler/tests/companies/test_juno_prompts.py` (NEW) + `scheduler/tests/companies/test_juno_x_queries.py` (NEW) | — | +8 prompt tests + +8 query tests |
| 15-03 | `frontend/src/pages/__tests__/WeeklyViralSweeperPage.test.tsx` (NEW) | — | +3-5 RTL tests |
| 15-04 | `backend/tests/test_weekly_sweeps_cross_tenant.py` (NEW) | — | +3 cross-tenant tests |
| 15-05 | `scheduler/tests/agents/test_juno_weekly_sweeper.py` (NEW) | — | +12+ unit tests |
| 15-06 | — | `scheduler/tests/test_worker.py` (extend) | +4 worker registration tests |
| 15-07 | `voice_calibration_uat.md` (NEW — operator artifact, not a pytest test) | — | n/a (operator UAT) |

**Total expected new tests:** ~40-45 across scheduler + backend + frontend.

---

## Wave 0 Gaps

The following test files do NOT exist at phase-start and are scheduled to be created by their corresponding plans:

- [ ] `scheduler/tests/agents/test_juno_weekly_sweeper.py` — JSWEEP-02, -03, -04 unit tests (~12+ tests) — owned by Plan 15-05
- [ ] `scheduler/tests/companies/test_juno_prompts.py` — anti-tactical clause string-equality + 7 other prompt invariants — owned by Plan 15-02
- [ ] `scheduler/tests/companies/test_juno_x_queries.py` — query validity + 512-char limit + handle-set + cashtag-absence assertions — owned by Plan 15-02
- [ ] `backend/tests/test_weekly_sweeps_cross_tenant.py` — JSWEEP-06 backend isolation (mirrors Phase 14's `test_calendar_cross_tenant.py`) — owned by Plan 15-04
- [ ] `frontend/src/pages/__tests__/WeeklyViralSweeperPage.test.tsx` — JSWEEP-05 + JSWEEP-06 frontend isolation (mirrors Phase 14's `ContentCalendarPage.test.tsx`) — owned by Plan 15-03

Existing test files extended (NOT new):

- `scheduler/tests/test_worker.py` — EXTEND with `JUNO_SWEEPER_CRON_ENABLED` env-gate tests (Plan 15-06)
- `scheduler/tests/agents/test_juno_daily_summary.py` — EXTEND with `raw_sources_jsonb` story-array-key persistence tests (Plan 15-01)

**Test framework dependencies:** All already present (pytest, pytest-asyncio, vitest, React Testing Library). No new packages needed.

---

## Refusal-Detector Test Contract (Phase 10 D-05 reused)

Phase 15 reuses Phase 10's `juno_refusal_detector` module verbatim. The sweeper-side refusal contract:

- **First Sonnet call** → output passed through `detect_refusal()` (or equivalent function name) — if refusal substring matched, retry once with framing-nudge prepended to user prompt
- **Second-attempt refusal OR malformed JSON** → `status='partial'`, persist row with diagnostic note in `notes_md`
- **Test boundary:** Phase 15's tests verify the WIRING (refusal-detector is called, retry happens, partial-status persists). The detector logic itself is Phase 10's test responsibility, not duplicated here.

---

## D-10 Zero-Regression Tests

Phase 15 makes ZERO Seva-side changes. Validation explicitly checks:

| File | Expected Diff |
|------|--------------|
| `scheduler/agents/weekly_sweeper.py` | byte-identical (only Seva sweeper module untouched) |
| `scheduler/agents/x_ingest.py` | byte-identical (Juno imports `fetch_top_x_posts` as-is) |
| `scheduler/agents/juno_refusal_detector.py` | byte-identical (Phase 10 module reused verbatim) |
| `scheduler/anthropic_client.py` | byte-identical (Phase 12 resolver consumed as-is) |
| `scheduler/companies/juno/feeds.py` + `serpapi.py` | byte-identical (daily-summary substrates; sweeper independent) |
| `backend/app/queries/scoped.py` + `scheduler/queries/scoped.py` | byte-identical |
| Existing v2.1 + v3.0 + v3.1 Seva tests | all pass byte-identically |

`git status --porcelain` after Phase 15 lands should show ONLY new Juno files + extensions to existing Juno or worker test files — NEVER Seva files in the modified list.

---

## Phase Exit Criteria

Phase 15 is considered validated when:

1. All 6 JSWEEP requirements have ≥1 passing automated test (see Per-Requirement Verification Map above)
2. Full test suite GREEN: scheduler (target: 323+ pass baseline + ~16 new), backend (target: 188+ baseline + ~3 new), frontend (target: 178+ baseline + ~3-5 new)
3. `scripts/verify-tenant-isolation.sh` exit 0
4. `scripts/verify-anthropic-resolver.sh` exit 0
5. `git status --porcelain scheduler/agents/weekly_sweeper.py` empty (D-10 byte-identical Seva sweeper)
6. Operator voice UAT APPROVED (5-6 criteria from CONTEXT §Voice UAT criteria + 15-07 plan body)
7. `voice_calibration_uat.md` created with operator's per-criterion verdict ledger

After exit criteria met + operator flips `JUNO_SWEEPER_CRON_ENABLED=true` in Railway: first real production sweep fires next Sunday 08:00 PT America/Los_Angeles.

---

*Phase: 15-juno-weekly-viral-sweeper*
*Validation strategy crystallized: 2026-05-20*
*Source: 15-RESEARCH.md §5 Validation Architecture (Nyquist Dimension 8)*
