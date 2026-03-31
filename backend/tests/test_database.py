"""
Tests for SQLAlchemy async engine configuration.
Covers: INFRA-07 — Neon connection pooling config
"""
import pytest


def test_engine_uses_pool_pre_ping():
    """
    Engine must have pool_pre_ping=True for Neon serverless cold-start handling.
    """
    pytest.skip("Requires app.database — will be enabled in Plan 03")


def test_engine_uses_pool_recycle_300():
    """
    Engine must have pool_recycle=300 to match Neon 5-min auto-suspend timeout.
    """
    pytest.skip("Requires app.database — will be enabled in Plan 03")


def test_engine_uses_asyncpg_driver():
    """
    DATABASE_URL must use postgresql+asyncpg:// scheme (not psycopg2).
    """
    pytest.skip("Requires app.database — will be enabled in Plan 03")
