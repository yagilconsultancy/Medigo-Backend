"""caregiver_profiles

Revision ID: 016
Revises: 015
Create Date: 2026-04-10

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision = "016"
down_revision = "015"
branch_label = None
depends_on = None


def upgrade() -> None:
    # Create caregiver_profiles table
    op.create_table(
        "caregiver_profiles",
        sa.Column("user_id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("business_id", UUID(as_uuid=True), nullable=True),
        # Caregiver-specific fields
        sa.Column("specialty", sa.String(30), nullable=False),
        sa.Column("license_number", sa.String(50), nullable=True),
        sa.Column("license_expiry", sa.Date, nullable=True),
        # Account management
        sa.Column("account_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("service_capabilities", JSONB, server_default="[]"),
        sa.Column("is_online", sa.Boolean, nullable=False, server_default="false"),
        # Suspension tracking
        sa.Column("suspension_reason", sa.Text, nullable=True),
        sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("suspended_by", UUID(as_uuid=True), nullable=True),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
        # Personal information
        sa.Column("date_of_birth", sa.Date, nullable=True),
        sa.Column("address", sa.String(500), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("province", sa.String(50), nullable=True),
        sa.Column("postal_code", sa.String(20), nullable=True),
        # Emergency contact
        sa.Column("emergency_contact_name", sa.String(255), nullable=True),
        sa.Column("emergency_contact_phone", sa.String(20), nullable=True),
        # Admin notes
        sa.Column("notes", sa.Text, nullable=True),
        # Stats (denormalized)
        sa.Column("rating", sa.Numeric(3, 2), nullable=False, server_default="5.00"),
        sa.Column("total_assignments", sa.Integer, nullable=False, server_default="0"),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        # Foreign keys
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="SET NULL"),
    )

    # Create index on business_id for fleet queries
    op.create_index(
        "ix_caregiver_profiles_business_id",
        "caregiver_profiles",
        ["business_id"],
    )

    # Create index on account_status for filtering
    op.create_index(
        "ix_caregiver_profiles_account_status",
        "caregiver_profiles",
        ["account_status"],
    )

    # Create index on specialty for filtering
    op.create_index(
        "ix_caregiver_profiles_specialty",
        "caregiver_profiles",
        ["specialty"],
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index("ix_caregiver_profiles_specialty", "caregiver_profiles")
    op.drop_index("ix_caregiver_profiles_account_status", "caregiver_profiles")
    op.drop_index("ix_caregiver_profiles_business_id", "caregiver_profiles")

    # Drop table
    op.drop_table("caregiver_profiles")
