"""
Tests for FastAPI health check endpoint.
Covers: INFRA-09 — health check endpoints, INFRA-03 — FastAPI backend
"""
import os

import pytest
from fastapi.testclient import TestClient

# Set required env vars before importing app (Settings validates at import)
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://fake-pooler.neon.tech/testdb?sslmode=require")
os.environ.setdefault("ANTHROPIC_API_KEY", "test")
os.environ.setdefault("TWILIO_ACCOUNT_SID", "test")
os.environ.setdefault("TWILIO_AUTH_TOKEN", "test")
os.environ.setdefault("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
os.environ.setdefault("DIGEST_WHATSAPP_TO", "whatsapp:+10000000000")
os.environ.setdefault("X_API_BEARER_TOKEN", "test")
os.environ.setdefault("X_API_KEY", "test")
os.environ.setdefault("X_API_SECRET", "test")
os.environ.setdefault("APIFY_API_TOKEN", "test")
os.environ.setdefault("SERPAPI_API_KEY", "test")
os.environ.setdefault("JWT_SECRET", "test")
os.environ.setdefault("DASHBOARD_PASSWORD", "test")
os.environ.setdefault("FRONTEND_URL", "https://test.sevamining.com")

from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_health_endpoint_returns_200(client):
    """GET /health must return HTTP 200."""
    response = client.get("/health")
    assert response.status_code == 200


def test_health_endpoint_response_body(client):
    """GET /health must return {"status": "ok"}."""
    response = client.get("/health")
    assert response.json() == {"status": "ok"}
