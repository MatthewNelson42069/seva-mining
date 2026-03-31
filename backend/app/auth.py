import jwt
import bcrypt
from datetime import datetime, timedelta, timezone
from app.config import get_settings

ALGORITHM = "HS256"
TOKEN_EXPIRE_DAYS = 7  # per D-08


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token() -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(days=TOKEN_EXPIRE_DAYS)
    return jwt.encode({"sub": "operator", "exp": expire}, settings.jwt_secret, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
