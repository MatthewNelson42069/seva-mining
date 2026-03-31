# Phase 1: Infrastructure and Foundation - Research

**Researched:** 2026-03-30
**Domain:** PostgreSQL schema design, Alembic migrations, Railway monorepo deployment, APScheduler advisory locks, Twilio WhatsApp template submission
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Monorepo with `/backend` and `/frontend` directories in a single git repository. Backend is Python (FastAPI), frontend is React. Railway deploys both from the same repo with different root directories and start commands.
- **D-02:** Backend uses `pyproject.toml` for dependency management (modern Python standard). Frontend uses `package.json` with npm.
- **D-03:** Full schema deployed from day one — all 6 tables (draft_items, content_bundles, agent_runs, daily_digests, watchlists, keywords) with all columns including JSONB fields for alternatives, event mode, and quality scores.
- **D-04:** Alembic for migration management. Use auto-generation as a starting point, then manually review and edit before applying. This gives control over index creation, enum types, and constraint naming.
- **D-05:** Neon connection pooling: `pool_pre_ping=True`, `pool_recycle=300`, use the `-pooler` connection string suffix for PgBouncer transaction-mode pooling.
- **D-06:** Draft status stored as PostgreSQL enum type: `pending`, `approved`, `edited_approved`, `rejected`, `expired`.
- **D-07:** JSONB array column on `draft_items` for draft alternatives (not separate rows).
- **D-08:** Indexes on: `status`, `platform`, `created_at`, `expires_at` columns across relevant tables.
- **D-09:** Two Railway services from the same repo: API service runs `uvicorn` (single worker for Neon free tier connection limits), scheduler worker runs a Python script with `asyncio.run()` and `AsyncIOScheduler`.
- **D-10:** Dockerfile for each service (or shared Dockerfile with different CMD). Railway auto-builds from Dockerfile.
- **D-11:** Health check endpoint at `/health` for the API service. Scheduler worker health verified via Railway's process monitoring.
- **D-12:** APScheduler 3.11.2 (NOT v4 alpha). `AsyncIOScheduler` in the scheduler worker process.
- **D-13:** Database-level job lock using PostgreSQL advisory locks to prevent duplicate scheduler instances during Railway zero-downtime deploys.
- **D-14:** Scheduler skeleton registers placeholder jobs for all agent schedules (Content 6am, Twitter 2h, Instagram 4h, expiry sweep 30min, digest 8am) — actual agent logic wired in later phases.
- **D-15:** Three Twilio WhatsApp message templates submitted to Meta for approval: Morning Digest, Breaking News Alert, Expiry Alert.
- **D-16:** Templates use Twilio's variable placeholder syntax (`{{1}}`, `{{2}}`, etc.) for dynamic content.
- **D-17:** Template submission happens early in the phase to account for 1-7 day Meta approval turnaround.
- **D-18:** All credentials via environment variables. Required vars: `DATABASE_URL`, `X_API_BEARER_TOKEN`, `X_API_KEY`, `X_API_SECRET`, `APIFY_API_TOKEN`, `ANTHROPIC_API_KEY`, `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM`, `SERPAPI_API_KEY`, `DIGEST_WHATSAPP_TO`, `FRONTEND_URL`, `JWT_SECRET`, `DASHBOARD_PASSWORD`.
- **D-19:** Use `pydantic-settings` for environment variable loading with validation and type coercion.

### Claude's Discretion

- Specific Alembic configuration (naming conventions, migration template)
- Dockerfile base image selection and layer optimization
- PostgreSQL advisory lock implementation details
- Railway service naming and configuration specifics

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| INFRA-01 | PostgreSQL database with full schema deployed on Neon (6 tables: draft_items, content_bundles, agent_runs, daily_digests, watchlists, keywords) | Schema design, SQLAlchemy models, Alembic migration init |
| INFRA-02 | Indexes on status, platform, created_at, expires_at columns for query performance | Index creation in Alembic migration, explicit index naming |
| INFRA-03 | FastAPI backend deployed on Railway with all API endpoints operational | Railway Dockerfile + railway.toml per-service config, health check pattern |
| INFRA-04 | Separate scheduler worker process deployed as second Railway service | Railway monorepo two-service config, separate Dockerfile per service |
| INFRA-05 | APScheduler with AsyncIOScheduler and database-level job lock to prevent duplicate runs during zero-downtime deploys | Advisory lock pattern with `pg_try_advisory_lock`, skeleton job registration |
| INFRA-06 | Alembic migration system for schema versioning | Alembic async init template, env.py async pattern, naming conventions |
| INFRA-07 | Neon connection pooling configured (pool_pre_ping=True, pool_recycle=300, PgBouncer transaction-mode) | Neon free tier 104 max_connections, -pooler suffix, pool_size=5 |
| INFRA-08 | Environment variable configuration for all external service credentials | pydantic-settings Settings class, .env local dev, Railway env vars |
| INFRA-09 | Health check endpoints for Railway monitoring | FastAPI `/health` endpoint, Railway health check config |
| WHAT-04 | All WhatsApp messages use Meta-approved message templates (submitted early in build) | Template submission via Twilio Console, variable syntax rules, approval timeline |
| EXEC-03 | All agent functions are async (AsyncAnthropic + AsyncIOScheduler) | AsyncIOScheduler job registration, async job functions, asyncio.run() entry point |
| EXEC-04 | Graceful error handling — agent failures logged and alerted, do not crash the worker process | Try/except in APScheduler job callbacks, separate process isolation |
</phase_requirements>

---

## Summary

Phase 1 establishes all infrastructure required to run the full system: a six-table PostgreSQL schema with JSONB columns and enum types deployed on Neon, Alembic for migration versioning, two Railway services (API + scheduler worker) built from Dockerfiles in the same monorepo, an APScheduler skeleton with PostgreSQL advisory lock job protection, pydantic-settings for environment configuration, and Twilio WhatsApp template submission to Meta.

The greenfield nature of this phase means there is no migration debt, but the full schema must be correct on the first migration — all tables, columns, indexes, and the PostgreSQL enum type must be defined explicitly (not auto-detected by Alembic alone). The most time-sensitive task is Twilio template submission, which must happen on day one of the phase to account for Meta's approval queue.

Railway's monorepo deployment model requires per-service `railway.toml` files (each specifying its own `dockerfilePath`) rather than a single shared config. The scheduler worker must be configured with `numReplicas = 1` and the PostgreSQL advisory lock provides the defense-in-depth layer for the overlap window during Railway zero-downtime deploys.

**Primary recommendation:** Start with Twilio template submission (WHAT-04), then database schema + Alembic migration, then Railway service scaffolding, then APScheduler skeleton. Parallelizing Twilio submission with local development maximizes the 1-7 day approval window.

---

## Project Constraints (from CLAUDE.md)

The following directives from CLAUDE.md are binding on all planning and implementation:

- **Package manager:** Use `uv` (not pip/venv) for Python dependencies. Use `pyproject.toml`.
- **Python version:** 3.12+ required. Current system Python is 3.9.6 — Python 3.12 must be installed (see Environment Availability).
- **APScheduler:** Version 3.11.2 only. Never upgrade to v4 alpha.
- **SQLAlchemy:** v2 patterns only. Never use `create_engine()` (sync), `Session` (sync), or v1 ORM patterns.
- **AsyncPG:** Use `postgresql+asyncpg://` DSN. Never use `requests` in async code.
- **No auto-posting:** Never implement. Not even partial.
- **Pydantic:** v2 patterns only (`model_config = ConfigDict(...)`). Never use v1 patterns.
- **Instagram scraping:** Only via `apify-client`. Never `instagram-private-api` or `instaloader`.
- **Frontend:** React 19, Tailwind v4, shadcn/ui on `tailwind-v4` branch only.
- **Auth:** Single password via bcrypt hash in env var. JWT 24h. No OAuth.
- **Schema:** Full schema from day one, keep all data forever.
- **Budget:** ~$255-275/mo total operating cost ceiling.
- **GSD workflow enforcement:** All file edits via GSD commands.

---

## Standard Stack

### Core (Phase 1 Relevant)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | 0.135.1 | HTTP API framework | Async-first, Pydantic v2 native, auto OpenAPI docs |
| Python | 3.12 | Runtime | Minimum for production target; 3.9 on system — must install 3.12 |
| uvicorn | via fastapi[standard] | ASGI server | Ships with fastapi[standard]; `--host 0.0.0.0 --port $PORT` for Railway |
| SQLAlchemy | 2.0.x | ORM + async engine | `create_async_engine` + `async_sessionmaker` + `asyncpg` |
| asyncpg | 0.30.x | Async PostgreSQL driver | Required for SQLAlchemy async; `postgresql+asyncpg://` DSN |
| Alembic | 1.14.x | Database migrations | Standard SQLAlchemy migration tool; use `alembic init -t async` |
| APScheduler | 3.11.2 | Job scheduler | Stable production version; v4 is alpha with breaking API changes |
| pydantic-settings | 2.x | Env var config | Typed Settings class with validation; auto-loads `.env` in dev |
| Twilio | 9.x | WhatsApp SDK | `client.messages.create(from_='whatsapp:+...', to='whatsapp:+...')` |
| uv | latest | Python package manager | Faster than pip, reproducible installs, `uv sync` |
| ruff | latest | Linter + formatter | Replaces flake8 + black + isort; FastAPI standard |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| python-dotenv | 1.x | Local .env loading | Dev only; pydantic-settings loads automatically |
| httpx | 0.27.x | Async HTTP client | Any additional async HTTP calls; never `requests` in async code |
| pytest + pytest-asyncio | latest | Backend testing | Async test support for FastAPI routes and DB sessions |

### Installation

```bash
# Install Python 3.12 (required — system has 3.9.6)
# macOS: brew install python@3.12
# or: uv python install 3.12

# Install uv (required)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Backend project init
mkdir -p seva-mining/backend seva-mining/scheduler
cd seva-mining/backend
uv init --python 3.12
uv add "fastapi[standard]" "sqlalchemy[asyncio]" asyncpg alembic \
        apscheduler==3.11.2 twilio \
        pydantic-settings python-dotenv httpx
uv add --dev ruff pytest pytest-asyncio

# Scheduler worker (shares same pyproject.toml or separate)
cd ../scheduler
uv init --python 3.12
uv add "sqlalchemy[asyncio]" asyncpg apscheduler==3.11.2 pydantic-settings
uv add --dev ruff pytest pytest-asyncio
```

---

## Architecture Patterns

### Recommended Project Structure

```
seva-mining/
├── backend/                        # FastAPI API service (Railway service 1)
│   ├── app/
│   │   ├── main.py                 # FastAPI app instance, lifespan, /health
│   │   ├── config.py               # pydantic-settings Settings class
│   │   ├── database.py             # async engine, session factory
│   │   └── models/
│   │       ├── __init__.py
│   │       ├── base.py             # DeclarativeBase + naming_convention
│   │       ├── draft_item.py       # draft_items table + DraftStatus enum
│   │       ├── content_bundle.py   # content_bundles table
│   │       ├── agent_run.py        # agent_runs table
│   │       ├── daily_digest.py     # daily_digests table
│   │       ├── watchlist.py        # watchlists table
│   │       └── keyword.py          # keywords table
│   ├── alembic/
│   │   ├── env.py                  # async migration env (alembic init -t async)
│   │   ├── script.py.mako
│   │   └── versions/
│   │       └── 0001_initial_schema.py
│   ├── alembic.ini
│   ├── pyproject.toml
│   ├── Dockerfile
│   └── railway.toml                # Railway service 1 config
│
├── scheduler/                      # APScheduler worker (Railway service 2)
│   ├── worker.py                   # asyncio.run() entry point + advisory lock
│   ├── config.py                   # pydantic-settings (shared pattern)
│   ├── database.py                 # same async engine pattern
│   ├── agents/
│   │   └── __init__.py             # placeholder — wired in later phases
│   ├── pyproject.toml
│   ├── Dockerfile
│   └── railway.toml                # Railway service 2 config
│
└── frontend/                       # React dashboard (later phases)
```

### Pattern 1: Alembic Async Configuration

**What:** Use `alembic init -t async` to generate an async-compatible `env.py`. The async template uses `async_engine_from_config` and `run_sync` for migration execution.

**When to use:** Always, when SQLAlchemy uses `create_async_engine`.

```python
# backend/app/models/base.py
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import MetaData

# Naming conventions prevent unnamed constraints in migrations
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
```

```python
# backend/alembic/env.py (key sections from async template)
# Source: https://github.com/sqlalchemy/alembic/blob/main/alembic/templates/async/env.py
import asyncio
from sqlalchemy.ext.asyncio import async_engine_from_config
from app.models.base import Base  # import all models before this
import app.models.draft_item      # trigger model registration
import app.models.content_bundle
# ... all model imports ...

target_metadata = Base.metadata

async def run_async_migrations():
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()

def run_migrations_online():
    asyncio.run(run_async_migrations())
```

```ini
# backend/alembic.ini - chronological file naming
file_template = %%(year)d_%%(month).2d_%%(day).2d_%%(hour).2d%%(minute).2d-%%(rev)s_%%(slug)s
```

**Commands:**
```bash
# Generate initial migration (review before applying)
cd backend && uv run alembic revision --autogenerate -m "initial_schema"
# Apply to Neon
uv run alembic upgrade head
```

### Pattern 2: Neon Async Engine Configuration

**What:** Configure `create_async_engine` with Neon-specific pooling parameters. Use the `-pooler` suffix in the hostname to route through PgBouncer in transaction mode.

```python
# backend/app/database.py
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,      # postgresql+asyncpg://.../dbname?sslmode=require
                                # hostname must end in -pooler.neon.tech for PgBouncer
    pool_size=5,                # Neon free tier: max_connections=104; stay conservative
    max_overflow=10,
    pool_pre_ping=True,         # detect stale connections after Neon compute auto-suspend
    pool_recycle=300,           # 5 min matches Neon default auto-suspend timeout
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
```

**Neon free tier facts (verified 2026-03-30):**
- Direct connection `max_connections`: ~104 (0.25 CU)
- PgBouncer `default_pool_size`: ~93 (0.9 x 104, as of Jan 2025 update)
- PgBouncer `max_client_conn`: 10,000
- PgBouncer mode: transaction (connections returned after each transaction)
- Storage: 0.5 GB per project

### Pattern 3: PostgreSQL Advisory Lock for Scheduler

**What:** Before executing any agent job, attempt `pg_try_advisory_lock(<lock_id>)` using a raw SQL call. If the lock is held (returns `false`), skip the run and log "skipped: lock held." Release with `pg_advisory_unlock` in a `finally` block.

**When to use:** In the scheduler worker process, wrapping every APScheduler job callback.

```python
# scheduler/worker.py
import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

logger = logging.getLogger(__name__)

# Stable integer IDs per job — never reuse across jobs
JOB_LOCK_IDS = {
    "twitter_agent": 1001,
    "instagram_agent": 1002,
    "content_agent": 1003,
    "expiry_sweep": 1004,
    "morning_digest": 1005,
}

async def with_advisory_lock(conn, lock_id: int, job_name: str, job_fn):
    """Wrap an async job function with a PostgreSQL advisory lock."""
    result = await conn.execute(
        text("SELECT pg_try_advisory_lock(:lock_id)"),
        {"lock_id": lock_id}
    )
    acquired = result.scalar()
    if not acquired:
        logger.info(f"Job {job_name}: skipped (lock held by another instance)")
        return
    try:
        await job_fn()
    except Exception as e:
        logger.error(f"Job {job_name}: failed with {e}", exc_info=True)
        # Do NOT re-raise — worker process must stay alive (EXEC-04)
    finally:
        await conn.execute(
            text("SELECT pg_advisory_unlock(:lock_id)"),
            {"lock_id": lock_id}
        )

async def placeholder_job(job_name: str):
    """Placeholder for agent jobs wired in later phases."""
    logger.info(f"Job {job_name}: placeholder executed (Phase 1 skeleton)")

async def main():
    scheduler = AsyncIOScheduler()

    # Register placeholder jobs (D-14)
    # Content Agent: daily at 6am
    scheduler.add_job(
        lambda: asyncio.create_task(placeholder_job("content_agent")),
        "cron", hour=6, minute=0, id="content_agent"
    )
    # Twitter Agent: every 2 hours
    scheduler.add_job(
        lambda: asyncio.create_task(placeholder_job("twitter_agent")),
        "interval", hours=2, id="twitter_agent"
    )
    # Instagram Agent: every 4 hours
    scheduler.add_job(
        lambda: asyncio.create_task(placeholder_job("instagram_agent")),
        "interval", hours=4, id="instagram_agent"
    )
    # Expiry sweep: every 30 minutes
    scheduler.add_job(
        lambda: asyncio.create_task(placeholder_job("expiry_sweep")),
        "interval", minutes=30, id="expiry_sweep"
    )
    # Morning digest: daily at 8am
    scheduler.add_job(
        lambda: asyncio.create_task(placeholder_job("morning_digest")),
        "cron", hour=8, minute=0, id="morning_digest"
    )

    scheduler.start()
    logger.info("Scheduler worker started. Jobs registered.")

    try:
        # Block forever — the scheduler runs in the background event loop
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
```

### Pattern 4: Railway Monorepo Per-Service Config

**What:** Each service gets its own `railway.toml` specifying its `dockerfilePath` and `numReplicas`. Railway reads whichever config file is assigned to the service via the dashboard or via absolute path.

```toml
# backend/railway.toml
[build]
builder = "dockerfile"
dockerfilePath = "backend/Dockerfile"

[deploy]
numReplicas = 1
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 5
healthcheckPath = "/health"
healthcheckTimeout = 10
```

```toml
# scheduler/railway.toml
[build]
builder = "dockerfile"
dockerfilePath = "scheduler/Dockerfile"

[deploy]
numReplicas = 1          # CRITICAL: exactly 1 — never autoscale the scheduler
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 5
# No healthcheckPath — worker has no HTTP port
```

```dockerfile
# backend/Dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml .
RUN pip install uv && uv sync --no-dev

COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .

# Run migrations then start server
CMD ["sh", "-c", "uv run alembic upgrade head && uv run uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1"]
```

```dockerfile
# scheduler/Dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml .
RUN pip install uv && uv sync --no-dev

COPY worker.py .
COPY agents/ ./agents/
COPY config.py .
COPY database.py .

CMD ["uv", "run", "python", "worker.py"]
```

### Pattern 5: pydantic-settings Config

**What:** Single `Settings` class loaded once per process. All required vars validated at startup — app crashes with a clear error if any are missing. Used in both backend and scheduler.

```python
# backend/app/config.py
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Database
    database_url: str  # postgresql+asyncpg://...-pooler.neon.tech/...?sslmode=require

    # External services
    anthropic_api_key: str
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_whatsapp_from: str  # whatsapp:+14155238886
    digest_whatsapp_to: str    # whatsapp:+1...
    x_api_bearer_token: str
    x_api_key: str
    x_api_secret: str
    apify_api_token: str
    serpapi_api_key: str

    # App config
    jwt_secret: str
    dashboard_password: str
    frontend_url: str

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

### Pattern 6: FastAPI Health Check + Lifespan

```python
# backend/app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.database import engine

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown
    await engine.dispose()

app = FastAPI(lifespan=lifespan)

@app.get("/health")
async def health():
    return {"status": "ok"}
```

### Pattern 7: Twilio WhatsApp Template Design

**What:** Three templates designed for Meta approval. Variable placement rules are strict — variables cannot appear at the start or end of message body, cannot be adjacent, must be sequentially numbered.

**Template 1: Morning Digest (Utility category)**
```
Template name: seva_morning_digest
Body: Daily gold sector digest for {{1}}. Top stories: {{2}}. Queue: {{3}} items pending review. Yesterday: {{4}} approved, {{5}} rejected, {{6}} expired. View dashboard: {{7}}
```

**Template 2: Breaking News Alert (Utility category)**
```
Template name: seva_breaking_news
Body: Breaking gold sector story: {{1}} (Source: {{2}}). Relevance score: {{3}}/10. Review on dashboard: {{4}}
```

**Template 3: Expiry Alert (Utility category)**
```
Template name: seva_expiry_alert
Body: High-value draft expiring soon on {{1}}: {{2}}. Expires in {{3}}. Review now: {{4}}
```

**Submission steps:**
1. Twilio Console > Messaging > Content Template Builder
2. Select "WhatsApp" channel, category "Utility"
3. Paste template body, set variable sample values (self-evident defaults)
4. Click "Save and submit for WhatsApp approval"
5. Monitor status — approval typically within 1 hour, up to 1 business day per 2025 Twilio docs (historically 1-7 days is the outer bound)

**Variable rules (enforced by Meta):**
- Sequential numbering: `{{1}}`, `{{2}}`, `{{3}}` — no gaps
- No adjacent variables (must have non-variable words between them)
- No variable at start or end of message body
- No variable-only lines
- Submitted templates cannot be edited — create new if rejected

### Anti-Patterns to Avoid

- **Running `Base.metadata.create_all()` directly:** Never do this. Always use `alembic upgrade head`. Direct create_all bypasses migration history and creates schema without version tracking.
- **Sync SQLAlchemy engine in async FastAPI:** Never use `create_engine()` (sync). Always `create_async_engine()`.
- **APScheduler v4:** Never install. PyPI has both 3.11.2 (stable) and 4.0.0a6 (alpha). Pin explicitly to 3.11.2.
- **Direct connection string without -pooler:** On Neon, direct connections bypass PgBouncer. Under concurrent load, 5 direct connections exhaust useful capacity quickly. Always use the `-pooler` hostname.
- **numReplicas > 1 for scheduler:** Setting `numReplicas = 2` on the scheduler service creates two independent APScheduler instances. The advisory lock handles overlap but doesn't fully replace correct deployment config. Lock is defense-in-depth, not a license for horizontal scaling.
- **Free-form WhatsApp messages for business-initiated alerts:** Will fail silently in Sandbox, fail loudly in production. All three notification types require approved templates before any notification logic is built.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Env var loading with type validation | Manual `os.getenv()` + casting | `pydantic-settings` | Type coercion, validation, error messages, .env support |
| DB migration versioning | Manual `CREATE TABLE` scripts | Alembic | Version history, rollback, autogenerate diff, async support |
| Advisory lock management | Custom lock table with TTLs | `pg_try_advisory_lock` / `pg_advisory_unlock` | Atomic, no table bloat, auto-released on session close |
| Async PostgreSQL connection pool | Manual asyncpg pool | SQLAlchemy async engine | Pool lifecycle, pre_ping, recycle, session management |
| WhatsApp message delivery | Direct HTTP to WhatsApp API | Twilio SDK | Template management, delivery tracking, error handling |

**Key insight:** This phase has almost no "build from scratch" work — it is configuration and wiring of well-established libraries. The complexity is in the configuration details (async Alembic env, Neon pool params, Railway per-service toml, advisory lock IDs) not in novel code.

---

## Common Pitfalls

### Pitfall 1: Alembic Autogenerate Misses Custom Types and Indexes

**What goes wrong:** Running `alembic revision --autogenerate` generates a migration that omits the PostgreSQL native enum type, has unnamed indexes, and may sequence creation incorrectly.

**Why it happens:** Alembic autogenerate works from SQLAlchemy metadata diffs, but PostgreSQL native enum types (`sa.Enum(name="draftstatus", ...)`) need to be explicitly created in the migration. The `--autogenerate` output is a starting point, not a final migration.

**How to avoid:** After autogenerate, manually review and ensure: (1) the `draftstatus` enum is created with `CREATE TYPE` before the table that uses it, (2) all indexes have explicit names matching the `ix_%(column_0_label)s` naming convention, (3) JSONB columns use `sa.JSON` or `postgresql.JSONB` type explicitly.

**Warning signs:** Migration applies without error but `\dT` in psql shows no custom types; indexes have auto-generated names that don't match convention.

### Pitfall 2: Neon Connection String Without -pooler Suffix

**What goes wrong:** Using the direct Neon connection hostname causes connections to go straight to Postgres (bypassing PgBouncer). Under concurrent load or cold starts, the pool fills and new connections fail with "remaining connection slots are reserved".

**Why it happens:** Neon provides two hostnames per project: direct (`ep-xxx.neon.tech`) and pooled (`ep-xxx-pooler.neon.tech`). The Railway env var must use the `-pooler` variant.

**How to avoid:** In the Railway environment variables, `DATABASE_URL` must contain the `-pooler` hostname. Verify by checking the Neon dashboard — Connection Details > Connection string — and selecting "Connection pooling" mode.

**Warning signs:** 500 errors during DB connection under light load; Neon dashboard showing connection count near max.

### Pitfall 3: APScheduler Duplicate Runs During Railway Zero-Downtime Deploy

**What goes wrong:** Railway's zero-downtime deploy briefly runs two scheduler worker instances simultaneously. Both try to execute the first job tick, producing duplicate placeholder logs (harmless now) but duplicate agent runs in later phases.

**Why it happens:** Railway replaces the old container with a new one but keeps the old container alive briefly to drain. If a job fires in that window, both instances execute it.

**How to avoid:** Advisory lock (D-13) prevents both instances from executing the same job. Ensure lock IDs are stable integers defined as constants, not dynamic values. Also configure `numReplicas = 1` in scheduler's `railway.toml`.

**Warning signs:** Duplicate job log entries at identical timestamps in Railway logs.

### Pitfall 4: Twilio WhatsApp Template Rejection Due to Variable Placement

**What goes wrong:** Meta rejects the template submission with a generic error. Variables placed at the beginning or end of the message body, or two variables separated only by a space, trigger automatic rejection.

**Why it happens:** Meta's template review enforces strict variable placement rules. The rules are easy to miss when iterating on template copy.

**How to avoid:** Review all three templates against the rules checklist before submission: (1) no `{{1}}` at message start or end, (2) no `{{n}} {{n+1}}` adjacent pattern, (3) provide self-evident variable samples. Test the exact template format in the Twilio Sandbox first.

**Warning signs:** Template status shows "Rejected" with rejection_reason field populated in Twilio Console; no notification received at intended WhatsApp number.

### Pitfall 5: Missing Model Imports in Alembic env.py

**What goes wrong:** `alembic revision --autogenerate` generates an empty migration (no changes detected) even though models are defined.

**Why it happens:** Alembic's `target_metadata = Base.metadata` is set, but the model module files are never imported. Python only registers SQLAlchemy models with `Base.metadata` when the module is imported, not when the file exists on disk.

**How to avoid:** In `alembic/env.py`, explicitly import every model module after setting `target_metadata`:
```python
from app.models import base  # noqa: F401
import app.models.draft_item  # noqa: F401
import app.models.content_bundle  # noqa: F401
# ... all model modules
target_metadata = base.Base.metadata
```

---

## Code Examples

### Full Schema Skeleton (SQLAlchemy Models)

```python
# backend/app/models/draft_item.py
import enum
import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Numeric, Text, DateTime, ForeignKey, Index
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, ENUM
from sqlalchemy.orm import relationship
from app.models.base import Base

class DraftStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    edited_approved = "edited_approved"
    rejected = "rejected"
    expired = "expired"

draft_status_enum = ENUM(
    "pending", "approved", "edited_approved", "rejected", "expired",
    name="draftstatus",
    create_type=False,   # created explicitly in migration, not auto-created
)

class DraftItem(Base):
    __tablename__ = "draft_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    platform = Column(String(20), nullable=False)
    status = Column(draft_status_enum, nullable=False, default="pending")
    source_url = Column(Text)
    source_text = Column(Text)
    source_account = Column(String(255))
    score = Column(Numeric(5, 2))
    quality_score = Column(Numeric(5, 2))
    alternatives = Column(JSONB, nullable=False, default=list)
    rationale = Column(Text)
    urgency = Column(String(20))
    related_id = Column(UUID(as_uuid=True), ForeignKey("draft_items.id"), nullable=True)
    rejection_reason = Column(Text)
    expires_at = Column(DateTime(timezone=True))
    decided_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_draft_items_status", "status"),
        Index("ix_draft_items_platform", "platform"),
        Index("ix_draft_items_created_at", "created_at"),
        Index("ix_draft_items_expires_at", "expires_at"),
    )
```

### Alembic Migration for Enum Type Creation

```python
# backend/alembic/versions/0001_initial_schema.py (key section)
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade():
    # Create enum type BEFORE the table that uses it
    op.execute("CREATE TYPE draftstatus AS ENUM "
               "('pending','approved','edited_approved','rejected','expired')")

    op.create_table(
        "draft_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("platform", sa.String(20), nullable=False),
        sa.Column("status",
                  postgresql.ENUM("pending","approved","edited_approved",
                                  "rejected","expired",
                                  name="draftstatus", create_type=False),
                  nullable=False, server_default="pending"),
        # ... all columns
    )
    op.create_index("ix_draft_items_status", "draft_items", ["status"])
    op.create_index("ix_draft_items_platform", "draft_items", ["platform"])
    op.create_index("ix_draft_items_created_at", "draft_items", ["created_at"])
    op.create_index("ix_draft_items_expires_at", "draft_items", ["expires_at"])

def downgrade():
    op.drop_table("draft_items")
    op.execute("DROP TYPE draftstatus")
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `alembic init` (sync) | `alembic init -t async` | Alembic 1.7+ | Correct async env.py template generated; no manual async wiring needed |
| Alembic config in `alembic.ini` only | `pyproject.toml` `[tool.alembic]` section supported | Alembic 1.16.0 | Project uses `pyproject.toml` — can put Alembic config there if preferred |
| Neon PgBouncer `default_pool_size=64` | Dynamic `0.9 × max_connections` | Jan 2025 | Free tier pool_size effectively ~93 now (was 64); `pool_size=5` app-side still correct |
| Legacy WhatsApp Templates (Twilio) | Content Templates (API-based) | April 2025 EOL | Legacy template format deprecated; must use Content Template Builder or Content API |
| `pip` + `requirements.txt` | `uv` + `pyproject.toml` | 2024-2025 mainstream | Standard for new Python projects; CLAUDE.md mandates uv |

**Deprecated/outdated:**
- **Legacy WhatsApp Templates:** EOL April 1, 2025. All new templates must use Twilio Content Template Builder. The `{{1}}` variable syntax is still correct for Content Templates.
- **Alembic sync init template:** Generates a sync `env.py`. For async SQLAlchemy, always use `alembic init -t async`.

---

## Open Questions

1. **WhatsApp Business Account status for Seva Mining**
   - What we know: Twilio template submission requires an active WhatsApp Business Account (WABA) linked to the Twilio account
   - What's unclear: Whether a WABA already exists for Seva Mining or needs to be created
   - Recommendation: Confirm WABA existence before Day 1 of the phase. If it does not exist, account setup adds 1-3 days before template submission can occur. Document in the plan as a prerequisite check.

2. **Shared vs. separate pyproject.toml for backend and scheduler**
   - What we know: CLAUDE.md mandates `pyproject.toml` for dependency management; architecture separates backend and scheduler into different directories
   - What's unclear: Whether one monorepo `pyproject.toml` with workspaces or two separate ones is preferred
   - Recommendation: Two separate `pyproject.toml` files (one in `backend/`, one in `scheduler/`) matching the Railway per-service root directory model. Simpler Dockerfiles, no workspace configuration needed.

3. **Neon project already created or needs provisioning**
   - What we know: `DATABASE_URL` must be set before migrations can run
   - What's unclear: Whether Neon account and project exist or are being created in this phase
   - Recommendation: Treat Neon project provisioning (account creation, project creation, connection string retrieval) as an explicit first task in the plan.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Python 3.12 | Backend runtime (CLAUDE.md requirement) | No | System has 3.9.6 | Install via `brew install python@3.12` or `uv python install 3.12` — no fallback, required |
| uv | Python package manager (CLAUDE.md requirement) | No | — | Install via `curl -LsSf https://astral.sh/uv/install.sh | sh` — no fallback |
| Node.js | npm / frontend tooling (Phase 1 does not require frontend) | Yes | v25.8.2 | — |
| npm | Frontend package manager | Yes | 11.11.1 | — |
| git | Version control | Yes | 2.50.1 | — |
| Docker | Dockerfile local build/test | No | — | Build and test on Railway directly; skip local Docker validation |
| Railway CLI | Service deployment | No | — | Deploy via Railway dashboard web UI; CLI install: `npm install -g @railway/cli` |

**Missing dependencies with no fallback:**
- **Python 3.12:** CLAUDE.md mandates 3.12+. System has 3.9.6. Plan must include installation as Task 0 before any backend code is written.
- **uv:** CLAUDE.md mandates uv. Plan must include installation as Task 0.

**Missing dependencies with fallback:**
- **Docker:** Not installed. Local Dockerfile validation is not possible. Fallback: test Railway deployment directly via `railway up` or push to git and let Railway build. This means Dockerfile errors are caught on Railway, not locally — add a verification step after first Railway deploy.
- **Railway CLI:** Not installed. Fallback: Railway web dashboard for initial service configuration. CLI can be added during the phase for faster iteration.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio |
| Config file | None yet — Wave 0 creates `backend/pytest.ini` |
| Quick run command | `cd backend && uv run pytest tests/ -x -q` |
| Full suite command | `cd backend && uv run pytest tests/ -v` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INFRA-01 | All 6 tables exist in Neon with correct columns | smoke (DB) | `pytest tests/test_schema.py::test_all_tables_exist -x` | No — Wave 0 |
| INFRA-02 | Indexes exist on status, platform, created_at, expires_at | smoke (DB) | `pytest tests/test_schema.py::test_indexes_exist -x` | No — Wave 0 |
| INFRA-03 | GET /health returns 200 | smoke (API) | `pytest tests/test_health.py::test_health_endpoint -x` | No — Wave 0 |
| INFRA-06 | Alembic current == head (no pending migrations) | smoke (DB) | `pytest tests/test_schema.py::test_migration_current -x` | No — Wave 0 |
| INFRA-07 | Engine uses pool_pre_ping=True, pool_recycle=300 | unit | `pytest tests/test_database.py::test_engine_config -x` | No — Wave 0 |
| INFRA-08 | Settings class raises if required env var missing | unit | `pytest tests/test_config.py::test_missing_env_var -x` | No — Wave 0 |
| INFRA-09 | /health endpoint reachable (Railway deployment) | manual smoke | Deploy + `curl https://<api-url>/health` | N/A — manual |
| INFRA-05 | Advisory lock prevents second scheduler instance from running same job | unit | `pytest tests/test_worker.py::test_advisory_lock_prevents_duplicate -x` | No — Wave 0 |
| EXEC-04 | Job exception does not crash scheduler process | unit | `pytest tests/test_worker.py::test_job_exception_isolation -x` | No — Wave 0 |
| WHAT-04 | Templates submitted and status is not "Rejected" | manual | Twilio Console verification | N/A — manual |

### Sampling Rate

- **Per task commit:** `cd backend && uv run pytest tests/ -x -q`
- **Per wave merge:** `cd backend && uv run pytest tests/ -v`
- **Phase gate:** Full suite green + manual INFRA-09 + manual WHAT-04 verification before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `backend/pytest.ini` — pytest + asyncio mode configuration
- [ ] `backend/tests/__init__.py` — test package
- [ ] `backend/tests/conftest.py` — async DB session fixture, test engine pointing to test DB or SQLite
- [ ] `backend/tests/test_schema.py` — covers INFRA-01, INFRA-02, INFRA-06
- [ ] `backend/tests/test_health.py` — covers INFRA-03
- [ ] `backend/tests/test_database.py` — covers INFRA-07
- [ ] `backend/tests/test_config.py` — covers INFRA-08
- [ ] `scheduler/tests/test_worker.py` — covers INFRA-05, EXEC-04
- [ ] Framework install in pyproject.toml dev dependencies: `pytest`, `pytest-asyncio`, `httpx` (for TestClient)

---

## Sources

### Primary (HIGH confidence)

- [Alembic async template on GitHub](https://github.com/sqlalchemy/alembic/blob/main/alembic/templates/async/env.py) — async env.py pattern
- [Alembic 1.18.4 tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html) — migration setup, naming conventions
- [Neon connection pooling docs](https://neon.com/docs/connect/connection-pooling) — PgBouncer transaction mode, -pooler suffix
- [Neon plans docs](https://neon.com/docs/introduction/plans) — free tier limits (0.5GB, 104 max_connections)
- [Neon changelog Jan 10, 2025](https://neon.com/docs/changelog/2025-01-10) — dynamic default_pool_size change
- [Twilio message template approvals](https://www.twilio.com/docs/whatsapp/tutorial/message-template-approvals-statuses) — approval statuses and timeline
- [Twilio Content Template Builder](https://www.twilio.com/docs/content/create-templates-with-the-content-template-builder) — template creation UI
- [Twilio variable syntax rules](https://www.twilio.com/docs/content/using-variables-with-content-api) — sequential numbering, adjacency, placement rules
- [Railway monorepo deployment guide](https://docs.railway.com/guides/monorepo) — per-service root directories
- [Railway config-as-code](https://docs.railway.com/config-as-code) — railway.toml format and service assignment
- [PostgreSQL advisory locks official docs](https://www.postgresql.org/docs/current/explicit-locking.html) — `pg_try_advisory_lock` semantics
- [APScheduler 3.11.2 PyPI](https://pypi.org/project/APScheduler/) — confirmed version

### Secondary (MEDIUM confidence)

- [Alembic best practices - DEV Community](https://dev.to/welel/best-practices-for-alembic-and-sqlalchemy-3b34) — naming conventions, migration review workflow
- [PostgreSQL advisory locks practical guide](https://www.ines-panker.com/2024/12/17/advisory-locks.html) — Python pattern with non-blocking try lock
- [Railway deploying monorepo two Dockerfiles](https://station.railway.com/questions/deploying-a-monorepo-with-two-dockerfile-d64425bc) — RAILWAY_DOCKERFILE_PATH variable approach
- [Twilio Legacy WhatsApp template EOL notice](https://help.twilio.com/articles/13550552351771) — April 2025 legacy template deprecation

### Tertiary (LOW confidence)

- [Neon free tiers infographic](https://www.freetiers.com/directory/neon) — supplementary free tier limits summary (cross-verified with official Neon docs)

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — versions verified against PyPI and official docs; library choices locked in CONTEXT.md
- Architecture: HIGH — patterns from ARCHITECTURE.md are pre-researched and verified; advisory lock pattern from official PostgreSQL docs
- Pitfalls: HIGH — critical pitfalls verified from official Twilio, Alembic, Neon, and Railway docs
- Environment: HIGH — direct system interrogation; tool availability confirmed by running commands

**Research date:** 2026-03-30
**Valid until:** 2026-06-30 (stable infra tools; Neon pricing/limits may change; Twilio template rules stable)
