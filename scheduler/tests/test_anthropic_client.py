"""Tests for scheduler/anthropic_client.py — v3.1 Phase 12 per-tenant
Anthropic resolver.

Covers D-05 acceptance criteria:
    (a) seva → SEVA_ANTHROPIC_API_KEY routing
    (b) juno → JUNO_ANTHROPIC_API_KEY routing
    (c) WARN-once on fallback (per company_id per process)
    (d) STRICT mode raises when per-tenant key unset
    (e) Cache returns same instance for same (company_id, timeout)
"""
from __future__ import annotations

import logging
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Reset Settings lru_cache between tests so monkeypatch.setenv takes effect.
# Same pattern used by scheduler/tests/test_config.py.
from config import get_settings  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_resolver_state(monkeypatch):
    """Clear resolver caches + Settings lru_cache before each test.

    get_settings() is @lru_cache'd so a previous test's env can leak into
    the next test's Settings() unless we clear the cache. The resolver's
    _client_cache + _warned_companies are module-level dicts/sets that
    also need fresh state per test.
    """
    # Clear Settings lru_cache (forces a fresh Settings() read of env)
    get_settings.cache_clear()

    # Lazy import so this fixture works even if anthropic_client failed to
    # import in a prior test (defensive — should never happen).
    from anthropic_client import _client_cache, _warned_companies

    _client_cache.clear()
    _warned_companies.clear()

    yield

    get_settings.cache_clear()
    _client_cache.clear()
    _warned_companies.clear()


def test_get_anthropic_client_seva_routes_to_seva_key(monkeypatch):
    monkeypatch.setenv("SEVA_ANTHROPIC_API_KEY", "sk-seva-AAAAAAAA")
    monkeypatch.setenv("JUNO_ANTHROPIC_API_KEY", "sk-juno-CCCCCCCC")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-shared-BBBBBBBB")
    monkeypatch.delenv("ANTHROPIC_RESOLVER_STRICT", raising=False)

    from anthropic_client import get_anthropic_client

    client = get_anthropic_client("seva")
    assert client.api_key == "sk-seva-AAAAAAAA"


def test_get_anthropic_client_juno_routes_to_juno_key(monkeypatch):
    monkeypatch.setenv("SEVA_ANTHROPIC_API_KEY", "sk-seva-AAAAAAAA")
    monkeypatch.setenv("JUNO_ANTHROPIC_API_KEY", "sk-juno-CCCCCCCC")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-shared-BBBBBBBB")
    monkeypatch.delenv("ANTHROPIC_RESOLVER_STRICT", raising=False)

    from anthropic_client import get_anthropic_client

    client = get_anthropic_client("juno")
    assert client.api_key == "sk-juno-CCCCCCCC"


def test_fallback_emits_warn_once_per_company(monkeypatch, caplog):
    # Per-tenant unset; only shared key present
    monkeypatch.delenv("SEVA_ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("JUNO_ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-shared-BBBBBBBB")
    monkeypatch.delenv("ANTHROPIC_RESOLVER_STRICT", raising=False)

    from anthropic_client import get_anthropic_client

    with caplog.at_level(logging.WARNING, logger="anthropic_client"):
        # Three calls for seva → exactly one WARN
        c1 = get_anthropic_client("seva")
        c2 = get_anthropic_client("seva")
        c3 = get_anthropic_client("seva")
        # One call for juno → adds one more WARN (different company)
        get_anthropic_client("juno")

    seva_warns = [
        r
        for r in caplog.records
        if r.levelname == "WARNING" and "company_id=seva" in r.getMessage()
    ]
    juno_warns = [
        r
        for r in caplog.records
        if r.levelname == "WARNING" and "company_id=juno" in r.getMessage()
    ]
    assert len(seva_warns) == 1, f"expected exactly 1 seva WARN, got {len(seva_warns)}"
    assert len(juno_warns) == 1, f"expected exactly 1 juno WARN, got {len(juno_warns)}"
    assert "SEVA_ANTHROPIC_API_KEY" in seva_warns[0].getMessage()
    assert "JUNO_ANTHROPIC_API_KEY" in juno_warns[0].getMessage()

    # All three seva calls return the same cached client built with shared key
    assert c1.api_key == "sk-shared-BBBBBBBB"
    assert c1 is c2 is c3


def test_strict_mode_raises_on_missing_per_tenant_key(monkeypatch):
    monkeypatch.delenv("JUNO_ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-shared-BBBBBBBB")
    monkeypatch.setenv("ANTHROPIC_RESOLVER_STRICT", "true")

    from anthropic_client import get_anthropic_client

    with pytest.raises(RuntimeError) as exc_info:
        get_anthropic_client("juno")

    msg = str(exc_info.value)
    assert "ANTHROPIC_RESOLVER_STRICT=true" in msg
    assert "JUNO_ANTHROPIC_API_KEY" in msg


def test_cache_returns_same_instance_for_same_args(monkeypatch):
    monkeypatch.setenv("SEVA_ANTHROPIC_API_KEY", "sk-seva-AAAAAAAA")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-shared-BBBBBBBB")
    monkeypatch.delenv("ANTHROPIC_RESOLVER_STRICT", raising=False)

    from anthropic_client import get_anthropic_client

    c1 = get_anthropic_client("seva", timeout=60.0)
    c2 = get_anthropic_client("seva", timeout=60.0)
    assert c1 is c2, "same (company_id, timeout) must return cached identity"

    c3 = get_anthropic_client("seva", timeout=30.0)
    assert c1 is not c3, "different timeout must build a new client"
    assert c3.api_key == "sk-seva-AAAAAAAA"
