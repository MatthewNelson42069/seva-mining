# Roadmap: Seva Mining AI Social Media Agency

> **DEPRECATION NOTICE (2026-04-19):** The Instagram Agent (Phase 6) has been fully removed from the product scope. Apify-based Instagram scraping proved non-viable and the platform-economics no longer justify the spend (~$50/mo). After that purge the system was a three-agent system (Twitter, Senior, Content). Phase 6 is retained below for historical context only — it will never be executed. Any dependencies or references to the Instagram Agent in later phases (Phase 7 dual-platform content, Phase 10 notifications, Phase 11 carousel rendering) are also deprecated in-place. See quick task `260419-lvy` for the purge commits.
>
> **DEPRECATION NOTICE (2026-04-20):** The Twitter Agent (Phase 4) and the broader Senior Agent (Phase 5, Phase 10) have been fully removed from the product scope. The X API Basic tier ($100/mo) was not justified when the Content Agent's news-feed pipeline was already producing higher-signal drafts, and the Senior Agent had narrowed in practice to a single cron — the 07:00 morning digest. Seva Mining is now a **single-agent** system (Content Agent only, with a trimmed `morning_digest` job and the opportunistic `gold_history_agent`). Phase 4 and Phase 5 are retained below for historical context only — they will never be re-executed. Phase 10 is retained as executed-and-trimmed: `morning_digest` at 15:00 UTC remains live; the "Twitter/Instagram/Content new-item alert" goal is now "Content new-item alert" only. `tweepy[async]>=4.14` and the `x_api_bearer_token` / `x_api_key` / `x_api_secret` env wiring are preserved — the Content Agent's `video_clip` pipeline still calls tweepy's async client to search X video clips when a story has strong video supporting material. This is an X API read used downstream by Content, not the Twitter Agent. See quick task `260420-sn9` for the purge commits.

## Overview

Build a single-agent AI monitoring and drafting system. The original build order was: database schema and infrastructure first (everything depends on it), then the FastAPI backend, then the React approval dashboard (human workflow must be testable before agents run), then agents in ascending complexity (Twitter Agent first — simplest pipeline — then Senior Agent core to manage the queue, then Content Agent — most complex). Dashboard views for digest and content review, and full Settings configurability, were wired last once agents were producing verified output. Post-2026-04-20 (`260420-sn9`) the Twitter Agent and Senior Agent are deprecated; the shipped system is the Content Agent + trimmed `morning_digest` cron + `gold_history_agent`.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Infrastructure and Foundation** - Full database schema on Neon, Alembic migrations, two Railway services configured, APScheduler worker skeleton with DB job lock, Twilio WhatsApp template submission
- [ ] **Phase 2: FastAPI Backend** - Password auth (bcrypt + JWT), all REST endpoints, state machine transition enforcement, Twilio outbound notification service
- [ ] **Phase 3: React Approval Dashboard** - Tabbed approval interface, approval cards with full context and inline editing, approve/edit+approve/reject actions, copy-to-clipboard, direct source links
- [x] **~~Phase 4: Twitter Agent~~** - **DEPRECATED 2026-04-20 — see quick task `260420-sn9`.** Originally shipped 2026-04-02 as X API v2 monitoring with engagement scoring, dual-format drafting, and monthly quota counter. Purged because X API Basic tier ($100/mo) spend was not justified when Content Agent's news pipeline produced higher-signal drafts.
- [ ] **~~Phase 5: Senior Agent Core~~** - **DEPRECATED 2026-04-20 — see quick task `260420-sn9`.** Never fully executed. Story fingerprint dedup + 15-item queue cap + expiry sweep are no longer relevant in a single-agent system; the Content Agent has its own cross-run dedup. The `morning_digest` slice is retained under Phase 10 as a trimmed cron job.
- [ ] **~~Phase 6: Instagram Agent~~** - **DEPRECATED 2026-04-19. Never executed. Retained for historical context only.** Apify scraper integration, per-hashtag baseline tracking, retry/health logic, comment draft alternatives with compliance checker
- [x] **Phase 7: Content Agent** - RSS and SerpAPI ingest, multi-step deep research, 7 content formats (thread, long_form, breaking_news, infographic, video_clip, quote, gold_history), dual-platform output (Twitter + Instagram), cross-run dedup, 12pm midday run, bi-weekly Gold History agent, compliance checker (completed 2026-04-07)
- [ ] **Phase 8: Dashboard Views and Digest** - Daily digest view, content review page, full Settings page wired to live DB config
- [ ] **Phase 9: Agent Execution Polish** - All scoring weights DB-driven and configurable, agent schedule config from Settings, run logs, quota display, graceful failure handling

<!-- Milestone v1.0.1 — Content preview & rendered images -->
- [x] **Phase 11: Content Preview and Rendered Images** - Full structured content brief rendering in dashboard modal (infographic, thread, long_form, breaking_news, quote, video_clip) via new `/content-bundles/{id}` endpoint, AI-generated rendered images (Nano Banana/Gemini) for infographic + quote formats stored in Cloudflare R2, background render job so agent cron stays fast, modal displays brief + rendered images inline

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

### ~~Phase 4: Twitter Agent~~
**DEPRECATED 2026-04-20 — see quick task `260420-sn9`. The Twitter Agent was shipped on 2026-04-02 and ran in prod until 2026-04-20. It has been fully purged from code, scheduler, frontend, and prod database (177 historical `draft_items WHERE platform='twitter'` rows deleted, all `twitter_*` config keys removed, all 40 watchlists emptied). This phase's plans 04-01..04-05 are retained as historical record only.**

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

### ~~Phase 5: Senior Agent Core~~
**DEPRECATED 2026-04-20 — see quick task `260420-sn9`. Phase 5 was never fully shipped; in practice only the `morning_digest` slice survived into prod (via Phase 10's 10-03). With Twitter purged and Instagram already purged in `260419-lvy`, there is only one producer (Content Agent) and no need for cross-platform dedup, queue cap displacement, or expiry sweeps. The `senior_agent.py` module was trimmed to morning-digest-only in `260420-sn9` Task 2. This phase header is retained for historical record only.**

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

### ~~Phase 6: Instagram Agent~~
**DEPRECATED 2026-04-19 — see quick task `260419-lvy`. The Instagram Agent is out of product scope. This phase will never execute. All `scheduler/agents/instagram_agent.py` code, Apify dependencies, Instagram platform tabs, and IG watchlist toggles have been purged. Plans `06-01..06-05` below are retained as historical record only.**

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
**Goal**: The Content Agent runs at 6am and 12pm daily, ingests RSS (8 feeds) and SerpAPI (10 keywords) news, sources video clips and quotes from Twitter, processes ALL qualifying stories above 7.0/10 across 7 content formats (thread, long_form, breaking_news, infographic, video_clip, quote, gold_history), produces dual-platform output (Twitter + Instagram) for applicable formats, and delivers to the Senior Agent. A separate Gold History Agent runs bi-weekly on Sunday producing drama-first storytelling threads with Instagram carousels.
**Depends on**: Phase 5
**Requirements**: CONT-01, CONT-02, CONT-03, CONT-04, CONT-05, CONT-06, CONT-07, CONT-08, CONT-09, CONT-10, CONT-11, CONT-12, CONT-13, CONT-14, CONT-15, CONT-16, CONT-17
**Success Criteria** (what must be TRUE):
  1. Agent runs at 6am and 12pm, pulls content from 8 RSS feeds and 10 SerpAPI keywords, deduplicates by URL and 85% headline similarity, cross-run dedup against today's earlier ContentBundles, and processes all qualifying stories above 7.0/10
  2. When nothing clears 7.0/10 and no video clips or quotes surface, the agent sends a "no story today" flag — no subthreshold story is surfaced
  3. Each qualifying story undergoes deep research and is drafted in the best-fit format (thread, long_form, breaking_news, infographic, quote) with dual-platform output where applicable
  4. Video clips from credible Twitter accounts produce video_clip ContentBundles with quote-tweet captions for both Twitter and Instagram
  5. A separate compliance checker Claude call validates no Seva Mining mention and no financial advice across all content
  6. Gold History Agent runs bi-weekly Sunday, picks an unused story, verifies facts via SerpAPI, produces a 5-7 tweet thread and 4-7 slide Instagram carousel
  7. All content types are tagged with `content_type` field (renamed from `format_type` via Alembic migration)
**Plans**: 10 plans

Plans:
- [x] 07-01-PLAN.md — Foundation: deps, ContentBundle model mirror, test stubs, config seed script
- [x] 07-02-PLAN.md — Ingest-Dedup-Score pipeline: RSS parsing, SerpAPI, dedup, scoring, story selection (TDD)
- [x] 07-03-PLAN.md — Deep research + drafting: article fetch, corroboration, Claude Sonnet format+draft prompt
- [x] 07-04-PLAN.md — Compliance checker, no-story flag, DraftItem builder, Senior Agent integration
- [x] 07-05-PLAN.md — Full pipeline wiring, worker.py integration, human verification checkpoint
- [x] 07-06-PLAN.md — DB migration: rename format_type to content_type across entire codebase
- [x] 07-07-PLAN.md — Breaking news format, expanded sourcing (8 RSS / 10 SerpAPI), cross-run dedup, multi-story pipeline
- [x] 07-08-PLAN.md — Video clip + quote formats: Twitter API search, Claude drafting, dual-platform output
- [x] 07-09-PLAN.md — Infographic Instagram dual-platform output, expanded Sonnet prompt with all 7 formats, historical mode
- [x] 07-10-PLAN.md — Gold History Agent, 12pm midday run, APScheduler job registration, config seed

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
**Plans**: 2 plans

Plans:
- [ ] 09-01-PLAN.md — Engagement gate thresholds to DB config (Twitter + Instagram agents, seed scripts)
- [ ] 09-02-PLAN.md — Schedule intervals to DB config (worker.py, seed scripts)

### Phase 10: Senior Agent WhatsApp Notifications
> **PARTIAL DEPRECATION (2026-04-20 — `260420-sn9`):** The Twitter + Instagram + Content multi-agent new-item alert goal is now Content-only (Twitter and Instagram agents were both purged). The `morning_digest` at 15:00 UTC continues to run as the sole surviving slice of the Senior Agent. All other Senior Agent responsibilities (dedup, queue cap, expiry sweep) are permanently out of scope.

**Goal**: The Senior Agent sends real WhatsApp notifications via the Twilio sandbox — a morning digest at 7am PST and an instant alert every time the Content Agent creates new draft items for review. The expiry sweep job is removed. The WhatsApp service is rewritten to use free-form sandbox messages instead of pre-approved Meta templates.
**Depends on**: Phase 9
**Requirements**: WHAT-01, WHAT-02, WHAT-05
**Success Criteria** (what must be TRUE):
  1. Morning digest WhatsApp message arrives on the operator's phone at 7am PST (15:00 UTC) summarising overnight queue activity
  2. A WhatsApp notification arrives within seconds of the Twitter, Instagram, or Content agent creating new draft items — message names the agent and item count
  3. The expiry_sweep job no longer runs — it is removed from the APScheduler worker
  4. Twilio sandbox credentials (Account SID, Auth Token, from/to numbers) are loaded from environment variables and the service sends messages successfully
**Plans**: 3 plans

Plans:
- [x] 10-01-PLAN.md — Rewrite WhatsApp service for sandbox free-form messages, wire Twilio credentials
- [ ] 10-02-PLAN.md — New item notification: hook into Twitter, Instagram, Content agents post-run
- [x] 10-03-PLAN.md — Morning digest at 15:00 UTC, remove expiry_sweep job, human verification checkpoint

---

## Milestone v1.0.1 — Content Preview and Rendered Images

Phase 11 opens the v1.0.1 milestone. Scope: upgrade the Content queue detail modal so the operator sees the complete structured brief the Content Agent produced (not just a flattened caption) AND views AI-rendered image mockups alongside the brief for visual formats.

### Phase 11: Content Preview and Rendered Images
**Goal**: Operator clicks any Content queue card and sees the full structured brief for every content format plus AI-rendered image previews for infographic and quote formats; no more "just a headline" modals
**Depends on**: Phase 10
**Requirements**: CREV-02 (expansion), plus new requirements to be captured in REQUIREMENTS.md during the phase
**Success Criteria** (what must be TRUE):
  1. `GET /content-bundles/{id}` returns the full ContentBundle (draft_content JSONB, deep_research, story_headline, sources, rendered_images) for an authenticated operator
  2. ContentDetailModal fetches the bundle via `engagement_snapshot.content_bundle_id` and renders a format-aware preview: infographic (InfographicPreview — Twitter + Instagram side-by-side, including carousel slides), thread (tweets list + long_form_post), long_form (single post), breaking_news (tweet + optional infographic_brief), quote (twitter_post + instagram_post), video_clip (twitter_caption + instagram_caption); falls back to plain text if bundle fetch fails
  3. After the Content Agent commits a bundle whose format is infographic or quote, a background job generates AI-rendered images (3 Instagram carousel slides + 1 Twitter visual = up to 4 images per bundle) via the Nano Banana / Gemini image API and uploads them to Cloudflare R2 under a public URL
  4. Rendered image URLs persist on ContentBundle (new column `rendered_images` JSONB — array of `{url, role}` objects where role ∈ `{instagram_slide_1, instagram_slide_2, instagram_slide_3, twitter_visual}`) via an Alembic migration, and the modal displays them inline alongside the brief
  5. Background render job is independent from the Content Agent cron — agent commits the bundle and returns in <5s; render completes asynchronously within ~2 minutes and the modal auto-refreshes/polls to pick up rendered images
  6. Render failures are logged per-image, do not crash the agent run, and the modal gracefully hides image slots when URLs are absent
**Plans**: TBD during planning

**Scope decisions locked (from discuss phase):**
- Image generation: AI (Nano Banana / Gemini), not template-based
- Storage: Cloudflare R2 (S3-compatible, free egress, public URLs, ~$0.015/GB-mo)
- Formats rendered: infographic first (3 IG slides + 1 Twitter = 4 images), quote second (1 IG + 1 Twitter = 2 images). Thread, long_form, breaking_news, video_clip skip image rendering (text-only or externally sourced)
- Rendering latency: background job separate from the 2-hour agent cron, so agent throughput stays fast

Plans:
- [x] 11-01-PLAN.md — Foundation and Wave 0 (deps, env, migration 0006, schemas, worker scheduler, test stubs)
- [x] 11-02-PLAN.md — Image render service (`render_bundle_job` — Imagen 4 + R2 + silent-fail)
- [x] 11-03-PLAN.md — Backend endpoints (`GET /content-bundles/{id}`, `POST /content-bundles/{id}/rerender`)
- [x] 11-04-PLAN.md — Content Agent integration (enqueue render on infographic/quote commit)
- [x] 11-05-PLAN.md — Frontend API and hook (`useContentBundle` + `useRerenderContentBundle`)
- [x] 11-06-PLAN.md — Format-aware modal (7 preview components + RenderedImagesGallery)
- [x] 11-07-PLAN.md — Human verification on staging + milestone finalization

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7 -> 8 -> 9 -> 10 -> 11

Milestones:
- **v1.0** — Phases 1–10 (originally core four-agent platform + dashboard + WhatsApp; post-2026-04-20 the only surviving agents are Content + trimmed morning_digest + gold_history_agent)
- **v1.0.1** — Phase 11 (content preview & rendered images) — shipped 2026-04-19

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Infrastructure and Foundation | 4/7 | In Progress|  |
| 2. FastAPI Backend | 3/4 | In Progress|  |
| 3. React Approval Dashboard | 3/5 | In Progress|  |
| 4. Twitter Agent | 5/5 | **Deprecated 2026-04-20** | (shipped 2026-04-02, purged 2026-04-20) |
| 5. Senior Agent Core | 0/6 | **Deprecated 2026-04-20** |  |
| 6. Instagram Agent | 0/5 | **Deprecated 2026-04-19** |  |
| 7. Content Agent | 10/10 | Complete   | 2026-04-07 |
| 8. Dashboard Views and Digest | 6/6 | Complete   |  |
| 9. Agent Execution Polish | 2/2 | Complete   |  |
| 10. Senior Agent WhatsApp Notifications | 2/3 | Complete    | 2026-04-07 |
| 11. Content Preview and Rendered Images | 7/7 | Complete   | 2026-04-19 |
