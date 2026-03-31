from fastapi import APIRouter, HTTPException, status
from app.schemas.auth import LoginRequest, TokenResponse
from app.auth import verify_password, create_access_token
from app.config import get_settings

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
