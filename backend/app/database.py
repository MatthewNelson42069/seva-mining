from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
)
from app.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    # Neon-specific pool config (D-05, INFRA-07)
    pool_size=5,            # conservative for Neon free tier (max_connections=104)
    max_overflow=10,
    pool_pre_ping=True,     # detect stale connections after Neon compute auto-suspend
    pool_recycle=300,       # 5 min matches Neon default auto-suspend timeout
    echo=False,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:
    """FastAPI dependency that yields an async database session."""
    async with AsyncSessionLocal() as session:
        yield session
