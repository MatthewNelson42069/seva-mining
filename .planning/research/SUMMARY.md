# Project Research Summary

**Project:** Seva Mining — AI Social Media Monitoring and Engagement Drafting System
**Domain:** AI-powered social listening, content drafting, and human-in-the-loop approval workflow (gold/mining sector)
**Researched:** 2026-03-30
**Confidence:** HIGH

## Executive Summary

Seva Mining requires a custom-built, single-operator social intelligence system that monitors X (Twitter) and Instagram for gold sector conversations, drafts AI-generated engagement responses, and routes them through a human approval workflow before manual posting. This is a well-understood problem class — a "human-in-the-loop agentic pipeline" — with established architectural patterns: an orchestrator-worker multi-agent system backed by a shared PostgreSQL database, a separate scheduler process, and a lightweight React approval dashboard. The stack is almost entirely pre-decided: FastAPI backend on Railway, APScheduler worker (separate process), Neon PostgreSQL, React 19 + Vite + Tailwind v4 frontend on Vercel, and Claude API for all LLM operations. The total operating cost is approximately $255-275/mo, directly competitive with Sprout Social ($249/mo+) while delivering capabilities generic tools cannot provide: gold-sector relevance scoring, recency decay curves, dual-format drafting, and a proactive Content Agent with deep research.

The recommended approach is a sequential build ordered by dependency graph: database schema first (everything depends on it), then FastAPI backend skeleton, then React dashboard (so the human workflow is testable before agents produce real data), then the scheduler worker, then agents in ascending complexity order (Twitter → Senior Agent core → Instagram → Content Agent). This ordering ensures every layer is verifiable before the next is added. The single most important architectural decision — already made correctly — is running APScheduler as a completely separate Railway service, not embedded in the FastAPI process. This prevents crash coupling, duplicate execution, and worker-count scheduler multiplication.

The key risks are operational, not architectural. X Basic API's 10,000 monthly tweet read cap will be exhausted in days without explicit budget tracking and hard-stop logic. Instagram scraping via Apify returns empty results silently when throttled, masking a real data gap as a quiet day. Claude will produce draft language that subtly implies financial advice unless a separate compliance checker Claude call (not the same prompt as draft generation) enforces the "no financial advice, no Seva mention" rules structurally. Twilio WhatsApp requires Meta-approved message templates for all production notifications — designing this at the end of development rather than the beginning blocks go-live. All four of these risks have concrete mitigations defined in research; they must be designed in from the start, not retrofitted.

## Key Findings

### Recommended Stack

See `/Users/matthewnelson/seva-mining/.planning/research/STACK.md` for full details.

The stack pairs a Python async backend with a modern React frontend. Two Railway services share one Neon PostgreSQL database — the only coupling point. All LLM operations use the `anthropic` SDK with `AsyncAnthropic`. Instagram is handled exclusively via Apify managed scraping (not direct scraping, which violates Instagram ToS and breaks constantly). X monitoring uses Tweepy v2 with the Basic API tier. The scheduler uses APScheduler 3.11.2 stable — version 4.x alpha must be avoided.

**Core technologies:**
- FastAPI 0.135.1 + Python 3.12: async-first API framework, auto OpenAPI docs, Pydantic v2 native
- APScheduler 3.11.2 (separate Railway worker): cron-based agent scheduling, single-process isolation mandatory
- SQLAlchemy 2.0 + asyncpg + Alembic: async ORM with migration discipline; `create_async_engine` only, never sync
- Neon PostgreSQL 16 (managed): free tier sufficient for v1; PgBouncer connection pooling via `-pooler` endpoint
- anthropic 0.86.0 (`AsyncAnthropic`): all Claude calls — scoring, drafting, evaluation, compliance checking
- apify-client 2.5.0: Instagram scraping via managed Apify Actors; handles bot detection, proxy rotation
- tweepy 4.x (`Client`, not legacy `API` class): X API v2 read-only monitoring
- React 19 + Vite 6 + Tailwind CSS 4: single-user approval dashboard, shadcn/ui components (tailwind-v4 branch)
- TanStack Query 5 + Zustand 5: server state (React Query) and UI state (Zustand) cleanly separated
- Twilio 9.x: outbound-only WhatsApp notifications (digest + breaking alerts)

**Critical version constraints:**
- APScheduler: 3.11.2 only — v4.x alpha has breaking API changes
- shadcn/ui: tailwind-v4 branch only — main branch targets Tailwind v3
- SQLAlchemy: v2 patterns only — v1 `Session` blocks the async event loop
- Tailwind CSS 4: use `@tailwindcss/vite` plugin, not PostCSS

### Expected Features

See `/Users/matthewnelson/seva-mining/.planning/research/FEATURES.md` for full details.

**Must have (table stakes) — all required for launch:**
- Twitter Agent: keyword/hashtag/cashtag monitoring, engagement gate (500+ likes), recency decay, dual-format drafting (reply + RT-with-comment), watchlist bypass
- Instagram Agent: Apify-based monitoring, engagement gate (200+ likes), comment draft alternatives
- Content Agent: RSS ingest, SerpAPI news search, deep research pass, format decision (thread/single/infographic brief), 7.0/10 quality threshold
- Senior Agent: queue management, deduplication, 15-item hard cap with priority scoring, auto-expiry, WhatsApp dispatch
- Approval Dashboard: platform-tabbed feed layout, approval cards with full context, inline editing, approve/edit+approve/reject with mandatory rejection reason, copy-to-clipboard, direct link to source
- Agent self-evaluation quality gate: separate compliance Claude call (not same prompt as generation) enforcing "no financial advice, no Seva mention" rules
- WhatsApp notifications: morning digest, breaking news alert, expiring draft alert (all as pre-approved Meta templates)
- Settings page: watchlist management, keyword configuration, scoring weights, agent schedule, run logs
- Simple password auth: bcrypt hashed password in environment variable, JWT session tokens

**Should have (differentiators — add after core validation):**
- Event mode: engagement spike (3x baseline) or gold price movement trigger; temporarily expands 15-item cap
- Infographic brief generation: structured visual content briefs for data-heavy Instagram posts
- Deduplication visual linking: cross-platform "related" card badges with story fingerprint matching
- Performance-driven learning loop: approval tracking feeding back into scoring weight adjustment

**Defer (v2+):**
- Analytics dashboard — requires weeks of historical data before trends are meaningful
- Multi-tenancy — build only when second client exists
- LinkedIn agent — add only if X + Instagram signal proves insufficient
- Two-way WhatsApp approval — reconsider only if dashboard friction proves to be the primary bottleneck

**Explicit anti-features (never implement):**
- Auto-posting to any platform — brand and compliance risk in gold/finance space cannot be mitigated by any confidence threshold
- Mobile-responsive dashboard — desktop-only v1; WhatsApp handles mobile touchpoints

### Architecture Approach

See `/Users/matthewnelson/seva-mining/.planning/research/ARCHITECTURE.md` for full details.

The system uses an orchestrator-worker hub-and-spoke pattern: Twitter, Instagram, and Content agents are independent workers that produce scored candidate drafts; Senior Agent is the sole orchestrator handling cross-cutting concerns (dedup, queue cap, expiry, notifications). All agents run in the same scheduler worker process — they communicate via function calls, not queues. The PostgreSQL database is the only integration point between the scheduler worker and the FastAPI API server. No message broker is needed at this volume. The React dashboard is a pure read/write layer against the FastAPI REST API; all truth lives in the database.

**Major components:**
1. Scheduler Worker (Railway service 1) — APScheduler cron triggers, four agent modules, shared DB writes
2. FastAPI Backend (Railway service 2) — REST API for dashboard, auth middleware, status transition enforcement, Twilio outbound
3. Neon PostgreSQL — drafts (JSONB alternatives array), watchlists, agent_runs, settings tables
4. React Dashboard (Vercel) — tabbed approval interface, settings management, read-only against FastAPI
5. Claude API — called by all four agents for scoring, drafting, self-evaluation, and compliance checking

**Key patterns:**
- State machine on draft lifecycle: `pending` → `approved` | `edited_approved` | `rejected` | `expired`; transitions enforced at API layer with rejection reason required
- JSONB array for draft alternatives: single-row fetch per card, no child table join
- Scheduler reads settings from DB on every run: never caches config in memory, so settings changes take effect on next run without restart
- Senior Agent calls Twilio SDK directly: avoids unnecessary HTTP round-trip through API server for outbound notifications

### Critical Pitfalls

See `/Users/matthewnelson/seva-mining/.planning/research/PITFALLS.md` for full details.

1. **X Basic API 10,000 tweet/month cap exhaustion** — Budget by tweet reads (not search calls); implement monthly quota counter in DB; hard-stop Twitter Agent at 500 remaining with dashboard alert and WhatsApp notification; deduplicate tweet IDs to prevent re-fetching; cap event mode fetch at 150 tweets per run.

2. **Instagram Apify scraper silent partial/empty results** — Compare result counts against per-hashtag baselines stored in DB; flag zero-result runs as scraper health events (not valid empty days); implement retry once at +2h; stagger run timing ±15 minutes; pin Apify Actor versions and update deliberately.

3. **Claude compliance violations despite prompt instructions** — Run a separate second Claude call as a compliance checker after draft generation (never in the same prompt); define "no financial advice" and "no Seva mention" with concrete example violations; track compliance rejection rate in run logs; alert if rate exceeds 2 rejections in a single run.

4. **APScheduler duplicate execution during Railway deploys** — Separate scheduler worker (already designed correctly); configure Railway replica count to exactly 1 with autoscaling disabled; add DB-level job lock (TTL row written before each agent run) as defense-in-depth.

5. **Twilio WhatsApp sandbox masks production template requirements** — Design all three notification types as WhatsApp message templates from day one; submit to Meta for approval during Phase 1 infrastructure (approval takes 1-7 business days); never treat sandbox success as production validation.

6. **Content quality threshold drift** — Store quality score + rationale for every draft permanently; track weekly approval rate in Settings page; include 3-5 "gold standard" example stories as scoring anchors in the rubric prompt; treat the compliance checker prompt as a system constraint, not a tunable parameter.

7. **Senior Agent cross-platform deduplication context loss** — Extract structured story fingerprints via Claude (`{event, direction, level}`) for each incoming item; store in JSONB column; match against fingerprints from last 24-48h window, not full text; if fingerprint extraction is uncertain, queue both items without "related" link rather than silently dropping either.

## Implications for Roadmap

Based on research, the dependency graph dictates a clear build order. Each phase delivers a verifiable layer before the next is added. The critical insight from architecture research is: build the human workflow (database schema, API, dashboard) before building agents, so there is a testable interface before any automated output exists.

### Phase 1: Infrastructure and Foundation
**Rationale:** Everything else depends on the database schema and deployment configuration. Twilio WhatsApp template approval takes 1-7 business days — submission must happen here, not at the end. The DB job lock and Railway single-replica configuration for the scheduler must be established before any agent runs.
**Delivers:** Complete database schema (all tables, JSONB structure, state enum, indexes), Alembic migration pipeline, Railway project configuration (two services), environment variables and secrets setup, Twilio WhatsApp templates submitted to Meta for approval, APScheduler worker skeleton with DB job lock.
**Addresses:** Simple authentication, run logging infrastructure, environment configuration
**Avoids:** APScheduler duplicate execution (Pitfall 4), Twilio production template block (Pitfall 6), API key exposure (security)

### Phase 2: FastAPI Backend Skeleton
**Rationale:** The dashboard cannot function without the API. Auth middleware, draft CRUD, and the state machine transitions must exist before the React frontend has anything to render or act on.
**Delivers:** Password auth (bcrypt + JWT), REST endpoints for drafts (GET, PATCH approve/reject/edit), settings CRUD, watchlist CRUD, agent run log queries, state machine transition enforcement with rejection reason requirement, Twilio outbound notification service.
**Addresses:** State machine (approved/rejected/expired transitions), rejection reason mandatory capture, settings API
**Avoids:** Auto-posting (never implement), raw prompt exposure via Settings API (security)

### Phase 3: React Approval Dashboard
**Rationale:** Build the human review interface against the API skeleton before agents produce real data. This makes the human workflow independently testable with seeded mock data. Inline editing, copy-to-clipboard, platform tabs, and expiry urgency indicators should all function correctly before any agent ever runs.
**Delivers:** Tabbed approval interface (Twitter / Instagram / Content tabs), approval cards with full context display, inline editing with side-by-side source context, approve / edit+approve / reject actions, mandatory rejection reason dropdown, copy-to-clipboard with toast, direct source link, score component breakdown on hover, expiry countdown color indicator, Settings page UI.
**Addresses:** Full approval card feature set, platform badges, account info, settings page, run logs view
**Avoids:** Modal-based inline editor losing source context (UX Pitfall), missing visual distinction between reply and RT-with-comment alternatives (UX Pitfall)

### Phase 4: Twitter Agent
**Rationale:** X API is the most structured and predictable data source — best choice for first end-to-end pipeline test. Building Twitter Agent first validates the full pipeline (fetch → score → draft → queue) before adding more complex integrations.
**Delivers:** X API v2 integration (OAuth 2.0 Bearer, keyword + watchlist search), engagement gate (500+ likes, watchlist 50+), recency decay curve, scoring formula, dual-format draft generation (reply + RT-with-comment alternatives), separate compliance checker Claude call, monthly quota counter and hard-stop logic, tweet ID deduplication in DB.
**Addresses:** Twitter monitoring, dual-format drafting, agent self-evaluation quality gate, quota tracking
**Avoids:** X API cap exhaustion (Pitfall 1) — quota counter MUST ship with this phase, not later

### Phase 5: Senior Agent Core
**Rationale:** Deduplication, queue cap enforcement, and expiry must exist before adding more agents to the queue — otherwise the second and third agents produce unchecked queue pollution.
**Delivers:** Story fingerprint extraction via Claude, cross-platform deduplication logic (related vs. duplicate distinction), 15-item hard queue cap with priority score tiebreaking, auto-expiry sweep (Twitter: 6h, Instagram: 12h), story fingerprint JSONB storage, WhatsApp morning digest and breaking alert dispatch via Twilio.
**Addresses:** Senior Agent queue management, deduplication, expiry, WhatsApp notifications
**Avoids:** Cross-platform story fingerprint context loss (Pitfall 7), queue cap conflict with event mode (soft cap design for later event mode)

### Phase 6: Instagram Agent
**Rationale:** Apify integration is less predictable than X API (silent partial results, version pinning, anti-bot measures). Build after core pipeline is proven. Cross-platform deduplication (Senior Agent) must be in place before Instagram items enter the queue.
**Delivers:** Apify Actor integration with retry logic, per-hashtag baseline result count tracking in DB, zero-result health alert, run timing stagger (±15 minutes), comment draft alternatives, engagement gate (200+ IG likes), Actor version pinning.
**Addresses:** Instagram monitoring, scraper health monitoring, comment drafting
**Avoids:** Instagram silent partial failure (Pitfall 2)

### Phase 7: Content Agent
**Rationale:** Most complex agent — RSS + SerpAPI + multi-step deep research + format decision logic. Build last when the full pipeline plumbing is proven. Hourly SerpAPI quota cap tracking must be designed in from the start.
**Delivers:** RSS feed ingestion (feedparser, etag/last-modified tracking), SerpAPI news search with result caching, multi-step deep research pass via Claude, format decision logic (thread / single post / infographic brief), 7.0/10 quality threshold with "no story today" explicit flag, approval-rate calibration tracking in DB, SerpAPI hourly consumption tracking and alert.
**Addresses:** Content Agent story pipeline, proactive story creation, quality gate, infographic brief generation skeleton
**Avoids:** Content quality threshold drift (Pitfall 5), SerpAPI hourly cap burst (integration gotcha)

### Phase 8: Settings and Configurability
**Rationale:** Wire all hardcoded scoring weights, thresholds, and schedules to DB-driven config via the Settings page. Polish once agents are producing correct output and the operator has enough experience to know what needs tuning.
**Delivers:** All scoring weights configurable from Settings page, keyword list management, watchlist CRUD, agent schedule configuration, weekly approval-rate calibration view, quota status dashboard display, run log viewer with items found/queued/filtered/errors per execution.
**Addresses:** Settings page full configurability, run logs, weekly approval rate calibration surface
**Avoids:** Hardcoded scoring weights requiring code deploys (technical debt pattern), settings cache in agent memory (Anti-Pattern 4)

### Phase 9: v1.x Enhancements
**Rationale:** Add differentiating features after the core workflow is validated with real usage data. Event mode requires baseline engagement data to define "3x normal." Deduplication visual linking is most valuable after both agents have run for several cycles.
**Delivers:** Event mode (engagement spike trigger + gold price movement trigger, soft queue cap expansion), cross-platform deduplication visual linking in dashboard, infographic generation full implementation, performance-driven learning loop foundation.
**Addresses:** Event mode, infographic generation, deduplication visual linking, learning loop
**Note:** These are P2 features — schedule based on operator feedback after v1 launch.

### Phase Ordering Rationale

- **Infrastructure before application:** Twilio template approval and DB job lock cannot be deferred. Both have external dependencies (Meta approval, Railway config) that block production unless started early.
- **Human workflow before automation:** Database → API → Dashboard ensures the approval workflow is correct and testable before any agent generates real output. This means the operator can validate UX with seeded data.
- **Simpler agent before complex:** Twitter Agent first (structured API, well-documented), Instagram second (managed scraping, requires retry design), Content Agent last (multi-step pipeline, most failure modes).
- **Senior Agent core between Twitter and Instagram:** Deduplication and queue cap must be in place before multiple agents contribute to the same queue. Otherwise queue management must be retrofitted to handle cross-platform scenarios it was never designed for.
- **Settings page last:** Configurability is polished, not foundational. All thresholds must be configurable in the DB from day one (no hardcoding), but the Settings UI can come after agents are producing verified output.

### Research Flags

Phases likely needing `/gsd:research-phase` during planning:
- **Phase 4 (Twitter Agent):** X API v2 search endpoints, rate limit window behavior, and OAuth 2.0 Bearer token setup have enough operational nuance that targeted API research during planning will save implementation time.
- **Phase 6 (Instagram Agent):** Apify Actor-specific configuration (proxy settings, run parameters, version pinning strategy) warrants Actor-level research during planning rather than discovering options mid-implementation.
- **Phase 7 (Content Agent):** Multi-step Claude research pipeline (chained prompts, structured output via tool use, format decision logic) benefits from a dedicated prompt engineering research pass before implementation.

Phases with standard patterns (skip research-phase):
- **Phase 1 (Infrastructure):** Railway two-service configuration, Alembic migrations, and Neon PostgreSQL connection config are all well-documented with high-confidence sources already in STACK.md.
- **Phase 2 (FastAPI Backend):** bcrypt + JWT single-user auth, SQLAlchemy async CRUD, FastAPI router patterns — all standard, verified against official docs.
- **Phase 3 (React Dashboard):** React 19 + TanStack Query + Zustand + shadcn/ui patterns are well-established. The main risk (shadcn tailwind-v4 branch) is already identified.
- **Phase 5 (Senior Agent):** Orchestrator-worker pattern is well-documented. Claude story fingerprint extraction is a standard structured output use case.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Core technologies pre-decided and version-verified against PyPI and official docs. Supporting library patterns confirmed from multiple consistent sources. One medium-confidence item: TanStack Query v5 + Zustand recommended pattern sourced from community blog, not official docs — but the recommendation is well-established in practice. |
| Features | HIGH (core), MEDIUM (differentiators) | Table stakes features confirmed against competitor analysis (Sprout Social, Hootsuite) and HITL workflow research. Gold-sector specific differentiators (event mode, niche relevance scoring) are novel — confidence is medium because there are no direct comparators to validate against. |
| Architecture | HIGH | Orchestrator-worker pattern confirmed against Azure Architecture Center (HIGH confidence source). Separate scheduler worker, JSONB alternatives, state machine, and shared-DB integration patterns all verified against multiple sources including official APScheduler and FastAPI documentation. |
| Pitfalls | HIGH | X API quota limits verified against official X API documentation. Apify Instagram scraping pitfalls confirmed against Apify official docs and blog. APScheduler multi-worker issue confirmed against official APScheduler FAQ. Twilio WhatsApp template requirements confirmed against Twilio official documentation. Claude compliance drift confirmed against Anthropic best practices documentation. |

**Overall confidence:** HIGH

### Gaps to Address

- **Gold price feed for Event Mode:** Event mode can trigger on engagement spike (3x baseline — derivable from agent history) OR gold price movement. The gold price feed integration is not yet researched. During Phase 9 planning, validate whether a free gold price API (e.g., metals-api.com, XE API) is suitable, or whether the engagement-spike trigger alone is sufficient for v1 event mode.
- **SerpAPI monthly plan selection:** STACK.md references SerpAPI at ~$50/mo with 100 searches/mo on the basic plan. The Content Agent runs daily — 100 searches/mo is approximately 3 searches per day, which may be insufficient if the agent queries multiple news topics per run. Validate the required search volume before selecting a SerpAPI plan.
- **WhatsApp Business account setup time:** The research identifies Meta template approval as taking 1-7 business days, but WhatsApp Business account registration itself (if not already done) can add additional lead time. Verify whether a WhatsApp Business account exists for Seva Mining before Phase 1 planning.
- **Neon free tier connection limit:** STACK.md specifies `pool_size=5, max_overflow=10` for the Neon free tier. The exact connection limit for Neon's free tier should be verified at setup — if the free tier caps at fewer than 15 connections, the pool config needs adjustment.

## Sources

### Primary (HIGH confidence)
- FastAPI PyPI (v0.135.1 confirmed): https://pypi.org/project/fastapi/
- Anthropic SDK PyPI (v0.86.0 confirmed): https://pypi.org/project/anthropic/
- APScheduler PyPI (stable 3.11.2, alpha 4.0.0a6): https://pypi.org/project/APScheduler/
- apify-client PyPI (v2.5.0 confirmed): https://pypi.org/project/apify-client/
- Neon connection pooling docs: https://neon.com/docs/connect/connection-pooling
- Neon + FastAPI async guide: https://neon.com/guides/fastapi-async
- X API Rate Limits (official): https://docs.x.com/x-api/fundamentals/rate-limits
- Twilio WhatsApp sandbox vs. production (official): https://www.twilio.com/docs/whatsapp/sandbox
- Twilio WhatsApp rules and best practices (official): https://support.twilio.com/hc/en-us/articles/360017773294
- APScheduler FAQ — interprocess synchronization (official): https://apscheduler.readthedocs.io/en/3.x/faq.html
- Anthropic Claude prompting best practices (official): https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices
- AI Agent Orchestration Patterns — Azure Architecture Center (HIGH): https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/ai-agent-design-patterns
- Human-in-the-Loop patterns — Cloudflare Agents docs (HIGH): https://developers.cloudflare.com/agents/guides/human-in-the-loop/
- shadcn Tailwind v4 compatibility: https://ui.shadcn.com/docs/tailwind-v4
- Railway FastAPI deployment guide: https://docs.railway.com/guides/fastapi
- Apify Instagram scraper official: https://apify.com/apify/instagram-scraper

### Secondary (MEDIUM confidence)
- SQLAlchemy 2.0 + asyncpg patterns: https://leapcell.io/blog/building-high-performance-async-apis-with-fastapi-sqlalchemy-2-0-and-asyncpg
- APScheduler multi-worker caution (community discussion): https://github.com/fastapi/fastapi/discussions/9143
- TanStack Query v5 + Zustand pattern: https://reactdeveloperx.blogspot.com/2025/08/next-gen-react-state-management-with_14.html
- Multi-agent patterns (orchestrators/workers): https://aiagentsblog.com/blog/multi-agent-patterns/
- ARQ vs APScheduler vs Celery comparison: https://leapcell.io/blog/celery-versus-arq-choosing-the-right-task-queue-for-python-applications
- Content approval workflows guide: https://influenceflow.io/resources/content-approval-workflows-a-complete-guide-for-2026-1/
- AI in Social Media monitoring tools 2026: https://www.ema.ai/additional-blogs/addition-blogs/best-social-media-ai-agents
- Ensuring reliability in AI agents — drift/hallucination in production: https://medium.com/@kamyashah2018/ensuring-reliability-in-ai-agents-preventing-drift-and-hallucinations-in-production-4b8f8600ec69
- Scheduled jobs with FastAPI and APScheduler — Sentry: https://sentry.io/answers/schedule-tasks-with-fastapi/

### Tertiary (informational)
- SerpAPI hourly quota cap behavior: https://blog.apify.com/best-serpapi-alternatives/
- SEC Risk Alert: Investment Adviser Use of Social Media: https://www.sec.gov/about/offices/ocie/riskalert-socialmedia.pdf
- feedparser PyPI (last release Sep 2025): https://pypi.org/project/feedparser/
- Twitter API Basic tier limits guide: https://www.gramfunnels.com/blog/twitter-api-limits

---
*Research completed: 2026-03-30*
*Ready for roadmap: yes*
