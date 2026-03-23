"""Add business_id and driver_id to fare_breakdowns for fleet revenue queries.

Revision ID: 004
Revises: 003
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "fare_breakdowns",
        sa.Column("business_id", UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "fare_breakdowns",
        sa.Column("driver_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_fare_breakdowns_business_id", "fare_breakdowns", ["business_id"])
    op.create_index("ix_fare_breakdowns_driver_id", "fare_breakdowns", ["driver_id"])


def downgrade() -> None:
    op.drop_index("ix_fare_breakdowns_driver_id", table_name="fare_breakdowns")
    op.drop_index("ix_fare_breakdowns_business_id", table_name="fare_breakdowns")
    op.drop_column("fare_breakdowns", "driver_id")
    op.drop_column("fare_breakdowns", "business_id")
