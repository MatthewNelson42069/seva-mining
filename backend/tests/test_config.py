"""
Tests for pydantic-settings config loading.
Covers: INFRA-08 — environment variable configuration
"""
import os
import pytest
from pydantic import ValidationError


def test_missing_env_var_raises(monkeypatch):
    """
    Settings class must raise ValidationError if DATABASE_URL is missing.
    """
    # Remove DATABASE_URL from environment before importing Settings
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    # Clear the lru_cache so Settings() is re-evaluated
    from app.config import get_settings
    get_settings.cache_clear()
    with pytest.raises(ValidationError):
        from app.config import Settings
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_settings_loads_from_env(monkeypatch):
    """
    Settings loads all required vars when present in environment.
    """
    required_vars = {
        "DATABASE_URL": "postgresql+asyncpg://test-pooler.neon.tech/testdb?sslmode=require",
        "ANTHROPIC_API_KEY": "sk-ant-test",
        "TWILIO_ACCOUNT_SID": "ACtest",
        "TWILIO_AUTH_TOKEN": "authtest",
        "TWILIO_WHATSAPP_FROM": "whatsapp:+14155238886",
        "DIGEST_WHATSAPP_TO": "whatsapp:+10000000000",
        "X_API_BEARER_TOKEN": "bearertest",
        "X_API_KEY": "keytest",
        "X_API_SECRET": "secrettest",
        "APIFY_API_TOKEN": "apifytest",
        "SERPAPI_API_KEY": "serpapitest",
        "JWT_SECRET": "jwtsecrettest",
        "DASHBOARD_PASSWORD": "passwordtest",
        "FRONTEND_URL": "https://test.sevamining.com",
    }
    for k, v in required_vars.items():
        monkeypatch.setenv(k, v)
    from app.config import get_settings
    get_settings.cache_clear()
    from app.config import Settings
    settings = Settings()
    assert settings.database_url == required_vars["DATABASE_URL"]
    assert settings.anthropic_api_key == "sk-ant-test"
