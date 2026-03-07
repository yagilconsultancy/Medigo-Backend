"""Add vehicle and document fields

Revision ID: 003
Revises: 002
Create Date: 2026-03-06
"""
from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add vehicle fields to driver_profiles
    op.add_column("driver_profiles", sa.Column("vehicle_color", sa.String(50), nullable=True))
    op.add_column("driver_profiles", sa.Column("vehicle_vin", sa.String(17), nullable=True))
    op.add_column("driver_profiles", sa.Column("vehicle_photo_url", sa.String(500), nullable=True))
    op.add_column("driver_profiles", sa.Column("vehicle_verified", sa.Boolean, server_default="false"))

    # Add expires_at to driver_documents
    op.add_column("driver_documents", sa.Column("expires_at", sa.Date, nullable=True))


def downgrade() -> None:
    op.drop_column("driver_documents", "expires_at")
    op.drop_column("driver_profiles", "vehicle_verified")
    op.drop_column("driver_profiles", "vehicle_photo_url")
    op.drop_column("driver_profiles", "vehicle_vin")
    op.drop_column("driver_profiles", "vehicle_color")
