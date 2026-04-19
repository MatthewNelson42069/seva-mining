from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        # Tolerate extra env vars so the backend process can load
        # scheduler.agents.image_render_agent via importlib without choking on
        # backend-only vars (jwt_secret, dashboard_password, …) in the shared
        # .env / Railway project env space. See Plan 11-07 finalization.
        extra="ignore",
    )

    # Required — scheduler cannot start without these
    database_url: str
    anthropic_api_key: str
    x_api_bearer_token: str

    # Optional — agents that need these will fail gracefully if absent
    x_api_key: Optional[str] = None
    x_api_secret: Optional[str] = None
    serpapi_api_key: Optional[str] = None
    twilio_account_sid: Optional[str] = None
    twilio_auth_token: Optional[str] = None
    twilio_whatsapp_from: Optional[str] = None
    digest_whatsapp_to: Optional[str] = None
    frontend_url: str = "http://localhost:5173"

    # Phase 11 — Image rendering (Gemini / Cloudflare R2)
    gemini_api_key: Optional[str] = None
    r2_account_id: Optional[str] = None
    r2_access_key_id: Optional[str] = None
    r2_secret_access_key: Optional[str] = None
    r2_bucket: Optional[str] = None
    r2_public_base_url: Optional[str] = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
