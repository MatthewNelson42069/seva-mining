from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
)
from config import get_settings


def _make_async_url(url: str) -> str:
    """Convert a standard PostgreSQL URL to asyncpg-compatible format.

    Neon (and most hosted Postgres) gives URLs with ?sslmode=require, but
    asyncpg uses ?ssl=require instead.  Also ensures the scheme uses the
    asyncpg driver prefix.
    """
    # Normalise scheme to postgresql+asyncpg://
    url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    # asyncpg does not accept sslmode=; translate to ssl=
    url = url.replace("sslmode=require", "ssl=require")
    url = url.replace("sslmode=prefer", "ssl=prefer")
    url = url.replace("sslmode=disable", "ssl=False")
    return url


settings = get_settings()

engine = create_async_engine(
    _make_async_url(settings.database_url),
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=300,
    echo=False,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:
    """Yields an async database session for scheduler jobs."""
    async with AsyncSessionLocal() as session:
        yield session
