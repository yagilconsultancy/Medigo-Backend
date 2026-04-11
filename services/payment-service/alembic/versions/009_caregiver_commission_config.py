"""Add caregiver commission config table with specialty-based rates.

Revision ID: 009
Revises: 008
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create caregiver_commission_configs table
    op.create_table(
        "caregiver_commission_configs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("specialty", sa.String(10), nullable=False, unique=True, index=True),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("commission_percent", sa.Numeric(5, 2), nullable=False, comment="Platform commission %"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true", index=True),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # Seed default commission rates for each specialty
    # PSW = Personal Support Worker (20%)
    # RPN = Registered Practical Nurse (20%)
    # RN = Registered Nurse (20%)
    # OT = Occupational Therapist (20%)
    # PT = Physiotherapist (20%)
    op.execute("""
        INSERT INTO caregiver_commission_configs (id, specialty, display_name, commission_percent, is_active)
        VALUES
            (gen_random_uuid(), 'PSW', 'Personal Support Worker', 20.00, true),
            (gen_random_uuid(), 'RPN', 'Registered Practical Nurse', 20.00, true),
            (gen_random_uuid(), 'RN', 'Registered Nurse', 20.00, true),
            (gen_random_uuid(), 'OT', 'Occupational Therapist', 20.00, true),
            (gen_random_uuid(), 'PT', 'Physiotherapist', 20.00, true)
    """)


def downgrade() -> None:
    op.drop_table("caregiver_commission_configs")
