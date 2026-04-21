"""
Shared test fixtures for scheduler tests.

Env-var defaults are set at import time so that any test which imports
``config.get_settings()`` (which is ``@lru_cache``'d) sees a fully populated
Settings object regardless of test collection order. Without this,
alphabetically-earlier test modules freeze the Settings cache without keys
like ``FRED_API_KEY`` / ``METALPRICEAPI_API_KEY``, causing later
``test_market_snapshot.py`` tests to read stale cached config.
"""
import os

# Required for config.Settings to instantiate successfully.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://fake-pooler.neon.tech/db?sslmode=require")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test-fake")
os.environ.setdefault("TWILIO_ACCOUNT_SID", "x")
os.environ.setdefault("TWILIO_AUTH_TOKEN", "x")
os.environ.setdefault("TWILIO_WHATSAPP_FROM", "whatsapp:+1x")
os.environ.setdefault("DIGEST_WHATSAPP_TO", "whatsapp:+1x")
os.environ.setdefault("X_API_BEARER_TOKEN", "test-bearer-token")
os.environ.setdefault("X_API_KEY", "test-key")
os.environ.setdefault("X_API_SECRET", "test-secret")
os.environ.setdefault("SERPAPI_API_KEY", "x")
os.environ.setdefault("FRONTEND_URL", "https://x.com")

# Market snapshot external APIs — must be present BEFORE any test imports
# config.get_settings() because the @lru_cache freezes the first call.
os.environ.setdefault("FRED_API_KEY", "test-fred-key")
os.environ.setdefault("METALPRICEAPI_API_KEY", "test-metals-key")
