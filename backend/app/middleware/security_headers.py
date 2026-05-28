"""Security headers middleware for the BigCommerce integration.

V58.12 P0 (2026-05-28): the FastAPI service had no CSP / X-Frame-Options /
HSTS. The embedded BigCommerce app loads in an iframe inside the BC
control panel — without `frame-ancestors` constraint, ANY origin can
embed the app and stage a clickjacking attack against the merchant
session token. Without HSTS, a one-time downgrade to HTTP exfiltrates
the JWT in cleartext.

Allowed iframe parents (BC docs):
- `https://store.bigcommerce.com`           — primary control panel
- `https://*.mybigcommerce.com`             — store-specific subdomains
- the app's own origin (some BC flows pop the app full-screen)

Anything else is denied.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config import settings


_FRAME_ANCESTORS = " ".join(
    [
        "'self'",
        "https://store.bigcommerce.com",
        "https://*.mybigcommerce.com",
    ]
)

_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.bigcommerce.com; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: https:; "
    "connect-src 'self' https://*.bigcommerce.com https://api.affilync.com; "
    f"frame-ancestors {_FRAME_ANCESTORS}; "
    "form-action 'self' https://*.bigcommerce.com; "
    "base-uri 'self'; "
    "object-src 'none'"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach defense-in-depth headers to every response."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response: Response = await call_next(request)

        # CSP — primary defense against XSS and clickjacking
        response.headers.setdefault("Content-Security-Policy", _CSP)

        # Legacy X-Frame-Options for older browsers — CSP frame-ancestors
        # supersedes this on modern browsers but BC merchant browsers
        # span a wide range.
        response.headers.setdefault(
            "X-Frame-Options",
            # ALLOW-FROM is non-standard and ignored by most browsers,
            # so we set ALLOWALL semantically and rely on CSP. Modern
            # browsers honor CSP > XFO when both are present.
            "SAMEORIGIN",
        )

        # HSTS — force HTTPS for 1 year. Render serves HTTPS only, so
        # this is purely a downgrade defense.
        if getattr(settings, "app_env", "").lower() == "production":
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )

        # MIME-type sniffing defense
        response.headers.setdefault("X-Content-Type-Options", "nosniff")

        # Reduce Referer leakage to third parties
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")

        # Limit access to powerful features
        response.headers.setdefault(
            "Permissions-Policy",
            "geolocation=(), microphone=(), camera=(), payment=()",
        )

        return response
