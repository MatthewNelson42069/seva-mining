# v3.0 Multi-Tenant Dashboards + Juno News Funnel — FEATURES Research

**Project:** Seva Mining v3.0 — Multi-Tenant Dashboards (Seva + Juno toggle) + Juno (Defence) News Funnel
**Mode:** Ecosystem / Feature Research (subsequent milestone — NEW features only)
**Domain:** Multi-tenant personal-intelligence tool — adding defence-sector tenant to an already-shipped single-tenant gold-sector app
**Confidence:** HIGH (multi-tenant UX patterns — Linear/Notion/Slack/Vercel are well-documented), HIGH (defence-news source taxonomy — Janes/Defense News/Breaking Defense/Defense One are industry-standard), MEDIUM (Canadian-specific procurement signal — DND/PSPC RSS coverage is thin), HIGH (world-events-relevance heuristic — semiconductor/hypersonic/conflict adjacency is well-mapped in CSIS/RAND analysis)
**Researched:** 2026-05-19

---

## SCOPE NOTE — What This Research Covers

v3.0 is a **subsequent milestone** layered on top of a shipped v2.1 single-tenant app. This research deliberately scopes ONLY to NEW features for v3.0:

1. **Multi-tenancy plumbing** — switcher UX, URL routing, per-company isolation surfaces
2. **Juno News Funnel content** — the defence-industry analog of Seva's "gold news + Ontario law + Ontario stats" structure
3. **World-events-relevant-to-defence** — the cross-cutting signal that distinguishes a defence News Funnel from a generic news aggregator

**Out of scope for this research (already built or deferred per PROJECT.md):**
- Seva News Funnel content (shipped v2.0, no changes)
- Tab 2 Content Calendar / Tab 3 Weekly Viral Sweeper (Juno-side deferred to v3.1+)
- Per-company branding (Juno reuses amber/zinc baseline initially)
- Cross-company analytics / unified dashboards (explicit anti-feature)
- N-company scaling beyond Seva + Juno (deferred to v3.2+)

---

## CATEGORY 1 — MULTI-TENANCY PLUMBING

### TABLE STAKES — Must Ship in v3.0

| Feature | Why Expected | Complexity | Dependencies on v2.x |
|---------|--------------|------------|----------------------|
| **Company switcher in `AppHeader`** | Every multi-tenant SaaS (Linear, Notion, Slack, Vercel, Linear) ships a workspace/team/org switcher; without it the app is single-tenant by definition | M | Surgical addition to Phase-5-frozen `AppHeader.tsx` — DO NOT rewrite; insert switcher component next to brand-mark |
| **Persistent active-company state** | User must not be re-prompted on each navigation — current company persists across tab switches and page reloads | S | URL is source of truth (see routing below); localStorage as backup for deep-link freshness |
| **URL reflects active company** | Deep-linking, browser back/forward, and shareable links all depend on company-in-URL — Linear/Notion both encode workspace in URL | M | Restructure existing `/` `/calendar` `/sweeper` routes; existing routes become `/{company}/...` (see routing decision below) |
| **Per-company data isolation in API** | Defence news must never bleed into gold summaries (and vice versa) — every read endpoint scoped by active company; every write tagged with `company_id` | M | Alembic migration adding `company_id` to `daily_summaries`, `calendar_items`, `weekly_sweeps`; backfill all existing rows to `company_id='seva'` in same migration |
| **Per-company cron scoping** | OPS-02 advisory-lock uniqueness must hold; daily_summary cron writes to the right company's rows; defence ingestion never overwrites gold rows | M | Either one cron that fans out per company (preferred — single OPS-02 lock per job-type), or N crons with N lock-IDs (rejected — explodes lock-ID space) |
| **Seva data preservation across migration** | Zero downtime, zero data loss for existing Seva summaries — operator must see Seva history intact after migration | M | Alembic backfill in same upward migration; tested on dev DB copy before prod |
| **Default landing company** | When user logs in, app must land on a company — first-login defaults to Seva (existing); switcher remembers last-active across sessions | S | localStorage `last_company` key checked on `/` redirect |

### DIFFERENTIATORS — Worth Considering in v3.0

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Keyboard shortcut for switcher** | Linear/Notion/Slack all ship cmd-shift-S or cmd-1/cmd-2 for instant workspace jump — saves a click for a high-frequency action | S | `Cmd+1` → Seva, `Cmd+2` → Juno; map via existing keyboard handler in `AppHeader` |
| **Visual company badge / accent strip** | Lets operator confirm at a glance which company is active — prevents "wait, am I looking at gold or defence?" mistakes | S | Small text label or 4px accent strip below header; keep amber/zinc baseline (no full per-company palette in v3.0) |
| **"Last updated" company-aware** | Existing v2.x footer/header timestamp reflects active-company's last summary, not the global most-recent | S | Already trivial once `company_id` is in queries |

### ANTI-FEATURES — Never Ship in v3.0

| Feature | Why Avoid | What to Do Instead |
|---------|-----------|-------------------|
| **Subdomain routing (juno.app, seva.app)** | Requires wildcard TLS, DNS work, Vercel config changes; zero UX benefit for a single-operator desktop tool; path-prefix is equivalent for shareability | Use path-prefix `/{company}/...` — works in any browser, no infra changes |
| **Command palette (Cmd+K) for company switching** | Heavyweight pattern (GitHub/Linear/Figma scale) for 2 companies; dropdown beats palette when N ≤ 5 | Simple dropdown next to brand-mark; revisit palette at N=4+ companies |
| **Per-company branding / color palettes** | Explicit out-of-scope in PROJECT.md ("Juno keeps the same amber/zinc baseline initially") | Keep zinc-900 + amber-500; defer branding to v3.1+ |
| **Cross-company "all companies overview"** | Explicit out-of-scope ("strict per-company isolation") — operator wears one hat at a time | Switcher is the ONLY cross-cutting surface |
| **Per-company user permissions / roles** | Single-operator model continues; no second user exists | No RBAC table, no `user_company_roles`, no permission checks |
| **Company self-signup / public onboarding** | Two-tenant tool, not a SaaS — no onboarding flow needed | Companies are seeded via migration (`INSERT INTO companies VALUES ('seva',...), ('juno',...)`); no admin UI |
| **Tenant deletion / archival UI** | Not needed at N=2 with hand-managed companies | Manual SQL if ever required; defer to v3.2+ |
| **Mobile-responsive switcher** | Desktop-only constraint preserved from v2.x | Hover/click dropdown sized for 1440×900 viewport |
| **Cross-company analytics dashboard** | Explicit out-of-scope in PROJECT.md | None — full per-company isolation |

### URL ROUTING DECISION POINT (for roadmapper discussion-phase)

Three options surveyed in the multi-tenant ecosystem:

| Pattern | Example | Pros | Cons | Verdict for v3.0 |
|---------|---------|------|------|------------------|
| **Path-prefix** | `/seva/summaries`, `/juno/summaries` | Zero infra change; deep-linkable; works on Vercel without DNS work; trivial to extract company in middleware | Slightly cluttered URLs | **RECOMMENDED** — matches Vercel-Labs multi-tenant template (custom-subpaths pattern); zero ops cost |
| **Subdomain** | `seva.app.com`, `juno.app.com` | Cleanest user-facing URL; natural tenant context | Wildcard TLS; DNS/Vercel config; SSL ops; bookmark migration for existing Seva users | **REJECTED** — infra overhead with zero UX win for single operator |
| **Query param** | `/summaries?company=seva` | Easiest to retrofit | Awkward for deep links; browsers don't isolate state by query string | **REJECTED** — feels hacky, not used by any major SaaS for tenant context |

**Recommendation:** Path-prefix `/{company}/...`. Existing routes (`/`, `/calendar`, `/sweeper`) become `/seva/`, `/seva/calendar`, `/seva/sweeper`. A bare `/` redirects to `/{last_company}/` (default `/seva/`). React Router v6 nested routes with a `:company` param at the top level.

### SWITCHER UX DECISION POINT (for roadmapper discussion-phase)

| Pattern | Example | Best at N | Verdict |
|---------|---------|-----------|---------|
| **Dropdown next to brand-mark** | Notion, Linear (top-left), Vercel | 2-8 | **RECOMMENDED** — simple, discoverable, matches `AppHeader` existing layout |
| **Sidebar icons (vertical)** | Slack, Discord | 5+ | Rejected for v3.0 — overkill at N=2; would force a sidebar where none exists |
| **Command palette (Cmd+K)** | GitHub, Figma | 10+ | Rejected for v3.0 — too heavyweight for 2 entities |
| **Segmented control / tabs** | Some dashboards | 2-3 only | Marginal — works but feels like content tabs (Tab 1/2/3 already exist); would visually conflict |

**Recommendation:** Dropdown next to brand-mark. Surgical addition to Phase-5-frozen `AppHeader.tsx`: a `<CompanySwitcher>` component placed between the brand-mark and the tabs nav. Trigger button shows current company name + chevron-down; opening reveals a list of 2 companies with check-mark on active. Cmd+1 / Cmd+2 keyboard shortcuts as a P2 nice-to-have.

---

## CATEGORY 2 — JUNO NEWS FUNNEL CONTENT

### Direct Comparison to Seva News Funnel (v2.0)

| Seva (gold) | Juno (defence) | Notes |
|-------------|----------------|-------|
| Gold News (RSS + SerpAPI) | **Defence News** (RSS + SerpAPI) | Same architecture; different feed URLs + SerpAPI queries |
| Ontario Law (SerpAPI + NRCan + Haiku filter) | **Canadian Defence Procurement** (DND + PSPC + Haiku filter) | Same architecture; Canada-specific signal |
| Ontario Stats (StatCan WDS direct poll) | **World Events Relevant to Defence** (Sonnet relevance filter — see Category 3) | DIFFERENT — no equivalent direct-poll API for defence "stats"; replaced with a curated geopolitical-relevance section |

Seva's 3-section structure (Gold News / Ontario Law / Ontario Stats) maps to Juno as (Defence News / Canadian Procurement / World Events). Same `SummaryCard` UI; same daily_summary cron pattern; same Linear amber/zinc design tokens; same XHandlePill plugin if any @handles appear.

### TABLE STAKES — Must Ship in v3.0

| Feature | Why Expected | Complexity | Dependencies on v2.x |
|---------|--------------|------------|----------------------|
| **Defence-sector RSS ingestion** | Direct analog of Seva's gold-sector RSS — without it the funnel is empty | M | feedparser already present from v2.0; only new feed URLs needed |
| **Defence-sector SerpAPI queries** | Direct analog of Seva's SerpAPI gold queries — covers what RSS misses (Bloomberg defence, niche outlets) | S | SerpAPI client already wired; new query strings only; ~$5-15/mo incremental cost inside existing $50/mo budget |
| **Sonnet daily summary for defence** | Mirrors Seva's `SUM-01..06` pattern — produces the structured 3-section card for Juno's Tab 1 | M | Same `daily_summary.py` flow; new system prompt for defence voice; ~$5-10/mo Sonnet cost |
| **Juno-scoped `daily_summary` cron** | Defence summary must fire 2x/day on the same 08:00 PT + 12:00 PT cadence as Seva (operator workflow consistency) | M | APScheduler — either fan-out from one daily_summary job per company, OR separate `juno_daily_summary` lock-id; respect OPS-02 |
| **Tab 1 renders Juno daily summary** | Live feed UI for Juno — reuses `SummaryCard`, `SectionBlock`, react-markdown + XHandlePill stack | S | Pure reuse of v2.1 Phase 5 components; only the data source changes (queried by `company_id='juno'`) |
| **30-day rolling retention for Juno** | Direct analog of Seva's 30-day prune — keeps Juno DB footprint bounded | S | Existing OPS-01 prune job extended to scope by `company_id` (or fans out per company) |

### Defence News Section — Feed Catalog

Concrete feed list assembled from research (these are the named sources to ingest, not abstract "defence news"):

| Source | URL | Coverage | Tier | Notes |
|--------|-----|----------|------|-------|
| **Janes Defence News** | janes.com/osint-insights/defence-news | Global defence intelligence — equipment, capabilities, geopolitics | T1 | Industry gold standard; structured intelligence framing |
| **Breaking Defense** | breakingdefense.com | US defence tech + policy + procurement | T1 | High-signal columnists; Pentagon-adjacent |
| **Defense News** | defensenews.com | Global politics/business/tech of defence | T1 | Senior decision-maker audience — matches Juno's analyst voice |
| **Defense One** | defenseone.com | National security futures + analysis | T1 | Long-form analysis layer |
| **DefenseScoop** | defensescoop.com | US military tech | T2 | Breaking-news tier |
| **Defense Daily** | defensedaily.com | Defence business / market intel — land/sea/air/space | T2 | Contract/business-lead density |
| **National Defense Magazine** | nationaldefensemagazine.org | NDIA — business + tech trends | T2 | Industrial-base coverage |
| **Inside Defense** | insidedefense.com | Pentagon-inside reporting | T2 | Free weekly Defense Business Briefing |
| **Defense Industry Daily** | defenseindustrydaily.com | Procurement + military systems analysis | T2 | Daily contract/program coverage |
| **Shephard Media** | shephardmedia.com | Global defence tech + business | T2 | Strong on aviation/digital-battlespace |

**Tier 1 = always ingest. Tier 2 = ingest, then Haiku-filter for signal (mirrors Seva's NRCan filter pattern).**

### Canadian Defence Procurement Section — Source Catalog

This is Juno's "Ontario Law" analog — Canada-specific procurement/policy signal:

| Source | URL Pattern | Type | Notes |
|--------|-------------|------|-------|
| **Canada.ca DND announcements** | canada.ca/en/department-national-defence/news.html | News listing (no clean RSS — scrape or SerpAPI) | DND official procurement announcements; F-35, P-8A, Defence Investment Agency news lives here |
| **Public Services and Procurement Canada (PSPC)** | canada.ca/en/public-services-procurement.html | News listing | Contract awards, RFP outcomes |
| **Canadian Defence Review** | canadiandefencereview.com/procurements-projects/ | Editorial coverage | Procurement program tracking |
| **Philippe Lagassé Substack** | philippelagasse.substack.com | Analyst commentary | Subject-matter expert; canonical Canadian defence-policy voice |
| **Atlantic Council — Canada defence briefs** | atlanticcouncil.org | Think-tank analysis | NATO/Canada strategic context |
| **SerpAPI Canadian defence queries** | (no URL — query layer) | News search | Catches Globe and Mail, National Post, CBC, CTV coverage that RSS misses |

**Filter strategy (mirrors Seva's Haiku NRCan filter):** Haiku evaluates each item with prompt "Is this Canadian defence procurement, policy, or industrial-base news? Reject consumer/lifestyle/sports content." Same architecture as Seva's Ontario-law filter — Sonnet-class judgment at Haiku price.

### Differentiator: Defence Procurement Signal Specificity

| Event Category | Why It Matters to a Defence Analyst | Source Hint |
|----------------|-----------------------------|-------------|
| **Major contract awards** ($100M+ Canadian; $1B+ global) | Industrial-base movement; supplier opportunities | Defense News + DND + PSPC |
| **Treaty signings / sanctions** | Reshape supply chains and end-customer markets | Defense One + Janes + Atlantic Council |
| **Defence-budget legislation / appropriations** | Forward-looking demand signal | National Defense Magazine + Lagassé |
| **NATO common-funding decisions** | Allied procurement convergence | nato.int + Janes |
| **Defence-tech program milestones** (F-35 delivery, F/A-XX selection, GCAP, FCAS, NGAD) | Program-of-record state | Breaking Defense + Defense News |
| **Supplier/contractor announcements** (Lockheed, BAE, Bombardier, CAE, Magellan, MDA) | Industrial-base health | Defense Daily + Defense Industry Daily |
| **Export-control actions (US ITAR/EAR, EU dual-use)** | Market access constraints | CSIS + Congress.gov + Defense One |

### Daily Summary System-Prompt Differences (Seva → Juno)

| Dimension | Seva (gold) | Juno (defence) |
|-----------|-------------|----------------|
| Voice | Senior gold analyst; Bloomberg commodities desk energy | Senior defence-industry analyst; Janes/CSIS desk energy |
| Hard prohibitions | No financial advice; no Seva mentions | No investment advice; no Juno mentions; no classified speculation; no advocacy for/against specific weapons programs |
| Output frame | Bull thesis on gold sector | Strategic landscape — what's moving, who's contracting, what supply chains shifted, what conflicts changed the demand picture |
| Specifics required | Cite ticker, price, ounce, % | Cite contract value, country, program designator, vendor, dollar amount |
| Anti-pattern | "Gold went up today" (no specifics) | "Tensions rose in [region]" (no specifics) — Sonnet must cite the event, the dollar figure, the program, the contracting authority |

### DIFFERENTIATORS — Worth Considering in v3.0

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Tier-1 vs Tier-2 source weighting** | Prioritize Janes/Defense News/Breaking Defense/Defense One over secondary outlets in summary citations | S | Tag each feed with a `tier` in config; Sonnet system prompt instructed to weight T1 sources more heavily |
| **Contract-value extraction** | Where a story names a dollar amount, surface it explicitly ("Lockheed wins $850M PAC-3 contract") | S | Sonnet prompt instruction; no NER required |
| **NATO/G7/AUKUS tag** | Flag stories where these alliance frameworks appear — high signal for Canadian-defence relevance | S | Sonnet prompt instruction; renders as small badge in `SectionBlock` |

### ANTI-FEATURES — Never Ship in v3.0

| Feature | Why Avoid | What to Do Instead |
|---------|-----------|-------------------|
| **Classified-source ingestion** | Out of scope, legally fraught, not the product | Open-source intelligence only — Janes, public news, .gov press releases |
| **Position-taking on defence policy** | Voice is analyst, not advocate; no editorial stances on weapons programs or military doctrine | Cite, don't endorse; report contract activity and strategic shifts, not opinions on whether they're good |
| **Stock-price / equity signals on defence primes** | Mirrors Seva's "no financial advice" prohibition; Juno is not a Lockheed-stock newsletter | Cover contract awards as industrial signal, not investment thesis |
| **Operational/tactical intelligence** | Out of scope; tool is strategic/industry-level | No order-of-battle, no specific unit deployments, no force posture commentary |
| **Real-time conflict updates** | The 2x-daily summary cadence is intentional; this is a digest tool, not a wire service | Roll-up format only; "today's strategic moves" not "minute-by-minute Ukraine updates" |
| **Defence-stats third section (Seva-style StatCan analog)** | No clean defence-stats API analog to StatCan WDS; defence "stats" are spread across SIPRI annual reports, GAO releases, NATO budget docs — too sparse for a daily section | Replace with World Events section (Category 3 below) |

---

## CATEGORY 3 — WORLD-EVENTS-RELEVANT-TO-DEFENCE

This is the **defining differentiator** of Juno's News Funnel vs a generic Google News defence feed. The question is: how do you filter generic world news for defence relevance without producing either (a) noise (everything is "geopolitically relevant" in some sense) or (b) too-narrow signal (only stories with "defence" in the headline)?

### The Relevance Heuristic (RECOMMENDED — for roadmap discussion-phase)

Sonnet relevance filter with explicit inclusion categories. A world-event item is "defence-relevant" if it fits any of these categories:

| Category | Examples | Why Defence-Relevant |
|----------|----------|----------------------|
| **Active armed conflict / war/peace transitions** | Ukraine offensives; Gaza developments; Sudan civil war; Taiwan Strait incidents | Direct demand-side signal for defence industrial base; reshapes treaty/alliance posture |
| **Geopolitical alignment shifts** | New mutual-defence agreements; BRICS expansion; alliance withdrawals; basing decisions | Reshapes contracting markets and export-control regimes |
| **Defence-spending policy actions** | National budget passages (US NDAA, Canadian DND vote, EU EDF allocations, NATO 2%-of-GDP commitments) | Forward demand signal; SIPRI 2024 data shows military expenditure at $2.7T, up 10th consecutive year |
| **Sanctions / export controls (defence-relevant)** | US BIS entity-list updates; EU dual-use revisions; ITAR enforcement actions; semiconductor export controls (advanced chips for hypersonic/AI weapons) | Direct market-access impact; supplier exclusions |
| **Energy / critical-mineral supply disruptions** | Strait of Hormuz incidents; rare-earth export controls (China); pipeline sabotage; uranium-supply shifts | Defence supply chains depend on critical minerals + secure energy; supply shock = procurement risk |
| **Semiconductor supply chain events** | TSMC announcements; CHIPS Act actions; ASML export controls; China SMIC progress | Modern precision weapons depend on advanced AI chips (per CSIS/RAND analysis); Taiwan disruption = US military capability impact |
| **Space-launch / orbital events with military application** | Starshield contracts; Chinese ASAT tests; reusable-launch program milestones; satellite-constellation deployments | Increasingly central to defence-tech roadmaps |
| **Hypersonic / AI / autonomy program announcements** | DARPA milestones; PLA hypersonic tests; AI-targeting program reveals | Next-generation defence-tech demand drivers |
| **Major treaty/sanctions events affecting NATO/G7/AUKUS** | New Five Eyes intel-sharing; ITAR carve-outs for AUKUS partners; Australia–Korea–Japan trilaterals | Alliance contracting and tech-transfer implications |

### The Anti-Relevance Heuristic (what Sonnet should REJECT)

| Category | Why Reject |
|----------|------------|
| **Consumer tech** unless export-controlled (chips) | iPhone launches are not defence news |
| **Sports / entertainment / celebrity** | Pure noise |
| **General finance / equities** unless defence-prime stocks during contract event | Generic market moves are not defence signal |
| **Generic domestic politics** without defence-policy linkage | Healthcare debates, immigration unless defence-recruiting linked |
| **Climate news** without defence-supply-chain or basing-impact angle | Climate matters to defence in some ways, but generic climate reports are not Juno-relevant |
| **Tech-industry news** unless export-controlled or defence-program adjacent | Most SaaS funding rounds are noise |

### TABLE STAKES — Must Ship in v3.0

| Feature | Why Expected | Complexity | Dependencies on v2.x |
|---------|--------------|------------|----------------------|
| **World-events ingestion (general news → Sonnet filter)** | The defining differentiator vs raw RSS — without the filter, the section is noise | M | Reuse SerpAPI client with broader news queries (geopolitics, conflicts, sanctions); pass through a Sonnet relevance pre-filter before inclusion |
| **Sonnet defence-relevance filter** | The intelligence layer — Haiku-or-Sonnet-class judgment on what counts as defence-relevant world news | M | Same architecture as Seva's Haiku Ontario-law filter; system prompt encoding the inclusion/exclusion categories above |
| **World Events section in daily summary** | The third section of Juno's `SummaryCard`, parallel to Seva's Ontario Stats | S | Reuse `SectionBlock`; new label + content from the relevance-filtered pool |
| **Source diversity in World Events** | A defence analyst expects coverage across Reuters/AP/FT/Bloomberg/Economist/CSIS/RUSI/Atlantic Council, not just one outlet | S | SerpAPI default already diverse; system prompt instruction to cite ≥3 sources per major item |

### DIFFERENTIATORS — Worth Considering in v3.0

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Inclusion-category tags** | Show "Why defence-relevant: [category]" inline — operator instantly sees the relevance reason | S | Sonnet emits category tag per item; render as small badge in `SectionBlock` |
| **SIPRI / NATO / IISS structured-data pulls** | Higher-signal than news scraping for spending data | L | Could add annual/quarterly SIPRI database polls; defer to v3.1+ — too sparse for daily |
| **Geographic concentration index** | At-a-glance "today's geopolitical center of gravity" — e.g. 3 of 5 items concern Indo-Pacific | M | Sonnet prompt instruction; renders as a one-line header on the section |

### ANTI-FEATURES — Never Ship in v3.0

| Feature | Why Avoid | What to Do Instead |
|---------|-----------|-------------------|
| **Live conflict map / dashboard** | Out of scope — this is a digest tool, not OSINT mapping | Cite events in prose; no maps |
| **ACLED / SIPRI live integration** | ACLED's value is structured-data API at scale; overkill for 5-item daily digest | Cite SIPRI as a source; don't ingest live |
| **Generic geopolitical news firehose** | Without the relevance filter this becomes a noisy world-news page; user can already get that elsewhere | The Sonnet filter IS the product — keep it tight |
| **Editorial / opinion takes from outlets** | Bias risk; analyst voice should be Juno's own, not borrowed | Cite factual reporting; synthesize analysis ourselves |
| **Predictive scoring ("conflict X likely to escalate")** | Quantitative geopolitical forecasting is a research discipline, not a digest feature | Report developments, don't forecast |

---

## FEATURE DEPENDENCIES (cross-category)

```
Multi-tenancy plumbing (Category 1)
    └── companies table + company_id column migration
        └──required by──> Juno News Funnel daily_summary writes (Cat 2)
        └──required by──> Tab 1 query scoping (Cat 2)
        └──required by──> 30-day prune scoped by company (Cat 2)
    └── company switcher in AppHeader
        └──required by──> User reaching Juno's Tab 1 at all
    └── URL routing /{company}/...
        └──required by──> Switcher state persistence
        └──required by──> Deep-linking back into Juno after page reload

Juno News Funnel (Category 2)
    └── defence-sector RSS + SerpAPI ingestion
        └──feeds──> Defence News section
        └──feeds──> Canadian Procurement section (with Haiku filter)
    └── World Events ingestion (broader queries)
        └──requires──> Sonnet defence-relevance filter (Cat 3)
        └──feeds──> World Events section
    └── Sonnet daily summary (Juno system prompt)
        └──requires──> all three section data pools above
        └──writes──> daily_summaries WHERE company_id='juno'
    └── Juno cron registration
        └──must respect──> OPS-02 advisory-lock uniqueness
        └──must scope writes by──> company_id='juno'

World Events relevance filter (Category 3)
    └── feeds World Events section directly
    └── parallel to Seva's Haiku NRCan filter — same architectural slot
```

---

## FEATURE PRIORITIZATION MATRIX

| Feature | User Value | Impl. Cost | Priority | Category |
|---------|------------|------------|----------|----------|
| `companies` table + `company_id` migration | HIGH | MEDIUM | P1 | Multi-tenancy |
| Company switcher in AppHeader (dropdown) | HIGH | MEDIUM | P1 | Multi-tenancy |
| URL routing `/{company}/...` | HIGH | MEDIUM | P1 | Multi-tenancy |
| Per-company API scoping (company_id in all queries) | HIGH | MEDIUM | P1 | Multi-tenancy |
| Defence-sector RSS ingestion (T1 feeds) | HIGH | MEDIUM | P1 | Juno News |
| Defence-sector SerpAPI queries | HIGH | LOW | P1 | Juno News |
| Sonnet daily summary for Juno (system prompt) | HIGH | MEDIUM | P1 | Juno News |
| Juno daily_summary cron + lock-id | HIGH | MEDIUM | P1 | Juno News |
| Tab 1 renders Juno daily summary | HIGH | LOW | P1 | Juno News |
| Sonnet defence-relevance world-events filter | HIGH | MEDIUM | P1 | World Events |
| World Events section in daily summary | HIGH | LOW | P1 | World Events |
| Canadian Procurement section (Haiku filter) | HIGH | MEDIUM | P1 | Juno News |
| 30-day prune extended to scope by company | HIGH | LOW | P1 | Multi-tenancy |
| Cmd+1 / Cmd+2 keyboard shortcuts | MEDIUM | LOW | P2 | Multi-tenancy |
| Visual company accent strip | MEDIUM | LOW | P2 | Multi-tenancy |
| T1 vs T2 source weighting | MEDIUM | LOW | P2 | Juno News |
| Inclusion-category tags on World Events items | MEDIUM | LOW | P2 | World Events |
| Contract-value extraction in summary | MEDIUM | LOW | P2 | Juno News |
| SIPRI / ACLED structured-data pulls | LOW | HIGH | P3 (v3.1+) | World Events |
| Per-company branding | LOW | MEDIUM | P3 (v3.1+) | Multi-tenancy |

---

## OPEN QUESTIONS / GAPS FOR DISCUSSION-PHASE

1. **Data-isolation strategy** — Row-level `company_id` column (simpler queries, single table) vs schema-per-company (cleaner isolation, harder migrations) vs separate tables (`juno_daily_summaries`)? PROJECT.md lists this as the hardest decision. **Research recommendation: row-level `company_id`** — matches v2.x table structure with minimal churn; backfill in single Alembic migration; SQLAlchemy queries gain a `.where(model.company_id == active_company)` clause. Schema-per-company would force duplicate Alembic histories per company.

2. **Cron topology** — One `daily_summary` job that fans out per company (preferred — single OPS-02 lock ID), or N jobs (Juno gets its own lock-id `juno_daily_summary`)? **Research recommendation: fan-out from one job** — OPS-02 lock-ID space stays small; per-company-failure semantics preserved by per-company DB writes inside the job; failure of Juno doesn't block Seva because they run in the same job sequentially with try/except scoping.

3. **DND/PSPC RSS gap** — Research confirms there is NO clean public RSS feed for DND or PSPC procurement announcements; coverage must come from Canada.ca scrape, SerpAPI, and editorial sources (Canadian Defence Review, Lagassé). Roadmapper should plan for SerpAPI-heavier Canadian-procurement ingestion than Seva's Ontario-law section.

4. **Defence "stats" section** — Seva has StatCan WDS direct-poll for monthly Ontario gold production. Defence has no equivalent daily/weekly structured-data feed. **Decision: replace third section with World Events** (per recommendation above) — this is the actual structural difference between Seva's and Juno's News Funnel. Confirm with operator during discussion-phase.

5. **Voice calibration for defence** — Seva's "Bloomberg commodities desk" voice maps to a "Janes/CSIS analyst desk" voice for Juno. System-prompt iteration during the build phase will be necessary; recommend including a voice-validation step in the Juno-side Phase 1.

6. **Switcher placement specifics** — Phase 5 froze `AppHeader.tsx`. Need surgical placement: left of tabs nav, right of brand-mark, OR below header in a sub-bar? **Research recommendation: between brand-mark and tabs nav** — matches Linear/Notion top-left placement and is the highest-visibility location without restructuring.

---

## Sources

- Linear workspace switcher (top-left dropdown pattern): https://linear.app/docs/workspaces (HIGH confidence)
- Notion workspace switcher + account dropdown: https://www.notion.com/help/create-delete-and-switch-workspaces (HIGH confidence)
- Slack workspace switcher sidebar pattern + Cmd+number shortcuts: https://slack.com/help/articles/1500002200741-Switch-between-workspaces (HIGH confidence)
- Vercel multi-tenant routing — custom subpaths via middleware: https://vercel.com/platforms/docs/multi-tenant-platforms/custom-subpaths (HIGH confidence)
- Vercel multi-tenant template (Next.js patterns): https://vercel.com/platforms/docs/examples/multi-tenant-template (HIGH confidence)
- Vercel-Labs multi-tenant preview URLs: https://github.com/vercel-labs/multi-tenant-preview-urls (MEDIUM confidence)
- Command palette UX patterns + when-to-use: https://medium.com/design-bootcamp/command-palette-ux-patterns-1-d6b6e68f30c1 (MEDIUM confidence)
- Multi-tenant SaaS routing tradeoffs (subdomain vs path-prefix vs query): https://workos.com/blog/developers-guide-saas-multi-tenant-architecture (MEDIUM confidence)
- Multi-tenant routing strategies on AWS: https://aws.amazon.com/blogs/networking-and-content-delivery/tenant-routing-strategies-for-saas-applications-on-aws/ (MEDIUM confidence)
- Janes Defence News: https://www.janes.com/osint-insights/defence-news (HIGH confidence)
- Breaking Defense: https://breakingdefense.com/ (HIGH confidence)
- Defense News: https://www.defensenews.com/ (HIGH confidence)
- Defense One: https://www.defenseone.com/ (HIGH confidence)
- DefenseScoop: https://defensescoop.com/ (MEDIUM confidence)
- Defense Daily: https://www.defensedaily.com/ (MEDIUM confidence)
- National Defense Magazine (NDIA): https://www.nationaldefensemagazine.org/ (MEDIUM confidence)
- Inside Defense: https://insidedefense.com/ (MEDIUM confidence)
- Defense Industry Daily: https://www.defenseindustrydaily.com/ (MEDIUM confidence)
- Canada DND F-35 + P-8A procurement context: https://canadiandefencereview.com/procurements-projects/ (MEDIUM confidence)
- 2026-27 DND Departmental Plan ($50B+ allocation): https://www.canada.ca/en/department-national-defence/corporate/reports-publications/departmental-plans/departmental-plan-2026-27.html (HIGH confidence)
- Philippe Lagassé Substack (Canadian defence analyst): https://philippelagasse.substack.com/ (MEDIUM confidence)
- NATO July 2025 procurement-policy update: https://www.nato.int/en/news-and-events/articles/news/2025/07/22/nato-allies-agree-new-procurement-policy (HIGH confidence)
- Atlantic Council on Canadian defence + NATO Hague commitments: https://www.atlanticcouncil.org/in-depth-research-reports/issue-brief/how-to-equip-canadas-defense-industrial-base-to-meet-natos-hague-summit-commitments/ (MEDIUM confidence)
- SIPRI 2024 military expenditure ($2.7T, 10th consecutive year of growth): https://www.sipri.org/media/press-release/2026/global-military-spending-rise-continues-european-and-asian-expenditures-surge (HIGH confidence)
- SIPRI Military Expenditure Database: https://www.sipri.org/databases (HIGH confidence)
- ACLED conflict-event tracking (context only — not for daily ingestion): https://libguides.princeton.edu/politics/conflict (MEDIUM confidence)
- CSIS on AI/semiconductor export controls + national security: https://www.csis.org/analysis/blocking-chinas-access-ai-chips-matters-us-national-security (HIGH confidence)
- CSIS on China's defence-tech pursuit + export-control implications: https://www.csis.org/analysis/chinas-pursuit-defense-technologies-implications-us-and-multilateral-export-control-and (HIGH confidence)
- RAND on advanced chips + national security: https://www.rand.org/pubs/commentary/2025/02/dont-be-fooled-advanced-chips-are-important-for-national.html (HIGH confidence)
- Shephard Media on China's use of US AI chips for hypersonic weapon engines: https://www.shephardmedia.com/news/digital-battlespace/china-turns-to-us-made-ai-chips-to-boost-hypersonic-weapon-performance/ (MEDIUM confidence)
- US Congress.gov on advanced semiconductor export controls (CRS R48642): https://www.congress.gov/crs-product/R48642 (HIGH confidence)
- IBISWorld on US-China tech competition + global defence: https://www.ibisworld.com/blog/us-china-tech-war/1/1126/ (MEDIUM confidence)
