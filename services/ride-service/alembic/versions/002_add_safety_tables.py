"""Add safety tables

Revision ID: 002
Revises: 001
Create Date: 2026-03-06
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "safety_reports",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("reporter_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("reported_user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("ride_id", UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("report_type", sa.String(50), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("status", sa.String(20), server_default="open"),
        sa.Column("resolution", sa.Text, nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "vehicle_checklists",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("driver_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("checklist_date", sa.Date, nullable=False),
        sa.Column("tires_ok", sa.Boolean, server_default="false"),
        sa.Column("brakes_ok", sa.Boolean, server_default="false"),
        sa.Column("lights_ok", sa.Boolean, server_default="false"),
        sa.Column("fluid_levels_ok", sa.Boolean, server_default="false"),
        sa.Column("wheelchair_ramp_ok", sa.Boolean, nullable=True),
        sa.Column("stretcher_mount_ok", sa.Boolean, nullable=True),
        sa.Column("first_aid_kit_ok", sa.Boolean, server_default="false"),
        sa.Column("fire_extinguisher_ok", sa.Boolean, server_default="false"),
        sa.Column("vehicle_clean", sa.Boolean, server_default="false"),
        sa.Column("all_passed", sa.Boolean, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("vehicle_checklists")
    op.drop_table("safety_reports")
