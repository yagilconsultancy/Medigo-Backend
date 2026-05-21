"""add fare_estimate_details jsonb column to rides

Revision ID: 014
Revises: 013
Create Date: 2026-05-21
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "rides",
        sa.Column("fare_estimate_details", JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("rides", "fare_estimate_details")
