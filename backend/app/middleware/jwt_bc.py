"""BigCommerce signed-JWT decoder with explicit issuer + audience binding.

V58.12 P0 (2026-05-28): the prior decoders called ``jwt.decode(...)``
with only ``audience=client_id``. PyJWT does NOT auto-verify the ``iss``
claim unless you pass ``issuer=...``. That meant any party with the
client_secret (e.g. accidentally committed to a satellite repo, or
leaked from another internal service) could forge a JWT with arbitrary
``sub``/``iss`` and pass auth as any store_hash.

BC documentation (Apps -> Signed Payload JWT) requires:

  iss == "bc/apps/{client_id}"

This module centralizes the decode + validation so every call site
gets the same guarantees.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

import jwt

from app.config import settings

logger = logging.getLogger(__name__)


def expected_issuer() -> str:
    """The BC-issued JWT ``iss`` value for this app."""
    return f"bc/apps/{settings.bigcommerce_client_id}"


def decode_bc_jwt(token: str) -> Dict[str, Any]:
    """Decode + verify a BigCommerce signed JWT.

    Raises:
        jwt.InvalidTokenError: if signature, aud, iss, or required claims
            fail validation.

    Returns the decoded payload dict on success.
    """
    payload = jwt.decode(
        token,
        settings.bigcommerce_client_secret,
        algorithms=["HS256"],
        audience=settings.bigcommerce_client_id,
        issuer=expected_issuer(),
        options={
            # Require all four for any BC-signed token.
            "require": ["aud", "iss", "sub", "exp"],
            "verify_signature": True,
            "verify_aud": True,
            "verify_iss": True,
            "verify_exp": True,
        },
    )
    # Defense in depth: re-check iss even if PyJWT already did.
    if payload.get("iss") != expected_issuer():
        raise jwt.InvalidIssuerError(
            f"Unexpected JWT issuer: {payload.get('iss')!r}"
        )
    return payload
