"""
Rate limiting middleware for BigCommerce — delegates to shared library.
"""

import logging

from app.config import settings

logger = logging.getLogger(__name__)

try:
    from affilync_integrations.rate_limit import (
        RateLimitConfig,
        RateLimitMiddleware,
        RateLimiter,
        RedisRateLimiter,
    )

    _redis_url = getattr(settings, "redis_url", None)
    if _redis_url:
        _limiter = RedisRateLimiter(
            redis_url=_redis_url,
            config=RateLimitConfig(
                requests_per_minute=60,
                requests_per_hour=1000,
                key_prefix="rate_limit:bc",
            ),
        )
    else:
        logger.critical(
            "RATE LIMITER: No REDIS_URL configured — using in-memory fallback. "
            "NOT safe for production multi-worker deployments."
        )
        _limiter = RateLimiter(
            config=RateLimitConfig(
                requests_per_minute=60,
                requests_per_hour=1000,
                key_prefix="rate_limit:bc",
            ),
        )

    def get_limiter():
        return _limiter

except ImportError:
    logger.critical(
        "RATE LIMITER: affilync_integrations not installed — "
        "rate limiting is DISABLED. Install the shared library."
    )
    from starlette.middleware.base import BaseHTTPMiddleware
    from fastapi import Request

    class RateLimitMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            return await call_next(request)

    def get_limiter():
        return None
