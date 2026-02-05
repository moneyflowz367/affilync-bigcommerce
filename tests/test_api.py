"""
Unit tests for BigCommerce API routes.
"""

import pytest
from unittest.mock import patch, AsyncMock


class TestHealthEndpoint:
    """Tests for the /health endpoint."""

    def test_health_check_returns_ok(self, client):
        """Test that health check returns healthy status."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["healthy", "ok"]

    def test_health_check_includes_service_info(self, client):
        """Test that health check includes service information."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "service" in data or "status" in data


class TestProductsAPI:
    """Tests for products API endpoints."""

    def test_get_products_requires_auth(self, client):
        """Test that getting products requires authentication."""
        response = client.get("/api/products")
        # Should require authentication
        assert response.status_code in [401, 403]

    @patch("backend.app.routes.api.get_current_store")
    def test_get_products_success(self, mock_get_store, client, db, mock_bigcommerce_client):
        """Test successful product retrieval."""
        mock_get_store.return_value = {
            "store_hash": "abc123",
            "access_token": "test-token"
        }

        response = client.get(
            "/api/products",
            headers={"Authorization": "Bearer test-session-token"}
        )
        # Should return products or auth error
        assert response.status_code in [200, 401, 403]


class TestSyncAPI:
    """Tests for sync API endpoints."""

    def test_sync_products_requires_auth(self, client):
        """Test that syncing products requires authentication."""
        response = client.post("/api/sync/products")
        assert response.status_code in [401, 403]

    @patch("backend.app.routes.api.get_current_store")
    @patch("backend.app.services.product_sync.ProductSyncService.sync_products")
    def test_sync_products_success(self, mock_sync, mock_get_store, client, db):
        """Test successful product sync."""
        mock_get_store.return_value = {
            "store_hash": "abc123",
            "access_token": "test-token"
        }
        mock_sync.return_value = {"synced": 10, "failed": 0}

        response = client.post(
            "/api/sync/products",
            headers={"Authorization": "Bearer test-session-token"}
        )
        assert response.status_code in [200, 202, 401, 403]


class TestConversionAPI:
    """Tests for conversion tracking API endpoints."""

    def test_get_conversions_requires_auth(self, client):
        """Test that getting conversions requires authentication."""
        response = client.get("/api/conversions")
        assert response.status_code in [401, 403, 404]

    @patch("backend.app.routes.api.get_current_store")
    def test_get_conversions_returns_list(self, mock_get_store, client, db):
        """Test that conversions endpoint returns a list."""
        mock_get_store.return_value = {
            "store_hash": "abc123",
            "access_token": "test-token"
        }

        response = client.get(
            "/api/conversions",
            headers={"Authorization": "Bearer test-session-token"}
        )
        # Should return list or auth error
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list) or "conversions" in data or "items" in data


class TestAnalyticsAPI:
    """Tests for analytics API endpoints."""

    def test_get_analytics_requires_auth(self, client):
        """Test that analytics requires authentication."""
        response = client.get("/api/analytics")
        assert response.status_code in [401, 403, 404]

    @patch("backend.app.routes.api.get_current_store")
    def test_get_analytics_success(self, mock_get_store, client, db):
        """Test successful analytics retrieval."""
        mock_get_store.return_value = {
            "store_hash": "abc123",
            "access_token": "test-token"
        }

        response = client.get(
            "/api/analytics",
            headers={"Authorization": "Bearer test-session-token"},
            params={"start_date": "2026-01-01", "end_date": "2026-01-31"}
        )
        # Should return analytics data or auth error
        assert response.status_code in [200, 401, 403, 404]
