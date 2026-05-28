"""
OAuth Routes for BigCommerce App Installation
Handles the OAuth flow for app installation
"""

import json
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.services.store_service import StoreService

logger = logging.getLogger(__name__)

router = APIRouter()

# Redis-backed CSRF state storage with in-memory fallback
_fallback_states: dict[str, dict] = {}
_redis_client = None


async def _get_redis():
    """Get or create Redis client for OAuth state."""
    global _redis_client
    if _redis_client is None:
        try:
            import redis.asyncio as aioredis

            _redis_client = aioredis.from_url(
                settings.redis_url, encoding="utf-8", decode_responses=True
            )
            await _redis_client.ping()
        except Exception as e:
            logger.warning(f"Redis unavailable for OAuth state: {e}")
            _redis_client = None
    return _redis_client


class _OAuthStateError(RuntimeError):
    """Raised when OAuth state storage is unavailable."""


async def _store_state(state: str) -> None:
    """Store OAuth state in Redis. Raise if Redis unavailable in prod.

    V58.9 P0 (2026-05-28): the in-memory fallback only works inside a
    SINGLE worker process. Render runs multiple workers; state issued by
    worker A is invisible to worker B and validation fails — UNLESS the
    callback happens to route to the same worker. Either path produces
    inconsistent behaviour, and under sustained Redis outage the in-memory
    dict on a freshly-recycled worker is empty → ANY state value can be
    "validated" by writing to that same dict via /auth and then quickly
    re-using it via /callback. CSRF protection collapses.

    Better to refuse the OAuth flow entirely when Redis is down. The user
    sees a clear failure and retries once Redis recovers, rather than
    completing an OAuth install with broken state-tracking.
    """
    redis = await _get_redis()
    if redis is not None:
        try:
            await redis.setex(f"oauth_state:bc:{state}", 600, "1")
            return
        except Exception as exc:
            logger.critical("oauth_state_redis_setex_failed: %s", exc)
            raise _OAuthStateError("OAuth state storage unavailable") from exc

    # Redis is None and we're in a non-test env — refuse.
    env = (os.getenv("ENVIRONMENT") or "").lower()
    if env in ("test", "testing", "ci", "pytest", "development", "dev"):
        # Dev / test fallback — single-process is fine for these envs.
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)
        expired = [k for k, v in _fallback_states.items() if v["created_at"] < cutoff]
        for k in expired:
            del _fallback_states[k]
        _fallback_states[state] = {"created_at": datetime.now(timezone.utc)}
        return

    logger.critical(
        "oauth_state_redis_unavailable env=%s — refusing OAuth install", env
    )
    raise _OAuthStateError("OAuth state storage unavailable")


async def _validate_state(state: str) -> bool:
    """Validate and consume OAuth state.

    V58.9 P0: under prod-Redis-outage, refuse to validate via the
    in-memory dict. Same multi-worker correctness argument as _store_state.
    """
    redis = await _get_redis()
    if redis is not None:
        try:
            key = f"oauth_state:bc:{state}"
            result = await redis.get(key)
            if result:
                await redis.delete(key)
                return True
            return False
        except Exception as exc:
            logger.critical("oauth_state_redis_validate_failed: %s", exc)
            return False

    env = (os.getenv("ENVIRONMENT") or "").lower()
    if env in ("test", "testing", "ci", "pytest", "development", "dev"):
        if state in _fallback_states:
            _fallback_states.pop(state)
            return True
        return False

    logger.critical(
        "oauth_state_redis_unavailable env=%s — failing validation closed", env
    )
    return False


@router.get("/auth")
async def auth_start(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Start the OAuth flow.

    BigCommerce redirects here when a merchant clicks "Install" in the app store.
    We redirect to BigCommerce's authorization URL.
    """
    # Get parameters from BigCommerce
    code = request.query_params.get("code")
    scope = request.query_params.get("scope")
    context = request.query_params.get("context")

    if code:
        # CSRF state token MUST be present and MUST validate. The previous
        # check `if state and not _validate_state(state)` silently skipped
        # validation when state was absent — an attacker could initiate the
        # callback by stripping the param, force-installing a store under
        # their own token. (V58.6 audit P0 2026-05-28.)
        state = request.query_params.get("state")
        if not state or not await _validate_state(state):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or missing OAuth state parameter",
            )

        # This is the callback - exchange code for token
        return await auth_callback(
            code=code,
            scope=scope,
            context=context,
            state=state,
            state_already_validated=True,
            db=db,
        )

    # Otherwise, this is the initial auth request
    # Generate CSRF state token and store in Redis
    state = secrets.token_urlsafe(32)
    try:
        await _store_state(state)
    except _OAuthStateError:
        # Redis is down in prod — refuse to issue an auth URL rather than
        # ship the merchant into an OAuth flow we can't validate.
        raise HTTPException(
            status_code=503,
            detail="OAuth state storage unavailable; please retry shortly.",
        )

    # Redirect to BigCommerce authorization
    params = {
        "client_id": settings.bigcommerce_client_id,
        "redirect_uri": f"{settings.app_url}/oauth/auth",
        "response_type": "code",
        "scope": "store_v2_default store_v2_orders store_v2_products store_webhooks_manage",
        "state": state,
    }

    auth_url = f"{settings.bigcommerce_auth_url}/oauth2/authorize?{urlencode(params)}"
    return RedirectResponse(url=auth_url)


@router.get("/callback")
async def auth_callback(
    code: str = Query(..., description="Authorization code"),
    scope: str = Query(..., description="Granted scopes"),
    context: str = Query(..., description="Store context"),
    state: str | None = Query(None, description="CSRF state token"),
    state_already_validated: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """
    OAuth callback handler.

    BigCommerce redirects here after the merchant authorizes the app.
    We exchange the code for an access token and install the app.

    CSRF state MUST validate. The /auth route is the canonical entry point
    and validates state before forwarding to this function with
    state_already_validated=True. Direct callers (legacy BigCommerce
    redirect URI) must supply a state that this route validates itself.
    (V58.6 audit P0 2026-05-28.)
    """
    if not state_already_validated:
        if not state or not await _validate_state(state):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or missing OAuth state parameter",
            )

    # Extract store hash from context (format: stores/{store_hash})
    store_hash = context.split("/")[-1] if context else None

    if not store_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid store context",
        )

    logger.info(f"OAuth callback for store: {store_hash}")

    try:
        # Exchange code for access token
        store_service = StoreService(db)
        token_response = await store_service.exchange_token(
            code=code,
            scope=scope,
            context=context,
        )

        access_token = token_response.get("access_token")
        user = token_response.get("user", {})

        if not access_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to get access token",
            )

        # Install the app
        store = await store_service.install_store(
            store_hash=store_hash,
            access_token=access_token,
            scope=scope,
            user=user,
        )

        # Register webhooks
        try:
            await store_service.register_webhooks(store)
        except Exception as e:
            logger.error(f"Failed to register webhooks: {e}")

        # Redirect to the app's main page
        # BigCommerce expects redirect to: https://store-{store_hash}.mybigcommerce.com/manage/app/{app_id}
        # But for embedded apps, redirect to our dashboard
        return RedirectResponse(
            url=f"{settings.app_url}/?store_hash={store_hash}",
            status_code=status.HTTP_302_FOUND,
        )

    except Exception as e:
        logger.exception(f"OAuth callback error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Installation failed: {str(e)}",
        )


@router.get("/load")
async def load_app(
    signed_payload_jwt: str = Query(..., alias="signed_payload_jwt"),
    db: AsyncSession = Depends(get_db),
):
    """
    Load callback for BigCommerce.

    Called when the app is loaded in the BigCommerce control panel.
    BigCommerce sends a signed JWT with store and user information.
    """
    import jwt

    try:
        # Decode the JWT (BigCommerce signs with client_secret)
        payload = jwt.decode(
            signed_payload_jwt,
            settings.bigcommerce_client_secret,
            algorithms=["HS256"],
            audience=settings.bigcommerce_client_id,
        )

        store_hash = payload.get("sub", "").split("/")[-1]
        user = payload.get("user", {})

        if not store_hash:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JWT payload",
            )

        # Verify store exists
        store_service = StoreService(db)
        store = await store_service.get_store_by_hash(store_hash)

        if not store or not store.is_active:
            # Store not installed, redirect to install
            return RedirectResponse(url=f"{settings.app_url}/oauth/auth")

        # Redirect to app dashboard
        return RedirectResponse(
            url=f"{settings.app_url}/?store_hash={store_hash}",
            status_code=status.HTTP_302_FOUND,
        )

    except jwt.InvalidTokenError as e:
        logger.error(f"Invalid JWT: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signed payload",
        )


@router.get("/uninstall")
async def uninstall_app(
    signed_payload_jwt: str = Query(..., alias="signed_payload_jwt"),
    db: AsyncSession = Depends(get_db),
):
    """
    Uninstall callback for BigCommerce.

    Called when the merchant uninstalls the app.
    """
    import jwt

    try:
        payload = jwt.decode(
            signed_payload_jwt,
            settings.bigcommerce_client_secret,
            algorithms=["HS256"],
            audience=settings.bigcommerce_client_id,
        )

        store_hash = payload.get("sub", "").split("/")[-1]

        if store_hash:
            store_service = StoreService(db)
            await store_service.uninstall_store(store_hash)
            logger.info(f"Store uninstalled via callback: {store_hash}")

        return {"status": "ok"}

    except jwt.InvalidTokenError as e:
        logger.error(f"Invalid JWT on uninstall: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signed payload",
        )


@router.get("/remove-user")
async def remove_user(
    signed_payload_jwt: str = Query(..., alias="signed_payload_jwt"),
    db: AsyncSession = Depends(get_db),
):
    """
    Remove user callback for BigCommerce.

    Called when a user is removed from the store.
    """
    import jwt

    try:
        payload = jwt.decode(
            signed_payload_jwt,
            settings.bigcommerce_client_secret,
            algorithms=["HS256"],
            audience=settings.bigcommerce_client_id,
        )

        # Log the event but don't take action
        # (we don't track individual users)
        logger.info(f"User removed from store: {payload}")

        return {"status": "ok"}

    except jwt.InvalidTokenError as e:
        logger.error(f"Invalid JWT on remove-user: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signed payload",
        )
