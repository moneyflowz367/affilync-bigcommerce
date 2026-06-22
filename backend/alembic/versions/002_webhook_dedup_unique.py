"""Atomic dedup: unique (store_id, hash) on bigcommerce_webhook_logs

The webhook handler dedups with a non-atomic check-then-insert (and a Redis
replay check that fails open on Redis outage), so two concurrent identical
BigCommerce webhooks — or a replay during a Redis outage — could both be
processed. A partial unique index makes the dedup atomic at the DB layer
(immune to the race and to Redis being down). hash IS NULL rows (legacy / not
deduped) are left unconstrained.

Revision ID: 002_webhook_dedup_unique
Revises: 001_initial
Create Date: 2026-06-22

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002_webhook_dedup_unique"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop any pre-existing duplicate (store_id, hash) rows (keep the earliest by
    # ctid) so the unique index can build. Only non-null hashes are deduped.
    op.execute(
        """
        DELETE FROM bigcommerce_webhook_logs a
        USING bigcommerce_webhook_logs b
        WHERE a.hash IS NOT NULL
          AND a.store_id = b.store_id
          AND a.hash = b.hash
          AND a.ctid > b.ctid
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_bc_webhook_logs_store_hash
        ON bigcommerce_webhook_logs (store_id, hash)
        WHERE hash IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_bc_webhook_logs_store_hash")
