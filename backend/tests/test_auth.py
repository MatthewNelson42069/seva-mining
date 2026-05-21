"""
Cookie-token auth endpoint and dependency tests.
Replaces the old JWT/bcrypt auth tests (quick-260521-9ze).
"""
import inspect
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.database import get_db
from app.main import app

# ===========================================================================
# Test 1-3: GET /auth/token-set redirects + cookie
# ===========================================================================

@pytest.mark.asyncio
async def test_token_set_valid_sets_cookie_and_redirects(client):
    """GET /auth/token-set?token=<valid> → 302, seva_auth_token cookie set."""
    token = "test-dashboard-token-for-tests-xyz"
    response = await client.get(
        f"/auth/token-set?token={token}",
        follow_redirects=False,
    )
    assert response.status_code == 302
    # Location header points to /
    assert response.headers.get("location") == "/"
    # Cookie is set
    set_cookie = response.headers.get("set-cookie", "")
    assert "seva_auth_token=" in set_cookie
    assert token in set_cookie
    assert "httponly" in set_cookie.lower()
    assert "samesite=lax" in set_cookie.lower()
    assert "secure" in set_cookie.lower()
    assert "max-age=31536000" in set_cookie.lower()


@pytest.mark.asyncio
async def test_token_set_valid_custom_next(client):
    """GET /auth/token-set?token=<valid>&next=/juno/calendar → 302, location=/juno/calendar."""
    token = "test-dashboard-token-for-tests-xyz"
    response = await client.get(
        f"/auth/token-set?token={token}&next=/juno/calendar",
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "/juno/calendar" in response.headers.get("location", "")


@pytest.mark.asyncio
async def test_token_set_wrong_token_returns_403(client):
    """GET /auth/token-set?token=wrong → 403, no set-cookie header."""
    response = await client.get(
        "/auth/token-set?token=wrongtoken",
        follow_redirects=False,
    )
    assert response.status_code == 403
    assert "set-cookie" not in response.headers


@pytest.mark.asyncio
async def test_token_set_missing_token_returns_422(client):
    """GET /auth/token-set (no token) → 422 (FastAPI required query param)."""
    response = await client.get("/auth/token-set", follow_redirects=False)
    assert response.status_code == 422


# ===========================================================================
# Test 5-7: Protected route with cookie auth (mocked DB to avoid table errors)
# ===========================================================================

def _make_mock_db_for_queue():
    """Mock AsyncSession that returns an empty list on execute (queue list)."""
    mock_db = AsyncMock()
    execute_result = MagicMock()
    scalars_result = MagicMock()
    scalars_result.all.return_value = []
    execute_result.scalars.return_value = scalars_result
    execute_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=execute_result)
    return mock_db


@pytest.mark.asyncio
async def test_protected_route_with_valid_cookie():
    """GET /queue with valid seva_auth_token cookie → 200."""
    token = "test-dashboard-token-for-tests-xyz"
    mock_db = _make_mock_db_for_queue()

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get("/queue", cookies={"seva_auth_token": token})
        assert response.status_code == 200
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_protected_route_with_wrong_cookie():
    """GET /queue with wrong cookie value → 403."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/queue", cookies={"seva_auth_token": "wrongtoken"})
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_protected_route_with_no_cookies():
    """GET /queue with no cookies → 403."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/queue")
    assert response.status_code == 403


# ===========================================================================
# Test 8: Timing-safe comparison
# ===========================================================================

def test_get_current_session_token_uses_compare_digest():
    """get_current_session_token uses secrets.compare_digest (timing-safe, not ==)."""
    from app.dependencies import get_current_session_token
    source = inspect.getsource(get_current_session_token)
    assert "compare_digest" in source, (
        "get_current_session_token must use secrets.compare_digest() "
        "for timing-safe comparison, not naive =="
    )


# ===========================================================================
# Test 9: Health check (public route still works)
# ===========================================================================

@pytest.mark.asyncio
async def test_health_no_auth_required(client):
    """GET /health works without any cookie (sanity check, AUTH-09)."""
    response = await client.get("/health")
    assert response.status_code == 200
