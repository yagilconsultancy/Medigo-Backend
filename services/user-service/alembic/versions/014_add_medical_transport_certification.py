"""Add medical_transport_certification to driver_profiles.

Revision ID: 014
Revises: 013
"""

import sqlalchemy as sa
from alembic import op

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "driver_profiles",
        sa.Column("medical_transport_certification", sa.String(255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("driver_profiles", "medical_transport_certification")
