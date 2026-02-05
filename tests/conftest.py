"""
Pytest configuration and fixtures for BigCommerce integration tests.
"""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Set test environment variables before importing app
os.environ.setdefault("BIGCOMMERCE_CLIENT_ID", "test-client-id")
os.environ.setdefault("BIGCOMMERCE_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("ENCRYPTION_KEY", "test-encryption-key-32chars-long!")
os.environ.setdefault("AFFILYNC_API_URL", "https://api.affilync.com")
os.environ.setdefault("AFFILYNC_API_KEY", "test-api-key")

from backend.app.main import app
from backend.app.database import Base, get_db


# Create test database
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db():
    """Create a fresh database for each test."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db):
    """Create a test client with database override."""
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def mock_bigcommerce_client():
    """Mock BigCommerce API client."""
    with patch("backend.app.services.bigcommerce_client.BigCommerceClient") as mock:
        client = AsyncMock()
        client.get_store_info.return_value = {
            "id": "store123",
            "name": "Test Store",
            "domain": "test-store.mybigcommerce.com"
        }
        client.get_products.return_value = {
            "data": [
                {
                    "id": 1,
                    "name": "Test Product",
                    "price": 29.99,
                    "sku": "TEST-001"
                }
            ],
            "meta": {"pagination": {"total": 1}}
        }
        mock.return_value = client
        yield client


@pytest.fixture
def mock_affilync_api():
    """Mock Affilync API calls."""
    with patch("backend.app.services.store_service.httpx.AsyncClient") as mock:
        client = AsyncMock()
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"brand_id": "brand-123", "verified": True}
        client.__aenter__.return_value.post.return_value = response
        client.__aenter__.return_value.get.return_value = response
        mock.return_value = client
        yield client


@pytest.fixture
def sample_store_data():
    """Sample store data for testing."""
    return {
        "store_hash": "abc123def",
        "access_token": "test-access-token",
        "email": "store@example.com",
        "store_name": "Test BigCommerce Store"
    }


@pytest.fixture
def sample_webhook_payload():
    """Sample webhook payload for testing."""
    return {
        "scope": "store/order/created",
        "store_id": "abc123def",
        "data": {
            "type": "order",
            "id": 12345
        },
        "hash": "valid-hmac-hash",
        "created_at": 1706723456,
        "producer": "stores/abc123def"
    }
