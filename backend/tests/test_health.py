"""
Tests for FastAPI health check endpoint.
Covers: INFRA-09 — health check endpoints
"""
import pytest


@pytest.mark.asyncio
async def test_health_endpoint_returns_200():
    """
    GET /health must return HTTP 200 with body {"status": "ok"}.
    """
    pytest.skip("Requires app.main FastAPI app — will be enabled in Plan 05")


@pytest.mark.asyncio
async def test_health_endpoint_response_body():
    """
    GET /health response body must be {"status": "ok"}.
    """
    pytest.skip("Requires app.main FastAPI app — will be enabled in Plan 05")
