"""Add fleet management tables

Revision ID: 007
Revises: 006
Create Date: 2026-03-22
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add contact_person to businesses
    op.add_column("businesses", sa.Column("contact_person", sa.String(255), nullable=True))

    # Fleet applications table
    op.create_table(
        "fleet_applications",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_name", sa.String(255), nullable=False),
        sa.Column("contact_person", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("province", sa.String(50), nullable=True),
        sa.Column("fleet_size", sa.Integer, server_default="0"),
        sa.Column("driver_count", sa.Integer, server_default="0"),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("status", sa.String(30), server_default="pending"),
        sa.Column("reviewed_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text, nullable=True),
        sa.Column("info_request_message", sa.Text, nullable=True),
        sa.Column("business_id", UUID(as_uuid=True), sa.ForeignKey("businesses.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Fleet documents table
    op.create_table(
        "fleet_documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("business_id", UUID(as_uuid=True), sa.ForeignKey("businesses.id"), nullable=True),
        sa.Column("application_id", UUID(as_uuid=True), sa.ForeignKey("fleet_applications.id"), nullable=True),
        sa.Column("document_type", sa.String(50), nullable=False),
        sa.Column("file_key", sa.String(500), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_size", sa.Integer, nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("verification_status", sa.String(20), server_default="pending"),
        sa.Column("verified_by", UUID(as_uuid=True), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.Date, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_fleet_documents_business_id", "fleet_documents", ["business_id"])
    op.create_index("ix_fleet_documents_application_id", "fleet_documents", ["application_id"])

    # Vehicles table
    op.create_table(
        "vehicles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("business_id", UUID(as_uuid=True), sa.ForeignKey("businesses.id"), nullable=False),
        sa.Column("driver_profile_id", UUID(as_uuid=True), sa.ForeignKey("driver_profiles.user_id"), nullable=True),
        sa.Column("vehicle_name", sa.String(255), nullable=True),
        sa.Column("make", sa.String(100), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("year", sa.Integer, nullable=False),
        sa.Column("plate_number", sa.String(20), nullable=False, unique=True),
        sa.Column("color", sa.String(50), nullable=True),
        sa.Column("vin", sa.String(17), nullable=True, unique=True),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("photo_url", sa.String(500), nullable=True),
        sa.Column("mileage", sa.Integer, nullable=True),
        sa.Column("insurance_expiry", sa.Date, nullable=True),
        sa.Column("registration_expiry", sa.Date, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_vehicles_business_id", "vehicles", ["business_id"])
    op.create_index("ix_vehicles_driver_profile_id", "vehicles", ["driver_profile_id"])

    # Vehicle maintenance logs table
    op.create_table(
        "vehicle_maintenance_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("vehicle_id", UUID(as_uuid=True), sa.ForeignKey("vehicles.id"), nullable=False),
        sa.Column("scheduled_date", sa.Date, nullable=False),
        sa.Column("completed_date", sa.Date, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_vehicle_maintenance_logs_vehicle_id", "vehicle_maintenance_logs", ["vehicle_id"])


def downgrade() -> None:
    op.drop_table("vehicle_maintenance_logs")
    op.drop_table("vehicles")
    op.drop_table("fleet_documents")
    op.drop_table("fleet_applications")
    op.drop_column("businesses", "contact_person")
