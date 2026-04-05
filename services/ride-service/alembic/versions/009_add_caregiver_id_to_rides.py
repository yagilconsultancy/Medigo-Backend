"""Add caregiver_id column to rides for scheduled TRANSPORT_CARE_ASSISTANT trips.

Revision ID: 009
Revises: 008
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "rides",
        sa.Column("caregiver_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_rides_caregiver_id", "rides", ["caregiver_id"])


def downgrade() -> None:
    op.drop_index("ix_rides_caregiver_id", table_name="rides")
    op.drop_column("rides", "caregiver_id")
