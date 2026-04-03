"""Add booking_channel and facility_id columns to rides.

Revision ID: 008
Revises: 007
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "rides",
        sa.Column("booking_channel", sa.String(30), nullable=False, server_default="mobile_app"),
    )
    op.add_column(
        "rides",
        sa.Column("facility_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_rides_facility_id", "rides", ["facility_id"])


def downgrade() -> None:
    op.drop_index("ix_rides_facility_id", table_name="rides")
    op.drop_column("rides", "facility_id")
    op.drop_column("rides", "booking_channel")
