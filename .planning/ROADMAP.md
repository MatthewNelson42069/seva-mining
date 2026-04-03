# Roadmap: Seva Mining AI Social Media Agency

## Overview

Build a four-agent AI monitoring and drafting system from the ground up. The dependency graph dictates the build order: database schema and infrastructure first (everything depends on it), then the FastAPI backend, then the React approval dashboard (human workflow must be testable before agents run), then agents in ascending complexity (Twitter Agent first — simplest pipeline — then Senior Agent core to manage the queue before adding more agents, then Instagram Agent, then Content Agent — most complex). Dashboard views for digest and content review, and full Settings configurability, are wired last once agents are producing verified output.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Infrastructure and Foundation** - Full database schema on Neon, Alembic migrations, two Railway services configured, APScheduler worker skeleton with DB job lock, Twilio WhatsApp template submission
- [ ] **Phase 2: FastAPI Backend** - Password auth (bcrypt + JWT), all REST endpoints, state machine transition enforcement, Twilio outbound notification service
- [ ] **Phase 3: React Approval Dashboard** - Tabbed approval interface, approval cards with full context and inline editing, approve/edit+approve/reject actions, copy-to-clipboard, direct source links
- [x] **Phase 4: Twitter Agent** - X API v2 monitoring, engagement scoring with recency decay, dual-format drafting with compliance checker, monthly quota counter with hard-stop logic (completed 2026-04-02)
- [ ] **Phase 5: Senior Agent Core** - Story fingerprint deduplication, 15-item queue cap, auto-expiry sweep, WhatsApp morning digest and alert dispatch
- [ ] **Phase 6: Instagram Agent** - Apify scraper integration, per-hashtag baseline tracking, retry/health logic, comment draft alternatives with compliance checker
- [ ] **Phase 7: Content Agent** - RSS and SerpAPI ingest, multi-step deep research, format decision logic, quality threshold with no-story flag, compliance checker
- [ ] **Phase 8: Dashboard Views and Digest** - Daily digest view, content review page, full Settings page wired to live DB config
- [ ] **Phase 9: Agent Execution Polish** - All scoring weights DB-driven and configurable, agent schedule config from Settings, run logs, quota display, graceful failure handling

## Phase Details

### Phase 1: Infrastructure and Foundation
**Goal**: The project infrastructure is fully deployed — database schema applied, both Railway services running and connected, APScheduler skeleton with DB job lock operational, and Twilio WhatsApp templates submitted for Meta approval
**Depends on**: Nothing (first phase)
**Requirements**: INFRA-01, INFRA-02, INFRA-03, INFRA-04, INFRA-05, INFRA-06, INFRA-07, INFRA-08, INFRA-09, WHAT-04, EXEC-03, EXEC-04
**Success Criteria** (what must be TRUE):
  1. Running `alembic upgrade head` against the Neon database creates all 6 tables with correct columns, indexes, and the draft state enum without errors
  2. Both Railway services (API and scheduler worker) deploy from the repo, pass their health check endpoints, and connect to the Neon database
  3. APScheduler worker starts and acquires the DB job lock; a second instance cannot acquire the same lock simultaneously
  4. All external service credentials load from environment variables and the app starts without any hard-coded secrets
  5. Twilio WhatsApp message templates for morning digest, breaking news, and expiry alert are submitted to Meta for approval
**Plans**: 7 plans

Plans:
- [x] 01-01-PLAN.md — Twilio WhatsApp template submission (WHAT-04)
- [x] 01-02-PLAN.md — Dev environment setup + test scaffolding (Wave 0)
- [x] 01-03-PLAN.md — pydantic-settings config, SQLAlchemy async engine, all 6 models
- [x] 01-04-PLAN.md — Alembic async init, initial schema migration, apply to Neon
- [ ] 01-05-PLAN.md — FastAPI backend skeleton, /health endpoint, Railway config
- [ ] 01-06-PLAN.md — APScheduler worker skeleton, advisory lock, Railway config
- [ ] 01-07-PLAN.md — Railway deployment verification, .env.example

### Phase 2: FastAPI Backend
**Goal**: The API server handles authenticated requests, enforces the draft state machine with correct transitions, and can trigger outbound WhatsApp notifications — giving the dashboard a complete interface to work against before agents run
**Depends on**: Phase 1
**Requirements**: AUTH-01, AUTH-02, AUTH-03, EXEC-01
**Success Criteria** (what must be TRUE):
  1. Operator logs in with the correct password and receives a JWT token; all protected API endpoints return 401 for requests without a valid token
  2. Session persists across browser refresh without re-login until the JWT expires
  3. Draft status transitions are enforced: pending can move to approved, edited_approved, or rejected (with mandatory reason); invalid transitions return an error
  4. Twilio outbound notification service sends a WhatsApp message to the configured number when called programmatically
**Plans**: 4 plans

Plans:
- [x] 02-01-PLAN.md — Dependencies, auth system (bcrypt + JWT), Pydantic schemas, edit_delta migration, auth tests
- [x] 02-02-PLAN.md — Queue endpoints with state machine enforcement (approve/reject/edit)
- [x] 02-03-PLAN.md — Supporting CRUD endpoints (watchlists, keywords, agent-runs, digests, content)
- [ ] 02-04-PLAN.md — WhatsApp notification service (Twilio templates), full test suite verification

### Phase 3: React Approval Dashboard
**Goal**: Operator can review, edit, approve, and reject draft cards on a tabbed dashboard using seeded mock data — the entire human review workflow is verified and polished before any agent produces real output
**Depends on**: Phase 2
**Requirements**: DASH-01, DASH-02, DASH-03, DASH-04, DASH-05, DASH-06, DASH-07, DASH-08, DASH-09, DASH-10
**Success Criteria** (what must be TRUE):
  1. Operator navigates between Twitter, Instagram, and Content tabs; cards within each tab are sorted by urgency
  2. Each approval card shows the platform badge, original post excerpt and URL, account info, all draft alternatives, rationale, urgency indicator, and final score without any expand click
  3. Operator can edit draft text inline on the card, then approve, edit+approve, or reject; rejection requires a reason; the card clears on any action
  4. One click copies the approved or edited draft text to clipboard with a toast confirmation; the source post link opens in a new tab
  5. Related cards sharing the same story across platforms are visually linked on the dashboard
**Plans**: 5 plans
**UI hint**: yes

Plans:
- [x] 03-01-PLAN.md — Bootstrap Vite + React 19 + Tailwind v4 + shadcn/ui, TypeScript types, API client, test infra, CORS fix
- [x] 03-02-PLAN.md — Zustand store, TanStack Query hooks, ApprovalCard component with draft tabs, inline editor, reject panel
- [x] 03-03-PLAN.md — Login page, auth flow, AppShell layout, sidebar, platform tabs, routing, page stubs
- [ ] 03-04-PLAN.md — QueuePage wiring, content modal, related badges, empty state, database seed script
- [ ] 03-05-PLAN.md — Human verification of complete approval dashboard (checkpoint)

### Phase 4: Twitter Agent
**Goal**: The Twitter Agent runs on schedule, fetches qualifying gold-sector posts, scores them, drafts dual-format alternatives with a separate compliance checker, and delivers items to the dashboard — with monthly quota tracking and hard-stop logic running from day one
**Depends on**: Phase 3
**Requirements**: TWIT-01, TWIT-02, TWIT-03, TWIT-04, TWIT-05, TWIT-06, TWIT-07, TWIT-08, TWIT-09, TWIT-10, TWIT-11, TWIT-12, TWIT-13, TWIT-14
**Success Criteria** (what must be TRUE):
  1. Agent runs every 2 hours, fetches posts matching configured cashtags/hashtags/keywords, and only passes posts with 500+ likes (or watchlist accounts with 50+ likes) to drafting
  2. Each qualifying post produces both a reply draft and a retweet-with-comment draft, each with 2-3 alternatives, in the senior analyst voice with rationale attached
  3. A separate compliance checker Claude call — not the drafting prompt — blocks any draft mentioning Seva Mining or containing financial advice from reaching the queue
  4. Monthly quota counter increments with every tweet read; the agent hard-stops at the configured safety margin and the quota counter is stored and readable from the database
  5. Recency decay applies correctly: full score under 1 hour, 50% at 4 hours, item marked expired at 6 hours
**Plans**: 5 plans

Plans:
- [x] 04-01-PLAN.md — Foundation: deps, scheduler models, Alembic migration (config table + platform_user_id), test stubs
- [x] 04-02-PLAN.md — Fetch-filter-score pipeline: scoring functions, engagement gates, recency decay, quota counter
- [x] 04-03-PLAN.md — Draft-compliance pipeline: Claude drafting, separate compliance checker, DraftItem persistence
- [x] 04-04-PLAN.md — Wiring: APScheduler integration, seed script (25 watchlist accounts, keywords, config defaults)
- [x] 04-05-PLAN.md — Backend model sync, full test suite, human verification checkpoint

### Phase 5: Senior Agent Core
**Goal**: All items entering the queue are deduplicated across platforms, the 15-item hard cap is enforced with priority tiebreaking, items auto-expire on schedule, and WhatsApp morning digests and alerts are dispatched via Twilio
**Depends on**: Phase 4
**Requirements**: SENR-01, SENR-02, SENR-03, SENR-04, SENR-05, SENR-06, SENR-07, SENR-08, SENR-09, WHAT-01, WHAT-02, WHAT-03, WHAT-05
**Success Criteria** (what must be TRUE):
  1. When two agents surface the same story, the dashboard shows separate platform cards visually linked as "related" — neither card is silently dropped
  2. When the queue reaches 15 items, a new higher-scoring item displaces the current lowest-scoring item
  3. Twitter items auto-expire at 6 hours and Instagram items at 12 hours; the expiry sweep runs every 30 minutes
  4. A WhatsApp morning digest arrives at 8am daily containing top 5 gold sector stories, queue snapshot, yesterday's approval and rejection counts, and the single highest-value queue item
  5. A WhatsApp expiry alert is sent when a high-scored item approaches expiry without review
**Plans**: 6 plans

Plans:
- [ ] 05-01-PLAN.md — Foundation: twilio dep, DailyDigest model, WhatsApp service mirror, test stubs, migration 0004
- [ ] 05-02-PLAN.md — Story deduplication: Jaccard similarity, fingerprint tokens, related_id linking (TDD)
- [ ] 05-03-PLAN.md — Queue cap: 15-item hard cap, priority displacement, tiebreaking, process_new_item (TDD)
- [ ] 05-04-PLAN.md — Expiry sweep: bulk-expire, breaking news alerts, expiry alerts, engagement alerts (TDD)
- [ ] 05-05-PLAN.md — Morning digest: assembly, DailyDigest record, WhatsApp dispatch with 7 variables (TDD)
- [ ] 05-06-PLAN.md — Worker wiring, Twitter Agent integration, config seed, human verification checkpoint

### Phase 6: Instagram Agent
**Goal**: The Instagram Agent runs on schedule, scrapes qualifying gold-sector posts via Apify with health monitoring, drafts comment alternatives with compliance checking, and handles scraper failures gracefully with alerting
**Depends on**: Phase 5
**Requirements**: INST-01, INST-02, INST-03, INST-04, INST-05, INST-06, INST-07, INST-08, INST-09, INST-10, INST-11, INST-12
**Success Criteria** (what must be TRUE):
  1. Agent runs every 4 hours, scrapes configured hashtags and watchlist accounts via Apify, and only passes posts with 200+ likes from the last 8 hours to drafting
  2. Each qualifying post produces 2-3 comment alternatives, none containing hashtags, all in the senior analyst voice
  3. A separate compliance checker Claude call blocks any draft mentioning Seva Mining or containing financial advice
  4. When Apify returns zero results for a hashtag with an established baseline, this is flagged as a scraper health event in the run log — not treated as a quiet day
  5. Items expire from the queue after 12 hours; critical scraper failures trigger a WhatsApp alert
**Plans**: 5 plans

Plans:
- [ ] 06-01-PLAN.md — Foundation: apify-client dep, 15 test stubs (Wave 0)
- [ ] 06-02-PLAN.md — Fetch-filter-score pipeline: scoring formula, follower normalization, engagement gate, InstagramAgent skeleton (TDD)
- [ ] 06-03-PLAN.md — Draft-compliance pipeline: Claude drafting, hashtag/Seva blocking, fail-safe compliance, 12h expiry (TDD)
- [ ] 06-04-PLAN.md — Health monitoring: retry logic, rolling baseline detection, critical failure WhatsApp alerting (TDD)
- [ ] 06-05-PLAN.md — Worker wiring, seed script (hashtags + watchlist + config), human verification checkpoint

### Phase 7: Content Agent
**Goal**: The Content Agent runs daily at 6am, ingests RSS and SerpAPI news, picks the single best qualifying story, conducts multi-step deep research, drafts it in the correct format with compliance checking, and delivers to the Senior Agent — or sends an explicit "no story today" flag
**Depends on**: Phase 5
**Requirements**: CONT-01, CONT-02, CONT-03, CONT-04, CONT-05, CONT-06, CONT-07, CONT-08, CONT-09, CONT-10, CONT-11, CONT-12, CONT-13, CONT-14, CONT-15, CONT-16, CONT-17
**Success Criteria** (what must be TRUE):
  1. Agent runs at 6am, pulls new content from all 4 RSS feeds and SerpAPI, deduplicates by URL and 85% headline similarity, and selects only the single highest-scoring story above 7.0/10
  2. When nothing clears 7.0/10, the agent explicitly sends a "no story today" flag to the Senior Agent — no subthreshold story is surfaced
  3. The selected story undergoes a deep research pass: full article retrieved, 2-3 corroborating sources found via web search, key data points extracted before drafting
  4. Format decision produces the correct output: thread format produces both a tweet thread (3-5 tweets under 280 chars each) and a single long-form X post; infographic brief includes headline, 5-8 key stats with sources, visual structure suggestion, and full caption text
  5. A separate compliance checker Claude call validates no Seva Mining mention and no financial advice across the entire content package before it is sent to the Senior Agent
**Plans**: 5 plans

Plans:
- [x] 07-01-PLAN.md — Foundation: deps, ContentBundle model mirror, test stubs, config seed script
- [x] 07-02-PLAN.md — Ingest-Dedup-Score pipeline: RSS parsing, SerpAPI, dedup, scoring, story selection (TDD)
- [x] 07-03-PLAN.md — Deep research + drafting: article fetch, corroboration, Claude Sonnet format+draft prompt
- [x] 07-04-PLAN.md — Compliance checker, no-story flag, DraftItem builder, Senior Agent integration
- [x] 07-05-PLAN.md — Full pipeline wiring, worker.py integration, human verification checkpoint

### Phase 8: Dashboard Views and Digest
**Goal**: Operator has a dedicated daily digest view showing morning digest output, a content review page for today's Content Agent bundle, and the full Settings page wired to live database configuration
**Depends on**: Phase 7
**Requirements**: DGST-01, DGST-02, DGST-03, CREV-01, CREV-02, CREV-03, CREV-04, CREV-05, SETT-01, SETT-02, SETT-03, SETT-04, SETT-05, SETT-06, SETT-07, SETT-08
**Success Criteria** (what must be TRUE):
  1. Operator views today's morning digest on the dashboard — top 5 stories, queue snapshot, yesterday's summary, and priority alert — and navigates to any historical digest
  2. Content review page shows today's full draft with format choice and rationale, all sources with links, and infographic preview where applicable; approving it queues the content for posting
  3. Settings page lets operator add or remove X and Instagram watchlist accounts, manage keywords with weights, and adjust scoring parameters; all changes persist to the database and take effect on the next agent run without a service restart
  4. Agent run log in Settings shows the last 7 days of runs filterable by agent, with items found, queued, filtered, and any errors per execution
  5. X API quota usage is displayed on the Settings page with a visual indicator showing current consumption against the 10,000/month cap
**Plans**: 6 plans
**UI hint**: yes

Plans:
- [x] 08-01-PLAN.md — Foundation: TypeScript types, API modules, MSW handlers, backend config endpoints, test stubs
- [x] 08-02-PLAN.md — DigestPage: daily digest with top stories, queue snapshot, yesterday summary, prev/next navigation
- [x] 08-03-PLAN.md — ContentPage: content bundle review with format rendering, infographic preview, approve/reject flow
- [x] 08-04-PLAN.md — SettingsPage shell + Watchlists tab + Keywords tab (CRUD with confirmation dialogs)
- [x] 08-05-PLAN.md — SettingsPage: Scoring, Notifications, Agent Runs, Schedule tabs + QuotaBar
- [x] 08-06-PLAN.md — Human verification of all 3 dashboard pages (checkpoint)

### Phase 9: Agent Execution Polish
**Goal**: All agent configuration is fully DB-driven with no hardcoded values, agent schedule intervals are configurable from Settings, and the system is resilient to individual agent failures without crashing the scheduler worker
**Depends on**: Phase 8
**Requirements**: EXEC-02
**Success Criteria** (what must be TRUE):
  1. Every agent reads its scoring weights, thresholds, and decay parameters from the database at the start of each run — a weight change in Settings affects the very next run without a deploy
  2. Agent run intervals (Twitter 2h, Instagram 4h, Content 6am) are adjustable from the Settings page schedule configuration and take effect on the next scheduled trigger
  3. An agent crash is caught, logged with full error detail, and does not crash the scheduler worker process — remaining agents continue running on schedule
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7 -> 8 -> 9

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Infrastructure and Foundation | 4/7 | In Progress|  |
| 2. FastAPI Backend | 3/4 | In Progress|  |
| 3. React Approval Dashboard | 3/5 | In Progress|  |
| 4. Twitter Agent | 5/5 | Complete   | 2026-04-02 |
| 5. Senior Agent Core | 0/6 | Planned    |  |
| 6. Instagram Agent | 0/5 | Planned    |  |
| 7. Content Agent | 1/5 | In Progress|  |
| 8. Dashboard Views and Digest | 0/6 | Planned    |  |
| 9. Agent Execution Polish | 0/TBD | Not started | - |
