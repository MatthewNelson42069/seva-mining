from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.database import engine
from app.routers.auth import router as auth_router


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

app.include_router(auth_router)


@app.get("/health")
async def health():
    """Health check endpoint for Railway monitoring. Returns 200 when app is running."""
    return {"status": "ok"}
