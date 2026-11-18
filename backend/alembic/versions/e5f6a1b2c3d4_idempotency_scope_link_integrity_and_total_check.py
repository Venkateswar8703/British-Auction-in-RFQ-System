"""idempotency scope link integrity and total check

Revision ID: e5f6a1b2c3d4
Revises: d4e5f6a1b2c3
Create Date: 2026-11-18 18:32:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'e5f6a1b2c3d4'
down_revision: Union[str, None] = 'd4e5f6a1b2c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = (bind.dialect.name == "postgresql")

    # 1. Total check constraint on bids
    if is_postgres:
        op.create_check_constraint(
            'chk_total_equals_components',
            'bids',
            'total = freight_charges + origin_charges + destination_charges'
        )

    # 2. Idempotency key index: replace global unique index with partial composite unique index
    try:
        op.drop_index('ix_bids_idempotency_key', table_name='bids')
    except Exception:
        pass

    if is_postgres:
        op.create_index(
            'idx_bids_rfq_supplier_idem',
            'bids',
            ['rfq_id', 'supplier_id', 'idempotency_key'],
            unique=True,
            postgresql_where=sa.text('idempotency_key IS NOT NULL')
        )
    else:
        op.create_index(
            'idx_bids_rfq_supplier_idem',
            'bids',
            ['rfq_id', 'supplier_id', 'idempotency_key'],
            unique=True,
            sqlite_where=sa.text('idempotency_key IS NOT NULL')
        )

    # 3. Link integrity
    if is_postgres:
        # Populate any NULL triggering_bid_id in auction_extensions before altering to NOT NULL
        op.execute(
            """
            UPDATE auction_extensions ext
            SET triggering_bid_id = sub.id
            FROM (
                SELECT DISTINCT ON (rfq_id) id, rfq_id
                FROM bids
                ORDER BY rfq_id, created_at DESC
            ) sub
            WHERE ext.rfq_id = sub.rfq_id AND ext.triggering_bid_id IS NULL;
            """
        )
        op.execute("DELETE FROM auction_extensions WHERE triggering_bid_id IS NULL;")

        # auction_extensions.triggering_bid_id: NOT NULL, ON DELETE RESTRICT
        op.drop_constraint('auction_extensions_triggering_bid_id_fkey', 'auction_extensions', type_='foreignkey')
        op.alter_column('auction_extensions', 'triggering_bid_id', nullable=False)
        op.create_foreign_key(
            'auction_extensions_triggering_bid_id_fkey',
            'auction_extensions',
            'bids',
            ['triggering_bid_id'],
            ['id'],
            ondelete='RESTRICT'
        )

        # auction_events.bid_id: keep nullable=True, ON DELETE RESTRICT
        op.drop_constraint('auction_events_bid_id_fkey', 'auction_events', type_='foreignkey')
        op.create_foreign_key(
            'auction_events_bid_id_fkey',
            'auction_events',
            'bids',
            ['bid_id'],
            ['id'],
            ondelete='RESTRICT'
        )


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = (bind.dialect.name == "postgresql")

    if is_postgres:
        # auction_events.bid_id -> revert to ON DELETE SET NULL
        op.drop_constraint('auction_events_bid_id_fkey', 'auction_events', type_='foreignkey')
        op.create_foreign_key(
            'auction_events_bid_id_fkey',
            'auction_events',
            'bids',
            ['bid_id'],
            ['id'],
            ondelete='SET NULL'
        )

        # auction_extensions.triggering_bid_id -> revert to nullable=True, ON DELETE SET NULL
        op.drop_constraint('auction_extensions_triggering_bid_id_fkey', 'auction_extensions', type_='foreignkey')
        op.alter_column('auction_extensions', 'triggering_bid_id', nullable=True)
        op.create_foreign_key(
            'auction_extensions_triggering_bid_id_fkey',
            'auction_extensions',
            'bids',
            ['triggering_bid_id'],
            ['id'],
            ondelete='SET NULL'
        )

    op.drop_index('idx_bids_rfq_supplier_idem', table_name='bids')
    op.create_index('ix_bids_idempotency_key', 'bids', ['idempotency_key'], unique=True)

    if is_postgres:
        op.drop_constraint('chk_total_equals_components', 'bids', type_='check')
