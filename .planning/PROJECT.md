# Seva Mining — AI Social Media Agency

## What This Is

A four-agent AI system that monitors the gold sector on X (Twitter) and Instagram 24/7, drafts engagement content, and surfaces everything to a web dashboard for manual approval. The system handles research, scoring, and drafting — you review, approve, copy, and post. Nothing is ever posted automatically. The Senior Agent sends daily digests and alerts via WhatsApp.

## Core Value

Every piece of content the system drafts must be genuinely valuable to the gold conversation it enters — a data point, an insight, a connection no one else made. If a draft wouldn't make a senior gold analyst stop scrolling, it shouldn't exist.

## Requirements

### Validated

- Validated in Phase 8: DigestPage daily digest with prev/next navigation (DGST-01..03)
- Validated in Phase 8: ContentPage content review with format-specific rendering and approve flow (CREV-01..05)
- Validated in Phase 8: SettingsPage with 6 tabs — Watchlists, Keywords, Scoring, Notifications, Agent Runs, Schedule (SETT-01..08)
- Validated in Phase 9: All agent engagement gate thresholds and schedule intervals DB-driven — tunable from Settings without a deploy (EXEC-02)

### Active

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
*Last updated: 2026-04-06 after Phase 9 completion*
