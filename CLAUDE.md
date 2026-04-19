<!-- GSD:project-start source:PROJECT.md -->
## Project

**Seva Mining — AI Social Media Agency**

A three-agent AI system that monitors the gold sector on X (Twitter) and news feeds 24/7, drafts engagement content, and surfaces everything to a web dashboard for manual approval. The system handles research, scoring, and drafting — you review, approve, copy, and post. Nothing is ever posted automatically. The Senior Agent sends daily digests and alerts via WhatsApp.

> **Historical note (2026-04-19):** The original design included a fourth agent — an Instagram Agent using an Apify scraper. That agent was deprecated and fully purged on 2026-04-19 (quick task `260419-lvy`). Apify-based scraping was not viable and the ~$50/mo spend did not fit the budget. The system is now three agents: Twitter, Senior, and Content. Any remaining references to Instagram in code (dormant content-agent output fields `instagram_post` / `instagram_caption` / `instagram_brief` / `instagram_carousel`, and image-render slide roles `instagram_slide_1..3`) are inert — nothing downstream consumes them.

**Core Value:** Every piece of content the system drafts must be genuinely valuable to the gold conversation it enters — a data point, an insight, a connection no one else made. If a draft wouldn't make a senior gold analyst stop scrolling, it shouldn't exist.

### Constraints

- **Budget**: ~$205-225/month total operating cost
- **X API**: Basic tier ($100/mo) — read-only access
- **News**: SerpAPI (~$50/mo) + RSS feeds (free)
- **AI**: Anthropic Claude API (~$30-50/mo)
- **Hosting**: Railway for backend (API + separate scheduler worker), Vercel for frontend (subdomain)
- **Database**: PostgreSQL via Neon (free tier, upgrade to Pro when 512MB fills)
- **WhatsApp**: Twilio (~$5/mo)
- **Stack**: FastAPI (Python) backend, React + Tailwind CSS frontend, APScheduler in separate worker process (three scheduled jobs: twitter_agent, content_agent, senior_agent)
- **Auth**: Simple password login, single user
- **Schema**: Full schema from day one including all columns for alternatives, event mode, quality scores. JSONB array for draft alternatives. Keep all data forever (no retention policy).
<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->
## Technology Stack

## Recommended Stack
### Core Technologies
| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| FastAPI | 0.135.1 | Python HTTP API framework | Async-first, Pydantic v2 native, auto OpenAPI docs. Industry standard for modern Python APIs. `fastapi[standard]` installs uvicorn + all essentials. |
| Python | 3.12+ | Runtime | 3.12 is the stable production target; 3.10 is minimum for FastAPI 0.135+. 3.12 has measurable performance improvements over 3.10/3.11. |
| Uvicorn | latest (via fastapi[standard]) | ASGI server | Ships with FastAPI standard install. For Railway deployment, run `uvicorn app.main:app --host 0.0.0.0 --port $PORT`. |
| React | 19 | Frontend UI framework | Latest stable. Removes need for `forwardRef`, improved concurrent rendering. This is a single-user internal tool — React 19 + Vite is the fastest path to a usable approval dashboard. |
| Vite | 6.x | Frontend build tool | Paired with React 19 via `npm create vite@latest -- --template react-ts`. SWC transformer enabled by default for faster hot reload. |
| Tailwind CSS | 4.x | Utility CSS | v4 integrates directly as a Vite plugin (`@tailwindcss/vite`) — no PostCSS config needed. Major DX improvement over v3 setup. |
| PostgreSQL (Neon) | 16 (managed) | Primary database | Neon free tier (512MB) is sufficient for v1. Serverless compute scale-to-zero, PgBouncer connection pooling built-in. Connect via `-pooler` endpoint. |
| SQLAlchemy | 2.0.x | ORM + query builder | `async_sessionmaker` + `asyncpg` driver is the correct pairing for FastAPI async. v2 API only — never mix v1 patterns. |
| Alembic | 1.14.x | Database migrations | The standard migration tool for SQLAlchemy. Use `alembic upgrade head` on deploy, before app starts. Never call `Base.metadata.create_all()` directly. |
| APScheduler | 3.11.2 | Job scheduler | Runs in the separate Railway worker process. `AsyncIOScheduler` with cron triggers for agent runs. v3 is stable production; v4 is still alpha (avoid). Requires single-process deployment — Gunicorn multi-worker would spawn duplicate schedulers. |
| anthropic | 0.86.0 | Claude API SDK | Official Python SDK. Async client (`AsyncAnthropic`) pairs naturally with FastAPI. Use for all LLM calls — message drafting, scoring, agent reasoning. |
| Twilio | 9.x | WhatsApp notifications | Official Python SDK. `client.messages.create(from_='whatsapp:+...', to='whatsapp:+...')`. Pre-register message templates for outbound notifications outside 24h window. |
| tweepy | 4.x | X (Twitter) API client | Official Python library for X API v2. Basic tier ($100/mo) gives read access — use `Client` (not legacy `API` class which is v1.1 only). |
| feedparser | 6.0.x | RSS ingestion | Battle-tested universal feed parser (15+ years). Handles RSS 0.9x/1.0/2.0 and Atom. Last release: Sep 2025. Single call: `feedparser.parse(url)`. |
| serpapi | latest | News search | Official SerpAPI Python client. Google News search endpoint for structured current-events data. Supplement RSS with keyword-driven searches. |
### Supporting Libraries
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| asyncpg | 0.30.x | Async PostgreSQL driver | Required for SQLAlchemy async. Use `postgresql+asyncpg://` DSN. Set `pool_pre_ping=True` and `pool_recycle=300` for Neon's serverless cold start behavior. |
| pydantic | 2.x (via FastAPI) | Request/response validation | Ships with FastAPI. Use `model_config = ConfigDict(from_attributes=True)` for ORM model serialization. |
| pydantic-settings | 2.x | Environment config | Typed settings from `.env` / environment variables. Single `Settings` class injected as FastAPI dependency. |
| python-dotenv | 1.x | Local .env loading | Only needed for local development. pydantic-settings loads it automatically in dev. |
| httpx | 0.27.x | Async HTTP client | Used by anthropic SDK internally. Also use directly for any additional API calls (SerpAPI, external webhooks). Do not mix with `requests` in async code. |
| passlib + bcrypt | passlib 1.7.x | Password hashing | For the single-user password auth. Hash the password at setup time, compare on login. No need for full OAuth machinery. |
| python-jose | 3.x | JWT tokens | Session token after password login. Short-lived JWTs stored in localStorage on the frontend. |
| TanStack Query | 5.x | Frontend server state | React Query v5. Handles API data fetching, caching, and background refetching for the dashboard. Each approval tab (Twitter, Content) gets independent query keys. |
| Zustand | 5.x | Frontend client state | Lightweight store for UI-only state: active tab, modal open/closed, inline edit mode, optimistic approval state before server confirms. Pair with TanStack Query — don't store server data here. |
| shadcn/ui | latest (Tailwind v4 branch) | UI component library | Copy-paste components, not a dependency. Approval cards, buttons, badges, tabs. Uses Radix UI primitives for accessibility. Verify Tailwind v4 compatibility — the `tailwind-v4` branch of shadcn is the correct one. |
| date-fns | 3.x | Date formatting | Recency decay display, timestamp formatting on approval cards. Lighter than dayjs for tree-shaking. |
### Development Tools
| Tool | Purpose | Notes |
|------|---------|-------|
| uv | Python package manager | Replaces pip + venv. Dramatically faster installs. `uv sync` for reproducible envs. Standard in new Python projects as of 2025. |
| ruff | Python linter + formatter | Replaces flake8 + black + isort in one tool. FastAPI's own codebase uses it. |
| pytest + pytest-asyncio | Backend testing | `pytest-asyncio` for async route and agent tests. Use `anyio` backend. |
| Vitest | Frontend unit testing | Native Vite testing. Faster than Jest for Vite projects. |
| Railway CLI | Deployment | `railway up` for deploy. Separate services for API and worker are configured in `railway.toml`. |
## Installation
# Backend (Python — using uv)
# Dev dependencies
# Frontend
# shadcn/ui (run after Tailwind v4 is configured)
## Alternatives Considered
| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| APScheduler 3.x (worker process) | Celery + Redis | If you need distributed workers across multiple machines or >100 concurrent tasks. Overkill here — adds Redis infrastructure cost (~$15/mo) with no benefit for a single-user 3-agent system. |
| APScheduler 3.x (worker process) | ARQ + Redis | Good choice if you already have Redis. ARQ is async-native and pairs naturally with FastAPI. Viable swap if you need job queuing (not just cron). Adds Redis dependency. |
| tweepy v2 Client | python-twitter-v2 / httpx direct | Tweepy is the community standard, actively maintained. Only use httpx direct if you need endpoints Tweepy doesn't expose (rare for Basic read-only). |
| feedparser | fastfeedparser | fastfeedparser is ~10x faster but less battle-tested on malformed feeds. Worth considering if ingesting >1,000 feeds/run. Overkill for 4 feeds. |
| Neon (serverless Postgres) | Supabase Postgres | Supabase bundles auth, storage, realtime — all unused here. Neon is leaner and Railway is the deployment target, not Supabase's stack. |
| shadcn/ui | Mantine / Ant Design | shadcn gives unstyled primitives that compose cleanly with Tailwind. Full component libraries ship their own CSS systems that fight Tailwind v4. |
| TanStack Query + Zustand | Redux Toolkit | Redux is overkill for a single-user internal tool with no complex client-side business logic. TanStack Query handles 90% of state. |
## What NOT to Use
| Avoid | Why | Use Instead |
|-------|-----|-------------|
| APScheduler 4.0 alpha | Still pre-release as of Apr 2025. API changed significantly from v3. No stable migration guide exists yet. | APScheduler 3.11.2 stable |
| SQLAlchemy 1.x / ORM v1 patterns | FastAPI async requires v2 `async_sessionmaker` and `AsyncSession`. v1 `Session` blocks the event loop. Pydantic v1 support also deprecated in FastAPI 0.135+. | SQLAlchemy 2.0 only |
| `requests` library in async routes | Blocks the event loop. Any sync I/O inside an async FastAPI route blocks all concurrent requests. | `httpx` with `async with AsyncClient()` |
| `AsyncIOScheduler` inside Gunicorn multi-worker | Each Gunicorn worker spawns its own scheduler — agents would run N times per cycle (N = worker count). Use a dedicated single-process worker. | APScheduler in a separate Railway service with `--workers 1` |
| Auto-posting to any platform | Out of scope by design. Never implement. Even accidental partial implementation creates compliance and reputational risk for the client. | Clipboard copy + direct link only |
| Pydantic v1 (`from pydantic import BaseModel` with v1 patterns) | FastAPI 0.135+ deprecates v1 support. Will break on Python 3.14+. | Pydantic v2 patterns: `model_config = ConfigDict(...)` |
| Celery for this use case | Adds Redis broker, separate worker, Celery Beat, and operational overhead for 3 cron jobs. The complexity-to-benefit ratio is wrong for this scale. | APScheduler in dedicated worker process |
| `create_engine()` (sync SQLAlchemy) | Blocks event loop in async FastAPI context. | `create_async_engine()` with `asyncpg` |
## Stack Patterns by Variant
- The API service runs FastAPI via `uvicorn`. The scheduler worker runs `python -m app.worker` — a script that starts `AsyncIOScheduler` and blocks via `asyncio.run()`. Configure as two separate Railway services in one project. Both share the same Neon database. Worker has no public port.
- Each agent (Senior, Content, Twitter) is a Python module called by APScheduler jobs, not a microservice. All agents run in the same scheduler worker process. They communicate via the PostgreSQL database (not queues). This is the simplest correct architecture for the scale and budget.
- Single password stored as bcrypt hash in an environment variable (not in DB). On login, compare hash, return a short-lived JWT (24h). Frontend stores JWT in localStorage and sends as `Authorization: Bearer` header. No refresh token needed for a single-user internal tool.
## Version Compatibility
| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| FastAPI 0.135.x | Pydantic 2.x only | Pydantic v1 deprecated. FastAPI 0.135+ will fail on v1 patterns with Python 3.14+. |
| SQLAlchemy 2.0 + asyncpg | FastAPI 0.135+ | Only use `create_async_engine` and `AsyncSession`. v1 `Session` is incompatible with async routes. |
| APScheduler 3.11.2 | Python 3.8-3.13 | v4 alpha has breaking API changes. Do not upgrade mid-project without testing. |
| React 19 | shadcn/ui (tailwind-v4 branch) | shadcn's main branch may still target React 18 / Tailwind v3. Verify you're on the `tailwind-v4` branch when running `npx shadcn@latest init`. |
| Tailwind CSS 4.x | @tailwindcss/vite (not PostCSS plugin) | v4 ships a dedicated Vite plugin. The separate `@tailwindcss/postcss` package is needed only for non-Vite setups. Do not install both. |
| anthropic 0.86.0 | Python 3.9+ | `AsyncAnthropic` client for use in async FastAPI routes and APScheduler async jobs. |
## Sources
- FastAPI PyPI — version 0.135.1 confirmed: https://pypi.org/project/fastapi/
- Anthropic SDK PyPI — version 0.86.0 confirmed: https://pypi.org/project/anthropic/
- APScheduler PyPI — stable 3.11.2, alpha 4.0.0a6 confirmed: https://pypi.org/project/APScheduler/
- Neon connection pooling docs — PgBouncer transaction mode, `-pooler` endpoint pattern: https://neon.com/docs/connect/connection-pooling
- Neon + FastAPI async guide: https://neon.com/guides/fastapi-async
- SQLAlchemy 2.0 + asyncpg patterns (MEDIUM confidence, multiple consistent sources): https://leapcell.io/blog/building-high-performance-async-apis-with-fastapi-sqlalchemy-2-0-and-asyncpg
- APScheduler multi-worker caution (MEDIUM confidence, community): https://github.com/fastapi/fastapi/discussions/9143
- TanStack Query v5 + Zustand recommended pattern (MEDIUM confidence): https://reactdeveloperx.blogspot.com/2025/08/next-gen-react-state-management-with_14.html
- shadcn Tailwind v4 compatibility: https://ui.shadcn.com/docs/tailwind-v4
- React 19 + Vite + Tailwind v4 setup: https://medium.com/@shavinathsaumye/setting-up-a-react-19-vite-tailwind-css-v4-project-e06fd031fac0
- Railway FastAPI deployment guide: https://docs.railway.com/guides/fastapi
- feedparser PyPI (last release Sep 2025): https://pypi.org/project/feedparser/
- SerpAPI Python client: https://serpapi.com/integrations/python
- Twilio WhatsApp Python: https://www.twilio.com/docs/whatsapp/quickstart
- Tweepy v2 Client (X API v2): https://www.tweepy.org/
- ARQ vs APScheduler vs Celery comparison (MEDIUM confidence): https://leapcell.io/blog/celery-versus-arq-choosing-the-right-task-queue-for-python-applications
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd:quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd:debug` for investigation and bug fixing
- `/gsd:execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd:profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
