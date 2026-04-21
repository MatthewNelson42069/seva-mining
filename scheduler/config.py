from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        # Tolerate extra env vars so the backend and scheduler share a single
        # .env / Railway project env space without choking on each other's vars.
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

    # Market snapshot grounding (quick-260420-oa1)
    fred_api_key: Optional[str] = None
    metalpriceapi_api_key: Optional[str] = None



@lru_cache
def get_settings() -> Settings:
    return Settings()
