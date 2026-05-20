---
phase: 12-per-tenant-anthropic-api-key
plan: 02
subsystem: infra
tags: [anthropic, multi-tenant, refactor, dead-code-removal, cost-attribution, async]

# Dependency graph
requires:
  - phase: 12-per-tenant-anthropic-api-key (plan 01)
    provides: "get_anthropic_client(company_id, *, timeout) resolver consumed at 5 call sites"
provides:
  - "All 4 production Anthropic instantiation sites in scheduler/ now route through the per-tenant resolver"
  - "1 UAT script site refactored — operator re-fires of voice-calibration script attribute correctly when JUNO_ANTHROPIC_API_KEY is set"
  - "content_agent.py public surface shrunk: 3 dead functions excised (check_compliance, is_gold_relevant_or_systemic_shock, review) + 1 orphaned helper (_extract_check_text)"
  - "test_content_agent.py shrunk to match: 13 dead-code test functions removed (3 review + 2 compliance + 8 gold-gate)"
  - "Zero AsyncAnthropic( calls remain in scheduler/agents/ or scheduler/scripts/ outside the resolver"
  - "Live exports preserved verbatim: fetch_stories, deduplicate_stories, _do_fetch (refactored internally), _score_relevance, classify_format_lightweight, build_draft_item, build_no_story_bundle"
affects: [phase-12-03-ci-grep-gate, phase-14-juno-calendar, phase-15-juno-weekly-sweeper]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Per-tenant client routing consumed at every production call site via from anthropic_client import get_anthropic_client + hardcoded 'seva'|'juno' literal (D-07)"
    - "Dead-code surgical excision pattern: when a private helper has zero non-test callers post-purge, delete the helper too. _extract_check_text was the third-order orphan in this plan."
    - "Test patches follow the resolver: when the production import shape changes from `from anthropic import AsyncAnthropic` to `from anthropic_client import get_anthropic_client`, every `patch(module.AsyncAnthropic)` call site must move to `patch(module.get_anthropic_client)` with the SAME `return_value=mock_client` semantics."

key-files:
  created: []
  modified:
    - "scheduler/agents/daily_summary.py (2 sites refactored — Seva line 583, Juno line 1226)"
    - "scheduler/agents/weekly_sweeper.py (1 site refactored — Seva line 399; orphaned settings/get_settings/select imports cleaned up; historical P6 docstring rephrased to avoid grep-gate substring collision)"
    - "scheduler/agents/content_agent.py (LIVE _do_fetch site refactored; 3 dead functions excised + 1 orphan helper deleted; module docstring updated; unused json import removed; net −277 lines)"
    - "scheduler/scripts/uat_voice_calibration.py (1 site refactored — Juno main() — surfaces the 4th refactor target CONTEXT.md D-09 missed)"
    - "scheduler/tests/test_content_agent.py (13 dead-code test functions removed; module docstring updated; net −247 lines)"
    - "scheduler/tests/agents/test_daily_summary.py (4 patch sites swapped from AsyncAnthropic to get_anthropic_client; regression test test_anthropic_client_timeout_is_60_seconds updated to assert on resolver call signature inside run_daily_summary scope)"
    - "scheduler/tests/test_weekly_sweeper.py (3 monkeypatch sites swapped from AsyncAnthropic to get_anthropic_client)"
    - "scheduler/tests/agents/test_juno_daily_summary.py (5 patch sites swapped from AsyncAnthropic to get_anthropic_client)"

key-decisions:
  - "CONTEXT.md line 1108 reclassified from 'dead' to 'live, refactor as Seva site' — _do_fetch is the engine of LIVE fetch_stories(), imported by daily_summary.py:36 + weekly_sweeper.py:47. Refactored with timeout=30.0 preserved verbatim."
  - "scheduler/scripts/uat_voice_calibration.py:377 surfaced as a 5th instantiation site CONTEXT.md missed (D-09 grep was scoped to scheduler/agents/; the planner's broader scheduler-wide grep caught it). Refactored as Juno site rather than exempted — Plan 03's grep gate scans scheduler/ not just scheduler/agents/, and attribution accuracy matters for operator UAT fires too."
  - "_extract_check_text deleted as a third-order orphan: its only callers were review() (deleted) and a test in test_review_empty_draft_treated_as_pass (deleted). Zero non-test callers post-purge → safe to remove. Plan implementer-note explicitly authorized this."
  - "Module docstring text in content_agent.py + test_content_agent.py updated to reflect new public surface (drop review/check_compliance/is_gold_relevant_or_systemic_shock mentions, drop CONT-14/15/16 compliance-only reqs from the test header). Net effect: future maintainers see only live code in both files."
  - "weekly_sweeper.py line 24 docstring P6 comment originally read `AsyncAnthropic(timeout=60.0)` — would have polluted Plan 03's grep gate count to 1 instead of 0. Rephrased to `anthropic_client constructed with timeout=60.0` (factual content preserved; substring collision eliminated)."
  - "Pre-existing ruff F401 errors in 3 files (daily_summary.py HAIKU_MODEL, weekly_sweeper.py select, uat_voice_calibration.py _build_juno_world_events_section) verified pre-existing via `git stash` against main; left in place per executor scope-boundary rule. Logged to .planning/phases/12-per-tenant-anthropic-api-key/deferred-items.md."

patterns-established:
  - "Resolver-consumer call-site pattern: every production Anthropic site is `client = get_anthropic_client('seva'|'juno', timeout=...)` with hardcoded tenant literal. Plan 03's CI grep gate enforces this pattern by forbidding any other AsyncAnthropic(api_key=...) construction outside scheduler/anthropic_client.py + scheduler/tests/."
  - "Test patch invariant: when production code calls the resolver instead of constructing the SDK directly, tests patch the resolver (`patch('module.get_anthropic_client', return_value=mock_client)`). Same return_value semantics as the old `patch('module.AsyncAnthropic', return_value=mock_client)` — Mock framework treats both transparently because both are function-call-shaped."

requirements-completed: [KEY-01, KEY-03]

# Metrics
duration: 11min
completed: 2026-05-20
---

# Phase 12 Plan 02: Per-tenant Resolver Consumption + Dead-Code Excision Summary

**Refactored 5 production Anthropic instantiation sites (4 in scheduler/agents/ + 1 in scheduler/scripts/) to route through the per-tenant resolver, surgically excised 3 dead Anthropic-using functions (~266 lines) + 13 corresponding dead-code tests, and left the codebase with zero `AsyncAnthropic(` calls outside scheduler/anthropic_client.py — Plan 03's CI grep gate now has a clean slate to enforce.**

## Performance

- **Duration:** 11 min
- **Started:** 2026-05-20T19:20:24Z
- **Completed:** 2026-05-20T19:31:27Z
- **Tasks:** 3 (auto, TDD-style — refactor + regression-guard)
- **Files modified:** 8 (5 production + 3 test files)

## Accomplishments

- All 4 production Anthropic instantiation sites in `scheduler/agents/` (`daily_summary.py` ×2 + `weekly_sweeper.py` + `content_agent.py::_do_fetch`) now route through the Plan 01 resolver — Seva calls bill to `SEVA_ANTHROPIC_API_KEY` and Juno calls bill to `JUNO_ANTHROPIC_API_KEY` once operator sets the env vars (fallback to shared key today).
- 1 additional UAT site refactored (`scheduler/scripts/uat_voice_calibration.py:377`) — surfaced by planner-grep, missed by CONTEXT.md D-09's narrower scheduler/agents/-only enumeration.
- Dead-code surgical excision per D-06: `check_compliance` (~25 lines), `is_gold_relevant_or_systemic_shock` (~178 lines), `review` (~28 lines), plus orphaned helper `_extract_check_text` (~35 lines) — net **−266 lines** of dead agent code; **−13** dead-code tests (3 review + 2 check_compliance + 8 is_gold_relevant_or_systemic_shock).
- Full scheduler regression suite **GREEN: 323 passed / 1 skipped** (down from Plan 01 baseline of 336/1 — the **−13** delta matches the deliberately deleted dead-code tests **exactly**, zero unintended regressions).
- Plan 03 grep gate dry-run: `grep -rnE 'AsyncAnthropic\(|Anthropic\(api_key=' scheduler/ --include='*.py' | grep -v 'scheduler/anthropic_client.py' | grep -v 'scheduler/tests/'` returns **zero hits**.

## Task Commits

Each task was committed atomically with `--no-verify` (parallel-executor protocol):

1. **Task 1: Refactor 3 daily_summary + weekly_sweeper Anthropic call sites** — `32ec118` (refactor)
2. **Task 2: Refactor content_agent.py LIVE _do_fetch + delete 3 dead functions + remove dead-code tests** — `fbce5b9` (refactor)
3. **Task 3: Refactor scheduler/scripts/uat_voice_calibration.py to use resolver** — `4d3b495` (refactor)

## Files Created/Modified

**Production files (4 modified):**

- `scheduler/agents/daily_summary.py` — added `from anthropic_client import get_anthropic_client` import; replaced Seva instantiation at line 583 with `get_anthropic_client("seva", timeout=60.0)`; replaced Juno instantiation at line 1226 with `get_anthropic_client("juno", timeout=JUNO_SONNET_TIMEOUT)`. Module constants `JUNO_SONNET_TIMEOUT = 60.0` and surrounding `quick-260514-ii6` 60s-timeout comment block preserved verbatim. `AsyncAnthropic` import preserved (still used as type hint at lines 237/353/937/968/1057).
- `scheduler/agents/weekly_sweeper.py` — added resolver import; replaced Seva sweeper instantiation at line 399 with `get_anthropic_client("seva", timeout=SONNET_TIMEOUT_S)`; orphaned `settings = get_settings()` line removed (no other settings usage remained in the orchestrator); orphaned `from config import get_settings` import removed; historical P6 docstring at line 24 rephrased from `AsyncAnthropic(timeout=60.0)` to `anthropic_client constructed with timeout=60.0` to avoid Plan 03 grep-gate substring collision. `AsyncAnthropic` import preserved (still used as type hint at line 270).
- `scheduler/agents/content_agent.py` — added resolver import; refactored LIVE `_do_fetch` instantiation at line 1108 to `get_anthropic_client("seva", timeout=30.0)` (preserves 30s per-request timeout); deleted `check_compliance`, `is_gold_relevant_or_systemic_shock`, `review`, and `_extract_check_text` (collectively ~266 lines); deleted now-unused `import json`; updated module docstring to reflect new public surface (drops review/compliance references; adds v3.1 Phase 12 excision note). `AsyncAnthropic` import preserved (still used as type hint at line 792 on `_score_relevance`).
- `scheduler/scripts/uat_voice_calibration.py` — added resolver import; replaced `AsyncAnthropic(api_key=settings.anthropic_api_key, timeout=JUNO_SONNET_TIMEOUT)` at line 377 with `get_anthropic_client("juno", timeout=JUNO_SONNET_TIMEOUT)`. `settings.anthropic_api_key` sanity check at line 375 preserved (operator-friendly fail-fast when no key available). `AsyncAnthropic` import preserved (still used as type hint at lines 229/263/291).

**Test files (3 modified):**

- `scheduler/tests/test_content_agent.py` — deleted 13 test functions covering the deleted production functions (3 review + 2 check_compliance + 8 is_gold_relevant_or_systemic_shock); deleted associated section banner comments + `GATE_CONFIG` fixture (was used exclusively by gold-gate tests); updated module docstring to reflect new public surface. Net −247 lines.
- `scheduler/tests/agents/test_daily_summary.py` — 4 `patch("agents.daily_summary.AsyncAnthropic", return_value=...)` sites swapped to `patch("agents.daily_summary.get_anthropic_client", return_value=...)` (same return_value semantics — the resolver is function-shaped not class-shaped, but Mock framework handles both transparently). Regression test `test_anthropic_client_timeout_is_60_seconds` updated: now asserts on `get_anthropic_client("seva", timeout=60.0)` signature inside `run_daily_summary`'s source slice, still enforcing the 60-second timeout AND the Seva tenant literal per D-07.
- `scheduler/tests/test_weekly_sweeper.py` — 3 `monkeypatch.setattr(weekly_sweeper, "AsyncAnthropic", lambda **kw: anthropic_inst)` sites swapped to `monkeypatch.setattr(weekly_sweeper, "get_anthropic_client", lambda *a, **kw: anthropic_inst)` (lambda accepts positional company_id argument now).
- `scheduler/tests/agents/test_juno_daily_summary.py` — 5 `patch("agents.daily_summary.AsyncAnthropic")` sites swapped to `patch("agents.daily_summary.get_anthropic_client")` (no signature change needed; `MockClient.return_value = mock_client` semantics work identically against the resolver).

## Decisions Made

- **CONTEXT.md D-09 line 1108 reclassified from dead to live (refactor as Seva, do NOT delete).** Verified via grep: `_do_fetch` is called by `fetch_stories()` (line 1175 of content_agent.py), which is imported by `daily_summary.py:36` (LIVE Seva daily cron) and `weekly_sweeper.py:47` (LIVE Seva weekly Sunday cron). Deleting `_do_fetch` would break both production crons. The original CONTEXT.md classification was a planner-grep precision error — `is_gold_relevant_or_systemic_shock` (lines 444-621 inclusive of line 483) IS dead, but `_do_fetch` (lines 1097-1172 inclusive of line 1108) is the engine of live `fetch_stories()`. Refactor result: 3 production Seva sites (daily_summary line 583, weekly_sweeper line 399, content_agent _do_fetch line 1108) + 2 production Juno sites (daily_summary line 1226, uat_voice_calibration line 377). Net deletes: 3 dead functions + 1 orphaned helper.
- **scheduler/scripts/uat_voice_calibration.py:377 added as a 5th refactor target.** CONTEXT.md D-09's enumeration was scoped to `scheduler/agents/`; the planner's broader grep `scheduler/` surfaced this 4th-or-rather-5th instantiation site in `scheduler/scripts/`. Decision: refactor (not exempt) — operator UAT fires deserve correct cost-attribution too, and Plan 03's grep gate will scan all of `scheduler/` not just `scheduler/agents/` (per D-08 exemption list which whitelists only the resolver module + tests dir).
- **`_extract_check_text` deleted as orphan despite not being in the "delete" list.** After deleting `review()` (its only production caller), `_extract_check_text` had zero non-test references. The remaining test reference was inside `test_review_empty_draft_treated_as_pass` (also deleted). Per plan implementer-note: "If zero non-test callers remain, ALSO delete `_extract_check_text` and its corresponding test (if any). If any caller exists ... preserve it." Decision: delete (zero callers post-purge).
- **Module docstring text updated, not preserved verbatim.** Both `scheduler/agents/content_agent.py` and `scheduler/tests/test_content_agent.py` had docstrings claiming `review` / `check_compliance` / `is_gold_relevant_or_systemic_shock` were part of the public surface. After deletion these claims would be lies. Updated both to reflect the new public surface (fetch_stories + classify_format_lightweight + helpers; explicit note about the Phase 12 excision for future maintainers).
- **Hardcoded `"seva"` / `"juno"` string literals at every call site (D-07).** Not extracted to a `company_id` variable. Each call site is unambiguously one tenant; the literal is grep-able; the `Literal["seva", "juno"]` type hint in the resolver catches typos at type-check time. 5 instantiation sites = 5 hardcoded literals.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test patches in `test_daily_summary.py`, `test_weekly_sweeper.py`, `test_juno_daily_summary.py` were patching the now-removed `AsyncAnthropic` import path**

- **Found during:** Task 1 verification (`pytest tests/agents/test_daily_summary.py tests/test_weekly_sweeper.py -q` exited with 3 failures after the production refactor landed; later Task 2 verification surfaced 4 more failures in `test_juno_daily_summary.py`).
- **Issue:** The plan's task-1 `<behavior>` block claimed "tests use `patch("agents.daily_summary.fetch_stories", AsyncMock(...))` etc. and do NOT inspect the Anthropic client construction directly ... swapping the constructor for a resolver call is invisible to them. Verified via the grep `patch.*AsyncAnthropic\|patch.*get_anthropic_client` in test_daily_summary.py — neither pattern appears." This was an incorrect planner statement — in reality `patch("agents.daily_summary.AsyncAnthropic", return_value=mock_client)` appears 4 times in `test_daily_summary.py`, `monkeypatch.setattr(weekly_sweeper, "AsyncAnthropic", lambda **kw: anthropic_inst)` appears 3 times in `test_weekly_sweeper.py`, and `patch("agents.daily_summary.AsyncAnthropic")` appears 5 times in `test_juno_daily_summary.py`. Once the production import path stopped going through `AsyncAnthropic` for the orchestrator construction, every one of these patches missed the real call site → the real (unmocked) `AsyncAnthropic` SDK class was invoked → TypeError "Could not resolve authentication method" because the fake env API key was rejected.
- **Fix:** Swapped every `AsyncAnthropic` patch target to `get_anthropic_client`. The Mock framework's `return_value` semantics work identically against both — `patch(..., return_value=mock_client)` means "the patched callable returns `mock_client` when invoked" regardless of whether the callable is a class constructor or a plain function. For the lambda-style `monkeypatch.setattr` in `test_weekly_sweeper.py`, the lambda signature changed from `lambda **kw: anthropic_inst` to `lambda *a, **kw: anthropic_inst` (the resolver takes `company_id` positionally).
- **Files modified:** `scheduler/tests/agents/test_daily_summary.py`, `scheduler/tests/test_weekly_sweeper.py`, `scheduler/tests/agents/test_juno_daily_summary.py` (12 patch sites total across 3 files).
- **Verification:** `pytest tests/agents/test_daily_summary.py tests/test_weekly_sweeper.py tests/agents/test_juno_daily_summary.py -q` exits 0 (all 75 tests passing). Full scheduler regression suite: 323 passed / 1 skipped (Plan 01 baseline 336/1, minus the 13 deliberately deleted dead-code tests = 323 expected).
- **Committed in:** `32ec118` (Task 1 — test_daily_summary.py + test_weekly_sweeper.py) and `fbce5b9` (Task 2 — test_juno_daily_summary.py, surfaced when running full suite post-Task-2).

**2. [Rule 1 - Bug] `test_anthropic_client_timeout_is_60_seconds` regression guard was scanning for the now-deleted `AsyncAnthropic` construction pattern**

- **Found during:** Task 1 verification.
- **Issue:** The test (quick-260514-ii6 regression guard from a 2026-05-14 timeout-too-low incident) scanned the `daily_summary` module source for `anthropic_client = AsyncAnthropic` and asserted `timeout=60.0` inside that construction block. After the refactor, that string no longer appears anywhere in `daily_summary.py` — the test would always fail.
- **Fix:** Updated the test to scan `inspect.getsource(ds_module.run_daily_summary)` (the Seva orchestrator only — Juno's 60s timeout is its own concern at line 1226 with a different module constant) for `anthropic_client = get_anthropic_client` and assert (a) `timeout=60.0` is inside the construction block, (b) `timeout=30.0` is NOT inside the construction block (legacy 30s ceiling removed), and (c) `"seva"` or `'seva'` appears inside the construction block (D-07 hardcoded literal at instantiation site). Docstring updated to explain the v3.1 Phase 12 migration. The regression intent (catch any future revert of the 60s timeout) is preserved.
- **Files modified:** `scheduler/tests/agents/test_daily_summary.py` (test body + docstring at line ~1394).
- **Verification:** `pytest tests/agents/test_daily_summary.py::test_anthropic_client_timeout_is_60_seconds -q` exits 0.
- **Committed in:** `32ec118` (Task 1).

**3. [Rule 3 - Blocking] Orphaned imports in `weekly_sweeper.py` and `content_agent.py`**

- **Found during:** Task 1 verification (weekly_sweeper.py — `settings = get_settings()` had only the Anthropic-line usage; once that line moved to the resolver, `settings` was unused; `from config import get_settings` was the next orphan up the chain). Task 2 ruff post-run (content_agent.py — `import json` was used only by the deleted `is_gold_relevant_or_systemic_shock` body).
- **Issue:** Ruff F401 would flag the now-unused imports if left in place. The plan's `<action>` block did not enumerate these orphans explicitly but did say "verify the now-orphan line".
- **Fix:** Removed `settings = get_settings()` line + `from config import get_settings` import from weekly_sweeper.py (orchestrator was the only caller). Removed `import json` from content_agent.py (only usage was inside the deleted `is_gold_relevant_or_systemic_shock` JSON-parse path).
- **Files modified:** `scheduler/agents/weekly_sweeper.py`, `scheduler/agents/content_agent.py`.
- **Verification:** `uv run ruff check scheduler/agents/weekly_sweeper.py scheduler/agents/content_agent.py` (modulo pre-existing F401 noise documented under "Issues Encountered") — no NEW errors introduced; the imports I removed are not flagged anywhere.
- **Committed in:** `32ec118` (weekly_sweeper.py) and `fbce5b9` (content_agent.py — `import json` removal).

**4. [Rule 1 - Bug] `weekly_sweeper.py` module docstring contained literal `AsyncAnthropic(timeout=60.0)` text that would pollute Plan 03's grep gate**

- **Found during:** Task 1 acceptance criterion check (`grep -c "AsyncAnthropic(" scheduler/agents/weekly_sweeper.py` returned 1 instead of 0).
- **Issue:** Line 24 of `weekly_sweeper.py` documents the P6 historical pitfall as `P6 (Sonnet timeout missing) — AsyncAnthropic(timeout=60.0)` — a comment, not a call site, but it contains the substring `AsyncAnthropic(` and would be counted by a naïve grep. The plan acknowledged this tension ("Plan 03 uses a pattern that excludes commented lines") but Plan 03 hasn't landed yet, and the acceptance criterion here is `grep -c "AsyncAnthropic(" ... returns 0` with no comment-exclusion clause. Leaving the comment text would fail acceptance.
- **Fix:** Rephrased the P6 docstring line from `AsyncAnthropic(timeout=60.0)` to `anthropic_client constructed with timeout=60.0`. The historical-pitfall content is preserved verbatim semantically; only the SDK-class-shaped grep-bait substring is eliminated.
- **Files modified:** `scheduler/agents/weekly_sweeper.py` (line 24, module docstring P6 bullet).
- **Verification:** `grep -c "AsyncAnthropic(" scheduler/agents/weekly_sweeper.py` returns 0 (was 1); module imports + 14 sweeper tests still GREEN.
- **Committed in:** `32ec118` (Task 1).

### Planner-Flagged Deviations (documented, not auto-fixed)

**A. CONTEXT.md D-09 line 1108 reclassification: dead → live (refactor as Seva, do NOT delete).** Anticipated by the planner in the 12-02-PLAN.md objective block (D-06 deviation note). Executed as planned — net delete count remains accurate (3 dead functions: check_compliance, is_gold_relevant_or_systemic_shock, review) but the function at line 1108 (which CONTEXT.md identified as one of "3 dead sites") turned out to be the LIVE `_do_fetch` engine of `fetch_stories()`. Refactored to `get_anthropic_client("seva", timeout=30.0)` instead of deleted.

**B. scheduler/scripts/uat_voice_calibration.py:377 added as a 4th-/5th refactor site.** Anticipated by the planner in the same objective block (D-09 deviation note). Executed as planned — CONTEXT.md's grep was scoped to `scheduler/agents/` and missed the `scheduler/scripts/` UAT one-shot.

---

**Total deviations:** 4 auto-fixed (Rules 1, 1, 3, 1) + 2 documented planner-flagged (already in plan objective). All Rule-1 fixes were necessary to keep the test suite GREEN — they patch test-file-side patches that referenced the production code's old import shape. Rule-3 fix was necessary for ruff-cleanliness. **Zero scope creep**; every deviation was inside the 5 files the plan explicitly targets.

## Issues Encountered

**Pre-existing ruff F401 errors in 3 of the touched production files were NOT fixed (out-of-scope per scope-boundary rule):**

1. `scheduler/agents/daily_summary.py` — `agents.juno_relevance.HAIKU_MODEL` imported but unused (pre-existing since Phase 10).
2. `scheduler/agents/weekly_sweeper.py` — `sqlalchemy.select` imported but unused (pre-existing since v3.0 Phase 9 when raw `select(...)` calls were rewritten to `scoped_summaries(...)`).
3. `scheduler/scripts/uat_voice_calibration.py` — `_build_juno_world_events_section` imported but unused (pre-existing since Phase 10 DEF-10).

Verified pre-existing via `git stash` against the plan-02-start commit (`c022a2b`). Logged to `.planning/phases/12-per-tenant-anthropic-api-key/deferred-items.md` per scope-boundary rule.

The plan's own acceptance criterion `uv run ruff check agents/daily_summary.py agents/weekly_sweeper.py exits 0` is therefore not strictly satisfied — but the 2 errors that surface are 100% pre-existing and 0% caused by plan-02 work. The strict reading would require fixing them; the executor-scope-boundary rule defers them. Documented for the verifier.

**4 pre-existing RuntimeWarnings in `test_daily_summary_prune.py` (already noted in 12-01-SUMMARY.md)** continue to fire — unchanged by plan-02 work, also pre-existing.

## User Setup Required

None for this plan. Operator-facing setup arrives at end of Plan 03 deploy:

- Set `SEVA_ANTHROPIC_API_KEY` + `JUNO_ANTHROPIC_API_KEY` in Railway env (operator action).
- Optionally flip `ANTHROPIC_RESOLVER_STRICT=true` AFTER per-tenant keys are confirmed working (operator's intended rollout per D-02).

Until those env vars are set, the resolver gracefully falls back to the shared `ANTHROPIC_API_KEY` with a one-time WARN per tenant per process — no production breakage between Plan 02 deploy and the env-var flip.

## Next Phase Readiness

- **Plan 03 unblocked:** The codebase is in the exact state Plan 03 needs — zero `AsyncAnthropic(` or `Anthropic(api_key=` outside `scheduler/anthropic_client.py` and `scheduler/tests/`. Plan 03 can implement `scripts/verify-anthropic-resolver.sh` (mirrors `scripts/verify-tenant-isolation.sh` pattern) and wire it into the CI lane — its dry-run will pass on first try. Plan 03 also extends `scheduler/worker.py:613` env-var status logging.
- **Phase 12 substance complete:** Once Plan 03 lands the grep gate + CI integration, Phase 12 is functionally done. Phase 13 (branding) and Phase 14/15 (Juno content) consume Phase 12's resolver transparently — they just call `get_anthropic_client("juno", ...)` at their new instantiation sites and get correct attribution automatically.
- **No blockers** — plan ships clean. Deferred items (3 pre-existing F401s) are tracked in `deferred-items.md` for a future maintenance window.

## Self-Check: PASSED

- FOUND: `scheduler/agents/daily_summary.py` modified (commit `32ec118`)
- FOUND: `scheduler/agents/weekly_sweeper.py` modified (commit `32ec118`)
- FOUND: `scheduler/agents/content_agent.py` modified (commit `fbce5b9`)
- FOUND: `scheduler/scripts/uat_voice_calibration.py` modified (commit `4d3b495`)
- FOUND: `scheduler/tests/test_content_agent.py` modified (commit `fbce5b9`)
- FOUND: `scheduler/tests/agents/test_daily_summary.py` modified (commit `32ec118`)
- FOUND: `scheduler/tests/test_weekly_sweeper.py` modified (commit `32ec118`)
- FOUND: `scheduler/tests/agents/test_juno_daily_summary.py` modified (commit `fbce5b9`)
- FOUND: commit `32ec118` (Task 1)
- FOUND: commit `fbce5b9` (Task 2)
- FOUND: commit `4d3b495` (Task 3)
- FOUND: `.planning/phases/12-per-tenant-anthropic-api-key/deferred-items.md` (deferred pre-existing ruff F401 log)
- Full scheduler regression: 323 passed / 1 skipped (Plan 01 baseline 336/1 − 13 deliberately deleted dead-code tests = 323 expected, exact match).
- Plan 03 grep-gate dry-run: `grep -rnE 'AsyncAnthropic\(|Anthropic\(api_key=' scheduler/ --include='*.py' | grep -v 'scheduler/anthropic_client.py' | grep -v 'scheduler/tests/'` returns zero hits.
- Live entry-point smoke import: `from agents.daily_summary import run_daily_summary, run_juno_daily_summary; from agents.weekly_sweeper import run_weekly_sweeper; from agents.content_agent import fetch_stories, deduplicate_stories` exits 0 (all live entry points import OK).
- Negative smoke: `from agents.content_agent import review` raises `ImportError` (function correctly deleted).

---
*Phase: 12-per-tenant-anthropic-api-key*
*Completed: 2026-05-20*
