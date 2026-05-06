"""Tests for scheduler/config.py — Phase 2, Plan 01.

Coverage:
  - ontario_law_filter_model defaults to "claude-haiku-4-5"
  - ontario_law_filter_model is overridable via ONTARIO_LAW_FILTER_MODEL env var
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://fake-pooler.neon.tech/db?sslmode=require"
)
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test-fake")
os.environ.setdefault("X_API_BEARER_TOKEN", "x")
os.environ.setdefault("SERPAPI_API_KEY", "x")


def test_ontario_law_filter_model_default():
    """ontario_law_filter_model defaults to 'claude-haiku-4-5' when env var is unset."""
    from config import get_settings

    get_settings.cache_clear()
    # Ensure env var is not set
    os.environ.pop("ONTARIO_LAW_FILTER_MODEL", None)
    s = get_settings()
    assert s.ontario_law_filter_model == "claude-haiku-4-5", (
        f"Expected 'claude-haiku-4-5', got {s.ontario_law_filter_model!r}"
    )


def test_ontario_law_filter_model_env_override(monkeypatch):
    """ONTARIO_LAW_FILTER_MODEL env var overrides the default."""
    from config import get_settings

    monkeypatch.setenv("ONTARIO_LAW_FILTER_MODEL", "claude-haiku-test")
    get_settings.cache_clear()
    s = get_settings()
    assert s.ontario_law_filter_model == "claude-haiku-test", (
        f"Expected 'claude-haiku-test', got {s.ontario_law_filter_model!r}"
    )
    # Cleanup
    get_settings.cache_clear()
