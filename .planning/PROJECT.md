# Seva Mining — AI Social Media Agency

## What This Is

A 2x-daily AI gold-intelligence digest. Twice a day (08:00 PT + 12:00 PT) a cron job ingests gold-sector news, Ontario/Canadian mining-favourable legislation, and Ontario gold-production statistics; produces a structured 3-section summary card; persists it to Postgres; surfaces it on a web feed at `/` for the operator to read; and delivers a teaser via WhatsApp with a link back to the feed. 30-day rolling retention. No drafting, no approval flow, no posting.

(Originally designed as a 6-sub-agent approval-dashboard product; pivoted to the digest model in v2.0 — see Evolution.)

## Core Value

Every piece of intelligence the digest surfaces must be genuinely useful to a senior gold analyst — a data point, an insight, a connection no one else made. If a bullet wouldn't make that analyst stop scrolling, it shouldn't be in the summary.

## Current Milestone: v3.0 Multi-Tenant Dashboards — Juno Industries Onboarding

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
*Last updated: 2026-05-19 — Milestone v3.0 initiated. Multi-tenant pivot: single-tenant Seva dashboard becomes a multi-tenant platform onboarding Juno Industries (defence tech, Canada) starting with the News Funnel. v2.1 complete (3-tab content engine + Linear UI + dead-code strip); v3.0 carries that surface forward and adds a company switcher.*
