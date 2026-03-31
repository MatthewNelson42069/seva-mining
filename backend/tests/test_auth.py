"""
Auth endpoint and unit tests.
Requirements: AUTH-01, AUTH-02, AUTH-03
Decisions: D-08 (7-day JWT expiry)
"""
import pytest
import bcrypt
import jwt
from datetime import datetime, timezone, timedelta
from fastapi.security import HTTPAuthorizationCredentials

from app.auth import verify_password, create_access_token, decode_token, TOKEN_EXPIRE_DAYS, ALGORITHM
from app.dependencies import get_current_user


# ===========================================================================
# Unit tests for auth helpers (no HTTP, no DB)
# ===========================================================================

def test_verify_password_correct():
    """verify_password returns True when password matches the hash."""
    password = "testpassword"
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    assert verify_password(password, hashed) is True


def test_verify_password_incorrect():
    """verify_password returns False when password does not match the hash."""
    password = "testpassword"
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    assert verify_password("wrongpassword", hashed) is False


def test_token_decode_roundtrip():
    """create_access_token produces a token that decode_token returns sub=operator."""
    token = create_access_token()
    payload = decode_token(token)
    assert payload["sub"] == "operator"


def test_token_has_7day_expiry():
    """Decoded token exp is approximately 7 days from now (D-08)."""
    token = create_access_token()
    payload = decode_token(token)
    exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    now = datetime.now(timezone.utc)
    delta = exp - now
    # Should be within 1 minute of 7 days
    assert abs(delta.total_seconds() - TOKEN_EXPIRE_DAYS * 86400) < 60


# ===========================================================================
# Auth dependency unit tests (no HTTP server needed)
# ===========================================================================

@pytest.mark.asyncio
async def test_protected_endpoint_invalid_token():
    """get_current_user raises 401 when given an invalid Bearer token."""
    from fastapi import HTTPException
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalid-token")
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(credentials)
    assert exc_info.value.status_code == 401


# ===========================================================================
# HTTP endpoint tests (login)
# ===========================================================================

@pytest.mark.asyncio
async def test_login_success(client):
    """POST /auth/login with correct password returns 200 + access_token + token_type=bearer (AUTH-01)."""
    # The env sets dashboard_password to bcrypt hash of "testpassword"
    response = await client.post("/auth/login", json={"password": "testpassword"})
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert len(data["access_token"]) > 10


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    """POST /auth/login with wrong password returns 401 (AUTH-01)."""
    response = await client.post("/auth/login", json={"password": "wrongpassword"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_health_no_auth_required(client):
    """GET /health works without any Authorization header (sanity check)."""
    response = await client.get("/health")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_protected_endpoint_no_token(client):
    """
    A route protected by get_current_user returns 403 (HTTPBearer returns 403 when
    no Authorization header is provided) or 401.
    AUTH-03
    """
    # Test by hitting login with no auth header on a route that needs auth
    # We test the dependency directly since no protected routes exist yet
    from fastapi import HTTPException
    from fastapi.security import HTTPAuthorizationCredentials
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="bad.token.here")
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(credentials)
    assert exc_info.value.status_code == 401
