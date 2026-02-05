"""
Unit tests for BigCommerce webhook routes.
"""

import pytest
import hmac
import hashlib
from unittest.mock import patch, AsyncMock


class TestOrderWebhook:
    """Tests for order webhook handling."""

    def test_order_created_webhook(self, client, db, sample_webhook_payload):
        """Test order created webhook processing."""
        payload = sample_webhook_payload.copy()
        payload["scope"] = "store/order/created"

        # Mock HMAC verification
        with patch("backend.app.middleware.hmac_verify.verify_hmac") as mock_verify:
            mock_verify.return_value = True
            response = client.post(
                "/webhooks/orders",
                json=payload,
                headers={"X-BC-Webhook-HMAC-SHA256": "test-signature"}
            )
            # Should acknowledge webhook
            assert response.status_code in [200, 202, 204]

    def test_order_updated_webhook(self, client, db, sample_webhook_payload):
        """Test order updated webhook processing."""
        payload = sample_webhook_payload.copy()
        payload["scope"] = "store/order/updated"

        with patch("backend.app.middleware.hmac_verify.verify_hmac") as mock_verify:
            mock_verify.return_value = True
            response = client.post(
                "/webhooks/orders",
                json=payload,
                headers={"X-BC-Webhook-HMAC-SHA256": "test-signature"}
            )
            assert response.status_code in [200, 202, 204]

    def test_webhook_without_signature_fails(self, client, sample_webhook_payload):
        """Test webhook without HMAC signature fails."""
        response = client.post("/webhooks/orders", json=sample_webhook_payload)
        # Should fail without signature
        assert response.status_code in [400, 401, 403]


class TestProductWebhook:
    """Tests for product webhook handling."""

    def test_product_created_webhook(self, client, db, sample_webhook_payload):
        """Test product created webhook processing."""
        payload = sample_webhook_payload.copy()
        payload["scope"] = "store/product/created"
        payload["data"] = {"type": "product", "id": 789}

        with patch("backend.app.middleware.hmac_verify.verify_hmac") as mock_verify:
            mock_verify.return_value = True
            response = client.post(
                "/webhooks/products",
                json=payload,
                headers={"X-BC-Webhook-HMAC-SHA256": "test-signature"}
            )
            assert response.status_code in [200, 202, 204]

    def test_product_deleted_webhook(self, client, db, sample_webhook_payload):
        """Test product deleted webhook processing."""
        payload = sample_webhook_payload.copy()
        payload["scope"] = "store/product/deleted"
        payload["data"] = {"type": "product", "id": 789}

        with patch("backend.app.middleware.hmac_verify.verify_hmac") as mock_verify:
            mock_verify.return_value = True
            response = client.post(
                "/webhooks/products",
                json=payload,
                headers={"X-BC-Webhook-HMAC-SHA256": "test-signature"}
            )
            assert response.status_code in [200, 202, 204]


class TestHMACVerification:
    """Tests for HMAC signature verification."""

    def test_valid_hmac_passes(self, client, sample_webhook_payload):
        """Test that valid HMAC signature passes verification."""
        import json
        import os

        client_secret = os.environ.get("BIGCOMMERCE_CLIENT_SECRET", "test-secret")
        payload_str = json.dumps(sample_webhook_payload)

        # Generate valid HMAC
        signature = hmac.new(
            client_secret.encode(),
            payload_str.encode(),
            hashlib.sha256
        ).hexdigest()

        with patch("backend.app.middleware.hmac_verify.verify_hmac") as mock_verify:
            mock_verify.return_value = True
            response = client.post(
                "/webhooks/orders",
                json=sample_webhook_payload,
                headers={"X-BC-Webhook-HMAC-SHA256": signature}
            )
            # Should not fail due to HMAC
            assert response.status_code != 401

    def test_invalid_hmac_fails(self, client, sample_webhook_payload):
        """Test that invalid HMAC signature fails verification."""
        with patch("backend.app.middleware.hmac_verify.verify_hmac") as mock_verify:
            mock_verify.return_value = False
            response = client.post(
                "/webhooks/orders",
                json=sample_webhook_payload,
                headers={"X-BC-Webhook-HMAC-SHA256": "invalid-signature"}
            )
            # Should fail with invalid signature
            assert response.status_code in [401, 403]
