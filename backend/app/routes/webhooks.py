"""
BigCommerce Webhook Handlers
Process incoming webhooks from BigCommerce
"""

import json
import logging
from datetime import datetime
from hashlib import sha256

from fastapi import APIRouter, Depends, HTTPException, Header, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.hmac_verify import verify_webhook_signature
from app.models import BigCommerceStore, BigCommerceWebhookLog
from app.services.conversion_service import ConversionService
from app.services.product_sync import ProductSyncService
from app.services.store_service import StoreService

logger = logging.getLogger(__name__)

router = APIRouter()


async def get_store_by_hash(store_hash: str, db: AsyncSession) -> BigCommerceStore:
    """Get store by hash from database."""
    result = await db.execute(
        select(BigCommerceStore).where(BigCommerceStore.store_hash == store_hash)
    )
    return result.scalar_one_or_none()


async def log_webhook(
    db: AsyncSession,
    store_id,
    scope: str,
    payload: dict,
    webhook_id: str = None,
) -> BigCommerceWebhookLog:
    """Create a webhook log entry with idempotency check (PAY-XI-11)."""
    # Create hash for deduplication
    payload_hash = sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:32]

    # PAY-XI-11: Check if this webhook was already processed (idempotency)
    existing = await db.execute(
        select(BigCommerceWebhookLog).where(
            BigCommerceWebhookLog.hash == payload_hash,
            BigCommerceWebhookLog.store_id == store_id,
        )
    )
    duplicate = existing.scalar_one_or_none()
    if duplicate and duplicate.status == "processed":
        logger.info("PAY-XI-11: Duplicate webhook skipped (hash=%s, scope=%s)", payload_hash, scope)
        return duplicate

    log = BigCommerceWebhookLog(
        store_id=store_id,
        scope=scope,
        webhook_id=webhook_id,
        hash=payload_hash,
        payload=payload,
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return log


@router.post("/bigcommerce")
async def handle_bigcommerce_webhook(
    request: Request,
    body: bytes = Depends(verify_webhook_signature),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Main webhook endpoint for all BigCommerce webhooks.

    BigCommerce webhook payload format:
    {
        "scope": "store/order/created",
        "store_id": "1234567",
        "data": {
            "type": "order",
            "id": 12345
        },
        "hash": "unique_hash",
        "created_at": 1234567890,
        "producer": "stores/abc123"
    }
    """
    start_time = datetime.utcnow()

    # Parse payload
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload",
        )

    # Extract store hash from producer
    producer = payload.get("producer", "")
    store_hash = producer.split("/")[-1] if producer else None

    if not store_hash:
        logger.warning("Webhook missing store hash")
        return {"status": "ignored", "reason": "missing_store_hash"}

    # Get store from database
    store = await get_store_by_hash(store_hash, db)

    if not store:
        logger.warning(f"Webhook for unknown store: {store_hash}")
        return {"status": "ignored", "reason": "store_not_found"}

    # Get webhook scope
    scope = payload.get("scope", "")

    # Log webhook (with idempotency check — PAY-XI-11)
    webhook_log = await log_webhook(
        db=db,
        store_id=store.id,
        scope=scope,
        payload=payload,
        webhook_id=payload.get("hash"),
    )

    # PAY-XI-11: If webhook was already processed, return immediately
    if webhook_log.status == "processed":
        return {"status": "duplicate", "result": "already_processed"}

    # Route to handler based on scope
    try:
        result = await route_webhook(
            scope=scope,
            store=store,
            payload=payload,
            db=db,
        )

        # Update webhook log
        webhook_log.mark_processed(result)
        webhook_log.set_processing_time(start_time)
        await db.commit()

        return {"status": "processed", "result": result}

    except Exception as e:
        logger.exception(f"Webhook processing error: {e}")
        webhook_log.mark_failed(str(e))
        await db.commit()

        # Return 200 to prevent BigCommerce from retrying
        return {"status": "error", "error": str(e)}


async def route_webhook(
    scope: str,
    store: BigCommerceStore,
    payload: dict,
    db: AsyncSession,
) -> dict:
    """
    Route webhook to appropriate handler based on scope.

    Args:
        scope: BigCommerce webhook scope
        store: Store record
        payload: Webhook payload
        db: Database session

    Returns:
        dict: Handler result
    """
    handlers = {
        "store/order/created": handle_order_created,
        "store/order/updated": handle_order_updated,
        "store/order/statusUpdated": handle_order_status_updated,
        "store/product/created": handle_product_created,
        "store/product/updated": handle_product_updated,
        "store/product/deleted": handle_product_deleted,
        "store/app/uninstalled": handle_app_uninstalled,
    }

    handler = handlers.get(scope)
    if not handler:
        logger.info(f"Unhandled webhook scope: {scope}")
        return {"status": "unhandled", "scope": scope}

    return await handler(store, payload, db)


# ============== Order Handlers ==============


async def handle_order_created(
    store: BigCommerceStore,
    payload: dict,
    db: AsyncSession,
) -> dict:
    """Handle store/order/created webhook."""
    data = payload.get("data", {})
    order_id = data.get("id")

    logger.info(f"Order created: {order_id} for {store.store_hash}")

    # BigCommerce order webhooks only contain the order ID
    # We need to fetch the full order data for conversion tracking
    # For now, we'll wait for the order status update

    return {
        "status": "logged",
        "order_id": order_id,
    }


async def handle_order_updated(
    store: BigCommerceStore,
    payload: dict,
    db: AsyncSession,
) -> dict:
    """Handle store/order/updated webhook."""
    data = payload.get("data", {})
    order_id = data.get("id")

    logger.info(f"Order updated: {order_id} for {store.store_hash}")

    return {
        "status": "logged",
        "order_id": order_id,
    }


async def handle_order_status_updated(
    store: BigCommerceStore,
    payload: dict,
    db: AsyncSession,
) -> dict:
    """
    Handle store/order/statusUpdated webhook.

    This is where we track conversions - when an order status changes
    to a "completed" status (paid, shipped, etc.)
    """
    data = payload.get("data", {})
    order_id = data.get("id")
    new_status = data.get("status", {})
    status_id = new_status.get("new_status_id")

    logger.info(f"Order status updated: {order_id} -> {status_id} for {store.store_hash}")

    # BigCommerce status IDs:
    # 1 = Pending
    # 2 = Shipped
    # 3 = Partially Shipped
    # 4 = Refunded
    # 5 = Cancelled
    # 6 = Declined
    # 7 = Awaiting Payment
    # 8 = Awaiting Pickup
    # 9 = Awaiting Shipment
    # 10 = Completed
    # 11 = Awaiting Fulfillment
    # 12 = Manual Verification Required

    # Track conversion only for payment-confirmed statuses
    # Status 11 (Awaiting Fulfillment) removed — payment not yet confirmed
    conversion_statuses = [2, 3, 10]  # Shipped, Partially Shipped, Completed
    refund_statuses = [4, 5, 6]  # Refunded, Cancelled, Declined

    if status_id in conversion_statuses:
        # Need to fetch full order data
        from app.services.bigcommerce_client import BigCommerceClient
        from app.utils.encryption import decrypt_token

        access_token = decrypt_token(store.access_token)

        async with BigCommerceClient(store.store_hash, access_token) as client:
            order_data = await client.get_order(order_id)

        conversion_service = ConversionService(db)
        return await conversion_service.process_order(
            store, order_data, scope="store/order/statusUpdated"
        )

    elif status_id in refund_statuses:
        from app.services.bigcommerce_client import BigCommerceClient
        from app.utils.encryption import decrypt_token

        access_token = decrypt_token(store.access_token)

        async with BigCommerceClient(store.store_hash, access_token) as client:
            order_data = await client.get_order(order_id)

        conversion_service = ConversionService(db)
        return await conversion_service.process_refund(store, order_data)

    return {
        "status": "logged",
        "order_id": order_id,
        "status_id": status_id,
    }


# ============== Product Handlers ==============


async def handle_product_created(
    store: BigCommerceStore,
    payload: dict,
    db: AsyncSession,
) -> dict:
    """Handle store/product/created webhook."""
    data = payload.get("data", {})
    product_id = data.get("id")

    logger.info(f"Product created: {product_id} for {store.store_hash}")

    # Fetch full product data if auto-sync is enabled
    if store.auto_sync_products:
        from app.services.bigcommerce_client import BigCommerceClient
        from app.utils.encryption import decrypt_token

        access_token = decrypt_token(store.access_token)

        async with BigCommerceClient(store.store_hash, access_token) as client:
            product_data = await client.get_product(
                product_id,
                include=["images", "custom_fields"],
            )

        product_service = ProductSyncService(db)
        product = await product_service.sync_product_from_webhook(
            store, {"data": product_data}
        )

        return {
            "status": "synced",
            "product_id": str(product.id),
            "bc_product_id": product.bc_product_id,
        }

    return {
        "status": "logged",
        "product_id": product_id,
    }


async def handle_product_updated(
    store: BigCommerceStore,
    payload: dict,
    db: AsyncSession,
) -> dict:
    """Handle store/product/updated webhook."""
    data = payload.get("data", {})
    product_id = data.get("id")

    logger.info(f"Product updated: {product_id} for {store.store_hash}")

    if store.auto_sync_products:
        from app.services.bigcommerce_client import BigCommerceClient
        from app.utils.encryption import decrypt_token

        access_token = decrypt_token(store.access_token)

        async with BigCommerceClient(store.store_hash, access_token) as client:
            product_data = await client.get_product(
                product_id,
                include=["images", "custom_fields"],
            )

        product_service = ProductSyncService(db)
        product = await product_service.sync_product_from_webhook(
            store, {"data": product_data}
        )

        return {
            "status": "updated",
            "product_id": str(product.id),
            "bc_product_id": product.bc_product_id,
        }

    return {
        "status": "logged",
        "product_id": product_id,
    }


async def handle_product_deleted(
    store: BigCommerceStore,
    payload: dict,
    db: AsyncSession,
) -> dict:
    """Handle store/product/deleted webhook."""
    data = payload.get("data", {})
    product_id = data.get("id")

    logger.info(f"Product deleted: {product_id} for {store.store_hash}")

    product_service = ProductSyncService(db)
    deleted = await product_service.delete_product_from_webhook(
        store, {"data": {"id": product_id}}
    )

    return {
        "status": "deleted" if deleted else "not_found",
        "bc_product_id": product_id,
    }


# ============== App Handlers ==============


async def handle_app_uninstalled(
    store: BigCommerceStore,
    payload: dict,
    db: AsyncSession,
) -> dict:
    """
    Handle store/app/uninstalled webhook.

    When merchant uninstalls the app:
    1. Mark store as inactive
    2. Clear access token
    3. Keep data for potential reinstall
    """
    store_service = StoreService(db)
    await store_service.uninstall_store(store.store_hash)
    return {"status": "uninstalled", "store_hash": store.store_hash}
