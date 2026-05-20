# Phase 12: Per-tenant Anthropic API Key - Context

**Gathered:** 2026-05-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Every Anthropic client instantiation in the scheduler routes through a single resolver — `get_anthropic_client(company_id)` — that picks the right per-tenant API key. Seva's calls bill to `SEVA_ANTHROPIC_API_KEY`; Juno's calls bill to `JUNO_ANTHROPIC_API_KEY`. Local-dev keeps working unchanged via graceful fallback to the existing shared `ANTHROPIC_API_KEY` when per-tenant vars are unset. After this phase, cost-attribution between Seva and Juno is clean at the Anthropic dashboard level — every downstream v3.1 LLM call (Sweeper Sonnet synthesis in Phase 15; any future Calendar drafting) automatically attributes correctly with no per-call-site change required.

**In scope:**
- New resolver module + per-tenant key resolution + caching + WARN-once-on-fallback semantics
- Refactor of 3 production Anthropic instantiation sites (`scheduler/agents/daily_summary.py` ×2 + `scheduler/agents/weekly_sweeper.py`)
- Surgical deletion of dead Anthropic-using functions inside `scheduler/agents/content_agent.py` (live exports `fetch_stories` + `deduplicate_stories` retained)
- New CI grep gate (`scripts/verify-anthropic-resolver.sh`) forbidding `AsyncAnthropic(` outside the resolver module
- Optional opt-in `ANTHROPIC_RESOLVER_STRICT=true` env var → prod safety net
- Structured log line at every Anthropic call for observable attribution
- Unit test asserting per-`company_id` key routing correctness
- New Railway env vars `SEVA_ANTHROPIC_API_KEY` + `JUNO_ANTHROPIC_API_KEY` (config layer only; operator flips the actual values post-deploy)

**Out of scope:**
- Backend Anthropic calls (zero instantiation sites exist in `backend/app/` — only env var declaration in `config.py`)
- Per-tenant SerpAPI key (only Anthropic is per-tenant in v3.1; SerpAPI stays shared)
- Per-tenant cost dashboard / monthly invoice splitting (OPS-DASH-v3X — uses Phase 12's separation but deferred)
- Changing call semantics / timeouts / models — every call site keeps its existing model + timeout + retry behavior; only the client instantiation changes

</domain>

<decisions>
## Implementation Decisions

### Resolver Behavior
- **D-01 Fallback policy** — When `SEVA_ANTHROPIC_API_KEY` or `JUNO_ANTHROPIC_API_KEY` is unset, the resolver falls back to the existing shared `ANTHROPIC_API_KEY` and emits exactly ONE WARN-level log line per tenant per process lifetime: `"JUNO_ANTHROPIC_API_KEY unset — using shared ANTHROPIC_API_KEY for company_id='juno'"`. Subsequent calls reuse the cached client silently — no log noise. If shared `ANTHROPIC_API_KEY` is ALSO unset, raise `RuntimeError` immediately (existing failure mode preserved).
- **D-02 Strict mode opt-in** — Add `ANTHROPIC_RESOLVER_STRICT` env var (default `false`). When set to `true`, the resolver RAISES `RuntimeError` instead of falling back to the shared key. Operator's intended rollout: deploy with `STRICT=false`, set per-tenant keys in Railway, fire smoke test to confirm attribution, then flip `STRICT=true` as a permanent safety net against accidentally unsetting a per-tenant key in the future. The strict-mode check happens at resolver-call time (first call per tenant), NOT at process boot — local-dev workflow stays unchanged when STRICT is off.

### Call-Site Pattern
- **D-07 Always-explicit company_id at instantiation sites** — Every production Anthropic instantiation site uses `get_anthropic_client('seva')` or `get_anthropic_client('juno')` with a hardcoded string literal (NOT a variable named `company_id`). Hardcoded literals are intentional: each call site is unambiguously one tenant, the literal is grep-able, and a typo'd `company_id` variable from somewhere else cannot accidentally route to the wrong key.
- **D-07a Downstream agents stay caller-injected** — `scheduler/agents/juno_relevance.py`, `scheduler/agents/juno_refusal_detector.py`, `scheduler/agents/ontario_law.py` keep their existing `client: AsyncAnthropic` parameter pattern. They do NOT instantiate clients themselves — orchestrators (`run_daily_summary`, `run_juno_daily_summary`, `run_weekly_sweeper`) instantiate via resolver and thread the client downward. This preserves test mockability (existing tests `monkeypatch` the injected client) and keeps the resolver call surface concentrated to 3 sites.

### Production Instantiation Sites (Locked List)
- **D-09 Three sites refactored** — Exactly these 3 production sites swap from raw `AsyncAnthropic(api_key=settings.anthropic_api_key, timeout=...)` to `get_anthropic_client('seva' | 'juno', timeout=...)`:
  1. `scheduler/agents/daily_summary.py:583` (Seva daily summary) → `get_anthropic_client('seva', timeout=60.0)`
  2. `scheduler/agents/daily_summary.py:1226` (Juno daily summary) → `get_anthropic_client('juno', timeout=JUNO_SONNET_TIMEOUT)`
  3. `scheduler/agents/weekly_sweeper.py:399` (Seva weekly sweeper) → `get_anthropic_client('seva', timeout=...)` (preserves existing timeout)
  - `timeout` stays a kwarg passed through to the underlying `AsyncAnthropic` constructor — resolver is a thin wrapper, not a behavior modifier.

### Dead Code Cleanup
- **D-06 Surgically delete dead Anthropic-using functions in content_agent.py** — `scheduler/agents/content_agent.py` has 3 `AsyncAnthropic(...)` sites (lines 428, 483, 1108) inside `review()` and related draft-validation functions. Per CLAUDE.md historical notes (260420-sn9 sub-agent purge), no production caller invokes these. Phase 12 deletes those specific dead functions + their corresponding tests in `scheduler/tests/test_content_agent.py`. The live exports `fetch_stories()` (used by `daily_summary.py` line 36 + Juno daily summary) and `deduplicate_stories()` (used by `weekly_sweeper.py` line 47) are preserved verbatim. Net effect: `content_agent.py` shrinks; grep gate has zero exceptions to manage; future maintainers see only live code.

### Verification & Observability
- **D-03 Structured log at every Anthropic call** — Resolver logs ONCE per call: `{"event": "anthropic_call", "company": "juno", "key_fingerprint": "ab12cd34", "model": "claude-sonnet-4-6"}`. `key_fingerprint` = SHA256(api_key)[:8] OR last-8-chars of api_key — implementation detail; key MUST NOT be logged in full. Observable forever in Railway logs without needing Anthropic console access.
- **D-04 Operator post-deploy verification workflow** — After v3.1 Phase 12 deploys: (1) operator sets `SEVA_ANTHROPIC_API_KEY` + `JUNO_ANTHROPIC_API_KEY` in Railway; (2) fires `python -m scheduler.cli run_daily_summary --company seva` (or analogous existing CLI); (3) checks Seva's Anthropic console for the request; (4) repeats for Juno. Both consoles must show only their own traffic; no cross-tenant attribution.
- **D-05 Resolver unit test** — `scheduler/tests/test_anthropic_client.py` (new file) asserts: (a) `get_anthropic_client('seva')` returns client with `api_key == SEVA_ANTHROPIC_API_KEY` when env is set; (b) same for juno; (c) WARN-once log emitted on fallback; (d) STRICT mode raises when per-tenant unset; (e) cache returns the same instance on repeated calls for same `company_id`. Uses `monkeypatch.setenv` + mock `Anthropic` to avoid real API calls.

### Grep Gate
- **D-08 CI grep gate** — New script `scripts/verify-anthropic-resolver.sh` runs in CI (mirroring `scripts/verify-tenant-isolation.sh` from v3.0 Phase 9). Forbids `AsyncAnthropic(` and `Anthropic(api_key=` OUTSIDE the resolver module. Exceptions: (a) the resolver module itself (`scheduler/anthropic_client.py`); (b) test files (`scheduler/tests/**/*.py`) which monkey-patch and may instantiate mocks directly; (c) any future explicit exemption documented with inline `# anthropic-resolver: exempt — <reason>` comment. Exit non-zero on violation; integrated into the same CI lane as `verify-tenant-isolation.sh`.

### Resolver Module Shape (Claude's Discretion → Planner)
- Module location: `scheduler/anthropic_client.py` (top-level scheduler module, mirrors `backend/app/queries/scoped.py` pattern where shared helpers live one level above per-feature directories). Planner may relocate if a stronger pattern emerges; document any deviation in the plan summary.
- Function signature: `def get_anthropic_client(company_id: Literal["seva", "juno"], *, timeout: float = 60.0) -> AsyncAnthropic` — `Literal` enforces tenant set at type-check time; `timeout` kwarg passes through to `AsyncAnthropic`.
- Caching: module-level `_client_cache: dict[str, AsyncAnthropic]` keyed on `(company_id, timeout)` tuple. First call instantiates; subsequent calls return cached. Cache is process-lifetime (no invalidation needed — env vars don't change mid-process).
- WARN-once: track `_warned_companies: set[str]` at module scope. First fallback per company adds + logs; subsequent fallbacks silent.

### Folded Todos
None — no pending todos matched Phase 12 scope.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents (researcher, planner, executor) MUST read these before planning or implementing.**

### Phase 12 Roadmap Source
- `.planning/ROADMAP.md` §"Phase 12: Per-tenant Anthropic API Key" (lines ~83-153 — full phase block with goal, depends-on, inputs, outputs, success criteria, complexity, hard parts)
- `.planning/REQUIREMENTS.md` §"Per-tenant Anthropic API Key (KEY)" — atomic acceptance criteria for KEY-01..04

### Project-Level Constraints
- `.planning/PROJECT.md` §"Current Milestone: v3.1" §"Hard parts the roadmap addresses" item 4 ("Per-tenant Anthropic key without breaking local dev")
- `CLAUDE.md` Historical notes 2026-04-20 (260420-sn9 purge) + 2026-04-23 (260423-k8n purge) — context on why `content_agent.py` has dead Anthropic-using functions still present

### v3.0 Patterns This Phase Extends
- `.planning/milestones/v3.0-phases/09-multi-tenant-foundation/09-CONTEXT.md` D-03 (row-level `company_id` with `Literal["seva", "juno"]` — the resolver uses the same Literal type)
- `scripts/verify-tenant-isolation.sh` — pattern reused for `scripts/verify-anthropic-resolver.sh`
- `backend/app/queries/scoped.py` + `scheduler/queries/scoped.py` — pattern reused: shared helper module above per-feature dirs

### Code-Level References (current state for the planner)
- `scheduler/agents/daily_summary.py:583` — Seva Sonnet instantiation (refactor target #1)
- `scheduler/agents/daily_summary.py:1226` — Juno Sonnet instantiation (refactor target #2)
- `scheduler/agents/weekly_sweeper.py:399` — Seva sweeper Sonnet instantiation (refactor target #3)
- `scheduler/agents/juno_relevance.py:87` — `client: AsyncAnthropic` parameter (no change; receives injected client)
- `scheduler/agents/juno_refusal_detector.py:57` — `client: AsyncAnthropic` parameter (no change)
- `scheduler/agents/ontario_law.py:228, 303` — `client: AsyncAnthropic` parameter (no change)
- `scheduler/agents/content_agent.py:428, 483, 1108` — dead Anthropic instantiation (DELETE; surgically excise enclosing functions + their tests)
- `scheduler/agents/content_agent.py` `fetch_stories()` + `deduplicate_stories()` — LIVE exports, PRESERVE
- `scheduler/worker.py:613` — env var status logging (extend to also report `SEVA_ANTHROPIC_API_KEY` + `JUNO_ANTHROPIC_API_KEY` presence/absence + `ANTHROPIC_RESOLVER_STRICT` state)
- `scheduler/config.py` (or equivalent) — settings module declaring `anthropic_api_key`; add `seva_anthropic_api_key: str | None = None` + `juno_anthropic_api_key: str | None = None` + `anthropic_resolver_strict: bool = False`
- `backend/app/config.py:16` — backend declares `anthropic_api_key`; not modified in this phase (no backend instantiation sites)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`scheduler/queries/scoped.py` pattern** — Single shared helper module above per-feature agent dirs. Resolver follows the same shape: `scheduler/anthropic_client.py` exports `get_anthropic_client(company_id, *, timeout)`. Same import path style for callers (`from anthropic_client import get_anthropic_client`).
- **`scripts/verify-tenant-isolation.sh` pattern** — Bash script run in CI that greps for forbidden patterns outside whitelisted modules + emits human-readable violations + exits non-zero. `scripts/verify-anthropic-resolver.sh` mirrors this shape exactly.
- **`worker.py:613` env-var status logging** — Already prints booleans for `ANTHROPIC_API_KEY`, `SERPAPI_API_KEY`, etc. Extend to include the new per-tenant + strict-mode vars so operators see config state at scheduler boot.

### Established Patterns
- **`pydantic_settings.BaseSettings`** (in `scheduler/config.py`) — All env vars declared with type hints + defaults. Add `seva_anthropic_api_key: str | None = None` + `juno_anthropic_api_key: str | None = None` + `anthropic_resolver_strict: bool = False`. Pydantic auto-loads from `.env`/env vars.
- **`from typing import Literal`** + `Literal["seva", "juno"]` — Same type used in v3.0 Phase 9 for `ACTIVE_COMPANIES`. Resolver uses identical signature so it's a static-type-checked tenant set.
- **Caller-injected `client: AsyncAnthropic`** — `juno_relevance.py` / `juno_refusal_detector.py` / `ontario_law.py` already follow this. Phase 12 doesn't disturb it — orchestrators inject the resolved client downward.
- **Module-level cache dicts** — `juno_relevance.py` uses a module-level cache for some operations; `weekly_sweeper.py` also has module-scoped state. Resolver's `_client_cache` follows the same idiom.

### Integration Points
- **Railway env-vars panel** — Operator-facing surface. Phase 12 deploys ADD `SEVA_ANTHROPIC_API_KEY` + `JUNO_ANTHROPIC_API_KEY` + `ANTHROPIC_RESOLVER_STRICT` slots; operator fills values post-deploy. The existing `ANTHROPIC_API_KEY` slot REMAINS as fallback — do not delete or rename.
- **CI lane** — New `scripts/verify-anthropic-resolver.sh` runs alongside `scripts/verify-tenant-isolation.sh` (both are pre-merge gates).
- **Logging pipeline** — Resolver structured log lines go through the existing scheduler logger; no new infrastructure.

</code_context>

<specifics>
## Specific Ideas

- **Key fingerprint format** — `hashlib.sha256(api_key.encode()).hexdigest()[:8]` OR `api_key[-8:]` (last 8 chars of raw key). Last-8 is operator-friendly (matches Anthropic console's truncated display format). Planner picks; either is acceptable.
- **WARN log line shape** — Use structured log if scheduler uses `structlog`; otherwise `logger.warning("anthropic_resolver fallback: %s_ANTHROPIC_API_KEY unset, using shared ANTHROPIC_API_KEY for company_id=%s", company_id.upper(), company_id)`.
- **Rollout sequencing** — Code-first, then env vars. Deploy v3.1 Phase 12 with resolver in place + STRICT=false; resolver silently uses shared key via WARN-once fallback (acceptable transient state). Then operator sets per-tenant env vars in Railway → scheduler picks them up on next deploy/restart. Once both keys set + manual verification passes, operator can flip STRICT=true. No deploy gap; resolver gracefully handles every intermediate state.

</specifics>

<deferred>
## Deferred Ideas

- **Per-tenant SerpAPI key** — Same per-tenant cost-attribution problem exists for SerpAPI ($50/mo budget, currently single shared key). Out of scope for v3.1; tracked as `OPS-SERPAPI-KEY-v3X` for v3.2+ if cost-attribution becomes a real operator pain point. Deferred because (a) SerpAPI cost is bounded by the $50/mo cap (much smaller than Anthropic) and (b) Juno-vs-Seva Anthropic cost is the more obvious operator-visible attribution issue.
- **Per-tenant cost dashboard** — Phase 12 enables this (separate Anthropic consoles per tenant) but doesn't build it. `OPS-DASH-v3X` tracked separately.
- **Anthropic SDK version pin / upgrade** — Currently `anthropic 0.86.0` per `CLAUDE.md` Technology Stack table. Phase 12 does not change the SDK version; resolver is a thin wrapper around whatever SDK is installed. If a future SDK upgrade changes the `AsyncAnthropic` constructor signature, the resolver becomes the single update site (a nice byproduct).
- **Reviewed Todos (not folded)** — None reviewed; cross-reference returned 0 matches.

</deferred>

---

*Phase: 12-per-tenant-anthropic-api-key*
*Context gathered: 2026-05-20*
