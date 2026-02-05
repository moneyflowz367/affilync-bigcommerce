"""
API Routes for BigCommerce App Frontend
Handles API requests from the embedded app
"""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import BigCommerceStore
from app.services.conversion_service import ConversionService
from app.services.product_sync import ProductSyncService
from app.services.store_service import StoreService

logger = logging.getLogger(__name__)

router = APIRouter()


# ============== Request/Response Models ==============


class StoreInfo(BaseModel):
    """Store information response."""

    store_hash: str
    store_name: Optional[str]
    store_domain: Optional[str]
    is_active: bool
    installed_at: Optional[str]
    brand_id: Optional[str]
    is_connected: bool
    settings: dict


class ProductResponse(BaseModel):
    """Product response model."""

    id: str
    bc_product_id: int
    title: str
    handle: Optional[str]
    price: Optional[float]
    image_url: Optional[str]
    is_synced: bool
    last_synced_at: Optional[str]


class ProductsListResponse(BaseModel):
    """Products list response."""

    products: list[ProductResponse]
    total: int
    limit: int
    offset: int


class ConnectBrandRequest(BaseModel):
    """Request to connect store to brand."""

    brand_id: str


class SettingsUpdateRequest(BaseModel):
    """Request to update store settings."""

    auto_sync_products: Optional[bool] = None
    cookie_duration_days: Optional[int] = None
    attribution_model: Optional[str] = None


class AnalyticsResponse(BaseModel):
    """Analytics overview response."""

    conversions: int
    revenue: float
    clicks: int
    top_affiliates: list[dict]
    top_products: list[dict]


# ============== Dependencies ==============


async def get_current_store(
    store_hash: str = Query(..., description="Store hash"),
    db: AsyncSession = Depends(get_db),
) -> BigCommerceStore:
    """
    Get the current store from query parameter.

    In a production app, this would validate session tokens.
    """
    store_service = StoreService(db)
    store = await store_service.get_store_by_hash(store_hash)

    if not store or not store.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Store not found or inactive",
        )

    return store


# ============== Store Endpoints ==============


@router.get("/store", response_model=StoreInfo)
async def get_store_info(
    store: BigCommerceStore = Depends(get_current_store),
):
    """Get current store information."""
    return StoreInfo(
        store_hash=store.store_hash,
        store_name=store.store_name,
        store_domain=store.store_domain,
        is_active=store.is_active,
        installed_at=store.installed_at.isoformat() if store.installed_at else None,
        brand_id=str(store.brand_id) if store.brand_id else None,
        is_connected=store.is_connected_to_affilync,
        settings={
            "auto_sync_products": store.auto_sync_products,
            "cookie_duration_days": store.cookie_duration_days,
            "attribution_model": store.attribution_model,
        },
    )


@router.post("/store/connect")
async def connect_to_brand(
    request: ConnectBrandRequest,
    store: BigCommerceStore = Depends(get_current_store),
    db: AsyncSession = Depends(get_db),
):
    """Connect store to an Affilync brand account."""
    store_service = StoreService(db)

    try:
        brand_id = UUID(request.brand_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid brand ID format",
        )

    updated = await store_service.connect_brand(store.id, brand_id)

    return {
        "status": "connected",
        "brand_id": str(updated.brand_id),
    }


@router.post("/store/disconnect")
async def disconnect_from_brand(
    store: BigCommerceStore = Depends(get_current_store),
    db: AsyncSession = Depends(get_db),
):
    """Disconnect store from Affilync brand account."""
    store_service = StoreService(db)
    await store_service.disconnect_brand(store.id)

    return {"status": "disconnected"}


@router.put("/store/settings")
async def update_store_settings(
    request: SettingsUpdateRequest,
    store: BigCommerceStore = Depends(get_current_store),
    db: AsyncSession = Depends(get_db),
):
    """Update store settings."""
    store_service = StoreService(db)

    settings_update = {}
    if request.auto_sync_products is not None:
        settings_update["auto_sync_products"] = request.auto_sync_products
    if request.cookie_duration_days is not None:
        settings_update["cookie_duration_days"] = request.cookie_duration_days
    if request.attribution_model is not None:
        settings_update["attribution_model"] = request.attribution_model

    if settings_update:
        await store_service.update_store_settings(store.id, **settings_update)

    return {"status": "updated", "settings": settings_update}


# ============== Products Endpoints ==============


@router.get("/products", response_model=ProductsListResponse)
async def get_products(
    store: BigCommerceStore = Depends(get_current_store),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    synced_only: bool = Query(False),
):
    """Get products for the store."""
    product_service = ProductSyncService(db)
    products, total = await product_service.get_store_products(
        store_id=store.id,
        limit=limit,
        offset=offset,
        synced_only=synced_only,
    )

    return ProductsListResponse(
        products=[
            ProductResponse(
                id=str(p.id),
                bc_product_id=p.bc_product_id,
                title=p.title,
                handle=p.handle,
                price=p.price,
                image_url=p.image_url,
                is_synced=p.is_synced,
                last_synced_at=p.last_synced_at.isoformat() if p.last_synced_at else None,
            )
            for p in products
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/products/sync")
async def sync_all_products(
    store: BigCommerceStore = Depends(get_current_store),
    db: AsyncSession = Depends(get_db),
    force: bool = Query(False),
):
    """Trigger full product sync."""
    if not store.brand_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Store must be connected to a brand first",
        )

    product_service = ProductSyncService(db)
    stats = await product_service.sync_all_products(store, force=force)

    return {
        "status": "completed",
        "stats": stats,
    }


# ============== Analytics Endpoints ==============


@router.get("/analytics", response_model=AnalyticsResponse)
async def get_analytics_overview(
    store: BigCommerceStore = Depends(get_current_store),
    db: AsyncSession = Depends(get_db),
    period: str = Query("month", regex="^(day|week|month)$"),
):
    """Get analytics overview for the store."""
    if not store.brand_id:
        return AnalyticsResponse(
            conversions=0,
            revenue=0,
            clicks=0,
            top_affiliates=[],
            top_products=[],
        )

    # Fetch analytics from Affilync API
    from affilync_integrations import AffilyncAPIClient
    from app.config import settings

    client = AffilyncAPIClient(
        api_url=settings.affilync_api_url,
        api_key=settings.affilync_api_key,
        source="bigcommerce-app",
    )

    try:
        usage = await client.get_brand_usage(
            brand_id=str(store.brand_id),
            period=period,
            source="bigcommerce",
        )

        return AnalyticsResponse(
            conversions=usage.get("conversion_count", 0),
            revenue=usage.get("total_revenue", 0),
            clicks=usage.get("click_count", 0),
            top_affiliates=usage.get("top_affiliates", []),
            top_products=usage.get("top_products", []),
        )

    except Exception as e:
        logger.error(f"Failed to fetch analytics: {e}")
        return AnalyticsResponse(
            conversions=0,
            revenue=0,
            clicks=0,
            top_affiliates=[],
            top_products=[],
        )


# ============== Health Endpoint ==============


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "affilync-bigcommerce",
    }
