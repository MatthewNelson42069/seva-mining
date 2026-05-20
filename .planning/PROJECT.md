# Seva Mining — Multi-Tenant AI Intelligence Platform

## What This Is

A **multi-tenant AI intelligence platform** producing 2x-daily defence/sector intelligence briefs for a Canadian operator. Twice daily (08:00/12:00 PT for Seva; 08:05/12:05 PT for Juno — 5-min stagger), per-tenant cron jobs ingest sector-specific news + regulatory/policy signals + relevant world events; produce a structured 3-section summary card per tenant; persist to Postgres with `company_id` row-level isolation; surface on the React dashboard at `/seva/*` and `/juno/*` (operator toggles via segmented switcher in `AppHeader`); and deliver WhatsApp teasers with deep links back to the feed. 30-day rolling retention. No drafting, no approval flow, no autoposting.

**Active tenants (v3.0):**
- **Seva Mining** — gold-sector daily digest (gold news + Ontario/Canadian mining law + Ontario gold-production stats)
- **Juno Industries** — defence-tech daily intelligence brief (Tier-1 defence press + Canadian procurement via SerpAPI + World Events Relevant to Defence via Haiku 4.5 relevance classifier; Janes/CSIS desk voice with anti-tactical framing)

(Originally designed as a 6-sub-agent approval-dashboard product for Seva; pivoted to the digest model in v2.0; expanded to multi-tenant in v3.0 — see Evolution.)

## Core Value

Every piece of intelligence the dashboard surfaces must be genuinely valuable to the analyst for that company — gold-sector intelligence for Seva, defence-industry + world-events-relevant-to-defence intelligence for Juno. If a bullet wouldn't make a senior analyst in that company's domain stop scrolling, it shouldn't be in the summary.

## Current State

🚧 **v3.1 in progress — Phase 14 shipped 2026-05-20** — Juno Content Calendar landed (JCAL-01..05 verified PASS by gsd-verifier, 5/5 requirements + 12/12 invariants). Phase 14 was the tightest scope in v3.1 — codebase scout caught that backend + frontend hooks were ALREADY multi-tenant from v2.1 Phase 6 + v3.0 Phase 9; only the Phase 9 D-09 short-circuit (13 lines at `ContentCalendarPage.tsx:42-54`) was gating `/juno/calendar`. Net change: deleted 13 lines + added 2 new test files (frontend RTL with TanStack Query key isolation + backend pytest with 4 cross-tenant 404 assertions covering PATCH × 2 directions + DELETE × 2 directions). REQUIREMENTS.md JCAL-01 wording relaxed per D-06 with `*(D-06)*` provenance marker. Zero Seva-side changes (D-07 byte-identical contract held across 12 critical files). Frontend tests: 175 → 178 (+3); backend tests: 184 → 188 (+4). 3 post-deploy human-verification items queued (visual confirmation /juno/calendar renders WeeklyGrid with navy palette; DayCell autosave round-trip; live CompanySwitcher Juno↔Seva with no mid-edit bleed). Next phase: 15 (Juno Weekly Viral Sweeper — largest v3.1 phase).

🚧 **v3.1 Phase 13 shipped 2026-05-20** — Per-company Branding landed (BRAND-01..05 verified PASS by gsd-verifier, 12/12 invariants + operator visual QA APPROVED 10/10 at 1440×900). `frontend/src/config/companyBrandConfig.ts` registry of record (mirrors `companySectionConfig.ts` pattern); `useCompanyBrand()` hook resolves URL → Zustand → 'seva' fallback. `/juno/*` now shows "Juno Industries" wordmark + "J" navy square + navy-toned palette `oklch(0.58 0.14 245)` resolved via `:root.dark[data-company='juno']` CSS override (specificity 0,2,0 beats Phase 8 `.dark` 0,1,0); `/seva/*` zero regression (D-09 byte-identical). FOWB-free transitions via `CompanyBrandEffect` single useEffect committing dataset+title+favicon atomically. Polish folded: tab title + favicon swap + bare-`/` redirect (TENANT-VISITED-v31-redux closed). Frontend tests: 168 → 175 (+2 Juno default + 5 FOWB; zero regressions).

🚧 **v3.1 Phase 12 shipped 2026-05-20** — Per-tenant Anthropic API Key resolver landed (KEY-01..04 verified PASS by gsd-verifier, 16/16 must-haves). `scheduler/anthropic_client.py` resolver routes every Anthropic call through `get_anthropic_client(company_id: Literal["seva","juno"], *, timeout)`; 5 production sites refactored (3 Seva + 2 Juno); 3 dead functions + 1 orphan helper excised from `content_agent.py`; CI grep gate `scripts/verify-anthropic-resolver.sh` enforces resolver-only Anthropic instantiation; `scheduler/worker.py::_validate_env` surfaces per-tenant + STRICT env-var status at boot. Operator post-deploy actions pending (Railway env-var config + Anthropic console attribution check + `ANTHROPIC_RESOLVER_STRICT=true` flip + CI integration).

✅ **v3.0.1 shipped 2026-05-20** — v3.0 audit cleanup complete (5/5 CLEANUP requirements verified PASS by gsd-verifier). All regression gates GREEN: backend 184 pass / scheduler 331 pass (+3 from new Haiku ValidationError observability tests) / frontend 168 pass. Production cron LIVE — `JUNO_CRON_ENABLED=true` flipped in Railway 2026-05-20; next 08:05 PT America/Los_Angeles cron writes the first real Juno defence intelligence brief.

✅ **v3.0 shipped 2026-05-19** — multi-tenant platform live. Seva + Juno toggle operational. Audit verdict: `tech_debt` — 20/20 requirements satisfied, 0 critical blockers, 8 non-blocking follow-ups (5 closed in v3.0.1; 3 deferred to v3.1+). See [`milestones/v3.0-MILESTONE-AUDIT.md`](milestones/v3.0-MILESTONE-AUDIT.md).

## Current Milestone: v3.1 Juno Feature Parity + Branding

**Goal:** Bring Juno to feature parity with Seva — build Juno's Content Calendar (Tab 2) + Weekly Viral Sweeper (Tab 3), apply proper Juno branding so `/juno/*` no longer renders the "Seva Mining" wordmark, and split the shared Anthropic API key per tenant for clean cost attribution. After v3.1 ships, Juno = a complete defence-industry equivalent of Seva (intelligence dashboard + content planner + weekly viral sweeper), not just a one-tab news brief.

**Target features:**
- **JUNO-CAL-v31** — Juno Content Calendar (Tab 2) — paper-planner UI scoped to Juno's `calendar_items` rows; weekly Mon-Sun grid with auto-save on blur; port of Seva's v2.1 Phase 6 implementation behind multi-tenant `scoped_*()` helpers; defence-aware drafting prompts (Janes/CSIS voice + anti-tactical clause preserved if any LLM-assist is wired in)
- **JUNO-SWEEP-v31** — Juno Weekly Viral Sweeper (Tab 3) — Sunday 08:00 PT APScheduler cron at lock slot `juno_weekly_sweeper=1021` (reserved in Phase 9); Juno-specific defence-sector X API queries (distinct from Seva's gold-sector queries); virality compute over Juno's `daily_summaries.raw_sources_jsonb` (Defence News + Canadian Procurement + World Events sub-arrays); 3 Sonnet 4.6 content angles per sweep; Tab 3 React UI renders the latest sweep card with empty-state copy for first deploy
- **TENANT-BRAND-v31** — Per-company branding — Juno logo + Juno wordmark + Juno color palette (defence-industry appropriate; subdued / authoritative vs Seva's gold-bull amber); brand assets keyed on `:company` URL segment; brand-token CSS values resolved per route; AppHeader wordmark + favicon adapt to active tenant; per-tenant Tailwind `--color-brand-accent*` token resolution
- **TENANT-KEY-v31** — Per-tenant Anthropic API key — Replace single shared `ANTHROPIC_API_KEY` env var with `SEVA_ANTHROPIC_API_KEY` + `JUNO_ANTHROPIC_API_KEY`; resolver picks the right key based on `company_id` at each LLM call site (Haiku classifier + Sonnet synthesis + future Calendar/Sweeper LLM calls); cost-attribution clean per tenant; rollback path: env-var unset on `JUNO_*` keys falls back to shared `ANTHROPIC_API_KEY`

**Budget:** Incremental — Juno's weekly sweeper reuses the existing X API Basic tier ($100/mo, shared with Seva); Sonnet calls for Juno sweeper synthesis ~$2-4/mo; Juno calendar adds no recurring cost (UI + DB only). Total monthly cost target: ~$210-225/month envelope unchanged.

**Stack additions (suspected — confirmed during research):**
- No new dependencies expected — Calendar reuses TanStack Query + Zustand + existing `<DayCell />` component; Sweeper reuses `tweepy.AsyncClient` + Sonnet 4.6 client; Branding is pure CSS-tokens-by-route work; Per-tenant key is config plumbing
- Possible: Alembic migration if any new column needed for branding storage (TBD — likely all branding is hardcoded per tenant in source, not DB-driven, until N>2 tenants requires it)

**Hard parts the roadmap addresses:**
1. **Juno Calendar port without breaking Seva Calendar.** v2.1 Phase 6 was single-tenant; Juno gets the same UI but scoped via `scoped_*()` helpers + `/api/{company}/calendar` router prefix already in place. Risk: regression in Seva Calendar behavior if the port introduces conditional logic.
2. **Sweeper defence-sector X queries — what to actually search.** Seva's gold-sector queries (`#gold`, cashtags, mining accounts) don't map. Need Juno-specific queries: defence primes? defence journalists? `#defence` / `#NATO` / specific RUSI/CSIS handles? Discuss-phase decision item.
3. **Branding without per-tenant code forks.** v3.0 Phase 9 D-08 established the pattern: single component, semantic config object (`companySectionConfig.ts`) per tenant. v3.1 extends this for brand colors + wordmark + logo — must not slip into `if (company === 'juno') {...}` branches.
4. **Per-tenant Anthropic key without breaking local dev.** Local-dev `.env` typically has one `ANTHROPIC_API_KEY`. Resolver must fall back gracefully when per-tenant keys aren't set (dev) but enforce them when set (prod cost-attribution). Avoid an "env-var typo silently routes to wrong tenant's key" footgun.
5. **Sweeper cron correctness in multi-tenant world.** OPS-02 already reserves lock `1021` for `juno_weekly_sweeper`. Cron must be `JUNO_SWEEPER_CRON_ENABLED` env-gated (mirroring `JUNO_CRON_ENABLED` precedent from v3.0 Phase 10) so this can deploy disabled and operator-enable after smoke fire passes.

**Out of scope (explicit exclusions — deferred to v3.2+):**
- **DEF-TIER2-v31** — Tier-2 defence RSS feeds (Defense Daily, Inside Defense, National Defense Magazine, Defense Industry Daily, Shephard, Defense One). Wait 1-2 weeks of v3.0/v3.0.1 Tier-1 production data before deciding if more feeds are needed. May be added mid-v3.1 if signal proves thin, but not in scope at milestone start.
- **TENANT-VISITED-v31** — Last-visited tenant for bare `/` redirect. Already half-built in v3.0 (Zustand `lastVisitedCompany` populated as switch-action byproduct). Tiny gap; not worth its own requirement; can be folded into Branding phase opportunistically if low-cost.
- **TENANT-N-v32** — `companies` DB table replacing hardcoded `CHECK company_id IN ('seva','juno')` constraint. v3.2+ scaling milestone when N>2 tenants required.
- **Operational/tactical defence intelligence** — hard prohibition (Anthropic content-policy boundary preserved across all Juno features including Calendar drafting + Sweeper synthesis).
- **Equity/financial signals on defence primes** — explicit anti-feature carried forward from v3.0.
- **Autoposting** — single-user manual approval model preserved.
- **Mobile-responsive UI** — desktop-only constraint preserved.

## Past Milestones

Collapsed milestone details — see `milestones/v3.0-ROADMAP.md` (snapshot at v3.0 close, includes v2.1 phase details) and `milestones/v2.0-ROADMAP.md` for full context.

<details>
<summary>v3.0 Multi-Tenant Dashboards — Juno Industries Onboarding (shipped 2026-05-19)</summary>

**Goal:** Transform the single-tenant Seva Mining dashboard (shipped through v2.1) into a multi-tenant platform supporting per-company dashboards under one UI, with a company switcher in the header. Onboard **Juno Industries** (defence tech, Canada) as the second tenant, starting with the News Funnel — ingesting defence-industry news plus world events that relate to defence (geopolitical shifts, conflicts, military spending, defence tech announcements).

**Target features:**
- **Multi-tenancy foundation** — `companies` table (or equivalent), per-company data isolation (row-level `company_id` vs schema-per-company — TBD in discuss-phase), company-switcher UX in `AppHeader` (frozen Phase 5 baseline gets a surgical addition), URL routing pattern (path prefix `/seva/` `/juno/` vs query param vs subdomain — TBD)
- **Juno News Funnel (Tab 1 of Juno dashboard)** — defence-sector RSS ingestion (Janes, Defense News, Breaking Defense, RCAF, NATO, etc.); SerpAPI defence-news queries; world-events-relevant-to-defence heuristic via Sonnet filter (e.g. geopolitical/conflict/military-spending stories); Juno-scoped `daily_summary` cron writing to a Juno-isolated table/scope; Tab 1 renders the live feed with the same Linear-style amber/zinc design from v2.1
- **Cross-tenant data integrity** — existing Seva data stays intact through the migration; defence ingestion doesn't bleed into gold-sector summaries and vice versa; OPS-02 advisory-lock uniqueness preserved if per-company schedulers are introduced

**Budget:** Incremental — defence-sector RSS feeds are free; SerpAPI defence-news queries add a small ($5-15/mo) overhead inside existing $50/mo SerpAPI budget; Sonnet calls for Juno daily summary add ~$5-10/mo. Total monthly cost target: ~$210-225/month (within original v1.0 envelope).

**Stack additions (suspected — will be confirmed during research):**
- `feedparser` already present from v2.0; new defence-sector RSS feed URLs only
- New env vars: `JUNO_*` namespace for any Juno-specific config (TBD — most config likely shared)
- Possibly Alembic migration to add `company_id` column to `daily_summaries` (or new `juno_daily_summaries` table — strategy TBD)

**Hard parts the roadmap addresses:**
1. **Multi-tenancy data isolation strategy.** Row-level `company_id` (single table, simpler queries) vs schema-per-company (cleaner isolation, harder migrations) vs separate tables (`juno_daily_summaries`). Decision affects every downstream piece.
2. **Company switcher UX without breaking Phase 5's frozen `AppHeader.tsx`.** Surgical addition: a dropdown or segmented control next to the brand mark, with state in URL (path-prefix routing) so deep links and browser back/forward work cleanly.
3. **Defence-sector news heuristic.** What counts as "defence industry news"? What counts as "world events relevant to defence"? Sonnet relevance filter needs a tight system prompt to avoid noise (e.g. excluding consumer tech, sports, finance unless directly defence-adjacent).
4. **Scheduler topology.** One cron that fans out per-company, or one cron per company? OPS-02 lock-ID assignment for Juno's daily_summary job.
5. **Migrating Seva data without downtime.** If we add `company_id` column, backfill all existing rows to `company_id='seva'` in the same migration. No data loss.

**Out of scope (explicit exclusions for v3.0 — deferred to v3.1+):**
- Juno Content Calendar (Tab 2) — same paper-planner UI but Juno-scoped, deferred
- Juno Weekly Viral Sweeper (Tab 3) — defence-sector X API queries + virality compute, deferred
- Per-company branding/color palettes (Juno keeps the same amber/zinc baseline initially; brand customization is a v3.1+ feature)
- Adding a third company beyond Seva + Juno (v3.0 proves the pattern with two; N companies is v3.2+)
- Mobile-responsive UI (still single-user desktop, same constraint as v2.x)
- Cross-company analytics / unified dashboards
- Per-company user permissions (single-operator model continues; the operator sees all companies they can switch into)

</details>

## Requirements

### Validated

**v2.0 Daily Summary Feed (shipped 2026-05-06):**
- ✓ Daily summary cron + agent (SUM-01..06) — v2.0 Phase 1
- ✓ Gold News section (GOLD-01..03) — v2.0 Phase 1
- ✓ Web feed UI at `/` (FEED-01..06) — v2.0 Phase 1
- ✓ WhatsApp teaser + failure alert (WHA-01..03) — v2.0 Phase 1
- ✓ Ontario Law section with SerpAPI + NRCan + Haiku filter (LAW-01..04) — v2.0 Phase 2
- ✓ Ontario Stats section with StatCan WDS direct poll (STAT-01..05) — v2.0 Phase 3
- ✓ 30-day prune cron + lock-id uniqueness assertion + retirement audit (OPS-01..04) — v2.0 Phase 4

**v2.1 Three-Tab Content Engine — Foundation (shipped 2026-05-18):**
- ✓ Three-tab dashboard shell + route restructure with auth-gate preservation (TAB-01..05) — v2.1 Phase 5
- ✓ `calendar_items` + `weekly_sweeps` tables (Alembic 0011/0012) with dual-model SQLAlchemy parity and auth-gated stub routers (DB-01..05) — v2.1 Phase 5

**v2.1 Content Calendar — Paper-Planner Model (shipped 2026-05-19):**
- ✓ Weekly Mon-Sun grid where each day is a direct-edit textarea with auto-save on blur; full CRUD over `calendar_items` with optimistic mutations + rollback; 1 row per date enforced via Alembic 0013 (title nullable + UNIQUE(date)); plain text only, no tags/dialogs/chips per user simplification (CAL-01..10) — v2.1 Phase 6

**v2.1 Weekly Viral Sweeper — X-API pivot (shipped 2026-05-19):**
- ✓ Sunday 08:00 PT APScheduler cron ingests top gold-sector tweets via tweepy `recent_search` (reused $100/mo Basic tier — Reddit dropped), computes story virality over past 7 days of `daily_summaries.raw_sources_jsonb.gold_news[]` (URL canonicalize + cross-reference rank), calls Sonnet 4.6 for 3 content angles, persists a `weekly_sweeps` row with status mapping (completed/partial/failed), and Tab 3 renders the latest sweep card with empty-state copy for the first deploy. SWEEP-01/02 dropped per X-API pivot (Reddit replaced); SWEEP-03..14 complete (SWEEP-13/14 carryover human-verify items deferred to first cron fire, tracked in 07-HUMAN-UAT.md) — v2.1 Phase 7

**v2.1 UI Polish + Dead-Code Strip (shipped 2026-05-19):**
- ✓ Linear-style dark/amber-500 design applied consistently across all 3 tabs via 3 semantic CSS tokens (`--color-brand-accent[-hover/-subtle]`) added to `index.css` `@theme inline`; UI-04 `border-zinc-800` baseline + `hover:border-zinc-700 transition-colors` unified across `SummaryCard`/`SweeperCard`/`SectionBlock`/`DayCell`; Geist Variable weights 400/500/600 enforced via grep script (UI-01..04). UI-05 reframed for X-API pivot — `@handle` monospace pills (replacing the original Reddit `r/gold` spec) implemented via `XHandlePill` + `rehypeHandleMentions` rehype plugin + `MarkdownContent` wrapper, applied everywhere `@\w+` appears in react-markdown content with `[rehypeRaw, rehypeSanitize, rehypeHandleMentions]` pipeline (sanitize first as security boundary). UI-06 dead-code strip removed `scheduler/agents/content/` directory entirely (15 files, ~5100 lines); `JOB_LOCK_IDS` shrunk to 4 keys; OPS-02 assertion still passes; DB rows preserved per `260420-sn9`/`260423-k8n` precedent. UI-07 visual QA at 1440×900 PASSED by operator across all 3 tabs (UI-01..07) — v2.1 Phase 8

**v3.0 Multi-Tenant Foundation (shipped 2026-05-19):**
- ✓ Single atomic deploy converted the single-tenant Seva dashboard to a two-tenant platform (Seva + Juno toggle). Alembic 0014 added `company_id VARCHAR(20) NOT NULL` with `server_default='seva'` to `daily_summaries`/`calendar_items`/`weekly_sweeps` (atomic backfill in same DDL transaction — no race), CHECK `company_id IN ('seva', 'juno')`, composite indexes `(company_id, sort_col)`. Cross-tenant leak defense via `backend/app/queries/scoped.py` + `scheduler/queries/scoped.py` helpers + CI grep gate `scripts/verify-tenant-isolation.sh` (blocks raw `select(DailySummary|CalendarItem|WeeklySweep)` outside `queries/scoped.py`). Backend routers refactored to `/api/{company}/...` prefix with `Depends(get_current_company)`; `ACTIVE_COMPANIES: Literal["seva","juno"]` in Python source. Per-company scheduler: `juno_daily_summary=1020` REGISTERED at `CronTrigger(hour="8,12", minute=5, timezone="America/Los_Angeles")` (5-min stagger from Seva); `juno_weekly_sweeper=1021` slot-only (v3.1+); OPS-02 uniqueness preserved with 6 keys. Frontend `<Route path=":company">` wrapper around TabbedDashboard; bookmark grace `<Navigate>` redirects for v2.x URLs (`/calendar` → `/seva/calendar`, etc.); `CompanyScopedRoute.tsx` validates `:company` ∈ ACTIVE_COMPANIES; `CompanySwitcher.tsx` segmented control using semantic `--color-brand-accent*` tokens (zero new amber-500 literals); centralized `frontend/src/api/queryKeys.ts` factory with `company_id` slot; Zustand `lastVisitedCompany` via `persist` + `partialize`; `queryClient.clear()` before `navigate()` on switch. **AppHeader.tsx Phase 5 byte-freeze formally lifted** with documented v3.0 rationale in 3 locations (inline comment + `09-SUMMARY.md` Decisions section + PROJECT.md Key Decisions). Juno renders empty-state on Tab 1/2/3 until Phase 10 (DEF-01..10) populates real defence-sector content. Critical bug surfaced + auto-fixed during smoke test: Juno's idempotency filter omitted `'partial'` status — extended to `status.in_(['running','completed','partial'])` so re-firing the cron within the 60-min window correctly idempotency-skips (TENANT-01..10) — v3.0 Phase 9

**v3.0 Juno Defence News Funnel (shipped 2026-05-19):**
- ✓ Config-only build on Phase 9 infrastructure. Populated `scheduler/companies/juno/{feeds, prompts, serpapi}.py` with real defence content: 13 Tier-1 RSS feeds (Defense News × 8 sub-feeds + Breaking Defense + DefenseScoop + RUSI Commentary + RUSI Publications + SIPRI Combined — all HTTP-validated 2026-05-19); 10 SerpAPI `google_news` queries (7 Canadian procurement + 3 fallback for war.gov/nato.int/canada.ca which lack clean RSS); Janes/CSIS-voice production Sonnet 4.6 system prompt with explicit anti-tactical clause (per Anthropic-Pentagon dispute precedent). New `scheduler/agents/juno_relevance.py` Haiku 4.5 classifier using GA `client.messages.parse(output_format=DefenceRelevance)` syntax — `{is_relevant, category, confidence, reasoning}` structured output filtering World Events at `confidence >= 0.7` across 9 inclusion categories (active conflict / alignment shifts / spending policy / sanctions+export controls / energy+critical-minerals / semiconductors / space / hypersonic+AI+autonomy / treaty events). New `scheduler/agents/juno_refusal_detector.py` substring-pattern detector (7 regex patterns scanning first 500 chars) with retry-once-with-framing-nudge fallback. New `scheduler/agents/juno_health_check.py` with bozo + empty + `<30%` of 7-day-avg flagging; 3+ feed flags → `status='partial'`. `run_juno_daily_summary` extended (+715 LOC) for real 3-section synthesis. SerpAPI gated morning-only (08:05 PT) to save ~$2-4/mo while 12:05 PT re-uses morning's substrate. `SummaryCard.tsx` per-tenant rendering via `companySectionConfig` (Juno reads "Defence News" / "Canadian Procurement" / "World Events Relevant to Defence"; Seva reads "Gold News" / "Ontario Law" / "Ontario Stats"; physical DB columns reused semantically per Phase 9 ARCHITECTURE D-08 — single component, no per-tenant fork). `JUNO_CRON_ENABLED` env var gate added to `worker.py::build_scheduler()` — production cron stayed disabled until operator-approved voice UAT. Voice UAT: 8 hand-curated defence stories produced sample Sonnet output; 5/7 automated criteria PASSED + 1 corpus-bounded (Sonnet correctly flagged 2/2/2 bullet gap rather than padding) + 1 operator-judgment (qualitative Janes/CSIS voice match APPROVED). Manual smoke fire wrote a `status='completed'` row with Defence News 2709 chars (Janes/CSIS voice, contract-value-named) + World Events 3464 chars (6/35 Haiku-survived) + Canadian Procurement 0 chars by design (12:05 PT cost gate). Visual QA at 1440×900 APPROVED 10/10 (DEF-01..10) — v3.0 Phase 10

**v3.0 milestone COMPLETE (2026-05-19):** Multi-tenant platform live. Seva + Juno toggle operational. Production Railway env-var `JUNO_CRON_ENABLED=true` flip is the sole remaining post-merge action before the next 08:05 PT cron writes a real defence-sector intelligence brief.

**v3.0.1 Audit Cleanup Bundle (shipped 2026-05-20):**
- ✓ CLEANUP-01 — Morning-only SerpAPI cost gate removed from `scheduler/agents/daily_summary.py::_build_juno_canadian_procurement_section`. Both daily Juno fires (08:05 PT + 12:05 PT) now execute the 7 Canadian-procurement SerpAPI queries. Budget: ~$5.25/mo → ~$8-9/mo inside $50/mo cap. Test refresh atomic in same commit (commits `1e2c03f` + `7e956b4`).
- ✓ CLEANUP-02 — `milestones/v3.0-REQUIREMENTS.md` traceability rows DEF-01..DEF-07 refreshed from "Scaffolded (Wave 0)" → "Complete (2026-05-19, plan 10-02 / 10-03 — <evidence>)" matching DEF-08..10 format (commits `5dd14b8` + `ff679f1`).
- ✓ CLEANUP-03 — Stale Phase 9 stub section-divider comment block removed from `scheduler/agents/daily_summary.py` (Phase 10 had already replaced the stub body inline; planner scoped to the misleading comment). Post-deletion: exactly one `async def run_juno_daily_summary` at line 1147; `scheduler/worker.py` lazy import unchanged (commits `8f9fb10` + `3736d00`).
- ✓ CLEANUP-04 — Both `milestones/v3.0-phases/{09-multi-tenant-foundation,10-juno-defence-news-funnel}/0[9-10]-VALIDATION.md` frontmatters flipped `nyquist_compliant: true` + `wave_0_complete: true` (commits `5c3ebbe` + `22467bb`).
- ✓ CLEANUP-05 — Haiku 4.5 classifier ValidationError observability via caller-owned `validation_errors: list[dict] | None = None` keyword-only accumulator in `scheduler/agents/juno_relevance.py::classify_story` + plumbed through `daily_summary.py` to `agent_runs.notes['haiku_validation_errors']` with `{input_excerpt, error_type, error_msg}` shape. Fail-closed contract preserved verbatim (item still excluded from synthesis on schema mismatch). 3 new RED→GREEN tests; backwards-compat via inspect.signature (commits `54af8d0` + `c46c97b` + `6476e7d`).
- ✓ Phase 11 verifier 5/5 PASS at `.planning/phases/11-audit-cleanup-bundle/11-VERIFICATION.md`. Regression suites all GREEN (scheduler 331 +3 / backend 184 / frontend 168). Phase 11 closed via manual artifact updates after GSD CLI hung on `phase complete` (commit `731cfaa`).
- ✓ Production action: `JUNO_CRON_ENABLED=true` flipped in Railway 2026-05-20 (scheduler service Variables). First real Juno production brief lands 2026-05-21 08:05 PT America/Los_Angeles (CLEANUP-01..05) — v3.0.1 Phase 11

### Key Decisions

- **v3.0 Phase 9 AppHeader freeze-lift (D-02):** The Phase 5 byte-freeze on `frontend/src/components/layout/AppHeader.tsx` was formally lifted in v3.0 to accommodate the `<CompanySwitcher />` insert (5-line surgical edit between brand mark and Logout). Documented in 3 locations: inline comment at AppHeader.tsx, phase-level `09-SUMMARY.md` Decisions section, and this PROJECT.md entry. Future maintainers: AppHeader is no longer byte-frozen — edits are permitted but require explicit documentation of milestone-level rationale.
- **v3.0 Phase 9 multi-tenancy strategy (D-03):** Row-level `company_id VARCHAR(20)` column on the 3 multi-tenant tables with `CHECK company_id IN ('seva', 'juno')` constraint + `ACTIVE_COMPANIES: Literal["seva", "juno"]` in Python source. Chosen over `companies` DB table (deferred to v3.2+ TENANT-N-v32), Postgres RLS, schema-per-tenant, and `fastapi-tenancy 0.4.0`. Cross-tenant data isolation enforced via mandatory `scoped_*()` query helpers + CI grep gate.
- **v3.0 Phase 10 voice anchor (D-01):** Juno Sonnet 4.6 system prompt designed from scratch (NOT cloned from Seva's gold-bull-bias prompt). Voice = Janes/CSIS desk energy (authoritative, sober, sourced-with-receipts senior-defence-analyst-at-a-think-tank). Explicit anti-tactical clause forbids operational/tactical/OOB/force-posture/capability-gap/troop-movement/targeting analysis per Anthropic-Pentagon dispute precedent. Source-driven regional balance (no in-prompt quota — Tier-1 feeds skew US-defence; rebalance is a substrate concern, not a prompt concern).
- **v3.0 Phase 10 relevance classifier (D-05/D-06/D-07):** Haiku 4.5 (cheap, fast, sufficient) + GA `messages.parse(output_format=PydanticModel)` syntax (NOT deprecated beta `output_config.format`). 9 inclusion categories from CSIS/RAND/SIPRI taxonomy. Confidence threshold `>= 0.7` for items reaching Sonnet synthesis. Reserved for v3.0.1+ logging cleanup: silent fail-closed on Pydantic ValidationError surfaced during voice UAT.

### Out of Scope (v3.0 deferrals to v3.1+/v3.2+)
- Juno Content Calendar (Tab 2) → v3.1+ JUNO-CAL-v31
- Juno Weekly Viral Sweeper (Tab 3) → v3.1+ JUNO-SWEEP-v31
- Per-company branding (Juno keeps "Seva Mining" wordmark in v3.0) → v3.1+ TENANT-BRAND-v31
- N>2 companies (`companies` DB table) → v3.2+ TENANT-N-v32
- Tier-2 defence RSS feeds (Defense Daily, Inside Defense, etc.) → v3.1+ if Tier-1 signal proves insufficient
- Per-tenant Anthropic API key → v3.1+ if content-policy review surfaces a need
- Equity/financial signals on defence primes — explicit anti-feature (out of scope permanently)
- Operational/tactical intelligence — hard prohibition (Anthropic content-policy boundary)

### Key Decisions

- **v3.0 Phase 9 AppHeader freeze-lift (D-02):** The Phase 5 byte-freeze on `frontend/src/components/layout/AppHeader.tsx` was formally lifted in v3.0 to accommodate the `<CompanySwitcher />` insert (5-line surgical edit between brand mark and Logout). Documented in 3 locations: inline comment at AppHeader.tsx, phase-level `09-SUMMARY.md` Decisions section, and this PROJECT.md entry. Future maintainers: AppHeader is no longer byte-frozen — edits are permitted but require explicit documentation of milestone-level rationale.
- **v3.0 Phase 9 multi-tenancy strategy (D-03):** Row-level `company_id VARCHAR(20)` column on the 3 multi-tenant tables with `CHECK company_id IN ('seva', 'juno')` constraint + `ACTIVE_COMPANIES: Literal["seva", "juno"]` in Python source. Chosen over `companies` DB table (deferred to v3.2+ TENANT-N-v32), Postgres RLS, schema-per-tenant, and `fastapi-tenancy 0.4.0`. Cross-tenant data isolation enforced via mandatory `scoped_*()` query helpers + CI grep gate.

**v1.0.1 Approval Dashboard (deprecated by v2.0 pivot, source retained as dead code):**
- ✓ Validated in Phase 8: DigestPage daily digest with prev/next navigation (DGST-01..03)
- ✓ Validated in Phase 8: ContentPage content review with format-specific rendering and approve flow (CREV-01..05)
- ✓ Validated in Phase 8: SettingsPage with 6 tabs — Watchlists, Keywords, Scoring, Notifications, Agent Runs, Schedule (SETT-01..08)
- ✓ Validated in Phase 9: All agent engagement gate thresholds and schedule intervals DB-driven — tunable from Settings without a deploy (EXEC-02)

### Active

> **Pivot 2026-04-27, completed 2026-05-06 — v2.0 supersedes the v1.0 Active list below.** The 6-sub-agent approval-dashboard product surface has been retired as dead code (crons deregistered in v2.0 Phase 4 Task 4; source files retained). The items below are kept for historical context only — they are NOT actively pursued. New v2.1+ requirements will be added when the next milestone is scoped.

- [ ] Four-agent system: Senior Agent (orchestrator), Content Agent (daily story), Twitter Agent (2h monitoring), Instagram Agent (4h monitoring)
- [ ] Approval dashboard with separate tabs for Twitter, Instagram, and Content
- [ ] Feed/timeline layout with inline editing on approval cards
- [ ] One-click copy to clipboard + direct link to post on platform
- [ ] Each approval card shows: platform badge, original post (URL + excerpt), account info, drafted response (2-3 alternatives), rationale, urgency indicator, final score, Approve/Edit+Approve/Reject buttons
- [ ] WhatsApp notifications via Twilio — morning digest + breaking news alerts + expiring high-value draft alerts
- [ ] Simple password authentication (single user)
- [ ] Content Agent: RSS ingestion (Kitco, Mining.com, JMN, WGC) + SerpAPI news search
- [ ] Content Agent: deep research pass with web search for corroborating sources before drafting
- [ ] Content Agent: format decision logic — long-form article, short post/thread, infographic brief
- [ ] Content Agent: threads drafted as both thread format AND single long-form X post
- [ ] Content Agent: infographic briefs include full caption text
- [ ] Content Agent: quality threshold (7.0/10) — "no story today" flag if nothing clears the bar
- [ ] Infographic generation — HTML templates for data-heavy pieces, AI image generation for creative/editorial
- [ ] Twitter Agent: X Basic API integration, keyword + cashtag + hashtag monitoring
- [ ] Twitter Agent: configurable watchlist (bypass engagement gate), stored in DB, editable from dashboard
- [ ] Twitter Agent: engagement scoring (likes x1 + retweets x2 + replies x1.5), account authority, topic relevance
- [ ] Twitter Agent: minimum gate 500+ likes OR watchlist account 50+ likes
- [ ] Twitter Agent: recency decay — full at 1h, 50% at 4h, expired at 6h
- [ ] Twitter Agent: drafts both reply AND retweet-with-comment for each post (user picks one)
- [ ] Twitter Agent: 2-3 draft alternatives per post
- [ ] Twitter Agent: event mode — triggers on engagement spike (3x+ normal) OR significant gold price movement, scales output to 8-10 posts
- [ ] Instagram Agent: Apify scraper integration, hashtag + account watchlist monitoring
- [ ] Instagram Agent: scoring (likes x1 + comments x2 + normalized followers x1.5), 200-like minimum, 8h window
- [ ] Instagram Agent: no hashtags in drafted comments, ever
- [ ] Instagram Agent: retry logic and best-effort reliability for scraping
- [ ] Senior Agent: queue management, hard cap 15 items, priority scoring
- [ ] Senior Agent: deduplication across agents — same story = separate cards per platform, visually linked as related
- [ ] Senior Agent: auto-expiry (Twitter: 6h, Instagram: 12h)
- [ ] Senior Agent: performance-driven learning loop — tracks what content types get engagement online, filters accordingly
- [ ] Agent self-evaluation: quality rubric (relevance, originality, tone match, no company mention, no financial advice) before queuing
- [ ] All scoring weights, thresholds, and decay curves configurable from dashboard Settings page
- [ ] Settings page: watchlist management (X + IG), keyword management, scoring parameters, agent run logs, notification preferences, agent schedule configuration
- [ ] State machine: pending -> approved/edited_approved/rejected(reason required)/expired(auto)
- [ ] Agent run logging: every execution logged with items found, queued, filtered, errors

### Out of Scope

- Auto-posting to any platform — v1 is manual post only
- LinkedIn agent — removed from scope
- Reddit monitoring — dropped, RSS + SerpAPI is sufficient signal
- Multi-tenancy — v1 is Seva Mining only, refactor when second client exists
- Mobile-responsive dashboard — desktop only
- Analytics dashboard — deferred to v2
- Two-way WhatsApp (approve/reject via chat) — notifications only

## Context

**Company:** Seva Mining (@sevamining on X and Instagram) — a gold exploration company. The Content Agent covers the broader gold sector, not Seva-specific news or projects.

**Non-negotiable rule:** Seva Mining is never mentioned in any drafted reply, comment, or retweet. Not once, not subtly, not ever. Every response stands on its own as a genuinely valuable contribution.

**Voice:** Senior analyst — data-driven, measured, cites specifics. Bloomberg commodities desk energy. Consistent across all platforms and formats. No variation between X, Instagram, or content pieces.

**Hard prohibition:** No financial advice — no buy/sell signals, price predictions, or investment recommendations in any draft.

**Content frequency expectation:** Content Agent produces stories ~4-5 days per week. The 7.0/10 quality threshold should be calibrated to roughly this frequency.

**Content value-add:** Story-dependent — connecting dots to broader trends, original analysis/modeling, or smart curation and contextualization. Whatever the story calls for.

**Seed data:** RSS feeds (Kitco, Mining.com, JMN, WGC) and keyword lists from the blueprint serve as initial seeds. User will customize via the dashboard Settings page during build.

**Future vision:** v2 adds analytics dashboard. Long-term: multi-client platform serving multiple mining companies.

## Constraints

- **Budget**: ~$255-275/month total operating cost
- **X API**: Basic tier ($100/mo) — read-only access
- **Instagram**: Apify scraper (~$50/mo) — managed scraping with bot detection handling
- **News**: SerpAPI (~$50/mo) + RSS feeds (free)
- **AI**: Anthropic Claude API (~$30-50/mo)
- **Hosting**: Railway for backend (API + separate scheduler worker), Vercel for frontend (subdomain)
- **Database**: PostgreSQL via Neon (free tier, upgrade to Pro when 512MB fills)
- **WhatsApp**: Twilio (~$5/mo)
- **Stack**: FastAPI (Python) backend, React + Tailwind CSS frontend, APScheduler in separate worker process
- **Auth**: Simple password login, single user
- **Schema**: Full schema from day one including all columns for alternatives, event mode, quality scores. JSONB array for draft alternatives. Keep all data forever (no retention policy).

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| WhatsApp over email for notifications | User prefers WhatsApp for daily digest and alerts, uses Twilio for delivery | — Pending |
| Separate scheduler worker | Scheduler crash shouldn't take down the dashboard API. Minimal extra Railway cost. | — Pending |
| SerpAPI over Google News RSS | More flexible structured data, worth $50/mo for quality signal | — Pending |
| No Reddit | Reddit API restrictions, RSS + SerpAPI provides sufficient signal | — Pending |
| Railway over Fly.io/Render | Simpler ops, good web+worker support, predictable pricing at this scale | — Pending |
| JSONB for draft alternatives | Alternatives always displayed together in approval card, never queried independently | — Pending |
| HTML templates + AI for infographics | Templates for consistent data-heavy pieces, AI generation for creative/editorial | — Pending |
| Desktop-only dashboard | Single user reviews on desktop, mobile responsiveness not needed for v1 | — Pending |
| Skip multi-tenancy for v1 | No over-engineering — refactor when second client actually exists | — Pending |
| Neon free tier | Upgrade to Pro ($19/mo) when 512MB storage limit is reached | — Pending |
| Event mode for Twitter | Engagement spike (3x+) OR significant price movement triggers higher output (8-10 posts) | — Pending |
| 2026-05-19 — v3.0 Phase 9 — AppHeader freeze formally lifted | Phase 5 byte-freeze of `AppHeader.tsx` lifted per 09-CONTEXT.md D-02. Surgical 5-line `<CompanySwitcher />` insert between brand-mark `<div>` and Logout `<button>`. Brand mark + wordmark stay "Seva Mining" on both tenants per D-02a; per-tenant branding deferred to v3.1+ (TENANT-BRAND-v31). Third documentation location per D-02 (a = 09-SUMMARY.md Decisions section; b = inline `// v3.0 freeze-lift (Phase 9) — see 09-CONTEXT.md D-02` comment in AppHeader.tsx; c = this entry). | Locked |
| 2026-05-19 — v3.0 Phase 9 — Multi-tenancy strategy: row-level company_id | Per 09-CONTEXT.md D-03 — Alembic 0014 adds `company_id` column + CHECK constraint `IN ('seva', 'juno')` to all three multi-tenant tables (`daily_summaries`, `calendar_items`, `weekly_sweeps`); `ACTIVE_COMPANIES: Literal["seva", "juno"]` lives in backend + scheduler `companies/__init__.py`. No `companies` DB table in v3.0 — accepted tech debt; close in v3.2+ when N>2 tenants requires a real table (REQUIREMENTS.md TENANT-N-v32). All tenant-scoped reads route through `backend/app/queries/scoped.py` helpers; CI grep gate (`scripts/verify-tenant-isolation.sh`) enforces no raw `select(DailySummary | CalendarItem | WeeklySweep)` outside that module. | Locked |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? -> Move to Out of Scope with reason
2. Requirements validated? -> Move to Validated with phase reference
3. New requirements emerged? -> Add to Active
4. Decisions to log? -> Add to Key Decisions
5. "What This Is" still accurate? -> Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-05-20 — v3.1 Phase 14 shipped (Juno Content Calendar Tab 2 enablement; 5/5 JCAL requirements verified PASS, 12/12 invariants). Tightest scope in v3.1: 13-line deletion + 2 new test files. Frontend tests 175 → 178 (+3); backend tests 184 → 188 (+4); zero regressions. 3 of 4 v3.1 phases complete (12, 13, 14). Next phase: 15 (Juno Weekly Viral Sweeper — JSWEEP-01..06; largest remaining; Sunday 08:00 PT cron + defence-sector X queries + Sonnet 4.6 Janes/CSIS synthesis + operator-gated rollout via JUNO_SWEEPER_CRON_ENABLED).*
