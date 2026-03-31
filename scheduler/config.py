from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    database_url: str
    anthropic_api_key: str
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_whatsapp_from: str
    digest_whatsapp_to: str
    x_api_bearer_token: str
    x_api_key: str
    x_api_secret: str
    apify_api_token: str
    serpapi_api_key: str
    frontend_url: str


@lru_cache
def get_settings() -> Settings:
    return Settings()
