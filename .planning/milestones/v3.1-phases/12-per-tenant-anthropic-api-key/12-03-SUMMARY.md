---
phase: 12-per-tenant-anthropic-api-key
plan: 03
subsystem: infra
tags: [anthropic, multi-tenant, ci, grep-gate, observability, cost-attribution, scheduler-boot]

# Dependency graph
requires:
  - phase: 12-per-tenant-anthropic-api-key (plan 01)
    provides: "scheduler/anthropic_client.py resolver module — the sole production AsyncAnthropic( instantiation site that the grep gate whitelists"
  - phase: 12-per-tenant-anthropic-api-key (plan 02)
    provides: "Codebase already grep-clean — zero AsyncAnthropic( outside resolver + tests, so the gate exits 0 on first run"
  - phase: 09-multi-tenant-foundation
    provides: "scripts/verify-tenant-isolation.sh template — Plan 03's grep gate mirrors its TARGETS + ALLOWED + exit-1 idiom verbatim"
provides:
  - "scripts/verify-anthropic-resolver.sh — CI grep gate forbidding raw AsyncAnthropic( or Anthropic(api_key= outside scheduler/anthropic_client.py + scheduler/tests/"
  - "Comment-line filter via ^[^#]* anchor in PATTERN — historical docstring/comment mentions don't trip the gate (ROADMAP Hard Parts P5 resolved)"
  - "D-08 inline-comment exemption escape hatch — lines containing '# anthropic-resolver: exempt' are stripped from violations"
  - "scheduler/worker.py::_validate_env extended with 3 new boot log lines — SEVA_ANTHROPIC_API_KEY, JUNO_ANTHROPIC_API_KEY (WARNING when unset), ANTHROPIC_RESOLVER_STRICT (INFO unconditional)"
  - "Operator post-deploy verification checklist (10-step, transcribed from CONTEXT D-04) — documented here, executed by operator"
affects: [phase-13-juno-branding, phase-14-juno-calendar, phase-15-juno-weekly-sweeper, all-future-anthropic-call-sites]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "CI grep gate mirroring Phase 9 scripts/verify-tenant-isolation.sh — same set -euo pipefail header, TARGETS + ALLOWED_PREFIXES idiom, grep-strip-empty-line cleanup, exit-1-with-actionable-message on failure"
    - "^[^#]* anchor pattern for skipping commented-out historical references (false-positive mitigation for grep gates that scan Python source)"
    - "grep scope filters --include='*.py' --exclude-dir=__pycache__ --exclude-dir=.venv — skip binary .pyc + vendored SDK source that would otherwise pollute grep output"
    - "Boot-time env-var status logging with severity-tiered output: INFO for present + STRICT toggle, WARNING for per-tenant unset (loud but non-fatal), ERROR for missing critical keys (existing pattern preserved)"

key-files:
  created:
    - "scripts/verify-anthropic-resolver.sh — CI grep gate (115 lines, chmod +x)"
  modified:
    - "scheduler/worker.py — extended _validate_env to log 3 new env vars at boot (+27 lines, ruff-clean)"

key-decisions:
  - "Plan-spec'd script body extended with grep scope filters (--include='*.py' --exclude-dir=__pycache__/.venv/node_modules) as Rule 1 auto-fix: first dry-run hit 3 false positives (.pyc binary, scheduler/.venv/.../anthropic/_client.py:293 vendored class declaration, backend/.venv/.../_client.py:293 ditto). Adding scope filters is the right fix — broadening ALLOWED_PREFIXES would have masked the real intent."
  - "WARNING (not ERROR or INFO) chosen as severity for per-tenant Anthropic key unset. Rationale: resolver falls back to shared ANTHROPIC_API_KEY gracefully (D-01) — so missing per-tenant key is NOT a failure state (ruling out ERROR), but operator likely wants to know they're unset in prod (ruling out plain INFO). WARNING is the operator-friendly middle ground, mirroring how worker.py already treats FRED_API_KEY / METALPRICEAPI_API_KEY misses (graceful fallback with WARNING surface)."
  - "ANTHROPIC_RESOLVER_STRICT logged unconditionally at INFO with human-readable interpretation suffix ('true (resolver will RAISE on per-tenant key miss)' vs 'false (resolver will fall back gracefully)'). Boolean toggles benefit from interpreted output in boot logs — operator can confirm intent without re-reading the resolver code."
  - "Boot smoke test uses `env -u SEVA_ANTHROPIC_API_KEY -u JUNO_ANTHROPIC_API_KEY uv run python -c '...'` to guarantee per-tenant vars are scoped out regardless of local env state. The plan's acceptance criterion `grep -c 'SEVA_ANTHROPIC_API_KEY: not set' returns 1` requires this — the executor's local env happened to not have those keys set, but env -u makes the test reproducible against any developer's machine."
  - "Negative-test smoke (per acceptance criteria optional clause) executed and confirmed: temporary `scheduler/agents/_gate_test_temp.py` containing `_test_violation = AsyncAnthropic(api_key='sk-test')` triggered exit code 1 with file:line in the violation message. File deleted immediately; tree returned to clean state."

patterns-established:
  - "CI grep-gate idiom for Phase-N pattern enforcement: bash script in scripts/, mirrors verify-tenant-isolation.sh shape, exits 0 on clean tree, exits 1 with actionable message on violation. Future patterns to enforce (per-tenant SerpAPI key, etc.) can clone this shape directly."
  - "Boot-time env-var status logging tier discipline: ERROR for critical-missing (agents fail), WARNING for graceful-fallback-with-operator-impact (per-tenant Anthropic, market data), INFO for present-or-optional-missing (SerpAPI, Twilio)."
  - "Comment-line filter via ^[^#]* anchor — grep gates on Python source that want to ignore docstring/comment mentions of the forbidden pattern. Validated by hand: weekly_sweeper.py line 24's historical P6 comment text (rephrased in Plan 02 but the principle holds for future docstrings) would NOT match if it contained AsyncAnthropic(...)."

requirements-completed: [KEY-03, KEY-04]

# Metrics
duration: 2min
completed: 2026-05-20
---

# Phase 12 Plan 03: CI Grep Gate + Boot Env-Var Visibility Summary

**Landed the bash CI grep gate (`scripts/verify-anthropic-resolver.sh`) that locks in Plan 02's clean tree by exiting 1 on any future raw `AsyncAnthropic(api_key=...)` reintroduction outside the resolver module + tests, and extended `scheduler/worker.py::_validate_env` to surface all 3 new per-tenant Anthropic env vars (SEVA/JUNO/STRICT) at scheduler boot — closing the operator-observability loop for Phase 12.**

## Performance

- **Duration:** 2 min
- **Started:** 2026-05-20T19:37:22Z
- **Completed:** 2026-05-20T19:39:49Z
- **Tasks:** 2 (auto; both committed atomically with --no-verify per parallel-executor protocol)
- **Files modified:** 2 (1 created, 1 modified)

## Accomplishments

- CI grep gate shipped (`scripts/verify-anthropic-resolver.sh`, 115 lines, chmod +x, ruff-N/A bash) — exits 0 on the current clean tree, exits 1 on any future reintroduction of `AsyncAnthropic(api_key=...)` outside the resolver + test allowlist. Mirrors Phase 9's `verify-tenant-isolation.sh` shape exactly (TARGETS + ALLOWED + exit semantics).
- Negative-test smoke confirmed: temp file `scheduler/agents/_gate_test_temp.py` with `_test_violation = AsyncAnthropic(api_key="sk-test")` triggered exit code 1 with `scheduler/agents/_gate_test_temp.py:7:_test_violation = AsyncAnthropic(api_key="sk-test")` in the violation message. Temp file deleted; tree returned to clean state.
- `scheduler/worker.py::_validate_env` extended with 27 lines: 2 per-tenant env-var status checks (WARNING-tiered) + 1 STRICT-mode interpretation log (INFO-tiered). Existing critical/optional/market_data blocks preserved verbatim.
- Boot smoke test confirms all 3 new env vars log at expected severity: `SEVA_ANTHROPIC_API_KEY: not set — resolver will fall back...` (WARNING), `JUNO_ANTHROPIC_API_KEY: not set — resolver will fall back...` (WARNING), `ANTHROPIC_RESOLVER_STRICT: false (resolver will fall back gracefully)` (INFO).
- Full scheduler regression suite **GREEN: 323 passed / 1 skipped** (identical to Plan 02 baseline — zero regressions). `test_worker.py` 39 tests pass unchanged. Ruff clean on `worker.py`.
- Companion gate `verify-tenant-isolation.sh` still exits 0 — Plan 03 did not touch any code under that gate's purview.

## Task Commits

Each task was committed atomically with `--no-verify` (parallel-executor protocol):

1. **Task 1: Create scripts/verify-anthropic-resolver.sh CI grep gate** — `c5680ca` (feat)
2. **Task 2: Extend scheduler/worker.py _validate_env to log per-tenant Anthropic env-var status** — `2c43bd2` (feat)

## Files Created/Modified

- **`scripts/verify-anthropic-resolver.sh`** (created, 115 lines, mode 0755) — bash CI grep gate. Header comments document D-08 exemption escape hatch + `^[^#]*` comment-line filter pattern. `TARGETS = ("scheduler" "backend")`, `ALLOWED_PREFIXES = ("scheduler/anthropic_client.py" "scheduler/tests/")`. Grep invocation uses `--include='*.py' --exclude-dir='__pycache__' --exclude-dir='.venv' --exclude-dir='node_modules'` scope filters. On failure: prints violation message with file:line of offending site + actionable fix suggestion + inline-marker escape-hatch documentation. Exit code 0 on PASS / 1 on FAIL.
- **`scheduler/worker.py`** (modified, +27 lines, lines 629-654 in post-edit file) — `_validate_env` function extended immediately after the existing `for key, present in optional.items(): ...` loop and immediately before the `market_data = {...}` block. New block adds: (a) `per_tenant_anthropic` dict with SEVA_/JUNO_ keys + WARNING-on-unset loop, (b) unconditional `logger.info("ENV ANTHROPIC_RESOLVER_STRICT: %s", ...)` with human-readable interpretation. Function signature `async def _validate_env() -> None` unchanged. No callers modified.

## Decisions Made

- **Grep scope filters added to plan-spec'd script body (Rule 1 auto-fix).** First dry-run of `scripts/verify-anthropic-resolver.sh` (as written verbatim from the plan) returned exit code 1 with 3 false positives:
  1. `scheduler/tests/agents/__pycache__/test_daily_summary.cpython-312-pytest-9.0.2.pyc` — binary `.pyc` file matched by grep
  2. `scheduler/.venv/lib/python3.12/site-packages/anthropic/_client.py:293:class AsyncAnthropic(AsyncAPIClient):` — the vendored Anthropic SDK's own class declaration
  3. `backend/.venv/.../_client.py:293:class AsyncAnthropic(AsyncAPIClient):` — same in backend's venv
  
  Adding `--include='*.py' --exclude-dir='__pycache__' --exclude-dir='.venv' --exclude-dir='node_modules'` to the grep invocation eliminates all three. The mirror script `verify-tenant-isolation.sh` happens to not hit this because its pattern `select\((DailySummary|...)` doesn't appear in vendored libs or as `.pyc` text-strings; Plan 03's pattern `AsyncAnthropic\(` does. Documented as Rule 1 auto-fix in Deviations below.
- **WARNING severity for per-tenant key unset.** ERROR was wrong (resolver gracefully falls back, no agent failure); plain INFO was too quiet (operator wants visibility on prod misconfiguration). WARNING is the right tier and is already used by `worker.py` for `FRED_API_KEY`/`METALPRICEAPI_API_KEY` (analogous graceful-fallback-with-operator-impact misses).
- **STRICT toggle logged unconditionally with interpreted suffix.** Boolean toggles benefit from human-readable interpretation in boot logs. Operator reading Railway logs sees `ENV ANTHROPIC_RESOLVER_STRICT: false (resolver will fall back gracefully)` and immediately knows what the toggle does without re-reading the resolver code.
- **Boot smoke test scoped with `env -u`.** The plan's nit-flagged concern about local-env pollution (executor might have SEVA_ANTHROPIC_API_KEY set locally → smoke test grep count would be 0 not 1) handled by prefixing the smoke command with `env -u SEVA_ANTHROPIC_API_KEY -u JUNO_ANTHROPIC_API_KEY uv run python -c '...'`. Makes the test reproducible against any developer's machine.
- **Negative-test smoke executed (optional acceptance clause).** Per the plan's discretionary acceptance criterion, temporarily created `scheduler/agents/_gate_test_temp.py` with `_test_violation = AsyncAnthropic(api_key="sk-test")`, ran the gate (exit code 1, violation message correct), deleted the temp file, re-ran the gate (exit code 0). Confirms the gate's enforcement behavior end-to-end.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Plan-spec'd script body lacked grep scope filters; first dry-run hit 3 false positives**

- **Found during:** Task 1 verification (`bash scripts/verify-anthropic-resolver.sh` exited 1 instead of 0 on the post-Plan-02 clean tree).
- **Issue:** The plan's `<action>` block specified the script body verbatim with `violations=$(grep -rnE "$PATTERN" "${TARGETS[@]}" 2>/dev/null || true)` — no `--include='*.py'`, no `--exclude-dir` filters. On the actual filesystem, `grep -rnE` recursing into `scheduler/` + `backend/` hit (a) binary `.pyc` files in `scheduler/tests/agents/__pycache__/` (matched as "binary file matches"), (b) the vendored Anthropic SDK's own class declaration at `scheduler/.venv/lib/python3.12/site-packages/anthropic/_client.py:293`, (c) same in `backend/.venv/`. All three were FALSE POSITIVES — none authored by humans, none in scope for the gate's enforcement intent.
- **Fix:** Extended the grep invocation to `grep -rnE --include='*.py' --exclude-dir='__pycache__' --exclude-dir='.venv' --exclude-dir='node_modules' "$PATTERN" "${TARGETS[@]}"`. Inline comment added to the script explaining each filter's purpose. Re-run: exit 0 PASS. Negative smoke (temp file with real violation) still triggers exit 1 — the filters only mask non-authored files, not real violations.
- **Files modified:** `scripts/verify-anthropic-resolver.sh` (lines ~67-78 — grep invocation block).
- **Verification:** `bash scripts/verify-anthropic-resolver.sh` returns exit 0 on clean tree; negative smoke (temp `_gate_test_temp.py`) returns exit 1 with correct file:line. Manual closure-grep `grep -rnE --include='*.py' --exclude-dir='__pycache__' --exclude-dir='.venv' '^[^#]*(AsyncAnthropic\(|Anthropic\(api_key=)' scheduler/ backend/ | grep -v 'scheduler/anthropic_client.py' | grep -v 'scheduler/tests/'` returns zero hits, agreeing with the gate.
- **Committed in:** `c5680ca` (Task 1 — fix applied before commit; the script as-committed already contains the scope filters).

---

**Total deviations:** 1 auto-fixed (Rule 1 — plan-spec'd script body was missing grep scope filters that are mandatory for any grep gate scanning a Python repo with venvs + .pyc caches present). Impact on plan: zero — the auto-fix is mechanical (adding 3 grep flags), preserves all plan-spec'd semantics (allowed-prefix logic, exemption escape hatch, exit codes, output format), and was necessary to satisfy the plan's own acceptance criterion (`bash scripts/verify-anthropic-resolver.sh exits 0 on the current tree`).

## Issues Encountered

**4 pre-existing RuntimeWarnings in `test_daily_summary_prune.py` (already documented in 12-01-SUMMARY.md + 12-02-SUMMARY.md) continue to fire** — unchanged by plan-03 work, also pre-existing. Out of scope per executor scope-boundary rule.

**3 pre-existing ruff F401 errors in `scheduler/agents/daily_summary.py`, `scheduler/agents/weekly_sweeper.py`, `scheduler/scripts/uat_voice_calibration.py`** — still in `.planning/phases/12-per-tenant-anthropic-api-key/deferred-items.md`. Plan 03 did not introduce or resolve any of them; `worker.py` itself is ruff-clean.

## User Setup Required

**Operator post-deploy checklist (10-step, from CONTEXT D-04 — transcribed for operator convenience):**

1. **Set `SEVA_ANTHROPIC_API_KEY` in Railway scheduler service env vars.** Get the key from the Seva Mining Anthropic console; copy into Railway → scheduler service → Variables tab.
2. **Set `JUNO_ANTHROPIC_API_KEY` in Railway scheduler service env vars.** Get the key from the Juno tenant's separate Anthropic console (a separate Anthropic account or organization, set up post-deploy if not already provisioned).
3. **Leave `ANTHROPIC_API_KEY` (shared) UNCHANGED** — it remains the resolver's fallback. Do not delete or rename.
4. **Leave `ANTHROPIC_RESOLVER_STRICT` unset (defaults to `false`)** until step 9 — gives the rollout a safety net during initial verification.
5. **Wait for next scheduler restart** (Railway auto-redeploys on env-var change). In Railway logs, look for the new boot lines:
   - `ENV SEVA_ANTHROPIC_API_KEY: SET ✓` (INFO)
   - `ENV JUNO_ANTHROPIC_API_KEY: SET ✓` (INFO)
   - `ENV ANTHROPIC_RESOLVER_STRICT: false (resolver will fall back gracefully)` (INFO)
   
   If you see WARNING `not set — resolver will fall back to shared ANTHROPIC_API_KEY` for either per-tenant key, the env var didn't land in the scheduler service. Re-check the Variables tab and trigger a manual redeploy.
6. **Manually fire Seva daily summary:** `cd scheduler && uv run python -c "import asyncio; from agents.daily_summary import run_daily_summary; asyncio.run(run_daily_summary())"` — OR wait for the next 08:00 PT cron. Open the Seva Anthropic console and confirm the request appears in the dashboard usage.
7. **Manually fire Juno daily summary:** `cd scheduler && uv run python -c "import asyncio; from agents.daily_summary import run_juno_daily_summary; asyncio.run(run_juno_daily_summary())"` — OR wait for the next Juno cron fire. Open the Juno Anthropic console; confirm the request appears there. Open the Seva Anthropic console; confirm the request does NOT appear there (no cross-tenant attribution).
8. **Cross-check structured log lines.** During each fire above, Railway logs should contain:
   - For Seva fire: `anthropic_call event=anthropic_call company=seva key_fingerprint=<last-8-of-seva-key>`
   - For Juno fire: `anthropic_call event=anthropic_call company=juno key_fingerprint=<last-8-of-juno-key>`
   
   The fingerprints should be the last 8 characters of each tenant's actual API key — verify they match what you set in step 1/2.
9. **Once both consoles show correct attribution, flip `ANTHROPIC_RESOLVER_STRICT=true` in Railway** as the permanent safety net. Next scheduler restart, the boot log will show `ENV ANTHROPIC_RESOLVER_STRICT: true (resolver will RAISE on per-tenant key miss)`. From this point forward, any future accidental unset of a per-tenant key will hard-fail the agent (no silent shared-key billing).
10. **Rollback (if needed):** unset both per-tenant env vars + `ANTHROPIC_RESOLVER_STRICT=false`. Next cron fire falls back to shared `ANTHROPIC_API_KEY`; no redeploy required, no production breakage. Step 5's WARNING log lines will return — that's the expected fallback signal.

## Next Phase Readiness

- **Phase 12 code-side complete.** All 4 KEY-XX requirements have plans claiming them in frontmatter: KEY-01 (Plans 01+02), KEY-02 (Plan 01), KEY-03 (Plans 02+03), KEY-04 (Plans 01+03). Plans 02+03 close KEY-03 (the grep gate enforces "all Anthropic calls route through resolver, forever"). Plans 01+03 close KEY-04 (cost-attribution observable via per-call structured log + boot env-var status).
- **Phase 12 operator-side pending.** The 10-step checklist above is the operator's task per CONTEXT D-04. Until step 9 lands (per-tenant keys set in Railway + STRICT=true), the resolver runs in graceful-fallback mode — shared `ANTHROPIC_API_KEY` continues to bill all calls. No production breakage between deploy and operator-side configuration.
- **Phase 13 (Juno branding) ready.** Phase 13 does not touch Anthropic call sites; consumes Phase 12's resolver transparently if it adds any new ones.
- **Phase 14 (Juno calendar) / Phase 15 (Juno weekly sweeper) ready.** Both phases will add new Anthropic instantiation sites — they MUST route through `get_anthropic_client("juno", ...)` per the resolver contract. The CI grep gate enforces this: any PR that tries to construct `AsyncAnthropic(api_key=...)` directly in those new agent files will fail the gate at CI time.
- **CI integration TODO (operator/CI-maintainer task, not Claude):** add `bash scripts/verify-anthropic-resolver.sh` to the CI pipeline alongside the existing `bash scripts/verify-tenant-isolation.sh` invocation. This is mechanical — same Railway/GitHub-Actions YAML stanza as the existing gate.

## Phase 12 Cross-Plan Closure Checklist

- [x] Resolver module + 5 unit tests (Plan 01)
- [x] Settings declaration: `seva_anthropic_api_key` + `juno_anthropic_api_key` + `anthropic_resolver_strict` (Plan 01)
- [x] 4 refactored production sites (3 Seva: daily_summary line 583, weekly_sweeper line 399, content_agent _do_fetch line 1108; 1 Juno: daily_summary line 1226) + 1 UAT script (Plan 02)
- [x] Dead-code excision: 3 dead functions + 1 orphan helper + 13 corresponding tests (Plan 02)
- [x] CI grep gate `scripts/verify-anthropic-resolver.sh` (Plan 03)
- [x] Boot-time env-var status logging — SEVA_/JUNO_/STRICT (Plan 03)

## Phase 12 Retrospective Signals

**What worked:**
- **Plan 01's interface-first ordering** — Plan 02's refactor was mechanical because the resolver contract was already locked + tested. Plan 03's grep gate landed in 2 minutes because Plan 02 left the tree clean (first dry-run after scope-filter fix exits 0).
- **CONTEXT.md's pre-discussion of D-01..D-09** eliminated ~90% of executor decisions. Plans 02 + 03 were nearly pure mechanical translation of the locked decisions.
- **Pattern reuse:** `scripts/verify-tenant-isolation.sh` shape directly transplanted to `scripts/verify-anthropic-resolver.sh` — saved planning time and ensures CI ergonomic consistency. Future grep-gate patterns can clone this template.
- **Severity-tiered boot logging:** the choice to use WARNING (not ERROR/INFO) for per-tenant unset matches the existing pattern for `FRED_API_KEY`/`METALPRICEAPI_API_KEY` in worker.py — convention preserved.

**Friction surfaced:**
- **Plan-spec'd grep script body needed scope filters (Rule 1 auto-fix in Plan 03).** The verbatim plan-body specification didn't include `--include='*.py'` or `--exclude-dir='.venv'/__pycache__` filters; first dry-run hit 3 false positives from vendored SDK source + binary .pyc files. Mechanical fix (3 grep flags), zero semantic change, but worth flagging for future grep-gate authors: any grep gate scanning a Python repo with venvs present needs scope filters from the start.
- **Plan 02 already documented:** CONTEXT.md's "3 dead sites" was based on a `scheduler/agents/`-scoped grep; the planner's broader `scheduler/` grep surfaced a 4th UAT-script site + reclassified one of the 3 "dead" sites as LIVE-refactor. (Same friction surfaced in Plan 02 — listed here for retrospective completeness.)

**Pattern reused:**
- `scripts/verify-tenant-isolation.sh` → `scripts/verify-anthropic-resolver.sh` — same TARGETS + ALLOWED + exit-1-with-message shape. Future per-tenant resources (SerpAPI key, model-tier routing, etc.) can clone both Plan 01's resolver-module pattern AND Plan 03's CI-gate pattern.
- Boot-time env-var status logging in `worker.py::_validate_env` — same severity-tiering as existing critical/optional/market_data blocks. Future env vars added by Phases 13+ can drop straight into this pattern.

## Self-Check: PASSED

- FOUND: `scripts/verify-anthropic-resolver.sh` (115 lines, executable, ruff-N/A bash)
- FOUND: `scheduler/worker.py` modified (+27 lines in `_validate_env`)
- FOUND: commit `c5680ca` (Task 1 — CI grep gate)
- FOUND: commit `2c43bd2` (Task 2 — worker.py extension)
- Acceptance criteria grep counts (Task 1): shebang OK, `set -euo pipefail` count=1, `scheduler/anthropic_client.py` mentions=5, `scheduler/tests/` mentions=4, `anthropic-resolver: exempt` mentions=4, executable bit SET.
- Acceptance criteria grep counts (Task 2): `SEVA_ANTHROPIC_API_KEY` count=1, `JUNO_ANTHROPIC_API_KEY` count=1, `ANTHROPIC_RESOLVER_STRICT` count=1, `fall back to shared ANTHROPIC_API_KEY` count=1, `settings.seva/juno_anthropic_api_key` count=2, `settings.anthropic_resolver_strict` count=1, existing `"ANTHROPIC_API_KEY": bool(settings.anthropic_api_key)` line preserved (count=1).
- `bash scripts/verify-anthropic-resolver.sh` exits 0 on clean tree (PASS message printed).
- Negative smoke: temp `scheduler/agents/_gate_test_temp.py` with `AsyncAnthropic(api_key="sk-test")` → exit 1 with correct file:line; temp deleted; re-run exits 0.
- Boot smoke: `env -u SEVA_ANTHROPIC_API_KEY -u JUNO_ANTHROPIC_API_KEY uv run python -c "..." 2>&1 | grep -c "SEVA_ANTHROPIC_API_KEY: not set"` returns 1 (matches plan acceptance).
- Full scheduler regression: **323 passed / 1 skipped** (Plan 02 baseline 323/1 — zero regressions).
- `test_worker.py` 39 tests pass unchanged.
- Ruff: `worker.py` clean (worker.py was the only modified Python file).
- Companion gate: `bash scripts/verify-tenant-isolation.sh` still exits 0 (no cross-gate breakage).
- Closure manual grep: `grep -rnE --include='*.py' --exclude-dir='__pycache__' --exclude-dir='.venv' '^[^#]*(AsyncAnthropic\(|Anthropic\(api_key=)' scheduler/ backend/ | grep -v 'scheduler/anthropic_client.py' | grep -v 'scheduler/tests/'` returns zero hits (manual grep agrees with the gate's PASS).

---
*Phase: 12-per-tenant-anthropic-api-key*
*Completed: 2026-05-20*
