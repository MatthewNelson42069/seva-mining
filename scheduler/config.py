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

    # Phase B (quick-260424-l0d) — kept in parity with backend; scheduler does not
    # post today, so these are accepted but unused. `extra="ignore"` already tolerates
    # missing-from-env, but declaring them here keeps the schema legible.
    x_access_token: Optional[str] = None
    x_access_token_secret: Optional[str] = None
    x_posting_enabled: bool = False
    x_posting_sim_prefix: str = "sim-"

    serpapi_api_key: Optional[str] = None
    twilio_account_sid: Optional[str] = None
    twilio_auth_token: Optional[str] = None
    twilio_whatsapp_from: Optional[str] = None
    digest_whatsapp_to: Optional[str] = None
    frontend_url: str = "http://localhost:5173"

    # Market snapshot grounding (quick-260420-oa1)
    fred_api_key: Optional[str] = None
    metalpriceapi_api_key: Optional[str] = None

    # v2.0 daily summary delivery (Phase 1, Plan 03)
    # Simulate-mode gate: when false, log the teaser but do NOT call Twilio.
    # Mirrors the X_POSTING_ENABLED simulate-mode pattern (quick-260424-l0d).
    # Default false so first deploys are safe — flip to true after WhatsApp
    # sandbox session is verified active.
    whatsapp_delivery_enabled: bool = False

    # Feed base URL embedded in WhatsApp teasers. Defaults to the production
    # Vercel URL so dev environments without FEED_BASE_URL set still produce
    # working clickable links to the user's feed.
    feed_base_url: str = "https://seva-mining-smm.vercel.app"



@lru_cache
def get_settings() -> Settings:
    return Settings()
