from fastapi import APIRouter, HTTPException, status

from app.auth import create_access_token, verify_password
from app.config import get_settings
from app.schemas.auth import LoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest):
    settings = get_settings()
    if not verify_password(body.password, settings.dashboard_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password",
        )
    token = create_access_token()
    return TokenResponse(access_token=token, token_type="bearer")
