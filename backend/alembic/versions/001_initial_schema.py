"""Initialize schema with BigCommerceStore, BigCommerceProduct, BigCommerceWebhookLog

Revision ID: 001_initial
Revises: None
Create Date: 2026-02-20

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create initial tables."""
    # bigcommerce_stores
    op.create_table(
        "bigcommerce_stores",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("store_hash", sa.String(50), unique=True, nullable=False, index=True),
        sa.Column("store_name", sa.String(255)),
        sa.Column("store_email", sa.String(255)),
        sa.Column("store_domain", sa.String(255)),
        sa.Column("access_token", sa.Text(), nullable=False),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("bc_user_id", sa.String(50), index=True),
        sa.Column("bc_user_email", sa.String(255)),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), index=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("installed_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.Column("uninstalled_at", sa.DateTime(), nullable=True),
        sa.Column("settings", postgresql.JSONB(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()")),
    )

    # bigcommerce_products
    op.create_table(
        "bigcommerce_products",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "store_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("bigcommerce_stores.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("bc_product_id", sa.Integer(), nullable=False, index=True),
        sa.Column("sku", sa.String(255), index=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("handle", sa.String(255), index=True),
        sa.Column("price", sa.Numeric(12, 2)),
        sa.Column("compare_at_price", sa.Numeric(12, 2)),
        sa.Column("cost_price", sa.Numeric(12, 2)),
        sa.Column("currency", sa.String(3), server_default="USD"),
        sa.Column("image_url", sa.Text()),
        sa.Column("images", postgresql.JSONB(), server_default="[]"),
        sa.Column("categories", postgresql.JSONB(), server_default="[]"),
        sa.Column("brand_name", sa.String(255)),
        sa.Column("inventory_level", sa.Integer()),
        sa.Column("inventory_tracking", sa.String(50)),
        sa.Column("is_visible", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("availability", sa.String(50), server_default="available"),
        sa.Column("affilync_product_id", postgresql.UUID(as_uuid=True), index=True),
        sa.Column("is_synced", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("last_synced_at", sa.DateTime(), nullable=True),
        sa.Column("sync_error", sa.Text()),
        sa.Column("metadata", postgresql.JSONB(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()")),
    )

    # bigcommerce_webhook_logs
    op.create_table(
        "bigcommerce_webhook_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "store_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("bigcommerce_stores.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("scope", sa.String(100), nullable=False, index=True),
        sa.Column("webhook_id", sa.String(255), index=True),
        sa.Column("hash", sa.String(64), index=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(50), server_default="received", index=True),
        sa.Column("result", postgresql.JSONB()),
        sa.Column("error", sa.Text()),
        sa.Column("processing_time_ms", sa.Integer()),
        sa.Column("received_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    """Drop all tables."""
    op.drop_table("bigcommerce_webhook_logs")
    op.drop_table("bigcommerce_products")
    op.drop_table("bigcommerce_stores")
