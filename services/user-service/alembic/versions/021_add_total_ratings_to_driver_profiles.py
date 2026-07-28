"""add_total_ratings_to_driver_profiles

Revision ID: 021
Revises: 020
Create Date: 2026-07-27 00:00:00.000000

Splits the rating counter out of total_trips.

Until now total_trips was incremented only by the ride.rating.submitted
consumer, so its value was really "number of ratings received" and it was used
as the weight for the running rating average.  Trip completion now owns
total_trips, so the rating average needs its own counter.

Seeding total_ratings from the existing total_trips is exact: every increment
that produced the current total_trips value came from a rating event.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '021'
down_revision: Union[str, None] = '020'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'driver_profiles',
        sa.Column('total_ratings', sa.Integer(), nullable=False, server_default='0')
    )
    # Historical total_trips was only ever bumped by rating events, so it is the
    # correct starting value for the rating count.
    op.execute('UPDATE driver_profiles SET total_ratings = total_trips')


def downgrade() -> None:
    op.drop_column('driver_profiles', 'total_ratings')
