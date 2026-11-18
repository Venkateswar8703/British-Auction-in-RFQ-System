"""add bid visibility and non negative charges check

Revision ID: d4e5f6a1b2c3
Revises: c3d4e5f6a1b2
Create Date: 2026-11-18 16:56:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'd4e5f6a1b2c3'
down_revision: Union[str, None] = 'c3d4e5f6a1b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add bid_visibility column
    op.add_column(
        'auction_configs',
        sa.Column('bid_visibility', sa.String(20), nullable=False, server_default='OPEN')
    )

    # Adjust constraints on bids to allow origin and destination charges >= 0
    # In SQLite, constraint drops/adds require batch or are no-ops
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.drop_constraint('chk_origin_pos', 'bids', type_='check')
        op.drop_constraint('chk_destination_pos', 'bids', type_='check')
        op.create_check_constraint('chk_origin_non_neg', 'bids', 'origin_charges >= 0')
        op.create_check_constraint('chk_destination_non_neg', 'bids', 'destination_charges >= 0')


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.drop_constraint('chk_destination_non_neg', 'bids', type_='check')
        op.drop_constraint('chk_origin_non_neg', 'bids', type_='check')
        op.create_check_constraint('chk_destination_pos', 'bids', 'destination_charges > 0')
        op.create_check_constraint('chk_origin_pos', 'bids', 'origin_charges > 0')

    op.drop_column('auction_configs', 'bid_visibility')

