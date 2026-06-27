"""Add bigcommerce_subscriptions table (subscription billing ladder)

Ports the TikTok Shop subscription-billing subsystem into BigCommerce. The
subscription is keyed to the BigCommerce store UUID (bigcommerce_stores.id),
the same identifier products and webhook logs link to. Plan ladder mirrors
TikTok: Free $0 / Starter $29 / Pro $99 / Enterprise $299.

Revision ID: 003_bigcommerce_subscriptions
Revises: 002_webhook_dedup_unique
Create Date: 2026-06-27

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "003_bigcommerce_subscriptions"
down_revision: Union[str, None] = "002_webhook_dedup_unique"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the bigcommerce_subscriptions table."""
    op.create_table(
        "bigcommerce_subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "store_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("bigcommerce_stores.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
            index=True,
        ),
        # Plan info
        sa.Column("plan", sa.String(50), nullable=False, server_default="free"),
        sa.Column("status", sa.String(50), nullable=False, server_default="active"),
        sa.Column("previous_plan", sa.String(50), nullable=True),
        # Pricing
        sa.Column("price_cents", sa.Integer(), server_default="0"),
        sa.Column("currency", sa.String(10), server_default="USD"),
        # Trial
        sa.Column("trial_days", sa.Integer(), server_default="0"),
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
        # Billing period
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        # Grace period
        sa.Column("grace_period_ends", sa.DateTime(timezone=True), nullable=True),
        sa.Column("downgrade_reason", sa.String(100), nullable=True),
        # Usage tracking
        sa.Column("conversions_used", sa.Integer(), server_default="0"),
        sa.Column("creators_used", sa.Integer(), server_default="0"),
        sa.Column("products_synced", sa.Integer(), server_default="0"),
        # Metadata
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), server_default="{}"),
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )


def downgrade() -> None:
    """Drop the bigcommerce_subscriptions table."""
    op.drop_table("bigcommerce_subscriptions")
