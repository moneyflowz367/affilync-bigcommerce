"""
Store Service
Manages BigCommerce store installations and OAuth
"""

import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import BigCommerceStore
from app.services.bigcommerce_client import BigCommerceClient
from app.utils.encryption import encrypt_token, decrypt_token

logger = logging.getLogger(__name__)


class StoreService:
    """Service for managing store installations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_store_by_hash(self, store_hash: str) -> Optional[BigCommerceStore]:
        """Get store by store hash."""
        result = await self.db.execute(
            select(BigCommerceStore).where(BigCommerceStore.store_hash == store_hash)
        )
        return result.scalar_one_or_none()

    async def get_store_by_id(self, store_id: UUID) -> Optional[BigCommerceStore]:
        """Get store by ID."""
        result = await self.db.execute(
            select(BigCommerceStore).where(BigCommerceStore.id == store_id)
        )
        return result.scalar_one_or_none()

    async def get_active_stores(self) -> list[BigCommerceStore]:
        """Get all active store installations."""
        result = await self.db.execute(
            select(BigCommerceStore).where(BigCommerceStore.is_active == True)
        )
        return result.scalars().all()

    async def exchange_token(
        self,
        code: str,
        scope: str,
        context: str,
    ) -> dict:
        """
        Exchange authorization code for access token.

        Args:
            code: Authorization code from OAuth callback
            scope: Granted scopes
            context: Store context string (stores/{store_hash})

        Returns:
            dict: Token response with access_token, user info, etc.

        Raises:
            Exception: On token exchange failure
        """
        url = f"{settings.bigcommerce_auth_url}/oauth2/token"

        data = {
            "client_id": settings.bigcommerce_client_id,
            "client_secret": settings.bigcommerce_client_secret,
            "code": code,
            "scope": scope,
            "grant_type": "authorization_code",
            "redirect_uri": f"{settings.app_url}/oauth/callback",
            "context": context,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, data=data)

            if response.status_code != 200:
                logger.error(f"Token exchange failed: {response.text}")
                raise Exception(f"Token exchange failed: {response.status_code}")

            return response.json()

    async def install_store(
        self,
        store_hash: str,
        access_token: str,
        scope: str,
        user: dict = None,
    ) -> BigCommerceStore:
        """
        Install or reinstall app for a store.

        Args:
            store_hash: BigCommerce store hash
            access_token: OAuth access token
            scope: Granted scopes
            user: BigCommerce user info

        Returns:
            BigCommerceStore: Created or updated store record
        """
        # Check for existing store
        existing = await self.get_store_by_hash(store_hash)

        # Encrypt access token
        encrypted_token = encrypt_token(access_token)

        if existing:
            # Reinstall - update token and reactivate
            existing.access_token = encrypted_token
            existing.scope = scope
            existing.is_active = True
            existing.uninstalled_at = None
            existing.updated_at = datetime.utcnow()

            if user:
                existing.bc_user_id = str(user.get("id"))
                existing.bc_user_email = user.get("email")

            logger.info(f"Store reinstalled: {store_hash}")
            await self.db.commit()
            return existing

        # Get store info from BigCommerce
        store_name = None
        store_email = None
        store_domain = None

        try:
            async with BigCommerceClient(store_hash, access_token) as client:
                store_info = await client.get_store()
                store_name = store_info.get("name")
                store_email = store_info.get("admin_email")
                store_domain = store_info.get("domain")
        except Exception as e:
            logger.warning(f"Failed to get store info: {e}")

        # Create new store record
        store = BigCommerceStore(
            store_hash=store_hash,
            store_name=store_name,
            store_email=store_email,
            store_domain=store_domain,
            access_token=encrypted_token,
            scope=scope,
            bc_user_id=str(user.get("id")) if user else None,
            bc_user_email=user.get("email") if user else None,
            is_active=True,
            settings={
                "auto_sync_products": False,
                "cookie_duration_days": settings.default_cookie_duration_days,
                "attribution_model": settings.default_attribution_model,
            },
        )

        self.db.add(store)
        await self.db.commit()
        await self.db.refresh(store)

        logger.info(f"New store installed: {store_hash}")
        return store

    async def uninstall_store(self, store_hash: str) -> bool:
        """
        Handle app uninstall webhook.

        Args:
            store_hash: Store hash

        Returns:
            bool: True if store was found and updated
        """
        store = await self.get_store_by_hash(store_hash)

        if not store:
            logger.warning(f"Uninstall webhook for unknown store: {store_hash}")
            return False

        store.is_active = False
        store.uninstalled_at = datetime.utcnow()
        # Clear access token for security
        store.access_token = ""

        await self.db.commit()
        logger.info(f"Store uninstalled: {store_hash}")
        return True

    async def register_webhooks(self, store: BigCommerceStore) -> list:
        """
        Register all required webhooks for a store.

        Args:
            store: Store record

        Returns:
            list: Created webhooks
        """
        access_token = decrypt_token(store.access_token)

        async with BigCommerceClient(store.store_hash, access_token) as client:
            webhooks = await client.register_all_webhooks(settings.webhook_callback_url)
            return webhooks

    async def update_store_settings(
        self,
        store_id: UUID,
        **settings_update,
    ) -> BigCommerceStore:
        """
        Update store settings.

        Args:
            store_id: Store ID
            **settings_update: Settings to update

        Returns:
            BigCommerceStore: Updated store
        """
        store = await self.get_store_by_id(store_id)
        if not store:
            raise ValueError(f"Store not found: {store_id}")

        store.update_settings(**settings_update)
        store.updated_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(store)
        return store

    async def connect_brand(
        self,
        store_id: UUID,
        brand_id: UUID,
    ) -> BigCommerceStore:
        """
        Connect store to an Affilync brand account.

        Args:
            store_id: Store ID
            brand_id: Affilync brand ID

        Returns:
            BigCommerceStore: Updated store
        """
        store = await self.get_store_by_id(store_id)
        if not store:
            raise ValueError(f"Store not found: {store_id}")

        store.brand_id = brand_id
        store.updated_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(store)

        logger.info(f"Store {store.store_hash} connected to brand {brand_id}")
        return store

    async def disconnect_brand(self, store_id: UUID) -> BigCommerceStore:
        """
        Disconnect store from Affilync brand account.

        Args:
            store_id: Store ID

        Returns:
            BigCommerceStore: Updated store
        """
        store = await self.get_store_by_id(store_id)
        if not store:
            raise ValueError(f"Store not found: {store_id}")

        store.brand_id = None
        store.updated_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(store)

        logger.info(f"Store {store.store_hash} disconnected from brand")
        return store

    def get_decrypted_token(self, store: BigCommerceStore) -> str:
        """Get decrypted access token for a store."""
        return decrypt_token(store.access_token)
