from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.database import engine
from app.routers.auth import router as auth_router
from app.routers.queue import router as queue_router
from app.routers.watchlists import router as watchlists_router
from app.routers.keywords import router as keywords_router
from app.routers.agent_runs import router as agent_runs_router
from app.routers.digests import router as digests_router
from app.routers.content import router as content_router
from app.routers.config import router as config_router


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
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:4173",
        _settings.frontend_url,
    ],
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


@app.get("/health")
async def health():
    """Health check endpoint for Railway monitoring. Returns 200 when app is running."""
    return {"status": "ok"}
