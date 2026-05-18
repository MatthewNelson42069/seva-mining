"""Phase 5 stub smoke tests — confirm GET /calendar and GET /weekly-sweeps
return 200 OK with empty payloads through auth, and 401 without auth.

Phase 5, Plan 04 — verifies DB-04 (router registration + auth gating).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_current_user
from app.main import app


@pytest.fixture
def client_with_auth():
    """Override get_current_user to bypass JWT validation for smoke tests."""
    # Synthetic user; the stub endpoints do not use the returned value.
    # get_current_user returns the JWT "sub" claim (a string), so mirror that shape.
    async def _fake_user():
        return "test-user"

    app.dependency_overrides[get_current_user] = _fake_user
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def client_no_auth():
    """No auth override — endpoints should return 401 without Authorization."""
    app.dependency_overrides.pop(get_current_user, None)
    with TestClient(app) as c:
        yield c


def test_calendar_stub_returns_empty_with_auth(client_with_auth):
    response = client_with_auth.get("/calendar")
    assert response.status_code == 200, response.text
    assert response.json() == {"items": [], "total": 0}


def test_calendar_stub_returns_401_without_auth(client_no_auth):
    response = client_no_auth.get("/calendar")
    assert response.status_code == 401, (
        f"Expected 401 without auth; got {response.status_code} body={response.text!r}"
    )


def test_weekly_sweeps_stub_returns_empty_with_auth(client_with_auth):
    response = client_with_auth.get("/weekly-sweeps")
    assert response.status_code == 200, response.text
    assert response.json() == {"sweeps": [], "total": 0}


def test_weekly_sweeps_stub_returns_401_without_auth(client_no_auth):
    response = client_no_auth.get("/weekly-sweeps")
    assert response.status_code == 401, (
        f"Expected 401 without auth; got {response.status_code} body={response.text!r}"
    )
