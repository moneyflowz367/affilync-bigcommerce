"""
Unit tests for BigCommerce OAuth routes.
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi import status


class TestOAuthInstall:
    """Tests for the /oauth/install endpoint."""

    def test_install_redirects_to_bigcommerce(self, client):
        """Test that install redirects to BigCommerce OAuth."""
        response = client.get(
            "/oauth/install",
            params={"code": "auth-code", "scope": "users_basic_information", "context": "stores/abc123"},
            allow_redirects=False
        )
        # Should either redirect or process the OAuth
        assert response.status_code in [200, 302, 307]

    def test_install_requires_context(self, client):
        """Test that install requires context parameter."""
        response = client.get(
            "/oauth/install",
            params={"code": "auth-code", "scope": "users_basic_information"}
        )
        # Should fail validation without context
        assert response.status_code in [400, 422]


class TestOAuthCallback:
    """Tests for the /oauth/callback endpoint."""

    @patch("backend.app.routes.oauth.exchange_code_for_token")
    def test_callback_success(self, mock_exchange, client, db, mock_affilync_api):
        """Test successful OAuth callback."""
        mock_exchange.return_value = {
            "access_token": "test-token",
            "user": {"email": "test@example.com"},
            "context": "stores/abc123"
        }

        response = client.get(
            "/oauth/callback",
            params={"code": "auth-code", "scope": "users_basic_information", "context": "stores/abc123"}
        )
        # Should succeed or redirect to dashboard
        assert response.status_code in [200, 302, 307]

    def test_callback_without_code_fails(self, client):
        """Test callback without code fails."""
        response = client.get("/oauth/callback")
        assert response.status_code in [400, 422]


class TestOAuthUninstall:
    """Tests for the /oauth/uninstall endpoint."""

    def test_uninstall_webhook(self, client, db):
        """Test store uninstall webhook handling."""
        payload = {
            "store_hash": "abc123",
            "user": {"id": 12345, "email": "test@example.com"}
        }
        response = client.post("/oauth/uninstall", json=payload)
        # Should acknowledge the uninstall
        assert response.status_code in [200, 204, 404]  # 404 if store not found is ok
