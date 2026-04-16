# Requirements: Seva Mining AI Social Media Agency

**Defined:** 2026-03-30
**Core Value:** Every piece of content the system drafts must be genuinely valuable to the gold conversation it enters — a data point, an insight, a connection no one else made.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Infrastructure

- [x] **INFRA-01**: PostgreSQL database with full schema deployed on Neon (6 tables: draft_items, content_bundles, agent_runs, daily_digests, watchlists, keywords)
- [x] **INFRA-02**: Indexes on status, platform, created_at, expires_at columns for query performance
- [x] **INFRA-03**: FastAPI backend deployed on Railway with all API endpoints operational
- [x] **INFRA-04**: Separate scheduler worker process deployed as second Railway service
- [x] **INFRA-05**: APScheduler with AsyncIOScheduler and database-level job lock to prevent duplicate runs during zero-downtime deploys
- [x] **INFRA-06**: Alembic migration system for schema versioning
- [x] **INFRA-07**: Neon connection pooling configured (pool_pre_ping=True, pool_recycle=300, PgBouncer transaction-mode)
- [x] **INFRA-08**: Environment variable configuration for all external service credentials
- [x] **INFRA-09**: Health check endpoints for Railway monitoring

### Authentication

- [x] **AUTH-01**: Operator can log in with a password on the dashboard
- [x] **AUTH-02**: Session persists across browser refresh (JWT token)
- [x] **AUTH-03**: Unauthenticated requests to dashboard and API are rejected

### Twitter Agent

- [x] **TWIT-01**: Agent monitors X via Basic API using configurable cashtags, hashtags, and natural language keywords every 2 hours
- [x] **TWIT-02**: Agent scores posts on engagement (40%), account authority (30%), and topic relevance (30%)
- [x] **TWIT-03**: Engagement formula: likes x1 + retweets x2 + replies x1.5
- [x] **TWIT-04**: Minimum engagement gate: 500+ likes OR watchlist account with 50+ likes
- [x] **TWIT-05**: Recency decay: full score under 1h, 50% at 4h, expired at 6h
- [x] **TWIT-06**: Top 3-5 qualifying posts per run passed to drafting
- [x] **TWIT-07**: Agent drafts both a reply comment AND a retweet-with-comment for each qualifying post
- [x] **TWIT-08**: Agent produces 2-3 alternative drafts per response type
- [x] **TWIT-09**: Each draft evaluated against quality rubric (relevance, originality, tone match, no company mention, no financial advice) before queuing
- [x] **TWIT-10**: Separate Claude compliance-checker call validates no Seva Mining mention and no financial advice in every draft
- [x] **TWIT-11**: Monthly X API quota counter tracks tweet reads against 10,000/month cap
- [x] **TWIT-12**: Hard-stop logic prevents API calls when quota approaches limit (configurable safety margin)
- [x] **TWIT-13**: Dashboard displays current quota usage and alerts when quota is low
- [x] **TWIT-14**: All drafts sent to Senior Agent with rationale explaining why this post matters and what angle the draft takes

### Instagram Agent

- [x] **INST-01**: Agent monitors Instagram via Apify scraper using configurable hashtags and account watchlist every 4 hours
- [x] **INST-02**: Agent scores posts: likes x1 + comment count x2 + normalized follower count x1.5
- [x] **INST-03**: Minimum engagement gate: 200+ likes from last 8 hours
- [x] **INST-04**: Top 3 posts per run passed to drafting
- [x] **INST-05**: Agent drafts 2-3 alternative comments per qualifying post (1-2 sentences each)
- [x] **INST-06**: No hashtags in any drafted comment, ever
- [x] **INST-07**: Each draft evaluated against quality rubric before queuing
- [x] **INST-08**: Separate Claude compliance-checker call on every draft
- [x] **INST-09**: Retry logic for Apify scraping failures with exponential backoff
- [x] **INST-10**: Scraper health monitoring: detect silent failures (HTTP 200 with empty results) by comparing against baseline expected volume
- [x] **INST-11**: Scraper failure alerts surfaced in agent run logs and WhatsApp if critical
- [x] **INST-12**: Items expire after 12 hours

### Content Agent

- [x] **CONT-01**: Agent runs daily at 6am, pulling new content from all sources since last run
- [x] **CONT-02**: RSS ingestion from Kitco News, Mining.com, Junior Mining Network, World Gold Council blog
- [x] **CONT-03**: SerpAPI news search with gold-sector keywords ("gold exploration", "gold price", "central bank gold", "gold ETF", "junior miners", "gold reserves")
- [x] **CONT-04**: Deduplication by URL and headline similarity (fuzzy match, 85% threshold)
- [x] **CONT-05**: Story scoring on relevance to gold/mining (40%), recency (30%), engagement signal (30%)
- [x] **CONT-06**: Quality threshold: only the single highest-scoring story above 7.0/10 is selected
- [x] **CONT-07**: "No story today" flag sent to Senior Agent if nothing clears the threshold
- [x] **CONT-08**: Deep research pass on selected story: pull full article, find 2-3 corroborating sources via web search, extract key data points
- [x] **CONT-09**: Format decision logic: long-form article (600-900 words) for complex/data stories, short post/thread for fast-moving news, infographic brief for data-heavy visual stories
- [x] **CONT-10**: Thread format drafted as both a tweet thread (3-5 tweets, each under 280 chars) AND a single long-form X post
- [x] **CONT-11**: Infographic brief includes headline, 5-8 key stats with sources, suggested visual structure, and full caption text
- [x] **CONT-12**: Infographic generation using HTML templates for data-heavy pieces and AI image generation for creative/editorial pieces
- [x] **CONT-13**: All content drafted in senior analyst voice — data-driven, measured, cites specifics
- [x] **CONT-14**: No mention of Seva Mining in any content
- [x] **CONT-15**: No financial advice in any content
- [x] **CONT-16**: Separate Claude compliance-checker call on all content
- [x] **CONT-17**: Content packaged with all sources and credibility score, sent to Senior Agent

### Senior Agent

- [x] **SENR-01**: Receives all drafts from sub-agents as they arrive
- [x] **SENR-02**: Deduplicates across agents — same story surfaces as separate cards per platform, visually linked as "related"
- [x] **SENR-03**: Prioritizes queue: Twitter time-sensitive first, breaking news content second, Instagram third, evergreen last
- [x] **SENR-04**: Hard cap of 15 items in queue — lower-scoring items displaced by higher-scoring new items when full
- [x] **SENR-05**: Auto-expires items after platform window (Twitter: 6h, Instagram: 12h)
- [x] **SENR-06**: Assembles morning digest daily at 8am
- [x] **SENR-07**: Morning digest contains: top 5 gold sector stories (one sentence each), queue snapshot by platform, yesterday's approved/rejected/expired counts, scraped surface metrics on @sevamining posts, single highest-value queue item
- [x] **SENR-08**: Logs every approval and rejection with reason tags
- [x] **SENR-09**: Expiry processor runs every 30 minutes to sweep stale items

### Approval Dashboard

- [ ] **DASH-01**: Separate tabs for Twitter, Instagram, and Content
- [ ] **DASH-02**: Feed/timeline layout sorted by urgency within each tab
- [ ] **DASH-03**: Each approval card shows: platform badge, original post URL and text excerpt, account name/follower count/why they matter, all draft alternatives (2-3 options for replies/comments, reply + RT for Twitter), rationale, urgency indicator, final score
- [ ] **DASH-04**: Three action buttons per card: Approve, Edit + Approve, Reject (rejection reason required)
- [ ] **DASH-05**: Inline editing of draft text directly on the card
- [ ] **DASH-06**: One-click copy to clipboard of approved/edited draft text with toast confirmation
- [ ] **DASH-07**: Direct link to original post opens in new tab
- [x] **DASH-08**: Related cards (same story across platforms) visually linked
- [ ] **DASH-09**: Desktop-only layout (no mobile responsiveness required)
- [ ] **DASH-10**: Clean minimal design — Linear/Notion aesthetic, content-focused, lots of white space

### Daily Digest View

- [x] **DGST-01**: Dashboard page renders today's morning digest cleanly
- [x] **DGST-02**: Shows top 5 gold sector stories, queue snapshot, yesterday's summary, priority alert
- [x] **DGST-03**: Historical digests viewable

### Content Review

- [x] **CREV-01**: Dashboard page for today's content bundle
- [x] **CREV-02**: Full draft displayed with format choice and rationale
- [x] **CREV-03**: All sources listed with links
- [x] **CREV-04**: Infographic preview when applicable
- [x] **CREV-05**: Approve to queue for posting
- [x] **CREV-06**: Content detail modal displays full structured brief for all content formats (infographic, thread, long_form, breaking_news, quote, video_clip) with format-aware rendering
- [x] **CREV-07**: Infographic and quote ContentBundles automatically generate AI-rendered images (4 and 2 respectively) stored in Cloudflare R2
- [x] **CREV-08**: Rendered images appear in the Content detail modal with skeleton+poll UX and graceful fallback on render failure
- [x] **CREV-09**: Operator can trigger a fresh image render via a "Regenerate images" button in the modal
- [x] **CREV-10**: Image rendering runs as a background job independent of the Content Agent cron; failures do not block bundle persistence or approval

### WhatsApp Notifications

- [x] **WHAT-01**: Morning digest sent to operator's WhatsApp daily at 8am via Twilio
- [x] **WHAT-02**: Breaking gold news alert sent when a high-scoring story is detected
- [x] **WHAT-03**: High-value draft expiry alert sent when a top-scored item is approaching expiration without review
- [ ] **WHAT-04**: All WhatsApp messages use Meta-approved message templates (submitted early in build)
- [x] **WHAT-05**: Notifications include link to dashboard for action

### Settings

- [x] **SETT-01**: Watchlist management for X (add/remove accounts, set relationship value 1-5, notes)
- [x] **SETT-02**: Watchlist management for Instagram (add/remove accounts, set follower threshold)
- [x] **SETT-03**: Keyword management (add/remove keywords, adjust weights, toggle active, filter by platform)
- [x] **SETT-04**: Scoring parameter configuration (all weights, thresholds, decay curves editable)
- [x] **SETT-05**: Agent run log display (last 7 days, filterable by agent)
- [x] **SETT-06**: Notification preferences (WhatsApp timing, alert thresholds)
- [x] **SETT-07**: Agent schedule configuration (change run intervals for each agent)
- [x] **SETT-08**: X API quota usage display with visual indicator

### Agent Execution

- [x] **EXEC-01**: Every agent run logged: agent name, start/end time, items found, items queued, items filtered, errors
- [x] **EXEC-02**: Agents read scoring settings from database at start of each run (no cached config)
- [x] **EXEC-03**: All agent functions are async (AsyncAnthropic + AsyncIOScheduler)
- [x] **EXEC-04**: Graceful error handling — agent failures logged and alerted, do not crash the worker process

## v1.x Requirements

Deferred to post-launch. Tracked but not in current roadmap.

### Event Mode

- **EVNT-01**: Event mode triggers on engagement spike (3x+ normal baseline) OR significant gold price movement
- **EVNT-02**: In event mode, Twitter Agent scales output to 8-10 posts per run
- **EVNT-03**: Queue hard cap temporarily expands during event windows
- **EVNT-04**: Event mode configurable from dashboard

### Learning Loop

- **LERN-01**: Senior Agent tracks rejection patterns over time by content type and angle
- **LERN-02**: System analyzes what content is getting the most engagement online in the gold sector
- **LERN-03**: After consistent rejections, system updates agent scoring thresholds
- **LERN-04**: Monthly summary: content angles approved most, platform performance comparison

### Deduplication Enhancements

- **DDUP-01**: Cross-platform story fingerprinting via semantic similarity for visual linking refinement

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Auto-posting to any platform | Brand risk in gold/finance sector; one bad auto-post damages credibility for months. The product's value is the human judgment layer. |
| LinkedIn agent | LinkedIn API is restrictive/expensive; gold sector conversation is lower-signal than X. Add only if X + IG prove insufficient. |
| Reddit monitoring | API restrictions post-2023. SerpAPI already captures Reddit-sourced stories once they reach mainstream coverage. |
| Multi-tenancy | Premature optimization. Refactor when second client exists. |
| Mobile-responsive dashboard | Single-user desktop workflow. WhatsApp covers mobile alerts. |
| Analytics dashboard | Requires enough historical data for trends. All data retained — add in v2. |
| Two-way WhatsApp (approve via chat) | Significant backend complexity for marginal time savings. Dashboard handles all actions. |
| Real-time streaming monitoring | X Basic API doesn't support streaming. Polling at 2h/4h is appropriate for 1-person review workflow. |
| Sentiment analytics | Engagement + topic relevance scoring already proxies for this. Add only if a clear decision depends on it. |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| INFRA-01 | Phase 1 | Complete |
| INFRA-02 | Phase 1 | Complete |
| INFRA-03 | Phase 1 | Complete |
| INFRA-04 | Phase 1 | Complete |
| INFRA-05 | Phase 1 | Complete |
| INFRA-06 | Phase 1 | Complete |
| INFRA-07 | Phase 1 | Complete |
| INFRA-08 | Phase 1 | Complete |
| INFRA-09 | Phase 1 | Complete |
| WHAT-04 | Phase 1 | Pending |
| EXEC-03 | Phase 1 | Complete |
| EXEC-04 | Phase 1 | Complete |
| AUTH-01 | Phase 2 | Complete |
| AUTH-02 | Phase 2 | Complete |
| AUTH-03 | Phase 2 | Complete |
| EXEC-01 | Phase 2 | Complete |
| DASH-01 | Phase 3 | Pending |
| DASH-02 | Phase 3 | Pending |
| DASH-03 | Phase 3 | Pending |
| DASH-04 | Phase 3 | Pending |
| DASH-05 | Phase 3 | Pending |
| DASH-06 | Phase 3 | Pending |
| DASH-07 | Phase 3 | Pending |
| DASH-08 | Phase 3 | Complete |
| DASH-09 | Phase 3 | Pending |
| DASH-10 | Phase 3 | Pending |
| TWIT-01 | Phase 4 | Complete |
| TWIT-02 | Phase 4 | Complete |
| TWIT-03 | Phase 4 | Complete |
| TWIT-04 | Phase 4 | Complete |
| TWIT-05 | Phase 4 | Complete |
| TWIT-06 | Phase 4 | Complete |
| TWIT-07 | Phase 4 | Complete |
| TWIT-08 | Phase 4 | Complete |
| TWIT-09 | Phase 4 | Complete |
| TWIT-10 | Phase 4 | Complete |
| TWIT-11 | Phase 4 | Complete |
| TWIT-12 | Phase 4 | Complete |
| TWIT-13 | Phase 4 | Complete |
| TWIT-14 | Phase 4 | Complete |
| SENR-01 | Phase 5 | Complete |
| SENR-02 | Phase 5 | Complete |
| SENR-03 | Phase 5 | Complete |
| SENR-04 | Phase 5 | Complete |
| SENR-05 | Phase 5 | Complete |
| SENR-06 | Phase 5 | Complete |
| SENR-07 | Phase 5 | Complete |
| SENR-08 | Phase 5 | Complete |
| SENR-09 | Phase 5 | Complete |
| WHAT-01 | Phase 5 | Complete |
| WHAT-02 | Phase 5 | Complete |
| WHAT-03 | Phase 5 | Complete |
| WHAT-05 | Phase 5 | Complete |
| INST-01 | Phase 6 | Complete |
| INST-02 | Phase 6 | Complete |
| INST-03 | Phase 6 | Complete |
| INST-04 | Phase 6 | Complete |
| INST-05 | Phase 6 | Complete |
| INST-06 | Phase 6 | Complete |
| INST-07 | Phase 6 | Complete |
| INST-08 | Phase 6 | Complete |
| INST-09 | Phase 6 | Complete |
| INST-10 | Phase 6 | Complete |
| INST-11 | Phase 6 | Complete |
| INST-12 | Phase 6 | Complete |
| CONT-01 | Phase 7 | Complete |
| CONT-02 | Phase 7 | Complete |
| CONT-03 | Phase 7 | Complete |
| CONT-04 | Phase 7 | Complete |
| CONT-05 | Phase 7 | Complete |
| CONT-06 | Phase 7 | Complete |
| CONT-07 | Phase 7 | Complete |
| CONT-08 | Phase 7 | Complete |
| CONT-09 | Phase 7 | Complete |
| CONT-10 | Phase 7 | Complete |
| CONT-11 | Phase 7 | Complete |
| CONT-12 | Phase 7 | Complete |
| CONT-13 | Phase 7 | Complete |
| CONT-14 | Phase 7 | Complete |
| CONT-15 | Phase 7 | Complete |
| CONT-16 | Phase 7 | Complete |
| CONT-17 | Phase 7 | Complete |
| DGST-01 | Phase 8 | Complete |
| DGST-02 | Phase 8 | Complete |
| DGST-03 | Phase 8 | Complete |
| CREV-01 | Phase 8 | Complete |
| CREV-02 | Phase 8 | Complete |
| CREV-03 | Phase 8 | Complete |
| CREV-04 | Phase 8 | Complete |
| CREV-05 | Phase 8 | Complete |
| CREV-06 | Phase 11 | Complete |
| CREV-07 | Phase 11 | Complete |
| CREV-08 | Phase 11 | Complete |
| CREV-09 | Phase 11 | Complete |
| CREV-10 | Phase 11 | Complete |
| SETT-01 | Phase 8 | Complete |
| SETT-02 | Phase 8 | Complete |
| SETT-03 | Phase 8 | Complete |
| SETT-04 | Phase 8 | Complete |
| SETT-05 | Phase 8 | Complete |
| SETT-06 | Phase 8 | Complete |
| SETT-07 | Phase 8 | Complete |
| SETT-08 | Phase 8 | Complete |
| EXEC-02 | Phase 9 | Complete |

**Coverage:**
- v1 requirements: 104 total (note: REQUIREMENTS.md previously stated 78 — actual count from requirement IDs is 99; Phase 11 adds 5 new CREV requirements)
- Mapped to phases: 104
- Unmapped: 0

---
*Requirements defined: 2026-03-30*
*Last updated: 2026-03-30 after roadmap creation*
