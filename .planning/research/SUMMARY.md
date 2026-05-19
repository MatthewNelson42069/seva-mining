# Project Research Summary

**Project:** Seva Mining v3.0 — Multi-Tenant Dashboards (Juno Industries onboarding) + Defence-Sector News Funnel
**Domain:** Subsequent-milestone integration — adding multi-tenancy + a Canadian defence-sector tenant on top of an already-shipped single-tenant FastAPI + SQLAlchemy 2.0 async + Postgres + APScheduler + React 19 + Tailwind v4 stack
**Researched:** 2026-05-19
**Confidence:** HIGH on stack additions, architecture integration shape, and pitfall taxonomy. MEDIUM on three operator-facing decisions where the four researchers diverge (scheduler topology, AppHeader freeze treatment, hardcoded-vs-DB companies list).

---

## Executive Summary

v3.0 is **not a new product** — it is a structural refactor that turns the shipped v2.1 single-tenant Seva dashboard into a two-tenant platform (Seva + Juno) and onboards Juno's defence-industry News Funnel as the second tenant's Tab 1. All four research files converge on the core architecture: a **row-level `company_id` column** on the three tenant-scoped tables (`daily_summaries`, `calendar_items`, `weekly_sweeps`), **path-prefix routing** (`/seva/*` and `/juno/*`) via React Router v6, **zero new Python or npm dependencies**, and a **defence News Funnel built from a curated Tier-1 RSS feed set** (Defense News, Breaking Defense, DefenseScoop, RUSI, SIPRI — all directly validated 2026-05-19) plus a SerpAPI fallback for paywalled sources (Janes, Bloomberg, Reuters) and a **Sonnet/Haiku structured-output relevance filter** for the "World Events Relevant to Defence" section. The Juno daily summary mirrors Seva's three-section `SummaryCard` structure (Defence News / Canadian Procurement / World Events) with a defence-analyst voice (Janes/CSIS desk energy) replacing Seva's gold-analyst voice.

The dominant risk is **cross-tenant data leak** — the v2.x codebase has ~20+ raw `select(DailySummary)` call sites that must each gain a `company_id` filter, and the natural ContextVar-based "ambient tenant" pattern is documented to leak across asyncio Tasks reusing pooled connections (CVE-2024-10976 territory). The recommended mitigation is an **explicit `company_id` parameter on every repository function** plus a `scoped_*()` query helper module, with a CI grep gate that fails any raw `select()` against multi-tenant tables outside the helpers. A secondary risk is **Anthropic content-policy refusal** on conflict-zone news (Ukraine, Gaza, Taiwan Strait) — Juno's Sonnet system prompt MUST frame analysis as "market/industry commentary" not "tactical/operational intelligence," and the daily summary agent needs a refusal-detector wrapper. Tertiary risks are the **0014 Alembic migration backfill race** (mitigated via expand/contract: ADD COLUMN with `DEFAULT 'seva'` in one deploy, then drop the DEFAULT in a follow-up) and **RSS feed silent death** (mitigated via per-feed `bozo`/`entries=[]` health-checks).

The four research files **converge on most decisions but disagree materially on three points** the planner must resolve at discuss-phase: (1) scheduler topology — three distinct proposals on the table; (2) AppHeader freeze treatment — formally lift vs. preserve via sibling component; (3) hardcoded company list vs. `companies` DB table. These are surfaced explicitly below and must NOT be smoothed over.

---

## Key Findings

### Recommended Stack

**Stack additions are pattern-only — zero new libraries.** All v3.0 capabilities ride on packages already shipped in v2.1: `anthropic>=0.86.0` (structured outputs GA in this SDK version), `feedparser 6.0.x`, `serpapi`, `sqlalchemy 2.0.x` async + `asyncpg`, `alembic`, `react-router-dom 6.x` (dynamic `:company` segment already supported), `zustand 5.x` (persist middleware already in the package). Env vars also stay flat — there are no per-tenant secrets in v3.0. Per-tenant config (RSS feed URLs, Sonnet system prompts, SerpAPI query templates) lives in a new `scheduler/companies/{seva,juno}/` Python package, code-reviewed and diffable.

**Core technologies (additive):**
- **Row-level `company_id` column** (no new lib) — single Alembic 0014 migration adds `company_id VARCHAR(20)` to the three tenant-scoped tables with backfill to `'seva'`, composite indexes `(company_id, date DESC)` / `(company_id, status)`, and a `CHECK company_id IN ('seva', 'juno')` constraint. Chosen over `fastapi-tenancy 0.4.0` (too new, released 2026-04-01), Postgres RLS (`SET LOCAL` semantics fragile with asyncpg pooling), and schema-per-tenant (multiplies Alembic complexity by N).
- **React Router v6 path-prefix `/:company`** (already installed) — `/seva/news-funnel`, `/juno/calendar`, etc. URL is the source of truth; Zustand `persist` middleware stores only "last visited" for bare `/` redirect. Rejected: subdomain (Vercel + DNS overhead) and query-param (doesn't compose with nested routes).
- **Anthropic structured outputs (`output_config.format` with Pydantic schema)** — for the "World Events → Defence Relevance" classifier. Returns `{is_relevant, category, confidence, reasoning}` from Haiku 4.5 at ~$1-2/mo at projected volume. Sonnet 4.6 retained for daily summary synthesis (~$5-10/mo additional for Juno).
- **Defence RSS feed set (Tier 1, all validated 2026-05-19)** — Defense News (Industry, Pentagon, Global, plus 5 domain sub-feeds), Breaking Defense, DefenseScoop, RUSI Commentary + Publications, SIPRI Combined. **NOT available as RSS:** Janes, IISS, Reuters (dropped RSS in 2020), Bloomberg — these route through SerpAPI `engine=google_news` with `site:` queries inside the existing $50/mo SerpAPI budget. **Phase-0 verification needed:** war.gov, nato.int, forces.gc.ca / canada.ca defence.

Full STACK.md verdict table at `.planning/research/STACK.md`.

### Expected Features

**Must have (table stakes for v3.0):**
- Company switcher in `AppHeader` — every multi-tenant SaaS ships one (Linear/Notion/Slack/Vercel pattern)
- Persistent active-company state — URL is canonical; `useParams()` reads it; Zustand mirrors "last visited" only
- URL reflects active company — `/seva/*` `/juno/*` for deep-linking, browser back/forward, shareable URLs
- Per-company API scoping — every read endpoint filtered by `company_id`; every write tagged with it
- Per-company cron scoping — daily_summary and weekly_sweeper write to the correct tenant's rows
- Seva data preservation through migration — zero downtime, zero data loss (backfill in same migration)
- Defence-sector RSS ingestion + SerpAPI queries (Janes/Bloomberg/Reuters fallback)
- Sonnet daily summary for Juno with defence-industry voice + dual-use exclusion list
- World Events section with Sonnet/Haiku structured-output relevance filter
- Tab 1 of Juno renders the live daily summary; Tabs 2 + 3 render empty-state copy until v3.1+

**Should have (differentiators):**
- Cmd+1 / Cmd+2 keyboard shortcuts for tenant switching
- Tier-1 vs Tier-2 feed source weighting in Sonnet prompts
- Inclusion-category tags rendered as badges in the World Events section
- Contract-value extraction in Defence News bullets
- Juno empty-state component for Tab 1 on day 1

**Anti-features (explicit do-NOT-build in v3.0):**
- Subdomain routing per tenant, per-tenant branding, cross-company dashboards, per-tenant RBAC, mobile-responsive switcher, equity signals on defence primes, operational/tactical intelligence, live conflict map, defence-stats third section (replaced with World Events).

Full feature catalog and prioritization matrix in `.planning/research/FEATURES.md`.

### Architecture Approach

**Additive integration, not rewrite.** No existing component is renamed or removed by v3.0 — every change is either a new file or a surgical edit. The five architectural decisions (D-01 through D-05) are landed in two phases: Foundation (DB + backend scope + frontend routing + AppHeader change) and Juno News Funnel (config-only).

**Major components added or modified:**
1. **`backend/app/queries/scoped.py`** (NEW) — `scoped_summaries(company_id)`, `scoped_calendar(company_id)`, `scoped_weekly_sweeps(company_id)`. The cross-leak defence — every router MUST start its query here.
2. **`backend/app/companies/` + `scheduler/companies/`** (NEW packages) — `ACTIVE_COMPANIES` Literal, per-tenant `CompanyConfig` dataclass.
3. **`scheduler/agents/daily_summary.py`** (MODIFIED) — per-company loop with per-company try/except.
4. **`frontend/src/components/layout/CompanySwitcher.tsx`** (NEW) — segmented control. Placement depends on AppHeader freeze decision.
5. **`frontend/src/App.tsx`** (MODIFIED) — `<Route path=":company">` wrapper; bare `/` redirects to `/seva`; v2.x bookmark grace redirects preserved.

Full file change map in `.planning/research/ARCHITECTURE.md` §4.

### Critical Pitfalls

Top items the roadmap must address (full taxonomy in `.planning/research/PITFALLS.md`):

1. **Query without `company_id` filter is the #1 multi-tenancy bug** (CRITICAL) — ~20+ raw `select(DailySummary)` call sites exist in v2.x. Mitigation: `scoped_*()` helpers + CI grep gate. Foundation phase.
2. **Async session ContextVar leak across pool connections** (CRITICAL) — Mitigation: explicit `company_id` parameter on every repo function. NO middleware ContextVar tenant. Foundation phase.
3. **0014 migration backfill race with daily_summary cron** (HIGH) — Mitigation: ADD COLUMN with `DEFAULT 'seva'` (expand/contract pattern). Foundation phase.
4. **Anthropic content-policy refusal on conflict-zone news** (HIGH) — Mitigation: market/industry framing + refusal-detector wrapper. Juno News Funnel phase.
5. **TanStack Query keys missing `company_id`** (HIGH) — Mitigation: centralized key factory + `queryClient.clear()` on switch. Foundation phase.
6. **RSS feed silent death** (HIGH) — Mitigation: per-feed `bozo`/`entries=[]` health-check + recent-history comparison alert. Juno News Funnel phase.
7. **Existing bookmarks to `/` break** (CRITICAL) — Mitigation: grace redirects inside `<ProtectedRoute />`. Foundation phase.

---

## Inter-Research Disagreements (planner must resolve at discuss-phase)

### Disagreement 1 — Scheduler topology (THREE distinct proposals)

| File | Proposal | New `JOB_LOCK_IDS` | Failure isolation | Trade-off |
|------|----------|--------------------|--------------------|-----------|
| **ARCHITECTURE.md D-02** | **Single cron per job-type with in-process per-company fan-out.** Outer lock 1017/1018/1019 reused; agent loops `for c in ACTIVE_COMPANIES` with per-company try/except. | **ZERO new entries** | Per-company try/except inside agent (sequential — Seva failure doesn't block Juno but Juno waits) | Tangles failure modes inside one job; OPS-02 lock inventory stays minimal; one Sonnet hang at 60s pushes Juno's start back |
| **STACK.md** | **Explicit per-company jobs with distinct lock IDs.** `juno_daily_summary: 1020`, `juno_weekly_sweeper: 1021`. Separate `add_job(..., args=[company_id])` per company. | **+2 entries (1020, 1021)** | True APScheduler-level isolation; Juno hang does not delay Seva | Lock-ID inventory grows linearly with tenants; adding company #3 means +2-3 more IDs |
| **PITFALLS.md §3.4** | **Per-tenant 100-ID blocks.** Seva: 1000-1099 (existing IDs retained). Juno: 1100-1199 (1117/1118/1119 reserved). Append-only block allocation rule in CONVENTIONS.md. | **+1-3 entries in Juno block; 100-ID block reserved** | True APScheduler isolation per company | Heavier lock-ID accounting; OPS-02 assertion gains a "registered job ⊆ JOB_LOCK_IDS keys" sub-check |

**Trade-off axes:** failure isolation (Options 2/3 real, Option 1 logical), lock-ID inventory (Option 1 stays at 4 forever; Option 3 reserves 100 per tenant), Railway log clarity (Options 2/3 clean), fan-out concurrency risk (Option 1 may approach Anthropic RPM; Options 2/3 staggered 5+ min explicitly avoid), future N tenants.

**Planner discuss-phase question:** Lock-ID minimalism (Option 1) vs APScheduler-level isolation + log clarity (Option 2 or 3)? Design for N=2 simplicity or pattern that scales cleanly to N=5+?

### Disagreement 2 — AppHeader freeze treatment (Path A vs Path B)

| File | Path | What happens to `AppHeader.tsx` | Visual QA baseline |
|------|------|--------------------------------|--------------------|
| **ARCHITECTURE.md D-04** | **Path A — Lift the freeze formally.** Document v3.0 milestone-level rationale; surgical 5-line insertion of `<CompanySwitcher />` between brand mark and Logout. | Edited (~5 lines) | Re-baselined to v3.0 |
| **PITFALLS.md §5** | **Path B — Preserve the freeze.** Add `frontend/src/components/CompanyBar.tsx` sibling rendered by `AppShell.tsx` BELOW `<AppHeader />` in its own border-b sub-bar. | Untouched | v2.1 baseline intact |

**Trade-off axes:** UX convention (header is conventional — Path A), visibility on /settings + /digest, freeze contract integrity, future maintenance (one canonical header vs two header-adjacent components).

**Planner discuss-phase question:** Phase 5 freeze as soft constraint that yields to milestone-level change (Path A — cleaner long-term), or hard contract v3.0 works around (Path B — lower-risk launch)?

### Disagreement 3 — Hardcoded company list vs `companies` DB table

| File | Lean | Rationale |
|------|------|-----------|
| **PITFALLS.md §3.4** | Hardcoded `COMPANIES = ['seva', 'juno']` acceptable for v3.0 with CHECK constraint; must become DB table by v3.2+. | Adding company #3 requires code deploy; no per-company config; operator can't self-serve. Trade-off worth taking at N=2. |
| **ARCHITECTURE.md D-05** | Per-company config lives in Python `companies/` package only. NO `companies` DB table. | DB-stored config only valuable for runtime operator edits; v3.0 has no Settings page (deprecated v2.0). Defer until Settings revived. |
| **STACK.md** | Alembic 0014 creates `companies` table with `(id, display_name, created_at)` + FK. | Referential integrity from day one. |

**Planner discuss-phase question:** v3.0 creates `companies` table in 0014 (STACK.md — referential integrity) or defers it (ARCHITECTURE.md D-05 — code-only config)? Both researchers agree it's a small migration; question is v3.0 vs v3.1 scope.

---

## Cross-Research Agreements (no debate needed)

1. **Row-level `company_id` for data isolation** — all four files. Rejected: fastapi-tenancy 0.4.0, schema-per-tenant, DB-per-tenant, Postgres RLS.
2. **Path-prefix routing `/seva/*` `/juno/*` via React Router v6** (Stack + Architecture). Rejected: subdomain, query-param.
3. **Zero new Python or npm dependencies** — pure pattern + schema + config additions (Stack + Architecture).
4. **Juno's third News Funnel section = "World Events Relevant to Defence"** via Sonnet/Haiku structured-output relevance filter (Features + Stack). Haiku 4.5 classifier + Sonnet 4.6 synthesis.

---

## Operator Decision Points (discuss-phase agenda)

1. **`companies` table vs hardcoded list** — see Disagreement 3.
2. **Per-tenant Anthropic API key vs shared key** — PITFALLS §5 recommends `ANTHROPIC_API_KEY_SEVA` and `ANTHROPIC_API_KEY_JUNO` separately so Anthropic-side safety logging keeps cross-tenant content separated upstream. STACK + ARCHITECTURE default to single shared key. Recommendation: defer to v3.1+ unless content-policy review becomes a real concern.
3. **Default `/` redirect target** — PITFALLS §4.1: hardcoded `/seva` (simpler) vs last-visited from localStorage (Linear/Notion pattern).
4. **Voice calibration for "senior defence analyst" tone** — FEATURES.md Open Q §5. Juno prompt designed from scratch (NEVER cloned from Seva per PITFALLS Technical Debt). Build-phase iteration with 3-5 sample voice-validation pass.
5. **DND/PSPC ingestion — SerpAPI-heavier strategy for Canadian procurement gap** — STACK + FEATURES confirm NO public RSS for DND/PSPC. Canadian Procurement section relies on SerpAPI `site:canada.ca defence`, `site:canadiandefencereview.com` + Lagassé Substack + Atlantic Council. Confirm $5-15/mo incremental SerpAPI budget acceptable.

---

## Implications for Roadmap

Research converges on **two phases**, with Foundation as a single atomic deploy.

### Phase 1: Multi-Tenant Foundation

**Rationale:** `company_id` migration is irreversible. Partial multi-tenancy is worse than none. Must ship as one deploy.

**Delivers:** Alembic 0014; `scoped_*()` helpers; `get_current_company()` dep; `/api/{company}` router prefix; `scheduler/companies/` package; daily_summary refactored to per-company loop (juno stub); frontend `/:company` routing; `CompanyScopedRoute`; `companyStore.ts`; `CompanySwitcher`; AppHeader edit OR sibling CompanyBar (discuss-phase); TanStack key factory; bookmark grace redirects; tenant-scoped test scaffolding + `test_multitenant_isolation.py`.

**Addresses (FEATURES):** Company switcher, persistent active-company state, URL reflects company, per-company API scoping, per-company cron scoping, Seva data preservation, default landing company, per-company query keys.

**Avoids (PITFALLS):** Missing `company_id` filter (CRITICAL), ContextVar leak (CRITICAL), backfill race (HIGH — expand/contract), missing composite index (HIGH), TanStack stale render (HIGH), bookmark breakage (CRITICAL), login drops context (HIGH), AppHeader freeze conflict (HIGH — Path A or B), lock-ID collision (CRITICAL — topology decision).

**Exit criteria:** `/seva/*` byte-equivalent to v2.1. `/juno/*` empty states. One scheduler fire produces Seva row AND Juno row (Juno `status='partial'`). `EXPLAIN ANALYZE` uses composite index. CI grep gate passes.

### Phase 2: Juno News Funnel

**Rationale:** Foundation live; isolation verified. Juno content is config-only after foundation.

**Delivers:** Populate `scheduler/companies/juno/{feeds,prompts,serpapi}.py` (Tier-1 RSS + paywalled SerpAPI fallback + Canadian-procurement queries); `DEFENCE_NEWS_SYSTEM_PROMPT` designed from scratch (anti-tactical framing, dual-use exclusion list, regional balance); `scheduler/agents/juno_relevance.py` Sonnet/Haiku structured-output classifier; refusal-detector wrapper; per-feed bozo health-check; voice-calibration UAT; Tab 1 of `/juno/` renders live summary.

**Uses (STACK):** Anthropic structured outputs (`output_config.format` with Pydantic schema), feedparser 6.0.x with bozo health-check, SerpAPI `engine=google_news` for paywalled fallback, Haiku 4.5 classification + Sonnet 4.6 synthesis.

**Implements (ARCHITECTURE):** `scheduler/companies/juno/` module; defence-relevance filter; Juno daily summary write inside `_run_daily_summary_for_company('juno')`.

**Avoids (PITFALLS):** Sonnet refusal (HIGH — framing + refusal-detector), Sonnet false positives consumer tech (HIGH — Haiku two-stage filter + exclusion list), RSS silent death (HIGH — bozo health-check), regional source bias (MEDIUM — US/Canada/Europe/Indo-Pacific quota), newsletter mixed with hard news (MEDIUM — feed-level wire/analysis/opinion tag), Anthropic rate limit collision (MEDIUM — ≥5 min stagger).

**Exit criteria:** Juno renders real summary on Tab 1 with non-empty Defence News, Canadian Procurement, World Events. Seva byte-identical. `SELECT count(*) FROM daily_summaries GROUP BY company_id` matches expected fire counts. Refusal-detector tested against ≥5 edge-case stories with no `"sonnet_refused"` errors.

### Phase Ordering Rationale

- Foundation must precede Juno content (column + helpers are deps).
- Foundation must ship as one deploy (partial multi-tenancy is worse than none).
- Phase 2 splits naturally — config-only after foundation; voice UAT discrete from infra.
- v3.0 deferrals (Juno Tab 2/3, per-company branding, third tenant) stay deferred per PROJECT.md.

### Research Flags

**Needs `/gsd:research-phase` during planning:**
- **Phase 2** — Juno Sonnet prompt design (voice iteration), Phase-0 RSS endpoint verification (war.gov, nato.int, canada.ca), refusal-detector test corpus curation.

**Standard patterns (skip research):**
- **Phase 1** — ARCHITECTURE D-01..D-05 documented with file-change map + code shapes. Open items are operator decisions, not research gaps.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All Tier-1 RSS URLs directly fetched + validated 2026-05-19. Anthropic structured outputs GA confirmed. fastapi-tenancy 0.4.0 PyPI metadata verified + rejected with rationale. MEDIUM only on NATO/war.gov/canada.ca specifics (Phase-0 verify). |
| Features | HIGH | Multi-tenancy UX patterns well-documented (Linear/Notion/Slack/Vercel). Defence news taxonomy industry-standard. MEDIUM on Canadian procurement signal (DND/PSPC RSS gap). |
| Architecture | HIGH | All claims grounded in direct v2.1 codebase reads with cited paths + line numbers. Additive, not rewriting. |
| Pitfalls | HIGH | Grounded in codebase audit + external sources (CVE-2024-10976, Anthropic-Pentagon dispute, Janes feed history). Three CRITICAL items have documented mitigations. |

**Overall:** HIGH on technical research; MEDIUM on three disagreements (operator decisions, not gaps).

### Gaps to Address

- **Phase-0 RSS verification** — war.gov press-releases, nato.int news feed, canada.ca defence web-feeds. Mitigation: SerpAPI `site:` fallback. Schedule curl verification as first task of Phase 2.
- **Juno voice calibration corpus** — 5-10 hand-curated defence stories for Phase 2 operator UAT. Assemble before Sonnet prompt design.
- **Refusal-detector test set** — 5-10 known-edge-case stories (Ukraine, Gaza, Taiwan, Iran, Korea) for monthly regression. Curate during Phase 2.
- **Three discuss-phase disagreements** — operator decisions, not research gaps. Roadmap should NOT presume resolution; discuss-phase agenda must include them.

---

## Sources

### Primary (HIGH confidence)

- v2.1 codebase direct reads: `backend/app/main.py`, `backend/app/models/{daily_summary,calendar_item,weekly_sweep}.py`, `backend/app/routers/{summaries,calendar,weekly_sweeps}.py`, `backend/alembic/versions/0013_calendar_title_nullable_unique_date.py`, `scheduler/worker.py`, `scheduler/agents/daily_summary.py`, `frontend/src/App.tsx`, `frontend/src/components/layout/{AppHeader,AppShell,TabbedDashboard}.tsx`
- `.planning/PROJECT.md` v3.0 milestone section
- `.planning/milestones/v2.1-research/{ARCHITECTURE,PITFALLS}.md` baseline
- Anthropic structured outputs: https://platform.claude.com/docs/en/build-with-claude/structured-outputs
- Defense News RSS feed inventory (fetched 2026-05-19): https://www.defensenews.com/m/rss/
- Breaking Defense feed: https://breakingdefense.com/feed/
- DefenseScoop feed: https://defensescoop.com/feed/
- RUSI RSS feeds: https://www.rusi.org/rusi-rss-feeds
- SIPRI RSS combined: https://www.sipri.org/rss
- React Router v6: https://reactrouter.com/start/declarative/routing
- fastapi-tenancy 0.4.0 PyPI: https://pypi.org/project/fastapi-tenancy/
- SIPRI 2024 military expenditure: https://www.sipri.org/media/press-release/2026/global-military-spending-rise-continues-european-and-asian-expenditures-surge
- 2026-27 DND Departmental Plan: https://www.canada.ca/en/department-national-defence/corporate/reports-publications/departmental-plans/departmental-plan-2026-27.html
- Anthropic-Pentagon dispute: https://en.wikipedia.org/wiki/Anthropic%E2%80%93United_States_Department_of_Defense_dispute
- Janes Defence News: https://www.janes.com/osint-insights/defence-news
- AWS multi-tenant RLS: https://aws.amazon.com/blogs/database/multi-tenant-data-isolation-with-postgresql-row-level-security/
- Crunchy Data RLS for tenants: https://www.crunchydata.com/blog/row-level-security-for-tenants-in-postgres
- TanStack Query invalidation: https://tanstack.com/query/v5/docs/framework/react/guides/query-invalidation
- Linear/Notion/Slack/Vercel switcher patterns: https://linear.app/docs/workspaces, https://www.notion.com/help/create-delete-and-switch-workspaces, https://slack.com/help/articles/1500002200741, https://vercel.com/platforms/docs/multi-tenant-platforms/custom-subpaths

### Secondary (MEDIUM confidence)

- FastAPI multi-tenancy community: https://github.com/fastapi/fastapi/discussions/6056
- Aditya Mattos FastAPI + RLS: https://adityamattos.com/multi-tenancy-in-python-fastapi-and-sqlalchemy-using-postgres-row-level-security
- MergeBoard FastAPI multitenancy: https://mergeboard.com/blog/6-multitenancy-fastapi-sqlalchemy-postgresql/
- PostgreSQL advisory locks: https://leapcell.io/blog/orchestrating-distributed-tasks-with-postgresql-advisory-locks
- NATO RSS landing: https://www.nato.int/cps/us/natohq/RSS.htm
- War.gov RSS landing: https://www.war.gov/news/rss/
- Defense One / Defense Daily / National Defense Magazine / Inside Defense / Defense Industry Daily
- Philippe Lagassé Substack: https://philippelagasse.substack.com/
- Atlantic Council Canadian defence: https://www.atlanticcouncil.org/in-depth-research-reports/issue-brief/how-to-equip-canadas-defense-industrial-base-to-meet-natos-hague-summit-commitments/
- Multi-Tenant Leakage SaaS: https://medium.com/@instatunnel/multi-tenant-leakage-when-row-level-security-fails-in-saas-da25f40c788c
- Defacto expand/contract migration: https://www.getdefacto.com/article/database-schema-migrations
- Anthropic-Pentagon timeline: https://www.techpolicy.press/a-timeline-of-the-anthropic-pentagon-dispute/
- Chatham House defence dual-use surge: https://www.chathamhouse.org/2026/04/how-surge-defence-and-dual-use-technology-investment-could-reconfigure-global-ai-race/02

### Tertiary (LOW confidence — needs Phase 0 / Phase 2 validation)

- FeedSpot top-60 defence RSS aggregator (discovery only): https://rss.feedspot.com/defense_rss_feeds/
- Department of National Defence Canada RSS — no direct endpoint confirmed; forces.gc.ca/en/stay-connected/rss-feeds.page 404'd
- RCAF news feed — subsumed under Canada DND fallback

---
*Research completed: 2026-05-19*
*Ready for roadmap: yes — with three discuss-phase decisions explicitly flagged for operator resolution*
