"""add min decrement to auction configs

Revision ID: c3d4e5f6a1b2
Revises: b225e45624e2
Create Date: 2026-11-18 15:56:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'c3d4e5f6a1b2'
down_revision: Union[str, None] = 'b225e45624e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column(
        'auction_configs',
        sa.Column('min_decrement', sa.Numeric(12, 2), nullable=True, server_default='0.00')
    )

def downgrade() -> None:
    op.drop_column('auction_configs', 'min_decrement')

