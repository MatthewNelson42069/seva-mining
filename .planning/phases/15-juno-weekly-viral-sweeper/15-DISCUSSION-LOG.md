# Phase 15: Juno Weekly Viral Sweeper - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `15-CONTEXT.md` — this log preserves the alternatives considered.

**Date:** 2026-05-20
**Phase:** 15-juno-weekly-viral-sweeper
**Areas discussed:** Defence-sector X queries, Virality compute over 3 sub-arrays, Sweeper system prompt strategy, Module structure + rollout

---

## Defence-Sector X Queries

### Q1: Defence-sector X query strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Single combined query | (Recommended) Mirror Seva — 1 search_recent_tweets call per cron with combined query. Quota-friendly (1 query/week). | ✓ |
| Multiple queries combined client-side | 3-5 separate queries (reporters, think-tanks, hashtags), merge + dedupe + rank client-side. 3-5x quota. | |
| Defer to research-phase | Mark JSWEEP-02 as discuss-decision-pending, let gsd-phase-researcher do a web-search pass during plan-phase. | |

**User's choice:** Single combined query
**Notes:** D-01. Mirrors Seva pattern. Quota math: ~4 calls/month × 100 tweets = ~400 tweets/month, deep margin within X API Basic tier (~10K/month cap; Seva uses ~400/month, combined ~800/month).

### Q2: Which specific X accounts/handles + hashtags?

| Option | Description | Selected |
|--------|-------------|----------|
| I'll pick now from curated list | Operator-driven curation. | |
| Use recommended starter set | (Recommended) Lock starter set: think-tanks (@RUSI_org @CSIS @IISS_org), defence press (@DefenseNews @BreakingDefense @DefenseScoop @JanesIntel), Canadian (@CDA_CDAI @canadaforces), tags (#defence #NATO). Excludes defence-prime cashtags per anti-feature. Tunable mid-execution. | ✓ |
| Defer to plan-phase researcher | Let gsd-phase-researcher web-search for high-signal defence handles + hashtags. | |

**User's choice:** Use recommended starter set
**Notes:** D-02. Defence-prime cashtags ($LMT, $RTX, $LDOS, $BAESY, $GD) explicitly EXCLUDED per PROJECT.md anti-feature (equity/financial signals on defence primes). Planner may verify handle existence + may surface higher-signal alternatives during research. Starter set is v1.0; tunable.

---

## Virality Compute Over 3 Sub-Arrays

### Q3: How should Juno sweeper compute virality across its 3 sub-arrays?

| Option | Description | Selected |
|--------|-------------|----------|
| Combine all 3 into one URL set | (Recommended) Read defence_news + canadian_procurement + world_events, concat into list, dedupe by URL, equal weight. Simplest; mirrors Seva's single-substrate. | ✓ |
| Weight by section (Defence News 2x) | Combine all 3 but give Defence News stories 2x weight in cross-reference rank. | |
| Defence News only | Read only defence_news. Ignore Procurement + World Events for sweeper. Most conservative; least coverage. | |
| Per-section virality + top-N each | Compute virality per-section, present as 3 sweeper sub-cards. Richest but most complex; Tab 3 UI redesign required. | |

**User's choice:** Combine all 3 into one URL set
**Notes:** D-03. Phase 9 NULL-guard preserved (`(row.raw_sources_jsonb or {})`). Status mapping inherits Seva pattern verbatim: completed/partial/failed. Per-section approach deferred (could be future enhancement).

---

## Sweeper System Prompt Strategy

### Q4: How should the Juno sweeper Sonnet system prompt be structured?

| Option | Description | Selected |
|--------|-------------|----------|
| New dedicated juno sweeper prompt | (Recommended) Add NEW `JUNO_SWEEPER_SYSTEM_PROMPT` in juno/prompts.py alongside daily-summary prompt. Includes Janes/CSIS voice + anti-tactical clause + "3 content angles" task framing + defence-sector audience description. Cleanest separation by task. | ✓ |
| Reuse Phase 10 prompt verbatim | Pass existing daily-summary prompt to sweeper Sonnet call without changes. Lower scope; risk: task-shape mismatch (3-section brief vs 3 content angles). | |
| Extend Phase 10 prompt with sweeper task suffix | Concatenate Phase 10 prompt + sweeper task appendix at runtime. Hybrid; mixes concerns. | |

**User's choice:** New dedicated juno sweeper prompt
**Notes:** D-04. Anti-tactical clause string-equality contract: bytes from Phase 10's daily-summary prompt's anti-tactical block MUST appear verbatim in `JUNO_SWEEPER_SYSTEM_PROMPT`. Grep-checkable. Anthropic client resolution: `get_anthropic_client('juno', timeout=JUNO_SONNET_TIMEOUT)` per Phase 12 D-09 with hardcoded literal per Phase 12 D-07.

### Q5: Should sweeper reuse Phase 10 refusal-detector pattern?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — reuse verbatim | (Recommended) Phase 10 established 7-substring regex refusal detector + retry-once-with-framing-nudge + `status='partial'` on 2nd-attempt failure. Defence content most likely refusal trigger; load-bearing safety net. | ✓ |
| No — sweeper output is less risky | Skip refusal-detector to reduce scope. Risk: silent malformed output if Sonnet refuses one angle. | |

**User's choice:** Yes — reuse verbatim
**Notes:** D-05. Imports `juno_refusal_detector` module from Phase 10 unchanged. Single source of truth for refusal contract.

---

## Module Structure + Rollout

### Q6: Module structure — separate Juno sweeper module or refactor Seva module?

| Option | Description | Selected |
|--------|-------------|----------|
| New scheduler/agents/juno_weekly_sweeper.py | (Recommended) NEW FILE parallel to v3.0 Phase 10 pattern. Imports shared helpers from `weekly_sweeper.py` (e.g., `_engagement_score`). ~500-700 LOC. Cleaner separation; D-10 zero-regression for Seva trivially held. | ✓ |
| Refactor weekly_sweeper.py for multi-tenancy | Extend existing module to accept company_id parameter. Smaller diff but tighter coupling. Risk: D-10 contract harder to maintain. | |

**User's choice:** New scheduler/agents/juno_weekly_sweeper.py
**Notes:** D-06. Shared-helper extraction strategy (planner picks): (a) export from `weekly_sweeper.py` and import into Juno file (preferred for code reuse if it doesn't break D-10), (b) duplicate in Juno module, or (c) refactor into `sweeper_helpers.py`. Default: (a) unless it breaks D-10.

### Q7: Operator rollout sequence

| Option | Description | Selected |
|--------|-------------|----------|
| Mirror Phase 10 exactly | (Recommended) 4-step: deploy disabled → manual smoke fire → voice UAT → flip env gate. Same precedent that worked for Phase 10 daily-summary. | ✓ |
| Simpler rollout (single smoke fire) | 3-step: deploy disabled → fire once → flip env gate. Skips formal voice UAT. Risk: voice misses on first real fire. | |

**User's choice:** Mirror Phase 10 exactly
**Notes:** D-07. Voice UAT criteria captured in CONTEXT.md `<specifics>` for operator reference. Rollback path: unset env var → next deploy registers no cron.

---

## Claude's Discretion

- **Exact handle list verification** — planner-research validates that the 9 X handles exist + are active (e.g., @RUSI_org might be @RUSI_org or @RUSI; planner does quick verification). May surface higher-signal alternatives.
- **Shared-helper extraction** — D-06 mentions planner picks (a) export/import vs (b) duplicate vs (c) refactor into shared module. Default (a) unless it breaks D-10.
- **X query constants file location** — `scheduler/companies/juno/x_queries.py` is recommended; planner may pick alternative naming or use `juno/__init__.py` re-export.
- **CLI hook** — if scheduler.cli doesn't already exist or doesn't have a smoke-fire entry, planner adds a thin CLI shim.
- **Tab 3 empty-state copy** — JSWEEP-05 leaves room for "Juno's first viral sweep runs Sunday 08:00 PT. Check back then." or "analogous Janes-voice copy". Planner picks based on existing Seva pattern or operator inputs.
- **Frontend short-circuit removal mechanism** — D-08 mirrors Phase 14 D-01 exactly. Planner verifies that the existing TanStack Query hook + sweep card rendering is multi-tenant-aware before deletion. If Phase 9 scaffolding is incomplete, planner adjusts scope.

## Deferred Ideas

- Per-section sweeper sub-cards (3 cards instead of 1) — D-03 picks single-substrate union.
- Multi-query parallel sweep — D-01 picks single combined query.
- Tier-2 defence X reporters — beyond D-02 starter set; mid-execution tunable.
- Defence-prime cashtags — permanent anti-feature per PROJECT.md.
- LinkedIn / IG ingestion — X API only per CLAUDE.md.
- Auto-posting of sweeper angles — hard prohibition per CLAUDE.md.
- Sweeper system-prompt iteration — if first 2-4 weeks of production surfaces issues, iterate in v3.2 (per ROADMAP "Out of Scope").
