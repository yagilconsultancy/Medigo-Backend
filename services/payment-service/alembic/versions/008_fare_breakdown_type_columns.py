"""Add ride type, trip type, care assistant and accessibility columns to fare_breakdowns.

Revision ID: 008
Revises: 007
"""

import sqlalchemy as sa
from alembic import op

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("fare_breakdowns", sa.Column("care_assistant_fee", sa.Numeric(10, 2), server_default="0", nullable=True))
    op.add_column("fare_breakdowns", sa.Column("accessibility_fee", sa.Numeric(10, 2), server_default="0", nullable=True))
    op.add_column("fare_breakdowns", sa.Column("attendant_fee", sa.Numeric(10, 2), server_default="0", nullable=True))
    op.add_column("fare_breakdowns", sa.Column("trip_type", sa.String(30), nullable=True))
    op.add_column("fare_breakdowns", sa.Column("trip_structure", sa.String(20), nullable=True))
    op.add_column("fare_breakdowns", sa.Column("is_round_trip", sa.Boolean(), server_default="false", nullable=True))
    op.add_column("fare_breakdowns", sa.Column("return_distance_charge", sa.Numeric(10, 2), server_default="0", nullable=True))


def downgrade() -> None:
    op.drop_column("fare_breakdowns", "return_distance_charge")
    op.drop_column("fare_breakdowns", "is_round_trip")
    op.drop_column("fare_breakdowns", "trip_structure")
    op.drop_column("fare_breakdowns", "trip_type")
    op.drop_column("fare_breakdowns", "attendant_fee")
    op.drop_column("fare_breakdowns", "accessibility_fee")
    op.drop_column("fare_breakdowns", "care_assistant_fee")
