import jwt
from fastapi import Depends, HTTPException, Path, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth import decode_token
from app.companies import ACTIVE_COMPANIES, CompanyId

bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> str:
    try:
        payload = decode_token(credentials.credentials)
        return payload["sub"]
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


# v3.0 Phase 9 — TENANT-04 — multi-tenant path-prefix dep (per 09-CONTEXT.md D-04).
# Slug regex ^[a-z][a-z0-9-]{1,19}$ is enforced via Path(..., pattern=...) so
# FastAPI returns 422 on regex mismatch BEFORE this dep body runs. The 404
# path is only hit when the slug matches the regex but is not in
# ACTIVE_COMPANIES (e.g. /api/seva-old/summaries → 404).
async def get_current_company(
    company: str = Path(..., pattern=r"^[a-z][a-z0-9-]{1,19}$"),
) -> CompanyId:
    """Validate :company path parameter against ACTIVE_COMPANIES.

    Returns the company slug as a typed Literal so downstream callers
    (scoped_summaries, etc.) get type-narrowed access (CompanyId, not raw str).
    Will be wired into router prefixes in Wave 2 — provided here in Wave 1
    so the scoped_*() helpers have a typed input source.
    """
    if company not in ACTIVE_COMPANIES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown company: {company}",
        )
    return company  # type: ignore[return-value]
