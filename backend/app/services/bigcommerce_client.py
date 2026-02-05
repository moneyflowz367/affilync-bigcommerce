"""
BigCommerce API Client
Handles all API interactions with BigCommerce
"""

import logging
from typing import Any, Dict, List, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class BigCommerceAPIError(Exception):
    """Error from BigCommerce API."""

    def __init__(self, message: str, status_code: int = None, response: dict = None):
        self.message = message
        self.status_code = status_code
        self.response = response or {}
        super().__init__(message)


class BigCommerceClient:
    """
    Client for BigCommerce API interactions.

    BigCommerce API uses store_hash for routing and access tokens for auth.
    API URL format: https://api.bigcommerce.com/stores/{store_hash}/v3/{endpoint}
    """

    def __init__(self, store_hash: str, access_token: str):
        """
        Initialize BigCommerce client.

        Args:
            store_hash: Store hash identifier
            access_token: OAuth access token
        """
        self.store_hash = store_hash
        self.access_token = access_token
        self.base_url = f"{settings.bigcommerce_api_url}/stores/{store_hash}"
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        """Async context manager entry."""
        self._client = httpx.AsyncClient(
            headers=self._get_headers(),
            timeout=30.0,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _get_headers(self) -> Dict[str, str]:
        """Get default request headers."""
        return {
            "X-Auth-Token": self.access_token,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _request(
        self,
        method: str,
        endpoint: str,
        json: Optional[Dict] = None,
        params: Optional[Dict] = None,
        version: str = "v3",
    ) -> Dict[str, Any]:
        """
        Make an authenticated request to BigCommerce API.

        Args:
            method: HTTP method
            endpoint: API endpoint path (without version prefix)
            json: JSON body data
            params: Query parameters
            version: API version (v2 or v3)

        Returns:
            Response JSON data

        Raises:
            BigCommerceAPIError: On API error
        """
        url = f"{self.base_url}/{version}/{endpoint.lstrip('/')}"

        if self._client is None:
            raise RuntimeError("Client not initialized. Use async context manager.")

        try:
            response = await self._client.request(
                method=method,
                url=url,
                json=json,
                params=params,
            )

            # BigCommerce rate limiting
            if response.status_code == 429:
                retry_after = response.headers.get("X-Rate-Limit-Time-Reset-Ms", "1000")
                raise BigCommerceAPIError(
                    f"Rate limited. Retry after {retry_after}ms",
                    status_code=429,
                )

            if response.status_code >= 400:
                error_data = {}
                try:
                    error_data = response.json()
                except Exception:
                    pass

                raise BigCommerceAPIError(
                    message=error_data.get("title", f"API error: {response.status_code}"),
                    status_code=response.status_code,
                    response=error_data,
                )

            if response.status_code == 204:
                return {}

            return response.json()

        except httpx.TimeoutException:
            raise BigCommerceAPIError("Request timeout", status_code=504)
        except httpx.RequestError as e:
            raise BigCommerceAPIError(f"Request failed: {str(e)}", status_code=503)

    # ============== Store Information ==============

    async def get_store(self) -> Dict[str, Any]:
        """Get store information."""
        response = await self._request("GET", "store", version="v2")
        return response

    async def get_store_status(self) -> Dict[str, Any]:
        """Get store status information."""
        response = await self._request("GET", "store/information", version="v2")
        return response

    # ============== Products ==============

    async def get_products(
        self,
        page: int = 1,
        limit: int = 50,
        include: Optional[List[str]] = None,
        is_visible: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        Get products from the store.

        Args:
            page: Page number
            limit: Products per page (max 250)
            include: Additional fields to include (images, custom_fields, etc.)
            is_visible: Filter by visibility

        Returns:
            Response with data array and pagination
        """
        params = {
            "page": page,
            "limit": min(limit, 250),
        }

        if include:
            params["include"] = ",".join(include)
        if is_visible is not None:
            params["is_visible"] = is_visible

        return await self._request("GET", "catalog/products", params=params)

    async def get_product(
        self,
        product_id: int,
        include: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Get a single product by ID.

        Args:
            product_id: BigCommerce product ID
            include: Additional fields to include

        Returns:
            Product data
        """
        params = {}
        if include:
            params["include"] = ",".join(include)

        response = await self._request(
            "GET",
            f"catalog/products/{product_id}",
            params=params,
        )
        return response.get("data", {})

    async def get_all_products(
        self,
        include: Optional[List[str]] = None,
        is_visible: Optional[bool] = True,
    ) -> List[Dict[str, Any]]:
        """
        Get all products from the store (handles pagination).

        Args:
            include: Additional fields to include
            is_visible: Filter by visibility

        Returns:
            List of all products
        """
        all_products = []
        page = 1
        limit = 250

        while True:
            response = await self.get_products(
                page=page,
                limit=limit,
                include=include,
                is_visible=is_visible,
            )

            products = response.get("data", [])
            all_products.extend(products)

            # Check pagination
            pagination = response.get("meta", {}).get("pagination", {})
            total_pages = pagination.get("total_pages", 1)

            if page >= total_pages:
                break

            page += 1

        return all_products

    # ============== Orders ==============

    async def get_order(self, order_id: int) -> Dict[str, Any]:
        """
        Get order by ID.

        Args:
            order_id: BigCommerce order ID

        Returns:
            Order data
        """
        return await self._request("GET", f"orders/{order_id}", version="v2")

    async def get_order_products(self, order_id: int) -> List[Dict[str, Any]]:
        """
        Get products in an order.

        Args:
            order_id: BigCommerce order ID

        Returns:
            List of order products
        """
        return await self._request("GET", f"orders/{order_id}/products", version="v2")

    async def get_orders(
        self,
        min_id: Optional[int] = None,
        max_id: Optional[int] = None,
        status_id: Optional[int] = None,
        limit: int = 50,
        page: int = 1,
    ) -> List[Dict[str, Any]]:
        """
        Get orders with filters.

        Args:
            min_id: Minimum order ID
            max_id: Maximum order ID
            status_id: Order status ID
            limit: Orders per page
            page: Page number

        Returns:
            List of orders
        """
        params = {"limit": limit, "page": page}

        if min_id:
            params["min_id"] = min_id
        if max_id:
            params["max_id"] = max_id
        if status_id:
            params["status_id"] = status_id

        return await self._request("GET", "orders", params=params, version="v2")

    # ============== Webhooks ==============

    async def create_webhook(
        self,
        scope: str,
        destination: str,
        is_active: bool = True,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Create a webhook.

        Args:
            scope: Webhook scope (e.g., "store/order/created")
            destination: Webhook callback URL
            is_active: Whether webhook is active
            headers: Optional headers to send with webhook

        Returns:
            Created webhook data
        """
        data = {
            "scope": scope,
            "destination": destination,
            "is_active": is_active,
        }

        if headers:
            data["headers"] = headers

        response = await self._request("POST", "hooks", json=data)
        return response.get("data", {})

    async def get_webhooks(self) -> List[Dict[str, Any]]:
        """Get all webhooks for the store."""
        response = await self._request("GET", "hooks")
        return response.get("data", [])

    async def delete_webhook(self, webhook_id: int) -> bool:
        """
        Delete a webhook.

        Args:
            webhook_id: Webhook ID

        Returns:
            True if deleted
        """
        try:
            await self._request("DELETE", f"hooks/{webhook_id}")
            return True
        except BigCommerceAPIError as e:
            if e.status_code == 404:
                return False
            raise

    async def register_all_webhooks(self, callback_url: str) -> List[Dict[str, Any]]:
        """
        Register all required webhooks for the app.

        Args:
            callback_url: Base callback URL

        Returns:
            List of created webhooks
        """
        # Define required webhook scopes
        scopes = [
            "store/order/created",
            "store/order/updated",
            "store/order/statusUpdated",
            "store/product/created",
            "store/product/updated",
            "store/product/deleted",
            "store/app/uninstalled",
        ]

        # Get existing webhooks
        existing = await self.get_webhooks()
        existing_scopes = {w.get("scope") for w in existing}

        created = []
        for scope in scopes:
            if scope not in existing_scopes:
                webhook = await self.create_webhook(
                    scope=scope,
                    destination=callback_url,
                    is_active=True,
                )
                created.append(webhook)
                logger.info(f"Created webhook: {scope}")
            else:
                logger.debug(f"Webhook already exists: {scope}")

        return created

    # ============== Categories ==============

    async def get_categories(self) -> List[Dict[str, Any]]:
        """Get all categories."""
        response = await self._request("GET", "catalog/categories", params={"limit": 250})
        return response.get("data", [])

    async def get_category(self, category_id: int) -> Dict[str, Any]:
        """Get a single category."""
        response = await self._request("GET", f"catalog/categories/{category_id}")
        return response.get("data", {})

    # ============== Customers ==============

    async def get_customer(self, customer_id: int) -> Dict[str, Any]:
        """Get customer by ID."""
        response = await self._request("GET", f"customers", params={"id:in": customer_id})
        customers = response.get("data", [])
        return customers[0] if customers else {}
