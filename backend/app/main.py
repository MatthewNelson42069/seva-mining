from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import engine
from app.routers.agent_runs import router as agent_runs_router
from app.routers.auth import router as auth_router
from app.routers.config import router as config_router
from app.routers.content import router as content_router
from app.routers.content_bundles import router as content_bundles_router
from app.routers.digests import router as digests_router
from app.routers.keywords import router as keywords_router
from app.routers.post_to_x import router as post_to_x_router
from app.routers.queue import router as queue_router
from app.routers.calendar import router as calendar_router
from app.routers.summaries import router as summaries_router
from app.routers.watchlists import router as watchlists_router
from app.routers.weekly_sweeps import router as weekly_sweeps_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup — nothing to initialize yet (DB engine created at module import)
    yield
    # Shutdown — dispose engine pool cleanly
    await engine.dispose()


app = FastAPI(
    title="Seva Mining API",
    description="AI Social Media Agency — backend API",
    version="0.1.0",
    lifespan=lifespan,
)

_settings = get_settings()
# Build allowed origins: always include localhost for dev, plus the
# production frontend URL from env (with and without trailing slash).
_origins = [
    "http://localhost:5173",
    "http://localhost:4173",
    "https://seva-mining-smm.vercel.app",
    _settings.frontend_url.rstrip("/"),
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(dict.fromkeys(_origins)),  # deduplicate, preserve order
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(queue_router)
app.include_router(watchlists_router)
app.include_router(keywords_router)
app.include_router(agent_runs_router)
app.include_router(digests_router)
app.include_router(content_router)
app.include_router(config_router)
app.include_router(content_bundles_router)
app.include_router(post_to_x_router)  # Phase B (quick-260424-l0d)
# v3.0 Phase 9 — TENANT-04 — multi-tenant path prefix per 09-CONTEXT.md D-04.
# Three tenant-scoped routers mounted under /api/{company}. Other routers
# (auth, queue, watchlists, keywords, agent_runs, digests, content, config,
# content_bundles, post_to_x) stay at root because they are NOT tenant-scoped
# in v3.0 — single-operator login is global, queue/content/agent telemetry
# is gold-only in v3.0 (per CONTEXT.md "v3.0 keeps 'Seva Mining' wordmark on
# both tenants; per-company branding deferred to v3.1+").
app.include_router(summaries_router, prefix="/api/{company}")       # v3.0 P9 — TENANT-04
app.include_router(calendar_router, prefix="/api/{company}")        # v3.0 P9 — TENANT-04
app.include_router(weekly_sweeps_router, prefix="/api/{company}")   # v3.0 P9 — TENANT-04


@app.get("/health")
async def health():
    """Health check endpoint for Railway monitoring. Returns 200 when app is running."""
    return {"status": "ok"}
