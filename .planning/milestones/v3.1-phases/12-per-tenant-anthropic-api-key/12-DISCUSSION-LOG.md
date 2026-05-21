# Phase 12: Per-tenant Anthropic API Key - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `12-CONTEXT.md` — this log preserves the alternatives considered.

**Date:** 2026-05-20
**Phase:** 12-per-tenant-anthropic-api-key
**Areas discussed:** Fallback + strict mode, Attribution verification, Dead-code call sites, Call site signature

---

## Fallback + Strict Mode

### Q1: When a tenant-specific Anthropic key is missing, what should the resolver do?

| Option | Description | Selected |
|--------|-------------|----------|
| Log WARN once + fall back | (Recommended) On startup or first call per tenant, log a single WARN line ('JUNO_ANTHROPIC_API_KEY unset — using shared ANTHROPIC_API_KEY'). Subsequent calls reuse the cached client silently. Preserves local-dev workflow (devs typically have only one key) while making the misconfig visible in Railway logs. | ✓ |
| Silent fallback | Fall back without any log. Cleanest for local-dev but you'd never notice if prod was misconfigured — Juno cost would silently bill to Seva's dashboard. | |
| Hard-fail in prod, soft in dev | Detect prod (e.g., RAILWAY_ENVIRONMENT=production) and refuse to start if tenant keys missing; fall back silently in dev. Strongest safety but couples resolver to deployment env-detection. | |

**User's choice:** Log WARN once + fall back
**Notes:** Decision captured as D-01. Rationale: operator-facing visibility in Railway logs without coupling resolver to env-detection.

### Q2: Add an opt-in STRICT_KEY_MODE env var?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — opt-in strict mode | (Recommended) Add ANTHROPIC_RESOLVER_STRICT=true env var. When set, the resolver raises on any per-tenant key fallback. You'd flip this on in Railway AFTER setting both per-tenant keys — gives you a hard safety net against accidentally unsetting one key later. Costs nothing when off. | ✓ |
| No — keep it simple | Just WARN log + fallback. If a per-tenant key gets unset accidentally, the WARN log is the only signal. Less code, fewer env vars to remember. | |

**User's choice:** Yes — opt-in strict mode
**Notes:** Decision captured as D-02. Rationale: prod safety net flipped on AFTER successful key rollout; off by default preserves local-dev workflow.

---

## Attribution Verification

### Q3: How should we verify per-tenant cost attribution post-deploy?

| Option | Description | Selected |
|--------|-------------|----------|
| Log line + manual check | (Recommended) Resolver logs a structured line at every Anthropic call: 'anthropic_call company=juno key_fingerprint=ab12cd34 model=claude-sonnet-4-6' (fingerprint = last 8 chars of api key, NOT the full key). Operator does one manual fire post-deploy + spot-checks Anthropic console for each tenant. Cheap, reversible, observable in Railway logs forever. | ✓ |
| Log line only | Same structured log, but no operator-console-check step. Trust the logs; rely on Anthropic's monthly invoice for attribution verification. Lower operator friction; if logs are wrong, you find out late. | |
| Console check only | Manual operator fire + Anthropic dashboard check, no extra logging. Saves a touch of log volume but you lose the audit trail — future debugging requires another manual fire. | |

**User's choice:** Log line + manual check
**Notes:** Decisions captured as D-03 (structured log) + D-04 (operator workflow). Belt-and-braces: logs catch silent misrouting, console-check catches log-write bugs.

### Q4: Should we add an automated regression test that asserts the right key is used per company_id?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — unit test on resolver | (Recommended) Test in scheduler/tests asserts get_anthropic_client('seva') returns a client whose api_key matches SEVA_ANTHROPIC_API_KEY (and same for juno). Catches future regressions where a typo'd company_id silently routes to wrong key. Cheap to write, runs in CI on every commit. | ✓ |
| No — trust the log + console check | Skip the test; rely on operator's post-deploy verification. Lower code volume; future regressions would need to slip past code review. | |

**User's choice:** Yes — unit test on resolver
**Notes:** Decision captured as D-05. Unit test asserts (a) Seva → SEVA_ANTHROPIC_API_KEY; (b) Juno → JUNO_ANTHROPIC_API_KEY; (c) WARN-once on fallback; (d) STRICT raises on missing; (e) cache returns same instance.

---

## Dead-code Call Sites

### Q5 (initial): What should Phase 12 do with content_agent.py's 3 dead Anthropic instantiation sites?

| Option | Description | Selected |
|--------|-------------|----------|
| Delete the file | (Recommended IF no remaining imports) Confirm content_agent.py has zero callers in production code (only its own tests), then delete the file + its test file. Cleanest. Mirrors the v2.1 Phase 8 UI-06 dead-code-strip precedent. | ✓ (initial — superseded by Q5b below) |
| Exempt from grep gate | Add inline comments at each of the 3 sites + add exception to scripts/verify-anthropic-resolver.sh. Lower risk, higher technical debt. | |
| Refactor through resolver | Pretend content_agent.py is live, refactor its 3 sites through get_anthropic_client('seva'). Cleanest from a code-consistency standpoint but spends time on dead code. | |
| Investigate first | Defer the decision until I verify whether content_agent.py truly has zero production callers. Make the call based on what I find. | |

**Verification finding (post-grep):** `content_agent.py` is NOT pure dead code. Two LIVE production imports found:
- `scheduler/agents/weekly_sweeper.py:47` — `from agents.content_agent import deduplicate_stories`
- `scheduler/agents/daily_summary.py:36` — `from agents.content_agent import fetch_stories`

Deleting the whole file would break Seva + Juno daily summary + Seva weekly sweeper. Initial "Delete the file" answer SUPERSEDED.

### Q5b (revised): Given content_agent.py has live exports, what now?

| Option | Description | Selected |
|--------|-------------|----------|
| Delete dead functions only | (Recommended) Surgically delete the dead Anthropic-using functions inside content_agent.py (lines around 428, 483, 1108 — likely the review(), draft validation, and one more) plus any test in test_content_agent.py that tests them. Keep fetch_stories + deduplicate_stories + their tests. Lower line count, cleanest grep gate result. | ✓ |
| Exempt from grep gate | Keep all dead functions intact. Add inline '# DEAD CODE — see CLAUDE.md 260420-sn9' comments at the 3 sites + exception in scripts/verify-anthropic-resolver.sh. Lower-risk (no behavior change), higher tech-debt. | |
| Refactor through resolver | Pretend the dead functions are live, refactor their 3 sites to use get_anthropic_client('seva'). Cleanest from grep-gate POV; spends time on dead code; will need re-purging later. | |

**User's choice:** Delete dead functions only
**Notes:** Decision captured as D-06. Mirrors v2.1 Phase 8 UI-06 dead-code-strip precedent — preserve live exports, excise dead.

---

## Call Site Signature

### Q6: How should call sites invoke the resolver?

| Option | Description | Selected |
|--------|-------------|----------|
| Always explicit company_id | (Recommended) Every call site writes get_anthropic_client(company_id) with company_id resolved from the surrounding scope (caller passes it as a function arg). Even at module-scoped Juno-only sites, the call is get_anthropic_client('juno') with a hardcoded literal + inline comment. Pros: grep gate is trivial (any 'AsyncAnthropic(' outside resolver = violation). Cons: slightly more verbose at Juno-only sites. | ✓ |
| Caller-injected client (current) | Keep the existing pattern where juno_relevance.py / juno_refusal_detector.py / ontario_law.py take 'client: AsyncAnthropic' as a parameter. Only the top-level orchestrator (run_daily_summary, run_juno_daily_summary, run_weekly_sweeper) calls get_anthropic_client() and threads the client downward. Pros: zero churn in agent modules. Cons: caller must always remember to pass the right tenant's client. | (partially adopted — see D-07a below) |
| Module-scoped factories | Each tenant-specific module gets a module-level helper: juno_relevance.py defines _get_juno_client() = lambda: get_anthropic_client('juno') and uses it internally. Lower verbosity at call sites; more indirection. | |

**User's choice:** Always explicit company_id
**Notes:** Decisions captured as D-07 (explicit literal at instantiation sites) + D-07a (downstream agents keep caller-injected pattern). Refined interpretation: explicit-literal applies to the 3 production INSTANTIATION sites (`daily_summary.py` ×2 + `weekly_sweeper.py`). Downstream agents that receive client as a parameter (`juno_relevance.py`, `juno_refusal_detector.py`, `ontario_law.py`) keep the caller-injected pattern — they NEVER instantiate, so the grep gate is satisfied. This concentrates resolver call surface to 3 sites + preserves test mockability for downstream agents.

---

## Claude's Discretion

- **Resolver module location** — `scheduler/anthropic_client.py` based on the `scheduler/queries/scoped.py` precedent. Planner may relocate if a stronger pattern emerges; deviation must be documented in plan summary.
- **Function signature shape** — `get_anthropic_client(company_id: Literal["seva", "juno"], *, timeout: float = 60.0) -> AsyncAnthropic`. Planner may adjust kwargs/defaults if needed.
- **Caching implementation** — module-level dict keyed on `(company_id, timeout)`. Planner may use `functools.lru_cache` or a class wrapper if cleaner.
- **Key fingerprint format** — `api_key[-8:]` (operator-friendly, matches Anthropic console) OR `hashlib.sha256(api_key.encode()).hexdigest()[:8]` (more secure). Planner picks.
- **WARN log structure** — Use `structlog` if available; otherwise plain `logger.warning(...)`. Planner aligns with existing scheduler logging idiom.

## Deferred Ideas

- **Per-tenant SerpAPI key** — Same cost-attribution problem; deferred to v3.2+ (`OPS-SERPAPI-KEY-v3X`). Out of scope for v3.1 because SerpAPI cost is bounded by smaller $50/mo cap.
- **Per-tenant cost dashboard** — Phase 12 enables it; building it is `OPS-DASH-v3X`, deferred.
- **Anthropic SDK upgrade** — Phase 12 keeps `anthropic 0.86.0`; resolver becomes the single update site if SDK changes.
