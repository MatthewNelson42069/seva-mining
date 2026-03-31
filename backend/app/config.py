from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database — must use postgresql+asyncpg://.../dbname?sslmode=require
    # Hostname must end in -pooler.neon.tech for PgBouncer transaction mode (D-05)
    database_url: str

    # Anthropic
    anthropic_api_key: str

    # Twilio WhatsApp (D-15, D-16, WHAT-04)
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_whatsapp_from: str   # format: whatsapp:+14155238886
    digest_whatsapp_to: str     # format: whatsapp:+1XXXXXXXXXX

    # X (Twitter) API — Basic tier read-only
    x_api_bearer_token: str
    x_api_key: str
    x_api_secret: str

    # Apify — Instagram scraping
    apify_api_token: str

    # SerpAPI — news search
    serpapi_api_key: str

    # App config
    jwt_secret: str
    dashboard_password: str     # stored as bcrypt hash in Phase 2
    frontend_url: str


@lru_cache
def get_settings() -> Settings:
    return Settings()
