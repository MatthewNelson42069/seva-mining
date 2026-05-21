from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        # Tolerate leftover env vars (e.g. DASHBOARD_PASSWORD, JWT_SECRET
        # from the pre-260521-9ze password/JWT auth model) so Railway boot
        # doesn't crash before those vars are scrubbed from the dashboard.
        extra="ignore",
    )

    # Required — API cannot start without these
    database_url: str
    anthropic_api_key: str
    x_api_bearer_token: str
    seva_dashboard_token: str   # Cookie-token auth — env var SEVA_DASHBOARD_TOKEN
    frontend_url: str = "http://localhost:5173"

    # Optional — routes that need these will fail gracefully if absent
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_whatsapp_from: str | None = None   # format: whatsapp:+14155238886
    digest_whatsapp_to: str | None = None     # format: whatsapp:+1XXXXXXXXXX

    x_api_key: str | None = None
    x_api_secret: str | None = None

    # Phase B (quick-260424-l0d): OAuth 1.0a User Context for posting + feature flag
    # See CLAUDE.md "Posting to X (Phase B Prereqs)" runbook before generating tokens.
    x_access_token: str | None = None
    x_access_token_secret: str | None = None
    x_posting_enabled: bool = False
    x_posting_sim_prefix: str = "sim-"

    serpapi_api_key: str | None = None

    # Phase 11 — Image rendering (Gemini / Cloudflare R2)
    gemini_api_key: str | None = None
    r2_account_id: str | None = None
    r2_access_key_id: str | None = None
    r2_secret_access_key: str | None = None
    r2_bucket: str | None = None
    r2_public_base_url: str | None = None

    # v2.0 daily summary delivery (Phase 1, Plan 03)
    # Simulate-mode gate: when false, log the teaser but do NOT call Twilio.
    # Mirrors the X_POSTING_ENABLED simulate-mode pattern (quick-260424-l0d).
    # Default false so first deploys are safe — flip to true after WhatsApp
    # sandbox session is verified active.
    whatsapp_delivery_enabled: bool = False

    # v2.0 Phase 2 — Ontario Law relevance filter (HIGH-1, HIGH-2, HIGH-6)
    # Mirrors scheduler/config.py for env-var parity. Backend never invokes the
    # filter directly today, but parity prevents drift if a future debug endpoint
    # surfaces filter config.
    ontario_law_filter_model: str = "claude-haiku-4-5"

    # Feed base URL embedded in WhatsApp teasers. Defaults to the production
    # Vercel URL so dev environments without FEED_BASE_URL set still produce
    # working clickable links to the user's feed.
    feed_base_url: str = "https://seva-mining-smm.vercel.app"


@lru_cache
def get_settings() -> Settings:
    return Settings()
