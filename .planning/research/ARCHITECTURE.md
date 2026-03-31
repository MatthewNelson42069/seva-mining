# Architecture Research

**Domain:** AI social media monitoring and content drafting system
**Researched:** 2026-03-30
**Confidence:** HIGH

## Standard Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          EXTERNAL SOURCES                                │
│  ┌────────────┐  ┌─────────────┐  ┌────────────┐  ┌──────────────────┐  │
│  │ X API v2   │  │ Apify Actors│  │  SerpAPI   │  │  RSS Feeds       │  │
│  │ (Basic)    │  │ (Instagram) │  │  + Google  │  │  (Kitco, WGC...) │  │
│  └─────┬──────┘  └──────┬──────┘  └─────┬──────┘  └────────┬─────────┘  │
└────────┼────────────────┼───────────────┼──────────────────┼────────────┘
         │                │               │                  │
┌────────▼────────────────▼───────────────▼──────────────────▼────────────┐
│                       SCHEDULER WORKER (Railway)                         │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │                  APScheduler (separate process)                      │ │
│  │  ┌───────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │ │
│  │  │ Twitter Agent │  │ Instagram    │  │ Content Agent            │  │ │
│  │  │ (2h interval) │  │ Agent (4h)   │  │ (daily, morning)         │  │ │
│  │  └───────┬───────┘  └──────┬───────┘  └─────────┬────────────────┘  │ │
│  │          │                 │                     │                   │ │
│  │          └─────────────────▼─────────────────────┘                   │ │
│  │                   Senior Agent (orchestrator)                         │ │
│  │           (dedup, scoring, queue cap, expiry, WhatsApp)               │ │
│  └─────────────────────────────┬───────────────────────────────────────┘ │
└────────────────────────────────┼─────────────────────────────────────────┘
                                 │ writes to DB (shared PostgreSQL)
┌────────────────────────────────▼─────────────────────────────────────────┐
│                      DATABASE LAYER (Neon PostgreSQL)                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ drafts       │  │ watchlists   │  │ agent_runs   │  │ settings     │  │
│  │ (JSONB alts) │  │ (X + IG)     │  │ (run logs)   │  │ (weights,    │  │
│  │              │  │              │  │              │  │  thresholds) │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘  │
└────────────────────────────────┬─────────────────────────────────────────┘
                                 │ reads/writes via API
┌────────────────────────────────▼─────────────────────────────────────────┐
│                      FASTAPI BACKEND (Railway)                            │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │ REST API: /drafts, /approve, /reject, /settings, /watchlists, /logs  │ │
│  │ Auth: password middleware (single user)                               │ │
│  │ Twilio outbound: WhatsApp digest + alerts (triggered by scheduler)    │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
└────────────────────────────────┬─────────────────────────────────────────┘
                                 │ HTTP REST
┌────────────────────────────────▼─────────────────────────────────────────┐
│                      REACT DASHBOARD (Vercel)                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ Twitter tab  │  │ Instagram tab│  │ Content tab  │  │ Settings     │  │
│  │ (approval    │  │ (approval    │  │ (approval    │  │ (watchlists, │  │
│  │  cards)      │  │  cards)      │  │  cards)      │  │  weights,    │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │  schedules)  │  │
│                                                          └──────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Communicates With |
|-----------|----------------|-------------------|
| Twitter Agent | Monitor X API every 2h, score posts, draft reply + RT-with-comment alternatives | Senior Agent, X API v2, PostgreSQL |
| Instagram Agent | Run Apify scraper every 4h, score posts, draft comment alternatives | Senior Agent, Apify API, PostgreSQL |
| Content Agent | Ingest RSS + SerpAPI daily, deep-research stories, draft posts/threads/infographic briefs | Senior Agent, SerpAPI, RSS, Claude API, PostgreSQL |
| Senior Agent | Queue management (cap 15), deduplication, priority re-scoring, auto-expiry, WhatsApp dispatch | All specialist agents, PostgreSQL, Twilio |
| APScheduler Worker | Trigger agents on cron intervals, isolated from API server to prevent cascading failures | All agents, PostgreSQL (job store) |
| FastAPI Backend | Serve REST API for dashboard, handle approval state transitions, validate auth | PostgreSQL, Twilio SDK, React dashboard |
| PostgreSQL (Neon) | Persist all drafts with state machine, agent run logs, settings, watchlists | FastAPI backend, Scheduler worker |
| React Dashboard | Human approval interface — review, inline edit, approve/reject drafts; manage settings | FastAPI backend only |
| Twilio WhatsApp | Outbound-only notifications: morning digest and breaking alerts | FastAPI backend (outbound SDK calls) |
| Claude API | LLM reasoning for all four agents — scoring, drafting, evaluation | Called by agents via Anthropic SDK |

## Recommended Project Structure

```
seva-mining/
├── backend/                      # FastAPI application (Railway service 1)
│   ├── app/
│   │   ├── main.py               # FastAPI app, lifespan, middleware
│   │   ├── auth.py               # Password middleware
│   │   ├── database.py           # SQLAlchemy engine, session factory
│   │   ├── models/               # SQLAlchemy ORM models
│   │   │   ├── draft.py          # drafts table, state enum
│   │   │   ├── watchlist.py      # watchlist entries
│   │   │   ├── agent_run.py      # run log entries
│   │   │   └── settings.py       # configurable parameters
│   │   ├── schemas/              # Pydantic request/response models
│   │   ├── routers/              # Endpoint groupings
│   │   │   ├── drafts.py         # GET, PATCH approve/reject/edit
│   │   │   ├── settings.py       # watchlist CRUD, weight config
│   │   │   └── logs.py           # agent run log queries
│   │   └── services/
│   │       └── notifications.py  # Twilio WhatsApp outbound
│   ├── alembic/                  # DB migrations
│   └── requirements.txt
│
├── scheduler/                    # APScheduler worker (Railway service 2)
│   ├── worker.py                 # Scheduler entry point, job registration
│   ├── agents/
│   │   ├── base.py               # Shared Claude client, DB session, logging
│   │   ├── senior_agent.py       # Orchestrator: dedup, queue cap, expiry, WhatsApp
│   │   ├── twitter_agent.py      # X API fetch, score, draft
│   │   ├── instagram_agent.py    # Apify fetch, score, draft
│   │   └── content_agent.py      # RSS + SerpAPI fetch, research, draft
│   ├── integrations/
│   │   ├── x_api.py              # X API v2 client, rate-limit handling
│   │   ├── apify_client.py       # Apify Actor runner, retry logic
│   │   ├── serpapi_client.py     # SerpAPI news search
│   │   └── rss_reader.py         # Feedparser RSS ingestion
│   └── requirements.txt
│
├── frontend/                     # React + Tailwind (Vercel)
│   ├── src/
│   │   ├── components/
│   │   │   ├── ApprovalCard/     # Core card: platform badge, drafts, actions
│   │   │   ├── DraftAlternatives/# Tabbed draft selector with inline edit
│   │   │   └── RelatedBadge/     # Cross-platform deduplication link
│   │   ├── pages/
│   │   │   ├── Twitter.tsx
│   │   │   ├── Instagram.tsx
│   │   │   ├── Content.tsx
│   │   │   └── Settings.tsx
│   │   ├── api/                  # Typed fetch wrappers to FastAPI
│   │   └── store/                # React Query or SWR for server state
│   └── package.json
│
└── .planning/                    # Project planning (not deployed)
```

### Structure Rationale

- **backend/ vs scheduler/:** Two separate Railway services with separate `requirements.txt`. The scheduler crash does not kill the dashboard API. Both share the same PostgreSQL database — the only coupling point.
- **agents/base.py:** All agents inherit Claude client initialization, DB session management, and structured run logging. Eliminates duplication and ensures every run is logged consistently.
- **integrations/:** Platform clients are isolated. Rate limit logic, retry logic, and API key config live here — agents call clean interfaces, not raw HTTP.
- **frontend/store/:** Use React Query (or SWR) — not Redux — for server state. All state is owned by the FastAPI backend. The dashboard polls or fetches on demand; no complex local state management needed.

## Architectural Patterns

### Pattern 1: Orchestrator-Worker (Hub-and-Spoke)

**What:** Senior Agent is the single coordinator. Twitter, Instagram, and Content agents are workers that produce candidate drafts but never interact with each other. All cross-cutting concerns (dedup, queue cap, expiry, notifications) flow through the Senior Agent only.

**When to use:** Exactly this case — a fixed set of specialized workers each producing independently scored items that need centralized arbitration before reaching the user.

**Trade-offs:** Simple to reason about and debug. Bottleneck is the Senior Agent, but given the low volume (15-item queue cap), this is never a problem. Workers cannot directly react to each other's output without going through the orchestrator.

```python
# scheduler/agents/senior_agent.py (conceptual)
class SeniorAgent:
    def process_batch(self, raw_candidates: list[Candidate]) -> None:
        deduplicated = self._deduplicate(raw_candidates)
        scored = self._rescore_priority(deduplicated)
        within_cap = self._enforce_queue_cap(scored, cap=15)
        self._persist_drafts(within_cap)
        self._send_whatsapp_alerts(within_cap)
```

### Pattern 2: State Machine for Draft Lifecycle

**What:** Every draft row has an explicit `status` column with allowed transitions enforced at the API layer (not just the DB). Valid states: `pending` -> `approved` | `edited_approved` | `rejected` (with required reason) | `expired` (auto by scheduler). No backward transitions.

**When to use:** Any human-approval workflow where audit trail matters and invalid state transitions must be prevented at the application boundary.

**Trade-offs:** Slightly more code for the transition guards, but prevents bugs where expired drafts get accidentally approved. Makes the audit log trivial.

```python
# backend/app/routers/drafts.py (conceptual)
VALID_TRANSITIONS = {
    "pending": {"approved", "edited_approved", "rejected"},
    # expired is set only by the scheduler
}

def transition_draft(draft_id, new_status, reason=None):
    draft = get_draft(draft_id)
    if new_status not in VALID_TRANSITIONS.get(draft.status, set()):
        raise HTTPException(400, f"Cannot transition from {draft.status} to {new_status}")
    if new_status == "rejected" and not reason:
        raise HTTPException(400, "Rejection reason required")
    draft.status = new_status
    draft.rejection_reason = reason
    draft.decided_at = utcnow()
```

### Pattern 3: JSONB Array for Draft Alternatives

**What:** Draft alternatives (2-3 per post) are stored as a JSONB array on the draft row rather than a child table. Each alternative is a structured object with `text`, `type` (reply/rt-with-comment/thread-format/long-form), and `selected` flag.

**When to use:** When alternatives are always displayed together, never filtered or queried independently, and the set is bounded and small.

**Trade-offs:** Simpler schema, single-row fetch for the full approval card. Cannot easily aggregate "which alternative type gets chosen most" without JSONB operators — acceptable for v1, queryable when needed for the learning loop.

```sql
-- drafts table (simplified)
CREATE TABLE drafts (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    platform    TEXT NOT NULL,         -- 'twitter' | 'instagram' | 'content'
    status      TEXT NOT NULL DEFAULT 'pending',
    source_url  TEXT,
    source_text TEXT,
    score       NUMERIC(4,2),
    alternatives JSONB NOT NULL,       -- [{text, type, selected}, ...]
    rationale   TEXT,
    urgency     TEXT,
    related_id  UUID REFERENCES drafts(id),  -- dedup link
    created_at  TIMESTAMPTZ DEFAULT now(),
    expires_at  TIMESTAMPTZ,
    decided_at  TIMESTAMPTZ,
    rejection_reason TEXT
);
```

### Pattern 4: Separate Scheduler Worker with Shared DB

**What:** APScheduler runs as a fully independent Python process (separate Railway service). It writes directly to the same PostgreSQL database the FastAPI backend reads from. No message queue between them — the DB is the integration point.

**When to use:** Low-volume, low-latency-tolerance background jobs (2-4h intervals). A message queue (Celery/Redis/RabbitMQ) adds operational complexity with no benefit at this scale.

**Trade-offs:** Dead simple ops. The shared DB creates a coupling point, but since both services only write to their own domains (scheduler writes drafts, API reads and updates status), contention is minimal. The scheduler never updates draft status; the API never triggers agents.

## Data Flow

### Agent Run Flow (Scheduler)

```
APScheduler cron fires (e.g., every 2h for Twitter Agent)
    |
    v
Twitter Agent: fetch X API (keyword/watchlist search)
    |
    v
Filter by engagement gate (500+ likes OR watchlist 50+)
    |
    v
Apply recency decay (full at 1h, 50% at 4h, expired at 6h)
    |
    v
Score each post (likes x1 + RTs x2 + replies x1.5 + authority + relevance)
    |
    v
Claude API: draft 2-3 reply alternatives + 2-3 RT-with-comment alternatives
    |
    v
Agent self-evaluation: quality rubric (relevance, originality, tone, no company mention)
    |
    v
Senior Agent: deduplicate against existing pending drafts
    |
    v
Senior Agent: enforce 15-item queue cap (lowest score items dropped)
    |
    v
Write passing drafts to PostgreSQL (status = 'pending')
    |
    v
Senior Agent: WhatsApp alert if breaking news (3x engagement spike or price move)
    |
    v
Log agent run (items_found, items_queued, items_filtered, errors)
```

### Human Approval Flow (Dashboard)

```
React Dashboard polls GET /drafts?status=pending
    |
    v
Renders approval cards per platform tab
    |
    v
User reviews card: reads source excerpt, alternatives, rationale, score
    |
    v
  [Approve] -> PATCH /drafts/{id}/approve  -> status = 'approved'
  [Edit+Approve] -> PATCH /drafts/{id}/approve + edited_text -> status = 'edited_approved'
  [Reject] -> PATCH /drafts/{id}/reject + reason -> status = 'rejected'
    |
    v
User copies approved draft text to clipboard
    |
    v
User follows direct link to source post on platform
    |
    v
User manually pastes and posts — system never auto-posts
```

### WhatsApp Notification Flow

```
Senior Agent (scheduler) identifies notification trigger:
  - Morning: daily digest at configured time
  - Breaking: engagement spike (3x+ normal) or gold price move
  - Expiring: high-value draft approaching expiry window
    |
    v
Senior Agent calls FastAPI endpoint OR directly calls Twilio SDK
(recommendation: Senior Agent calls Twilio SDK directly — no need to route
 through API for an outbound-only notification)
    |
    v
Twilio sends WhatsApp message to configured number
    |
    v
No inbound handling — notifications only, one-way
```

### Settings Change Flow

```
User edits settings in React Dashboard
    |
    v
PATCH /settings (weights, thresholds, watchlists, schedule config)
    |
    v
FastAPI writes to settings/watchlist tables in PostgreSQL
    |
    v
Scheduler worker reads settings from DB at the START of each agent run
(not cached in memory — always reads fresh from DB so changes take effect
 on the next scheduled run without a restart)
```

## Integration Points

### External Services

| Service | Integration Pattern | Key Constraints | Notes |
|---------|---------------------|-----------------|-------|
| X API v2 (Basic) | Direct HTTP via `tweepy` or `httpx`, OAuth 2.0 Bearer Token | 15-min rate limit windows, read-only, 7-day lookback | Track `X-Rate-Limit-Remaining` header; implement exponential backoff; 2h polling interval naturally stays under limits |
| Apify (Instagram) | Apify Python client, synchronous Actor run-and-fetch | ~$50/mo credit, scraping latency 30-60s per run | Implement retry with 3 attempts; treat partial results as success (best-effort reliability per requirements) |
| SerpAPI | REST API, simple `requests` call | ~$50/mo, 100 searches/mo on basic plan | Cache results within same Content Agent run to avoid duplicate calls; one call per news topic |
| RSS Feeds | `feedparser` library, no auth | No rate limits, free | Parse on each Content Agent run; track `etag`/`last-modified` headers to detect new items |
| Claude API (Anthropic) | `anthropic` Python SDK, direct API calls | ~$30-50/mo budget | Use `claude-3-haiku` for scoring/filtering (cheap), `claude-3-5-sonnet` for drafting (quality); structured output via tool use |
| Twilio WhatsApp | `twilio` Python SDK, outbound only | WhatsApp Business requires pre-approved message templates for business-initiated messages | Register digest and alert templates in Twilio Console before first deploy |
| Neon PostgreSQL | `psycopg2` / `asyncpg` via SQLAlchemy | Free tier: 512MB storage; no connection pooling on free tier | Use PgBouncer or SQLAlchemy pool size=5; upgrade to Neon Pro ($19/mo) when approaching 512MB |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| Scheduler Worker <-> PostgreSQL | Direct SQLAlchemy writes (drafts, run logs) | Scheduler ONLY writes; never updates draft status after creation |
| FastAPI Backend <-> PostgreSQL | SQLAlchemy reads + status transition writes | API ONLY updates status/decided_at; never creates draft rows |
| React Dashboard <-> FastAPI Backend | REST over HTTPS, JSON | Dashboard is stateless — all truth lives in the DB via the API |
| Senior Agent <-> Twilio | Direct SDK call from scheduler process | Avoids unnecessary HTTP round-trip through the API server for outbound notifications |
| Twitter Agent -> Senior Agent | In-process Python function call (same scheduler process) | All four agents run in the same worker process — no IPC needed |

## Suggested Build Order

The dependency graph dictates this sequence:

1. **Database schema + migrations** — Everything depends on the schema. Full schema from day one (all columns, JSONB structure, state enum). No iterative schema evolution.

2. **FastAPI backend skeleton** — Auth middleware, basic CRUD for drafts (read + status transitions), settings endpoints. The dashboard cannot function without this.

3. **React dashboard** — Build against the API. Approval cards, tabs, inline editing, clipboard copy. The human workflow needs to be verifiable before agents produce real data.

4. **Scheduler worker skeleton** — APScheduler setup, shared DB session, run logging infrastructure, base agent class. Wire up without real agent logic first.

5. **Twitter Agent** — Highest signal-to-noise, most structured API. Implement X API integration, scoring, and drafting. First end-to-end test of the full pipeline.

6. **Senior Agent core** — Dedup, queue cap, expiry. Needed before adding more agents to avoid queue pollution.

7. **Instagram Agent** — Apify integration is less predictable than X API. Build with retry logic and best-effort semantics after the core pipeline is proven.

8. **Content Agent** — Most complex (RSS + SerpAPI + deep research + format decision logic + infographic brief). Build last when the plumbing is fully tested.

9. **WhatsApp notifications** — Twilio template registration takes 24-48h for WhatsApp Business approval. Register templates early, implement notifications once agents are producing real output.

10. **Settings page + configurability** — Wire all scoring weights, thresholds, and schedules to DB-driven config. Polish once agents are producing correct output.

## Anti-Patterns

### Anti-Pattern 1: Running APScheduler Inside the FastAPI Process

**What people do:** Add `AsyncIOScheduler` to the FastAPI lifespan and run agents in the same process as the API server.

**Why it's wrong:** A long-running agent job (especially Content Agent doing deep research) blocks FastAPI workers. More critically, on Railway with multiple worker processes (Gunicorn), you get N scheduler instances running simultaneously, causing duplicated agent runs and duplicate drafts in the queue. The API server and the scheduler have completely different SLA requirements — coupling them means a scheduler crash takes down the dashboard.

**Do this instead:** Separate Railway services. Scheduler worker runs as a single-process Python script (`python worker.py`). Shares only the PostgreSQL database with the API.

### Anti-Pattern 2: Storing Draft Alternatives as Child Table Rows

**What people do:** Create a `draft_alternatives` table with a foreign key to `drafts`, one row per alternative.

**Why it's wrong:** Alternatives are always fetched together, displayed together, and operated on together. A join on every approval card fetch adds complexity with zero benefit. The set is bounded (2-3 items). Querying "which alternative was chosen" requires JSONB operators either way since the user may edit the text.

**Do this instead:** JSONB array on the draft row. Single-row fetch returns everything needed to render a complete approval card.

### Anti-Pattern 3: Auto-Posting or Removing the Human Gate

**What people do:** Once the pipeline is working well, add a confidence threshold that auto-approves and posts high-scoring drafts.

**Why it's wrong:** The core value proposition of the system — and the non-negotiable constraint — is that every post is manually reviewed. Auto-posting removes the human check on the "no company mention" and "no financial advice" rules. A single hallucinated reply that mentions Seva Mining or implies a buy signal is a reputational risk that no confidence score can fully eliminate.

**Do this instead:** Keep the approval gate forever. The friction of copy-paste is the point.

### Anti-Pattern 4: Per-Run Settings Cache in Agent Memory

**What people do:** Load scoring weights and watchlists once at worker startup and cache them in agent instance variables.

**Why it's wrong:** The user changes watchlist or scoring weights via the dashboard; the scheduler worker never sees the change until it restarts. This is a subtle, hard-to-diagnose bug.

**Do this instead:** Agents read all configurable parameters from PostgreSQL at the start of each run. At this polling frequency (every 2-4h), the DB read is negligible overhead and ensures settings changes take effect on the next run.

### Anti-Pattern 5: Using a Message Queue Between Scheduler and API

**What people do:** Add Redis + Celery (or RabbitMQ) so agents publish draft events and the API consumes them.

**Why it's wrong:** At 15 drafts per cycle and 2-4h intervals, a message queue adds significant operational complexity (another Railway service, connection management, dead-letter handling) with no throughput benefit. The shared PostgreSQL database is a perfectly adequate integration point at this volume.

**Do this instead:** Scheduler writes to PostgreSQL; API reads from PostgreSQL. The DB is the queue. Add a message broker only if volume grows to warrant it (likely never for this single-user system).

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| Single user (current) | Monolith split only at scheduler/API boundary. Neon free tier. Single-instance scheduler. |
| Second client (v2) | Introduce `client_id` tenant column on all tables. Separate scheduler job sets per client. Upgrade Neon to Pro. |
| 10+ clients | Extract agents to separate microservices with a proper job queue (Celery + Redis). Multi-tenant auth. Dedicated DB per client or row-level security. |

### Scaling Priorities

1. **First bottleneck:** Neon free tier storage (512MB). Symptom: write errors. Fix: upgrade to Neon Pro ($19/mo). Trigger: approaching 400MB.
2. **Second bottleneck:** Claude API costs. Symptom: bill exceeds budget. Fix: replace scoring/filtering calls with `claude-3-haiku` (10x cheaper than Sonnet), reserve Sonnet for final draft generation only.

## Sources

- [AI Agent Orchestration Patterns - Azure Architecture Center](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/ai-agent-design-patterns) — HIGH confidence
- [Multi-Agent Patterns: Orchestrators, Workers, and Pipelines](https://aiagentsblog.com/blog/multi-agent-patterns/) — MEDIUM confidence
- [Agent Orchestration Patterns: Swarm vs Mesh vs Hierarchical vs Pipeline](https://dev.to/jose_gurusup_dev/agent-orchestration-patterns-swarm-vs-mesh-vs-hierarchical-vs-pipeline-b40) — MEDIUM confidence
- [APScheduler PyPI documentation](https://pypi.org/project/APScheduler/) — HIGH confidence
- [Scheduled Jobs with FastAPI and APScheduler - Sentry](https://sentry.io/answers/schedule-tasks-with-fastapi/) — MEDIUM confidence
- [X API Rate Limits - Official Docs](https://docs.x.com/x-api/fundamentals/rate-limits) — HIGH confidence
- [Build a Secure Twilio Webhook with Python and FastAPI - Twilio Official](https://www.twilio.com/en-us/blog/build-secure-twilio-webhook-python-fastapi) — HIGH confidence
- [Why All Your Workflows Should Be Postgres Rows - DBOS](https://www.dbos.dev/blog/why-workflows-should-be-postgres-rows) — MEDIUM confidence
- [Human-in-the-Loop patterns - Cloudflare Agents docs](https://developers.cloudflare.com/agents/guides/human-in-the-loop/) — HIGH confidence
- [How to Build Production-Ready AI Agents with RAG and FastAPI - The New Stack](https://thenewstack.io/how-to-build-production-ready-ai-agents-with-rag-and-fastapi/) — MEDIUM confidence

---
*Architecture research for: AI social media monitoring and content drafting system (Seva Mining)*
*Researched: 2026-03-30*
