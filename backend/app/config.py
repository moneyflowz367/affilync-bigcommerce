"""
Configuration settings for BigCommerce integration
"""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # App identification
    app_name: str = "Affilync BigCommerce App"
    app_version: str = "1.0.0"
    debug: bool = False

    # BigCommerce OAuth
    bigcommerce_client_id: str
    bigcommerce_client_secret: str
    bigcommerce_app_id: str = ""

    # BigCommerce API
    bigcommerce_api_url: str = "https://api.bigcommerce.com"
    bigcommerce_auth_url: str = "https://login.bigcommerce.com"

    # Affilync API
    affilync_api_url: str = "https://api.affilync.com"
    affilync_api_key: str

    # Database
    database_url: str

    # Redis (for sessions and rate limiting)
    redis_url: Optional[str] = None

    # Security
    encryption_key: str
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    # V58.36 P0 (2026-05-28): per-app bearer token sent as the
    # Authorization header on every outbound BC webhook. The
    # previous HMAC-content-hash scheme assumed a header
    # X-BC-Api-Content-Hash that BigCommerce never sends on outbound
    # webhook deliveries — every webhook 401'd at the middleware
    # silently. BC's actual outbound-webhook auth pattern is the
    # `headers` map configured at webhook registration time. Operator
    # generates a strong random secret and sets this env var; the
    # registration code propagates it as `Authorization: Bearer <v>`,
    # and the middleware compares constant-time. Falls back to
    # bigcommerce_client_secret in dev so unit tests don't have to
    # set a separate secret.
    bigcommerce_webhook_secret: Optional[str] = None

    # App URLs
    app_url: str = "https://bigcommerce.affilync.com"
    webhook_callback_url: str = ""

    # Defaults
    default_cookie_duration_days: int = 30
    default_attribution_model: str = "last_click"

    # Rate limiting
    rate_limit_per_minute: int = 60
    rate_limit_per_hour: int = 1000

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Set default webhook URL if not provided
        if not self.webhook_callback_url:
            self.webhook_callback_url = f"{self.app_url}/webhooks/bigcommerce"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
