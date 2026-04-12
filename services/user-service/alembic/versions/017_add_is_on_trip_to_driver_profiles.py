"""add_is_on_trip_to_driver_profiles

Revision ID: 017
Revises: 016
Create Date: 2026-04-12 21:14:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '017'
down_revision: Union[str, None] = '016'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add is_on_trip column to driver_profiles
    op.add_column(
        'driver_profiles',
        sa.Column('is_on_trip', sa.Boolean(), nullable=False, server_default='false')
    )


def downgrade() -> None:
    op.drop_column('driver_profiles', 'is_on_trip')
