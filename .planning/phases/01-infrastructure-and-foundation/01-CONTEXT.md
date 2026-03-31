# Phase 1: Infrastructure and Foundation - Context

**Gathered:** 2026-03-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Deploy the complete project infrastructure: full PostgreSQL schema on Neon with all 6 tables, Alembic migration system, two Railway services (API server + scheduler worker), APScheduler skeleton with database-level job lock, environment variable configuration, health check endpoints, and Twilio WhatsApp template submission to Meta for approval.

</domain>

<decisions>
## Implementation Decisions

### Project Structure
- **D-01:** Monorepo with `/backend` and `/frontend` directories in a single git repository. Backend is Python (FastAPI), frontend is React. Railway deploys both from the same repo with different root directories and start commands.
- **D-02:** Backend uses `pyproject.toml` for dependency management (modern Python standard). Frontend uses `package.json` with npm.

### Database Schema
- **D-03:** Full schema deployed from day one — all 6 tables (draft_items, content_bundles, agent_runs, daily_digests, watchlists, keywords) with all columns including JSONB fields for alternatives, event mode, and quality scores.
- **D-04:** Alembic for migration management. Use auto-generation as a starting point, then manually review and edit before applying. This gives control over index creation, enum types, and constraint naming.
- **D-05:** Neon connection pooling: `pool_pre_ping=True`, `pool_recycle=300`, use the `-pooler` connection string suffix for PgBouncer transaction-mode pooling.
- **D-06:** Draft status stored as PostgreSQL enum type: `pending`, `approved`, `edited_approved`, `rejected`, `expired`.
- **D-07:** JSONB array column on `draft_items` for draft alternatives (not separate rows).
- **D-08:** Indexes on: `status`, `platform`, `created_at`, `expires_at` columns across relevant tables.

### Railway Deployment
- **D-09:** Two Railway services from the same repo: API service runs `uvicorn` (single worker for Neon free tier connection limits), scheduler worker runs a Python script with `asyncio.run()` and `AsyncIOScheduler`.
- **D-10:** Dockerfile for each service (or shared Dockerfile with different CMD). Railway auto-builds from Dockerfile.
- **D-11:** Health check endpoint at `/health` for the API service. Scheduler worker health verified via Railway's process monitoring.

### APScheduler Configuration
- **D-12:** APScheduler 3.11.2 (NOT v4 alpha). `AsyncIOScheduler` in the scheduler worker process.
- **D-13:** Database-level job lock using PostgreSQL advisory locks to prevent duplicate scheduler instances during Railway zero-downtime deploys.
- **D-14:** Scheduler skeleton registers placeholder jobs for all agent schedules (Content 6am, Twitter 2h, Instagram 4h, expiry sweep 30min, digest 8am) — actual agent logic wired in later phases.

### WhatsApp Templates
- **D-15:** Three Twilio WhatsApp message templates submitted to Meta for approval:
  1. **Morning Digest** — Contains: top stories count, queue item count by platform, yesterday's approved/rejected/expired counts, priority alert summary, dashboard link
  2. **Breaking News Alert** — Contains: story headline, source, relevance score, dashboard link
  3. **Expiry Alert** — Contains: draft item summary, platform, time until expiry, dashboard link
- **D-16:** Templates use Twilio's variable placeholder syntax (`{{1}}`, `{{2}}`, etc.) for dynamic content.
- **D-17:** Template submission happens early in the phase to account for 1-7 day Meta approval turnaround.

### Environment Variables
- **D-18:** All credentials via environment variables, never hardcoded. Required vars: `DATABASE_URL`, `X_API_BEARER_TOKEN`, `X_API_KEY`, `X_API_SECRET`, `APIFY_API_TOKEN`, `ANTHROPIC_API_KEY`, `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM`, `SERPAPI_API_KEY`, `DIGEST_WHATSAPP_TO`, `FRONTEND_URL`, `JWT_SECRET`, `DASHBOARD_PASSWORD`.
- **D-19:** Use `pydantic-settings` for environment variable loading with validation and type coercion.

### Claude's Discretion
- Specific Alembic configuration (naming conventions, migration template)
- Dockerfile base image selection and layer optimization
- PostgreSQL advisory lock implementation details
- Railway service naming and configuration specifics

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Context
- `.planning/PROJECT.md` — Full project vision, constraints, key decisions
- `.planning/REQUIREMENTS.md` — All 99 v1 requirements with phase mapping
- `.planning/ROADMAP.md` — Phase 1 details, success criteria, dependencies

### Research
- `.planning/research/STACK.md` — Technology versions, installation commands, compatibility notes
- `.planning/research/ARCHITECTURE.md` — System architecture, component boundaries, build order
- `.planning/research/PITFALLS.md` — Critical pitfalls including APScheduler job lock, Neon pooling, Twilio template timing

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- None — greenfield project, no existing code

### Established Patterns
- None — patterns will be established in this phase

### Integration Points
- Neon PostgreSQL (external) — database connection via SQLAlchemy async
- Railway (external) — deployment platform for both services
- Twilio (external) — WhatsApp Business API for template submission

</code_context>

<specifics>
## Specific Ideas

- Neon requires specific SQLAlchemy config for serverless cold starts (pool_pre_ping, pool_recycle)
- APScheduler v4 is alpha — must use v3.11.2
- Railway zero-downtime deploys can briefly run two scheduler instances — advisory lock is required
- Twilio WhatsApp templates take 1-7 days for Meta approval — submit on day one of the phase

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-infrastructure-and-foundation*
*Context gathered: 2026-03-30*
