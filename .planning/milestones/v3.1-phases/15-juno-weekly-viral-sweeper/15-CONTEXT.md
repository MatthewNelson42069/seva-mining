# Phase 15: Juno Weekly Viral Sweeper (Tab 3) - Context

**Gathered:** 2026-05-20
**Status:** Ready for planning (UI-SPEC recommended for Tab 3 render decisions; gsd-phase-researcher may validate X handle existence)

<domain>
## Phase Boundary

Deliver the Juno Weekly Viral Sweeper — Tab 3 of the Juno dashboard. Every Sunday 08:00 PT America/Los_Angeles, an APScheduler cron at lock `juno_weekly_sweeper=1021` (env-gated via `JUNO_SWEEPER_CRON_ENABLED`) fires `run_juno_weekly_sweeper()` which: (1) pulls top defence-sector X posts via tweepy `search_recent_tweets` (single combined query string covering defence-press handles + think-tank handles + defence hashtags); (2) computes story virality over the past 7 days of Juno's `daily_summaries.raw_sources_jsonb` using the union of Defence News + Canadian Procurement + World Events sub-arrays as the substrate; (3) calls Sonnet 4.6 (via Phase 12 per-tenant key resolver — bills to `JUNO_ANTHROPIC_API_KEY`) with a NEW dedicated `JUNO_SWEEPER_SYSTEM_PROMPT` in Janes/CSIS voice + anti-tactical clause, requesting exactly 3 content angles; (4) handles refusals via Phase 10's `juno_refusal_detector` (retry-once-with-framing-nudge, then `status='partial'`); (5) persists a `weekly_sweeps` row with `company_id='juno'` + status ∈ (completed, partial, failed) using Phase 9's idempotency-filter pattern (skip if recent run exists with `status IN ('running', 'completed', 'partial')`); (6) Tab 3 at `/juno/sweeper` renders the latest sweep card via the same shape Seva uses, with cross-tenant isolation (TanStack Query keyed on company); week-picker history works for both tenants.

After this phase + operator voice UAT + Railway env flip: Juno's first real weekly viral sweep fires next Sunday 08:00 PT.

**In scope:**
- **🆕 Extend Phase 10 Juno substrate writer (POST-RESEARCH D-03a)** — modify `scheduler/agents/daily_summary.py::_build_juno_defence_news_section` (+ `_build_juno_canadian_procurement_section` + `_build_juno_world_events_section` or whatever the actual function names are) to persist story-URL arrays alongside markdown into `raw_sources_jsonb` keys `defence_news` / `canadian_procurement` / `world_events`. Juno-only — Seva's `_build_seva_*_section` UNTOUCHED. Land in Wave 0 / first plan so virality substrate exists before Sweeper module consumes it.
- New `scheduler/agents/juno_weekly_sweeper.py` module — `run_juno_weekly_sweeper()` orchestrator (~500-700 LOC; parallels Phase 10's `daily_summary.py::run_juno_daily_summary` shape)
- New `JUNO_SWEEPER_SYSTEM_PROMPT` constant in `scheduler/companies/juno/prompts.py` alongside existing daily-summary prompt
- New `JUNO_SWEEPER_X_QUERY` constant (the single combined query string) — likely in `scheduler/companies/juno/x_queries.py` (new file) or appended to existing juno/serpapi.py-style module
- `scheduler/worker.py` MODIFIED — register `juno_weekly_sweeper` cron at lock 1021 with `CronTrigger(day_of_week='sun', hour=8, minute=0, timezone='America/Los_Angeles')` env-gated by `JUNO_SWEEPER_CRON_ENABLED` (mirrors Phase 10's `JUNO_CRON_ENABLED` pattern verbatim)
- `scheduler/config.py` MODIFIED — add `juno_sweeper_cron_enabled: bool = False` Settings field; worker `_validate_env` extended to log its status at boot
- `frontend/src/pages/WeeklyViralSweeperPage.tsx` MODIFIED — delete Phase 9 D-09 short-circuit at lines 48-56 (same pattern as Phase 14 calendar gate); `<WeeklyViralSweeperPage />` already accepts company via useParams → existing scaffolding (per Phase 14 codebase scout precedent) probably handles the rest. Verify during plan-phase.
- New frontend test `frontend/src/pages/__tests__/WeeklyViralSweeperPage.test.tsx` (RTL + TanStack Query key isolation, mirror Phase 14 D-04 pattern)
- New backend test `backend/tests/test_weekly_sweeps_cross_tenant.py` (POST as Seva, attempt GET via /api/juno/weekly-sweeps/{seva_uuid}, assert 404; mirror Phase 14 D-05)
- New scheduler test `scheduler/tests/test_juno_weekly_sweeper.py` (unit tests for X query construction, virality compute over 3 sub-arrays, refusal-detector integration, status mapping)
- Frontmatter / settings for the env-gated cron

**Out of scope:**
- **Defence-prime cashtags ($LMT, $RTX, $LDOS, $BAESY, etc.)** — explicit anti-feature per PROJECT.md (equity/financial signals on defence primes)
- **Operational/tactical content** — hard prohibition per v3.0 Phase 10 D-01 anti-tactical clause; system prompt enforces; refusal-detector backstops
- **Per-section virality (3 sub-cards instead of 1)** — D-03 picked single-substrate union; per-section would require Tab 3 UI redesign (out of scope)
- **Multiple parallel X queries** — D-01 picked single combined query (quota-friendly)
- **Seva sweeper changes** — D-10 zero-regression: D-09 byte-identical contract preserved; Seva sweeper (`weekly_sweeper.py`) untouched
- **Marketplace / LinkedIn / IG ingestion** — X API only
- **Mobile-responsive UI** — desktop-only constraint preserved

</domain>

<decisions>
## Implementation Decisions

### X Query Strategy (JSWEEP-02)

- **D-01 Single combined X query per Sunday cron.** Mirrors Seva sweeper pattern — one `tweepy.AsyncClient.search_recent_tweets` call with a combined query string. Top-10 engagement-ranked posts returned. Quota-friendly (1 query/week = ~4 queries/month, deep margin within X API Basic tier's ~10K-tweets/month and Seva's existing usage).
- **D-02 Starter handle/tag set (POST-RESEARCH REVISION 2026-05-20):**
  - **Think-tanks (3):** `@RUSI_org`, `@CSIS`, `@IISS_org`
  - **Defence press (4) — corrected handles:** `@defense_news` (was `@DefenseNews`), `@BreakingDefense`, `@DefenseScoop`, `@JanesINTEL` (was `@JanesIntel`, official form)
  - **Canadian original (2) — corrected handles:** `@CDAInstitute` (was `@CDA_CDAI`), `@CanadianForces` (was `@canadaforces`)
  - **Canadian Tier-2 ADDED (2) per research:** `@DavePerryCGAI` (CGAI President — highest single-analyst signal), `@Murray_Brewster` (CBC senior defence reporter)
  - **Hashtags (2):** `#defence`, `#NATO`
  - **EXCLUDED (anti-feature):** Defence-prime cashtags (`$LMT`, `$RTX`, `$LDOS`, `$BAESY`, `$GD`, etc.) — equity/financial signals on defence primes are explicit anti-feature per PROJECT.md.
  - **Final constructed query** (verified ~250 chars; well within X API Basic-tier 512-char limit per 15-RESEARCH.md correction):
    ```
    (from:RUSI_org OR from:CSIS OR from:IISS_org OR from:defense_news OR
     from:BreakingDefense OR from:DefenseScoop OR from:JanesINTEL OR
     from:CDAInstitute OR from:CanadianForces OR from:DavePerryCGAI OR
     from:Murray_Brewster OR #defence OR #NATO) -is:retweet lang:en
    ```
  - **Total: 11 handles + 2 hashtags = 13 query terms.**
  - **Query-length limit FIX:** X API Basic-tier query length limit is **512 chars**, NOT 1024 (CONTEXT.md original cited the Academic Research tier limit by mistake — see 15-RESEARCH.md §3).
  - **Tunability path:** Additional Tier-2 candidates `@CadsiCanada` (industry association) + `@NationalDefence` (DND official) are RESERVED — add if v1.0 signal proves thin. Mid-execution tunable.
- **Storage:** Constant `JUNO_SWEEPER_X_QUERY` in a new file `scheduler/companies/juno/x_queries.py` (parallel to existing `scheduler/companies/juno/feeds.py`, `prompts.py`, `serpapi.py` modules). Planner decides exact file name.

### Virality Compute Substrate (JSWEEP-02 continued)

- **D-03 Combine all 3 Juno sub-arrays into one URL set.** Sweeper reads `(row.raw_sources_jsonb or {}).get('defence_news', []) + .get('canadian_procurement', []) + .get('world_events', [])`, concatenates, dedupes by URL (canonical form per Seva pattern), treats as the week's news substrate. Equal weight per story regardless of source section.
- **🔴 CRITICAL post-research correction (D-03a):** Research verified by reading `daily_summary.py:1336-1358` that Phase 10's Juno `raw_sources_jsonb` currently stores **diagnostic counts only**, NOT story-URL arrays. The keys `defence_news` / `canadian_procurement` / `world_events` do NOT yet exist on Juno rows. Phase 15 ADDS A NEW TASK to extend Phase 10's `_build_juno_*_section` writer functions to persist story-URL arrays alongside the markdown they already write. This is a Juno-only Phase 10 source change — Seva's `_build_seva_*_section` is UNTOUCHED (D-10 byte-identical contract held). Resolution path locked 2026-05-20 per operator decision.
- **D-03b Backfill behavior:** Existing Juno rows (from yesterday's first production fire onward) have empty arrays. After the Phase 15 source extension lands + scheduler redeploys, NEW Juno rows have populated arrays. First Sweeper run sees a thin substrate until ~7 days of new Juno rows accumulate. Acceptable — `status='partial'` with diagnostic note "substrate accumulating from new schema" for the first 0-2 sweeps post-deploy.
- **Phase 9 NULL-guard preserved (P3):** `(row.raw_sources_jsonb or {})` defensive read — failed rows may have NULL `raw_sources_jsonb`.
- **Status mapping inherits Seva pattern verbatim:** `completed` / `partial` / `failed` per Seva sweeper's existing logic. `'partial'` triggers when (a) refusal detected on 2nd attempt, (b) X API returns 0 posts but synthesis succeeds, (c) virality compute returns 0 cross-references but synthesis succeeds, (d) substrate is empty due to D-03b backfill window.

### Sonnet Synthesis (JSWEEP-04)

- **D-04 New dedicated `JUNO_SWEEPER_SYSTEM_PROMPT` constant** in `scheduler/companies/juno/prompts.py` alongside the existing `DEFENCE_NEWS_SYSTEM_PROMPT` (or equivalent Phase 10 daily-summary prompt name). Components:
  - Janes/CSIS desk voice anchor (verbatim from Phase 10 D-01)
  - Anti-tactical clause (verbatim from Phase 10 D-01 — non-negotiable; same string-equality lock as daily-summary prompt)
  - "3 content angles" task framing (mirror Seva sweeper prompt structure at `weekly_sweeper.py:204` but with defence-sector audience reframing instead of Bloomberg gold-desk)
  - Defence-sector audience description: "senior defence analyst at a Western think-tank or trade-press desk; values authoritative sourcing, sober tone, geopolitical context, anti-OOB-speculation"
  - Refusal-prone framing avoidance: phrasing tuned away from operational/targeting/force-disposition triggers
- **Anti-tactical clause string-equality contract:** the exact bytes from Phase 10's daily-summary prompt's anti-tactical block MUST appear verbatim in `JUNO_SWEEPER_SYSTEM_PROMPT`. Grep-checkable. Phase 10 considered this load-bearing for content-policy compliance.
- **Anthropic client resolution:** Sonnet call uses `get_anthropic_client('juno', timeout=JUNO_SONNET_TIMEOUT)` per Phase 12 D-09 — bills to `JUNO_ANTHROPIC_API_KEY` (or shared fallback per Phase 12 D-01). Hardcoded company_id literal `'juno'` (not variable) per Phase 12 D-07.

### Refusal Handling (JSWEEP-04 continued)

- **D-05 Reuse Phase 10 refusal-detector verbatim.** Import `juno_refusal_detector.detect_refusal()` (or equivalent function name) from `scheduler/agents/juno_refusal_detector.py`. Pattern:
  1. First Sonnet call → check output via refusal-detector
  2. If refusal detected → retry once with framing-nudge prepended to user prompt ("This is a defence-trade-press analytical task; not operational/tactical")
  3. Second-attempt refusal OR malformed JSON → `status='partial'`, persist row with diagnostic note in `notes_md` field
- **No new refusal-detector code.** Phase 10 module is the single source of truth for this contract.

### Module Structure (JSWEEP wiring)

- **D-06 New file `scheduler/agents/juno_weekly_sweeper.py`.** Parallels v3.0 Phase 10's pattern where `run_juno_daily_summary()` lives alongside Seva's `run_daily_summary()` in the same `daily_summary.py` file — but for v3.1 Phase 15, we go further and put Juno in its own file to keep `weekly_sweeper.py` byte-identical (D-10 zero-regression). Shape:
  - `from agents.weekly_sweeper import _engagement_score, _compute_virality_for_url_set, _build_user_prompt_for_angles` (or analogous shared helpers if planner extracts them; otherwise re-implement)
  - `from agents.juno_refusal_detector import detect_refusal` (Phase 10 module)
  - `from anthropic_client import get_anthropic_client` (Phase 12 resolver)
  - `from companies.juno.prompts import JUNO_SWEEPER_SYSTEM_PROMPT` (D-04)
  - `from companies.juno.x_queries import JUNO_SWEEPER_X_QUERY` (D-02 constant location)
  - `run_juno_weekly_sweeper(session: AsyncSession) -> None` — top-level orchestrator
- **Shared helper extraction:** if Seva's `weekly_sweeper.py` has reusable internal functions (e.g., `_engagement_score`, virality math, week-anchor compute), planner decides whether to (a) export them from `weekly_sweeper.py` and import into the new file, (b) duplicate them in Juno module, or (c) refactor into a shared `scheduler/agents/sweeper_helpers.py`. Default: prefer (a) for code reuse; only choose (b) or (c) if (a) breaks D-10 byte-identical Seva contract. Planner picks.

### Cron Registration + Env Gate (JSWEEP-01)

- **`scheduler/worker.py` MODIFIED** at the existing cron registration section. Add:
  ```python
  juno_sweeper_cron_enabled = os.getenv('JUNO_SWEEPER_CRON_ENABLED', 'false').lower() == 'true'
  if juno_sweeper_cron_enabled:
      logger.info('juno_weekly_sweeper cron ENABLED via JUNO_SWEEPER_CRON_ENABLED=true env var')
      scheduler.add_job(
          _make_juno_weekly_sweeper_job(engine),
          trigger=CronTrigger(
              day_of_week='sun', hour=8, minute=0,
              timezone='America/Los_Angeles',
          ),
          id='juno_weekly_sweeper',
          name='Weekly Viral Sweeper — Juno — Sun 08:00 America/Los_Angeles',
          max_instances=1,
          misfire_grace_time=1800,
      )
  else:
      logger.info('juno_weekly_sweeper cron DISABLED — set JUNO_SWEEPER_CRON_ENABLED=true after voice UAT')
  ```
- Boot-time env logging in `_validate_env` extended to print `JUNO_SWEEPER_CRON_ENABLED: <bool>` alongside the existing `JUNO_CRON_ENABLED` line.
- **Lock ID:** `JOB_LOCK_IDS['juno_weekly_sweeper'] = 1021` already in dict; OPS-02 uniqueness assertion continues to pass.
- **Job factory:** new helper `_make_juno_weekly_sweeper_job(engine)` (parallels existing `_make_juno_daily_summary_job` pattern at worker.py:246).

### Operator Rollout (JSWEEP precedent)

- **D-07 Mirror Phase 10 rollout exactly.** Four-step operator workflow:
  1. **Deploy disabled.** `JUNO_SWEEPER_CRON_ENABLED` unset in Railway → cron does not register at boot. Logs "DISABLED — set JUNO_SWEEPER_CRON_ENABLED=true after voice UAT" on every restart so misconfig is visible.
  2. **Manual smoke fire.** Operator runs `python -m scheduler.cli run_juno_weekly_sweeper` (or equivalent — planner adds a CLI hook if absent) against the production DB. One-shot synthesis of 3 angles + `weekly_sweeps` row written.
  3. **Voice UAT.** Operator reads the 3 angles. Criteria (planner may refine):
     - Voice: reads as Janes/CSIS desk (sober, sourced, geopolitical context — NOT tactical/operational)
     - Quality: each angle connects an X signal with a news-week signal (per the sweeper task contract)
     - Quantity: exactly 3 angles, NOT 2 or 4
     - Anti-features: no defence-prime cashtags, no troop-movement / OOB / capability-gap / targeting analysis
     - Refusal handling: if refusal detector fired (visible in agent_runs.notes), the retry-with-framing-nudge correctly produced clean output OR `status='partial'` was persisted
  4. **Flip env gate.** Operator sets `JUNO_SWEEPER_CRON_ENABLED=true` in Railway → scheduler service redeploys → next Sunday 08:00 PT fires for real.
- **Rollback path:** unset env var → next deploy registers no cron → no Sunday fire. No data deletion needed (existing `weekly_sweeps` rows survive).

### Frontend (JSWEEP-05, JSWEEP-06)

- **D-08 Delete the Juno short-circuit at `frontend/src/pages/WeeklyViralSweeperPage.tsx:48-56`** verbatim (mirrors Phase 14 D-01 pattern). After deletion, the existing `<WeeklyViralSweeperPage />` render path serves both tenants. Verify during plan-phase that the existing `useWeeklySweeps` hook + sweep card rendering is already multi-tenant-aware (Phase 9 likely landed this scaffolding, parallel to calendar).
- **D-09 Frontend cross-tenant isolation test.** New file `frontend/src/pages/__tests__/WeeklyViralSweeperPage.test.tsx` mirroring Phase 14's D-04 — RTL render at `/juno/sweeper` then `/seva/sweeper`, assert TanStack Query cache has separate keys (`['weekly-sweeps', 'juno', ...]` vs `['weekly-sweeps', 'seva', ...]`), zero cross-tenant data bleed.
- **Empty-state copy for first deploy (JSWEEP-05):** Match Phase 14 pattern — defer to existing Seva empty-state shape if applicable. If Seva sweeper has a "no sweeps yet" empty state, Juno inherits via same component. If Seva sweeper assumes ≥1 row from cron-fired data, Phase 15 adds a tenant-agnostic empty-state branch.

### Backend (JSWEEP-06 isolation)

- **Backend isolation test.** New file `backend/tests/test_weekly_sweeps_cross_tenant.py` mirroring Phase 14 D-05 pattern — POST a Seva `weekly_sweeps` row (or seed via fixture), then attempt GET `/api/juno/weekly-sweeps/{seva_uuid}` and assert 404. Same for PATCH/DELETE if those endpoints exist. Tests both directions (Juno UUID via /api/seva/ → 404).
- **Status_code == 404, NOT 403** per JCAL-05 precedent — tenant existence isolation, not permission isolation. Grep gate `grep -c "status_code == 403"` returns 0.

### Zero-Regression Contract (D-10)

- **D-10 Zero Seva-side changes.** This phase modifies ZERO Seva files. Files NOT touched:
  - `scheduler/agents/weekly_sweeper.py` (unless planner exports shared helpers — see D-06 module structure)
  - `scheduler/agents/x_ingest.py` (unless planner extends query-parameterization pattern to add the Juno query as an option — preferred path: Juno file imports `fetch_top_x_posts` and passes its own query string verbatim)
  - All v2.1 / v3.0 / v3.1 Seva-facing components, hooks, tests
  - `scheduler/companies/juno/feeds.py`, `serpapi.py` (daily-summary substrates — sweeper is independent)
- After Phase 15 lands, full Seva regression suite passes byte-identically (frontend ≥178, backend ≥188, scheduler ≥323).

### Folded Todos
None — no pending todos matched Phase 15 scope at cross-reference time.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents (researcher, planner, executor) MUST read these before planning or implementing.**

### Phase 15 Roadmap Source
- `.planning/ROADMAP.md` §"Phase 15: Juno Weekly Viral Sweeper (Tab 3)" (lines ~291-380 — full phase block with goal, depends-on, inputs, outputs, success criteria, complexity, hard parts P1..P9 including P8 "Sweeper Sonnet bills to wrong Anthropic key")
- `.planning/REQUIREMENTS.md` §"Juno Weekly Viral Sweeper (JSWEEP)" — atomic acceptance criteria for JSWEEP-01..06

### Project-Level Constraints
- `.planning/PROJECT.md` §"Current Milestone: v3.1" §"Hard parts the roadmap addresses" items 2 + 5 ("Sweeper defence-sector X queries — what to actually search" + "Sweeper cron correctness in multi-tenant world")
- `.planning/PROJECT.md` §"Out of Scope" — defence-prime equity/financial signals (anti-feature reminder for D-02 query construction)
- `CLAUDE.md` §"What NOT to Use" — autoposting prohibition (sweeper output is operator-reviewed only, NOT auto-posted)

### v2.1 / v3.0 Patterns This Phase Builds On
- `.planning/milestones/v3.0-phases/10-juno-defence-news-funnel/10-CONTEXT.md` D-01 — Janes/CSIS voice anchor + verbatim anti-tactical clause (reused in D-04 sweeper prompt)
- `.planning/milestones/v3.0-phases/10-juno-defence-news-funnel/10-CONTEXT.md` (refusal-detector pattern from `juno_refusal_detector.py` — reused in D-05)
- `.planning/milestones/v3.0-phases/09-multi-tenant-foundation/09-CONTEXT.md` D-08 — single-component + per-tenant config registry idiom (sweeper UI inherits this)
- `.planning/phases/12-per-tenant-anthropic-api-key/12-CONTEXT.md` D-07 — hardcoded `'juno'` literal at instantiation site for `get_anthropic_client('juno', ...)` (mandatory pattern)
- `.planning/phases/14-juno-content-calendar/14-CONTEXT.md` D-01 + D-04 + D-05 — Phase 14 short-circuit removal + frontend test + backend test patterns (mirror exactly for Phase 15)
- Existing v2.1 Phase 7 Seva sweeper implementation in `scheduler/agents/weekly_sweeper.py` — reference shape for Juno sweeper orchestrator
- Existing v3.0 Phase 10 daily-summary pattern in `scheduler/agents/daily_summary.py::run_juno_daily_summary` — reference for tenant-scoped agent shape

### Code-Level References (current state for the planner)
- `scheduler/worker.py:108` — `JOB_LOCK_IDS['juno_weekly_sweeper'] = 1021` already reserved
- `scheduler/worker.py:246` — `_make_juno_daily_summary_job` factory pattern to mirror for `_make_juno_weekly_sweeper_job`
- `scheduler/worker.py:458` — Juno daily summary env-gate registration pattern to mirror for sweeper
- `scheduler/agents/weekly_sweeper.py:204` — Seva sweeper Sonnet system prompt (Bloomberg commodities-desk voice; reference for "3 content angles" task framing only — Juno gets different voice)
- `scheduler/agents/weekly_sweeper.py:153` — Seva virality compute call shape: `stories = raw.get('gold_news', []) or []` (Juno will replace with the 3-sub-array union)
- `scheduler/agents/x_ingest.py:78` — `fetch_top_x_posts(query, max_results=100)` already query-parametrized; Juno just imports and passes the Juno query
- `scheduler/agents/juno_relevance.py` — Haiku classifier (NOT used by sweeper; documentation only)
- `scheduler/agents/juno_refusal_detector.py` — Phase 10 refusal-detector module to reuse verbatim
- `scheduler/companies/juno/prompts.py` — append new `JUNO_SWEEPER_SYSTEM_PROMPT` constant alongside existing daily-summary prompt
- `scheduler/anthropic_client.py` — Phase 12 resolver; sweeper calls `get_anthropic_client('juno', timeout=...)`
- `frontend/src/pages/WeeklyViralSweeperPage.tsx:48-56` — Phase 9 D-09 Juno short-circuit to delete
- `frontend/src/hooks/useWeeklySweeps.ts` (or equivalent) — existing TanStack Query hook (verify multi-tenant-aware during plan-phase)
- `backend/app/routers/weekly_sweeps.py` (or equivalent) — backend router (verify `Depends(get_current_company)` already wired by Phase 9)

### New Files Phase 15 Creates
- `scheduler/agents/juno_weekly_sweeper.py` (NEW — orchestrator)
- `scheduler/companies/juno/x_queries.py` (NEW — constants; planner may relocate)
- `scheduler/tests/test_juno_weekly_sweeper.py` (NEW — unit tests)
- `frontend/src/pages/__tests__/WeeklyViralSweeperPage.test.tsx` (NEW — D-09 cross-tenant isolation)
- `backend/tests/test_weekly_sweeps_cross_tenant.py` (NEW — backend 404 contract)

### Files Phase 15 Modifies
- `scheduler/worker.py` — cron registration + env-gate + boot logging
- `scheduler/config.py` — add `juno_sweeper_cron_enabled: bool = False` Settings field
- `scheduler/companies/juno/prompts.py` — append `JUNO_SWEEPER_SYSTEM_PROMPT` constant
- `frontend/src/pages/WeeklyViralSweeperPage.tsx` — delete Juno short-circuit at 48-56

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets (heavy reuse)
- **`scheduler/agents/x_ingest.py::fetch_top_x_posts(query, max_results)`** — already query-parameterized. Juno passes its own query string verbatim; no x_ingest changes needed.
- **`scheduler/agents/weekly_sweeper.py`** — Seva sweeper orchestrator. Phase 15's Juno module mirrors this shape (cron handler → ingest → virality → Sonnet → persist).
- **`scheduler/agents/juno_refusal_detector.py`** — Phase 10 module. Reused verbatim.
- **`scheduler/anthropic_client.py::get_anthropic_client('juno', timeout)`** — Phase 12 resolver. Single call site; hardcoded literal.
- **`scheduler/companies/juno/prompts.py`** — extend with NEW constant; do NOT modify existing daily-summary prompt.
- **`weekly_sweeps` table** — already multi-tenant via Alembic 0014. `scoped_weekly_sweeps_*()` helpers exist in backend + scheduler.
- **TanStack Query keys** — `queryKeys.weekly_sweeps(companyId, ...)` factory likely already exists from Phase 9.

### Established Patterns
- **Env-gated cron registration** — Phase 10 `JUNO_CRON_ENABLED` precedent (worker.py:458). Phase 15 mirrors exactly with `JUNO_SWEEPER_CRON_ENABLED`.
- **Operator voice UAT before flip** — Phase 10 precedent: 5-7 criteria UAT, operator signs off, then env var flipped in Railway. Mirror for Phase 15.
- **Tenant-isolation tests** — Phase 14 D-04 + D-05 patterns. Mirror for Phase 15 sweeper.
- **Refusal-detector retry-with-framing-nudge** — Phase 10 pattern; reused.
- **Idempotency filter includes `'partial'`** — Phase 9 critical bugfix; every Juno cron must include this in re-fire skip filter to avoid duplicate rows.
- **Per-tenant Anthropic key** — Phase 12 D-07: hardcoded literal `'juno'` at the resolver call site, NOT a variable. Inline comment cites the hardcoded choice per Phase 12 Hard Part P8.

### Integration Points
- **Sweeper depends on real daily_summaries rows** — for virality compute substrate. Juno daily summary has been live since Phase 10; first real production rows arrive 2026-05-21 08:05 PT (post Phase 12 Railway env flip). Phase 15's sweeper cron deployment can land before any real data exists — first Sunday fire would just have empty virality compute → `status='partial'` with diagnostic note. Acceptable.
- **Tab 3 React rendering** — likely already handles loading + empty states for Seva (verify during plan-phase). Juno inherits via the same component once short-circuit is deleted.

</code_context>

<specifics>
## Specific Ideas

- **X query constants location:** prefer `scheduler/companies/juno/x_queries.py` (new file, parallel to existing `feeds.py` / `serpapi.py`). Planner may pick `scheduler/companies/juno/__init__.py` re-export or alternative naming.
- **CLI hook for manual smoke fire:** if `scheduler/cli.py` doesn't already exist or doesn't include a `run_juno_weekly_sweeper` entry, planner adds a thin CLI shim (`python -m scheduler.cli run_juno_weekly_sweeper`). Mirror Phase 10 precedent (`python -m scheduler.cli run_juno_daily_summary` exists or analogous).
- **Voice UAT criteria** (operator may refine before Phase 15 fires):
  1. Each angle reads as Janes/CSIS desk (sober, sourced-with-receipts, geopolitical context — NOT tactical/operational)
  2. Exactly 3 angles (not 2, not 4 — Sonnet sometimes drifts)
  3. Each angle connects an X signal with a news-week signal (the sweeper's task contract)
  4. No defence-prime cashtags, no troop-movement / OOB / capability-gap / targeting analysis
  5. If refusal-detector fired, retry-with-framing-nudge produced clean output OR row persisted with `status='partial'` + diagnostic note
  6. Tone differentiates clearly from Seva's Bloomberg-gold-desk voice (eye check)
- **Anti-tactical clause string-equality:** the bytes from Phase 10's daily-summary prompt's anti-tactical block (likely a multi-line string starting "EXPLICITLY FORBIDDEN: operational/tactical content..." or similar) must appear verbatim in `JUNO_SWEEPER_SYSTEM_PROMPT`. Grep-checkable.
- **Quota math** (X API Basic tier ~$100/mo, ~10K tweets/month cap):
  - Seva existing usage: ~4 calls/month (weekly cron × 4 weeks), each ≤100 tweets = ~400 tweets/month
  - Juno Phase 15 add: ~4 calls/month, each ≤100 tweets = ~400 tweets/month
  - Combined: ~800 tweets/month, ~8% of cap. Deep headroom.

</specifics>

<deferred>
## Deferred Ideas

- **Per-section sweeper sub-cards** — instead of 1 combined card, Tab 3 could show separate Defence News / Procurement / World Events sub-cards each with their own 3 angles. Out of scope per D-03 (single-substrate union). Could be a future enhancement if operator finds 1-card insufficient.
- **Multi-query parallel sweep** — fire N=3-5 separate X queries (reporters, think-tanks, hashtags as separate calls), merge client-side. Out of scope per D-01 (single combined query). Could move to multi-query if 1-query first-fire signal is thin.
- **Tier-2 defence X reporters** — beyond the D-02 starter set, additional reporters could be added (e.g., defence-business journalists, military-specific freelancers). Mid-execution tunable per the D-02 "tunability path" note. Not a phase blocker.
- **Defence-prime cashtags** — explicit ANTI-FEATURE per PROJECT.md (equity/financial signals on defence primes). Permanent exclusion. Documented here so future maintainers can verify intent.
- **LinkedIn / IG ingestion** — X API only per CLAUDE.md autoposting prohibition + budget constraints. Out of scope.
- **Auto-posting of sweeper angles** — hard prohibition per CLAUDE.md. Operator manually reviews + posts.
- **Sweeper system-prompt iteration** — if first 2-4 weeks of production sweeps surface voice/tone misses or refusal-rate issues, iterate `JUNO_SWEEPER_SYSTEM_PROMPT` in v3.2. Tracked in ROADMAP "Out of Scope" line "Sweeper system-prompt iteration".
- **Reviewed Todos (not folded)** — None reviewed; cross-reference returned 0 matches.

</deferred>

---

*Phase: 15-juno-weekly-viral-sweeper*
*Context gathered: 2026-05-20*
