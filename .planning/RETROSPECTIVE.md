# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v3.1 — Juno Feature Parity + Branding

**Shipped:** 2026-05-21
**Phases:** 5 (12-16) | **Plans:** 19 | **Commits:** ~82 | **Files changed:** 119 | **LOC:** +21,325 / -870

### What Was Built

- **Per-tenant Anthropic API key resolver** (Phase 12) — `get_anthropic_client(company_id)` with module-level cache, WARN-once-on-fallback, opt-in `ANTHROPIC_RESOLVER_STRICT` env gate, CI grep gate, hardcoded `'juno'`/`'seva'` literals at instantiation sites for grep-ability (D-07 contract).
- **Per-company branding** (Phase 13) — `companyBrandConfig.ts` registry pattern extending Phase 9 D-08 `companySectionConfig.ts`; Juno navy `oklch(0.58 0.14 245)` + "Juno Industries" wordmark + "J" letter mark + Juno favicon; `:root.dark[data-company='juno']` CSS selector (specificity 0,2,0 beats Phase 8's `.dark` 0,1,0); zero `if (company === 'juno')` branches; operator visual QA 10/10 PASS.
- **Juno Content Calendar Tab 2** (Phase 14) — port of v2.1 Phase 6 paper-planner UI to `/juno/calendar`; weekly Mon-Sun grid with auto-save on blur; full CRUD via existing `scoped_*()` helpers + `/api/{company}/calendar` router prefix from Phase 9; cross-tenant isolation tests pass; zero Seva regression.
- **Juno Weekly Viral Sweeper Tab 3** (Phase 15) — Sunday 08:00 PT APScheduler cron at lock 1021; 11 corrected defence-industry X handles + 2 hashtags (~261 chars within 512-char X API Basic limit); D-03a substrate fix extending Phase 10 writers to persist story-URL arrays under `raw_sources_jsonb` keys `defence_news`/`canadian_procurement`/`world_events`; Sonnet 4.6 synthesis with Janes/CSIS voice + verbatim anti-tactical clause (CI grep gate enforces string equality); refusal-detector pattern from Phase 10; `JUNO_SWEEPER_CRON_ENABLED` env gate; operator voice UAT APPROVED.
- **v3.1 audit cleanup bundle** (Phase 16) — five pre-existing carry-over items closed before archive (frontend ESLint, backend ruff, scheduler ruff, scheduler test RuntimeWarning, stale Phase-9-era `SummaryFeedPage` empty-state copy). Verifier 5/5 PASS; mirrors Phase 11 pattern; flipped audit verdict from `tech_debt` → `passed`.

### What Worked

- **Single-tenant → multi-tenant pattern preservation.** v3.1 reused every multi-tenant primitive from v3.0 (scoped query helpers, `/api/{company}/...` routers, `Literal["seva", "juno"]`, `companySectionConfig.ts`). Phase 14 was nearly a config-only port — Calendar landed in a single plan with zero cross-tenant leakage and zero Seva regression.
- **Researcher catching contract bugs before planning.** Phase 13 researcher caught the CSS specificity bug (naive `:root[data-company='juno']` 0,1,0 would lose to Phase 8's `.dark` 0,1,0 — recommended `:root.dark[data-company='juno']` 0,2,0). Phase 15 researcher caught D-03 substrate contradiction (Phase 10 stored only diagnostic counts, sweeper needed story arrays) and 4 broken X handles. All caught pre-planning, zero rework downstream.
- **Audit cleanup bundle pattern (Phase 11 → Phase 16).** Bundling all pre-existing carry-over items into a single ~30-60-min phase before archive — instead of leaving them as "milestone shipped with tech_debt verdict" — flips the archive verdict from `tech_debt` to `passed` and prevents items from compounding milestone-to-milestone.
- **Operator UAT gates.** Three operator-approved checkpoints during v3.1 (Phase 13 visual QA, Phase 15 voice UAT, Railway env-var flip outside workflow) — each unblocked the next phase without surprise rework.

### What Was Inefficient

- **GSD CLI spinner-loop bug.** `gsd-tools phase complete` / `init` / `milestone complete` hung repeatedly in TUI spinner loops throughout v3.1. Workaround: manual artifact updates each time. Cost: ~15-20 min cumulative across the milestone.
- **Phase 16 parallel-execution race.** Wave-based parallel executor agents share `.git/index` when committing concurrently with `--no-verify`. Plans 16-04 + 16-05 race-bundled into a single commit `5fc45f0` under 16-04's attribution. Zero functional impact (both plans landed atomically), but documented in both `SUMMARY.md` files as a known executor edge case. Fix candidates for future: sequence file-disjoint commits within the same wave, OR avoid `--no-verify` so pre-commit hooks serialize via filelock.
- **Phase 16 plan-checker initial BLOCKER.** First planner produced 1 plan with 5 tasks / 15 files — exceeded scope sanity threshold. Required revision: split into 5 single-task plans mirroring Phase 11 exactly. Lesson: cleanup-bundle phases should always be sized via the Phase 11 precedent (1 plan per cleanup item).
- **Plan-phase context drift after compaction.** The session compacted mid-v3.1 archive; CWD slipped back to home directory after the Bash tool's working state reset, requiring re-anchoring with `cd /Users/matthewnelson/seva-mining &&` prefix.

### Patterns Established

- **Substrate-extend-not-rewrite (D-03a precedent).** When a later phase needs richer data than an earlier phase persisted, *extend the earlier phase's writers* to populate additional keys rather than refactor the consumer. v3.1 Phase 15 extended Phase 10's `_build_juno_*_section` writers to persist story-URL arrays without touching the Phase 10 synthesis path or Seva substrate.
- **`useCompanyBrand()` hook + registry config pattern.** Per-tenant frontend variation (Phase 13) uses a React hook returning typed config from a registry (`companyBrandConfig.ts`). Pattern is now the canonical extension for any future per-tenant frontend customisation — strictly no `if (company === 'juno') {...}` branches anywhere in source.
- **CSS-var bridging via `:root.dark[data-company='X']` selector pattern.** Tailwind v4 `@theme inline` + per-tenant `:root.dark[data-company='X']` overrides win the specificity battle against the global `.dark` rule without `!important`. Documented in Phase 13 D-03.
- **`{TENANT}_CRON_ENABLED` env-gate pattern.** v3.0 Phase 10 established `JUNO_CRON_ENABLED` for the daily summary cron; v3.1 Phase 15 extended with `JUNO_SWEEPER_CRON_ENABLED` for the weekly sweeper. Pattern: every new tenant-specific cron job ships disabled by default, operator-enabled via Railway env after smoke fire passes.
- **Verbatim anti-tactical clause + string-equality CI grep gate.** Phase 10 D-01 established the Janes/CSIS-voice anti-tactical clause; Phase 15 enforced *string-equality* on the clause via CI grep, not just presence. Any future Juno LLM call site that touches the clause must keep it verbatim or break CI.

### Key Lessons

1. **Always extend substrate writers when a downstream consumer needs richer data — don't rewrite the consumer to work around thin substrate.** D-03a in Phase 15 saved hours of refactoring the sweeper to recompute story URLs from `agent_runs` notes; instead, three writer extensions in Phase 10's daily_summary path populated the needed arrays. Zero impact to existing readers.
2. **Researcher agents pay back when they catch contract violations pre-planning.** Phase 13 (CSS specificity), Phase 15 (substrate + X handles): all bugs caught before planning started. The cost is ~5-10 min of researcher overhead per phase; the saving is 30-60 min per caught bug × downstream rework cascade.
3. **Audit-cleanup-bundle phases keep milestones honest.** A milestone shipping with `tech_debt` verdict feels like a hangover; flipping it to `passed` via a small cleanup bundle (Phase 11 → Phase 16) eliminates the compounding-debt-across-milestones smell and prevents future planners from absorbing pre-existing items into unrelated phase scopes.
4. **Parallel executor `--no-verify` commits race on `.git/index`.** Either serialize commits within a wave or drop `--no-verify` so pre-commit hooks filelock-serialize. Zero functional impact in v3.1 Phase 16, but the next race could bundle commits under the wrong attribution in a more consequential way.
5. **Hardcoded literals at instantiation sites preserve grep-ability for audit and cost-attribution.** v3.1 Phase 12 D-07: `get_anthropic_client('juno', ...)` at the call site, not `get_anthropic_client(company_id, ...)`. Costs a tiny bit of DRY, buys a `grep "get_anthropic_client('juno'" -rn` audit query that's invaluable for cost-attribution clarity and per-tenant call-site enumeration.

### Cost Observations

- Model mix: predominantly Sonnet (planning + execution); Haiku for relevance classification (Phase 10 carryover) and refusal detection
- Sessions: ~10-15 sessions across v3.1 planning + execution (estimated — not formally tracked)
- Notable: research-agent overhead (~5-10 min per phase) demonstrably pays back via caught contract bugs (Phase 13 CSS, Phase 15 D-03 substrate + X handles) — net positive on every phase that used it

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Phases | Plans | Key Change |
|-----------|--------|-------|------------|
| v2.0 | 4 | 9 | Established GSD workflow + 3-section daily-summary architecture |
| v2.1 | 4 | 20 | Three-tab dashboard + paper-planner Calendar + X-API sweeper pivot from Reddit |
| v3.0 | 2 | 10 | Single atomic multi-tenant deploy (row-level `company_id` + scoped helpers + CI grep gate); Juno News Funnel config-only build on the shared infra |
| v3.0.1 | 1 | 5 | First audit-cleanup-bundle pattern (Phase 11); production cron flip |
| v3.1 | 5 | 19 | Juno feature parity + branding; substrate-extend pattern; second audit-cleanup bundle (Phase 16) flipped `tech_debt` → `passed` |

### Cumulative Quality

| Milestone | Scheduler tests | Backend tests | Frontend tests | Notable |
|-----------|-----------------|---------------|----------------|---------|
| v3.0 close | 321 | 184 | 168 | Multi-tenant baseline established |
| v3.0.1 close | 331 (+10) | 184 | 168 | +3 Haiku validation observability tests |
| v3.1 close | 363 (+32) | 191 (+7) | 181 (+13) | All GREEN; 2 CI grep gates exit 0 (tenant-isolation + anti-tactical-clause) |
