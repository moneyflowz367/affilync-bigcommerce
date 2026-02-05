"""
BigCommerce Integration Service
Main FastAPI application
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import init_db, close_db
from app.middleware.hmac_verify import WebhookHMACMiddleware
from app.routes import oauth, webhooks, api

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting BigCommerce integration service...")
    await init_db()

    # Configure encryption
    from affilync_integrations.encryption import configure_encryption

    configure_encryption(settings.encryption_key, salt_suffix="bigcommerce")

    logger.info("BigCommerce integration service started")

    yield

    # Shutdown
    logger.info("Shutting down BigCommerce integration service...")
    await close_db()
    logger.info("BigCommerce integration service stopped")


# Create FastAPI app
app = FastAPI(
    title="Affilync BigCommerce Integration",
    description="BigCommerce app for Affilync affiliate tracking",
    version=settings.app_version,
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://store.bigcommerce.com",
        "https://*.mybigcommerce.com",
        settings.app_url,
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add webhook HMAC verification middleware
app.add_middleware(WebhookHMACMiddleware)

# Mount routes
app.include_router(oauth.router, prefix="/oauth", tags=["OAuth"])
app.include_router(webhooks.router, prefix="/webhooks", tags=["Webhooks"])
app.include_router(api.router, prefix="/api", tags=["API"])


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "affilync-bigcommerce",
        "version": settings.app_version,
        "status": "running",
    }


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint for Render."""
    return {
        "status": "healthy",
        "service": "affilync-bigcommerce",
        "version": settings.app_version,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8006,
        reload=settings.debug,
    )
