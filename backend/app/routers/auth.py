import secrets

from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse

from app.config import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/token-set")
async def token_set(token: str, next: str = "/"):
    """Validate ?token= against SEVA_DASHBOARD_TOKEN; set cookie; 302 to next.

    Called by the frontend bootstrap (main.tsx) when the operator visits
    the dashboard with ?token=<value> in the URL. On success, sets a
    1-year HttpOnly+SameSite=Lax+Secure cookie and redirects to the clean
    URL. On failure, returns 403 with no cookie set.

    Uses secrets.compare_digest for timing-safe comparison (quick-260521-9ze).
    """
    settings = get_settings()
    if not secrets.compare_digest(token, settings.seva_dashboard_token):
        raise HTTPException(status_code=403, detail="Invalid token")
    response = RedirectResponse(url=next, status_code=302)
    response.set_cookie(
        key="seva_auth_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=True,
        max_age=31536000,
    )
    return response
