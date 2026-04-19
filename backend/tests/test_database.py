"""
Tests for SQLAlchemy async engine configuration.
Covers: INFRA-07 — Neon connection pooling config
"""
import pytest


@pytest.fixture(autouse=True)
def set_db_env(monkeypatch):
    """Provide a valid DATABASE_URL so Settings() can instantiate."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://fake-pooler.neon.tech/testdb?sslmode=require")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "ACtest")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "authtest")
    monkeypatch.setenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
    monkeypatch.setenv("DIGEST_WHATSAPP_TO", "whatsapp:+10000000000")
    monkeypatch.setenv("X_API_BEARER_TOKEN", "bearertest")
    monkeypatch.setenv("X_API_KEY", "keytest")
    monkeypatch.setenv("X_API_SECRET", "secrettest")
    monkeypatch.setenv("APIFY_API_TOKEN", "apifytest")
    monkeypatch.setenv("SERPAPI_API_KEY", "serpapitest")
    monkeypatch.setenv("JWT_SECRET", "a" * 32)  # >=32 bytes to pass validator
    monkeypatch.setenv("DASHBOARD_PASSWORD", "password")
    monkeypatch.setenv("FRONTEND_URL", "https://test.sevamining.com")
    from app.config import get_settings
    get_settings.cache_clear()


def test_engine_uses_pool_pre_ping():
    """
    Engine must have pool_pre_ping=True for Neon serverless cold-start handling.
    """
    import importlib

    import app.database
    importlib.reload(app.database)
    from app.database import engine
    assert engine.pool._pre_ping is True


def test_engine_uses_pool_recycle_300():
    """
    Engine must have pool_recycle=300 to match Neon 5-min auto-suspend timeout.
    """
    import importlib

    import app.database
    importlib.reload(app.database)
    from app.database import engine
    assert engine.pool._recycle == 300


def test_engine_uses_asyncpg_driver():
    """
    DATABASE_URL must use postgresql+asyncpg:// scheme (not psycopg2 or sync).
    """
    import importlib

    import app.database
    importlib.reload(app.database)
    from app.database import engine
    assert engine.url.drivername.startswith("postgresql+asyncpg")
