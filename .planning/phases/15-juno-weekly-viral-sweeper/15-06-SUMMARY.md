---
phase: 15-juno-weekly-viral-sweeper
plan: 06
subsystem: scheduler
tags: [juno, weekly-sweeper, cron, apscheduler, env-gate, phase-15, wave-2]

# Dependency graph
requires:
  - phase: 15-05
    provides: "scheduler/agents/juno_weekly_sweeper.py::run_juno_weekly_sweeper async entry point (Wave 2 prereq — lazy-imported inside _make_juno_weekly_sweeper_job factory)"
  - phase: 10-juno-defence-news-funnel
    provides: "JUNO_CRON_ENABLED env-gate pattern verbatim (worker.py:458 — Phase 15 mirrors structurally for JUNO_SWEEPER_CRON_ENABLED)"
  - phase: 09-multi-tenant-foundation
    provides: "JOB_LOCK_IDS['juno_weekly_sweeper'] = 1021 reservation (D-01 Phase 9 — slot-only until Phase 15 wires registration)"
provides:
  - "scheduler/worker.py — new _make_juno_weekly_sweeper_job(engine) factory mirroring Phase 10's _make_juno_daily_summary_job pattern (advisory-lock wrap + lazy import)"
  - "scheduler/worker.py — JUNO_SWEEPER_CRON_ENABLED-gated registration block in build_scheduler() at Sunday 08:00 PT America/Los_Angeles under lock 1021"
  - "scheduler/worker.py — _validate_env extended to log JUNO_SWEEPER_CRON_ENABLED status at boot (parity with JUNO_CRON_ENABLED visibility)"
  - "scheduler/tests/test_worker.py — 4 new tests covering: cron disabled by default, cron enabled registers Sun 08:00 PT job, two Juno gates independent (typo mitigation), lock 1021 + OPS-02 uniqueness sanity check"
affects:
  - 15-07-PLAN  # voice UAT runs against this plan's cron registration once operator flips JUNO_SWEEPER_CRON_ENABLED=true in Railway

# Tech tracking
tech-stack:
  added: []  # zero new dependencies — pure scheduler wiring
  patterns:
    - "Env-gated cron registration via os.getenv (NOT Settings field) per RESEARCH §6 Open Q 4 LOCKED — pattern parity with Phase 10's JUNO_CRON_ENABLED gate is the chosen path; behavior identical, no scheduler/config.py edit needed"
    - "Job factory mirrors per-company pattern (Phase 9 D-01): factory closes over engine, lazy-imports the entry point inside the inner async job(), wraps in with_advisory_lock(conn, lock_id, name, run_fn)"
    - "Quote-style parity for grep consistency: new juno_weekly_sweeper CronTrigger uses single-quoted day_of_week='sun' matching Seva's existing weekly_sweeper block (so `grep -c \"day_of_week='sun'\" worker.py` returns 3: Seva + Juno + the JOB_LOCK_IDS comment-line preview)"
    - "Boot-time gate visibility via _validate_env: JUNO_SWEEPER_CRON_ENABLED logged as INFO at every Railway restart so misconfig is visible without grepping the APScheduler job-registered log lines"

key-files:
  created: []  # zero new files — surgical extension of existing files only
  modified:
    - scheduler/worker.py  # +78/-1 LOC net (factory + registration block + docstring + _validate_env log)
    - scheduler/tests/test_worker.py  # +150 LOC appended (4 new tests)

key-decisions:
  - "Use os.getenv pattern, NOT Settings field (RESEARCH §6 Open Q 4 LOCKED): mirrors Phase 10 JUNO_CRON_ENABLED verbatim. Avoids touching scheduler/config.py; behavior is byte-identical to a Settings-field implementation; CI grep gate stays focused on env-var name spelling."
  - "Quote-style is single-quoted day_of_week='sun' matching Seva's existing weekly_sweeper CronTrigger (worker.py line 502). Grep gate `grep -c \"day_of_week='sun'\"` now returns 3 (Seva + Juno + JOB_LOCK_IDS-comment lookalike); plan acceptance criterion expected 2 but the actual count includes a comment-line mention of weekly_sweeper's existing pattern (preexisting; not a new addition)."
  - "Lock 1021 NOT modified in JOB_LOCK_IDS dict — already reserved Phase 9 D-01. Single grep line `\"juno_weekly_sweeper\": 1021` matches in worker.py (unchanged); OPS-02 uniqueness assertion at module import still passes (6 unique values across midday_digest/daily_summary/daily_summary_prune/weekly_sweeper/juno_daily_summary/juno_weekly_sweeper)."
  - "Same-time fire as Seva weekly_sweeper (Sun 08:00 PT America/Los_Angeles) is intentional — independent advisory locks (1019 Seva vs 1021 Juno) isolate them; max_instances=1 is per-job-id, not global. CONTEXT D-01 + RESEARCH 'Hard parts' P5 confirm safe."
  - "Boot-time env logging extension: added a 6-line INFO block inside _validate_env (after the ANTHROPIC_RESOLVER_STRICT log line) reading JUNO_SWEEPER_CRON_ENABLED status via os.getenv. Parity with Phase 12's per-tenant Anthropic key log block."

patterns-established:
  - "v3.1 Phase 15 cron registration shape: os.getenv env gate → if/else block with ENABLED INFO log + add_job (with explicit max_instances=1 + misfire_grace_time=1800) vs DISABLED INFO log explaining the flip path → reusable shape if a third tenant ever lands a weekly cron"
  - "v3.1 Phase 15 worker test fixture pattern: `patch.dict(os.environ, {'JUNO_CRON_ENABLED': '...', 'JUNO_SWEEPER_CRON_ENABLED': '...'})` combo lets a single test exercise the independence of multiple env gates simultaneously; mirrors the Phase 10 fixture but with two gates instead of one"
  - "Test-existing-tests-unchanged invariant: the pre-existing `test_juno_weekly_sweeper_NOT_registered` test (which asserts the sweeper is absent under JUNO_CRON_ENABLED=true alone) STILL passes after Phase 15 because its env context does NOT set JUNO_SWEEPER_CRON_ENABLED — so the gate defaults to disabled and the sweeper stays absent. D-10 byte-identical contract held without test edits."

requirements-completed: [JSWEEP-01]

# Metrics
duration: ~3min
completed: 2026-05-21
---

# Phase 15 Plan 06: Juno Weekly Sweeper Cron Registration Summary

**Wired Plan 15-05's `run_juno_weekly_sweeper` orchestrator into APScheduler via a new `_make_juno_weekly_sweeper_job(engine)` factory + JUNO_SWEEPER_CRON_ENABLED-gated `scheduler.add_job(...)` block in `build_scheduler()` at Sunday 08:00 PT America/Los_Angeles under lock 1021. Mirrors Phase 10's JUNO_CRON_ENABLED precedent verbatim — `os.getenv` pattern (NOT Settings field per RESEARCH §6 Open Q 4 LOCKED). Production deploys default to DISABLED; operator flips the env var after Plan 15-07 voice UAT. Added 4 new worker tests (cron disabled by default + cron enabled registers Sun 08:00 PT job + two Juno gates independent + lock 1021 OPS-02 sanity); scheduler suite 359 → 363 passed (+4). D-10 byte-identical contract held: Seva weekly_sweeper registration UNCHANGED, existing JUNO_CRON_ENABLED block UNCHANGED, JOB_LOCK_IDS dict UNCHANGED.**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-05-21T01:00:16Z
- **Completed:** 2026-05-21T01:03:21Z
- **Tasks:** 2 (both committed atomically with --no-verify per Wave 2 parallel-execution protocol)
- **Files created:** 0
- **Files modified:** 2 (scheduler/worker.py + scheduler/tests/test_worker.py)

## Module Changes: scheduler/worker.py

### Insertion 1 — `_make_juno_weekly_sweeper_job(engine)` factory

Placed AFTER `_make_juno_daily_summary_job` (line ~273), BEFORE `_make_daily_summary_prune_job`. Mirrors Phase 10's factory verbatim — swaps the lock ID (1021 vs 1020) and the inner entry point (`run_juno_weekly_sweeper` vs `run_juno_daily_summary`). Closes over `engine`, lazy-imports the entry point so worker.py module import does NOT pay the juno_weekly_sweeper module's import cost on Railway boot.

```python
def _make_juno_weekly_sweeper_job(engine):
    """v3.1 Phase 15 (JSWEEP-01). Mirrors _make_juno_daily_summary_job exactly..."""

    async def job():
        async with engine.connect() as conn:
            from agents.juno_weekly_sweeper import run_juno_weekly_sweeper  # lazy
            await with_advisory_lock(
                conn,
                JOB_LOCK_IDS["juno_weekly_sweeper"],
                "juno_weekly_sweeper",
                run_juno_weekly_sweeper,
            )

    return job
```

### Insertion 2 — JUNO_SWEEPER_CRON_ENABLED-gated registration block

Placed AFTER the Seva `weekly_sweeper` registration (line ~509), BEFORE the `CONTENT_CRON_AGENTS` loop (line ~511). Identical structural shape to Phase 10's JUNO_CRON_ENABLED block (worker.py:458) — env-var read via `os.getenv`, if/else with distinct INFO log lines, `scheduler.add_job(...)` with explicit `max_instances=1` + `misfire_grace_time=1800`.

```python
juno_sweeper_cron_enabled = os.getenv("JUNO_SWEEPER_CRON_ENABLED", "false").lower() == "true"
if juno_sweeper_cron_enabled:
    logger.info(
        "juno_weekly_sweeper cron ENABLED via JUNO_SWEEPER_CRON_ENABLED=true env var"
    )
    scheduler.add_job(
        _make_juno_weekly_sweeper_job(engine),
        trigger=CronTrigger(
            day_of_week='sun',
            hour=8,
            minute=0,
            timezone='America/Los_Angeles',
        ),
        id="juno_weekly_sweeper",
        name="Weekly Viral Sweeper — Juno — Sun 08:00 America/Los_Angeles",
        max_instances=1,
        misfire_grace_time=1800,
    )
else:
    logger.info(
        "juno_weekly_sweeper cron DISABLED — set JUNO_SWEEPER_CRON_ENABLED=true in "
        "Railway env after voice UAT approves "
        "(.planning/phases/15-juno-weekly-viral-sweeper/voice_calibration_uat.md)"
    )
```

### Insertion 3 — _validate_env boot-time log line

Added a 6-line INFO block to `_validate_env` (after the existing `ANTHROPIC_RESOLVER_STRICT` log line) reading `JUNO_SWEEPER_CRON_ENABLED` via `os.getenv` and logging its boot status. Mirrors the Phase 10 / Phase 12 env-var-visibility pattern.

```python
juno_sweeper_cron_enabled = os.getenv("JUNO_SWEEPER_CRON_ENABLED", "false").lower() == "true"
logger.info(
    "ENV JUNO_SWEEPER_CRON_ENABLED: %s",
    "true (juno_weekly_sweeper cron WILL register at Sun 08:00 PT)"
    if juno_sweeper_cron_enabled
    else "false (juno_weekly_sweeper cron disabled — flip after voice UAT)",
)
```

### Insertion 4 — `build_scheduler` docstring update

Updated the bulleted list of cron jobs to mention `juno_weekly_sweeper` (env-gated) alongside `juno_daily_summary`. Removed the now-outdated "juno_weekly_sweeper (lock 1021) is reserved in JOB_LOCK_IDS but NOT registered as a job — slot-only per v3.0 Phase 9 D-01" sentence (post-Phase 15, it IS registered when the env gate is flipped).

## Module Changes: scheduler/tests/test_worker.py

Appended 4 new tests to the end of the file (+150 LOC) inside a `# v3.1 Phase 15 — JUNO_SWEEPER_CRON_ENABLED env-gate tests (JSWEEP-01)` section divider. Mirrors the existing JUNO_CRON_ENABLED test fixture shape verbatim — same `patch("worker._read_schedule_config")` + `patch.dict(os.environ, ...)` + `try/finally` cleanup pattern.

| Test | Asserts |
|------|---------|
| `test_juno_sweeper_cron_disabled_by_default` | With `JUNO_SWEEPER_CRON_ENABLED=false` (and `JUNO_CRON_ENABLED=false`), `scheduler.get_job("juno_weekly_sweeper")` returns None and the job ID is absent from the job list |
| `test_juno_sweeper_cron_enabled_registers_job` | With both `JUNO_CRON_ENABLED=true` AND `JUNO_SWEEPER_CRON_ENABLED=true`, the sweeper job is registered with `day_of_week='sun'`, `hour=8`, `minute=0`, `timezone=America/Los_Angeles`. Total job count is 5: `{daily_summary, daily_summary_prune, weekly_sweeper, juno_daily_summary, juno_weekly_sweeper}` |
| `test_juno_sweeper_cron_independent_of_juno_daily_summary_gate` | With `JUNO_CRON_ENABLED=false` but `JUNO_SWEEPER_CRON_ENABLED=true`: the sweeper IS registered, the daily summary is NOT registered. Proves the two env gates are independent (typo mitigation). |
| `test_juno_sweeper_lock_id_is_1021_and_unique` | `JOB_LOCK_IDS["juno_weekly_sweeper"] == 1021` AND `len(set(JOB_LOCK_IDS.values())) == len(JOB_LOCK_IDS)` (OPS-02 sanity check; lock 1021 was reserved Phase 9 D-01 and Phase 15 does NOT modify the dict) |

## Test Pass Counts

| Suite | Before (Plan 15-05 close) | After (Plan 15-06 close) | Delta |
|-------|---------------------------|--------------------------|-------|
| Full scheduler suite | 359 passed, 1 skipped | **363 passed, 1 skipped** | **+4** |
| `test_worker.py` only | 39 passed | **43 passed** | **+4** |
| Existing worker tests (byte-identical) | 39 passed | 39 passed | 0 |
| `test_juno_weekly_sweeper_NOT_registered` (pre-existing test) | PASSED | PASSED | 0 (its env context doesn't set JUNO_SWEEPER_CRON_ENABLED, so the gate stays default-disabled and the sweeper stays absent — D-10 byte-identical contract held without test edits) |

Pre-existing 4 `RuntimeWarning` on `daily_summary_prune.py` AsyncMock unrelated to this plan (verified in Plan 15-02/15-05 summaries).

## Task Commits

Each task committed atomically with `--no-verify` per Wave 2 parallel-execution protocol:

1. **Task 1: feat(15-06): register juno_weekly_sweeper cron with JUNO_SWEEPER_CRON_ENABLED gate** — `343c711` (scheduler/worker.py +82/-4 LOC)
2. **Task 2: test(15-06): add 4 tests for JUNO_SWEEPER_CRON_ENABLED env-gate** — `ec4ade7` (scheduler/tests/test_worker.py +150 LOC)

## Decisions Made

- **Use os.getenv pattern, NOT Settings field** (RESEARCH §6 Open Q 4 LOCKED) — pattern parity with Phase 10 wins; behavior is byte-identical to a Settings-field implementation; CI grep gate stays focused on the env-var name spelling; no scheduler/config.py edit needed.
- **Same-time fire as Seva weekly_sweeper (Sun 08:00 PT) is intentional** — independent advisory locks (1019 Seva vs 1021 Juno) isolate them; `max_instances=1` is per-job-id not global. CONTEXT D-01 + RESEARCH "Hard parts" P5 explicitly confirm this is safe. Operator does NOT need to stagger the Juno sweeper away from Seva's time.
- **Lock 1021 reservation NOT modified in JOB_LOCK_IDS dict** — already reserved Phase 9 D-01; OPS-02 uniqueness assertion at module import still passes with 6 unique values; Phase 15 wires the registration WITHOUT touching the dict.
- **Quote-style parity for grep consistency** — new juno_weekly_sweeper CronTrigger uses single-quoted `day_of_week='sun'` matching Seva's existing weekly_sweeper block (line 502). `grep -c "day_of_week='sun'"` now returns 3 (Seva + Juno + a comment-line preview in the JUNO_CRON_ENABLED comment block); plan's acceptance criterion expected 2 but the third match is a pre-existing comment-line reference (not a new addition).
- **Boot-time env logging via _validate_env extension** — added a 6-line INFO block reading `JUNO_SWEEPER_CRON_ENABLED` status; parity with Phase 12's per-tenant Anthropic key log block. Surfaces gate status at every Railway restart so misconfig is visible without grepping the APScheduler job-registered log lines.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `grep -c "day_of_week='sun'"` returns 3, not 2 as plan acceptance criterion expected**
- **Found during:** Task 1 acceptance verification (grep gate check)
- **Issue:** Plan acceptance criterion stated `grep -c "day_of_week='sun'"` should return 2 (Seva existing + new Juno). Actual count: 3. Investigation: the third match is a pre-existing comment-line reference inside the JUNO_CRON_ENABLED comment block at worker.py (pre-existing before Phase 15). Not a new addition, not a duplicate registration.
- **Fix:** No production-code change required. Documented in this SUMMARY's Decisions section. The substantive invariants all hold: exactly 2 `scheduler.add_job(...)` calls reference `day_of_week='sun'` (Seva at line ~502 + new Juno block); only ONE call site has `id="juno_weekly_sweeper"` (verified via separate grep gate).
- **Files modified:** None (test-expectation alignment with pre-existing comment text).
- **Verification:** All 4 new tests pass; all 39 existing tests pass byte-identically; OPS-02 lock-uniqueness assertion holds.

**Total deviations:** 1 auto-fixed (grep-expectation alignment with pre-existing comment text; not a production-code issue). No plan re-scope, no test count change, no Sonnet/Anthropic refactoring needed.

## Authentication Gates

None encountered. This plan touches scheduler wiring + tests only — no API key resolution, OAuth flow, or interactive credential prompts in the execution path. The operator's post-merge `JUNO_SWEEPER_CRON_ENABLED=true` Railway flip is documented but is OUT of band for this plan (gated by Plan 15-07 voice UAT).

## D-10 Zero-Regression Evidence

**Protected files BYTE-IDENTICAL after plan:**

```bash
$ git status --porcelain \
    scheduler/agents/juno_weekly_sweeper.py \
    scheduler/agents/weekly_sweeper.py \
    scheduler/agents/x_ingest.py \
    scheduler/config.py \
    scheduler/companies/juno/prompts.py \
    scheduler/companies/juno/x_queries.py \
    scheduler/agents/daily_summary.py \
    scheduler/anthropic_client.py \
    scheduler/queries/scoped.py
# (empty output — all 9 protected files untouched)
```

**Seva regression GREEN:**

```bash
$ cd scheduler && uv run pytest tests/test_worker.py tests/test_weekly_sweeper.py tests/agents/test_juno_daily_summary.py -x
# All pass — Seva weekly_sweeper.py + juno_daily_summary tests byte-identical
```

**Full scheduler regression:**

```bash
$ cd scheduler && uv run pytest -q | tail -3
363 passed, 1 skipped, 4 warnings in 10.39s
```

363 passed (359 baseline + 4 new = 363). Perfect match.

**CI grep gates PASS:**

```bash
$ bash scripts/verify-tenant-isolation.sh
PASS — all tenant-scoped selects routed through queries/scoped.py
$ bash scripts/verify-anthropic-resolver.sh
PASS — all Anthropic client instantiations routed through scheduler/anthropic_client.py
```

## Grep Gates Verification

| Gate | Expected | Actual | Pass |
|------|----------|--------|------|
| `grep -c "def _make_juno_weekly_sweeper_job" scheduler/worker.py` | == 1 | 1 | yes |
| `grep -c "_make_juno_weekly_sweeper_job(engine)" scheduler/worker.py` | == 1 | 1 (factory call site in build_scheduler) | yes |
| `grep -c "_make_juno_weekly_sweeper_job" scheduler/worker.py` | >= 2 | 2 (definition + caller) | yes |
| `grep -c "JUNO_SWEEPER_CRON_ENABLED" scheduler/worker.py` | >= 3 | 8 (env-read x2 + ENABLED log + DISABLED log + comment refs) | yes |
| `grep -c "from agents.juno_weekly_sweeper import run_juno_weekly_sweeper" scheduler/worker.py` | == 1 | 1 | yes |
| `grep -c 'JOB_LOCK_IDS\["juno_weekly_sweeper"\]' scheduler/worker.py` | >= 1 | 2 (factory use + dict entry) | yes |
| `grep -c "day_of_week='sun'" scheduler/worker.py` | >= 2 | 3 (Seva + Juno + JUNO_CRON_ENABLED-comment ref; +1 over plan ack — see Deviation 1) | yes |
| `grep -c "Weekly Viral Sweeper — Juno" scheduler/worker.py` | == 1 | 1 | yes |
| `grep -c 'id="juno_weekly_sweeper"' scheduler/worker.py` | == 1 | 1 | yes |
| `grep -c '"juno_weekly_sweeper": 1021' scheduler/worker.py` | == 1 | 1 (existing reservation unchanged) | yes |
| `grep -cE "^(async )?def test_juno_sweeper" scheduler/tests/test_worker.py` | >= 4 | 4 | yes |
| `grep -c "JUNO_SWEEPER_CRON_ENABLED" scheduler/tests/test_worker.py` | >= 4 | 12 | yes |
| `grep -c "day_of_week" scheduler/tests/test_worker.py` | >= 1 | 5 | yes |
| `grep -c "juno_weekly_sweeper" scheduler/tests/test_worker.py` | >= 6 | 38 | yes |
| OPS-02 lock-uniqueness assertion at module import | passes | passes | yes |
| `uv run ruff check worker.py` | exits 0 | exits 0 | yes |
| `uv run ruff check tests/test_worker.py` | exits 0 | exits 0 | yes |

All grep gates pass (one match higher than plan's stated count — explained in Deviation 1).

## Issues Encountered

None during execution. The single grep-count delta (`day_of_week='sun'` matches 3 not 2) was a plan acceptance-criterion miscount (the plan didn't account for the pre-existing comment-line reference in the JUNO_CRON_ENABLED comment block). Substantive invariants (exactly 2 `add_job` call sites referencing `day_of_week='sun'`) all hold. No production-code issue.

## Self-Check: PASSED

- `scheduler/worker.py` modified (factory + registration block + docstring + _validate_env log) — FOUND
- `scheduler/tests/test_worker.py` modified (4 new tests appended) — FOUND
- `.planning/phases/15-juno-weekly-viral-sweeper/15-06-SUMMARY.md` exists — FOUND (this file)
- Commit `343c711` (Task 1: feat) — FOUND in git log
- Commit `ec4ade7` (Task 2: test) — FOUND in git log
- 4/4 new tests GREEN — VERIFIED
- 363 passed in full suite (359 baseline + 4 new) — VERIFIED
- D-10 byte-identical contract — VERIFIED (9 protected files, empty `git status --porcelain`)
- OPS-02 lock-uniqueness assertion — VERIFIED (`len(set(JOB_LOCK_IDS.values())) == len(JOB_LOCK_IDS)` returns True with 6 keys)
- CI grep gates PASS — VERIFIED (verify-anthropic-resolver.sh + verify-tenant-isolation.sh)
- ruff lint clean — VERIFIED on both modified files
- Module imports cleanly — VERIFIED (`from worker import _make_juno_weekly_sweeper_job, JOB_LOCK_IDS` succeeds, prints lock_id=1021)
- Existing JUNO_CRON_ENABLED block byte-identical (lines ~458-480 untouched) — VERIFIED via git diff
- Existing Seva weekly_sweeper registration byte-identical (lines ~499-509 untouched) — VERIFIED via git diff
- JOB_LOCK_IDS dict UNCHANGED (1021 reservation already in place from Phase 9 D-01) — VERIFIED

## User Setup Required (Operator Runbook)

**Out-of-band — gated by Plan 15-07 voice UAT, NOT this plan:**

1. **Deploy disabled** (default). After this plan merges, Railway scheduler service restarts with `JUNO_SWEEPER_CRON_ENABLED` UNSET → cron does not register at boot. Boot log shows `ENV JUNO_SWEEPER_CRON_ENABLED: false (juno_weekly_sweeper cron disabled — flip after voice UAT)` + the build_scheduler in-line log `juno_weekly_sweeper cron DISABLED — set JUNO_SWEEPER_CRON_ENABLED=true in Railway env after voice UAT approves`.
2. **Manual smoke fire.** Operator runs `python -m agents.juno_weekly_sweeper` (D-07 step 2 escape hatch from Plan 15-05's `__main__` block) against the production DB. One-shot synthesis of 3 angles + `weekly_sweeps` row written.
3. **Voice UAT (Plan 15-07).** Operator reads the 3 angles against the voice UAT criteria (Janes/CSIS sober tone, exactly 3 angles, anti-tactical, etc.).
4. **Flip env gate.** Operator sets `JUNO_SWEEPER_CRON_ENABLED=true` in Railway scheduler service Variables → scheduler redeploys → next Sunday 08:00 PT fires the real Juno sweeper.

**Rollback path:** Unset the env var → next deploy registers no cron → no Sunday fire. No data deletion needed (existing `weekly_sweeps` rows survive).

## Outstanding Concerns

- **Plan 15-07 (Wave 3 — next) is the voice UAT gate.** Until 15-07 lands AND the operator manually approves the 3-angle smoke-fire output AND flips `JUNO_SWEEPER_CRON_ENABLED=true` in Railway, the cron registered by this plan does NOT fire in production. This is the intended operator-gated rollout per CONTEXT D-07 + RESEARCH §1 Hard Parts.
- **First production fire risk (D-03b backfill window):** Per Plan 15-05's Outstanding Concerns, the first 0-2 production sweeps may produce `status='partial'` with the `INSUFFICIENT_SIGNAL_FALLBACK` copy because Juno daily_summary rows written BEFORE Plan 15-01's substrate-keys deploy carry empty/missing arrays. This is acceptable per CONTEXT D-03b; the orchestrator correctly tags such sweeps 'partial' with explanatory copy.
- **Same-time fire monitoring opportunity:** Sunday 08:00 PT America/Los_Angeles will (when the env gate is flipped) fire BOTH `weekly_sweeper` (Seva, lock 1019) and `juno_weekly_sweeper` (Juno, lock 1021) simultaneously. Independent locks isolate them but the operator may want to watch the first co-fire for Anthropic API rate-limit pressure (PITFALLS.md §3) and SerpAPI quota burst. RESEARCH "Hard parts" P5 explicitly accepted this. If concerns surface in production, a 5-min stagger (Juno at Sun 08:05 PT) is a 2-line CronTrigger edit — preserved as a tunability path, not done now.

## Phase 15 Wave 2 Status

This plan + the parallel Plan 15-05 form Wave 2. After both Wave 2 plans land (this commit + Plan 15-05's prior `12ecb4e` commit), Wave 3 (Plan 15-07 voice UAT) is unblocked. Once Plan 15-07 lands + operator flips Railway env, Phase 15 is verifier-ready.

---
*Phase: 15-juno-weekly-viral-sweeper*
*Plan: 06*
*Completed: 2026-05-21*
