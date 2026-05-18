"""
HMAC Verification for BigCommerce Webhooks
Verifies webhook signatures using SHA256 HMAC
"""

import hashlib
import hmac
import logging
from typing import Callable

from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.config import settings

logger = logging.getLogger(__name__)


def verify_webhook_hmac(payload: bytes, signature: str) -> bool:
    """
    Verify BigCommerce webhook HMAC signature.

    BigCommerce uses SHA256 HMAC with the client secret.
    The signature is sent in the X-BC-Api-Content-Hash header.

    Args:
        payload: Raw request body bytes
        signature: Signature from X-BC-Api-Content-Hash header

    Returns:
        bool: True if signature is valid
    """
    if not signature:
        return False

    # Compute expected signature
    expected = hmac.new(
        settings.bigcommerce_client_secret.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()

    # Constant-time comparison
    return hmac.compare_digest(expected.lower(), signature.lower())


class WebhookHMACMiddleware(BaseHTTPMiddleware):
    """
    Middleware to verify BigCommerce webhook HMAC signatures.
    Only applies to /webhooks/bigcommerce endpoint.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Only verify webhooks path
        if not request.url.path.startswith("/webhooks/bigcommerce"):
            return await call_next(request)

        # Get HMAC header
        hmac_header = request.headers.get("X-BC-Api-Content-Hash")
        if not hmac_header:
            logger.warning("Webhook request missing HMAC header")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing HMAC header",
            )

        # Read body and store for later use
        body = await request.body()

        # Verify HMAC
        if not verify_webhook_hmac(body, hmac_header):
            logger.warning("Webhook HMAC verification failed")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid HMAC signature",
            )

        # SEC: replay protection. Without this, a captured webhook
        # (passive eavesdrop on the wire, or copied from logs/proxies)
        # can be replayed indefinitely — the HMAC remains valid forever
        # because BigCommerce does not include a fresh nonce by default.
        # Dedup on (hash of body + signature) for 24 h; the body is the
        # only thing the signature commits to, so a true replay is
        # byte-identical. Redis is best-effort: if it's down we log and
        # allow (fail-open) rather than block legitimate webhooks.
        # (Pre-launch audit 2026-05-18.)
        try:
            import hashlib as _hashlib

            from app.services.redis_service import get_redis  # type: ignore

            redis = await get_redis()
            if redis is not None:
                replay_key = (
                    "bc_webhook_replay:"
                    + _hashlib.sha256(body + hmac_header.encode()).hexdigest()
                )
                # SET NX EX 86400 — atomic dedup with 24 h TTL.
                claimed = await redis.set(replay_key, b"1", nx=True, ex=86400)
                if not claimed:
                    logger.warning(
                        "Replayed BigCommerce webhook rejected: %s", replay_key[:60]
                    )
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Webhook already processed",
                    )
        except HTTPException:
            raise
        except Exception as redis_err:
            # Redis unreachable — log and allow. Webhooks are idempotent
            # on the application side; HMAC has already validated the
            # payload, so allowing dedup-skipped delivery is preferable
            # to blocking legitimate Connect webhooks during a Redis outage.
            logger.warning("Webhook replay-protection skipped: %s", redis_err)

        # Store body in state for route handler
        request.state.raw_body = body

        return await call_next(request)


async def verify_webhook_signature(request: Request) -> bytes:
    """
    FastAPI dependency to verify webhook signature and return body.

    Alternative to middleware for more granular control.

    Usage:
        @router.post("/webhooks/bigcommerce")
        async def handle_webhook(body: bytes = Depends(verify_webhook_signature)):
            ...
    """
    hmac_header = request.headers.get("X-BC-Api-Content-Hash")
    if not hmac_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing HMAC header",
        )

    body = await request.body()

    if not verify_webhook_hmac(body, hmac_header):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid HMAC signature",
        )

    return body
