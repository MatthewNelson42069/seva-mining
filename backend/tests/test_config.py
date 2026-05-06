"""
Tests for pydantic-settings config loading.
Covers: INFRA-08 — environment variable configuration
"""
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
        "SERPAPI_API_KEY": "serpapitest",
        "JWT_SECRET": "a" * 32,  # >=32 bytes to pass validator
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


def test_jwt_secret_valid_length_passes(monkeypatch):
    """JWT_SECRET of exactly 32 bytes is accepted."""
    required = {
        "DATABASE_URL": "postgresql+asyncpg://test-pooler.neon.tech/testdb?sslmode=require",
        "ANTHROPIC_API_KEY": "sk-ant-test",
        "X_API_BEARER_TOKEN": "bearertest",
        "JWT_SECRET": "a" * 32,  # exactly at boundary
        "DASHBOARD_PASSWORD": "bcrypt-hash-placeholder",
    }
    for k, v in required.items():
        monkeypatch.setenv(k, v)
    from app.config import get_settings
    get_settings.cache_clear()
    from app.config import Settings
    settings = Settings()
    assert settings.jwt_secret == "a" * 32


def test_jwt_secret_too_short_raises(monkeypatch):
    """JWT_SECRET shorter than 32 bytes raises ValidationError with length in message."""
    required = {
        "DATABASE_URL": "postgresql+asyncpg://test-pooler.neon.tech/testdb?sslmode=require",
        "ANTHROPIC_API_KEY": "sk-ant-test",
        "X_API_BEARER_TOKEN": "bearertest",
        "JWT_SECRET": "a" * 25,  # too short
        "DASHBOARD_PASSWORD": "bcrypt-hash-placeholder",
    }
    for k, v in required.items():
        monkeypatch.setenv(k, v)
    from app.config import get_settings
    get_settings.cache_clear()
    from app.config import Settings
    with pytest.raises(ValidationError) as exc_info:
        Settings()
    err_str = str(exc_info.value)
    assert "JWT_SECRET must be at least 32 bytes" in err_str
    assert "25" in err_str  # actual length surfaced


# ---------------------------------------------------------------------------
# Phase 2, Plan 01 — ontario_law_filter_model config tests
# ---------------------------------------------------------------------------


def test_ontario_law_filter_model_default(monkeypatch):
    """ontario_law_filter_model defaults to 'claude-haiku-4-5' when env var is unset."""
    required = {
        "DATABASE_URL": "postgresql+asyncpg://test-pooler.neon.tech/testdb?sslmode=require",
        "ANTHROPIC_API_KEY": "sk-ant-test",
        "X_API_BEARER_TOKEN": "bearertest",
        "JWT_SECRET": "a" * 32,
        "DASHBOARD_PASSWORD": "bcrypt-hash-placeholder",
    }
    for k, v in required.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("ONTARIO_LAW_FILTER_MODEL", raising=False)
    from app.config import Settings, get_settings

    get_settings.cache_clear()
    s = Settings()
    assert s.ontario_law_filter_model == "claude-haiku-4-5", (
        f"Expected 'claude-haiku-4-5', got {s.ontario_law_filter_model!r}"
    )


def test_ontario_law_filter_model_env_override(monkeypatch):
    """ONTARIO_LAW_FILTER_MODEL env var overrides the default in backend config."""
    required = {
        "DATABASE_URL": "postgresql+asyncpg://test-pooler.neon.tech/testdb?sslmode=require",
        "ANTHROPIC_API_KEY": "sk-ant-test",
        "X_API_BEARER_TOKEN": "bearertest",
        "JWT_SECRET": "a" * 32,
        "DASHBOARD_PASSWORD": "bcrypt-hash-placeholder",
        "ONTARIO_LAW_FILTER_MODEL": "claude-haiku-test",
    }
    for k, v in required.items():
        monkeypatch.setenv(k, v)
    from app.config import Settings, get_settings

    get_settings.cache_clear()
    s = Settings()
    assert s.ontario_law_filter_model == "claude-haiku-test", (
        f"Expected 'claude-haiku-test', got {s.ontario_law_filter_model!r}"
    )
