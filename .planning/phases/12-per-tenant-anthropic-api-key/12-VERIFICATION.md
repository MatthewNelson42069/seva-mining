---
phase: 12-per-tenant-anthropic-api-key
verified: 2026-05-20T20:05:00Z
status: passed
score: 16/16 must-haves verified (4 requirements + 12 invariants)
re_verification:
  previous_status: none
  previous_score: n/a
human_verification:
  - test: "Set SEVA_ANTHROPIC_API_KEY + JUNO_ANTHROPIC_API_KEY in Railway; trigger run_daily_summary (Seva) + run_juno_daily_summary (Juno); confirm each tenant's Anthropic console shows only its own request usage"
    expected: "Seva console shows Seva request IDs only; Juno console shows Juno request IDs only; no cross-tenant attribution"
    why_human: "Cost-attribution verification requires (a) operator-side Railway env-var configuration, (b) access to two separate Anthropic consoles, (c) eyeballing dashboards — not programmatically verifiable from this repo. Documented in CONTEXT D-04 + 12-03-SUMMARY as operator post-deploy responsibility, not phase substance."
  - test: "After step above passes, flip ANTHROPIC_RESOLVER_STRICT=true in Railway; verify next scheduler restart shows 'ENV ANTHROPIC_RESOLVER_STRICT: true (resolver will RAISE on per-tenant key miss)' INFO log; verify no agent failures"
    expected: "Boot log line shows true interpretation; subsequent cron fires succeed without raising RuntimeError (both per-tenant keys are set so strict mode never fires the fallback raise)"
    why_human: "Requires Railway boot log inspection + observation across multiple cron cycles — not part of code-side verification."
---

# Phase 12: Per-tenant Anthropic API Key Verification Report

**Phase Goal (from ROADMAP.md):** Every Anthropic call routes through a single resolver (`get_anthropic_client(company_id)`) that selects the right per-tenant key. Seva's calls bill to `SEVA_ANTHROPIC_API_KEY`; Juno's to `JUNO_ANTHROPIC_API_KEY`. Local-dev keeps working via graceful fallback to shared `ANTHROPIC_API_KEY`. After this phase, every downstream v3.1 LLM call automatically attributes correctly with no per-call-site change required.

**Verified:** 2026-05-20T20:05:00Z
**Status:** PASSED (code-side complete; operator post-deploy actions remain pending per CONTEXT D-04)
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| #   | Truth                                                                                                                                              | Status     | Evidence                                                                                                                                                                                       |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Single resolver `get_anthropic_client(company_id, *, timeout)` exists with `Literal["seva","juno"]` signature                                       | VERIFIED   | `scheduler/anthropic_client.py:45-49` — exact signature `get_anthropic_client(company_id: Literal["seva", "juno"], *, timeout: float = 60.0) -> AsyncAnthropic`                                |
| 2   | All 5 production Anthropic instantiation sites in scheduler/ route through the resolver with hardcoded `"seva"` / `"juno"` literals               | VERIFIED   | daily_summary.py:585 ("seva"), daily_summary.py:1227 ("juno"), weekly_sweeper.py:400 ("seva"), content_agent.py:868 ("seva"), uat_voice_calibration.py:382 ("juno")                              |
| 3   | Resolver routes per-tenant key correctly: seva → SEVA_ANTHROPIC_API_KEY, juno → JUNO_ANTHROPIC_API_KEY (when env vars set)                          | VERIFIED   | resolver lines 72-77 + `test_get_anthropic_client_seva_routes_to_seva_key` + `test_get_anthropic_client_juno_routes_to_juno_key` — both PASSED                                                  |
| 4   | Graceful fallback to shared ANTHROPIC_API_KEY with WARN-once per company per process when per-tenant unset                                          | VERIFIED   | resolver lines 86-95 + `test_fallback_emits_warn_once_per_company` — PASSED (asserts exactly 1 WARN per company across 3 seva calls + 1 juno call)                                              |
| 5   | STRICT mode (`ANTHROPIC_RESOLVER_STRICT=true`) raises RuntimeError instead of falling back                                                          | VERIFIED   | resolver lines 80-85 + `test_strict_mode_raises_on_missing_per_tenant_key` — PASSED (asserts `"ANTHROPIC_RESOLVER_STRICT=true"` + `"JUNO_ANTHROPIC_API_KEY"` in error message)                  |
| 6   | CI grep gate (`scripts/verify-anthropic-resolver.sh`) exits 0 on current tree and exits 1 on reintroduced violations                                 | VERIFIED   | gate exits 0 with PASS message; negative-test (temp file with `_x = AsyncAnthropic(api_key="sk-test")` in scheduler/agents/) exits 1 with file:line in violation message; cleanup re-run exits 0 |
| 7   | Worker boot logs SEVA/JUNO/STRICT env-var status at scheduler startup                                                                                | VERIFIED   | worker.py:629-653 + boot smoke test with `env -u SEVA_/-u JUNO_` shows 3 expected log lines: 2 WARNINGs ("not set — resolver will fall back...") + 1 INFO ("ANTHROPIC_RESOLVER_STRICT: false ...") |

**Score:** 7/7 truths verified

---

### Requirements Coverage (KEY-01..04)

| Requirement | Statement                                                                                                                                                                                                                                                                                                                                              | Status     | Evidence                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **KEY-01**  | Operator sets `SEVA_ANTHROPIC_API_KEY` + `JUNO_ANTHROPIC_API_KEY`; all LLM call sites resolve via `get_anthropic_client(company_id)`                                                                                                                                                                                                                  | PASS       | All 5 instantiation sites use resolver with hardcoded literal — see Invariant 7 evidence. Settings declares 2 new env-var-bound fields at `scheduler/config.py:25-26`. Operator Railway env-var step is documented in 12-03-SUMMARY user-setup checklist (PENDING — phase boundary).                                                                                                                                                                                       |
| **KEY-02**  | Graceful fallback to shared `ANTHROPIC_API_KEY` when per-tenant unset (preserves local-dev)                                                                                                                                                                                                                                                            | PASS       | resolver lines 86-95 implements WARN-once fallback; `test_fallback_emits_warn_once_per_company` asserts exactly 1 WARN per company across 3 seva + 1 juno calls. Boot smoke test confirms WARNING log lines fire when per-tenant unset. Settings field defaults to `None` so any missing env var triggers fallback path (not raise). Existing `anthropic_api_key: str` REQUIRED field preserved at `scheduler/config.py:18` (hard-fail at Settings() if shared key missing). |
| **KEY-03**  | All call sites routed through resolver (CI grep gate enforces)                                                                                                                                                                                                                                                                                          | PASS       | `bash scripts/verify-anthropic-resolver.sh` exits 0 with PASS message. Manual cross-check: `grep -rn 'AsyncAnthropic(' scheduler/ --include='*.py' --exclude-dir=__pycache__ --exclude-dir=.venv` returns 3 hits: anthropic_client.py:97 (resolver itself), test_ontario_law.py:70 (test exempt), test_daily_summary.py:1406 (docstring mention — non-instantiation). Negative test confirms gate catches reintroductions.                                                |
| **KEY-04**  | Cost attribution clean — each tenant's Anthropic dashboard shows only its own usage (observable via structured log + boot env-var visibility)                                                                                                                                                                                                          | PASS (code-side); HUMAN-PENDING (dashboard verification) | Resolver emits `anthropic_call event=anthropic_call company=<seva\|juno> key_fingerprint=<last-8>` at every call (anthropic_client.py:111-123). Boot env-var visibility via worker.py:629-653 confirmed. Actual Anthropic dashboard verification requires operator-side Railway env-var configuration + manual fire of run_daily_summary / run_juno_daily_summary + dashboard inspection (CONTEXT D-04 — documented as operator task in 12-03-SUMMARY, NOT phase substance).      |

**Score:** 4/4 requirements satisfied at code level. KEY-04 dashboard verification deferred to operator post-deploy per CONTEXT D-04 (not a phase verification failure).

---

### Preserved Invariants

| # | Invariant | Status | Evidence |
| - | --------- | ------ | -------- |
| 1 | Resolver signature `get_anthropic_client(company_id: Literal["seva","juno"], *, timeout: float = 60.0) -> AsyncAnthropic` exists in `scheduler/anthropic_client.py` | VERIFIED | `anthropic_client.py:45-49` exact match |
| 2 | Fallback semantics: when per-tenant key unset, falls back to shared `ANTHROPIC_API_KEY` + emits WARN log ONCE per company per process via module-scoped `_warned_companies: set[str]` | VERIFIED | `anthropic_client.py:42` declares module-level set; lines 88-95 implement WARN-once gate; `test_fallback_emits_warn_once_per_company` asserts exactly 1 WARN per company across 3+1 calls |
| 3 | STRICT mode: `ANTHROPIC_RESOLVER_STRICT=true` env var raises `RuntimeError` instead of falling back | VERIFIED | `anthropic_client.py:80-85` raises RuntimeError with message containing both `"ANTHROPIC_RESOLVER_STRICT=true"` and `"<COMPANY>_ANTHROPIC_API_KEY"`; `test_strict_mode_raises_on_missing_per_tenant_key` PASSED |
| 4 | Module-scoped state: `_client_cache: dict[tuple[str, float], AsyncAnthropic]` and `_warned_companies: set[str]` are module-level, NOT function-level | VERIFIED | `anthropic_client.py:38` and `:42` — both declared at module scope; test fixture clears them via `from anthropic_client import _client_cache, _warned_companies; _client_cache.clear(); _warned_companies.clear()` (test_anthropic_client.py:40-43) |
| 5 | Cache identity: repeated calls with same `(company_id, timeout)` return same instance | VERIFIED | `anthropic_client.py:66-70` checks `cache_key in _client_cache` before instantiation; `test_cache_returns_same_instance_for_same_args` asserts `c1 is c2` for same args AND `c1 is not c3` for different timeout — PASSED |
| 6 | Key fingerprint never exposes full key — log line uses last-8-chars (NEVER the raw api_key) | VERIFIED | `anthropic_client.py:117` `fingerprint = api_key[-8:]`; only `fingerprint` (not `api_key`) is passed to `logger.info` at line 119. The full `api_key` only flows to `AsyncAnthropic(api_key=...)` constructor at line 97 (not to any logger). |
| 7 | Hardcoded company_id literals at instantiation sites (D-07) | VERIFIED | All 5 sites use string literals: daily_summary.py:585 `"seva"`, :1227 `"juno"`, weekly_sweeper.py:400 `"seva"`, content_agent.py:868 `"seva"`, uat_voice_calibration.py:382 `"juno"` — no variable indirection at any site |
| 8 | Downstream agents untouched: `juno_relevance.py`, `juno_refusal_detector.py`, `ontario_law.py` STILL take `client: AsyncAnthropic` as parameter; they do NOT instantiate clients | VERIFIED | juno_relevance.py:87 `client: AsyncAnthropic`; juno_refusal_detector.py:57 `client: AsyncAnthropic`; ontario_law.py:228 `client: AsyncAnthropic`, :303 `anthropic_client: AsyncAnthropic`. No `AsyncAnthropic(` instantiation in any of the three files — grep confirms zero instantiation calls (only type hints + import). |
| 9 | Live exports preserved: `from agents.content_agent import fetch_stories` and `from agents.content_agent import deduplicate_stories` still succeed; `daily_summary.py:36` and `weekly_sweeper.py:47` imports continue to resolve | VERIFIED | `daily_summary.py:36`: `from agents.content_agent import fetch_stories` (line confirmed); `weekly_sweeper.py:47`: `from agents.content_agent import deduplicate_stories` (line confirmed); smoke import `from agents.content_agent import fetch_stories, deduplicate_stories` exits 0; `fetch_stories` defined at content_agent.py:933, `deduplicate_stories` at :218 |
| 10 | Dead functions deleted: `from agents.content_agent import review` raises ImportError; same for `check_compliance` and `is_gold_relevant_or_systemic_shock` | VERIFIED | `python -c "from agents.content_agent import review"` → `ImportError: cannot import name 'review' from 'agents.content_agent'`; same for `check_compliance` + `is_gold_relevant_or_systemic_shock`. Grep `^(async )?def (check_compliance\|is_gold_relevant_or_systemic_shock\|review\|_extract_check_text)\b` returns 0 matches in content_agent.py. |
| 11 | Grep gate enforces: `grep -rn 'AsyncAnthropic(' scheduler/ --include='*.py' --exclude-dir=__pycache__ --exclude-dir=.venv` matches ONLY in `scheduler/anthropic_client.py` (and possibly `scheduler/tests/`) | VERIFIED | Manual grep returns exactly 3 hits: `scheduler/anthropic_client.py:97` (resolver), `scheduler/tests/agents/test_ontario_law.py:70` (test exempt), `scheduler/tests/agents/test_daily_summary.py:1406` (regression-test docstring mention — non-instantiation). `bash scripts/verify-anthropic-resolver.sh` exits 0 with PASS. Negative-test (temp file with raw AsyncAnthropic call) exits 1 with file:line in violation message. |
| 12 | Worker boot logging extended: `scheduler/worker.py::_validate_env` logs `SEVA_ANTHROPIC_API_KEY`, `JUNO_ANTHROPIC_API_KEY`, `ANTHROPIC_RESOLVER_STRICT` presence/absence | VERIFIED | worker.py:629-653 — `per_tenant_anthropic` dict iterated for SEVA/JUNO (INFO if set, WARNING if not); `logger.info("ENV ANTHROPIC_RESOLVER_STRICT: %s", ...)` with human-readable suffix. Existing `ANTHROPIC_API_KEY: SET ✓` line preserved at line 613. Boot smoke test with `env -u SEVA_ -u JUNO_ -u STRICT` confirms 2 WARNINGs + 1 INFO emitted at expected severities. |

**Score:** 12/12 invariants verified

---

### Required Artifacts (Level 1-3)

| Artifact | Expected | Level 1 (Exists) | Level 2 (Substantive) | Level 3 (Wired) | Status |
| -------- | -------- | ---------------- | --------------------- | --------------- | ------ |
| `scheduler/anthropic_client.py` | Resolver module with `get_anthropic_client` + `_client_cache` + `_warned_companies` + `_log_call` | YES (123 lines, ruff-clean) | YES (signature matches, both module-level caches declared, fallback + STRICT + fingerprint logic present) | YES (imported by 4 production agents + 1 UAT script — see invariant 2) | VERIFIED |
| `scheduler/tests/test_anthropic_client.py` | 5 unit tests covering D-05 scenarios | YES (141 lines) | YES (5 test functions: seva routing, juno routing, WARN-once, STRICT raise, cache identity) | YES (autouse fixture clears `_client_cache` + `_warned_companies` + `get_settings.cache_clear()`) — all 5 tests PASSED | VERIFIED |
| `scheduler/config.py` | 3 new Settings fields: `seva_anthropic_api_key`, `juno_anthropic_api_key`, `anthropic_resolver_strict` | YES (existing file modified) | YES (3 fields declared with correct types + defaults at lines 25-27) | YES (consumed by resolver at anthropic_client.py:72-86 via `get_settings()`; consumed by worker at worker.py:635-651) | VERIFIED |
| `scheduler/agents/daily_summary.py` | 2 sites refactored (Seva line 583, Juno line 1226) + resolver import | YES (modified) | YES (lines 585 + 1227 both call resolver with hardcoded literal + correct timeout) | YES (`from anthropic_client import get_anthropic_client` at line 38) | VERIFIED |
| `scheduler/agents/weekly_sweeper.py` | 1 site refactored (Seva line 399) + resolver import | YES (modified) | YES (line 400 calls `get_anthropic_client("seva", timeout=SONNET_TIMEOUT_S)`) | YES (`from anthropic_client import get_anthropic_client` at line 49) | VERIFIED |
| `scheduler/agents/content_agent.py` | LIVE _do_fetch site refactored + 3 dead functions deleted + 1 orphan helper deleted | YES (modified) | YES (line 868 `get_anthropic_client("seva", timeout=30.0)`; grep confirms 0 matches for `^(async )?def (check_compliance\|is_gold_relevant_or_systemic_shock\|review\|_extract_check_text)\b`) | YES (`from anthropic_client import get_anthropic_client` at line 46; live exports `fetch_stories` line 933 + `deduplicate_stories` line 218 preserved + import-resolved by daily_summary.py:36 + weekly_sweeper.py:47) | VERIFIED |
| `scheduler/scripts/uat_voice_calibration.py` | 1 site refactored (Juno line 377) | YES (modified) | YES (line 382 `get_anthropic_client("juno", timeout=JUNO_SONNET_TIMEOUT)`) | YES (resolver import at line 52; smoke import OK) | VERIFIED |
| `scheduler/tests/test_content_agent.py` | 13 dead-code test functions removed | YES (modified) | YES (net -247 lines per Plan-02 SUMMARY; full scheduler suite down from 336 to 323 = -13 expected = -13 actual) | YES (test_content_agent.py module docstring updated to reflect new public surface) | VERIFIED |
| `scripts/verify-anthropic-resolver.sh` | CI grep gate + executable + 50+ lines | YES (115 lines, mode 0755) | YES (set -euo pipefail header; TARGETS + ALLOWED_PREFIXES; `^[^#]*` comment-line filter; exempt-marker escape hatch; --include='*.py' + --exclude-dir scope filters) | YES (mirrors verify-tenant-isolation.sh pattern; both gates exit 0 on current tree) | VERIFIED |
| `scheduler/worker.py` | _validate_env extended with 3 new env-var status logs | YES (modified, +27 lines) | YES (lines 629-653 implement per-tenant dict iteration + STRICT interpretation log; existing critical/optional blocks preserved) | YES (settings.seva_anthropic_api_key, settings.juno_anthropic_api_key, settings.anthropic_resolver_strict all consumed; boot smoke test confirms logs emit at expected severities) | VERIFIED |

---

### Key Link Verification

| From | To | Via | Status |
| ---- | -- | --- | ------ |
| `scheduler/agents/daily_summary.py::run_daily_summary` | `scheduler/anthropic_client.py::get_anthropic_client` | `from anthropic_client import get_anthropic_client` (line 38) + call at line 585 with `"seva", timeout=60.0` | WIRED |
| `scheduler/agents/daily_summary.py::run_juno_daily_summary` | `scheduler/anthropic_client.py::get_anthropic_client` | same import + call at line 1227 with `"juno", timeout=JUNO_SONNET_TIMEOUT` | WIRED |
| `scheduler/agents/weekly_sweeper.py::run_weekly_sweeper` | `scheduler/anthropic_client.py::get_anthropic_client` | `from anthropic_client import get_anthropic_client` (line 49) + call at line 400 with `"seva", timeout=SONNET_TIMEOUT_S` | WIRED |
| `scheduler/agents/content_agent.py::_do_fetch` (engine of LIVE `fetch_stories()`) | `scheduler/anthropic_client.py::get_anthropic_client` | `from anthropic_client import get_anthropic_client` (line 46) + call at line 868 with `"seva", timeout=30.0` | WIRED |
| `scheduler/scripts/uat_voice_calibration.py::main` | `scheduler/anthropic_client.py::get_anthropic_client` | `from anthropic_client import get_anthropic_client` (line 52) + call at line 382 with `"juno", timeout=JUNO_SONNET_TIMEOUT` | WIRED |
| `scheduler/anthropic_client.py::get_anthropic_client` | `scheduler/config.py::Settings` | `from config import get_settings` (line 30) + `settings = get_settings()` (line 72) + `getattr(settings, per_tenant_attr)` (line 74) + `settings.anthropic_resolver_strict` (line 80) + `settings.anthropic_api_key` (line 86) | WIRED |
| `scheduler/anthropic_client.py::get_anthropic_client` | `anthropic.AsyncAnthropic` | `from anthropic import AsyncAnthropic` (line 28) + `AsyncAnthropic(api_key=api_key, timeout=timeout)` (line 97) | WIRED |
| `scheduler/tests/test_anthropic_client.py` | `scheduler/anthropic_client.py::get_anthropic_client` | `from anthropic_client import get_anthropic_client` (used in all 5 tests) + autouse fixture clears `_client_cache` + `_warned_companies` directly | WIRED |
| `scheduler/worker.py::_validate_env` | `scheduler/config.py::Settings.seva_anthropic_api_key/juno_anthropic_api_key/anthropic_resolver_strict` | `settings = get_settings()` (line 610) + `settings.seva_anthropic_api_key` (line 635) + `settings.juno_anthropic_api_key` (line 636) + `settings.anthropic_resolver_strict` (line 651) | WIRED |
| `scripts/verify-anthropic-resolver.sh` | `scheduler/anthropic_client.py` + `scheduler/tests/` (allowlist) | TARGETS=("scheduler" "backend") + ALLOWED_PREFIXES=("scheduler/anthropic_client.py" "scheduler/tests/") + grep pattern `^[^#]*(AsyncAnthropic\(\|Anthropic\(api_key=)` with --include='*.py' + --exclude-dir filters | WIRED |

All 10 key links VERIFIED (no NOT_WIRED, no PARTIAL).

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| `anthropic_client.py::get_anthropic_client` | `api_key` (str returned to AsyncAnthropic constructor) | Either `settings.seva_anthropic_api_key`, `settings.juno_anthropic_api_key`, or `settings.anthropic_api_key` (read via `get_settings()` which reads env vars via pydantic-settings) | YES — Settings reads from real env vars (Railway/`.env`); resolver test `test_get_anthropic_client_seva_routes_to_seva_key` asserts `client.api_key == "sk-seva-AAAAAAAA"` after `monkeypatch.setenv("SEVA_ANTHROPIC_API_KEY", "sk-seva-AAAAAAAA")` — real env-var read demonstrated | FLOWING |
| `worker.py::_validate_env` | `settings.seva_anthropic_api_key`, `settings.juno_anthropic_api_key`, `settings.anthropic_resolver_strict` | `get_settings()` → Settings() → pydantic-settings env-var read | YES — boot smoke test with `env -u SEVA_/-u JUNO_` produces 2 WARNING lines + 1 INFO line at correct severities; reflects real env-var state | FLOWING |
| `daily_summary.py::run_daily_summary` `anthropic_client` | `get_anthropic_client("seva", timeout=60.0)` return value | resolver returns real AsyncAnthropic instance | YES — existing test suite (test_daily_summary.py: 5 patch sites updated to `patch("agents.daily_summary.get_anthropic_client")`) passes; resolver's identity-cached instance is the same client the test mocks substitute for | FLOWING |
| (analogous for weekly_sweeper, content_agent._do_fetch, daily_summary Juno path, uat_voice_calibration) | resolver return value | same | YES — full scheduler regression suite 323/1 GREEN | FLOWING |

All data-flow traces FLOWING.

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Resolver tests pass | `cd scheduler && uv run pytest tests/test_anthropic_client.py -v` | 5/5 PASSED in 0.16s | PASS |
| Full scheduler regression | `cd scheduler && uv run pytest -q` | 323 passed, 1 skipped, 4 warnings (pre-existing prune RuntimeWarnings) in 12.56s — matches baseline exactly | PASS |
| CI grep gate (positive — clean tree) | `bash scripts/verify-anthropic-resolver.sh` | exit 0; "PASS — all Anthropic client instantiations routed through scheduler/anthropic_client.py" | PASS |
| CI grep gate (negative — violation reintroduced) | created scheduler/agents/_gate_negative_test_temp.py with `_x = AsyncAnthropic(api_key="sk-test")`; ran gate | exit 1; "FAIL — raw AsyncAnthropic(...) ... found"; violation cites file:line; cleanup re-run exits 0 | PASS |
| Companion tenant-isolation gate | `bash scripts/verify-tenant-isolation.sh` | exit 0; PASS | PASS |
| Live entry-point smoke import | `uv run python -c "from agents.daily_summary import run_daily_summary, run_juno_daily_summary; from agents.weekly_sweeper import run_weekly_sweeper; from agents.content_agent import fetch_stories, deduplicate_stories; from anthropic_client import get_anthropic_client; print('ALL OK')"` | "ALL OK" exit 0 | PASS |
| Dead-function ImportError (negative invariant 10) | `uv run python -c "from agents.content_agent import review"` | `ImportError: cannot import name 'review' from 'agents.content_agent'` (analogous for check_compliance + is_gold_relevant_or_systemic_shock) | PASS |
| Boot-time env-var visibility | `env -u SEVA_ANTHROPIC_API_KEY -u JUNO_ANTHROPIC_API_KEY -u ANTHROPIC_RESOLVER_STRICT uv run python -c "import asyncio, logging; logging.basicConfig(level=logging.INFO); from worker import _validate_env; asyncio.run(_validate_env())"` | 2 WARNING lines (SEVA + JUNO "not set — resolver will fall back...") + 1 INFO line ("ANTHROPIC_RESOLVER_STRICT: false (resolver will fall back gracefully)") | PASS |

All behavioral spot-checks PASS.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| `scheduler/agents/daily_summary.py` | (import) | F401 `agents.juno_relevance.HAIKU_MODEL` unused | Info | Pre-existing per Phase 10; documented in deferred-items.md; verified pre-existing in main@c022a2b. Not a Phase 12 regression. |
| `scheduler/agents/weekly_sweeper.py` | 44 | F401 `sqlalchemy.select` unused | Info | Pre-existing per v3.0 Phase 9 (select() calls rewritten to scoped helpers; bare import left behind). Not a Phase 12 regression. |
| `scheduler/scripts/uat_voice_calibration.py` | 56 | F401 `_build_juno_world_events_section` unused | Info | Pre-existing per Phase 10 DEF-10. Not a Phase 12 regression. |
| `scheduler/tests/agents/test_daily_summary_prune.py` | (4 sites) | RuntimeWarning: "coroutine 'AsyncMockMixin._execute_mock_call' was never awaited" | Info | Pre-existing test-infrastructure warning. Documented in 12-01-SUMMARY. Not a Phase 12 regression. |

**No BLOCKER or WARNING anti-patterns introduced by Phase 12.** All 4 noise items are pre-existing and explicitly tracked in `.planning/phases/12-per-tenant-anthropic-api-key/deferred-items.md` per executor scope-boundary rule.

---

### Operator Post-Deploy Actions (CONTEXT D-04) — PENDING

The phase ships the code-side substance. The following operator-side actions remain PENDING and are NOT phase verification responsibility (per CONTEXT D-04 + 12-03-SUMMARY user-setup checklist):

1. Set `SEVA_ANTHROPIC_API_KEY` in Railway scheduler service env vars.
2. Set `JUNO_ANTHROPIC_API_KEY` in Railway scheduler service env vars.
3. Leave `ANTHROPIC_API_KEY` (shared) UNCHANGED.
4. Leave `ANTHROPIC_RESOLVER_STRICT` unset (defaults to false) until verification passes.
5. Wait for next scheduler restart; confirm Railway boot logs show `ENV SEVA_ANTHROPIC_API_KEY: SET ✓` + `ENV JUNO_ANTHROPIC_API_KEY: SET ✓` + `ENV ANTHROPIC_RESOLVER_STRICT: false (...)`.
6. Manually fire Seva daily summary; verify request appears in Seva Anthropic console.
7. Manually fire Juno daily summary; verify request appears in Juno Anthropic console; verify Seva console does NOT show it.
8. Cross-check structured log lines `anthropic_call event=anthropic_call company=<tenant> key_fingerprint=<last-8>` in Railway logs.
9. Once both consoles show correct attribution, flip `ANTHROPIC_RESOLVER_STRICT=true` as permanent safety net.
10. Rollback path: unset per-tenant vars + STRICT=false → graceful fallback to shared key.

Also pending (operator/CI maintainer task, NOT Claude): add `bash scripts/verify-anthropic-resolver.sh` to the CI pipeline alongside `bash scripts/verify-tenant-isolation.sh`.

These pending actions are listed in `human_verification` frontmatter but do NOT block phase-verdict PASS — they are documented operator responsibilities per CONTEXT D-04, and the code-side substance is complete.

---

### Anticipated Deviations (Planner-Flagged, Orchestrator-Pre-Validated)

These were called out by the planner in advance and verified as documented (NOT verification failures):

1. **`content_agent.py:1108` reclassification**: CONTEXT.md listed line 1108 as one of "3 dead sites" inside `review()` and related draft-validation functions. Planner-grep verified the line lives inside LIVE `_do_fetch` → `fetch_stories()` (called by `daily_summary.py:36` + `weekly_sweeper.py:47`). Plan 02 refactored as Seva site (timeout=30.0) instead of deleting. Net effect: 5 instantiation sites refactored (not 3), 3 dead functions + 1 orphan helper deleted (not 3 functions exactly). **VERIFIED**: content_agent.py:868 has resolver call; live exports preserved (line 933 fetch_stories, line 218 deduplicate_stories); 3 dead functions ImportError on import.
2. **`scheduler/scripts/uat_voice_calibration.py:377` added as 5th refactor site**: CONTEXT.md's D-09 grep was scoped to `scheduler/agents/` and missed the `scheduler/scripts/` one-shot. Plan 02 refactored as Juno site (not exempted). **VERIFIED**: uat_voice_calibration.py:382 has `get_anthropic_client("juno", timeout=JUNO_SONNET_TIMEOUT)`.
3. **Plan 01 omitted `model` field from per-call structured log**: CONTEXT D-03 example log included `model="claude-sonnet-4-6"`, but resolver cannot know caller's model at resolve-time (model bound at `.messages.create()` time). Documented as Claude's-Discretion deviation in 12-01-SUMMARY. **VERIFIED**: `_log_call` at anthropic_client.py:111-123 logs `event` + `company` + `key_fingerprint` only; inline comment at line 109-110 explains the omission.
4. **Plan 02 deleted 1 orphan helper (`_extract_check_text`) in addition to 3 specified dead functions**: Per Plan 02 implementer-note, when a private helper has zero non-test callers post-purge, delete it too. `_extract_check_text`'s only callers were `review()` (deleted) and a test (deleted). **VERIFIED**: grep `^(async )?def _extract_check_text` returns 0 matches in content_agent.py.

All 4 anticipated deviations are documented in plan SUMMARYs and verified as correctly executed.

---

### Goal-Backward Summary: Does the codebase deliver what the phase promised?

**YES.** The phase goal stated:

> Every Anthropic call routes through a single resolver (`get_anthropic_client(company_id)`) that selects the right per-tenant key. Seva's calls bill to `SEVA_ANTHROPIC_API_KEY`; Juno's to `JUNO_ANTHROPIC_API_KEY`. Local-dev keeps working via graceful fallback to shared `ANTHROPIC_API_KEY`. After this phase, every downstream v3.1 LLM call automatically attributes correctly with no per-call-site change required.

Working backwards from the goal:

- **"Single resolver"** — `scheduler/anthropic_client.py::get_anthropic_client` exists with the contracted signature and is the ONLY production AsyncAnthropic instantiation site (enforced by CI grep gate). VERIFIED.
- **"Selects the right per-tenant key"** — `getattr(settings, f"{company_id}_anthropic_api_key")` at resolver line 73-74 + tested by `test_get_anthropic_client_seva_routes_to_seva_key` + `test_get_anthropic_client_juno_routes_to_juno_key`. VERIFIED.
- **"Seva calls bill to SEVA_..., Juno calls bill to JUNO_..."** — All 5 production sites use hardcoded `"seva"` or `"juno"` literal (Invariant 7). Anthropic API uses the api_key in the constructor to determine which account bills the request, and the resolver passes the correct per-tenant key per company. Dashboard verification = operator post-deploy task per CONTEXT D-04 (HUMAN-PENDING).
- **"Local-dev keeps working via graceful fallback"** — WARN-once fallback to `ANTHROPIC_API_KEY` implemented at resolver lines 86-95; tested by `test_fallback_emits_warn_once_per_company`; boot smoke test confirms WARNING log lines fire when per-tenant unset. VERIFIED.
- **"Every downstream v3.1 LLM call automatically attributes correctly with no per-call-site change required"** — Downstream agents (`juno_relevance.py`, `juno_refusal_detector.py`, `ontario_law.py`) preserve `client: AsyncAnthropic` parameter pattern (Invariant 8); orchestrators (`run_daily_summary`, `run_juno_daily_summary`, `run_weekly_sweeper`) inject the resolved client downward. New v3.1 sites (Phase 14 Calendar, Phase 15 Sweeper synthesis) will inherit attribution automatically by calling `get_anthropic_client("juno", ...)` at their orchestrator level — the CI grep gate enforces this forever. VERIFIED.

The codebase achieves the goal. The remaining work (operator Railway env-var configuration + dashboard attribution verification + STRICT toggle flip + CI pipeline integration of the grep gate) is operator-side per CONTEXT D-04 — out of phase scope.

---

## Final Phase Verdict: **PASS**

- **7/7 observable truths** verified
- **4/4 requirements** (KEY-01..04) satisfied at code level (KEY-04 dashboard observation is operator post-deploy task)
- **12/12 preserved invariants** verified
- **10/10 key artifacts** pass Level 1-3 (Exists, Substantive, Wired)
- **10/10 key links** WIRED
- **All data-flow traces** FLOWING (Level 4)
- **All behavioral spot-checks** PASS (including negative-test for grep gate)
- **0 phase-introduced anti-patterns** (4 documented pre-existing noise items in `deferred-items.md`)
- **All 4 planner-anticipated deviations** correctly executed per plan documentation
- **Full scheduler regression suite GREEN**: 323 passed, 1 skipped (exact baseline match — -13 deleted dead-code tests + 5 new resolver tests = -8 net vs Phase 11's 331)
- **Backend regression**: 184 passed, 5 skipped (no Phase 12 touch points; baseline confirmed by orchestrator)
- **Frontend regression**: 168 passed (no Phase 12 touch points; baseline confirmed by orchestrator)
- **Both CI grep gates** (verify-tenant-isolation.sh + verify-anthropic-resolver.sh) exit 0 on current tree
- **Negative-test smoke**: grep gate catches reintroduced raw `AsyncAnthropic(api_key=...)` violations and reports file:line correctly

Phase 12 code-side substance is complete. The operator post-deploy actions listed in `human_verification` frontmatter (Railway env-var configuration + Anthropic console attribution verification + STRICT toggle flip + CI pipeline integration) are operator responsibilities per CONTEXT D-04 and 12-03-SUMMARY user-setup checklist — they do NOT block this phase verdict.

---

_Verified: 2026-05-20T20:05:00Z_
_Verifier: Claude (gsd-verifier)_
