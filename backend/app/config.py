from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Required — API cannot start without these
    database_url: str
    anthropic_api_key: str
    x_api_bearer_token: str
    jwt_secret: str
    dashboard_password: str     # bcrypt hash
    frontend_url: str = "http://localhost:5173"

    # Optional — routes that need these will fail gracefully if absent
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_whatsapp_from: str | None = None   # format: whatsapp:+14155238886
    digest_whatsapp_to: str | None = None     # format: whatsapp:+1XXXXXXXXXX

    x_api_key: str | None = None
    x_api_secret: str | None = None

    apify_api_token: str | None = None
    serpapi_api_key: str | None = None

    # Phase 11 — Image rendering (Gemini / Cloudflare R2)
    gemini_api_key: str | None = None
    r2_account_id: str | None = None
    r2_access_key_id: str | None = None
    r2_secret_access_key: str | None = None
    r2_bucket: str | None = None
    r2_public_base_url: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
