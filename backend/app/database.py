import ssl

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings

settings = get_settings()

# asyncpg doesn't support sslmode= in the URL — strip it and use connect_args
_db_url = settings.database_url
if "sslmode=" in _db_url:
    import re
    _db_url = re.sub(r"[?&]sslmode=[^&]*", "", _db_url)
    if "?" not in _db_url and "&" in _db_url:
        _db_url = _db_url.replace("&", "?", 1)

_ssl_context = ssl.create_default_context()

engine = create_async_engine(
    _db_url,
    # Neon-specific pool config (D-05, INFRA-07).
    # quick-260421-eoe bump 5 → 15: the 7-sub-agent scheduler topology can
    # issue up to 7 parallel writes during the stagger window, and the
    # user-facing API must still serve /queue + /content_bundles on top.
    # Neon free tier allows max_connections=104 — 15 + scheduler's 15 +
    # overflow stays well under that.
    pool_size=15,
    max_overflow=10,
    pool_pre_ping=True,     # detect stale connections after Neon compute auto-suspend
    pool_recycle=300,       # 5 min matches Neon default auto-suspend timeout
    echo=False,
    connect_args={"ssl": _ssl_context},
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
