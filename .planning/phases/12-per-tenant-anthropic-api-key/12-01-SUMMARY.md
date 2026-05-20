---
phase: 12-per-tenant-anthropic-api-key
plan: 01
subsystem: infra
tags: [anthropic, multi-tenant, pydantic-settings, async, logging, resolver, cost-attribution]

# Dependency graph
requires:
  - phase: 09-multi-tenant-foundation
    provides: "ACTIVE_COMPANIES Literal['seva','juno'] + row-level company_id pattern reused for resolver type guard"
  - phase: 02-fastapi-backend
    provides: "scheduler/config.py pydantic-settings BaseSettings pattern with @lru_cache get_settings()"
provides:
  - "get_anthropic_client(company_id, *, timeout) resolver — single function entry point for all production Anthropic instantiation in scheduler"
  - "Per-tenant API key routing: SEVA_ANTHROPIC_API_KEY for company_id='seva', JUNO_ANTHROPIC_API_KEY for 'juno'"
  - "WARN-once-per-tenant-per-process fallback semantics when per-tenant env var unset (D-01)"
  - "Opt-in STRICT mode (ANTHROPIC_RESOLVER_STRICT=true) that raises RuntimeError instead of falling back (D-02)"
  - "Process-lifetime client cache keyed on (company_id, timeout) tuple — same args → same instance (identity)"
  - "Structured per-call log line 'anthropic_call event=... company=... key_fingerprint=...' with last-8-char fingerprint (D-03 — never the full key)"
  - "3 new Settings fields: seva_anthropic_api_key, juno_anthropic_api_key, anthropic_resolver_strict"
  - "5 unit tests covering all D-05 acceptance scenarios"
affects: [phase-12-02-refactor-call-sites, phase-12-03-ci-grep-gate, phase-14-juno-calendar, phase-15-juno-weekly-sweeper]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Shared resolver-module pattern (mirrors scheduler/queries/scoped.py — single function export, module-level cache, structured log)"
    - "Literal['seva','juno'] static type guard at function signature (reuses Phase 9 D-03 multi-tenant Literal idiom)"
    - "Module-level dict/set caches with autouse pytest fixture reset between tests (mirrors juno_relevance.py module-cache idiom)"

key-files:
  created:
    - "scheduler/anthropic_client.py — resolver module (123 lines, ruff-clean)"
    - "scheduler/tests/test_anthropic_client.py — 5 unit tests (141 lines, ruff-clean)"
  modified:
    - "scheduler/config.py — added 3 Settings fields (seva/juno per-tenant keys + strict-mode flag)"

key-decisions:
  - "Key fingerprint format = last-8-chars of raw API key (operator-friendly, matches Anthropic console truncation per CONTEXT specifics) rather than SHA256[:8]"
  - "Stdlib logger.warning/logger.info (scheduler does not use structlog) — log idiom is grep-friendly key=value pairs"
  - "_log_call omits 'model' from the per-call log because the resolver cannot know the caller's model choice at resolve-time (model is chosen later at .messages.create() time). Documented as inline code comment."
  - "Module-level dict cache (not functools.lru_cache) so tests can reset state via direct mutation in the autouse fixture"
  - "Settings Optional[str] = None matches existing scheduler/config.py style (rather than 'str | None = None')"

patterns-established:
  - "Per-tenant resource resolver pattern: single function entrypoint, tenant-keyed cache, WARN-once fallback, opt-in STRICT mode. Future per-tenant resources (SerpAPI key, etc.) can clone this shape."
  - "Structured cost-attribution logging: 'anthropic_call event=... company=... key_fingerprint=...' grep-able forever in Railway logs"

requirements-completed: [KEY-01, KEY-02, KEY-04]

# Metrics
duration: 3min
completed: 2026-05-20
---

# Phase 12 Plan 01: Per-tenant Anthropic Resolver Module Summary

**Single `get_anthropic_client(company_id, *, timeout)` resolver that routes each tenant's calls to its own SEVA_/JUNO_ANTHROPIC_API_KEY with WARN-once fallback to the shared key, opt-in STRICT mode, process-lifetime per-(company,timeout) cache, and last-8-char-fingerprint structured logging — unblocking Plan 02's 3-site refactor and Plan 03's CI grep gate.**

## Performance

- **Duration:** 3 min
- **Started:** 2026-05-20T19:13:09Z
- **Completed:** 2026-05-20T19:15:56Z
- **Tasks:** 3 (auto, TDD-style)
- **Files modified:** 3 (1 modified, 2 created)

## Accomplishments

- Per-tenant Anthropic resolver module shipped with full D-01..D-03/D-05/D-07 contract: tenant routing, WARN-once fallback, STRICT-mode raise, identity-cached clients, structured cost-attribution log line at every call.
- 3 new Settings fields landed in `scheduler/config.py` (`seva_anthropic_api_key`, `juno_anthropic_api_key`, `anthropic_resolver_strict`) — required `anthropic_api_key: str` preserved unchanged so scheduler-boot failure mode is identical.
- 5 unit tests cover all D-05 scenarios (seva routing, juno routing, WARN-once fallback, STRICT raise, cache identity); full scheduler regression suite 336 passed / 1 skipped — +5 new tests, zero regressions vs Phase 11 baseline (331+).

## Task Commits

Each task was committed atomically with `--no-verify` (parallel-executor protocol):

1. **Task 1: Add per-tenant + strict-mode Settings fields to scheduler/config.py** — `d4bbebd` (feat)
2. **Task 2: Create scheduler/anthropic_client.py resolver module** — `55bec5f` (feat)
3. **Task 3: Create scheduler/tests/test_anthropic_client.py with 5+ resolver tests** — `8e9e2f0` (test)

_Note: Tasks were marked `tdd="true"` in the plan, but the executor wrote production code (Task 2) and tests (Task 3) as separate atomic commits to match the plan's task boundaries — the plan itself ordered RED-then-GREEN at the plan level (Task 2 module + Task 3 tests). All 5 tests pass against the module landed in Task 2._

## Files Created/Modified

- **`scheduler/config.py`** (modified) — added 8 lines: `seva_anthropic_api_key: Optional[str] = None`, `juno_anthropic_api_key: Optional[str] = None`, `anthropic_resolver_strict: bool = False` immediately after the required `anthropic_api_key: str` field, with a 4-line explanatory comment block referencing D-01/D-02.
- **`scheduler/anthropic_client.py`** (created, 123 lines) — module docstring + imports + `_client_cache: dict[tuple[str, float], AsyncAnthropic] = {}` + `_warned_companies: set[str] = set()` + public `get_anthropic_client(company_id, *, timeout) -> AsyncAnthropic` + private `_log_call(company_id, api_key)` structured-log helper. Contains exactly one `AsyncAnthropic(api_key=...)` call site (grep-gate compliance).
- **`scheduler/tests/test_anthropic_client.py`** (created, 141 lines) — autouse `_reset_resolver_state` fixture clearing `get_settings.cache_clear() + _client_cache.clear() + _warned_companies.clear()` between tests, plus the 5 D-05 test functions.

## Decisions Made

- **Key-fingerprint format → last-8-chars of raw key** (not SHA256[:8]). Per CONTEXT specifics: operator-friendly, matches Anthropic console's truncated display format. Implementation: `fingerprint = api_key[-8:] if len(api_key) >= 8 else "short_key"`.
- **Log idiom → stdlib `logger.warning` / `logger.info`** (not structlog). Scheduler doesn't use structlog anywhere; keeping the resolver stdlib-only avoids adding a dependency for one module. Log lines are grep-friendly `key=value` shape.
- **`_log_call` omits `model` from the per-call log line.** The CONTEXT D-03 example included `model="claude-sonnet-4-6"` in the structured payload, but the resolver does not know the caller's model choice at resolve-time (model is bound at `.messages.create()` time, not client instantiation). Documented as inline code comment `# 'model' intentionally omitted — resolver does not know caller's model choice; downstream sites can wrap with structlog if model attribution is needed.` This is a CONTEXT-deviation by design — see Deviations section.
- **Module-level dict cache (not `functools.lru_cache`).** Tests must be able to reset cache state between runs via direct `_client_cache.clear()` mutation in the autouse fixture; `@lru_cache` would require `get_anthropic_client.cache_clear()` calls and is less direct.
- **Settings field syntax → `Optional[str] = None`** (not `str | None = None`). Matches the existing style of `scheduler/config.py` (uses `from typing import Optional` throughout) — consistency over modernity in a file that's been stable since Phase 02.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Docstring referenced "AsyncAnthropic(api_key=...)" causing grep-gate count to be 2 instead of 1**

- **Found during:** Task 2 (resolver module creation), discovered via the acceptance criterion `grep -c "AsyncAnthropic(api_key=" anthropic_client.py == 1`.
- **Issue:** The plan-specified module docstring text was `"CI grep gate scripts/verify-anthropic-resolver.sh enforces that this is the ONLY production site that calls AsyncAnthropic(api_key=...)."` — that string literally contains `AsyncAnthropic(api_key=` and therefore matched the grep gate, returning a count of 2 (one docstring mention + one real call). The plan's own acceptance criterion required the count to be exactly 1 because Plan 03's CI grep gate will use the same pattern to detect violations across the codebase.
- **Fix:** Rephrased the docstring to `"...the ONLY production site that constructs the AsyncAnthropic SDK class."` — preserves intent, eliminates the grep-pattern collision. No semantic change.
- **Files modified:** `scheduler/anthropic_client.py` (docstring only, line ~21)
- **Verification:** `grep -c 'AsyncAnthropic(api_key=' scheduler/anthropic_client.py` returns 1; module import + 5 unit tests still PASS.
- **Committed in:** `55bec5f` (Task 2 commit — fix applied before commit).

### CONTEXT.md Deviation (documented, not auto-fixed)

**D-03 structured log line omits `model` field.** CONTEXT D-03 specified the structured log payload as `{"event": "anthropic_call", "company": "juno", "key_fingerprint": "ab12cd34", "model": "claude-sonnet-4-6"}` — the resolver cannot supply `model` at resolve-time because the model is chosen by the caller at `.messages.create()` time, not at client instantiation. Per the plan's own Task 2 implementer note ("Do NOT add `model` to `_log_call` — the resolver doesn't know the model"), this was an anticipated deviation. Trade-off accepted: model-attribution at per-call granularity is now a wrapper concern for callers that need it (e.g. could wrap `client.messages.create()` with a logging proxy in a future plan if Anthropic console attribution by-model becomes a v3.2+ operator need). For now, key-attribution alone satisfies the cost-attribution-by-tenant goal of Phase 12.

---

**Total deviations:** 1 auto-fixed (Rule 1 — bug in plan-specified docstring text causing grep-gate collision) + 1 documented CONTEXT deviation (`model` field omitted from per-call log by design).
**Impact on plan:** Auto-fix was necessary to satisfy the plan's own acceptance criterion AND to keep Plan 03's CI grep gate behavior clean. CONTEXT deviation is benign and was explicitly anticipated by the planner.

## Issues Encountered

None. Plan-level verification checks 1-5 (resolver+config tests pass, full scheduler regression GREEN, ruff clean across 3 files, single `AsyncAnthropic(api_key=` call site, signature matches `(company_id: Literal['seva', 'juno'], *, timeout: float = 60.0) -> AsyncAnthropic`) all passed cleanly on first run after each task's commit.

## User Setup Required

None for this plan. Operator-facing setup arrives at end of Plan 02 / Plan 03 deploy:

- Set `SEVA_ANTHROPIC_API_KEY` + `JUNO_ANTHROPIC_API_KEY` in Railway env (operator action).
- Optionally flip `ANTHROPIC_RESOLVER_STRICT=true` AFTER per-tenant keys are confirmed working (operator's intended rollout per D-02).

Until those env vars are set, the resolver gracefully falls back to the shared `ANTHROPIC_API_KEY` with a one-time WARN per tenant per process — no production breakage between Plan 02 deploy and the env-var flip.

## Next Phase Readiness

- **Plan 02 unblocked:** Can now `from anthropic_client import get_anthropic_client` and swap the 3 production `AsyncAnthropic(api_key=settings.anthropic_api_key, ...)` instantiation sites (`scheduler/agents/daily_summary.py:583` Seva Sonnet, `scheduler/agents/daily_summary.py:1226` Juno Sonnet, `scheduler/agents/weekly_sweeper.py:399` Seva sweeper Sonnet) to `get_anthropic_client('seva' | 'juno', timeout=...)`. Plan 02 also handles the content_agent.py dead-code excision (D-06) and the UAT script refactor.
- **Plan 03 unblocked:** Can now whitelist `scheduler/anthropic_client.py` as the sole exception in `scripts/verify-anthropic-resolver.sh` (mirrors `scripts/verify-tenant-isolation.sh` pattern).
- **No blockers** — Plan 01 ships clean.

## Self-Check: PASSED

- FOUND: `scheduler/anthropic_client.py` (123 lines, ruff-clean)
- FOUND: `scheduler/tests/test_anthropic_client.py` (141 lines, 5 tests PASS, ruff-clean)
- FOUND: 3 new fields in `scheduler/config.py` (`grep -c` returns 1/1/1; required `anthropic_api_key: str` line untouched, count 1)
- FOUND: commit `d4bbebd` (Task 1 — Settings fields)
- FOUND: commit `55bec5f` (Task 2 — resolver module)
- FOUND: commit `8e9e2f0` (Task 3 — 5 unit tests)
- Full scheduler regression: 336 passed / 1 skipped, no warnings escalated to errors (4 pre-existing RuntimeWarnings in `test_daily_summary_prune.py` — unrelated, out of scope per executor scope-boundary rule).

---
*Phase: 12-per-tenant-anthropic-api-key*
*Completed: 2026-05-20*
