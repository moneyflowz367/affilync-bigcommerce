"""
Redis-backed rate limiting middleware for BigCommerce integration.
"""

import logging
import time
from collections import defaultdict
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings

logger = logging.getLogger(__name__)

# Fallback in-memory store (only used if Redis unavailable)
_fallback_requests: dict = defaultdict(list)
_redis_client = None


async def get_redis():
    """Get or create Redis client."""
    global _redis_client
    if _redis_client is None:
        try:
            import redis.asyncio as aioredis

            _redis_client = aioredis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            await _redis_client.ping()
        except Exception as e:
            logger.warning(f"Redis unavailable for rate limiting: {e}")
            _redis_client = None
    return _redis_client


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Redis-backed rate limiting middleware.
    Falls back to in-memory if Redis is unavailable.
    """

    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request."""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def _check_redis_limit(self, client_ip: str) -> tuple[bool, int]:
        """Check rate limit using Redis INCR + EXPIRE."""
        redis = await get_redis()
        if not redis:
            return self._check_memory_limit(client_ip)

        try:
            key = f"rate_limit:bc:{client_ip}"
            current = await redis.incr(key)
            if current == 1:
                await redis.expire(key, 60)
            remaining = max(0, self.requests_per_minute - current)
            return current > self.requests_per_minute, remaining
        except Exception as e:
            logger.warning(f"Redis rate limit error: {e}")
            return self._check_memory_limit(client_ip)

    def _check_memory_limit(self, client_ip: str) -> tuple[bool, int]:
        """Fallback in-memory rate limit check."""
        now = time.time()
        minute_ago = now - 60
        _fallback_requests[client_ip] = [
            t for t in _fallback_requests[client_ip] if t > minute_ago
        ]
        if len(_fallback_requests[client_ip]) >= self.requests_per_minute:
            return True, 0
        _fallback_requests[client_ip].append(now)
        return False, self.requests_per_minute - len(_fallback_requests[client_ip])

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with rate limiting."""
        if request.url.path in ["/health", "/healthz", "/"]:
            return await call_next(request)

        if request.url.path.startswith("/webhooks"):
            return await call_next(request)

        client_ip = self._get_client_ip(request)
        is_limited, remaining = await self._check_redis_limit(client_ip)

        if is_limited:
            return Response(
                content='{"detail": "Rate limit exceeded"}',
                status_code=429,
                media_type="application/json",
                headers={
                    "Retry-After": "60",
                    "X-RateLimit-Limit": str(self.requests_per_minute),
                    "X-RateLimit-Remaining": "0",
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))
        return response
