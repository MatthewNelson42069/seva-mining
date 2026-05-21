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
    # Build absolute redirect to the Vercel frontend. Without this, the
    # browser resolves a relative `Location: /seva/` against the BACKEND
    # origin and the operator ends up on the API domain seeing JSON 404
    # instead of the dashboard. Also closes an open-redirect vector by
    # restricting `next` to same-origin paths under the frontend host.
    if not next.startswith("/") or next.startswith("//"):
        # Reject absolute URLs, schemes, and protocol-relative inputs.
        # Only accept path-and-query strings rooted at the frontend host.
        raise HTTPException(status_code=400, detail="Invalid next path")
    redirect_target = settings.frontend_url.rstrip("/") + next
    response = RedirectResponse(url=redirect_target, status_code=302)
    response.set_cookie(
        key="seva_auth_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=True,
        max_age=31536000,
    )
    return response
