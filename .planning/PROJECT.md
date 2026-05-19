# Seva Mining — AI Social Media Agency

## What This Is

A 2x-daily AI gold-intelligence digest. Twice a day (08:00 PT + 12:00 PT) a cron job ingests gold-sector news, Ontario/Canadian mining-favourable legislation, and Ontario gold-production statistics; produces a structured 3-section summary card; persists it to Postgres; surfaces it on a web feed at `/` for the operator to read; and delivers a teaser via WhatsApp with a link back to the feed. 30-day rolling retention. No drafting, no approval flow, no posting.

(Originally designed as a 6-sub-agent approval-dashboard product; pivoted to the digest model in v2.0 — see Evolution.)

## Core Value

Every piece of intelligence the digest surfaces must be genuinely useful to a senior gold analyst — a data point, an insight, a connection no one else made. If a bullet wouldn't make that analyst stop scrolling, it shouldn't be in the summary.

## Current Milestone: v2.1 Three-Tab Content Engine + UI Polish

**Goal:** Expand the v2.0 daily summary feed (a single-page product surface) into a 3-tab content engine: (1) News Funnel — the existing feed, becomes Tab 1 unchanged; (2) Content Calendar — a simple personal planning surface for content ideas; (3) Weekly Viral Sweeper — surfaces what's getting traction in the gold/mining sector via Reddit + story virality. Layer in a Linear-style UI redesign with amber-gold accents.

**Target features:**
- **Tab 1 — News Funnel:** Existing daily summary feed becomes the first tab in the new navigation. Content unchanged. Label: "News Funnel".
- **Tab 2 — Content Calendar:** Weekly grid view, plan items with title + optional markdown notes + tag/category. Click-to-edit, drag-or-dropdown reschedule. New `calendar_items` DB table + REST CRUD endpoints. Optimistic UI via TanStack Query. **NO AI drafting, NO autoposting, NO scheduled cron triggers** — pure personal planning surface.
- **Tab 3 — Weekly Viral Sweeper:** Sunday-morning cron (08:00 PT) ingests top Reddit posts (r/gold, r/Wallstreetsilver, r/silverbugs, etc. via `praw`) AND computes story virality from the existing news pipeline (count cross-references across feeds over past 7 days). Produces a weekly card with three sections: top Reddit posts, top viral stories, and 3 Sonnet-authored content angle suggestions. New `weekly_sweeps` DB table.
- **UI redesign:** Linear-style modern SaaS aesthetic. Dark theme preserved, amber-gold accents (Tailwind `amber-500`), top tab navigation via shadcn `Tabs` primitive, refined Inter typography, generous whitespace, subtle borders + hover states.

**Budget:** $0 incremental — Reddit API is free (praw + read-only public access via OAuth client credentials), no X API revival, no new paid integrations. Total monthly cost stays ~$200.

**Stack additions:**
- `praw` ~7.x (Python Reddit API Wrapper) — backend
- `shadcn Tabs` component (Radix UI Tabs primitive on Tailwind v4 branch) — frontend
- `@dnd-kit/core` for drag-and-drop OR date-dropdown fallback (research-determined)
- 3 new env vars: `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USER_AGENT`

**Hard parts the roadmap addresses:**
1. **Reddit API auth.** User creates a Reddit app at reddit.com/prefs/apps; stores client_id/secret in Railway env. Same setup pattern as SerpAPI/Twilio.
2. **Drag-and-drop complexity.** Real DnD in a calendar grid is more code than it looks. Research evaluates `@dnd-kit/core` vs date-dropdown fallback — let the planner decide based on risk.
3. **Story virality compute.** URL-similarity dedup (SequenceMatcher 0.85 threshold per existing content_agent pattern) over `daily_summaries.raw_sources_jsonb.gold_news[].link` for the past 7 days. Heaviest piece of sweeper logic.
4. **Sonnet "3 content angles" generation.** Single weekly Sonnet call combining Reddit + virality inputs.
5. **UI migration.** Restructure App.tsx routes: `/` becomes the tabbed layout; legacy redirects from v2.0 must be preserved.

**Out of scope (explicit exclusions for v2.1):**
- AI content drafting (v1.0 sub-agents stay retired)
- Autoposting to X / IG / LinkedIn (Phase B stays dormant)
- Instagram / LinkedIn integration
- Live macro stat indicators (FRED API — deferred to v2.2)
- Kitco scraping (deferred to v2.2)
- Mobile-responsive UI (desktop-only constraint preserved)
- WhatsApp ping for calendar items (deferred to v2.2)

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
*Last updated: 2026-05-19 — Phase 7 (Weekly Viral Sweeper) shipped with X-API pivot (Reddit dropped, tweepy reused). v2.1 progress: 3/4 phases complete (5, 6, 7); Phase 8 UI Polish + Dead-Code Strip remains.*
