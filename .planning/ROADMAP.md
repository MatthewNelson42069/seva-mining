# Roadmap: Seva Mining

## Milestones

- ✅ **v1.0.1 — Approval Dashboard (deprecated by v2.0 pivot)** — Phases 1-11, shipped 2026-04-25 → archive: [`milestones/v1.0.1/ROADMAP.md`](milestones/v1.0.1/ROADMAP.md)
- ✅ **v2.0 — Daily Summary Feed** — Phases 1-4 (reset numbering), shipped 2026-05-06 → archive: [`milestones/v2.0-ROADMAP.md`](milestones/v2.0-ROADMAP.md)
- ✅ **v2.1 — Three-Tab Content Engine + UI Polish** — Phases 5-8 (project-wide counter continues), shipped 2026-05-19 → archive in [`milestones/v3.0-ROADMAP.md`](milestones/v3.0-ROADMAP.md) (snapshot at v3.0 close includes v2.1 phase details — v2.1 was never archived separately before v3.0 started)
- ✅ **v3.0 — Multi-Tenant Dashboards (Juno Industries Onboarding)** — Phases 9-10, shipped 2026-05-19 → archive: [`milestones/v3.0-ROADMAP.md`](milestones/v3.0-ROADMAP.md) (audit: [`milestones/v3.0-MILESTONE-AUDIT.md`](milestones/v3.0-MILESTONE-AUDIT.md))
- ✅ **v3.0.1 — v3.0 Audit Cleanup Bundle** — Phase 11, shipped 2026-05-20 (verifier 5/5 PASS)
- 🚧 **v3.1 — Juno Feature Parity + Branding** — Phases 12-15, planning 2026-05-20

## Phases

<details>
<summary>✅ v2.0 Daily Summary Feed (Phases 1-4) — SHIPPED 2026-05-06</summary>

- [x] Phase 1: Gold News Card + Web Feed (6/6 plans) — completed 2026-05-06
- [x] Phase 2: Ontario Law Ingestion (1/1 plan) — completed 2026-05-06
- [x] Phase 3: Ontario Stats Ingestion (1/1 plan) — completed 2026-05-06
- [x] Phase 4: Prune Cron + Operations Hardening (1/1 plan, 4 tasks) — completed 2026-05-06

Phase artifacts archived to `milestones/v2.0-phases/`. Full roadmap detail: `milestones/v2.0-ROADMAP.md`.

</details>

<details>
<summary>✅ v1.0.1 Approval Dashboard (Phases 1-11) — DEPRECATED by v2.0 pivot</summary>

11 phases shipped between 2026-03-30 and 2026-04-25 covering FastAPI backend, React approval dashboard, Twitter Agent (later deprecated), Senior Agent (later deprecated), Instagram Agent (later deprecated), Content Agent + 6 sub-agents, dashboard views + WhatsApp digest, agent execution polish, and content preview / rendered images. Source files retained as dead code per v2.0 retirement intent. Full archive: `milestones/v1.0.1/ROADMAP.md`.

</details>

<details>
<summary>✅ v2.1 Three-Tab Content Engine + UI Polish (Phases 5-8) — SHIPPED 2026-05-19</summary>

- [x] Phase 5: Foundation — Tabs + DB + Backend Stubs (5/5 plans) — completed 2026-05-19
- [x] Phase 6: Content Calendar (5/5 plans) — completed 2026-05-19
- [x] Phase 7: Weekly Viral Sweeper (6/6 plans) — completed 2026-05-19 (X-API pivot from Reddit per 07-CONTEXT.md D-03)
- [x] Phase 8: UI Polish + Dead-Code Strip (4/4 plans) — completed 2026-05-19

Full roadmap detail snapshot in `milestones/v3.0-ROADMAP.md` (v2.1 phases were never archived separately — captured in the v3.0 close snapshot).

</details>

<details>
<summary>✅ v3.0 Multi-Tenant Dashboards — Juno Industries Onboarding (Phases 9-10) — SHIPPED 2026-05-19</summary>

- [x] Phase 9: Multi-Tenant Foundation (5/5 plans, verifier 10/10 PASS) — completed 2026-05-19
- [x] Phase 10: Juno Defence News Funnel (5/5 plans, verifier 10/10 PASS, voice UAT + visual QA APPROVED) — completed 2026-05-19

Full roadmap detail: `milestones/v3.0-ROADMAP.md`. Audit verdict `tech_debt` (20/20 reqs satisfied; 8 non-blocking follow-ups for v3.0.1/v3.1+).

</details>

<details>
<summary>✅ v3.0.1 v3.0 Audit Cleanup Bundle (Phase 11) — SHIPPED 2026-05-20</summary>

- [x] Phase 11: Audit Cleanup Bundle (5/5 plans, verifier 5/5 PASS; `JUNO_CRON_ENABLED=true` flipped in Railway 2026-05-20) — completed 2026-05-20

Full roadmap detail snapshot in this file under "v3.0.1" section (the v3.0.1 roadmap was inlined rather than archived to a separate file since it was a single-phase milestone). Milestone audit recap in `MILESTONES.md`.

</details>

---

### v3.1 — Juno Feature Parity + Branding

**Milestone goal:** Bring Juno to feature parity with Seva (Tab 2 Content Calendar + Tab 3 Weekly Viral Sweeper), give Juno its own visual identity (logo + wordmark + color palette — defence-industry appropriate, not borrowed amber from Seva), and split the shared Anthropic API key per tenant so cost attribution is clean. After v3.1 ships, `/juno/*` is a complete defence-industry equivalent of `/seva/*` — three live tabs with their own branding, not a one-tab news brief borrowing Seva's chrome.

**Phase numbering:** Project-wide counter continues. v3.0.1 closed at Phase 11; v3.1 runs Phases 12-15. No reset.

**Ordering rationale:** Phase 12 (per-tenant Anthropic key) lands first — smallest scope, pure plumbing, unblocks cost-attribution for every downstream Juno LLM call (calendar drafting if any, sweeper Sonnet synthesis). Phase 13 (branding) lands second — visual identity arrives before the operator sees the new Juno tabs, so v3.1's mid-milestone state is "Juno feels like Juno even though Tabs 2/3 are still placeholder," not "Juno has new features but still wears Seva's wordmark." Phase 14 (Calendar Tab 2) lands third — port of v2.1 Phase 6 with minimal new logic; Phase 9's `scoped_*()` + `/api/{company}/calendar` scaffolding is already in place. Phase 15 (Sweeper Tab 3) lands last — most complex (defence-sector X queries TBD, Sunday 08:00 PT cron at reserved lock 1021, Sonnet 4.6 synthesis with Janes/CSIS voice + anti-tactical clause from Phase 10 D-01); benefits from Phase 12's per-tenant key already being production-tested before Juno Sonnet costs hit a dedicated Juno API account.

- [ ] **Phase 12: Per-tenant Anthropic API Key** — Resolver + grep gate + Railway env wiring; `get_anthropic_client(company_id)` falls back to shared `ANTHROPIC_API_KEY` when per-tenant unset; all call sites routed through resolver (KEY-01..04)
- [ ] **Phase 13: Per-company Branding** — Juno wordmark + logo + color palette via `companyBrandConfig.ts` registry pattern (extends Phase 9 D-08 `companySectionConfig.ts` precedent); no `if (company === 'juno')` branches; CI grep gate (BRAND-01..05)
- [ ] **Phase 14: Juno Content Calendar (Tab 2)** — Port of v2.1 Phase 6 paper-planner UI to `/juno/calendar`; full CRUD over Juno's `calendar_items` rows via existing `scoped_*()` helpers + `/api/{company}/calendar` router prefix; cross-tenant isolation tests (JCAL-01..05)
- [ ] **Phase 15: Juno Weekly Viral Sweeper (Tab 3)** — Sunday 08:00 PT APScheduler cron at lock 1021; defence-sector X queries via `tweepy.AsyncClient.search_recent_tweets`; virality compute over Juno's `daily_summaries.raw_sources_jsonb`; Sonnet 4.6 synthesis with Janes/CSIS voice + anti-tactical clause + refusal-detector pattern from Phase 10; `JUNO_SWEEPER_CRON_ENABLED` env gate; Tab 3 render (JSWEEP-01..06)

---

## Phase Details

### Phase 12: Per-tenant Anthropic API Key

**Goal:** Every Anthropic call routes through a single resolver (`get_anthropic_client(company_id)`) that selects the right per-tenant key — Seva's Haiku/Sonnet calls bill to Seva's Anthropic dashboard; Juno's calls bill to Juno's. Local-dev workflow preserved via graceful fallback to shared `ANTHROPIC_API_KEY` when per-tenant vars unset. After this phase, every downstream v3.1 LLM call (Sweeper Sonnet synthesis in Phase 15; any future Calendar drafting) automatically attributes correctly with no per-call-site change required.

**Depends on:** v3.0.1 milestone shipped (✓ Phase 11) — production cron operational, Haiku 4.5 classifier observability landed in CLEANUP-05, all current Anthropic call sites enumerated in audit.

**Requirements:** KEY-01, KEY-02, KEY-03, KEY-04

**Inputs:**
- v3.0.1 codebase as shipped — all Anthropic call sites currently use `os.getenv("ANTHROPIC_API_KEY")` directly or via module-level `AsyncAnthropic()` instantiation
- Known call sites (full enumeration deferred to plan-phase via `grep -rn 'Anthropic(api_key=\|AsyncAnthropic(api_key=\|anthropic.AsyncAnthropic\|anthropic.Anthropic' scheduler/ backend/`):
  - `scheduler/agents/daily_summary.py` — Sonnet 4.6 synthesis for both Seva gold news AND Juno defence/procurement/world-events
  - `scheduler/agents/juno_relevance.py` — Haiku 4.5 classifier (`client.messages.parse(output_format=DefenceRelevance)`)
  - `scheduler/agents/juno_refusal_detector.py` — retry-with-framing-nudge call (Phase 10 pattern)
  - `scheduler/agents/weekly_sweeper.py` — Seva Sonnet 4.6 for 3 content angles (existing; gets reattributed to Seva's key)
  - `scheduler/agents/content_agent.py::review()` — Haiku compliance gate (dead-code-adjacent but still imported; included for safety)
  - any backend-side LLM call (less common — confirm via grep)
- Phase 9 D-03 multi-tenancy pattern: `company_id` flows through call signatures (already plumbed for `scoped_*()` helpers + `Depends(get_current_company)` routers)
- Phase 9 CI grep gate precedent: `scripts/verify-tenant-isolation.sh` blocks raw `select(DailySummary|...)` outside `queries/scoped.py` — same pattern reused for Anthropic instantiation
- Operator preference: ship resolver + fall-back BEFORE setting per-tenant Railway env vars (zero-deploy-gap rollout: resolver acts as no-op when keys unset)

**Outputs:**
- `scheduler/anthropic_client.py` CREATED — `get_anthropic_client(company_id: Literal["seva", "juno"]) -> AsyncAnthropic` resolver; reads `SEVA_ANTHROPIC_API_KEY` or `JUNO_ANTHROPIC_API_KEY` env var based on `company_id`; falls back to shared `ANTHROPIC_API_KEY` with single `logger.warning(...)` at startup if per-tenant var unset (warning emitted once per process via module-level flag, not per-call); raises `RuntimeError` only if neither per-tenant NOR shared key is set
- `backend/app/anthropic_client.py` CREATED — sync mirror of scheduler resolver for any backend Anthropic call sites (likely zero or near-zero; included for grep-gate completeness)
- `scheduler/agents/daily_summary.py` MODIFIED — replace direct `AsyncAnthropic(api_key=...)` instantiation with `get_anthropic_client(company_id)`; both `run_daily_summary` (Seva) and `run_juno_daily_summary` (Juno) updated; `company_id` already flows through these paths
- `scheduler/agents/juno_relevance.py` MODIFIED — `classify_story` resolves Haiku client via `get_anthropic_client('juno')` (Juno-specific call site, hardcoded company_id)
- `scheduler/agents/juno_refusal_detector.py` MODIFIED — retry-with-framing-nudge call routes through `get_anthropic_client('juno')`
- `scheduler/agents/weekly_sweeper.py` MODIFIED — existing Seva sweeper Sonnet call resolved via `get_anthropic_client('seva')` (hardcoded company_id; multi-tenant sweeper lands in Phase 15)
- `scripts/verify-anthropic-resolver.sh` CREATED — CI grep gate: `grep -rEn 'AsyncAnthropic\(api_key=|Anthropic\(api_key=' scheduler/ backend/` returns hits ONLY inside `scheduler/anthropic_client.py` + `backend/app/anthropic_client.py`; exit 1 on any other hit
- `scheduler/tests/test_anthropic_client.py` CREATED — unit tests covering: (a) per-tenant key resolution when both env vars set, (b) fallback to shared key when per-tenant unset (with WARN log assertion), (c) `RuntimeError` when neither key set, (d) memoization (same client instance returned for repeated calls with same `company_id` within a process)
- `.env.example` MODIFIED — document `SEVA_ANTHROPIC_API_KEY` + `JUNO_ANTHROPIC_API_KEY` as optional with fallback behavior note
- Operator post-merge action documented: set both env vars in Railway scheduler service (not in backend service unless backend grep surfaces LLM call sites)

**Success Criteria** (what must be TRUE when this phase completes):
1. After deploy + setting both per-tenant Railway env vars, the next 08:05 PT Juno fire's Anthropic dashboard activity appears in the Juno account (JUNO_ANTHROPIC_API_KEY) and zero usage appears in the Seva account; the next 08:00 PT Seva fire's activity appears only in the Seva account
2. With `SEVA_ANTHROPIC_API_KEY` + `JUNO_ANTHROPIC_API_KEY` unset locally but `ANTHROPIC_API_KEY` set, the scheduler boots cleanly, both crons fire, and a single `WARN` log line per process notes the fallback (no per-call warning spam); behavior unchanged from v3.0.1
3. `scripts/verify-anthropic-resolver.sh` exits 0 — every Anthropic client instantiation lives inside the resolver module; zero raw `AsyncAnthropic(api_key=...)` outside `scheduler/anthropic_client.py` + `backend/app/anthropic_client.py`
4. Full regression suites GREEN — scheduler `pytest` stays at 331+ pass (zero regressions from Phase 11 baseline); backend at 184+; frontend untouched at 168
5. Operator can roll back per-tenant key by unsetting both `SEVA_ANTHROPIC_API_KEY` + `JUNO_ANTHROPIC_API_KEY` in Railway env vars — next cron fires fall back to shared `ANTHROPIC_API_KEY` with no redeploy required (mirrors `JUNO_CRON_ENABLED` rollback precedent from Phase 10)

**Plans:** 1/3 plans executed
- [x] 12-01-PLAN.md — Wave 1 — Resolver module (`scheduler/anthropic_client.py`) + Settings fields (`seva_anthropic_api_key`, `juno_anthropic_api_key`, `anthropic_resolver_strict`) + 5+ unit tests (KEY-01, KEY-02, KEY-04)
- [ ] 12-02-PLAN.md — Wave 2 — Refactor 4 production sites (`daily_summary.py` ×2, `weekly_sweeper.py`, `content_agent.py::_do_fetch`) + 1 UAT script (`scripts/uat_voice_calibration.py`) through resolver; surgically excise 3 dead functions from `content_agent.py` (`check_compliance`, `is_gold_relevant_or_systemic_shock`, `review`) + their tests (KEY-01, KEY-03)
- [ ] 12-03-PLAN.md — Wave 3 — CI grep gate (`scripts/verify-anthropic-resolver.sh`) mirroring `verify-tenant-isolation.sh` pattern + extend `scheduler/worker.py::_validate_env` to log per-tenant key + STRICT-mode status at boot (KEY-03, KEY-04)

**Planner deviations from CONTEXT.md (documented in 12-02-PLAN.md objective):**
- `content_agent.py:1108` reclassified from "dead" to LIVE refactor target (inside `_do_fetch` → `fetch_stories()` LIVE export)
- `scheduler/scripts/uat_voice_calibration.py:377` added as 4th refactor target (not in CONTEXT.md's D-09 enumeration; surfaced by broader scheduler-wide grep)
- Net effect: 4 refactored sites + 1 UAT script + 3 dead functions deleted (`check_compliance`, `is_gold_relevant_or_systemic_shock`, `review`); CONTEXT D-09 said "3 refactor + 3 dead delete" — final count is "4 refactor + 1 UAT refactor + 3 dead delete"; grep gate result identical to CONTEXT intent: zero `AsyncAnthropic(` outside resolver

**Complexity:** S (pure plumbing — single new module, ~5 call-site edits, one grep gate, no schema changes, no UI work)
**Estimated duration:** 1-2 hours

**Dependencies:**
- v3.0.1 milestone shipped (✓ done 2026-05-20)
- No external blockers — operator can create separate Anthropic accounts/keys at any time; key setup decoupled from code deploy

**Hard parts (cross-ref PROJECT.md "Hard parts the roadmap addresses"):**

| # | Pitfall | Severity | Prevention |
|---|---------|----------|-----------|
| P1 | Env-var typo silently routes to wrong tenant's key — `SEVA_ANTHROPIC_API_KEY` typo'd as `SVA_ANTHROPIC_API_KEY` would fall back to shared key and bill to whichever tenant's account holds it | HIGH | Resolver logs `INFO` at first resolution per `company_id` showing which key var was used (`SEVA_ANTHROPIC_API_KEY` vs `JUNO_ANTHROPIC_API_KEY` vs `ANTHROPIC_API_KEY (fallback)`); operator verifies log on first deploy; post-deploy smoke fire manually checks Anthropic console attribution |
| P2 | Fallback semantics ambiguous — does "per-tenant key unset" mean "use shared" or "hard-fail in prod"? Decided once + documented | HIGH | Single fallback policy: per-tenant unset → shared key with WARN log; both unset → `RuntimeError`. No env-driven mode flag. Documented in module docstring + `.env.example` + cross-ref in PROJECT.md Key Decisions table |
| P3 | Resolver imported at module-load time when env vars not yet set (test env, CI) breaks collection | MEDIUM | Resolver is a function, not module-level constant; clients instantiated lazily inside the function on first call; tests using `monkeypatch.setenv` work cleanly |
| P4 | Memoization-induced stale key after env var change at runtime (rare; mid-process secret rotation) | LOW | Memoization keyed on `(company_id, key_used)` tuple — if operator rotates a key and bounces the scheduler service (Railway redeploy on env var change), new process starts fresh; in-process rotation not supported (acceptable for our deployment model) |
| P5 | Grep gate false positives — `# AsyncAnthropic(api_key=...)` in a comment/docstring would trip the gate | LOW | Grep pattern restricted to non-commented uses: `grep -rEn '^[^#]*AsyncAnthropic\(api_key=' scheduler/ backend/`; alternatively use `ast` walk if the simple pattern proves noisy |

**Architecture reference:**
- `scheduler/companies/` directory — Phase 9 per-tenant config registry pattern (extends to anthropic resolver)
- `scheduler/queries/scoped.py` + `backend/app/queries/scoped.py` — Phase 9 pattern this resolver mirrors (single module owning a tenant-scoped concern + CI grep gate enforcing single source)
- v3.0 Phase 9 09-CONTEXT.md D-08 (config registry pattern) — same shape applied to Anthropic key resolution

**Feature reference:**
- REQUIREMENTS.md KEY-01..04 — observable acceptance criteria per requirement
- PROJECT.md "Hard parts" #4 (per-tenant Anthropic key without breaking local dev) + "Stack additions" note (no new dependencies expected)

**UI hint**: no

---

### Phase 13: Per-company Branding

**Goal:** Every `/juno/*` route renders Juno's brand chrome — Juno wordmark in `AppHeader`, Juno logo icon, defence-industry-appropriate color palette (subdued / authoritative, not Seva's amber) — and every `/seva/*` route continues to render Seva's existing chrome with zero regression. Brand resolution is config-driven via a `companyBrandConfig.ts` registry that mirrors Phase 9 D-08's `companySectionConfig.ts` pattern; no `if (company === 'juno')` branches anywhere in components. Adding a future tenant requires only a registry entry.

**Depends on:** Phase 12 (per-tenant key resolver) — not a hard dependency, but ordering keeps the milestone's smaller plumbing phases at the front. Independent of Phases 14/15 (Calendar/Sweeper are content; branding is chrome).

**Requirements:** BRAND-01, BRAND-02, BRAND-03, BRAND-04, BRAND-05

**Inputs:**
- v3.0 shipped frontend — `frontend/src/components/layout/AppHeader.tsx` (freeze formally lifted in Phase 9 D-02; current state: "Seva Mining" wordmark hardcoded on both tenants per D-02a deferred decision)
- `frontend/src/index.css` — existing `@theme inline` block with three semantic amber tokens (`--color-brand-accent`, `-hover`, `-subtle`) added in Phase 8 UI-01..04; Tailwind v4 token resolution pattern established
- `frontend/src/components/layout/CompanySwitcher.tsx` — Phase 9's segmented control already consumes semantic `--color-brand-accent*` tokens; consumes registry post-rename
- `frontend/src/companies/companySectionConfig.ts` — Phase 9 D-08 registry pattern (single source of truth keyed on `company_id`, consumed by `SummaryCard.tsx` for section titles); v3.1's `companyBrandConfig.ts` is a sibling registry with same shape but different fields (wordmark, iconPath, colorTokens)
- Operator design preferences (TBD during discuss-phase): exact Juno color palette (candidates: navy/slate base + desaturated steel-blue accent + muted-bronze hover; alternate: graphite + cool-grey + electric-cyan accent for "tech-defence" feel rather than "naval-defence"); exact Juno wordmark wording ("Juno Industries" vs "Juno" vs "JUNO"); logo asset source (operator-provided SVG or AI-generated)
- v3.0 Phase 9 D-08 inline-comment precedent: every "if you'd be tempted to write `if (company === 'juno')` here, you must instead extend the registry" doc-comment idiom

**Outputs:**
- `frontend/public/brand/juno-icon.svg` CREATED — Juno logo asset (defence-industry appropriate; subdued, NOT amber)
- `frontend/public/brand/juno-icon.png` CREATED — favicon fallback (browser/OS-level branding for `/juno/*` browser tabs; out of v3.1 scope if too complex — defer to v3.2 if router-level favicon swap proves brittle)
- `frontend/public/brand/seva-icon.svg` CREATED — Seva logo asset extracted from current hardcoded reference (if currently inline; otherwise NOT MODIFIED — registry entry just points at existing path)
- `frontend/src/companies/companyBrandConfig.ts` CREATED — registry keyed on `company_id` with shape: `{ wordmark: string, iconPath: string, accentToken: string, accentHoverToken: string, accentSubtleToken: string }`; one entry each for `'seva'` and `'juno'`; doc-comment forbids per-tenant component branches with explicit anti-pattern callout (mirrors Phase 9 D-08 comment block)
- `frontend/src/hooks/useCompanyBrand.ts` CREATED — `useCompanyBrand()` consults `useParams<{company}>()` + `companyBrandConfig[company]`; returns the registry entry typed strictly
- `frontend/src/index.css` MODIFIED — `@theme inline` extended with Juno's color tokens (e.g., `--color-juno-accent`, `--color-juno-accent-hover`, `--color-juno-accent-subtle` — defence palette under `.dark`); Seva's existing `--color-brand-accent*` tokens RENAMED to `--color-seva-accent*` (or kept as `brand-accent` and added Juno as `juno-accent` — naming TBD during plan-phase, but the registry abstracts the choice from components)
- `frontend/src/components/layout/AppHeader.tsx` MODIFIED — wordmark slot reads `useCompanyBrand().wordmark` instead of hardcoded "Seva Mining" string; icon slot reads `iconPath`; documented as second formally permitted post-freeze edit (cross-ref Phase 9 D-02 freeze-lift; v3.1 BRAND lift documented inline + in PROJECT.md Key Decisions)
- `frontend/src/components/layout/CompanySwitcher.tsx` MODIFIED — active/inactive token references switched from hardcoded `--color-brand-accent*` to registry-driven `useCompanyBrand().accentToken` (or equivalent CSS variable indirection so the segmented control colors flip on company switch)
- `frontend/src/components/calendar/DayCell.tsx` + `frontend/src/components/feed/SummaryCard.tsx` + `frontend/src/components/feed/SectionBlock.tsx` + `frontend/src/components/sweeper/SweeperCard.tsx` MODIFIED (light-touch) — any hardcoded `--color-brand-accent*` references swap to registry-driven token names; CSS class strings use Tailwind v4 arbitrary value syntax `[--color-brand-accent:var(--color-juno-accent)]` or equivalent
- `scripts/verify-no-brand-branching.sh` CREATED — CI grep gate: `grep -rEn "company === ['\"](?:seva|juno)['\"]" frontend/src/components/` returns hits ONLY inside `companies/` registry files or `CompanyScopedRoute.tsx` route guard; zero hits in `Brand*` / `AppHeader*` / `TabbedDashboard*` / `Calendar*` / `Sweeper*` / `SummaryCard*` / `SectionBlock*`
- `frontend/src/__tests__/branding.test.tsx` CREATED — RTL test scenario: render `<MemoryRouter initialEntries={['/seva']}>...` asserts "Seva Mining" wordmark + Seva icon path + Seva accent token in computed style; same with `'/juno'` asserts "Juno Industries" wordmark + Juno icon + Juno accent; route-change scenario asserts simultaneous flip (no FOWB intermediate state)
- Visual QA at 1440×900 operator-approved on both `/seva/feed` + `/juno/feed` (and Tab 2 + Tab 3 placeholders) — Janes/CSIS-appropriate aesthetic confirmed; defence color palette not garish

**Success Criteria** (what must be TRUE when this phase completes):
1. User on any `/juno/*` route sees "Juno Industries" wordmark in `AppHeader` + Juno logo icon + Juno color palette applied to active tab + active company switcher button; user on any `/seva/*` route sees the v3.0 "Seva Mining" + Seva icon + amber baseline unchanged (zero regression visible to operator at 1440×900)
2. User switches Seva → Juno via `CompanySwitcher`; wordmark + icon + accent color flip simultaneously on route change with no intermediate state showing the wrong brand; verified by the RTL route-change test
3. `scripts/verify-no-brand-branching.sh` exits 0 — zero `company === 'juno'` or `company === 'seva'` substrings in `frontend/src/components/`; all brand resolution flows through `useCompanyBrand()` → `companyBrandConfig.ts`
4. Adding a hypothetical third tenant (e.g., `'acme'`) requires editing exactly one file (`companyBrandConfig.ts`) + adding two assets (logo SVG + favicon PNG); zero component edits needed — verified by a doc-comment example in the registry file plus a smoke test scenario in `branding.test.tsx`
5. Full regression suites GREEN — frontend `vitest` stays at 168+ pass + the new branding scenario tests; backend + scheduler untouched

**Plans:** TBD (planner decomposition pending)

**Complexity:** M (more touch points than Phase 12; light-touch but spread across 5-7 frontend files + new registry + new test file + CSS token plumbing; operator design input required for color palette)
**Estimated duration:** 3-5 hours including operator design check-in for Juno palette

**Dependencies:**
- Phase 12 SHOULD complete first (clean ordering — smaller phase lands first), but Phase 13 has no code-level dependency on Phase 12; could be reordered if operator prefers branding-first execution
- Operator design input on Juno color palette + wordmark wording — surfaced as a discuss-phase decision item before plan-phase

**Hard parts (cross-ref PROJECT.md "Hard parts the roadmap addresses"):**

| # | Pitfall | Severity | Prevention |
|---|---------|----------|-----------|
| P1 | Branding slips into `if (company === 'juno')` branches inside components — exactly the anti-pattern Phase 9 D-08 prohibited | CRITICAL | `scripts/verify-no-brand-branching.sh` CI gate (mirrors `scripts/verify-tenant-isolation.sh` from Phase 9); `companyBrandConfig.ts` doc-comment block explicitly cites the anti-pattern + Phase 9 D-08 precedent; planner reviews this in discuss-phase before any component edit |
| P2 | Flash of wrong brand (FOWB) on route change — wordmark and icon render Seva's then re-render Juno's on first frame after `/seva → /juno` nav | HIGH | `useCompanyBrand()` reads `useParams<{company}>()` synchronously inside the component on every render; brand registry consulted in same render pass as `<CompanyScopedRoute>` guard; FOWB test in `branding.test.tsx` asserts no intermediate Seva chrome during route push |
| P3 | Tailwind v4 token name collision — renaming `--color-brand-accent` to `--color-seva-accent` breaks every existing CSS class string that references the old token (Phase 8 unified `border-zinc-800 hover:border-zinc-700` + amber-500 baseline) | HIGH | Choose ONE of: (a) keep `--color-brand-accent*` as Seva's tokens (status quo) + add `--color-juno-accent*` as Juno's, with components reading a CSS var indirection like `var(--color-active-accent)` set by route-level CSS; OR (b) rename all + grep-driven mass replace. Decide in discuss-phase. Path (a) is lower-risk for v3.1; path (b) is cleaner long-term. Default recommendation: (a) — accepting tiny semantic asymmetry over rename blast radius |
| P4 | Juno color palette feels "off-brand" for defence — too cyan/futuristic when Janes/CSIS aesthetic is sober/authoritative; or too military-camo when the brief is intelligence-analyst, not warfighter | HIGH | Operator design review BEFORE plan-phase; 2-3 palette candidates rendered as static mockups; cross-check with v3.0 Phase 10 D-01 Janes/CSIS voice anchor — "sober senior-defence-analyst-at-a-think-tank" maps to navy/slate/desaturated-steel-blue; explicitly NOT olive-drab / camo / red-alert-red |
| P5 | Favicon swap on route change is brittle — browsers cache the favicon aggressively; `/seva/` → `/juno/` route change may not re-fetch the favicon mid-session | MEDIUM | Defer favicon swap to v3.2 if browser-cache complexity dominates; in-page wordmark + logo are the v3.1 deliverable; document the deferral inline in the registry. Alternative: dynamically swap `<link rel="icon">` via `document.head` mutation on route change — acceptable if simple |
| P6 | AppHeader edit re-opens the freeze debate — Phase 5 byte-froze, Phase 9 D-02 surgically lifted for `<CompanySwitcher />`, now v3.1 needs another edit for `useCompanyBrand()` wordmark slot | LOW | Documented as second formally permitted post-freeze edit (v3.1 BRAND); inline comment in AppHeader.tsx cites both Phase 9 D-02 and this phase; PROJECT.md Key Decisions table gets a new row noting that AppHeader.tsx is now a normal file (no freeze, but edits require milestone-level rationale) |

**Architecture reference:**
- v3.0 Phase 9 D-08 — config registry pattern (`companySectionConfig.ts`) this phase extends
- v3.0 Phase 9 D-02 — AppHeader freeze-lift precedent + documentation pattern this phase mirrors
- Phase 8 UI-01..04 — Tailwind v4 `@theme inline` + semantic `--color-brand-accent*` token foundation

**Feature reference:**
- REQUIREMENTS.md BRAND-01..05 — observable acceptance criteria per requirement
- PROJECT.md "Hard parts" #3 (branding without per-tenant code forks)

**UI hint**: yes

---

### Phase 14: Juno Content Calendar (Tab 2)

**Goal:** Operator opens `/juno/calendar` and sees a fully functional weekly paper-planner grid identical to Seva's `/seva/calendar`, scoped to Juno's `calendar_items` rows. Every CRUD operation (GET range / POST / PATCH / DELETE) routes through `/api/juno/calendar/*` with `Depends(get_current_company)` enforcing `company_id='juno'` server-side; every database call goes through the `scoped_*()` helpers established in Phase 9. Zero leak in either direction — Seva calendar continues to show only Seva's rows; Juno calendar shows only Juno's. Cross-tenant isolation regression tests added.

**Depends on:** Phase 9 (multi-tenant scaffolding: `/api/{company}/calendar/*` router prefix + `Depends(get_current_company)` + `scoped_calendar_*()` helpers + `<Route path=":company">` frontend wrapper + `CalendarPage` already routes under `/:company/calendar`). Phase 13 (branding) — soft dependency: lands first so the Juno calendar header renders with Juno chrome rather than Seva's wordmark above it during the calendar's first operator UAT.

**Requirements:** JCAL-01, JCAL-02, JCAL-03, JCAL-04, JCAL-05

**Inputs:**
- v3.0 shipped backend — `backend/app/routers/calendar.py` already accepts the `/api/{company}/calendar/*` prefix and uses `scoped_calendar_*()` helpers; behavior verified for Seva in production
- v3.0 shipped frontend — `frontend/src/pages/ContentCalendarPage.tsx` already mounts under `/:company/calendar`; current behavior: renders the v2.1 Phase 6 weekly grid for both tenants but reads `useParams<{company}>()` only minimally; queryKey factory in `frontend/src/api/queryKeys.ts` already slots `company_id`
- v2.1 Phase 6 implementation (the reference Seva implementation) — `WeeklyGrid.tsx`, `DayCell.tsx`, `WeekNav.tsx`, `useCalendar` hook + 3 optimistic mutation hooks + Pydantic schemas + Alembic 0013 (title nullable + UNIQUE(date)); v3.1 Phase 14 should NOT diverge from this shape — same UI, same auto-save-on-blur, same optimistic+rollback semantics, just scoped to Juno
- Phase 9 D-08 + Phase 10's `companySectionConfig.ts` precedent — Juno-specific empty-state copy / placeholder text goes through a registry, not a component branch
- Phase 9 idempotency-filter critical bug precedent — any new query that filters by status MUST include `'partial'` (not relevant for calendar but worth re-stating as a project-wide invariant for plan-phase)
- v3.0 Phase 9 CI grep gate `scripts/verify-tenant-isolation.sh` — already protects `select(CalendarItem)` outside `scoped.py`; v3.1 must not weaken this

**Outputs:**
- `frontend/src/companies/companyCalendarConfig.ts` CREATED OR `companySectionConfig.ts` EXTENDED — registry-keyed empty-state copy + any Juno-specific micro-copy (e.g., "No content planned for this defence-industry week" vs "for this gold-sector week" — exact copy TBD in discuss-phase, defaults to a tenant-neutral phrasing)
- `frontend/src/pages/ContentCalendarPage.tsx` MODIFIED — consume `useCompanyBrand()` (from Phase 13) for any visible chrome + consume `companyCalendarConfig` for empty-state copy + ensure all `useCalendar()` calls + 3 mutation hooks pass `company` from `useParams<{company}>()` and key TanStack queries on `['calendar', company, start, end]` (4-tuple replacing v2.1's 3-tuple — Phase 9 already established this pattern, verify it's applied here)
- `frontend/src/api/calendar.ts` MODIFIED (if not already done in Phase 9) — every API client function takes `company: string` parameter and constructs `/api/${company}/calendar...` URL; queryKey factory updated; mutation hooks invalidate the 4-tuple key
- `frontend/src/components/calendar/WeeklyGrid.tsx` + `DayCell.tsx` + `WeekNav.tsx` MODIFIED only if `company` is needed deeper than `ContentCalendarPage.tsx` — likely NOT needed (page-level prop drilling preferred over hook-in-leaf-component)
- `backend/app/routers/calendar.py` MODIFIED only if a Juno-specific server-side rule emerges (e.g., per-tenant date validation, per-tenant size limit) — default: no edit; v2.1 Phase 6 server already works correctly under Phase 9's multi-tenant routing
- `backend/tests/test_calendar_tenant_isolation.py` CREATED — cross-tenant isolation tests: (a) POST `/api/juno/calendar` with valid body inserts row with `company_id='juno'` (verified via direct DB read); (b) attempting to PATCH a Seva row via `/api/juno/calendar/{seva_item_id}` returns 404 (not 403 — tenant existence isolation); (c) attempting to GET `/api/seva/calendar` after inserting a Juno row shows zero Juno bleed-through; (d) `scoped_calendar_*()` helpers correctly filter by `company_id` (verified via DB query plan or direct assertion on returned rows)
- `frontend/src/__tests__/calendar-tenant-isolation.test.tsx` CREATED — RTL scenario: render `<MemoryRouter initialEntries={['/juno/calendar']}>`, mock GET `/api/juno/calendar` returns `{items: [{...juno_row}]}` + mock GET `/api/seva/calendar` returns `{items: [{...seva_row}]}`; switch routes; assert TanStack Query keys are distinct (no shared cache key collision) + assert UI flips to the right dataset on switch
- Operator-approved human UAT: open `/juno/calendar`, edit a day cell, verify auto-save on blur, refresh page, verify persistence, switch to `/seva/calendar` and confirm Seva's prior data unchanged; mirrors v2.1 Phase 6 closing checkpoint protocol

**Success Criteria** (what must be TRUE when this phase completes):
1. Operator opens `/juno/calendar` and sees the weekly Mon-Sun paper-planner grid; current week is highlighted; empty week shows the Juno empty-state copy from the registry (not Seva's gold-sector copy)
2. Operator types into a Juno day cell, blurs the field, and the row is persisted with `company_id='juno'` (verified via `SELECT company_id, body FROM calendar_items WHERE date = ...`); refreshing the page or switching tabs and returning shows the edit intact
3. Operator switches `/juno/calendar` → `/seva/calendar` via `CompanySwitcher`; calendar view immediately reflects Seva's content with zero Juno bleed-through (TanStack Query keys properly scoped); reverse switch shows zero Seva bleed-through into Juno's view
4. Attempting to PATCH a Seva row via `/api/juno/calendar/{seva_item_id}` returns 404 — server-side `Depends(get_current_company)` + `scoped_calendar_*()` helpers correctly enforce tenant existence isolation (verified by `backend/tests/test_calendar_tenant_isolation.py`)
5. Full regression suites GREEN + the new isolation tests pass: backend stays at 184+ + new cross-tenant tests, frontend at 168+ + new isolation scenario; `scripts/verify-tenant-isolation.sh` continues to exit 0 (no new raw `select(CalendarItem)` outside `scoped.py`)

**Plans:** TBD (planner decomposition pending)

**Complexity:** S-M (most logic ALREADY EXISTS — v2.1 Phase 6 is fully functional under Phase 9's multi-tenant routing; v3.1 Phase 14 is verification + isolation tests + empty-state copy registry + Juno-specific UAT, not new feature build)
**Estimated duration:** 2-3 hours

**Dependencies:**
- Phase 9 multi-tenant foundation (✓ shipped 2026-05-19) — `/api/{company}/calendar/*` router prefix + `scoped_calendar_*()` helpers + `<Route path=":company">` wrapper all in place
- Phase 13 (branding) SHOULD complete first so `/juno/calendar` operator UAT happens with Juno chrome already rendered — but Phase 14 has no code-level dependency on Phase 13; could ship without Juno wordmark and operator sees "Seva Mining" header above Juno calendar (acceptable but ugly)

**Hard parts (cross-ref PROJECT.md "Hard parts the roadmap addresses"):**

| # | Pitfall | Severity | Prevention |
|---|---------|----------|-----------|
| P1 | Calendar port introduces conditional logic that regresses Seva — `if (company === 'juno') { useCustomGrid() } else { useStandardGrid() }` style branches | CRITICAL | No new component branches; all per-tenant variation goes through `companyCalendarConfig` registry (empty-state copy only); component code is identical for both tenants; before any commit, `grep -rEn "company === ['\"](?:seva|juno)['\"]" frontend/src/components/calendar/` returns zero hits |
| P2 | TanStack Query key collision — if `queryKeys.calendar(start, end)` is still 3-tuple (Phase 9 may have already updated to 4-tuple including company; verify), Juno cache pollutes Seva cache and vice versa | CRITICAL | Pre-flight check in plan-phase: confirm `queryKey` is 4-tuple `['calendar', company, start, end]`; if not, Phase 9 left tech debt and this phase fixes it as a prerequisite; cross-tenant isolation RTL test (above) catches this |
| P3 | `scoped_calendar_*()` helper bug — Phase 9's helpers were verified for `SummaryCard`/daily_summary path; less exercised for calendar CRUD; an off-by-one in the `WHERE company_id = :company` filter could leak | HIGH | `backend/tests/test_calendar_tenant_isolation.py` exercises all 4 CRUD ops (GET range, POST, PATCH, DELETE) with both tenants populated and asserts strict isolation; if the test surfaces a Phase 9 helper bug, fix it in the helper (`scheduler/queries/scoped.py` + `backend/app/queries/scoped.py`) not in the router |
| P4 | 404 vs 403 semantics on cross-tenant access — JCAL-05 explicitly specifies 404 (tenant existence isolation), but a routing default behavior could return 403 if `Depends(get_current_company)` triggers before the row lookup | HIGH | Verify behavior in `backend/tests/test_calendar_tenant_isolation.py` — explicitly assert 404 on `PATCH /api/juno/calendar/{seva_row_id}`; if implementation returns 403, fix the dependency order so 404 is the response (matches v2.1 Phase 6 single-tenant behavior on nonexistent IDs) |
| P5 | Empty-state copy registry over-engineering — copy is 1-3 short strings per tenant; a full registry feels heavy | LOW | Acceptable trade-off: registry is the established Phase 9 D-08 pattern; even 1-string overhead pays off when Phase 15 adds Juno sweeper empty-state copy + future tenants need their own; keep the registry shape minimal but consistent |
| P6 | Operator UAT scope creep — operator notices broader UX issues during `/juno/calendar` testing (e.g., wants tag chips, drag-drop reschedule, multi-row-per-day) | MEDIUM | Operator UAT is YES/NO on the v3.1 acceptance criteria, not an open redesign session; broader feature requests get filed as v3.2 candidates in PROJECT.md "Out of Scope (v3.x deferrals)" not patched into v3.1 |

**Architecture reference:**
- v2.1 Phase 6 implementation — `WeeklyGrid.tsx` + `DayCell.tsx` + `useCalendar` + Alembic 0013; verbatim shape for Juno
- v3.0 Phase 9 `scoped_calendar_*()` helpers + `/api/{company}/calendar` router + `<Route path=":company">` wrapper
- v3.0 Phase 9 D-08 `companySectionConfig.ts` — registry pattern for Juno-specific copy/labels

**Feature reference:**
- REQUIREMENTS.md JCAL-01..05 — observable acceptance criteria per requirement
- PROJECT.md "Hard parts" #1 (Juno Calendar port without breaking Seva Calendar)

**UI hint**: yes

---

### Phase 15: Juno Weekly Viral Sweeper (Tab 3)

**Goal:** Every Sunday 08:00 PT America/Los_Angeles, the Juno weekly sweeper cron fires (gated by `JUNO_SWEEPER_CRON_ENABLED=true` env var per Phase 10 precedent); ingests top defence-sector posts from X via `tweepy.AsyncClient.search_recent_tweets` (Juno-specific query set distinct from Seva's gold-sector queries); computes story virality across the past 7 days of Juno's `daily_summaries.raw_sources_jsonb` (Defence News + Canadian Procurement + World Events sub-arrays); calls Sonnet 4.6 (via Phase 12 per-tenant key resolver — bills to Juno's Anthropic account) for exactly 3 content angles in Janes/CSIS voice with anti-tactical clause preserved; persists a `weekly_sweeps` row with `company_id='juno'` + Phase 9 idempotency-filter pattern (includes `'partial'` status); Tab 3 at `/juno/sweeper` renders the latest sweep card with empty-state copy for first deploy. Cross-tenant isolation verified — `/seva/sweeper` shows only Seva sweeps, `/juno/sweeper` shows only Juno sweeps.

**Depends on:** Phase 9 (lock slot `juno_weekly_sweeper=1021` already reserved; `weekly_sweeps` table multi-tenant via Alembic 0014; `/api/{company}/weekly-sweeps` router prefix + `scoped_weekly_sweeps_*()` helpers in place; sweeper page already mounts under `/:company/sweeper`). Phase 10 (Janes/CSIS voice anchor in `scheduler/companies/juno/prompts.py` — anti-tactical clause + refusal-detector pattern reused for sweeper Sonnet call; `juno_refusal_detector.py` + `juno_health_check.py` modules already exist). Phase 12 (per-tenant Anthropic key resolver — Juno sweeper Sonnet calls bill to `JUNO_ANTHROPIC_API_KEY`). Phase 13 (branding — operator UAT happens with Juno chrome above the sweeper card). Phase 14 (Juno Calendar — orthogonal but ordering preserves the "smaller phases first, biggest phase last" cadence).

**Requirements:** JSWEEP-01, JSWEEP-02, JSWEEP-03, JSWEEP-04, JSWEEP-05, JSWEEP-06

**Inputs:**
- v3.0 Phase 9 — `juno_weekly_sweeper=1021` lock slot reserved (verified in `scheduler/worker.py::JOB_LOCK_IDS`); `weekly_sweeps` table accepts `company_id='juno'` rows via Alembic 0014 CHECK constraint; `scoped_weekly_sweeps_*()` helpers exist; v2.1 Phase 7 Seva sweeper continues to write `company_id='seva'` rows on Sunday 08:00 PT
- v3.0 Phase 10 — `scheduler/companies/juno/prompts.py` Janes/CSIS-voice system prompt with verbatim anti-tactical clause; `juno_refusal_detector.py` (7 substring patterns + retry-with-framing-nudge + `status='partial'` fallback); `juno_health_check.py` (signal-quality flagging); these modules are sweeper-applicable as-is or with minimal sweeper-specific extension
- v3.0 Phase 12 — `get_anthropic_client('juno')` returns Anthropic client billing to Juno's account; Sonnet 4.6 call site uses resolver
- v2.1 Phase 7 Seva sweeper implementation (reference shape) — `scheduler/agents/weekly_sweeper.py` + `scheduler/agents/x_ingest.py` (tweepy `AsyncClient.search_recent_tweets`) + virality compute over `daily_summaries.raw_sources_jsonb.gold_news[]` + 3-angle Sonnet call + status mapping (completed/partial/failed); v3.1 Phase 15 ports this shape to Juno with key differences: defence-sector X queries instead of gold-sector; virality compute reads Juno's three substantive sub-arrays (defence_news + canadian_procurement + world_events) instead of Seva's single `gold_news[]`; Sonnet voice is Janes/CSIS not Bloomberg-commodities; cron registration at lock 1021 with `JUNO_SWEEPER_CRON_ENABLED` env gate
- Defence-sector X query candidates (TBD during discuss-phase — primary unresolved input):
  - Reporter handles: @ChrisOMartens (Janes), @ColinClarkAFA (Breaking Defense), @ddstutz (Defense Daily), @TheaButton (Defense News), @nickschifrin (PBS NewsHour defence), @PolymerSerene (Reuters defence) — confirm currently active
  - Think-tank / agency: @CSIS, @RUSI_org, @TheIISS, @NATO, @DeptofDefense, @CanadianForces, @PSPC_SPAC (Public Services and Procurement Canada)
  - Hashtags: `#defence` `#NATO` `#defencetech` `#procurement` (low-signal-to-noise — likely needs tight engagement floor)
  - Defence-prime cashtags: `$LMT` `$RTX` `$NOC` `$BA` `$GD` `$BAESY` — explicit anti-feature per PROJECT.md ("Equity/financial signals on defence primes — explicit anti-feature carried forward from v3.0") — DECISION: exclude cashtags from sweeper queries
- Phase 9 idempotency filter critical bug pattern — Juno sweeper's "skip if recent run exists" filter MUST include `'partial'` status; without it, Sunday cron creates duplicate rows
- Phase 10 voice UAT precedent — operator-approved voice UAT BEFORE production-enabling `JUNO_SWEEPER_CRON_ENABLED=true` (deploy disabled, smoke-fire approve voice on real defence-X-ingested data, then flip)
- Phase 11 CLEANUP-05 Haiku ValidationError observability — pattern reused if sweeper introduces any new structured-output LLM calls (likely only Sonnet 4.6 which is free-form, but verify in plan-phase)

**Outputs:**
- `scheduler/companies/juno/sweeper_queries.py` CREATED — `JUNO_X_QUERIES: list[str]` constant defining the defence-sector recent-search queries (`(from:@ChrisOMartens OR from:@CSIS OR ...) -is:retweet lang:en min_faves:N`); operator-approved query set finalized in discuss-phase; documented inline why cashtags are excluded
- `scheduler/agents/juno_weekly_sweeper.py` CREATED — `async def run_juno_weekly_sweeper() -> None`; full orchestration: idempotency check (filter `status.in_(['running', 'completed', 'partial'])` per Phase 9 critical-fix pattern) → `agent_runs` INSERT → X ingest via `JUNO_X_QUERIES` → virality compute over past 7 days of Juno `daily_summaries.raw_sources_jsonb.defence_news[] + canadian_procurement[] + world_events[]` (URL canonicalize + cross-reference rank, mirrors v2.1 Phase 7 Seva shape) → Sonnet 4.6 call via `get_anthropic_client('juno')` with `DEFENCE_SWEEPER_SYSTEM_PROMPT` (extends `scheduler/companies/juno/prompts.py` Janes/CSIS voice + verbatim anti-tactical clause) → refusal-detector wrap via `juno_refusal_detector.call_with_refusal_guard(...)` (reused from Phase 10) → status mapping (completed/partial/failed) → `weekly_sweeps` INSERT with `company_id='juno'` → `finally` telemetry; idempotency-filter line gets an inline comment cross-referencing Phase 9 D-01b critical-fix
- `scheduler/companies/juno/prompts.py` MODIFIED — append `DEFENCE_SWEEPER_SYSTEM_PROMPT` constant (~400-600 tokens; reuses Janes/CSIS voice anchor from `DEFENCE_NEWS_SYSTEM_PROMPT` + anti-tactical clause verbatim + sweeper-specific instructions: "produce exactly 3 content angles, each suitable for a defence-industry intelligence newsletter — NOT for operational targeting / OOB / force-posture / capability-gap analysis ...")
- `scheduler/worker.py` MODIFIED — `_make_juno_weekly_sweeper_job(engine)` factory + `build_scheduler()` registration via `CronTrigger(day_of_week='sun', hour=8, minute=0, timezone='America/Los_Angeles')` (NOT 5-min staggered from Seva because Seva sweeper is also 08:00 Sunday — they fire same-time and that's OK; the advisory lock 1019 vs 1021 isolates them); `JUNO_SWEEPER_CRON_ENABLED` env gate wraps registration (default-disabled semantics matching Phase 10 `JUNO_CRON_ENABLED` pattern); INFO log on both ENABLED/DISABLED paths
- `scheduler/agents/juno_x_ingest.py` CREATED OR `scheduler/agents/x_ingest.py` REFACTORED — defence-sector X ingest function; if refactor: `x_ingest.py` becomes tenant-aware via `company_id` parameter consuming `scheduler/companies/{company}/sweeper_queries.py::COMPANY_X_QUERIES`; if separate module: clearer separation but more code duplication. Plan-phase decides (default recommendation: refactor `x_ingest.py` to tenant-aware — mirrors `daily_summary.py` shape)
- `frontend/src/companies/companySweeperConfig.ts` CREATED OR `companySectionConfig.ts` EXTENDED — Juno-specific empty-state copy ("Juno's first viral sweep runs Sunday 08:00 PT. Check back then." or Janes-voiced equivalent) + any per-tenant micro-copy
- `frontend/src/pages/WeeklyViralSweeperPage.tsx` MODIFIED — consume `useParams<{company}>()` + `useCompanyBrand()` (Phase 13) + `companySweeperConfig` registry; `useWeeklySweeps()` hook keyed on `['weekly-sweeps', company, ...]`; week-picker history UI works for both tenants identically
- `frontend/src/components/sweeper/SweeperCard.tsx` — likely NO MODIFICATION required; v2.1 Phase 7 component is already content-agnostic (renders 3 angles + virality + sources, regardless of sector); verify in plan-phase
- `backend/tests/test_weekly_sweeps_tenant_isolation.py` CREATED — cross-tenant isolation tests: (a) GET `/api/juno/weekly-sweeps` returns only Juno sweeps; (b) GET `/api/seva/weekly-sweeps` returns only Seva sweeps; (c) idempotency filter correctly includes `'partial'` status (regression test for Phase 9 D-01b)
- `scheduler/tests/agents/test_juno_weekly_sweeper.py` CREATED — unit tests covering: orchestrator happy path, refusal-detector retry path, refusal-detector second-attempt failure → `status='partial'`, idempotency-skip (recent run exists with `status='completed'` OR `'partial'` OR `'running'`), X ingest empty result → `status='partial'`, Sonnet timeout → `status='failed'`
- `scheduler/tests/test_worker.py` MODIFIED — assertion bumps for new job registration (Phase 5 / Phase 7 pattern: hardcoded job counts in 2-3 test assertions need increment when build_scheduler registers a new job)
- Voice UAT artifact — `phases/15-juno-weekly-viral-sweeper/voice_calibration_uat.md` (mirrors Phase 10's pattern); operator runs `python -m scheduler.scripts.uat_sweeper_voice_calibration` against a curated 5-10 defence-X-post fixture; produces sample Sonnet output; operator APPROVES per Phase 10 criteria (Janes/CSIS voice match + anti-tactical clause respected + 3 distinct angles + no equity/financial signals on defence primes)
- Operator post-merge action: flip `JUNO_SWEEPER_CRON_ENABLED=true` in Railway scheduler service env vars (mirrors `JUNO_CRON_ENABLED` operator-gated rollout)

**Success Criteria** (what must be TRUE when this phase completes):
1. Operator opens `/juno/sweeper` (Tab 3); first deploy shows the Juno empty-state card with copy "Juno's first viral sweep runs Sunday 08:00 PT" (or operator-approved equivalent); after the first Sunday 08:00 PT fire post-`JUNO_SWEEPER_CRON_ENABLED=true` flip, the sweeper card renders 3 defence-sector content angles with sources, virality scores, and Janes/CSIS voice
2. The first real Juno sweep `weekly_sweeps` row has `company_id='juno'`, `status='completed'` (or `'partial'` if refusal-detector triggered second-attempt failure or X ingest signal was thin), 3 angles populated, sources sub-array populated with defence-sector tweets/URLs (no gold-sector bleed), and `agent_runs.notes` shows the executed `JUNO_X_QUERIES` and the virality computation summary
3. Cross-tenant isolation holds: `/seva/sweeper` shows ONLY Seva sweeps (gold-sector content); `/juno/sweeper` shows ONLY Juno sweeps; switching tenants via `CompanySwitcher` correctly invalidates TanStack Query cache (4-tuple key includes `company`); `backend/tests/test_weekly_sweeps_tenant_isolation.py` exits GREEN
4. Operator-approved voice UAT artifact (`phases/15-juno-weekly-viral-sweeper/voice_calibration_uat.md`) shows 5/7+ automated criteria PASS plus operator-qualitative APPROVE for Janes/CSIS voice match + anti-tactical clause + no equity/financial signal on primes; voice UAT precedes `JUNO_SWEEPER_CRON_ENABLED=true` flip
5. Full regression suites GREEN — scheduler stays at 331+ pass + the new `test_juno_weekly_sweeper.py` tests + worker count bumps; backend at 184+ + new isolation tests; frontend at 168+ + new sweeper isolation scenario test; `scripts/verify-tenant-isolation.sh` continues to exit 0; `scripts/verify-anthropic-resolver.sh` (Phase 12) continues to exit 0 (Juno sweeper Sonnet call resolves via `get_anthropic_client('juno')`)

**Plans:** TBD (planner decomposition pending)

**Complexity:** L (largest v3.1 phase — 6 requirements; new scheduler agent module + system prompt + cron registration + tenant-aware X ingest + frontend page modifications + cross-tenant isolation tests + voice UAT precedent + operator-gated rollout via env var flip; defence-X-query set is the primary unresolved discuss-phase decision; benefits from being the last phase so Phase 12's per-tenant key resolver + Phase 13's branding + Phase 14's calendar isolation patterns are all production-tested by execution start)
**Estimated duration:** 6-10 hours including voice UAT + operator approval cycle

**Dependencies:**
- Phase 9 multi-tenant foundation (✓ shipped 2026-05-19) — lock slot 1021 reserved; `weekly_sweeps` table multi-tenant; `scoped_weekly_sweeps_*()` helpers in place
- Phase 10 Juno defence funnel (✓ shipped 2026-05-19) — Janes/CSIS voice anchor in `scheduler/companies/juno/prompts.py`; refusal-detector + health-check modules; voice UAT pattern
- Phase 12 (per-tenant Anthropic key) — Juno sweeper Sonnet billing flows through resolver; soft dependency (could ship Phase 15 first and have sweeper bill to shared `ANTHROPIC_API_KEY`, then Phase 12 retroactively attributes), but ordering keeps clean
- Phase 13 (branding) — operator UAT happens with Juno chrome above sweeper card; soft dependency
- Phase 14 (calendar) — orthogonal; ordering preserves "smaller first, biggest last" cadence
- Discuss-phase resolution: defence-sector X query set (handles + tags + hashtags); engagement floor; whether to refactor `x_ingest.py` to tenant-aware vs separate `juno_x_ingest.py` module
- Operator voice UAT approval BEFORE `JUNO_SWEEPER_CRON_ENABLED=true` flip in Railway (mirrors Phase 10 cron-enable contract)

**Hard parts (cross-ref PROJECT.md "Hard parts the roadmap addresses"):**

| # | Pitfall | Severity | Prevention |
|---|---------|----------|-----------|
| P1 | Defence-sector X queries are the wrong shape — too narrow (e.g., only @CSIS) misses signal; too broad (e.g., `#defence`) drowns in noise; defence-prime cashtags violate PROJECT.md's anti-feature on equity/financial signals | CRITICAL | Discuss-phase produces operator-approved `JUNO_X_QUERIES` list; cashtags explicitly EXCLUDED with inline comment citing PROJECT.md anti-feature; engagement floor (`min_faves:N`) calibrated against curated sample fixture before going live; voice UAT exercises real defence-X ingest result |
| P2 | Idempotency filter omits `'partial'` — same Phase 9 critical bug; if a Juno sweep fires, hits refusal, and lands `status='partial'`, the next Sunday 08:00 PT fire (or any retry inside the 7-day window) would NOT skip-via-idempotency and would write a duplicate row | CRITICAL | `scheduler/agents/juno_weekly_sweeper.py` idempotency filter MUST use `status.in_(['running', 'completed', 'partial'])` (matches Phase 9 D-01b Juno daily_summary precedent); inline comment cross-references Phase 9 critical-fix; regression test in `test_juno_weekly_sweeper.py` explicitly exercises `'partial'` previous-status → skip-via-idempotency path |
| P3 | Sonnet refusal on defence content — Janes/CSIS voice with anti-tactical clause is exactly the voice Phase 10 designed for, but sweeper context (analyzing viral X posts about defence) may surface refusal patterns the daily_summary path doesn't hit (e.g., a viral X thread describing a specific weapon system's operational use) | HIGH | Refusal-detector pattern from Phase 10 reused verbatim — 7 substring patterns + retry-with-framing-nudge; on second-attempt failure, sweep persists with `status='partial'` and operator UAT decides if anti-tactical clause needs tightening for sweeper context; v3.1 ships with Phase 10's prompt; v3.2 may iterate on `DEFENCE_SWEEPER_SYSTEM_PROMPT` if production-data refusal rate >10% |
| P4 | Equity/financial signal slips into sweeper synthesis — viral X post about LMT earnings surprise, BAESY contract win, or RTX stock move could naturally produce a Sonnet angle that violates PROJECT.md's anti-feature on equity/financial signals on defence primes | HIGH | `DEFENCE_SWEEPER_SYSTEM_PROMPT` explicit anti-feature clause: "Do NOT produce content angles that focus on share price, earnings, dividends, stock movement, or investment thesis on defence primes (LMT, RTX, NOC, BA, GD, BAESY, etc.); focus on policy, procurement, capability narrative, geopolitical signal"; voice UAT criterion explicitly checks no equity-angle in sample output; refusal-detector pattern set may need a sweeper-specific extension to catch equity-flavored synthesis |
| P5 | Lock 1021 vs lock 1019 same-time fire — both Seva (lock 1019) and Juno (lock 1021) sweepers fire Sunday 08:00 PT; APScheduler may queue them serially despite independent locks; if Seva sweep runs 20+ min, Juno's `misfire_grace_time=1800` could swallow it | MEDIUM | Same-time fires are independent jobs on independent locks; APScheduler `max_instances=1` is per-job-id not global; verify via boot log assertion in `scheduler/tests/test_worker.py` (both jobs registered, both fire at 08:00 Sunday, both complete within grace window); if real-world ordering issue surfaces, add `minute=2` stagger for Juno (08:02 instead of 08:00) — defer this decision to plan-phase based on Seva sweep duration data |
| P6 | Operator UAT scope creep — operator wants 5 angles instead of 3, or wants a different empty-state copy mid-UAT | MEDIUM | UAT is YES/NO on the v3.1 acceptance criteria (Janes/CSIS voice + anti-tactical clause + 3 distinct angles + no equity/financial bleed); structural changes (5 angles vs 3, different sweep cadence) get filed as v3.2 candidates; minor copy edits accepted inline |
| P7 | `x_ingest.py` refactor breaks Seva sweeper — making the existing module tenant-aware via `company_id` parameter requires touching the Seva production code path | HIGH | Plan-phase decides between refactor (cleaner, more risk) and new `juno_x_ingest.py` module (more duplication, lower Seva-regression risk); if refactor, atomic commit + full regression suite + manual Seva sweep dry-run before deploy; if separate module, accept ~150 LOC of duplication and revisit in v3.2 |
| P8 | Sweeper Sonnet bills to wrong Anthropic key — if Phase 12 resolver isn't fully wired or has a typo'd company_id, Juno sweeper synthesis could bill to Seva | HIGH | Sweeper Sonnet call uses `get_anthropic_client('juno')` with hardcoded company_id (not `get_anthropic_client(company_id)` with a variable); inline comment cites the hardcoded choice; post-deploy manual fire of `run_juno_weekly_sweeper()` followed by check of Juno Anthropic console activity confirms attribution before Sunday cron fires |

**Architecture reference:**
- v2.1 Phase 7 implementation — `scheduler/agents/weekly_sweeper.py` + `scheduler/agents/x_ingest.py` + virality compute + 3-angle Sonnet pattern; verbatim shape for Juno
- v3.0 Phase 9 — lock slot 1021 reservation + `weekly_sweeps` multi-tenant + `scoped_weekly_sweeps_*()` helpers
- v3.0 Phase 10 — Janes/CSIS voice + anti-tactical clause + refusal-detector + voice UAT precedent
- v3.1 Phase 12 — per-tenant Anthropic key resolver (cost-attribution boundary)
- v3.1 Phase 13 — `useCompanyBrand()` + registry pattern (operator UAT happens with Juno chrome)

**Feature reference:**
- REQUIREMENTS.md JSWEEP-01..06 — observable acceptance criteria per requirement
- PROJECT.md "Hard parts" #2 (Sweeper defence-sector X queries — what to actually search) + #5 (Sweeper cron correctness in multi-tenant world)

**UI hint**: yes

---

## Progress

| Phase | Milestone | Plans | Status | Completed |
|-------|-----------|-------|--------|-----------|
| 1. Gold News Card + Web Feed | v2.0 | 6/6 | Complete | 2026-05-06 |
| 2. Ontario Law Ingestion | v2.0 | 1/1 | Complete | 2026-05-06 |
| 3. Ontario Stats Ingestion | v2.0 | 1/1 | Complete | 2026-05-06 |
| 4. Prune Cron + Ops Hardening | v2.0 | 1/1 | Complete | 2026-05-06 |
| 5. Foundation — Tabs + DB + Backend Stubs | v2.1 | 5/5 | Complete | 2026-05-19 |
| 6. Content Calendar | v2.1 | 5/5 | Complete | 2026-05-19 |
| 7. Weekly Viral Sweeper | v2.1 | 6/6 | Complete | 2026-05-19 |
| 8. UI Polish + Dead-Code Strip | v2.1 | 4/4 | Complete | 2026-05-19 |
| 9. Multi-Tenant Foundation | v3.0 | 5/5 | Complete | 2026-05-19 |
| 10. Juno Defence News Funnel | v3.0 | 5/5 | Complete | 2026-05-19 |
| 11. v3.0 Audit Cleanup Bundle | v3.0.1 | 5/5 | Complete | 2026-05-20 |
| 12. Per-tenant Anthropic API Key | v3.1 | 1/3 | In Progress|  |
| 13. Per-company Branding | v3.1 | 0/? | Pending | - |
| 14. Juno Content Calendar (Tab 2) | v3.1 | 0/? | Pending | - |
| 15. Juno Weekly Viral Sweeper (Tab 3) | v3.1 | 0/? | Pending | - |

---

## Next Milestone

v3.2+ scope candidates (deferred from v3.1 planning or surfaced during v3.1 execution):

- **TENANT-N-v32** — `companies` DB table replacing hardcoded `CHECK company_id IN ('seva','juno')` constraint; scales beyond N=2 tenants
- **DEF-TIER2-v3X** — Tier-2 defence RSS feeds (Defense Daily, Inside Defense, National Defense Magazine, Defense Industry Daily, Shephard, Defense One); decision deferred pending 2-4 weeks of Tier-1 production signal data
- **TENANT-VISITED-v31-redux** — Last-visited tenant for bare `/` redirect; Zustand `lastVisitedCompany` already populated as switch-action byproduct in Phase 9; may opportunistically land in v3.1 Phase 13 if budget allows
- **OPS-DASH-v3X** — Per-tenant cost dashboard (read Anthropic + SerpAPI usage by tenant via the per-tenant key separation from Phase 12); useful operator tooling but not a v3.1 deliverable
- **Sweeper system-prompt iteration** — if v3.1 Phase 15 voice UAT or production-data refusal rate surfaces issues with `DEFENCE_SWEEPER_SYSTEM_PROMPT`, iterate in v3.2
