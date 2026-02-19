"""
Authentication middleware for BigCommerce integration service.

Validates requests using either:
1. API key in X-API-Key header (service-to-service)
2. JWT signed by BigCommerce client secret (embedded app loads)
3. Session token validated against stored access tokens
"""

import logging
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, Query, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db

logger = logging.getLogger(__name__)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)


async def require_auth(
    api_key: Optional[str] = Depends(api_key_header),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> dict:
    """
    Require authentication via either API key or JWT token.

    Returns a dict with auth context:
    - {"type": "api_key"} for service-to-service calls
    - {"type": "jwt", "store_hash": ...} for BigCommerce signed payloads
    """
    # Try API key first (service-to-service)
    if api_key and api_key == settings.affilync_api_key:
        return {"type": "api_key"}

    # Try JWT token (BigCommerce signed payload or internal JWT)
    if credentials:
        try:
            payload = jwt.decode(
                credentials.credentials,
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm],
            )
            return {
                "type": "jwt",
                "store_hash": payload.get("store_hash"),
                "user_id": payload.get("user_id"),
            }
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
            )
        except jwt.InvalidTokenError:
            pass

        # Try BigCommerce-signed JWT (signed with client_secret)
        try:
            payload = jwt.decode(
                credentials.credentials,
                settings.bigcommerce_client_secret,
                algorithms=["HS256"],
                audience=settings.bigcommerce_client_id,
            )
            store_hash = payload.get("sub", "").split("/")[-1]
            return {
                "type": "bigcommerce_jwt",
                "store_hash": store_hash,
                "user": payload.get("user", {}),
            }
        except jwt.InvalidTokenError:
            pass

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Valid API key or JWT token required",
        headers={"WWW-Authenticate": "Bearer"},
    )
