"""Add admin driver management columns and suspension logs table.

Revision ID: 011
Revises: 010
Create Date: 2026-03-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns to driver_profiles
    op.add_column("driver_profiles", sa.Column("account_status", sa.String(20), nullable=False, server_default="pending"))
    op.add_column("driver_profiles", sa.Column("service_capabilities", JSONB, server_default="[]"))
    op.add_column("driver_profiles", sa.Column("suspension_reason", sa.Text, nullable=True))
    op.add_column("driver_profiles", sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("driver_profiles", sa.Column("suspended_by", UUID(as_uuid=True), nullable=True))
    op.add_column("driver_profiles", sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("driver_profiles", sa.Column("notes", sa.Text, nullable=True))
    op.add_column("driver_profiles", sa.Column("emergency_contact_name", sa.String(255), nullable=True))
    op.add_column("driver_profiles", sa.Column("emergency_contact_phone", sa.String(20), nullable=True))
    op.add_column("driver_profiles", sa.Column("date_of_birth", sa.Date, nullable=True))
    op.add_column("driver_profiles", sa.Column("address", sa.String(500), nullable=True))
    op.add_column("driver_profiles", sa.Column("city", sa.String(100), nullable=True))
    op.add_column("driver_profiles", sa.Column("province", sa.String(50), nullable=True))
    op.add_column("driver_profiles", sa.Column("postal_code", sa.String(20), nullable=True))

    # Set account_status for existing approved drivers
    op.execute(
        sa.text("UPDATE driver_profiles SET account_status = 'active' WHERE is_approved = true")
    )

    # Create driver_suspension_logs table
    op.create_table(
        "driver_suspension_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("driver_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("performed_by", UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("driver_suspension_logs")

    op.drop_column("driver_profiles", "postal_code")
    op.drop_column("driver_profiles", "province")
    op.drop_column("driver_profiles", "city")
    op.drop_column("driver_profiles", "address")
    op.drop_column("driver_profiles", "date_of_birth")
    op.drop_column("driver_profiles", "emergency_contact_phone")
    op.drop_column("driver_profiles", "emergency_contact_name")
    op.drop_column("driver_profiles", "notes")
    op.drop_column("driver_profiles", "deactivated_at")
    op.drop_column("driver_profiles", "suspended_by")
    op.drop_column("driver_profiles", "suspended_at")
    op.drop_column("driver_profiles", "suspension_reason")
    op.drop_column("driver_profiles", "service_capabilities")
    op.drop_column("driver_profiles", "account_status")
