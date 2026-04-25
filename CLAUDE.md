<!-- GSD:project-start source:PROJECT.md -->
## Project

**Seva Mining — AI Social Media Agency**

A 6-sub-agent AI system that monitors the gold sector via news feeds 24/7, drafts engagement content across 6 content types (breaking news, threads, quotes, infographics, gold media, gold history), and surfaces everything to a web dashboard for manual approval. Each sub-agent runs its own APScheduler cron every 2 hours (staggered across the 2h window). A shared Content Agent review service provides compliance gating and news ingestion for the sub-agents to call into — it is not itself scheduled. You review, approve, copy, and post. Nothing is ever posted automatically. A trimmed morning-digest job sends daily digests and alerts via WhatsApp.

> **Historical note (2026-04-19):** The original design included a fourth agent — an Instagram Agent using an Apify scraper. That agent was deprecated and fully purged on 2026-04-19 (quick task `260419-lvy`). Apify-based scraping was not viable and the ~$50/mo spend did not fit the budget. After that purge the system was three agents: Twitter, Senior, and Content. Any remaining references to Instagram in code (dormant content-agent output fields `instagram_post` / `instagram_caption` / `instagram_brief` / `instagram_carousel`, and image-render slide roles `instagram_slide_1..3`) are inert — nothing downstream consumes them.
>
> **Historical note (2026-04-20):** The Twitter Agent and the broader Senior Agent were deprecated and fully purged on 2026-04-20 (quick task `260420-sn9`). Rationale: the Twitter Agent's X API Basic tier ($100/mo) spend was not justified when the Content Agent's news-feed pipeline was already producing higher-signal drafts, and the Senior Agent had narrowed in practice to a single cron — the 07:00 morning digest. Net effect at the time was a single-agent system (Content only). (Superseded 2026-04-21 by quick task `260421-eoe` — see note below.) The scheduler runs 8 jobs: 7 sub-agents (`sub_breaking_news`, `sub_threads`, `sub_long_form`, `sub_quotes`, `sub_infographics`, `sub_video_clip`, `sub_gold_history`) each on a staggered 2h interval, plus a trimmed `morning_digest` daily cron. Content Agent (`scheduler/agents/content_agent.py`) is a library module — NOT a scheduled job — exposing `fetch_stories()` (shared SerpAPI+RSS ingestion, 30-min cache) and `review(draft)` (Haiku compliance gate) for sub-agents to call inline. `tweepy[async]>=4.14` and the `x_api_bearer_token` / `x_api_key` / `x_api_secret` env wiring are preserved because the Content Agent's `video_clip` pipeline still calls tweepy's async client to search and transcribe X video clips when a story has strong video supporting material — this is not "the Twitter Agent," just an X API read used downstream by Content. The `watchlists` table is retained in schema but was fully emptied in this purge (40 rows, all legacy Twitter + Instagram accounts) — the table is no longer read by any agent and the Watchlists UI tab has been removed. All `twitter_*` config keys were deleted. The `draft_items.platform` column stays as `String(20)` but `frontend/src/api/types.ts` narrows the Platform type to `'content'` only. 177 historical `draft_items WHERE platform='twitter'` rows were deleted from prod.
>
> **Historical note (2026-04-23):** The `sub_long_form` sub-agent was deprecated and fully purged on 2026-04-23 (quick task `260423-k8n`). Rationale: "makes things simpler" — longer-form content that warrants publication can ride under the threads sub-agent's short-thread shape; a dedicated long-form drafter added complexity without clear differentiated value. The scheduler is now a **6-sub-agent topology** (`sub_breaking_news`, `sub_threads`, `sub_quotes`, `sub_infographics`, `sub_gold_media`, `sub_gold_history`) running 7 jobs total (6 subs + `morning_digest`). The stagger-within-4h cohort collapses from offsets `[0, 17, 34]` to `[0, 17]`; the 34-minute slot is retired, not reassigned. Historical `content_bundles.content_type='long_form'` and `agent_runs.agent_name='sub_long_form'` rows are preserved in the DB — no Alembic migration, no data loss. The deprecated frontend route `/agents/long-form` is removed; bookmark-breakage is acceptable for a single-user internal tool. The `long_form_post` compat field inside `thread` draft_content (ThreadPreview.tsx, content_agent.py `_extract_check_text` thread branch) is retained — it is a thread-format feature, not a `sub_long_form` reference. This purge mirrors the `260419-lvy` (Instagram) and `260420-sn9` (Twitter + Senior) precedents; partially unwinds `260419-r0r` (long_form 400-char floor) and `260421-eoe` (the 7-sub-agent split that created `sub_long_form`).

**Core Value:** Every piece of content the system drafts must be genuinely valuable to the gold conversation it enters — a data point, an insight, a connection no one else made. If a draft wouldn't make a senior gold analyst stop scrolling, it shouldn't exist.

### Constraints

- **Budget**: ~$205-225/month total operating cost
- **X API**: Basic tier ($100/mo) — read-only access
- **News**: SerpAPI (~$50/mo) + RSS feeds (free)
- **AI**: Anthropic Claude API (~$30-50/mo)
- **Hosting**: Railway for backend (API + separate scheduler worker), Vercel for frontend (subdomain)
- **Database**: PostgreSQL via Neon (free tier, upgrade to Pro when 512MB fills)
- **WhatsApp**: Twilio (~$5/mo)
- **Stack**: FastAPI (Python) backend, React + Tailwind CSS frontend, APScheduler in separate worker process (seven scheduled jobs: 6 sub-agents + `morning_digest`)
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
| Unattended auto-posting to any platform | Scheduled or agent-driven posting (no human in the loop) is out of scope. The risk model is unattended autonomous publishing — not user-initiated posting. User-initiated approve→post-to-X (Phase B, quick-260424-l0d) is explicitly in scope: a draft only ships when the user opens the detail modal, clicks "Post to X", and confirms in a second dialog; the backend writes `draft_items.approval_state` atomically inside a single FOR-UPDATE transaction. | User-initiated approve→post via `/items/{id}/post-to-x` (single-tweet + thread; breaking_news + thread content_types only). Clipboard copy + manual paste remains available for every other format. Never run posting on a cron, and never expose a "post all queued" bulk action. |
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

## X Developer Portal — Approve→Post-to-X Runbook (Phase B, quick-260424-l0d)

Phase B's `POST /items/{id}/post-to-x` route uses `tweepy.AsyncClient` with OAuth 1.0a User Context to post on behalf of the Seva Mining X account. The X API Basic tier ($100/mo) covers the Write quota. The keys/tokens are read from env vars (`x_api_key`, `x_api_secret`, `x_access_token`, `x_access_token_secret`) and the route is gated by `X_POSTING_ENABLED=true` — when unset, the backend writes `sim-{uuid4()}` IDs without any tweepy call (D2 simulate mode).

**One-time setup at the X Developer Portal — do these in order; step 4 (Read+Write) MUST happen before step 5 (token regeneration), or the Access Token will only carry Read scope and `tweepy.create_tweet()` will return 403.**

1. Log in at https://developer.x.com/en/portal/dashboard with the Seva Mining X account.
2. Open the project containing the existing Basic-tier app (the same app whose Bearer Token already powers the Content Agent's video_clip pipeline).
3. Open the app → "Keys and tokens" tab. The "API Key" + "API Key Secret" pair is the OAuth 1.0a app key — copy these to `X_API_KEY` and `X_API_SECRET` in Railway env if not already set.
4. Open the app → "User authentication settings" → click "Set up" or "Edit". Set "App permissions" to **Read and write** (NOT "Read and write and Direct message" — DMs are out of scope and asking for unused scopes is a compliance smell). Type of App: "Web App, Automated App or Bot". Callback URI: any valid URL is fine for OAuth 1.0a token generation (e.g. `https://seva-mining-smm.vercel.app/oauth/callback` even if unused). Save.
5. Back on "Keys and tokens" → "Access Token and Secret" → click "Regenerate". The new token pair is what carries the Read+Write scope — copy these to `X_ACCESS_TOKEN` and `X_ACCESS_TOKEN_SECRET`. Old tokens (if any) are now Read-only and will silently fail for `create_tweet`.

After the token pair is in Railway env, set `X_POSTING_ENABLED=true` to flip the route from simulate mode to real posting. To roll back, set `X_POSTING_ENABLED=false` (or unset it) — the route reverts to writing sim-IDs without redeploy. Verify with: open a draft in the dashboard, click "Post to X", confirm; the toast should link to a real `https://x.com/i/web/status/{tweet_id}` URL when `X_POSTING_ENABLED=true`, or a `sim-...` ID otherwise.

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
