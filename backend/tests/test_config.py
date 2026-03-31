"""
Tests for pydantic-settings config loading.
Covers: INFRA-08 — environment variable configuration
"""
import pytest


def test_missing_env_var_raises():
    """
    Settings class must raise ValidationError if a required env var is missing.
    This test will be enabled when app/config.py exists (Plan 03).
    """
    pytest.skip("Requires app.config — will be enabled in Plan 03")


def test_settings_loads_from_env(monkeypatch):
    """
    Settings class loads all required vars when present in environment.
    """
    pytest.skip("Requires app.config — will be enabled in Plan 03")
