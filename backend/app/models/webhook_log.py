"""
BigCommerceWebhookLog Model - Webhook event logging
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.database import Base


class BigCommerceWebhookLog(Base):
    """
    Logs incoming webhooks from BigCommerce for debugging and auditing.
    """

    __tablename__ = "bigcommerce_webhook_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Store relationship
    store_id = Column(
        UUID(as_uuid=True),
        ForeignKey("bigcommerce_stores.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Webhook details
    scope = Column(String(100), nullable=False, index=True)  # e.g., "store/order/created"
    webhook_id = Column(String(255), index=True)  # BigCommerce webhook ID
    hash = Column(String(64), index=True)  # Event hash for deduplication

    # Payload
    payload = Column(JSONB, nullable=False)

    # Processing status
    status = Column(String(50), default="received", index=True)
    result = Column(JSONB)
    error = Column(Text)
    processing_time_ms = Column(Integer)

    # Timestamps
    received_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime)

    # Relationships
    store = relationship("BigCommerceStore", back_populates="webhook_logs")

    def __repr__(self) -> str:
        return f"<BigCommerceWebhookLog {self.scope} - {self.status}>"

    def mark_processed(self, result: dict = None) -> None:
        """Mark webhook as successfully processed."""
        self.status = "success"
        self.result = result
        self.processed_at = datetime.utcnow()

    def mark_failed(self, error: str) -> None:
        """Mark webhook as failed."""
        self.status = "failed"
        self.error = error
        self.processed_at = datetime.utcnow()

    def set_processing_time(self, start_time: datetime) -> None:
        """Calculate and set processing time."""
        if start_time:
            delta = datetime.utcnow() - start_time
            self.processing_time_ms = int(delta.total_seconds() * 1000)
